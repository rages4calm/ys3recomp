"""Authored package and loader-provenance fixtures; no game or SDK bytes."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.package_checks import (inspect_loaded_sdl, packaged_environment,
                                    sha256, verify_package)


class PackageFixture(unittest.TestCase):
    def setUp(self):
        scratch = Path('.local/batch-004/temp')
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.bin = self.root / 'package'
        self.bin.mkdir()
        self.binary = self.bin / 'pce-consumer.exe'
        self.binary.write_bytes(b'authored executable fixture')
        self.dll = self.bin / 'SDL3.dll'
        self.dll.write_bytes(b'authored library fixture')
        self.built = {
            'schema': 1, 'kind': 'pce-consumer-build', 'desktop': True,
            'binary': str(self.binary), 'binary_sha256': sha256(self.binary),
            'output_files': {p.name: sha256(p) for p in self.bin.iterdir()},
        }


class PackageReceiptTests(PackageFixture):
    def test_official_adjacent_package_is_bound_by_hash(self):
        result = verify_package(self.built, self.binary)
        self.assertEqual(result['binary'], str(self.binary))
        self.assertEqual(result['dll'], str(self.dll))
        self.assertEqual(result['dll_sha256'], sha256(self.dll))
        self.assertEqual(result['output_files'], self.built['output_files'])
        self.assertTrue(result['official_desktop_build'])

    def test_nonofficial_or_nondesktop_receipts_rejected(self):
        for key, value in (('desktop', False), ('desktop', 1),
                           ('kind', 'unbound-build'), ('schema', 2)):
            invalid = copy.deepcopy(self.built)
            invalid[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                verify_package(invalid, self.binary)

    def test_binary_drift_or_receipt_selecting_another_binary_rejected(self):
        other = self.root / 'other.exe'
        other.write_bytes(self.binary.read_bytes())
        invalid = copy.deepcopy(self.built)
        invalid['binary'] = str(other)
        with self.assertRaises(ValueError):
            verify_package(invalid, self.binary)
        self.binary.write_bytes(b'changed executable')
        with self.assertRaises(ValueError):
            verify_package(self.built, self.binary)

    def test_dll_tampering_rejected(self):
        self.dll.write_bytes(b'tampered library')
        with self.assertRaises(ValueError):
            verify_package(self.built, self.binary)

    def test_missing_or_directory_dll_rejected(self):
        self.dll.unlink()
        with self.assertRaises(ValueError):
            verify_package(self.built, self.binary)
        self.dll.mkdir()
        with self.assertRaises(ValueError):
            verify_package(self.built, self.binary)

    def test_dll_must_be_pinned_and_complete_output_set_exact(self):
        invalid = copy.deepcopy(self.built)
        invalid['output_files'].pop('SDL3.dll')
        with self.assertRaises(ValueError):
            verify_package(invalid, self.binary)
        (self.bin / 'unexpected.dll').write_bytes(b'unreceipted output')
        with self.assertRaises(ValueError):
            verify_package(self.built, self.binary)

    def test_symlink_to_external_dll_rejected_even_with_matching_bytes(self):
        external = self.root / 'external.dll'
        external.write_bytes(self.dll.read_bytes())
        self.dll.unlink()
        try:
            self.dll.symlink_to(external)
        except OSError as exc:
            self.skipTest(f'Creating an authored symlink is unavailable: {exc}')
        with self.assertRaises(ValueError):
            verify_package(self.built, self.binary)


class ChildEnvironmentTests(PackageFixture):
    def test_removes_all_loader_fallbacks_and_retains_exact_path_evidence(self):
        sdk = self.root / 'sdk'
        sdk.mkdir()
        (sdk / 'SDL3.dll').write_bytes(b'authored SDK fixture')
        system = self.root / 'system'
        system.mkdir()
        entries = ['', '.', 'relative', str(self.bin), str(sdk), str(system)]
        original = os.pathsep.join(entries)
        source = {'Path': original, 'SDL_AUDIODRIVER': 'dummy',
                  'sdl_videodriver': 'dummy', 'SDL_RENDER_DRIVER': 'software',
                  'KEEP_VALUE': 'retained'}
        child, evidence = packaged_environment(self.binary, source)
        self.assertEqual(child, {'Path': str(system), 'KEEP_VALUE': 'retained'})
        self.assertEqual(source['Path'], original)
        self.assertEqual(evidence['original_path'], original)
        self.assertEqual(evidence['child_path'], child['Path'])
        self.assertEqual([item['entry'] for item in evidence['removed_entries']], entries[:-1])
        self.assertTrue(all(item['reason'] for item in evidence['removed_entries']))
        self.assertEqual(evidence['removed_sdl_driver_overrides'], {
            'SDL_AUDIODRIVER': 'dummy', 'sdl_videodriver': 'dummy',
            'SDL_RENDER_DRIVER': 'software'})

    def test_quoted_sdk_directory_is_also_removed(self):
        system = self.root / 'system'
        system.mkdir()
        quoted = f'"{self.bin}"'
        child, evidence = packaged_environment(
            self.binary, {'PATH': os.pathsep.join([quoted, str(system)])})
        self.assertEqual(child['PATH'], str(system))
        self.assertEqual(evidence['removed_entries'][0]['entry'], quoted)

    def test_absent_ambiguous_or_fully_removed_path_rejected(self):
        for source in ({}, {'Path': str(self.root), 'PATH': str(self.root)},
                       {'PATH': os.pathsep.join(['', '.', str(self.bin)])}):
            with self.subTest(source=source), self.assertRaises(ValueError):
                packaged_environment(self.binary, source)


@unittest.skipUnless(os.name == 'nt', 'Windows live-module inspection contract')
class LiveModuleBindingTests(PackageFixture):
    def inspect(self, result, pid=123):
        with patch('scripts.package_checks.subprocess.check_output',
                   return_value=json.dumps(result)) as process:
            proof = inspect_loaded_sdl(pid, self.dll, self.binary)
        argv = process.call_args.args[0]
        self.assertIn('-NonInteractive', argv)
        self.assertIn('Get-Process -Id 123', argv[-1])
        self.assertEqual(process.call_args.kwargs['timeout'], 15)
        return proof

    def fixture(self):
        return {'pid': 123, 'executable': str(self.binary), 'sdl': [str(self.dll)]}

    def test_actual_process_and_adjacent_module_hashes_bound(self):
        proof = self.inspect(self.fixture())
        self.assertEqual(proof['pid'], 123)
        self.assertEqual(proof['executable'], str(self.binary))
        self.assertEqual(proof['binary_sha256'], sha256(self.binary))
        self.assertEqual(proof['loaded_sdl'], str(self.dll))
        self.assertEqual(proof['dll_sha256'], sha256(self.dll))
        self.assertTrue(proof['adjacent_package_loaded'])

    def test_wrong_pid_or_executable_rejected(self):
        other = self.root / 'other.exe'
        other.write_bytes(self.binary.read_bytes())
        for key, value in (('pid', 124), ('executable', str(other))):
            result = self.fixture()
            result[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect(result)

    def test_wrong_missing_or_multiple_loaded_dlls_rejected(self):
        other = self.root / 'SDL3.dll'
        other.write_bytes(self.dll.read_bytes())
        for loaded in ([], [str(other)], [str(self.dll), str(other)]):
            result = self.fixture()
            result['sdl'] = loaded
            with self.subTest(loaded=loaded), self.assertRaises(ValueError):
                self.inspect(result)

    def test_nonpositive_and_boolean_process_ids_rejected_before_subprocess(self):
        with patch('scripts.package_checks.subprocess.check_output') as process:
            for pid in (0, -1, True, '123'):
                with self.subTest(pid=pid), self.assertRaises(ValueError):
                    inspect_loaded_sdl(pid, self.dll, self.binary)
        process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
