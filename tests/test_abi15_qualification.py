"""Authored path-bound ABI15 matrix graphs and focused rejection cases.

Only live Git verification and the already-qualified ABI13 capture validator
are mocked. File bytes, artifact lists, package proof, matrix comparison,
regeneration, WAV geometry, expectation links and before/after hashes are real.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import qualify_abi15 as q
from tests.test_dsp_qualification import dump, sha, DspEvidence
from tests.test_native_audio import NativeAudioEvidence


def identity(tool):
    return {'revision': tool['revision'], 'runtime_abi': tool['runtime_abi'], 'tracked_source_clean': True,
            'shared_source_identity': {'revision': tool['revision'], 'source_sha256': tool['source_sha256'], 'source_files': 53}}


class Matrix:
    def __init__(self, root):
        self.root = root
        base = NativeAudioEvidence(root)
        old, run = copy.deepcopy(base.receipts[0]), copy.deepcopy(base.runs[0])
        self.receipts, self.runs, self.paths = [], [], []
        self.capture = root / 'capture.json'
        self.capture.write_text('{"authored":"immutable ABI13 observations"}\n')
        self.frames = list(range(1, 25)) + [93735] + list(range(93736, 93749)) + [94800]
        route = json.loads(base.route_path.read_text())
        route['checkpoints'] = [{'frame': f, 'png_sha256': 'c' * 64} for f in self.frames]
        dump(base.route_path, route)
        self.route = route
        self.old_module = self.make_module(root / 'old-module', 13)
        self.new_module = self.make_module(root / 'new-module', 15)
        for index, name in enumerate(('baseline', 'legacy', 'gear', 'off', 'legacy-ref', 'gear-ref')):
            folder = root / name
            folder.mkdir()
            receipt, current = copy.deepcopy(old), copy.deepcopy(run)
            desktop, off, gear, is_old = index < 4, index == 3, index in (2, 5), index == 0
            tool = q.OLD_TOOL if is_old else q.TOOL
            receipt['tool_identity'] = identity(tool)
            receipt['tool_identity_after'] = copy.deepcopy(receipt['tool_identity'])
            receipt.update(source_route=str(base.route_path), source_route_sha256=sha(base.route_path), images=copy.deepcopy(route['checkpoints']), memory_edits_replayed=709)
            receipt['source_command'] = copy.deepcopy(route['initial_command'])
            receipt['command'] = copy.deepcopy(base.receipts[0]['command'])
            # Start with only original guest arguments; selections below are explicit.
            for flag in ('--audio-output', '--audio-profile', '--audio-rate', '--audio-out', '--audio-frames', '--hidden', '--unthrottled'):
                while flag in receipt['command']:
                    where = receipt['command'].index(flag)
                    del receipt['command'][where:where + 2]
            receipt['command'] += ['--audio-output', 'off' if off else 'on']
            if not off:
                receipt['command'] += ['--audio-profile', 'filtered', '--audio-rate', '48000', '--audio-out', str(folder / 'audio.wav'), '--audio-frames', '1440000']
                if not is_old and not gear:
                    receipt['command'] += ['--audio-timing', 'legacy']
            if desktop:
                receipt['command'] += ['--hidden', 'on', '--unthrottled', 'on']
                # Retain the authored package proof while assigning a distinct actual output directory.
                package = receipt['desktop_contract']['package_before']
                binary = folder / 'bin/pce-consumer.exe'
                binary.parent.mkdir()
                binary.write_bytes(('Authored package ' + name).encode())
                dll = binary.with_name('SDL3.dll')
                dll.write_bytes(b'Authored SDL fixture')
                outputs = {x.name: sha(x) for x in binary.parent.iterdir()}
                package.update(binary=str(binary), binary_sha256=sha(binary), dll=str(dll), dll_sha256=sha(dll), output_files=outputs)
                receipt['desktop_contract']['package_after'] = copy.deepcopy(package)
                for field in ('loaded_sdl_before', 'loaded_sdl_final'):
                    receipt['desktop_contract'][field].update(executable=str(binary), binary_sha256=sha(binary), loaded_sdl=str(dll), dll_sha256=sha(dll))
                receipt['command'][0] = str(binary)
                receipt['binary_sha256'] = sha(binary)
                self.descriptor(folder, receipt, tool, self.old_module if is_old else self.new_module, off, gear, is_old, outputs)
            else:
                binary = folder / 'headless.exe'
                binary.write_bytes(b'Authored independent supervised headless runner')
                receipt['command'][0] = str(binary)
                receipt['binary_sha256'] = sha(binary)
                receipt.pop('desktop_contract')
                current.pop('desktop')
            receipt['input_sha256'] = {str(p): sha(p) for p in (base.payload, base.route_path)}
            receipt['input_sha256'][receipt['command'][0]] = receipt['binary_sha256']
            core = copy.deepcopy(old['audio_contract']['validated_output'])
            core.update(wav_frames=108, wav_truncated=False)
            if gear:
                core.update(timing='gear-v1', pcm_hash=9988)
            full = copy.deepcopy(core)
            if desktop:
                full.update(device_open=True, fast_forward_muted=True, host={'submitted_frames':108,'dropped_frames':108,'clears':1,'pauses':1,'queued_frames':0,'peak_queue_frames':0,'input_rate':48000,'device_rate':48000,'device_channels':2,'device_format':33056})
            current.update(stop='dev_quit', **q.FINAL_TIERS)
            current['ticks'] = (100 * 21477273 + 44099) // 44100
            if off:
                current.pop('audio_output')
            else:
                current['audio_output'] = copy.deepcopy(full)
            if desktop:
                current['desktop'].update(presented=94800, polls=95000)
                receipt['desktop_contract']['presentation'] = copy.deepcopy(current['desktop'])
                if off:
                    receipt['desktop_contract'].pop('audio_output', None)
                else:
                    receipt['desktop_contract']['audio_output'] = copy.deepcopy(full)
            receipt['audio_contract'] = {'runtime_abi': tool['runtime_abi'], 'mode':'off' if off else 'on',
                'headless_pcm_only':not desktop, 'wav_frame_limit':None if off else 1440000,
                'validated_output':None if off else copy.deepcopy(core), 'audio_output_absent':off}
            if not is_old:
                receipt['audio_selection'] = (None if off else
                    copy.deepcopy(q.GEAR if gear else q.LEGACY) if desktop else
                    {'profile':'filtered','sample_rate':48000})
            receipt['checkpoint_status'] = []
            for frame in self.frames:
                state = copy.deepcopy(old['final_status'])
                state.update(frame=frame, ticks=current['ticks'])
                state['host'].update(native_steps=q.FINAL_TIERS['native_steps'], interpreter_steps=981)
                if off:
                    state['host'].pop('audio_output')
                else:
                    state['host']['audio_output'] = copy.deepcopy(full)
                receipt['checkpoint_status'].append(state)
            for field in q.ENDPOINTS:
                receipt[field] = copy.deepcopy(receipt['checkpoint_status'][-1])
            if is_old:
                window = {'requested_start_frame':93735,'started':True,'actual_start_frame':93735,'actual_start_ticks':33650360835,'native_steps_before':2920491782,'interpreter_steps_before':981}
                current['code_capture_window'] = window
                receipt['capture_contract'] = {'authored': True}
            if not off:
                DspEvidence.write_wave(folder / 'audio.wav', 48000, 108, gear)
                receipt['audio_contract'].update(wav_path=str(folder / 'audio.wav'), wav_sha256=sha(folder / 'audio.wav'), wav_bytes=(folder / 'audio.wav').stat().st_size)
            path = folder / 'receipt.json'
            self.receipts.append(receipt)
            self.runs.append(current)
            self.paths.append(path)
        self.proof_path = root / 'reemission.json'
        files = []
        for name in self.old_module[1]:
            a, b = self.old_module[1][name], self.new_module[1][name]
            files.append({'file':name,'old':{'path':str(a),'sha256':sha(a)},'new':{'path':str(b),'sha256':sha(b)},'abi_assertions_replaced':int(name.endswith('.cpp')),'translated_operations_and_guards_exact':True})
        self.proof = {'passed':True,'tool':identity(q.TOOL),'old_manifest':{'path':str(self.old_module[0]),'sha256':sha(self.old_module[0])},'new_manifest':{'path':str(self.new_module[0]),'sha256':sha(self.new_module[0])},'capture':{'path':str(self.capture),'sha256':sha(self.capture)},'source_capture_runtime_abi':13,'module_runtime_abi':15,'artifact_count':209,'assertion_only_changed_artifacts':208,'normalization':{'only_bytes_from':'static_assert(abi_version == 13);','only_bytes_to':'static_assert(abi_version == 15);','all_other_source_bytes_exact':True,'all_other_manifest_metadata_exact':True},'files':files,'evidence_sha256':{str(self.capture):sha(self.capture)}}
        dump(self.proof_path, self.proof)
        self.expectation_path = root / 'expectation.json'
        self.write()

    def make_module(self, folder, abi):
        folder.mkdir()
        names = ['module.cpp'] + [f'module_part_{i:04}.cpp' for i in range(207)] + ['module_parts.hpp']
        files = {}
        for name in names:
            path = folder / name
            path.write_text((f'static_assert(abi_version == {abi});\n' if name.endswith('.cpp') else '') + '// Authored synthetic guarded operation\n')
            files[name] = path
        manifest = {'schema':1,'runtime_abi':abi,'capture_runtime_abi':13,'code_capture_sha256':sha(self.capture),'native_instructions_emitted':44879,'excluded_observations':4,'excluded_retired_hits':981,'excluded_physical_ranges':[{'start':1069880,'length':6}],'guards':['full_mpr_snapshot','exact_source_bytes_per_instruction','instruction_deadline'],'translation_units':[{'file':n,'sha256':sha(p)} for n,p in files.items() if n.endswith('.cpp')],'generated_headers':[{'file':n,'sha256':sha(p)} for n,p in files.items() if n.endswith('.hpp')]}
        path = folder / 'module.json'
        dump(path, manifest)
        return path, files

    def descriptor(self, folder, receipt, tool, module, off, gear, old, outputs):
        manifest, files = module
        source = files['module.cpp']
        descriptor = folder / 'project.toml'
        descriptor.write_text('schema=1\n[tool]\npath='+json.dumps(str(self.root))+'\nrevision='+json.dumps(tool['revision'])+'\nsource_sha256='+json.dumps(tool['source_sha256'])+'\nruntime_abi='+str(tool['runtime_abi'])+'\n[runtime]\ntier="hybrid"\naudio='+json.dumps('off' if off else 'on')+'\n'+('' if off else 'audio_profile="filtered"\naudio_rate=48000\n'+('audio_timing="legacy"\n' if not gear and not old else ''))+'[module.source]\npath='+json.dumps(str(source))+'\nsha256='+json.dumps(sha(source))+'\n[module.manifest]\npath='+json.dumps(str(manifest))+'\nsha256='+json.dumps(sha(manifest))+'\n[payload]\npath='+json.dumps(str(self.root/'authored-payload'))+'\nsha256='+json.dumps(sha(self.root/'authored-payload'))+'\n')
        bound = {'module_source':sha(source),'module_manifest':sha(manifest),'payload':sha(self.root/'authored-payload')}
        bound.update({('module_header:' if n.endswith('.hpp') else 'module_unit:')+n:sha(p) for n,p in files.items()})
        binding = {'descriptor_sha256':sha(descriptor),'tool':{k:tool[k] for k in ('revision','source_sha256')},'files':bound,'revision_override':False}
        built = {'schema':1,'kind':'pce-consumer-build','binding':binding,'desktop':True,'binary':receipt['command'][0],'binary_sha256':receipt['binary_sha256'],'output_files':outputs}
        build = folder / 'build'; build.mkdir()
        build_receipt = build / 'build-receipt.json'; dump(build_receipt,built)
        receipt.update(project_descriptor=str(descriptor),project_descriptor_sha256=sha(descriptor),project_build=str(build),project_build_receipt_sha256=sha(build_receipt),project_binding=binding,project_verification_before={'schema':1,'verified':True,**copy.deepcopy(binding)},project_verification_after={'schema':1,'verified':True,**copy.deepcopy(binding)},project_output_files_before=outputs.copy(),project_output_files_after=outputs.copy())

    def write(self):
        for path, receipt, run in zip(self.paths,self.receipts,self.runs):
            dump(path,receipt);dump(path.parent/'run.stdout',run)
        baseline_q = self.root/'baseline-qualification.json'
        dump(baseline_q,{'result':'pass','evidence_sha256':{str(p):sha(p) for p in (self.paths[0],self.paths[0].parent/'run.stdout',self.paths[0].parent/'audio.wav')}})
        roles = {'baseline_receipt':self.paths[0],'baseline_run':self.paths[0].parent/'run.stdout','baseline_wav':self.paths[0].parent/'audio.wav','baseline_qualification':baseline_q,'reemission_proof':self.proof_path}
        for label,index in (('legacy',4),('gear',5)):
            roles.update({label+'_receipt':self.paths[index],label+'_run':self.paths[index].parent/'run.stdout',label+'_wav':self.paths[index].parent/'audio.wav'})
        for role in ('tool_contract','finite_state_evidence','independent_timing_evidence'):
            path=self.root/(role+'.json');dump(path,{'result':'pass','runtime_abi':15,'descriptor_schema':1,'tool_identity':q.TOOL});roles[role]=path
        upstream = {'result':'pass','revision':q.TOOL['revision'],'source_sha256':q.TOOL['source_sha256'],'runtime_abi':15,'route_sha256':self.receipts[0]['source_route_sha256'],'module_manifest_sha256':sha(self.new_module[0])}
        upstream.update({role+'_sha256':sha(path) for role,path in roles.items() if role in q.REF_ROLES | (q.REVIEW_ROLES-{'upstream_qualification'})})
        path=self.root/'upstream.json';dump(path,upstream);roles['upstream_qualification']=path
        self.expectation={'schema':1,'kind':'ys3-reviewed-abi15-matrix','tool':q.TOOL,'route':{k:self.receipts[0][k] for k in q.ROUTE},'files':{role:{'path':str(path),'sha256':sha(path)} for role,path in roles.items()},'qualification_success':'pass','qualification_pointers':{k:'/'+k for k in q.POINTERS},'success_bindings':{role:{'pointer':'/passed' if role=='reemission_proof' else '/result','value':True if role=='reemission_proof' else 'pass'} for role in q.REVIEW_ROLES-{'upstream_qualification'}},'reviewed_binding':{'qualified':True,'tool':q.TOOL,'route':{k:self.receipts[0][k] for k in q.ROUTE},'execution':{'tier':'hybrid','profile':'filtered','sample_rate':48000,'legacy_explicit':True,'gear_default':True,'off_explicit':True,'reference_host':'headless','candidate_host':'packaged-desktop'},'independent_scope':'Authored fixture only','unexposed_internal_state_not_retail_verified':True,'evidence_sha256':{role:sha(path) for role,path in roles.items()}}}
        dump(self.expectation_path,self.expectation)

    def qualify(self):
        with patch.object(q,'live_tool',return_value=identity(q.TOOL)), patch.object(q.prior,'validate_managed_capture',return_value=({}, {'retired_instructions':32946624})):
            return q.qualify_abi15(*self.paths[:4], self.expectation_path)


class Abi15QualificationTests(unittest.TestCase):
    def fixture(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        return Matrix(Path(folder.name))

    def test_complete_path_bound_matrix_and_reemission_pass(self):
        result=self.fixture().qualify()
        self.assertTrue(result['legacy_exact_old_guest_native_source_pcm_wav'])
        self.assertTrue(result['gear_exact_new_headless_reference'])
        self.assertTrue(result['off_exact_gear_guest_and_pcm_absent'])
        self.assertEqual(result['images'],39)
        self.assertEqual(len(result['measurements']),42)
        self.assertEqual(len(result['reemission'][0]['exact_abi_static_assert_changes']),208)

    def test_guest_native_mpr_generation_image_and_assist_changes_fail(self):
        mutations=(lambda f:f.runs[2].update(native_steps=1),lambda f:f.receipts[1]['checkpoint_status'][0]['host']['cpu']['mpr'].__setitem__(7,9),lambda f:f.receipts[3]['final_status']['host']['cpu']['instruction_generations'].__setitem__(0,99),lambda f:f.receipts[2]['images'][0].update(png_sha256='d'*64),lambda f:f.receipts[1].update(memory_edits_replayed=710),lambda f:f.receipts[5]['checkpoint_status'][0]['host'].update(unknown_guest=1))
        for mutate in mutations:
            fixture=self.fixture();mutate(fixture);fixture.write()
            with self.assertRaises((ValueError,KeyError)):fixture.qualify()

    def test_explicit_legacy_default_gear_and_off_absence_are_required(self):
        mutations=(lambda f:f.receipts[1]['command'].__setitem__(f.receipts[1]['command'].index('--audio-timing')+1,'gear'),lambda f:f.receipts[2]['command'].extend(['--audio-timing','gear']),lambda f:f.runs[3].update(audio_output=None),lambda f:f.receipts[3]['checkpoint_status'][0]['host'].update(audio_output=None),lambda f:f.receipts[3]['desktop_contract'].update(audio_output=None),lambda f:f.runs[2]['audio_output'].pop('timing'))
        for mutate in mutations:
            fixture=self.fixture();mutate(fixture);fixture.write()
            with self.assertRaises(ValueError):fixture.qualify()

    def test_headless_exact_two_key_metadata_keeps_independent_timing_bindings(self):
        fixture=self.fixture()
        for index,timing in ((4,'legacy'),(5,'gear')):
            self.assertEqual(set(fixture.receipts[index]['audio_selection']),{'profile','sample_rate'})
            q.receipt_contract(fixture.receipts[index],timing,'on',False)
        self.assertTrue(fixture.qualify()['gear_exact_new_headless_reference'])

    def test_headless_wrong_timing_or_marker_and_consumer_two_key_metadata_fail(self):
        mutations=(lambda f:f.receipts[4]['command'].__setitem__(f.receipts[4]['command'].index('--audio-timing')+1,'gear'),
                   lambda f:f.receipts[5]['command'].extend(['--audio-timing','legacy']),
                   lambda f:f.runs[5]['audio_output'].pop('timing'),
                   lambda f:f.receipts[1]['audio_selection'].pop('timing'),
                   lambda f:f.receipts[5]['audio_selection'].update(timing='gear'))
        for mutate in mutations:
            fixture=self.fixture();mutate(fixture);fixture.write()
            with self.assertRaises(ValueError):fixture.qualify()

    def test_reference_pcm_wav_and_checkpoint_drift_fail(self):
        for mutate in (lambda f:f.runs[5]['audio_output'].update(pcm_hash=123),lambda f:f.receipts[4]['checkpoint_status'][3]['host']['audio_output'].update(peak=901),lambda f:(f.paths[2].parent/'audio.wav').write_bytes(b'changed')):
            fixture=self.fixture();mutate(fixture);fixture.write()
            with self.assertRaises(ValueError):fixture.qualify()

    def test_module_operation_guard_and_manifest_changes_fail(self):
        fixture=self.fixture();fixture.new_module[1]['module_part_0000.cpp'].write_text('static_assert(abi_version == 15);\n// Wrong operation\n')
        with self.assertRaises(ValueError):fixture.qualify()

    def test_reemission_operation_checker_rejects_even_rebound_artifacts(self):
        fixture=self.fixture()
        old=(None,fixture.old_module[0],json.loads(fixture.old_module[0].read_text()),fixture.old_module[1])
        new=(None,fixture.new_module[0],json.loads(fixture.new_module[0].read_text()),fixture.new_module[1])
        self.assertTrue(q.regenerated_module(old,new)['translated_operations_and_guards_exact'])
        target=fixture.new_module[1]['module_part_0000.cpp']
        target.write_text('static_assert(abi_version == 15);\n// Rebound but different guarded operation\n')
        for entry in new[2]['translation_units']:
            if entry['file']==target.name:entry['sha256']=sha(target)
        with self.assertRaisesRegex(ValueError,'translated operations/guards changed'):
            q.regenerated_module(old,new)

    def test_reviewed_reference_must_link_exact_profile_module_and_artifacts(self):
        fixture=self.fixture()
        fixture.expectation['qualification_pointers']['legacy_run_sha256']='/gear_run_sha256'
        dump(fixture.expectation_path,fixture.expectation)
        with self.assertRaisesRegex(ValueError,'upstream.legacy_run_sha256'):fixture.qualify()
        fixture=self.fixture()
        fixture.expectation['success_bindings']['finite_state_evidence']['value']=False
        dump(fixture.expectation_path,fixture.expectation)
        with self.assertRaisesRegex(ValueError,'explicitly pass'):fixture.qualify()

    def test_one_source_edge_drift_fails_even_if_reference_and_ratio_agree(self):
        fixture=self.fixture()
        # Rebind both Gear outputs consistently, including actual WAV bytes.
        # The complete core/reference comparison and160/147 floor would agree;
        # only the independent integer master/source-edge relation rejects it.
        for index in (2,5):
            receipt=fixture.receipts[index]
            objects=[fixture.runs[index]['audio_output'],receipt['audio_contract']['validated_output']]
            if index==2:objects.append(receipt['desktop_contract']['audio_output'])
            objects += [receipt[field]['host']['audio_output'] for field in q.ENDPOINTS]
            objects += [state['host']['audio_output'] for state in receipt['checkpoint_status']]
            for audio in objects:
                audio['processing']['source_frames']=101
                audio.update(frames=101*160//147,wav_frames=101*160//147)
                if 'host' in audio:
                    audio['host'].update(submitted_frames=101*160//147,dropped_frames=101*160//147)
            target=fixture.paths[index].parent/'audio.wav'
            DspEvidence.write_wave(target,48000,101*160//147,True)
            receipt['audio_contract'].update(wav_sha256=sha(target),wav_bytes=target.stat().st_size)
        fixture.write()
        with self.assertRaisesRegex(ValueError,'gear_source_clock'):fixture.qualify()

    def test_gear_source_clock_is_checked_at_each_intermediate_state(self):
        fixture=self.fixture()
        for index in (2,5):
            # Keep both reference/candidate guest ticks equal to one another;
            # a one-master-tick move across sample100's ceiling edge is invalid.
            fixture.receipts[index]['checkpoint_status'][7]['ticks']-=1
        fixture.write()
        with self.assertRaisesRegex(ValueError,'gear_source_clock'):fixture.qualify()

    def test_unknown_abi_and_malformed_proof_fields_fail(self):
        fixture=self.fixture();fixture.expectation['tool']=dict(q.TOOL,runtime_abi=16)
        dump(fixture.expectation_path,fixture.expectation)
        with self.assertRaises(ValueError):fixture.qualify()
        fixture=self.fixture();fixture.proof['files'][0]['translated_operations_and_guards_exact']=False
        dump(fixture.proof_path,fixture.proof);fixture.write()
        with self.assertRaisesRegex(ValueError,'proof_operations'):fixture.qualify()
        fixture=self.fixture();manifest=json.loads(fixture.new_module[0].read_text());manifest['excluded_retired_hits']=0;dump(fixture.new_module[0],manifest)
        with self.assertRaises(ValueError):fixture.qualify()

    def test_old_capture_window_and_new_capture_rejection(self):
        fixture=self.fixture();fixture.runs[0]['code_capture_window']['actual_start_ticks']+=1;fixture.write()
        with self.assertRaisesRegex(ValueError,'capture_window'):fixture.qualify()
        fixture=self.fixture();fixture.runs[1]['code_capture_window']={};fixture.write()
        with self.assertRaisesRegex(ValueError,'capture-free'):fixture.qualify()

    def test_bound_reference_links_and_success_cannot_be_bypassed(self):
        fixture=self.fixture();fixture.expectation['reviewed_binding']['unexposed_internal_state_not_retail_verified']=False;dump(fixture.expectation_path,fixture.expectation)
        with self.assertRaisesRegex(ValueError,'unexposed'):fixture.qualify()
        fixture=self.fixture();fixture.expectation['files']['gear_run']['sha256']='d'*64;dump(fixture.expectation_path,fixture.expectation)
        with self.assertRaisesRegex(ValueError,'hash mismatch'):fixture.qualify()

    def test_actual_package_tamper_and_all_artifact_hashes_fail(self):
        fixture=self.fixture();Path(fixture.receipts[2]['command'][0]).with_name('SDL3.dll').write_bytes(b'Changed DLL')
        with self.assertRaises(ValueError):fixture.qualify()
        fixture=self.fixture();fixture.old_module[1]['module_parts.hpp'].write_bytes(b'changed source header')
        with self.assertRaises(ValueError):fixture.qualify()


if __name__=='__main__':
    unittest.main()
