"""Retained launcher receipt layouts preserve hashes and closed-run requirements."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import play_local as launcher


def extension():
    identity = {'revision': 'a' * 40, 'runtime_abi': 17}
    package = {'binary': 'authored.exe', 'output_files': {'authored.exe': 'b' * 64}}
    return {'kind': 'ys3-reset-extension-replay', 'passed': True, 'exit_code': 0,
            'child_stopped': True, 'natural_quit': True,
            'project_descriptor': {'path': 'authored/project.toml', 'sha256': 'c' * 64},
            'project_build_receipt': {'path': 'authored/build-receipt.json', 'sha256': 'd' * 64},
            'tool_identity_before': identity, 'tool_identity_after': copy.deepcopy(identity),
            'package_before': package, 'package_after': copy.deepcopy(package)}


class LauncherReceiptTests(unittest.TestCase):
    def test_structured_extension_preserves_all_explicit_bindings(self):
        value = extension()
        descriptor, built, identity, package = launcher.receipt_contract(value)
        self.assertEqual(descriptor, ('authored/project.toml', 'c' * 64))
        self.assertEqual(built, ('authored/build-receipt.json', 'd' * 64))
        self.assertEqual(identity, value['tool_identity_after'])
        self.assertEqual(package, value['package_after'])

    def test_legacy_receipt_keeps_original_project_and_package_checks(self):
        value = {'passed': True, 'exit_code': 0, 'project_descriptor': 'authored.toml',
                 'project_descriptor_sha256': 'a' * 64, 'project_build': 'build',
                 'project_build_receipt_sha256': 'b' * 64, 'tool_identity': {'runtime_abi': 16},
                 'desktop_contract': {'package_after': {'binary': 'authored.exe'}}}
        descriptor, built, identity, package = launcher.receipt_contract(value)
        self.assertEqual(descriptor, ('authored.toml', 'a' * 64))
        self.assertEqual(Path(built[0]), Path('build/build-receipt.json'))
        self.assertEqual(built[1], 'b' * 64)
        self.assertEqual(identity, value['tool_identity'])
        self.assertEqual(package, value['desktop_contract']['package_after'])

    def test_failed_noninteger_or_unclosed_extension_is_rejected(self):
        for field, bad in [('passed', False), ('exit_code', False), ('exit_code', 0.0),
                           ('exit_code', 1), ('child_stopped', False), ('natural_quit', False)]:
            value = extension(); value[field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                launcher.receipt_contract(value)

    def test_missing_unknown_and_invalid_artifact_fields_are_rejected(self):
        for name in ('project_descriptor', 'project_build_receipt'):
            for mutation in (lambda x: x.pop('sha256'), lambda x: x.update(extra='unexpected'),
                             lambda x: x.update(path=''), lambda x: x.update(path=12),
                             lambda x: x.update(sha256='invalid')):
                value = extension(); mutation(value[name])
                with self.subTest(name=name), self.assertRaises(ValueError):
                    launcher.receipt_contract(value)

    def test_changed_tool_identity_or_package_is_rejected(self):
        for field in ('tool_identity_after', 'package_after'):
            value = extension(); value[field]['unexpected'] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                launcher.receipt_contract(value)

    def test_structured_receipt_cannot_fall_back_to_legacy_fields(self):
        value = extension(); value.pop('project_build_receipt')
        value.update(project_build='legacy', project_build_receipt_sha256='d' * 64)
        with self.assertRaises(KeyError):
            launcher.receipt_contract(value)

    def test_bound_file_still_requires_exact_digest_and_qualification_membership(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'authored.txt'; file.write_text('authored fixture')
            digest = launcher.sha(file); graph = {str(file.resolve()): digest}
            self.assertEqual(launcher.bound(file, digest, graph), file.resolve())
            with self.assertRaises(ValueError): launcher.bound(file, '0' * 64, graph)
            with self.assertRaises(ValueError): launcher.bound(file, digest, {})
            file.write_text('changed fixture')
            with self.assertRaises(ValueError): launcher.bound(file, digest, graph)

    def test_failure_returns_error_before_any_launch_or_folder_open(self):
        with patch.object(launcher, 'prepare', side_effect=ValueError('changed binding')), \
             patch('sys.argv', ['play_local.py', '--info']), \
             patch.object(launcher.subprocess, 'run') as run:
            self.assertEqual(launcher.main(), 1)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
