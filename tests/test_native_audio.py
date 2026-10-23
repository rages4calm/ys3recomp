"""Authored path-bound native/audio evidence; never opens retail inputs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.qualify_native_audio import (qualify_native_audio, tiers, CAPTURE_TOOL,
                                         verify_capture_tool, compare_capture_observations)
from scripts.replay_route import finish_managed_capture, managed_capture_selection
from scripts import qualify_native_audio as native_qualifier
from tests.test_dsp_qualification import DspEvidence, dump, sha


class NativeAudioEvidence:
    def __init__(self, root):
        graph = DspEvidence(root)
        graph.receipts[3] = copy.deepcopy(graph.receipts[2])
        graph.runs[3] = copy.deepcopy(graph.runs[2])
        for flag in ('--hidden', '--unthrottled'):
            command = graph.receipts[3]['command']
            index = command.index(flag)
            del command[index:index + 2]
        graph.package(3, graph.paths[3].parent, {'profile': 'filtered', 'sample_rate': 48000})
        self.paths = graph.paths[2:]
        self.receipts = graph.receipts[2:]
        self.runs = graph.runs[2:]
        self.prefix = 25
        self.root = root
        self.payload = root / 'authored-payload'
        self.payload.write_bytes(b'Authored synthetic payload')
        seed = root / 'authored-seed'
        seed.write_bytes(bytes(2048))
        historical = root / 'authored-historical'
        historical.write_bytes(b'Authored historical executable')
        images = []
        self.protected = {str(p): sha(p) for p in (self.payload, seed, historical)}
        for frame in range(1, 27):
            image = root / f'authored-image-{frame}.png'
            image.write_bytes(('Authored synthetic image ' + str(frame)).encode())
            images.append({'frame': frame, 'png_sha256': sha(image)})
            self.protected[str(image)] = sha(image)
        self.route_path = root / 'route.json'
        route = {'checkpoints': images, 'steps': [{'kind': 'authored-assist', 'expected': [1], 'data': [2]}],
                 'initial_command': ['authored-historical', 'authored-payload', '0', '0', 'mpr', '100', '100', 'hybrid'],
                 'binary_sha256': sha(historical), 'initial_bram_sha256': sha(seed)}
        dump(self.route_path, route)
        self.protected[str(self.route_path)] = sha(self.route_path)
        self.modules = []
        for side, (path, receipt, run) in enumerate(zip(self.paths, self.receipts, self.runs)):
            folder = path.parent
            receipt['audio_contract']['wav_path'] = str(folder / 'audio.wav')
            source = folder / 'module.cpp'
            source.write_text('// Authored synthetic module ' + str(side), encoding='utf-8')
            manifest = folder / 'module.json'
            dump(manifest, {'schema': 1, 'runtime_abi': 13, 'native_instructions_emitted': side + 1,
                            'translation_units': [{'file': 'module.cpp', 'sha256': sha(source)}], 'generated_headers': []})
            self.modules.append(source)
            receipt['source_route'] = str(self.route_path)
            receipt['source_route_sha256'] = sha(self.route_path)
            receipt['source_binary_anchor'] = str(historical)
            receipt['source_binary_sha256'] = sha(historical)
            receipt['initial_bram_sha256'] = sha(seed)
            receipt['command'][1] = str(self.payload)
            receipt['command'] += ['--bram', str(seed), '--dev-port', '0', '--audio-out', str(folder / 'audio.wav'), '--audio-frames', '24']
            receipt['source_command'] = ['authored-historical', 'authored-payload', '0', '0', 'mpr', '100', '100', 'hybrid']
            receipt['images'] = copy.deepcopy(images)
            receipt['input_sha256'] = dict(self.protected, **{receipt['command'][0]: receipt['binary_sha256']})
            state = copy.deepcopy(receipt['final_status'])
            receipt['checkpoint_status'] = []
            for frame in range(1, 27):
                current = copy.deepcopy(state)
                current.update(frame=frame, ticks=frame * 10)
                current['host'].update(native_steps=frame * (1 if side == 0 else 2),
                                       interpreter_steps=frame * (3 if side == 0 else 2), pc=16384)
                current['host']['cpu'].update(mpr=[255, 248, 128, 129, 130, 131, 132, 0],
                                             physical_pc=1048576, instruction_bytes=[234] * 7,
                                             instruction_physical=list(range(1048576, 1048583)),
                                             instruction_generations=[3] * 7)
                receipt['checkpoint_status'].append(current)
            for field in ('before_final_release', 'final_status', 'released_status'):
                receipt[field] = copy.deepcopy(receipt['checkpoint_status'][-1])
            run.update(native_steps=26 * (1 if side == 0 else 2), interpreter_steps=26 * (3 if side == 0 else 2),
                       native_block_steps=2 + side, interpreter_block_steps=3 - side,
                       ticks=260, pc=16384, mpr=[255, 248, 128, 129, 130, 131, 132, 0], instruction_bytes=[234] * 7)
            run['desktop'].update(presented=26, polls=60)
            receipt['desktop_contract']['presentation'] = copy.deepcopy(run['desktop'])
            descriptor = Path(receipt['project_descriptor'])
            with descriptor.open('a', encoding='utf-8') as stream:
                stream.write('\n[module.source]\npath = ' + json.dumps(str(source)) + '\nsha256 = "' + sha(source) + '"\n')
                stream.write('\n[module.manifest]\npath = ' + json.dumps(str(manifest)) + '\nsha256 = "' + sha(manifest) + '"\n')
                stream.write('\n[payload]\npath = ' + json.dumps(str(self.payload)) + '\nsha256 = "' + sha(self.payload) + '"\n')
            built_path = Path(receipt['project_build']) / 'build-receipt.json'
            built = json.loads(built_path.read_text())
            built['binding']['descriptor_sha256'] = sha(descriptor)
            built['binding']['files'] = {'module_source': sha(source), 'module_manifest': sha(manifest),
                                          'module_unit:module.cpp': sha(source), 'payload': sha(self.payload)}
            receipt['project_descriptor_sha256'] = sha(descriptor)
            receipt['project_build_receipt_sha256'] = dump(built_path, built)
            verification = {'schema': 1, 'verified': True, **copy.deepcopy(built['binding'])}
            receipt['project_verification_before'] = verification
            receipt['project_verification_after'] = copy.deepcopy(verification)
            receipt['project_binding'] = copy.deepcopy(built['binding'])
        self.write()

    def write(self):
        for path, receipt, run in zip(self.paths, self.receipts, self.runs):
            dump(path, receipt)
            dump(path.parent / 'run.stdout', run)

    def qualify(self, **kwargs):
        return qualify_native_audio(*self.paths, prefix_frame=self.prefix, **kwargs)


CAPTURE_SOURCE = Path(__file__).resolve().parents[1] / '.deps/pcenginerecomp-capture'


class ManagedNativeAudioEvidence(NativeAudioEvidence):
    """Actual public shared validator, authored files, no runtime execution."""
    def __init__(self, root):
        super().__init__(root)
        self.tool = CAPTURE_SOURCE.resolve()
        route = json.loads(self.route_path.read_text())
        route['initial_command'] += ['--dev-port', '0', '--dev-start-paused', 'on',
                                      '--dev-memory-write', 'on', '--bram', 'authored-seed',
                                      '--video-output', 'continuous']
        patches = [{'frame': 1, 'physical': 4096, 'expected': 'ea' * 6, 'data': '80' * 6},
                   {'frame': 2, 'physical': 4096, 'expected': '80' * 6, 'data': 'ea' * 6}]
        route['assistance'] = {'jump_patch_active': False, 'code_patches': patches}
        route['steps'] = []
        for frame in range(1, 27):
            route['steps'].append({'frames': 1, 'mask': 0, 'target_frame': frame})
            if frame <= 2:
                edit = patches[frame - 1]
                route['steps'].append({'frame': frame, 'memory_write': {'address': edit['physical'],
                                      'expected': edit['expected'], 'data': edit['data']}})
        for entry in route['checkpoints']:
            entry['file'] = f"authored-image-{entry['frame']}.png"
        route['last_status'] = {'frame': 26, 'paused': True, 'host': {'cd_control': {'bram_seeded': True}}}
        dump(self.route_path, route)
        self.captures = []
        for side, (path, receipt, run) in enumerate(zip(self.paths, self.receipts, self.runs)):
            receipt['tool_identity'] = {'revision': CAPTURE_TOOL['revision'], 'runtime_abi': 13,
                'tracked_source_clean': True, 'shared_source_identity': {
                    'revision': CAPTURE_TOOL['revision'], 'source_sha256': CAPTURE_TOOL['source_sha256']}}
            receipt['tool_identity_after'] = copy.deepcopy(receipt['tool_identity'])
            receipt['source_route_sha256'] = sha(self.route_path)
            receipt['input_sha256'][str(self.route_path)] = sha(self.route_path)
            receipt['source_command'] = copy.deepcopy(route['initial_command'])
            receipt['command'] += ['--dev-start-paused', 'on', '--dev-memory-write', 'on', '--video-output', 'continuous']
            descriptor = Path(receipt['project_descriptor'])
            text = descriptor.read_text().replace('[tool]\n', '[tool]\npath = ' + json.dumps(str(self.tool)) + '\n')
            text = text.replace('revision = "' + 'a' * 40 + '"', 'revision = "' + CAPTURE_TOOL['revision'] + '"')
            text = text.replace('source_sha256 = "' + 'b' * 64 + '"', 'source_sha256 = "' + CAPTURE_TOOL['source_sha256'] + '"')
            manifest = self.modules[side].with_name('module.json')
            previous_hash = sha(manifest)
            module = json.loads(manifest.read_text())
            module['excluded_physical_ranges'] = [{'start': 4096, 'length': 6}]
            dump(manifest, module)
            text = text.replace(previous_hash, sha(manifest))
            descriptor.write_text(text, encoding='utf-8')
            build_path = Path(receipt['project_build']) / 'build-receipt.json'
            built = json.loads(build_path.read_text())
            built['binding']['descriptor_sha256'] = sha(descriptor)
            built['binding']['tool'] = {key: CAPTURE_TOOL[key] for key in ('revision', 'source_sha256')}
            built['binding']['files']['module_manifest'] = sha(manifest)
            receipt['project_descriptor_sha256'] = sha(descriptor)
            receipt['project_build_receipt_sha256'] = dump(build_path, built)
            receipt['project_binding'] = copy.deepcopy(built['binding'])
            receipt['project_verification_before'] = {'schema': 1, 'verified': True, **copy.deepcopy(built['binding'])}
            receipt['project_verification_after'] = copy.deepcopy(receipt['project_verification_before'])
            boundary = copy.deepcopy(receipt['checkpoint_status'][24])
            proof = {'status_before': copy.deepcopy(boundary), 'status': boundary,
                     'canonical_readback': [{'address': 4096, 'expected': 'ea' * 6, 'observed': 'ea' * 6}],
                     'retired_instructions': 100}
            window = {'requested_start_frame': 25, 'started': True, 'actual_start_frame': 25,
                      'actual_start_ticks': 250, 'native_steps_before': boundary['host']['native_steps'],
                      'interpreter_steps_before': boundary['host']['interpreter_steps']}
            run['code_capture_window'] = window
            capture_path = path.parent / 'observed-code.json'
            capture = {'schema': 1, 'runtime_abi': 13, 'capacity': 512, 'dropped_instructions': 0,
                       'unreadable_instructions': 0, 'retired_instructions': 4, 'complete': True,
                       'observations': [{'pc': 16384, 'mpr': [255, 248, 128, 129, 130, 131, 132, 0],
                                         'physical': [1048576], 'data': [234],
                                         'native_hits': 1 + side, 'interpreted_hits': 3 - side}]}
            dump(capture_path, capture)
            self.captures.append(capture_path)
            receipt['command'] += ['--code-capture', str(capture_path), '--capture-limit', '512',
                                  '--code-capture-start-frame', '25']
            selected = managed_capture_selection(route, 25, 512)
            receipt['capture_contract'] = finish_managed_capture(capture_path, self.tool, selected, proof, run)
        self.write()


class NativeAudioTests(unittest.TestCase):
    def fixture(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return NativeAudioEvidence(Path(folder.name))

    def test_hash_bound_native_gain_preserves_pcm_wav_all_states(self):
        result = self.fixture().qualify()
        self.assertTrue(result['passed'])
        self.assertEqual(result['images'], 26)
        self.assertEqual(result['endpoint_states'], 3)
        self.assertEqual(result['native_steps_gained'], 26)
        self.assertEqual(result['suffix_native_steps_gained'], 1)
        self.assertTrue(result['pcm_and_bounded_wav_exact'])

    def test_per_checkpoint_and_runner_retirement_conservation(self):
        for mutate in (lambda f: f.runs[1].update(interpreter_steps=53),
                       lambda f: f.runs[1].update(interpreter_block_steps=3),
                       lambda f: f.receipts[1]['checkpoint_status'][5]['host'].update(native_steps=0),
                       lambda f: f.receipts[1]['final_status']['host'].update(native_steps=0)):
            fixture = self.fixture()
            mutate(fixture)
            fixture.write()
            with self.assertRaises(ValueError):
                fixture.qualify()

    def test_guest_source_mpr_device_assist_and_capture_drift_fail(self):
        for mutate in (lambda f: f.runs[1]['device'].update(writes=7),
                       lambda f: f.runs[1]['source'].update(generations=[3, 5]),
                       lambda f: f.runs[1].update(mpr=[0] * 8),
                       lambda f: f.receipts[1]['checkpoint_status'][3]['host']['cpu'].update(instruction_generations=[9] * 7),
                       lambda f: f.receipts[1].update(memory_edits_replayed=3),
                       lambda f: f.runs[1].update(code_capture={'enabled': True}),
                       lambda f: f.receipts[1]['images'][0].update(png_sha256='e' * 64)):
            fixture = self.fixture()
            mutate(fixture)
            fixture.write()
            with self.assertRaises(ValueError):
                fixture.qualify()

    def test_actual_input_package_source_and_wave_tamper_fail(self):
        for role in ('input', 'module', 'binary', 'dll', 'wav', 'descriptor', 'build'):
            fixture = self.fixture()
            receipt = fixture.receipts[1]
            paths = {'input': fixture.payload, 'module': fixture.modules[1],
                     'binary': Path(receipt['command'][0]), 'dll': Path(receipt['command'][0]).with_name('SDL3.dll'),
                     'wav': fixture.paths[1].parent / 'audio.wav', 'descriptor': Path(receipt['project_descriptor']),
                     'build': Path(receipt['project_build']) / 'build-receipt.json'}
            with paths[role].open('ab') as stream:
                stream.write(b'tampered')
            with self.subTest(role=role), self.assertRaises((ValueError, KeyError)):
                fixture.qualify()

    def test_profile_dsp_pcm_and_wav_drift_fail(self):
        for mutate in (lambda f: f.runs[1]['audio_output'].update(pcm_hash=42),
                       lambda f: f.runs[1]['audio_output']['processing'].update(source_frames=99),
                       lambda f: f.runs[1]['audio_output']['processing'].update(profile='filtered-v2'),
                       lambda f: f.receipts[1].update(audio_selection={'profile': 'raw', 'sample_rate': 44100}),
                       lambda f: f.receipts[1]['checkpoint_status'][0]['host']['audio_output'].update(wav_frames=23)):
            fixture = self.fixture()
            mutate(fixture)
            fixture.write()
            with self.assertRaises(ValueError):
                fixture.qualify()

    def test_zero_gain_suffix_only_or_prefix_only_gains_fail(self):
        fixture = self.fixture()
        with self.assertRaises(ValueError):
            fixture.qualify(min_native_gain=2)
        for state in fixture.receipts[1]['checkpoint_status']:
            if state['frame'] == fixture.prefix:
                state['host'].update(native_steps=51, interpreter_steps=49)
        fixture.write()
        with self.assertRaisesRegex(ValueError, 'positive measured native gain'):
            fixture.qualify()

    def test_removed_checkpoint_missing_suffix_and_future_abi_fail(self):
        for mutate in (lambda f: f.receipts[1]['checkpoint_status'].pop(),
                       lambda f: setattr(f, 'prefix', 26),
                       lambda f: f.receipts[0]['tool_identity'].update(runtime_abi=14)):
            fixture = self.fixture()
            mutate(fixture)
            fixture.write()
            with self.assertRaises((ValueError, KeyError)):
                fixture.qualify()

    def test_strict_counters_and_complete_block_pairs(self):
        for value in (True, -1, 1.5, 1 << 64):
            with self.assertRaises(ValueError):
                tiers({'native_steps': value, 'interpreter_steps': 1}, 'malformed')
        for value in ({'native_steps': 2, 'interpreter_steps': 1, 'native_block_steps': 1},
                      {'native_steps': 2, 'interpreter_steps': 1, 'native_block_steps': 3, 'interpreter_block_steps': 0}):
            with self.assertRaises(ValueError):
                tiers(value, 'malformed')

    def test_malformed_source_identity_rejected_even_if_both_receipts_agree(self):
        for mutate in (lambda s: s['host'].update(pc=True),
                       lambda s: s['host']['cpu'].update(mpr=[0] * 7),
                       lambda s: s['host']['cpu'].update(instruction_bytes=[True] * 7),
                       lambda s: s['host']['cpu'].update(instruction_generations=[-1] * 7),
                       lambda s: s['host']['cpu'].update(physical_pc=0),
                       lambda s: s.update(paused=False)):
            fixture = self.fixture()
            for receipt in fixture.receipts:
                mutate(receipt['checkpoint_status'][1])
            fixture.write()
            with self.assertRaises(ValueError):
                fixture.qualify()

    def test_capture_flags_require_separate_review_even_when_equal(self):
        for flag in ('--code-capture', '--capture-start-frame'):
            fixture = self.fixture()
            for receipt in fixture.receipts:
                receipt['command'] += [flag, 'authored-capture']
            fixture.write()
            with self.assertRaisesRegex(ValueError, 'capture-bearing'):
                fixture.qualify()

    def test_recorded_build_binding_cannot_disagree_with_actual_build(self):
        fixture = self.fixture()
        fixture.receipts[1]['project_binding']['files']['module_source'] = 'e' * 64
        fixture.write()
        with self.assertRaisesRegex(ValueError, 'recorded_project_binding'):
            fixture.qualify()

    def test_nullable_guard_and_invented_block_telemetry_fail(self):
        with self.assertRaises(ValueError):
            tiers({'native_steps': 1, 'interpreter_steps': 1, 'guard_misses': None}, 'malformed')
        fixture = self.fixture()
        fixture.receipts[1]['checkpoint_status'][0]['host'].update(native_block_steps=0)
        fixture.write()
        with self.assertRaises(ValueError):
            fixture.qualify()


class CaptureProjectionTests(unittest.TestCase):
    def test_only_per_identity_tier_redistribution_is_projected(self):
        left = {'schema': 1, 'runtime_abi': 13, 'capacity': 2, 'retired_instructions': 5,
                'complete': True, 'dropped_instructions': 0, 'unreadable_instructions': 0,
                'observations': [{'pc': 1, 'mpr': [0] * 8, 'physical': [1], 'data': [234],
                                  'native_hits': 1, 'interpreted_hits': 4}]}
        right = copy.deepcopy(left)
        right['observations'][0].update(native_hits=4, interpreted_hits=1)
        compare_capture_observations(left, right)
        for mutate in (lambda c: c['observations'][0].update(native_hits=5),
                       lambda c: c['observations'][0].update(pc=2),
                       lambda c: c['observations'][0].update(mpr=[1] * 8),
                       lambda c: c['observations'][0].update(data=[128]),
                       lambda c: c.update(capacity=3)):
            changed = copy.deepcopy(right)
            mutate(changed)
            with self.assertRaises(ValueError):
                compare_capture_observations(left, changed)


@unittest.skipUnless((CAPTURE_SOURCE / 'pcerecomp/capture.py').is_file(), 'Pinned public c5 capture dependency required; no retail inputs')
class ActualSharedCaptureNativeTests(unittest.TestCase):
    def fixture(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return ManagedNativeAudioEvidence(Path(folder.name))

    def test_actual_public_source_loader_and_package_bound_capture_gain(self):
        fixture = self.fixture()
        result = fixture.qualify()
        self.assertTrue(result['managed_capture']['enabled'])
        self.assertEqual(result['managed_capture']['old']['retired_instructions'], 4)
        self.assertEqual(result['managed_capture']['new']['window']['native_steps_before'], 50)
        for source in fixture.captures:
            self.assertEqual(result['evidence_sha256'][str(source)], sha(source))

    def test_live_source_tuple_requires_reviewed_revision_and_full_digest(self):
        source = verify_capture_tool({'tool': {'path': str(CAPTURE_SOURCE)}}, CAPTURE_TOOL)
        self.assertEqual(source, CAPTURE_SOURCE.resolve())
        for key in ('revision', 'source_sha256', 'runtime_abi'):
            changed = dict(CAPTURE_TOOL)
            changed[key] = 14 if key == 'runtime_abi' else 'e' * len(changed[key])
            with self.assertRaises(ValueError):
                verify_capture_tool({'tool': {'path': str(CAPTURE_SOURCE)}}, changed)

    def test_capture_window_and_prefix_counter_tampering_rejected(self):
        fixture = self.fixture()
        original = copy.deepcopy(fixture.runs[1])
        for key, changed in (('requested_start_frame', 24), ('started', False), ('actual_start_frame', 26),
                             ('actual_start_ticks', 251), ('native_steps_before', 51), ('interpreter_steps_before', 51)):
            fixture.runs[1] = copy.deepcopy(original)
            fixture.runs[1]['code_capture_window'][key] = changed
            fixture.write()
            with self.subTest(key=key), self.assertRaises(ValueError):
                fixture.qualify()

    def test_fresh_restore_and_source_proof_drift_rejected(self):
        fixture = self.fixture()
        receipt = fixture.receipts[1]
        original = copy.deepcopy(receipt['capture_contract'])
        changes = (lambda p: p['canonical_readback'][0].update(observed='80' * 6),
                   lambda p: p['status_before'].update(frame=24),
                   lambda p: p['status']['host']['cpu'].update(instruction_generations=[4] * 7),
                   lambda p: p.update(retired_instructions=101),
                   lambda p: p['canonical_readback'].append({'address': 42, 'expected': 'ea', 'observed': 'ea'}))
        for change in changes:
            receipt['capture_contract'] = copy.deepcopy(original)
            change(receipt['capture_contract']['start_proof'])
            fixture.write()
            with self.assertRaises(ValueError):
                fixture.qualify()

    def test_actual_raw_file_mutation_and_loss_fail(self):
        fixture = self.fixture()
        path = fixture.captures[1]
        raw = path.read_bytes()
        path.write_bytes(raw + b' ')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            fixture.qualify()
        capture = json.loads(raw)
        capture.update(complete=False, dropped_instructions=1, retired_instructions=5)
        dump(path, capture)
        fixture.receipts[1]['capture_contract']['sha256'] = sha(path)
        fixture.write()
        with self.assertRaises(ValueError):
            fixture.qualify()

    def test_mutation_after_shared_loading_is_caught_by_after_hash(self):
        fixture = self.fixture()
        real_factory = native_qualifier.load_capture_api
        class MutatingLoader:
            def __init__(self, real):
                self.real = real

            def load_capture(self, path):
                loaded = self.real.load_capture(path)
                with Path(path).open('ab') as stream:
                    stream.write(b' ')
                return loaded
        with patch.object(native_qualifier, 'load_capture_api', side_effect=lambda root: MutatingLoader(real_factory(root))):
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                fixture.qualify()

    def test_actual_c5_capture_run_rejects_replaced_packaged_binary(self):
        fixture = self.fixture()
        binary = Path(fixture.receipts[1]['command'][0])
        binary.write_bytes(b'Changed synthetic executable')
        with self.assertRaises(ValueError):
            fixture.qualify()

    def test_original_source_exclusions_cannot_be_dropped_even_with_rebound_manifest(self):
        fixture = self.fixture()
        receipt = fixture.receipts[1]
        module = fixture.modules[1].with_name('module.json')
        previous_hash = sha(module)
        changed = json.loads(module.read_text())
        changed['excluded_physical_ranges'] = []
        dump(module, changed)
        descriptor = Path(receipt['project_descriptor'])
        descriptor.write_text(descriptor.read_text().replace(previous_hash, sha(module)), encoding='utf-8')
        build_path = Path(receipt['project_build']) / 'build-receipt.json'
        built = json.loads(build_path.read_text())
        built['binding']['descriptor_sha256'] = sha(descriptor)
        built['binding']['files']['module_manifest'] = sha(module)
        receipt['project_descriptor_sha256'] = sha(descriptor)
        receipt['project_build_receipt_sha256'] = dump(build_path, built)
        receipt['project_binding'] = copy.deepcopy(built['binding'])
        receipt['project_verification_before'] = {'schema': 1, 'verified': True, **copy.deepcopy(built['binding'])}
        receipt['project_verification_after'] = copy.deepcopy(receipt['project_verification_before'])
        fixture.write()
        with self.assertRaisesRegex(ValueError, 'original_code_exclusions'):
            fixture.qualify()

    def test_shared_valid_observations_cannot_move_hits_between_source_identities(self):
        fixture = self.fixture()
        route = json.loads(fixture.route_path.read_text())
        for side, (receipt, run, path) in enumerate(zip(fixture.receipts, fixture.runs, fixture.captures)):
            capture = json.loads(path.read_text())
            first = capture['observations'][0]
            second = copy.deepcopy(first)
            second.update(pc=16385, physical=[1048577], native_hits=0, interpreted_hits=1 + side)
            first.update(native_hits=1 + side, interpreted_hits=2 if side == 0 else 0)
            capture['observations'].append(second)
            dump(path, capture)
            old = receipt['capture_contract']
            receipt['capture_contract'] = finish_managed_capture(path, fixture.tool,
                managed_capture_selection(route, 25, 512), old['start_proof'], run)
        fixture.write()
        with self.assertRaisesRegex(ValueError, 'exact_source_identities_and_retired_hits'):
            fixture.qualify()


if __name__ == '__main__':
    unittest.main()
