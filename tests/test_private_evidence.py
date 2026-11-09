import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.private_evidence import Evidence, load


class PrivateEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.history = self.root / ".local/evidence-history"
        self.history.mkdir(parents=True)
        self.relative = ".local/batch-001/wire.jsonl"
        self.payload = b'{"synthetic":true}\n' * 100
        self.hash = hashlib.sha256(self.payload).hexdigest()
        archive = self.history / "proof.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(self.relative, self.payload)
        self.entry = dict(path=self.relative, bytes=len(self.payload), sha256=self.hash)
        identity = dict(file=archive.name, bytes=archive.stat().st_size,
                        sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
        self.record = dict(passed=True, **identity, entries=[self.entry])
        self.index = dict(schema=1, root=str(self.root), archives=[identity],
                          entry_indexes=["proof.json"])
        self.write_indexes()

    def write_indexes(self):
        (self.history / "proof.json").write_text(json.dumps(self.record), encoding="utf-8")
        (self.history / "index.json").write_text(json.dumps(self.index), encoding="utf-8")

    def test_verify_reads_archive_without_expanding_it(self):
        q = self.root / "qualification.json"
        target = self.root / self.relative
        q.write_text(json.dumps(dict(passed=True, evidence_sha256={str(target): self.hash})))
        self.assertEqual(Evidence(self.root).verify(q), dict(loose=0, archived=1))
        self.assertFalse(target.exists())

    def test_restores_exact_file_and_existing_match_is_unchanged(self):
        evidence = Evidence(self.root)
        self.assertTrue(evidence.restore(self.relative))
        self.assertEqual((self.root / self.relative).read_bytes(), self.payload)
        self.assertFalse(evidence.restore(self.relative))

    def test_changed_loose_file_is_never_overwritten(self):
        target = self.root / self.relative
        target.parent.mkdir(parents=True)
        target.write_bytes(b"owner changes")
        with self.assertRaisesRegex(ValueError, "overwrite"):
            Evidence(self.root).restore(self.relative)
        self.assertEqual(target.read_bytes(), b"owner changes")

    def test_existing_temporary_file_is_not_deleted(self):
        target = self.root / self.relative
        target.parent.mkdir(parents=True)
        temporary = target.with_name(target.name + ".evidence-restore.tmp")
        temporary.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            Evidence(self.root).restore(self.relative)
        self.assertEqual(temporary.read_bytes(), b"existing")

    def test_changed_archive_is_refused_before_restore(self):
        with (self.history / "proof.zip").open("ab") as f:
            f.write(b"changed")
        with self.assertRaisesRegex(ValueError, "Archive bytes changed"):
            Evidence(self.root).restore(self.relative)
        self.assertFalse((self.root / self.relative).exists())

    def test_entry_hash_mismatch_leaves_no_destination(self):
        self.entry["sha256"] = "0" * 64
        self.write_indexes()
        with self.assertRaisesRegex(ValueError, "Restored bytes differ"):
            Evidence(self.root).restore(self.relative)
        self.assertFalse((self.root / self.relative).exists())
        self.assertFalse(list((self.root / ".local/batch-001").glob("*.tmp")))

    def test_escape_and_absolute_restore_are_refused(self):
        for path in ("../outside", str(self.root / "outside")):
            with self.assertRaises(ValueError):
                Evidence(self.root).restore(path)

    def test_duplicate_paths_and_wrong_private_prefix_are_refused(self):
        self.record["entries"].append(dict(self.entry))
        self.write_indexes()
        with self.assertRaisesRegex(ValueError, "Duplicate archived path"):
            Evidence(self.root)
        self.record["entries"] = [dict(self.entry, path="xlocal/batch-001/wire.jsonl")]
        self.write_indexes()
        with self.assertRaisesRegex(ValueError, "outside a private batch"):
            Evidence(self.root)

    def test_strict_json_rejects_duplicates_and_nonfinite_values(self):
        path = self.root / "bad.json"
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":1e9999}'):
            path.write_text(text)
            with self.assertRaises(ValueError):
                load(path)


if __name__ == "__main__":
    unittest.main()
