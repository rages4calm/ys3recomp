"""Authored ABI16 files, references and diagnostic/source mutation checks.

No retail process runs. Only live Git verification is mocked; package/build
bindings, all 209 generated fixtures, PCM/WAV bytes and audit hashes are real.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import qualify_abi16 as q
from tests.test_abi15_qualification import Matrix as Matrix15, identity
from tests.test_dsp_qualification import dump, sha


class BaseMatrix(Matrix15):
    def make_module(self, folder, abi):
        path, files = super().make_module(folder, abi)
        value = json.loads(path.read_text())
        value.update(native_contexts=57, unsupported_observations=0)
        dump(path, value)
        return path, files


class Matrix:
    def __init__(self, root):
        self.root = root
        self.old = BaseMatrix(root)
        for path, receipt in zip(self.old.paths, self.old.receipts):
            seed = root / 'authored-seed'
            receipt['input_sha256'][str(seed)] = sha(seed)
            dump(path, receipt)
        for index in (1, 2):
            self.old.runs[index]['scsi'] = {'unknown_commands': 0}
            dump(self.old.paths[index].parent / 'run.stdout', self.old.runs[index])
        self.module = self.old.make_module(root / 'module16', 16)
        self.paths, self.receipts, self.runs = [], [], []
        for old_index, name in ((1, 'new-legacy'), (2, 'new-gear'), (3, 'new-off'), (4, 'new-legacy-ref'), (5, 'new-gear-ref')):
            receipt, run = copy.deepcopy(self.old.receipts[old_index]), copy.deepcopy(self.old.runs[old_index])
            desktop, off, gear = old_index < 4, old_index == 3, old_index in (2, 5)
            folder = root / name
            folder.mkdir()
            previous_binary = Path(receipt['command'][0])
            binary = folder / ('bin/consumer.exe' if desktop else 'bin/headless.exe')
            binary.parent.mkdir(exist_ok=True)
            binary.write_bytes(previous_binary.read_bytes())
            receipt['command'][0] = str(binary)
            receipt['input_sha256'].pop(str(previous_binary))
            receipt['input_sha256'][str(binary)] = sha(binary)
            receipt['tool_identity'] = identity(q.TOOL)
            receipt['tool_identity']['shared_source_identity']['source_files'] = 54
            receipt['tool_identity_after'] = copy.deepcopy(receipt['tool_identity'])
            receipt['audio_contract']['runtime_abi'] = 16
            receipt['audio_selection'] = None if off else copy.deepcopy(q.GEAR if gear else q.LEGACY)
            run['development'].update(enabled=True, memory_write_enabled=True, memory_write_requests=709, memory_bytes_changed=723)
            if not off:
                wav = folder / 'audio.wav'
                wav.write_bytes(Path(receipt['audio_contract']['wav_path']).read_bytes())
                receipt['command'][receipt['command'].index('--audio-out') + 1] = str(wav)
                receipt['audio_contract']['wav_path'] = str(wav)
            if desktop:
                dll = binary.with_name('SDL3.dll')
                dll.write_bytes(previous_binary.with_name('SDL3.dll').read_bytes())
                outputs = {p.name: sha(p) for p in binary.parent.iterdir()}
                package = receipt['desktop_contract']['package_before']
                package.update(binary=str(binary), dll=str(dll), output_files=outputs)
                receipt['desktop_contract']['package_after'] = copy.deepcopy(package)
                for field in ('loaded_sdl_before', 'loaded_sdl_final'):
                    receipt['desktop_contract'][field].update(executable=str(binary), loaded_sdl=str(dll))
                self.old.descriptor(folder, receipt, q.TOOL, self.module, off, gear, False, outputs)
            else:
                outputs = {binary.name: sha(binary)}
                self.old.descriptor(folder, receipt, q.TOOL, self.module, off, gear, False, outputs)
                build_path = Path(receipt['project_build']) / 'build-receipt.json'
                built = json.loads(build_path.read_text())
                built['desktop'] = False
                dump(build_path, built)
                receipt['project_build_receipt_sha256'] = sha(build_path)
            unknown = {'accepted_responses': 1, 'opcodes': [{'opcode': 1, 'attempts': 1}], 'last_command': [1],
                       'origin': {'pc': run['pc'], 'ticks': run['ticks'] - 1, 'mpr': run['mpr'].copy(),
                                  'physical_pc': (run['mpr'][run['pc'] >> 13] << 13) | (run['pc'] & 8191),
                                  'fetch': run['instruction_bytes'].copy()}}
            run.setdefault('scsi', {})['unknown_commands'] = 1
            run['cd_unknown'] = copy.deepcopy(unknown)
            for group in [receipt['checkpoint_status']] + [[receipt[field]] for field in q.ENDPOINTS]:
                for state in group:
                    state['host']['debug_memory'] = {'write_enabled': True, 'write_requests': 709, 'bytes_changed': 723}
                    state['host']['unknown_commands'] = 1
                    state['host']['cd_unknown'] = copy.deepcopy(unknown)
            self.paths.append(folder / 'receipt.json')
            self.receipts.append(receipt)
            self.runs.append(run)
        self.proof_path = root / 'proof16.json'
        self.proof = copy.deepcopy(self.old.proof)
        self.proof.update(tool=copy.deepcopy(self.receipts[0]['tool_identity']),
                          old_manifest={'path': str(self.old.new_module[0]), 'sha256': sha(self.old.new_module[0])},
                          new_manifest={'path': str(self.module[0]), 'sha256': sha(self.module[0])},
                          module_runtime_abi=16,
                          normalization={'only_bytes_from': 'static_assert(abi_version == 15);',
                                         'only_bytes_to': 'static_assert(abi_version == 16);',
                                         'all_other_source_bytes_exact': True, 'all_other_manifest_metadata_exact': True})
        self.proof['files'] = [{'file': name, 'old': {'path': str(self.old.new_module[1][name]), 'sha256': sha(self.old.new_module[1][name])},
                               'new': {'path': str(path), 'sha256': sha(path)},
                               'abi_assertions_replaced': int(name.endswith('.cpp')), 'translated_operations_and_guards_exact': True}
                              for name, path in self.module[1].items()]
        self.expectation_path = root / 'expectation16.json'
        self.write()

    def write(self):
        for path, receipt, run in zip(self.paths, self.receipts, self.runs):
            dump(path, receipt)
            dump(path.parent / 'run.stdout', run)
        dump(self.proof_path, self.proof)
        roles = {'reemission_proof': self.proof_path}
        for timing, new_index, old_index in (('legacy', 3, 1), ('gear', 4, 2)):
            for label, path in ((timing, self.paths[new_index]), ('baseline_' + timing, self.old.paths[old_index])):
                roles.update({label + '_receipt': path, label + '_run': path.parent / 'run.stdout', label + '_wav': path.parent / 'audio.wav'})
        baseline = self.root / 'baseline15-qualified.json'
        dump(baseline, {'passed': True, 'tool': q.previous.TOOL,
                        'evidence_sha256': {str(path): sha(path) for role, path in roles.items() if role.startswith('baseline_')}})
        roles['baseline_qualification'] = baseline
        contract = self.root / 'tool16-qualified.json'
        dump(contract, {'passed': True, 'runtime_abi': 16, 'descriptor_schema': 1, 'tool_identity': q.TOOL})
        roles['tool_contract'] = contract
        upstream = {'result': 'pass', 'revision': q.TOOL['revision'], 'source_sha256': q.TOOL['source_sha256'],
                    'runtime_abi': 16, 'route_sha256': self.receipts[0]['source_route_sha256'], 'module_manifest_sha256': sha(self.module[0])}
        upstream.update({role + '_sha256': sha(path) for role, path in roles.items() if role in q.REF_ROLES | (q.REVIEW_ROLES - {'upstream_qualification'})})
        path = self.root / 'upstream16.json'
        dump(path, upstream)
        roles['upstream_qualification'] = path
        route = {key: self.receipts[0][key] for key in q.ROUTE}
        self.expectation = {'schema': 1, 'kind': 'ys3-reviewed-abi16-matrix', 'tool': copy.deepcopy(q.TOOL), 'route': route,
                            'files': {role: {'path': str(path), 'sha256': sha(path)} for role, path in roles.items()},
                            'qualification_success': 'pass', 'qualification_pointers': {key: '/' + key for key in q.POINTERS},
                            'success_bindings': {role: {'pointer': '/passed', 'value': True} for role in q.REVIEW_ROLES - {'upstream_qualification'}},
                            'reviewed_binding': {'qualified': True, 'tool': q.TOOL, 'route': route, 'execution': q.EXECUTION,
                                                 'cd_origin_is_initial_latch_not_retirement': True, 'no_new_native_coverage_claim': True,
                                                 'independent_scope': 'Authored finite fixture, no hardware or retail execution',
                                                 'evidence_sha256': {role: sha(path) for role, path in roles.items()}}}
        dump(self.expectation_path, self.expectation)

    def descriptor_timing(self, index, timing):
        receipt = self.receipts[index]
        descriptor = Path(receipt['project_descriptor'])
        descriptor.write_text(descriptor.read_text().replace('[module.source]', 'audio_timing=' + json.dumps(timing) + '\n[module.source]'))
        digest = sha(descriptor)
        receipt['project_descriptor_sha256'] = digest
        receipt['project_binding']['descriptor_sha256'] = digest
        for field in ('project_verification_before', 'project_verification_after'):
            receipt[field]['descriptor_sha256'] = digest
        build_path = Path(receipt['project_build']) / 'build-receipt.json'
        built = json.loads(build_path.read_text())
        built['binding']['descriptor_sha256'] = digest
        dump(build_path, built)
        receipt['project_build_receipt_sha256'] = sha(build_path)

    def qualify(self):
        with patch.object(q, 'live_tool', return_value=copy.deepcopy(self.receipts[0]['tool_identity'])):
            return q.qualify_abi16(*self.paths[:3], self.expectation_path)


class Abi16QualificationTests(unittest.TestCase):
    def fixture(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return Matrix(Path(folder.name))

    def test_complete_new16_reference_matrix_retains_diagnostic_and_old15_differences(self):
        result = self.fixture().qualify()
        self.assertTrue(result['passed'])
        self.assertTrue(result['all_cd_unknown_fields_validated_and_exact'])
        self.assertEqual(len(result['measurements']), 42)
        self.assertEqual(result['reemission']['artifacts'], 209)
        self.assertEqual(len(result['reemission']['exact_abi_static_assert_changes']), 208)
        self.assertIn('/scsi/unknown_commands', result['abi15_conservation']['gear']['runner_guest_differences'])

    def test_new_diagnostic_mutations_rejected_without_ignoring_fields(self):
        changes = (lambda d: d.update(accepted_responses=0), lambda d: d.update(extra=True),
                   lambda d: d['opcodes'][0].update(opcode=3), lambda d: d['origin'].update(physical_pc=0),
                   lambda d: d['origin']['mpr'].pop(), lambda d: d['origin'].update(ticks=1 << 64),
                   lambda d: d['origin']['fetch'].__setitem__(0, 256), lambda d: d['origin'].update(pc=True))
        fixture = self.fixture()
        original = copy.deepcopy(fixture.runs[1]['cd_unknown'])
        for change in changes:
            with self.subTest(change=change):
                fixture.runs[1]['cd_unknown'] = copy.deepcopy(original)
                change(fixture.runs[1]['cd_unknown'])
                fixture.write()
                with self.assertRaises((ValueError, KeyError)):
                    fixture.qualify()

    def test_well_formed_diagnostic_mismatch_and_later_clock_are_rejected(self):
        fixture = self.fixture()
        fixture.receipts[4]['checkpoint_status'][8]['host']['cd_unknown']['origin']['fetch'][0] ^= 1
        fixture.write()
        with self.assertRaises(ValueError):
            fixture.qualify()
        fixture = self.fixture()
        fixture.runs[1]['cd_unknown']['origin']['ticks'] = fixture.runs[1]['ticks'] + 1
        fixture.write()
        with self.assertRaises(ValueError):
            fixture.qualify()

    def test_native_pc_mpr_fetch_generations_images_and_original_assists_are_exact(self):
        changes = (lambda f: f.runs[1].update(native_steps=2),
                   lambda f: f.runs[1].update(pc=7),
                   lambda f: f.receipts[4]['checkpoint_status'][0]['host']['cpu']['mpr'].__setitem__(7, 7),
                   lambda f: f.receipts[1]['final_status']['host']['cpu']['instruction_bytes'].__setitem__(0, 9),
                   lambda f: f.receipts[2]['released_status']['host']['cpu']['instruction_generations'].__setitem__(0, 2),
                   lambda f: f.receipts[0]['images'][0].update(png_sha256='d' * 64),
                   lambda f: f.receipts[0].update(memory_edits_replayed=710))
        fixture = self.fixture()
        original = copy.deepcopy((fixture.receipts, fixture.runs))
        for change in changes:
            with self.subTest(change=change):
                fixture.receipts, fixture.runs = copy.deepcopy(original)
                change(fixture)
                fixture.write()
                with self.assertRaises((ValueError, KeyError)):
                    fixture.qualify()

    def test_future_guest_field_cannot_be_silently_discarded(self):
        fixture = self.fixture()
        fixture.receipts[4]['checkpoint_status'][0]['host']['future_irq_state'] = 3
        fixture.write()
        with self.assertRaises(ValueError):
            fixture.qualify()

    def test_one_gear_source_clock_edge_drift_rejected_even_when_pcm_matches(self):
        fixture = self.fixture()
        for index in (1, 4):
            fixture.runs[index]['ticks'] += (21477273 + 44099) // 44100
        fixture.write()
        with self.assertRaisesRegex(ValueError, 'gear_source_clock'):
            fixture.qualify()

    def test_off_requires_absent_pcm_and_no_wav(self):
        fixture = self.fixture()
        fixture.runs[2]['audio_output'] = None
        fixture.write()
        with self.assertRaises(ValueError):
            fixture.qualify()
        fixture = self.fixture()
        (fixture.paths[2].parent / 'audio.wav').write_bytes(b'unexpected')
        with self.assertRaises(ValueError):
            fixture.qualify()

    def test_explicit_headless_gear_matches_packaged_default_and_reports_actual_forms(self):
        fixture = self.fixture()
        fixture.receipts[4]['command'].extend(['--audio-timing', 'gear'])
        fixture.descriptor_timing(4, 'gear')
        fixture.write()
        result = fixture.qualify()
        self.assertEqual(result['gear_timing_bridge'], {'candidate_argv': 'default-omitted', 'candidate_descriptor': 'default-omitted',
                                                       'headless_argv': 'explicit-gear', 'headless_descriptor': 'explicit-gear'})
        fixture = self.fixture()
        result = fixture.qualify()
        self.assertEqual(result['gear_timing_bridge']['headless_argv'], 'default-omitted')
        self.assertEqual(result['gear_timing_bridge']['headless_descriptor'], 'default-omitted')

    def test_explicit_packaged_gear_wrong_headless_timing_and_duplicates_rejected(self):
        fixture = self.fixture()
        original = copy.deepcopy(fixture.receipts)
        mutations = ((1, ['--audio-timing', 'gear']), (4, ['--audio-timing', 'legacy']),
                     (4, ['--audio-timing', 'gear', '--audio-timing', 'gear']), (3, ['--audio-timing', 'gear']))
        for index, arguments in mutations:
            with self.subTest(index=index, arguments=arguments):
                fixture.receipts = copy.deepcopy(original)
                fixture.receipts[index]['command'].extend(arguments)
                fixture.write()
                with self.assertRaises(ValueError):
                    fixture.qualify()
        fixture = self.fixture()
        fixture.descriptor_timing(4, 'legacy')
        fixture.write()
        with self.assertRaisesRegex(ValueError, 'descriptor.reference_explicit_gear'):
            fixture.qualify()
        fixture = self.fixture()
        fixture.descriptor_timing(1, 'gear')
        fixture.write()
        with self.assertRaisesRegex(ValueError, 'packaged default Gear descriptor'):
            fixture.qualify()

    def test_both_hosts_require_current_three_key_selection(self):
        fixture = self.fixture()
        q.receipt_contract(fixture.receipts[3], 'legacy', 'on', False)
        for index in (0, 3):
            with self.subTest(index=index):
                original = fixture.receipts[index]['audio_selection'].copy()
                fixture.receipts[index]['audio_selection'].pop('timing')
                fixture.write()
                with self.assertRaises(ValueError):
                    fixture.qualify()
                fixture.receipts[index]['audio_selection'] = original

    def test_headless_relative_argv_resolves_only_bound_actual_inputs(self):
        fixture = self.fixture()
        for index in (3, 4):
            receipt = fixture.receipts[index]
            receipt['launch_cwd'] = str(fixture.root)
            receipt['command'][1] = 'authored-payload'
            receipt['command'][receipt['command'].index('--bram') + 1] = 'authored-seed'
        fixture.write()
        self.assertTrue(fixture.qualify()['passed'])
        fixture.receipts[4]['launch_cwd'] = str(fixture.root / 'new-gear')
        fixture.write()
        with self.assertRaises((OSError, ValueError, KeyError)):
            fixture.qualify()

    def test_actual_package_and_reference_artifact_hashes_are_rehashed(self):
        fixture = self.fixture()
        Path(fixture.receipts[0]['command'][0]).with_name('SDL3.dll').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            fixture.qualify()
        fixture = self.fixture()
        fixture.paths[4].parent.joinpath('run.stdout').write_text('{}')
        with self.assertRaises(ValueError):
            fixture.qualify()

    def test_wav_argv_must_name_the_actual_bounded_artifact(self):
        fixture = self.fixture()
        receipt = fixture.receipts[0]
        receipt['command'][receipt['command'].index('--audio-out') + 1] = str(fixture.root / 'authored-payload')
        fixture.write()
        with self.assertRaisesRegex(ValueError, 'WAV.actual_argv_destination'):
            fixture.qualify()
        fixture = self.fixture()
        receipt = fixture.receipts[3]
        receipt['command'][receipt['command'].index('--audio-frames') + 1] = '1440001'
        fixture.write()
        with self.assertRaisesRegex(ValueError, 'command.wav_limit'):
            fixture.qualify()

    def test_reemission_proof_and_source_exclusions_cannot_be_relabelled(self):
        fixture = self.fixture()
        fixture.proof['normalization']['only_bytes_from'] = 'abi_version == 13'
        fixture.write()
        with self.assertRaises(ValueError):
            fixture.qualify()
        fixture = self.fixture()
        path = fixture.module[1]['module_part_0000.cpp']
        path.write_text(path.read_text() + '// changed operation\n')
        with self.assertRaises(ValueError):
            fixture.qualify()

    def test_whole_six_byte_exclusion_and_context_contract_are_enforced(self):
        fixture = self.fixture()
        old_manifest, old_files = q.module_files(fixture.old.new_module[0], {})
        new_manifest, new_files = q.module_files(fixture.module[0], {})
        mutations = ({'excluded_physical_ranges': [{'start': 1069880, 'length': 1}]},
                     {'excluded_observations': 3}, {'excluded_retired_hits': 980},
                     {'native_contexts': 56}, {'unsupported_observations': 1})
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                left, right = copy.deepcopy(old_manifest), copy.deepcopy(new_manifest)
                left.update(mutation)
                right.update(mutation)
                with self.assertRaises(ValueError):
                    q.regenerated_module((None, fixture.old.new_module[0], left, old_files),
                                         (None, fixture.module[0], right, new_files))

    def test_before_after_artifact_rehash_detects_late_changes(self):
        fixture = self.fixture()
        calls = []
        def verify(*args):
            calls.append(True)
            if len(calls) == 2:
                path = fixture.module[1]['module_parts.hpp']
                path.write_bytes(path.read_bytes() + b'late mutation')
            return copy.deepcopy(fixture.receipts[0]['tool_identity'])
        with patch.object(q, 'live_tool', side_effect=verify):
            with self.assertRaisesRegex(ValueError, 'evidence changed'):
                q.qualify_abi16(*fixture.paths[:3], fixture.expectation_path)

    def test_expectation_pin_and_binding_cannot_drift(self):
        fixture = self.fixture()
        fixture.expectation['tool']['runtime_abi'] = 15
        dump(fixture.expectation_path, fixture.expectation)
        with self.assertRaises(ValueError):
            fixture.qualify()

    def test_all_three_modes_may_differ_from_old15_but_must_match_new_reference(self):
        fixture = self.fixture()
        for run in fixture.runs:
            run['irq_entries'] = run.get('irq_entries', 0) + 9
            run['native_steps'] += 7
        for receipt in fixture.receipts:
            for group in [receipt['checkpoint_status']] + [[receipt[field]] for field in q.ENDPOINTS]:
                for state in group:
                    state['host']['irq_entries'] = state['host'].get('irq_entries', 0) + 9
                    state['host']['native_steps'] += 7
                    state['host']['cpu']['instruction_generations'][0] += 1
        fixture.write()
        result = fixture.qualify()
        self.assertTrue(result['passed'])
        self.assertIn('/native_steps', result['abi15_conservation']['legacy']['runner_guest_differences'])
        self.assertIn('/host/cpu/instruction_generations/0', result['abi15_conservation']['gear']['observations'][0]['guest_differences'])


if __name__ == '__main__':
    unittest.main()
