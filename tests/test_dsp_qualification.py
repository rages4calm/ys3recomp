"""Authored schema-2 DSP evidence graphs; no retail media or runtime DSP."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import wave

from scripts.qualify_dsp import qualify_dsp
from tests.test_desktop_qualification import desktop_fixture
from tests.test_dsp_contract import hosted


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8')
    return sha(path)


class DspEvidence:
    def __init__(self, root, filtered_cap=24):
        self.root = root
        self.tool = {'revision': 'a' * 40, 'source_sha256': 'b' * 64, 'runtime_abi': 13}
        _, base, _, run = desktop_fixture()
        self.receipts = [copy.deepcopy(base) for _ in range(4)]
        self.runs = [copy.deepcopy(run) for _ in range(4)]
        self.paths = []
        raw = copy.deepcopy(base['audio_contract']['validated_output'])
        processed = dict(copy.deepcopy(raw), sample_rate=48000, frames=100 * 160 // 147,
                         mixed_nonzero=90, peak=900, pcm_hash=999,
                         wav_frames=min(108, filtered_cap), wav_truncated=108 > filtered_cap,
                         processing={'profile': 'filtered-v1', 'source_rate': 44100,
                                     'source_frames': 100, 'raw_pcm_hash': raw['pcm_hash'],
                                     'raw_peak': raw['peak'], 'raw_mixed_nonzero': raw['mixed_nonzero'],
                                     'resampler': 'sinc64-q30-v1', 'latency_source_frames': 31,
                                     'tail_flushed': False})
        self.route = {key: hashlib.sha256(key.encode()).hexdigest() for key in
                      ('source_route_sha256', 'source_binary_sha256', 'initial_bram_sha256')}
        identity = {'revision': self.tool['revision'], 'runtime_abi': 13, 'tracked_source_clean': True,
                    'shared_source_identity': {'revision': self.tool['revision'], 'source_sha256': self.tool['source_sha256']}}
        for index, role in enumerate(('old', 'raw', 'processed', 'reference')):
            folder = root / role
            folder.mkdir()
            path = folder / 'receipt.json'
            self.paths.append(path)
            receipt, current = self.receipts[index], self.runs[index]
            core = copy.deepcopy(raw if index < 2 else processed)
            chosen = {'profile': 'raw' if index < 2 else 'filtered', 'sample_rate': core['sample_rate']}
            if index != 0:
                receipt['audio_selection'] = chosen
            receipt.update(self.route)
            receipt['tool_identity'] = copy.deepcopy(identity)
            receipt['tool_identity_after'] = copy.deepcopy(identity)
            receipt['source_command'] = ['historical', 'payload', '0', '0', 'mpr', '100', '100', 'hybrid']
            receipt['command'] = receipt['source_command'] + ['--audio-output', 'on']
            if index != 0:
                receipt['command'] += ['--audio-profile', chosen['profile'], '--audio-rate', str(chosen['sample_rate'])]
            receipt['audio_contract'].update(runtime_abi=13, mode='on', headless_pcm_only=index == 3,
                                              wav_frame_limit=20 if index < 2 else filtered_cap,
                                              validated_output=copy.deepcopy(core))
            full = hosted(core) if index < 3 else copy.deepcopy(core)
            current['audio_output'] = copy.deepcopy(full)
            for field in ('before_final_release', 'final_status', 'released_status'):
                receipt[field]['host']['audio_output'] = copy.deepcopy(full)
            receipt['checkpoint_status'][0]['host']['audio_output'] = copy.deepcopy(full)
            if index < 3:
                self.package(index, folder, chosen)
                receipt['desktop_contract']['audio_output'] = copy.deepcopy(full)
                receipt['desktop_contract']['presentation'] = copy.deepcopy(current['desktop'])
            else:
                receipt.pop('desktop_contract')
                current.pop('desktop')
                binary = folder / 'headless-fixture.exe'
                binary.write_bytes(b'authored headless fixture')
                receipt['command'][0] = str(binary)
                receipt['binary_sha256'] = sha(binary)
            receipt['input_sha256'] = {'authored-protected-input': 'protected-hash', receipt['command'][0]: receipt['binary_sha256']}
            self.write_wave(folder / 'audio.wav', core['sample_rate'], core['wav_frames'], index >= 2)
            receipt['audio_contract'].update(wav_path=str(folder / 'audio.wav'), wav_sha256=sha(folder / 'audio.wav'),
                                              wav_bytes=(folder / 'audio.wav').stat().st_size)
        self.independent = {'result': True, 'source_sha256': self.tool['source_sha256'], 'runtime_abi': 13,
                            'scope': 'Authored independent filter-stage and FIR-vector evidence'}
        self.expectation_path = root / 'dsp-expectation.json'
        self.manifest = {'schema': 2, 'kind': 'ys3-reviewed-dsp-profile', 'tool': self.tool,
                         'selection': {'profile': 'filtered', 'sample_rate': 48000}, 'route': self.route,
                         'wav_frame_limit': filtered_cap, 'raw_bridge': {}, 'files': {},
                         'qualification_success': True, 'gear_success': True,
                         'qualification_pointers': {key: '/' + key for key in
                             ('result', 'tool_revision', 'source_sha256', 'runtime_abi', 'route_sha256', 'profile', 'sample_rate',
                              'run_sha256', 'receipt_sha256', 'wav_sha256', 'independent_gear_sha256')},
                         'gear_pointers': {'result': '/result', 'source_sha256': '/source_sha256', 'runtime_abi': '/runtime_abi'},
                         'reviewed_binding': {'qualified': True, 'tool': self.tool, 'route': self.route,
                             'selection': {'profile': 'filtered', 'sample_rate': 48000},
                             'execution': {'tier': 'hybrid', 'audio': 'on', 'raw_bridge_host': 'packaged-desktop',
                                           'candidate_host': 'packaged-desktop', 'reference_host': 'headless'},
                             'raw_bridge': {}, 'evidence_sha256': {}, 'independent_scope': self.independent['scope']}}
        self.write()

    @staticmethod
    def write_wave(path, rate, frames, processed):
        with wave.open(str(path), 'wb') as stream:
            stream.setnchannels(2)
            stream.setsampwidth(2)
            stream.setframerate(rate)
            stream.writeframes((b'\1\0\xff\xff' if processed else b'\0\0\0\0') * frames)

    def package(self, index, folder, chosen):
        receipt = self.receipts[index]
        build = folder / 'build'
        binary = build / 'bin/pce-consumer.exe'
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b'authored executable fixture')
        dll = binary.with_name('SDL3.dll')
        dll.write_bytes(b'authored DLL fixture')
        outputs = {file.name: sha(file) for file in binary.parent.iterdir()}
        binary_hash = sha(binary)
        receipt['binary_sha256'] = binary_hash
        receipt['command'][0] = str(binary)
        receipt['command'] += ['--hidden', 'on', '--unthrottled', 'on']
        package = {'binary': str(binary), 'binary_sha256': binary_hash, 'dll': str(dll),
                   'dll_sha256': sha(dll), 'output_files': outputs, 'official_desktop_build': True}
        live = {'pid': 1234, 'executable': str(binary), 'binary_sha256': binary_hash,
                'loaded_sdl': str(dll), 'dll_sha256': sha(dll), 'adjacent_package_loaded': True, 'inspection': 'authored fixture'}
        proof = receipt['desktop_contract']
        proof.update(package_before=package, package_after=copy.deepcopy(package),
                     loaded_sdl_before=live, loaded_sdl_final=copy.deepcopy(live))
        proof['environment']['original_path'] = str(folder / 'system')
        proof['environment']['child_path'] = str(folder / 'system')
        descriptor = folder / 'project.toml'
        descriptor.write_text('schema = 1\n[tool]\nrevision = "' + self.tool['revision'] +
            '"\nsource_sha256 = "' + self.tool['source_sha256'] + '"\nruntime_abi = 13\n' +
            '[runtime]\ntier = "hybrid"\naudio = "on"\naudio_profile = "' + chosen['profile'] +
            '"\naudio_rate = ' + str(chosen['sample_rate']) + '\n', encoding='utf-8')
        binding = {'descriptor_sha256': sha(descriptor), 'tool': {key: self.tool[key] for key in ('revision', 'source_sha256')},
                   'files': {'authored': 'hash'}, 'revision_override': False}
        built = {'schema': 1, 'kind': 'pce-consumer-build', 'binding': binding, 'desktop': True,
                 'binary': str(binary), 'binary_sha256': binary_hash, 'output_files': outputs}
        build_receipt = build / 'build-receipt.json'
        dump(build_receipt, built)
        verification = {'schema': 1, 'verified': True, **copy.deepcopy(binding)}
        receipt.update(project_descriptor=str(descriptor), project_descriptor_sha256=sha(descriptor),
                       project_build=str(build), project_build_receipt_sha256=sha(build_receipt),
                       project_verification_before=verification, project_verification_after=copy.deepcopy(verification),
                       project_output_files_before=outputs, project_output_files_after=outputs.copy(),
                       shared_project_run_used=False, project_execution_mode='shared-verify-then-consumer-route')

    def all_audio(self, index):
        receipt = self.receipts[index]
        return [self.runs[index]['audio_output'], receipt['audio_contract']['validated_output'],
                *([receipt['desktop_contract']['audio_output']] if index < 3 else []),
                *(receipt[name]['host']['audio_output'] for name in ('before_final_release', 'final_status', 'released_status')),
                *(state['host']['audio_output'] for state in receipt['checkpoint_status'])]

    def write(self):
        for path, receipt, run in zip(self.paths, self.receipts, self.runs):
            dump(path, receipt)
            dump(path.parent / 'run.stdout', run)
        roles = {'run': self.paths[3].parent / 'run.stdout', 'receipt': self.paths[3],
                 'wav': self.paths[3].parent / 'audio.wav', 'independent_gear': self.root / 'independent.json',
                 'upstream_qualification': self.root / 'upstream.json'}
        dump(roles['independent_gear'], self.independent)
        self.qualification = {'result': True, 'tool_revision': self.tool['revision'], 'source_sha256': self.tool['source_sha256'],
                              'runtime_abi': 13, 'route_sha256': self.route['source_route_sha256'], 'profile': 'filtered', 'sample_rate': 48000,
                              **{role + '_sha256': sha(roles[role]) for role in ('run', 'receipt', 'wav', 'independent_gear')}}
        dump(roles['upstream_qualification'], self.qualification)
        self.manifest['files'] = {role: {'path': str(path), 'sha256': sha(path)} for role, path in roles.items()}
        self.manifest['raw_bridge'] = {role + '_sha256': sha(path) for role, path in
                                      (('receipt', self.paths[1]), ('run', self.paths[1].parent / 'run.stdout'),
                                       ('wav', self.paths[1].parent / 'audio.wav'))}
        self.manifest['reviewed_binding']['raw_bridge'] = self.manifest['raw_bridge'].copy()
        self.manifest['reviewed_binding']['evidence_sha256'] = {role: sha(path) for role, path in roles.items()}
        dump(self.expectation_path, self.manifest)

    def qualify(self):
        return qualify_dsp(*self.paths[:3], self.expectation_path)


class DspQualificationTests(unittest.TestCase):
    def test_raw_bridge_processed_reference_and_separate_measurements(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = DspEvidence(Path(folder))
            result = fixture.qualify()
            self.assertTrue(result['raw_bridge_exact'])
            self.assertTrue(result['raw_source_projection_exact'])
            self.assertEqual(result['measurements']['old_raw']['final']['pcm_hash'], 123456)
            self.assertEqual(result['measurements']['processed']['final']['pcm_hash'], 999)
            self.assertEqual(result['measurements']['processed']['final']['frames'], 108)

    def test_guest_native_source_input_image_and_assist_mutations_fail(self):
        changes = (lambda f: f.runs[2]['device'].update(writes=7),
                   lambda f: f.runs[2].update(native_steps=99, interpreter_steps=1),
                   lambda f: f.runs[2].update(native_block_steps=4, interpreter_block_steps=1),
                   lambda f: f.runs[2].update(guard_misses=1),
                   lambda f: f.runs[2]['source'].update(generations=[3, 5]),
                   lambda f: f.receipts[2]['input_sha256'].update(authored_new_input='changed'),
                   lambda f: f.receipts[2]['images'][0].update(png_sha256='changed'),
                   lambda f: f.receipts[2].update(memory_edits_replayed=3),
                   lambda f: f.receipts[2]['checkpoint_status'][0]['host'].update(unknown_guest=1))
        for change in changes:
            with tempfile.TemporaryDirectory() as folder:
                fixture = DspEvidence(Path(folder))
                change(fixture)
                fixture.write()
                with self.assertRaises(ValueError):
                    fixture.qualify()

    def test_raw_projection_counters_hash_peak_and_mix_must_match_old_source(self):
        changes = (('psg_nonzero', 11), ('adpcm_nonzero', 21), ('cdda_nonzero', 31),
                   ('processing.raw_pcm_hash', 44), ('processing.raw_peak', 44), ('processing.raw_mixed_nonzero', 44))
        for key, changed in changes:
            with tempfile.TemporaryDirectory() as folder:
                fixture = DspEvidence(Path(folder))
                for index in (2, 3):
                    for audio in fixture.all_audio(index):
                        if key.startswith('processing.'):
                            audio['processing'][key.split('.')[1]] = changed
                        else:
                            audio[key] = changed
                fixture.write()
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'raw_projection'):
                    fixture.qualify()

    def test_frame_floor_latency_profile_tail_and_unknown_fields_fail(self):
        changes = (lambda a: a.update(frames=107), lambda a: a['processing'].update(source_frames=99),
                   lambda a: a['processing'].update(latency_source_frames=0),
                   lambda a: a['processing'].update(profile='filtered-v2'),
                   lambda a: a['processing'].update(resampler='linear'),
                   lambda a: a['processing'].update(tail_flushed=True),
                   lambda a: a['processing'].update(new_field=1), lambda a: a.update(new_pcm_field=1))
        for change in changes:
            with tempfile.TemporaryDirectory() as folder:
                fixture = DspEvidence(Path(folder))
                change(fixture.runs[2]['audio_output'])
                fixture.write()
                with self.assertRaises(ValueError):
                    fixture.qualify()

    def test_processed_checkpoint_requires_new_reference_not_old_or_guessed_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = DspEvidence(Path(folder))
            fixture.receipts[3]['checkpoint_status'][0]['host']['audio_output']['pcm_hash'] = 123456
            fixture.write()
            with self.assertRaisesRegex(ValueError, 'processed_reference_pcm'):
                fixture.qualify()

    def test_checkpoint_output_pending_is_bounded_and_endpoint_is_strict(self):
        for pending in (0, 29):
            with tempfile.TemporaryDirectory() as folder:
                fixture = DspEvidence(Path(folder))
                host = fixture.receipts[2]['checkpoint_status'][0]['host']['audio_output']['host']
                host.update(submitted_frames=108 - pending, dropped_frames=108 - pending)
                fixture.write()
                self.assertTrue(fixture.qualify()['passed'])
                fixture.receipts[2]['final_status']['host']['audio_output']['host'].update(submitted_frames=107, dropped_frames=107)
                fixture.write()
                with self.assertRaises(ValueError):
                    fixture.qualify()

    def test_unsaturated_checkpoint_wav_drain_is_not_compared_as_generated_pcm(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = DspEvidence(Path(folder), filtered_cap=200)
            audio = fixture.receipts[2]['checkpoint_status'][0]['host']['audio_output']
            audio.update(wav_frames=79, wav_truncated=False)
            audio['host'].update(submitted_frames=79, dropped_frames=79)
            fixture.write()
            self.assertTrue(fixture.qualify()['passed'])
            audio['wav_frames'] = 80
            fixture.write()
            with self.assertRaises(ValueError):
                fixture.qualify()

    def test_loss_queue_bad_device_telemetry_and_submission_mismatch_fail(self):
        changes = (lambda a: a.update(discarded_frames=1), lambda a: a['host'].update(queued_frames=1),
                   lambda a: a['host'].update(peak_queue_frames=1), lambda a: a['host'].update(input_rate=44100),
                   lambda a: a['host'].update(device_format=0), lambda a: a['host'].update(device_channels=True),
                   lambda a: a['host'].update(dropped_frames=107))
        for change in changes:
            with tempfile.TemporaryDirectory() as folder:
                fixture = DspEvidence(Path(folder))
                change(fixture.runs[2]['audio_output'])
                fixture.write()
                with self.assertRaises(ValueError):
                    fixture.qualify()

    def test_pinned_reference_hash_links_and_independent_result_are_required(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = DspEvidence(Path(folder))
            (fixture.paths[3].parent / 'run.stdout').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'artifact hash mismatch'):
                fixture.qualify()
        for key, changed in (('result', False), ('source_sha256', 'e' * 64), ('runtime_abi', 14)):
            with tempfile.TemporaryDirectory() as folder:
                fixture = DspEvidence(Path(folder))
                fixture.independent[key] = changed
                fixture.write()
                with self.assertRaisesRegex(ValueError, 'independent_qualification'):
                    fixture.qualify()

    def test_upstream_review_must_link_tool_route_profile_rate_and_artifacts(self):
        for key, changed in (('result', False), ('tool_revision', 'e' * 40), ('source_sha256', 'e' * 64),
                             ('runtime_abi', 14), ('route_sha256', 'e' * 64), ('profile', 'raw'),
                             ('sample_rate', 44100), ('run_sha256', 'e' * 64), ('receipt_sha256', 'e' * 64),
                             ('wav_sha256', 'e' * 64), ('independent_gear_sha256', 'e' * 64)):
            with tempfile.TemporaryDirectory() as folder:
                fixture = DspEvidence(Path(folder))
                fixture.qualification[key] = changed
                artifact = fixture.root / 'upstream.json'
                actual = dump(artifact, fixture.qualification)
                fixture.manifest['files']['upstream_qualification']['sha256'] = actual
                fixture.manifest['reviewed_binding']['evidence_sha256']['upstream_qualification'] = actual
                dump(fixture.expectation_path, fixture.manifest)
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'upstream_qualification'):
                    fixture.qualify()

    def test_tool_identity_official_build_descriptor_and_raw_selection_are_bound(self):
        changes = (lambda f: f.receipts[2]['tool_identity'].update(revision='e' * 40),
                   lambda f: f.receipts[3]['tool_identity_after'].update(runtime_abi=14),
                   lambda f: f.receipts[1].update(audio_selection={'profile': 'filtered', 'sample_rate': 48000}),
                   lambda f: f.receipts[2].update(project_descriptor_sha256='e' * 64),
                   lambda f: f.receipts[2]['desktop_contract']['loaded_sdl_final'].update(dll_sha256='changed'))
        for change in changes:
            with tempfile.TemporaryDirectory() as folder:
                fixture = DspEvidence(Path(folder))
                change(fixture)
                fixture.write()
                with self.assertRaises(ValueError):
                    fixture.qualify()

    def test_wave_hash_geometry_and_versioned_expectation_cannot_be_bypassed(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = DspEvidence(Path(folder))
            fixture.receipts[2]['audio_contract']['wav_sha256'] = fixture.receipts[0]['audio_contract']['wav_sha256']
            fixture.write()
            with self.assertRaises(ValueError):
                fixture.qualify()
        for key, value in (('schema', 1), ('kind', 'ys3-reviewed-audio-upgrade'), ('allowed_pcm_changes', ['pcm_hash'])):
            with tempfile.TemporaryDirectory() as folder:
                fixture = DspEvidence(Path(folder))
                fixture.manifest[key] = value
                dump(fixture.expectation_path, fixture.manifest)
                with self.assertRaises(ValueError):
                    fixture.qualify()

    def test_valid_but_wrong_descriptor_profile_rate_is_rejected_after_rebinding(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = DspEvidence(Path(folder))
            receipt = fixture.receipts[2]
            path = Path(receipt['project_descriptor'])
            path.write_text(path.read_text().replace('audio_rate = 48000', 'audio_rate = 44100'))
            changed = sha(path)
            receipt['project_descriptor_sha256'] = changed
            build_path = Path(receipt['project_build']) / 'build-receipt.json'
            built = json.loads(build_path.read_text())
            built['binding']['descriptor_sha256'] = changed
            receipt['project_build_receipt_sha256'] = dump(build_path, built)
            for field in ('project_verification_before', 'project_verification_after'):
                receipt[field]['descriptor_sha256'] = changed
            fixture.write()
            with self.assertRaisesRegex(ValueError, 'descriptor.selection'):
                fixture.qualify()

    def test_actual_packaged_binary_and_dll_bytes_remain_bound(self):
        for name in ('binary', 'dll'):
            with tempfile.TemporaryDirectory() as folder:
                fixture = DspEvidence(Path(folder))
                path = Path(fixture.receipts[2]['desktop_contract']['package_before'][name])
                path.write_bytes(b'changed authored package bytes')
                with self.assertRaises(ValueError):
                    fixture.qualify()

    def test_new_reference_wav_geometry_is_checked_even_with_updated_hash_graph(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = DspEvidence(Path(folder))
            path = fixture.paths[3].parent / 'audio.wav'
            fixture.write_wave(path, 44100, 24, True)
            fixture.receipts[3]['audio_contract'].update(wav_sha256=sha(path), wav_bytes=path.stat().st_size)
            fixture.write()
            with self.assertRaisesRegex(ValueError, 'wav.geometry'):
                fixture.qualify()


if __name__ == '__main__':
    unittest.main()
