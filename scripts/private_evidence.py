"""Verify compressed private evidence, or restore one explicitly named file."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(stream):
    return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("Nonfinite JSON value: " + value)

    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            invalid(value)
        return number

    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs,
                      parse_constant=invalid, parse_float=finite)


def local_path(root, relative):
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ValueError("Expected a project-relative path")
    path = root / rel
    if not path.resolve().is_relative_to(root):
        raise ValueError("Path escapes the project")
    for item in (path, *path.parents):
        if item.exists() and (item.is_symlink() or item.is_junction()):
            raise ValueError("Linked paths are refused")
        if item == root:
            break
    return path


class Evidence:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.directory = self.root / ".local/evidence-history"
        index = load(self.directory / "index.json")
        if index["schema"] != 1 or Path(index["root"]).resolve() != self.root:
            raise ValueError("Foreign evidence index")
        self.entries = {}
        self.archives = {}
        self.checked = set()
        for name, expected in zip(index["entry_indexes"], index["archives"], strict=True):
            if Path(name).name != name or Path(expected["file"]).name != expected["file"]:
                raise ValueError("Archive/index name escapes its directory")
            record = load(self.directory / name)
            if record.get("passed") is not True:
                raise ValueError("Unverified archive index")
            if any(record[key] != expected[key] for key in ("file", "bytes", "sha256")):
                raise ValueError("Archive index identity differs")
            self.archives[record["file"]] = expected
            for entry in record["entries"]:
                path = local_path(self.root, entry["path"])
                relative = path.relative_to(self.root).as_posix()
                if not re.fullmatch(r"\.local/batch-[0-9]{3}/.+", relative):
                    raise ValueError("Evidence path is outside a private batch")
                key = os.path.normcase(str(path))
                if key in self.entries:
                    raise ValueError("Duplicate archived path")
                self.entries[key] = (record["file"], entry)

    def archive(self, name):
        path = local_path(self.root, ".local/evidence-history/" + name)
        if name not in self.checked:
            expected = self.archives[name]
            with path.open("rb") as stream:
                if path.stat().st_size != expected["bytes"] or digest(stream) != expected["sha256"]:
                    raise ValueError("Archive bytes changed: " + name)
            self.checked.add(name)
        return path

    def hash_file(self, path):
        path = Path(path)
        if path.is_file():
            with path.open("rb") as stream:
                return digest(stream), "loose"
        key = os.path.normcase(str(path))
        if key not in self.entries:
            raise ValueError("File is neither loose nor in retained evidence: " + str(path))
        name, entry = self.entries[key]
        with zipfile.ZipFile(self.archive(name)) as archive:
            with archive.open(entry["path"]) as stream:
                actual = digest(stream)
        if actual != entry["sha256"]:
            raise ValueError("Archived entry changed: " + entry["path"])
        return actual, "archived"

    def restore(self, relative):
        path = local_path(self.root, relative)
        key = os.path.normcase(str(path))
        if key not in self.entries:
            raise ValueError("Path is not in retained evidence")
        name, entry = self.entries[key]
        if path.exists():
            if self.hash_file(path)[0] != entry["sha256"]:
                raise ValueError("Refusing to overwrite a changed file")
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".evidence-restore.tmp")
        created = False
        try:
            h = hashlib.sha256()
            with zipfile.ZipFile(self.archive(name)) as archive:
                with archive.open(entry["path"]) as source, temporary.open("xb") as target:
                    created = True
                    while block := source.read(1024 * 1024):
                        h.update(block)
                        target.write(block)
            if temporary.stat().st_size != entry["bytes"] or h.hexdigest() != entry["sha256"]:
                raise ValueError("Restored bytes differ")
            if path.exists():
                raise ValueError("Restore destination appeared concurrently")
            os.rename(temporary, path)
        finally:
            if created:
                temporary.unlink(missing_ok=True)
        return True

    def verify(self, qualification):
        record = load(qualification)
        if record.get("passed") is not True:
            raise ValueError("Qualification did not pass")
        counts = {"loose": 0, "archived": 0}
        for number, (name, expected) in enumerate(record["evidence_sha256"].items(), 1):
            actual, location = self.hash_file(Path(name))
            if actual != expected:
                raise ValueError("Evidence differs: " + name)
            counts[location] += 1
            if number % 250 == 0:
                print(f"Verified {number} evidence files", flush=True)
        return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify", type=Path, help="verify a qualification without expanding its evidence")
    group.add_argument("--restore", help="restore one project-relative archived path; never overwrite")
    args = parser.parse_args()
    try:
        evidence = Evidence(ROOT)
        if args.verify:
            counts = evidence.verify(args.verify)
            print(json.dumps(dict(passed=True, **counts)))
        else:
            print(json.dumps(dict(passed=True, restored=evidence.restore(args.restore))))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print("Private evidence refused: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
