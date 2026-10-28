"""Destructive cleanup checks use disposable authored fixtures only."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import clean_build_files as cleanup


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name).resolve()
        self.batch = self.root / '.local/batch-001'
        self.batch.mkdir(parents=True)
        self.obj = self.batch / 'build-native/build/CMakeFiles/game.dir/sample.obj'
        self.obj.parent.mkdir(parents=True)
        self.obj.write_bytes(b'authored disposable object')
        self.qpath = self.batch / 'native-qualified.json'
        self.qpath.write_text(json.dumps({'passed': True, 'evidence_sha256': {'fixture': 'digest'}}))
        self.selection = self.root / '.local/launcher/selection.json'
        self.selection.parent.mkdir()
        self.select()

    def select(self):
        self.selection.write_text(json.dumps({'qualification': {
            'path': str(self.qpath.relative_to(self.root)), 'digest': cleanup.digest(self.qpath)}}))

    def target(self, path=None):
        path = path or self.obj
        info = path.stat()
        return {'path': str(path), 'sha256': cleanup.digest(path),
                'bytes': info.st_size, 'mtime_ns': info.st_mtime_ns}

    def test_delete_unbound_object_and_repeat(self):
        cleanup.remove_target(self.target(), self.root, set())
        self.assertFalse(self.obj.exists())
        self.assertEqual(list(cleanup.candidates(self.root, set())), [])

    def test_protected_object_stays(self):
        with self.assertRaisesRegex(ValueError, 'Refused'):
            cleanup.remove_target(self.target(), self.root, {self.obj})
        self.assertTrue(self.obj.exists())

    def test_changed_object_stays(self):
        target = self.target()
        self.obj.write_bytes(b'changed after review')
        with self.assertRaisesRegex(ValueError, 'changed'):
            cleanup.remove_target(target, self.root, set())
        self.assertTrue(self.obj.exists())

    def test_outside_build_and_executable_stay(self):
        for path in (self.batch / 'source.obj', self.obj.with_suffix('.exe'), self.root / 'outside.obj'):
            path.write_bytes(b'keep')
            with self.assertRaises(ValueError):
                cleanup.remove_target(self.target(path), self.root, set())
            self.assertTrue(path.exists())

    def test_historical_graph_key_and_value_protected(self):
        (self.batch / 'historical.json').write_text(json.dumps({str(self.obj): 'hash',
                                                              'path': str(self.obj.with_suffix('.exe'))}))
        protected, snapshots = cleanup.protection(self.root)
        self.assertIn(self.obj, protected)
        self.assertIn(self.obj.with_suffix('.exe'), protected)
        cleanup.unchanged(snapshots, self.root)
        self.qpath.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'changed'):
            cleanup.unchanged(snapshots, self.root)

    def test_changed_selection_qualification_rejected(self):
        self.qpath.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'changed'):
            cleanup.protection(self.root)

    def test_reparse_attribute_rejected(self):
        real = Path.lstat
        class Fake:
            st_mode = 0o100644
            st_file_attributes = 0x400
        with patch.object(Path, 'lstat', lambda path: Fake() if path == self.obj else real(path)):
            with self.assertRaisesRegex(ValueError, 'reparse'):
                cleanup.safe_path(self.obj, self.root)

    def test_preview_apply_and_noop_report(self):
        output = io.StringIO()
        with patch.object(cleanup, 'ROOT', self.root), patch.object(cleanup, 'ensure_idle'), contextlib.redirect_stdout(output):
            self.assertEqual(cleanup.main(['--preview']), 0)
            self.assertTrue(self.obj.exists())
            self.assertEqual(cleanup.main([]), 0)
            self.assertFalse(self.obj.exists())
            self.assertEqual(cleanup.main([]), 0)
        self.assertIn('nothing removed', output.getvalue())
        receipts = list((self.root / '.local/cleanup').glob('*.jsonl'))
        self.assertEqual(len(receipts), 2)
        self.assertTrue(all(json.loads(p.read_text().splitlines()[-1])['passed'] for p in receipts))

    def test_active_process_and_parent_paths_use_both_slash_styles(self):
        def process(pid, parent, name, command):
            return dict(ProcessId=pid, ParentProcessId=parent, Name=name,
                        ExecutablePath=str(self.root.parent / name), CommandLine=command)
        other = process(1, 0, 'cmake.exe', 'cmake --build ' + str(self.root.parent / 'other/build'))
        child = process(2, 1, 'ninja.exe', 'ninja -j2')
        cleanup.check_processes(self.root, [other, child])
        other['CommandLine'] = 'cmake --build ' + self.batch.as_posix() + '/build-native'
        with self.assertRaisesRegex(ValueError, 'Close this project'):
            cleanup.check_processes(self.root, [child, other])
        other['CommandLine'] = None
        with self.assertRaisesRegex(ValueError, 'Cannot inspect'):
            cleanup.check_processes(self.root, [other])

    def test_inventory_refreshes_exited_process_but_refuses_persistent_unknown(self):
        platform = patch.object(cleanup, 'os', SimpleNamespace(name='nt'))
        platform.start()
        self.addCleanup(platform.stop)
        unknown = dict(ProcessId=7, ParentProcessId=0, Name='ninja.exe',
                       ExecutablePath=None, CommandLine=None)
        bad = SimpleNamespace(stdout=json.dumps([unknown]))
        empty = SimpleNamespace(stdout='[]')
        with patch.object(cleanup.subprocess, 'run', side_effect=[bad, empty]) as query:
            cleanup.ensure_idle(self.root)
            self.assertEqual(query.call_count, 2)
        with patch.object(cleanup.subprocess, 'run', return_value=bad) as query:
            with self.assertRaisesRegex(ValueError, 'Cannot inspect'):
                cleanup.ensure_idle(self.root)
            self.assertEqual(query.call_count, 2)


if __name__ == '__main__':
    unittest.main()
