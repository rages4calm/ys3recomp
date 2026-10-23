"""Authored, media-free upstream identity and publication-contract checks."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("verify_tool", ROOT / "scripts/verify_tool.py")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)
AUDIT_SPEC = importlib.util.spec_from_file_location("audit_public", ROOT / "scripts/audit_public.py")
AUDIT = importlib.util.module_from_spec(AUDIT_SPEC)
AUDIT_SPEC.loader.exec_module(AUDIT)


class ToolIdentityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ys3-synthetic-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "--quiet")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.header = self.root / "runtime/include/pce/runtime.hpp"
        self.header.parent.mkdir(parents=True)
        self.header.write_text("inline constexpr unsigned abi_version = 12;\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Authored fixture")
        self.revision = self.git("rev-parse", "HEAD")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE, text=True).strip()

    def test_exact_clean_source_and_abi_pass(self):
        self.assertEqual(VERIFY.verify(self.root, self.revision, 12), {
            "revision": self.revision, "runtime_abi": 12, "tracked_source_clean": True})

    def test_wrong_revision_rejected(self):
        with self.assertRaisesRegex(ValueError, "revision mismatch"):
            VERIFY.verify(self.root, "0" * 40, 12)

    def test_dirty_tracked_source_rejected(self):
        self.header.write_text("inline constexpr unsigned abi_version = 12; // edited\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "tracked source is dirty"):
            VERIFY.verify(self.root, self.revision, 12)

    def test_staged_source_change_rejected(self):
        self.header.write_text("inline constexpr unsigned abi_version = 13;\n", encoding="utf-8")
        self.git("add", ".")
        with self.assertRaisesRegex(ValueError, "tracked source is dirty"):
            VERIFY.verify(self.root, self.revision, 12)

    def test_wrong_committed_abi_rejected(self):
        self.header.write_text("inline constexpr unsigned abi_version = 13;\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Different synthetic ABI")
        with self.assertRaisesRegex(ValueError, "runtime ABI mismatch"):
            VERIFY.verify(self.root, self.git("rev-parse", "HEAD"), 12)

    def test_hidden_index_change_rejected(self):
        self.git("update-index", "--assume-unchanged", "runtime/include/pce/runtime.hpp")
        self.header.write_text("inline constexpr unsigned abi_version = 12; // hidden edit\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "assume-unchanged"):
            VERIFY.verify(self.root, self.revision, 12)

    def test_nested_root_and_short_identity_rejected(self):
        with self.assertRaisesRegex(ValueError, "checkout root"):
            VERIFY.verify(self.root / "runtime", self.revision, 12)
        with self.assertRaisesRegex(ValueError, "full lowercase Git commit"):
            VERIFY.verify(self.root, self.revision[:7], 12)

    def test_explicit_clean_revision_override(self):
        (self.root / "authored.txt").write_text("A different authored revision.\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "Authored development revision")
        next_revision = self.git("rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "revision mismatch"):
            VERIFY.verify(self.root, self.revision, 12)
        self.assertEqual(VERIFY.verify(self.root, next_revision, 12)["revision"], next_revision)


class ManifestTests(unittest.TestCase):
    def test_published_identity_and_budget(self):
        manifest = json.loads((ROOT / "toolchain.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["tool"]["runtime_abi"], 12)
        self.assertEqual(manifest["disposable_output_budget_bytes"], 1073741824)
        for item in manifest["inputs"].values():
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(item["access"], "read-only")


class PublicationAuditTests(unittest.TestCase):
    def test_only_authored_paths_pass(self):
        self.assertTrue(AUDIT.allowed_path("src/module_bundle.cpp.in"))
        self.assertTrue(AUDIT.allowed_path("tests/test_synthetic.py"))
        for path in (".local/route.json", "src/game.bin", "screenshots/frame.png", "src/module.json", "../README.md"):
            with self.subTest(path=path):
                self.assertFalse(AUDIT.allowed_path(path))

    def test_private_content_and_generated_source_rejected(self):
        personal_path = ("C:" + chr(92) + "Users" + chr(92) + "Example" + chr(92) + "private").encode()
        private_uuid = "-".join(("12345678", "1234", "1234", "1234", "123456789abc")).encode()
        generated = b"// " + b"Generated private source; regenerate from the snapshot."
        for content in (personal_path, private_uuid, generated, b"binary" + bytes([0])):
            with self.subTest(content=content):
                self.assertTrue(AUDIT.inspect_content("README.md", content))
        self.assertEqual(AUDIT.inspect_content("README.md", b"Authored public source.\n"), [])


if __name__ == "__main__":
    unittest.main()
