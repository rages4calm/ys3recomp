"""Retained launcher receipt layouts preserve hashes and closed-run requirements."""
import copy
import contextlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace, ModuleType
import tempfile
import unittest
import sys
from unittest.mock import Mock, patch
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


def sparse():
    package = extension()['package_after']
    source = dict(revision='a' * 40, source_sha256='b' * 64, source_files=123)
    receipt = dict(passed=True, exit_code=0, child_stopped=True, natural_quit=True,
                   explicit_manifest_quit=True, cut_policy='explicit-milestones',
                   reference=False, native=12345, interpreted=0,
                   project_descriptor='authored/project.toml',
                   project_build_receipt='authored/build-receipt.json',
                   input_bindings={'authored/project.toml': 'c' * 64,
                                   'authored/build-receipt.json': 'd' * 64},
                   package_before=copy.deepcopy(package), package_after=package,
                   fingerprint={'source_context': 'e' * 64})
    return receipt, dict(native_qualified=True, current_package=copy.deepcopy(package), tool=source)


class LauncherReceiptTests(unittest.TestCase):
    def test_sparse_scenario_uses_qualified_tool_and_original_input_digests(self):
        receipt, qualification = sparse()
        descriptor, built, tool, package = launcher.receipt_contract(receipt, qualification)
        self.assertEqual(descriptor, ('authored/project.toml', 'c' * 64))
        self.assertEqual(built, ('authored/build-receipt.json', 'd' * 64))
        self.assertEqual(tool, qualification['tool'])
        self.assertEqual(package, qualification['current_package'])
        source = qualification['tool']
        qualification['tool'] = dict(revision=source['revision'], runtime_abi=29,
                                    shared_source_identity=source, tracked_source_clean=True)
        self.assertEqual(launcher.receipt_contract(receipt, qualification)[2], qualification['tool'])

    def test_sparse_rejects_failed_unclosed_reference_or_non_native_scenarios(self):
        for key, value in [('passed', False), ('exit_code', False), ('exit_code', 1),
                           ('child_stopped', False), ('natural_quit', False),
                           ('explicit_manifest_quit', False), ('cut_policy', 'unknown'),
                           ('reference', True), ('reference', 0), ('native', 0),
                           ('native', True), ('interpreted', 1), ('interpreted', False)]:
            receipt, qualification = sparse(); receipt[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                launcher.receipt_contract(receipt, qualification)

    def test_sparse_rejects_missing_digest_package_or_tool_qualification(self):
        mutations = [lambda r, q: r['input_bindings'].pop(r['project_descriptor']),
                     lambda r, q: r['input_bindings'].update({r['project_build_receipt']: 'invalid'}),
                     lambda r, q: r.update(project_descriptor=''),
                     lambda r, q: r['package_before'].update(changed=True),
                     lambda r, q: q['current_package'].update(changed=True),
                     lambda r, q: q.update(native_qualified=False),
                     lambda r, q: q.pop('tool'),
                     lambda r, q: q['tool'].update(source_sha256='invalid'),
                     lambda r, q: q['tool'].update(source_files=True)]
        for mutate in mutations:
            receipt, qualification = sparse(); mutate(receipt, qualification)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                launcher.receipt_contract(receipt, qualification)
        with self.assertRaises(ValueError): launcher.receipt_contract(sparse()[0])

    def test_one_official_verification_object_builds_command_and_rechecks_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); tool = base/'sdk'; module = base/'module'; module.mkdir()
            for name in ('runtime', 'pcerecomp', 'cmake', 'scripts'):
                (tool/name).mkdir(parents=True)
            (tool/'CMakeLists.txt').write_text('authored synthetic SDK')
            descriptor = base/'project.toml'; descriptor.write_text('authored descriptor')
            source = module/'module.cpp'; source.write_text('authored source')
            identity = dict(revision='a'*40, source_sha256='b'*64, source_files=1)
            selected = dict(revision='a'*40, runtime_abi=29,
                            shared_source_identity=identity, tracked_source_clean=True)
            checked = dict(files={'module_source': source}, identities={'module_source': launcher.sha(source)},
                           descriptor_sha256=launcher.sha(descriptor), tool_identity=identity)
            project = ModuleType('pcerecomp.project')
            project.verify = Mock(return_value=checked)
            def command_for(actual, binary):
                self.assertIs(actual, checked)
                return [str(binary), '--wall-seconds', '600']
            project.command_for = Mock(side_effect=command_for)
            project.source_identity = Mock(return_value=identity)
            project._binding = lambda p: dict(descriptor_sha256=p['descriptor_sha256'])
            package = ModuleType('pcerecomp'); package.project = project
            verifier = ModuleType('scripts.verify_tool')
            verifier.verify = Mock(side_effect=lambda *a: dict(revision='a'*40, runtime_abi=29, tracked_source_clean=True))
            def run_helper(arguments, environment):
                self.assertEqual(arguments[1:4], ['-I', '-B', '-X'])
                prefix = Path(arguments[4].split('=', 1)[1])
                self.assertEqual(list(prefix.iterdir()), [])
                index = arguments.index('-c'); stream = io.StringIO()
                with patch.object(sys, 'argv', ['-c', *arguments[index+2:]]), \
                     patch.object(sys, 'path', list(sys.path)), \
                     patch.dict(sys.modules, {'pcerecomp': package, 'pcerecomp.project': project,
                                              'scripts.verify_tool': verifier}), contextlib.redirect_stdout(stream):
                    exec(compile(arguments[index+1], '<authored-launch-helper>', 'exec'), {})
                return json.loads(stream.getvalue())
            with patch.object(launcher, 'shared', side_effect=run_helper) as invocation:
                plan = launcher.verified_launch(tool, descriptor, base/'authored.exe', selected, os.environ.copy())
            invocation.assert_called_once(); project.verify.assert_called_once_with(descriptor)
            project.command_for.assert_called_once()
            launcher.recheck_inputs(plan)
            source.write_text('changed after verification')
            with self.assertRaises(ValueError): launcher.recheck_inputs(plan)
            source.write_text('authored source'); (module/'unexpected.hpp').write_text('new member')
            with self.assertRaises(ValueError): launcher.recheck_inputs(plan)

    def test_long_replay_receipt_does_not_relax_other_metadata_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'long-route.json'
            file.write_text(json.dumps(extension()) + ' ' * launcher.METADATA_LIMIT,
                            encoding='utf-8')
            with self.assertRaises(ValueError):
                launcher.load(file)
            value = launcher.load_replay_receipt(file)
            self.assertEqual(launcher.receipt_contract(value),
                             launcher.receipt_contract(extension()))

    def test_oversize_replay_is_rejected_before_reading(self):
        with patch.object(Path, 'stat', return_value=SimpleNamespace(
                st_size=launcher.REPLAY_RECEIPT_LIMIT + 1)), \
             patch.object(Path, 'read_text') as read:
            with self.assertRaises(ValueError):
                launcher.load_replay_receipt(Path('oversize-route.json'))
            read.assert_not_called()

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
