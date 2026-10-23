"""Verify the intended immutable upstream source and runtime ABI before building."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
IMPLEMENTATION_TREES = ("runtime", "pcerecomp", "cmake", "scripts")
IGNORED_PRIVATE_OR_CACHE = {".local", ".deps", ".research", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
    )
    return result.stdout.strip()


def verify(tool_root: Path, expected_revision: str, expected_abi: int) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_revision):
        raise ValueError("Expected revision must be an explicit full lowercase Git commit ID")
    tool_root = tool_root.resolve(strict=True)
    if Path(git(tool_root, "rev-parse", "--show-toplevel")).resolve() != tool_root:
        raise ValueError("Tool root must be the upstream checkout root")
    actual_revision = git(tool_root, "rev-parse", "HEAD")
    if actual_revision != expected_revision:
        raise ValueError(f"Upstream revision mismatch: expected {expected_revision}, found {actual_revision}")
    # These index flags can conceal local edits from ordinary Git status/diff.
    flags = git(tool_root, "ls-files", "-v").splitlines()
    if any(line and (line[0].islower() or line[0] == "S") for line in flags):
        raise ValueError("Upstream index has assume-unchanged or skip-worktree flags")
    if git(tool_root, "status", "--porcelain=v1", "--untracked-files=no"):
        raise ValueError("Upstream tracked source is dirty; commit or restore it before using an identity override")
    # Include ignored files: an ignore rule must not hide a header, Python module
    # or build fragment that can shadow the intended committed implementation.
    untracked = set(filter(None, git(tool_root, "ls-files", "--others", "-z", "--", *IMPLEMENTATION_TREES).split("\0")))
    ignored = set(filter(None, git(tool_root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--", *IMPLEMENTATION_TREES).split("\0")))
    shadow_files = sorted(name for name in untracked if not (
        name in ignored and set(Path(name).parts) & IGNORED_PRIVATE_OR_CACHE
    ))
    if shadow_files:
        raise ValueError("Upstream has untracked implementation source: " + ", ".join(shadow_files[:8]))
    header = (tool_root / "runtime/include/pce/runtime.hpp").read_text(encoding="utf-8")
    versions = re.findall(r"inline\s+constexpr\s+unsigned\s+abi_version\s*=\s*(\d+)\s*;", header)
    if versions != [str(expected_abi)]:
        raise ValueError(f"Upstream runtime ABI mismatch: expected {expected_abi}, found {versions}")
    return {"revision": actual_revision, "runtime_abi": expected_abi, "tracked_source_clean": True}


def main() -> int:
    manifest = json.loads((ROOT / "toolchain.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-root", type=Path, default=ROOT / manifest["tool"]["checkout"])
    parser.add_argument("--expected-revision", default=manifest["tool"]["revision"])
    parser.add_argument("--expected-abi", type=int, default=manifest["tool"]["runtime_abi"])
    parser.add_argument("--expected-source-sha256", help="exact source digest through the shared consumer API")
    args = parser.parse_args()
    try:
        identity = verify(args.tool_root, args.expected_revision, args.expected_abi)
        source_hash = args.expected_source_sha256
        if source_hash is None and args.expected_revision == manifest['tool']['revision']:
            source_hash = manifest['tool'].get('source_sha256')
        if source_hash is not None:
            if not re.fullmatch(r'[0-9a-f]{64}', source_hash):
                raise ValueError('Expected source SHA256 must be a full lowercase digest')
            env = dict(os.environ, PYTHONPATH=str(args.tool_root.resolve()),
                       PYTHONSAFEPATH='1', PYTHONDONTWRITEBYTECODE='1')
            shared = json.loads(subprocess.check_output(
                [sys.executable, '-m', 'pcerecomp.project', 'identity', str(args.tool_root.resolve())],
                env=env, text=True, timeout=30))
            if shared['source_sha256'] != source_hash or shared['revision'] != args.expected_revision:
                raise ValueError('Shared consumer source identity differs from the intended pin')
            identity['shared_source_identity'] = shared
        print(json.dumps(identity, sort_keys=True))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Tool verification rejected: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
