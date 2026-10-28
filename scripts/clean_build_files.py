"""Repeatable cleanup of unbound compiler intermediates; --preview deletes nothing.

Read qualification metadata for exclusions, without repeatedly hashing all game
data. Never remove batch directories, executables, source, captures or inputs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BATCH = re.compile(r"batch-\d{3}")
EXTENSIONS = {".obj", ".o", ".pch", ".gch", ".ilk", ".idb"}


def say(message):
    print(message, flush=True)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_path(path, root):
    """Refuse links/junctions at every ancestor, including the workspace."""
    path, root = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Target outside cleanup domain: " + str(path))
    for item in (path, *path.parents):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Link/reparse path refused: " + str(item))
    if path.resolve() != path:
        raise ValueError("Resolved path differs: " + str(path))
    return path


def referenced_paths(value):
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str) and Path(item).is_absolute():
            yield Path(os.path.abspath(item))


def protection(root):
    local = root / ".local"
    selection_path = safe_path(local / "launcher/selection.json", root)
    selection_bytes = selection_path.read_bytes()
    binding = json.loads(selection_bytes)["qualification"]
    qpath = safe_path(root / binding["path"], local)
    qbytes = qpath.read_bytes()
    if hashlib.sha256(qbytes).hexdigest() != binding["digest"]:
        raise ValueError("Selected qualification changed")
    q = json.loads(qbytes)
    if not (q.get("passed") is True or q.get("result") == "pass") or not q.get("evidence_sha256"):
        raise ValueError("Selected qualification must pass and contain its protection graph")
    documents = {selection_path, qpath}
    for batch in sorted(local.glob("batch-*")):
        if not BATCH.fullmatch(batch.name):
            continue
        safe_path(batch, local)
        documents.update(batch.glob("*.json"))
        for folder in ("qualification", "publication", "cleanup", "policy"):
            directory = batch / folder
            if directory.is_dir():
                safe_path(directory, local)
                documents.update(directory.glob("*.json"))
    legacy_plan = local / "cleanup-20261023/plan.json"
    if legacy_plan.exists():
        documents.add(legacy_plan)
    protected, snapshots = set(), {}
    for index, document in enumerate(sorted(documents), 1):
        safe_path(document, local)
        raw = document.read_bytes()
        snapshots[document] = hashlib.sha256(raw).hexdigest()
        protected.add(document)
        protected.update(referenced_paths(json.loads(raw)))
        if index % 25 == 0:
            say(f"  Protection metadata: {index}/{len(documents)} documents")
    if selection_path.read_bytes() != selection_bytes or qpath.read_bytes() != qbytes:
        raise ValueError("Launcher selection changed during review")
    return protected, snapshots


def ensure_idle(root):
    if os.name != "nt":
        raise ValueError("Real cleanup requires Windows process inspection")
    command = "$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine) | ConvertTo-Json -Compress"
    for attempt in range(2):
        result = subprocess.run(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                                 "-Command", command], capture_output=True, text=True,
                                check=True, timeout=30)
        processes = json.loads(result.stdout) if result.stdout.strip() else []
        if isinstance(processes, dict):
            processes = [processes]
        try:
            check_processes(root, processes)
            return
        except ValueError as error:
            if attempt or not str(error).startswith('Cannot inspect'):
                raise
            say('  A process exited or could not be inspected; refreshing inventory once...')


def check_processes(root, processes):
    relevant = re.compile(r"(pce-consumer|cmake|ninja|cl|clang|clang\+\+|link|lld-link)\.exe", re.I)
    by_pid = {item['ProcessId']: item for item in processes}
    root_pattern = re.compile(re.escape(str(root).replace('\\', '/').casefold().rstrip('/'))
                              + r'''(?=[/\s"']|$)''')
    for process in processes:
        if not relevant.fullmatch(process['Name']):
            continue
        if not process.get('ExecutablePath') or not process.get('CommandLine'):
            raise ValueError("Cannot inspect active game/build process: " + process['Name'])
        cursor, visited = process, set()
        while cursor and cursor['ProcessId'] not in visited:
            visited.add(cursor['ProcessId'])
            text = (str(cursor.get('ExecutablePath') or '') + ' ' + str(cursor.get('CommandLine') or ''))
            if root_pattern.search(text.replace('\\', '/').casefold()):
                raise ValueError("Close this project's game/build processes: " + process['Name'])
            cursor = by_pid.get(cursor['ParentProcessId'])


def candidates(root, protected):
    local = root / ".local"
    for batch in sorted(local.glob("batch-*")):
        if not BATCH.fullmatch(batch.name):
            continue
        safe_path(batch, local)
        say("  Checking compiler files: " + batch.name)
        for build in sorted(batch.glob("build*")):
            if not build.is_dir():
                continue
            safe_path(build, batch)
            for directory, dirs, files in os.walk(build, followlinks=False):
                parent = safe_path(Path(directory), batch)
                for name in dirs:
                    safe_path(parent / name, batch)
                if "CMakeFiles" not in parent.relative_to(build).parts:
                    continue
                for name in sorted(files):
                    path = parent / name
                    if path.suffix.casefold() not in EXTENSIONS:
                        continue
                    safe_path(path, batch)
                    if path in protected or not stat.S_ISREG(path.lstat().st_mode):
                        continue
                    info = path.stat()
                    yield {"path": str(path), "sha256": digest(path),
                           "bytes": info.st_size, "mtime_ns": info.st_mtime_ns}


def unchanged(snapshots, root):
    for path, expected in snapshots.items():
        safe_path(path, root)
        if digest(path) != expected:
            raise ValueError("Protection metadata changed: " + str(path))


def remove_target(target, root, protected):
    path = safe_path(Path(target["path"]), root / ".local")
    relative = path.relative_to(root / ".local")
    if (len(relative.parts) < 4 or not BATCH.fullmatch(relative.parts[0])
            or not relative.parts[1].startswith("build") or "CMakeFiles" not in relative.parts[2:-1]
            or path.suffix.casefold() not in EXTENSIONS or path in protected):
        raise ValueError("Refused cleanup target: " + str(path))
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_size != target["bytes"]
            or info.st_mtime_ns != target["mtime_ns"] or digest(path) != target["sha256"]):
        raise ValueError("Compiler file changed during review: " + str(path))
    path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true", help="Review only; delete nothing")
    parser.add_argument("--no-pause", action="store_true", help="Root CMD: return without pausing")
    args = parser.parse_args(argv)
    started = time.monotonic()
    try:
        say("[1/4] Reading protection metadata (game data is not bulk-hashed)...")
        protected, snapshots = protection(ROOT)
        say("[2/4] Checking for active game/build processes...")
        ensure_idle(ROOT)
        say("[3/4] Reviewing disposable compiler files...")
        targets = list(candidates(ROOT, protected))
        total = sum(item["bytes"] for item in targets)
        say(f"  {len(targets)} removable files, {total / 1048576:.1f} MiB.")
        unchanged(snapshots, ROOT)
        if args.preview:
            say(f"Preview complete in {time.monotonic() - started:.1f}s; nothing removed.")
            return 0
        ensure_idle(ROOT)
        receipt_dir = ROOT / ".local/cleanup"
        if receipt_dir.exists():
            safe_path(receipt_dir, ROOT)
        else:
            receipt_dir.mkdir()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        receipt = receipt_dir / ("compiler-" + stamp + ".jsonl")
        say("[4/4] Removing reviewed compiler files; receipt: " + str(receipt))
        with receipt.open("x", encoding="utf-8", buffering=1) as stream:
            stream.write(json.dumps({"kind": "compiler-cleanup", "targets": targets,
                                     "protection_metadata": {str(p): h for p, h in snapshots.items()}}) + "\n")
            for index, target in enumerate(targets, 1):
                remove_target(target, ROOT, protected)
                stream.write(json.dumps({"removed": target["path"]}) + "\n")
                if index % 25 == 0 or index == len(targets):
                    say(f"  Removed {index}/{len(targets)} files")
            unchanged(snapshots, ROOT)
            stream.write(json.dumps({"passed": True, "removed": len(targets), "bytes": total}) + "\n")
        say(f"Finished in {time.monotonic() - started:.1f}s. Removed {total / 1048576:.1f} MiB.")
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        say("Cleanup stopped: " + str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
