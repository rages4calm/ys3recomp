"""Verify the intended immutable upstream source and runtime ABI before building."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


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
    header = (tool_root / "runtime/include/pce/runtime.hpp").read_text(encoding="utf-8")
    versions = re.findall(r"inline\s+constexpr\s+unsigned\s+abi_version\s*=\s*(\d+)\s*;", header)
    if versions != [str(expected_abi)]:
        raise ValueError(f"Upstream runtime ABI mismatch: expected {expected_abi}, found {versions}")
    return {"revision": actual_revision, "runtime_abi": expected_abi, "tracked_source_clean": True}


def main() -> int:
    manifest = json.loads((ROOT / "toolchain.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-root", type=Path, default=ROOT / ".deps/pcenginerecomp")
    parser.add_argument("--expected-revision", default=manifest["tool"]["revision"])
    parser.add_argument("--expected-abi", type=int, default=manifest["tool"]["runtime_abi"])
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.tool_root, args.expected_revision, args.expected_abi), sort_keys=True))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Tool verification rejected: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
