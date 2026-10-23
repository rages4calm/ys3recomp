"""Read-only publication audit of staged authored text; stage intended files first."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
ROOT_FILES = {"AGENTS.md", "README.md", "LICENSE", "CMakeLists.txt", "toolchain.json", ".gitignore", ".gitattributes",
              "Play Ys III.cmd", "Native Files.cmd", "Clean Old Build Files.cmd"}
PATTERNS = {
    "credential-like content": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"),
    "personal absolute path": re.compile(rb"(?:[A-Za-z]:[\\/]Users[\\/][^\s\"'<>]+|/[U]sers/[^\s\"'<>]+|/[h]ome/[^\s\"'<>]+)"),
    "chat or other private UUID": re.compile(rb"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
    "generated private game source": re.compile(rb"(?m)^// Generated private source;"),
}


def allowed_path(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        return False
    if name in ROOT_FILES:
        return True
    if len(path.parts) != 2 or path.name.startswith("."):
        return False
    directory = path.parts[0]
    return (
        (directory == "docs" and path.suffix == ".md")
        or (directory == "scripts" and path.suffix == ".py")
        or (directory == "tests" and path.name.startswith("test_") and path.suffix == ".py")
        or (directory == "src" and path.suffix in {".cpp", ".in"})
    )


def inspect_content(name: str, data: bytes) -> list[str]:
    problems = []
    if not allowed_path(name):
        problems.append("path outside authored source allowlist")
    if len(data) > 256 * 1024:
        problems.append("file exceeds 256 KiB authored source cap")
    if b"\0" in data:
        problems.append("binary content")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        problems.append("non-UTF8 content")
    for description, pattern in PATTERNS.items():
        if pattern.search(data):
            problems.append(description)
    return problems


def main() -> int:
    try:
        entries = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=ROOT).split(b"\0")
        problems, count, total = [], 0, 0
        for entry in filter(None, entries):
            metadata, raw_name = entry.split(b"\t", 1)
            mode, object_id, stage = metadata.split()
            name = raw_name.decode("utf-8")
            if mode != b"100644" and mode != b"100755":
                problems.append(f"{name}: non-regular index entry")
                continue
            if stage != b"0":
                problems.append(f"{name}: unresolved index merge")
                continue
            data = subprocess.check_output(["git", "cat-file", "blob", object_id.decode("ascii")], cwd=ROOT)
            count += 1
            total += len(data)
            problems.extend(f"{name}: {problem}" for problem in inspect_content(name, data))
        if count == 0:
            problems.append("No staged/tracked source; stage the intended authored files before auditing")
        if total > 2 * 1024 * 1024:
            problems.append("Authored source exceeds 2 MiB baseline cap")
    except (OSError, ValueError, UnicodeDecodeError, subprocess.CalledProcessError) as error:
        print(f"Publication audit failed: {error}", file=sys.stderr)
        return 1
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"Audited {count} staged/tracked files, {total} bytes; {len(problems)} problems")
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
