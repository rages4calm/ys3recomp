"""Authored reset-capture/source proofs; no BIOS/game assets or hosts run."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import importlib
import wave
import struct
import zlib
import tomllib
from unittest.mock import patch

from scripts import qualify_reset_native as q

TOOL_ROOT=Path(__file__).resolve().parents[1]/'.deps/pcenginerecomp-abi17'


def pcm(ticks,desktop=False):
    frames=ticks*44100//21477273
    value={'enabled':True,'sample_rate':44100,'channels':2,'frames':frames,'psg_nonzero':0,
        'adpcm_nonzero':0,'cdda_nonzero':0,'mixed_nonzero':0,'peak':0,'pcm_hash':14695981039346656037,
        'discarded_frames':0,'wav_frames':min(frames,q.WAV_LIMIT),'wav_truncated':frames>q.WAV_LIMIT,'timing':'gear-v1'}
    if desktop:
        value.update(device_open=True,fast_forward_muted=True)
        value['host']={'submitted_frames':frames,'dropped_frames':frames,'queued_frames':0,'peak_queue_frames':0,'clears':1,'pauses':1}
    return value


def boot():
    return {'mode':'system-card-reset','profile':'super','initialization':'gear-deterministic-zero-v1',
        'vector_physical':8190,'pc':256,'a':0,'x':0,'y':0,'sp':0,'p':4,'clock_divisor':12,
        'ticks':0,'cycles':0,'mpr':[0]*8,'bram':'blank-unformatted'}


def state(frame=600,ticks=215397015,desktop=True,native=5,interpreted=3):
    cpu={'a':0,'x':0,'y':0,'sp':0,'p':4,'clock_divisor':12,'mpr_latch':0,'irq_sampled':0,'irq_vector':0,
        'mpr':[0]*8,'physical_pc':256,'instruction_bytes':[234]*7,'instruction_physical':list(range(256,263)),
        'instruction_generations':[0]*7}
    host={'boot':boot(),'debug_memory':{'write_enabled':False,'write_requests':0,'bytes_changed':0},
        'pc':256,'native_steps':native,'interpreter_steps':interpreted,'irq_entries':0,'rti_steps':0,'sectors_read':0,
        'read_errors':0,'unknown_commands':0,'adpcm_dma_bytes':0,'buttons':[0]*5,'cpu':cpu,
        'cd_control':{'bram_seeded':False},'scsi':{'master_ticks':ticks,'unknown_commands':0},
        'cd_unknown':{'accepted_responses':0,'opcodes':[],'last_command':[],'origin':None},'cd_audio':{},
        'adpcm':{'master_ticks':ticks},'audio_output':pcm(ticks,desktop),'vdc':{},
        'raster':{'frames':frame,'master_ticks':ticks},'interrupts':{}}
    return {'id':1,'ok':True,'frame':frame,'ticks':ticks,'paused':True,'local_paused':False,'host':host}


class ReceiptFixture:
    """Real pinned verifier/emitter, authored files, no compiler or host runs."""
    def __init__(self,root):
        from scripts import replay_reset as api,prepare_reset_descriptor as desc
        self.root,self.api,self.desc=root,api,desc
        self.out=root/'replay';self.out.mkdir();cwd=self.out/'cwd';cwd.mkdir()
        self.capture=capture();self.capture['capacity']=65536
        self.capture_path=self.out/'observed-code.json';self.dump(self.capture_path,self.capture)
        loader=q.merge.load_capture_api(TOOL_ROOT);emitter=importlib.import_module(loader.__package__+'.emitter')
        module=root/'module';emitter.emit_capture(self.capture,module,q.sha256(self.capture_path),single_unit=True)
        assets={}
        for name in ('bios','toc','disc','libchdr'):
            path=root/name
            raw=bytearray([234])*q.BIOS_BYTES if name=='bios' else bytearray(b'authored '+name.encode())
            if name=='bios':raw[8190:8192]=bytes([0,1])
            path.write_bytes(raw);assets[name]={'path':str(path),'sha256':q.sha256(path)}
        self.bios_hash=assets['bios']['sha256']
        self.descriptor=root/'project.toml';reference={'assets':assets,'limits':{'steps':20000000000,'ticks':100000000000,'wall_seconds':600}}
        self.descriptor.write_text(desc.descriptor_text(reference,module/'module.cpp',TOOL_ROOT,q.TOOL),encoding='utf-8')
        project,_,_=api.load_shared(TOOL_ROOT.resolve());self.project=project
        verified=project.verify(self.descriptor);verification={'schema':1,'verified':True,**project._binding(verified)}
        self.build=root/'build';self.build.mkdir();binary=self.build/'bin/game.exe';binary.parent.mkdir()
        binary.write_bytes(b'authored nonexecutable package');binary.with_name('SDL3.dll').write_bytes(b'authored adjacent dll')
        outputs={p.name:q.sha256(p) for p in binary.parent.iterdir()}
        built={'schema':1,'kind':'pce-consumer-build','binding':project._binding(verified),'binary':str(binary),
            'binary_sha256':q.sha256(binary),'desktop':True,'output_files':outputs,'commands':[],'execution_evidence':False}
        self.dump(self.build/'build-receipt.json',built)
        package=q.verify_package(built,binary)
        from scripts.package_checks import packaged_environment
        _,environment=packaged_environment(binary)
        loaded={'pid':12345,'executable':str(binary),'binary_sha256':q.sha256(binary),'loaded_sdl':str(binary.with_name('SDL3.dll')),
            'dll_sha256':q.sha256(binary.with_name('SDL3.dll')),'adjacent_package_loaded':True,'inspection':'authored synthetic fixture'}
        first=state(0,0,native=0,interpreted=0);last=state()
        proof={'status_before':first,'status':copy.deepcopy(first),'retired_instructions':0,
            'vector_readback':{'address':8190,'expected':'0001','observed':'0001'},
            'fetch_readback':[{'address':i,'expected':234,'observed':234} for i in range(256,263)]}
        window={'requested_start_frame':0,'started':True,'actual_start_frame':0,'actual_start_ticks':0,'native_steps_before':0,'interpreter_steps_before':0}
        runner={**{field:0 for field in api.RUNNER_FIELDS},'boot':boot(),'stop':'dev_quit','pc':256,'mpr':[0]*8,'instruction_bytes':[234]*7,'ticks':last['ticks'],
            'scope':'System Card reset-vector boot; deterministic reference initialization; not hardware power-on certification','p':4,'clock_divisor':12,
            'native_steps':5,'interpreter_steps':3,'native_block_steps':0,'interpreter_block_steps':0,'guard_misses':3,
            'development':{'enabled':True,'port':12345,'memory_write_enabled':False,'memory_write_requests':0,'memory_bytes_changed':0},
            'audio_output':pcm(last['ticks'],True),'cd_control':{'bram_seeded':False},'scsi':{'unknown_commands':0,'master_ticks':last['ticks']},
            'cd_unknown':copy.deepcopy(last['host']['cd_unknown']),'adpcm':{'master_ticks':last['ticks']},'raster':{'frames':600,'master_ticks':last['ticks']},
            'desktop':{name:0 for name in api.DESKTOP_FIELDS},'code_capture_window':window}
        runner['desktop'].update(presented=600,polls=600)
        contract={'schema':1,'runtime_abi':17,'path':str(self.capture_path),'sha256':q.sha256(self.capture_path),
            'bytes':self.capture_path.stat().st_size,'start_frame':0,'capacity':65536,'start_proof':proof,
            'capture':{k:v for k,v in self.capture.items() if k!='observations'},'observations':1,'window':window}
        identity={'revision':q.TOOL['revision'],'runtime_abi':17,'tracked_source_clean':True,
            'shared_source_identity':{k:q.TOOL[k] for k in ('revision','source_sha256','source_files')}}
        originals=[]
        for index in range(7):
            path=root/f'original-{index}';path.write_bytes(bytes([index]));originals.append({'path':str(path),'sha256':q.sha256(path),'bytes':1})
        self.receipt={'schema':1,'kind':'ys3-reset-replay','passed':True,'error':None,'exit_code':0,'child_stopped':True,
            'natural_quit':True,'supervisor_failure':None,'shared_project_run_used':False,'execution_mode':'shared-verify-command-consumer-tcp',
            'tool_identity':identity,'tool_identity_before':identity,'tool_identity_after':identity,'project_descriptor':str(self.descriptor),
            'project_descriptor_sha256':q.sha256(self.descriptor),'project_build':str(self.build),
            'project_build_receipt':api.binding(self.build/'build-receipt.json'),'project_build_receipt_sha256':q.sha256(self.build/'build-receipt.json'),
            'project_verification_before':verification,'project_verification_after':verification,
            'desktop_contract':dict(package_before=package,package_after=package,environment=environment,working_directory=str(cwd),
                loaded_sdl_before=copy.deepcopy(loaded),loaded_sdl_final=copy.deepcopy(loaded),**{field:True for field in ('packaged','hidden','unthrottled','working_directory_initially_empty','working_directory_finally_empty')}),
            'asset_hashes_before':verified['identities'],'asset_hashes_after':verified['identities'],'initial_boot':boot(),
            'command':api.reset_command(project,verified,binary,self.out),'protected_inputs_before':originals,'protected_inputs_after':originals,
            'runner':runner,'states':[first,last],'actions':[['advance','600']],'final_status':copy.deepcopy(last),
            'capture_contract':contract,'start_proof':proof,'boot_validation':{'valid':True},'raw_files':{}}
        self.path=self.out/'receipt.json';self.save()

    @staticmethod
    def dump(path,value):path.write_text(json.dumps(value)+'\n',encoding='utf-8')

    def save(self):
        self.dump(self.out/'run.stdout',self.receipt['runner']);(self.out/'run.stderr').write_bytes(b'authored TCP log')
        for role in ('states','actions'):
            (self.out/(role+'.jsonl')).write_text(''.join(json.dumps(value)+'\n' for value in self.receipt[role]),encoding='utf-8')
        with wave.open(str(self.out/'audio.wav'),'wb') as audio:
            audio.setnchannels(2);audio.setsampwidth(2);audio.setframerate(44100);audio.writeframes(bytes(q.WAV_LIMIT*4))
        self.receipt['raw_files']={role:self.api.binding(self.out/name) for role,name in
            {'stdout':'run.stdout','stderr':'run.stderr','wav':'audio.wav','states':'states.jsonl','actions':'actions.jsonl'}.items()}
        self.dump(self.path,self.receipt)

    def qualify(self):
        # Only the known retail-BIOS policy is replaced for this authored fixture.
        with patch.object(self.desc,'USA_BIOS_SHA256',self.bios_hash):return q.bind_receipt(self.path,{})


def capture(native=5,interpreted=3,physical=256):
    bank=physical>>13;pc=256
    mpr=[0]*8;mpr[pc>>13]=bank
    return {'schema':1,'runtime_abi':17,'capacity':512,'retired_instructions':native+interpreted,
            'complete':True,'dropped_instructions':0,'unreadable_instructions':0,
            'observations':[{'pc':pc,'mpr':mpr,'physical':[physical],'data':[234],
                             'native_hits':native,'interpreted_hits':interpreted}]}


class ResetNativeProofTests(unittest.TestCase):
    def test_actual_shared_loader_conserves_each_execution_tier_and_total(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'capture.json';path.write_text(json.dumps(capture()))
            run={'native_steps':5,'interpreter_steps':3,'native_block_steps':0,'interpreter_block_steps':0,'guard_misses':3}
            value,report=q.load_capture(TOOL_ROOT,path,run,512,{})
            self.assertEqual(report['native'],5);self.assertEqual(report['total'],8)
            self.assertEqual(value['runtime_abi'],17)
            run['interpreter_steps']=4
            with self.assertRaises(ValueError):q.load_capture(TOOL_ROOT,path,run,512,{})

    def test_actual_shared_loader_rejects_loss_relabel_capacity_and_mpr_mapping(self):
        mutations=(lambda c:c.update(runtime_abi=16),lambda c:c.update(dropped_instructions=1,retired_instructions=9),
                   lambda c:c['observations'][0]['physical'].__setitem__(0,257),lambda c:c['observations'][0]['mpr'].pop())
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'capture.json'
            run={'native_steps':5,'interpreter_steps':3,'native_block_steps':0,'interpreter_block_steps':0,'guard_misses':3}
            for mutate in mutations:
                with self.subTest(mutate=mutate):
                    value=capture();mutate(value);path.write_text(json.dumps(value))
                    with self.assertRaises(ValueError):q.load_capture(TOOL_ROOT,path,run,512,{})
            path.write_text(json.dumps(capture()))
            with self.assertRaises(ValueError):q.load_capture(TOOL_ROOT,path,run,513,{})

    def test_positive_bios_work_before_menu_is_actual_prefix_source_evidence(self):
        prefix=capture(5,3);full=capture(10,7);profile=capture(0,17)
        proof=q.prove_native_bios(prefix,full,profile,bytes([234])*q.BIOS_BYTES)
        self.assertEqual(proof['before_menu_frame'],600)
        self.assertEqual(proof['before_menu']['native'],5)
        self.assertEqual(proof['full_route']['native'],10)

    def test_later_bios_native_work_cannot_be_promoted_to_boot_prefix_proof(self):
        prefix=capture(0,3);full=capture(10,7)
        with self.assertRaisesRegex(ValueError,'before the System Card menu'):
            q.prove_native_bios(prefix,full,full,bytes([234])*q.BIOS_BYTES)

    def test_boot_source_requires_exact_bios_bytes_full_mpr_and_compiled_membership(self):
        prefix=capture();full=capture(10,7);profile=capture(0,17)
        wrong_bios=bytearray([234])*q.BIOS_BYTES;wrong_bios[256]=233
        with self.assertRaisesRegex(ValueError,'BIOS source bytes'):
            q.prove_native_bios(prefix,full,profile,wrong_bios)
        wrong_profile=copy.deepcopy(profile);wrong_profile['observations'][0]['mpr'][7]=1
        with self.assertRaisesRegex(ValueError,'absent from actual compiled profile'):
            q.prove_native_bios(prefix,full,wrong_profile,bytes([234])*q.BIOS_BYTES)
        prefix['observations'][0]['native_hits']=11
        with self.assertRaisesRegex(ValueError,'not retained'):
            q.prove_native_bios(prefix,full,profile,bytes([234])*q.BIOS_BYTES)

    def test_ram_native_work_does_not_prove_translated_bios_boot(self):
        prefix=capture(5,3,0x100100);full=capture(10,7,0x100100)
        with self.assertRaisesRegex(ValueError,'before the System Card menu'):
            q.prove_native_bios(prefix,full,full,bytes([234])*q.BIOS_BYTES)

    def test_conflicting_file_epochs_cannot_overwrite_prior_evidence_bindings(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'evidence';path.write_bytes(b'first');hashes={}
            q.file_hash(path,q.sha256(path),hashes)
            path.write_bytes(b'second')
            with self.assertRaisesRegex(ValueError,'conflicting evidence epochs'):
                q.file_hash(path,q.sha256(path),hashes)

    def test_official_binding_package_actual_argv_capture_and_wav_positive(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture=ReceiptFixture(Path(temporary))
            result=fixture.qualify()
            self.assertEqual(result[5]['native'],5)
            self.assertEqual(result[5]['interpreted'],3)
            self.assertEqual(result[6]['audio_output']['frames'],215397015*44100//21477273)

    def test_module_reader_consumes_real_descriptor_json_native_path_strings(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture=ReceiptFixture(Path(temporary))
            config=tomllib.loads(fixture.descriptor.read_text(encoding='utf-8'))
            with patch.object(fixture.desc,'USA_BIOS_SHA256',fixture.bios_hash):
                actual=fixture.desc.validate_reset_descriptor(config,fixture.descriptor)
            # This is the public API's real result, including its JSON round trip.
            actual=json.loads(json.dumps(actual))
            self.assertTrue(all(type(path)is str for path in actual['files'].values()))
            self.assertEqual(q.module_manifest(actual)['native_instructions_emitted'],1)
            self.assertEqual(q.module_manifest(actual)['runtime_abi'],17)
            manifest=q.module_manifest(actual)
            patches=[{'frame':1,'physical':1069880,'expected':'ea'*6,'data':'80'*6},
                {'frame':2,'physical':1069880,'expected':'80'*6,'data':'ea'*6}]
            route={'assistance':{'jump_patch_active':False,'code_patches':patches},'last_status':{'frame':2},
                'steps':[{'frame':p['frame'],'memory_write':{'address':p['physical'],'expected':p['expected'],'data':p['data']}} for p in patches]}
            route_path=Path(temporary)/'route.json';fixture.dump(route_path,route)
            selection={'schema':1,'tool_identity':fixture.receipt['tool_identity'],'route_sha256':q.sha256(route_path),
                'raw_capture_sha256':q.sha256(fixture.capture_path),'capture_runtime_abi':17,'module_runtime_abi':17,
                'translation_units':len(manifest['translation_units']),'raw_observations':1,'raw_retired_instructions':8,'raw_complete':True,
                'excluded_physical_ranges':manifest['excluded_physical_ranges'],'excluded_observations':0,'excluded_retired_hits':0,
                'native_identities':1,'mpr_contexts':1,'unsupported_observations':0,
                'assist_source_audit':q.audit_assist_source(fixture.capture,route,((1069880,6),)),
                'expected_native_hits':8,'execution_evidence':False,
                'scope':'Upstream17 emission from retained16composed profile plusactualzeroassist17reset capture, originalepochs retained. Inheritedentire6byte physicalsource span excluded acrossallvariants. Emission alone does not prove execution.'}
            q.validate_selection(selection,fixture.capture,fixture.capture_path,actual,route,route_path,TOOL_ROOT)
            public_selection=copy.deepcopy(selection)
            public_selection['scope']='Complete observed profile emitted through upstream API with entire verified-restored temporary-code spans excluded. Original capture identity, completeness and hit totals are preserved. Unknown/unvisited code and excluded source remain hybrid.'
            q.validate_selection(public_selection,fixture.capture,fixture.capture_path,actual,route,route_path,TOOL_ROOT)
            for field,value in (('execution_evidence',True),('scope','authored unsupported execution claim'),('expected_native_hits',9)):
                changed=copy.deepcopy(selection);changed[field]=value
                with self.assertRaises(ValueError):q.validate_selection(changed,fixture.capture,fixture.capture_path,actual,route,route_path,TOOL_ROOT)

    def test_official_binding_rejects_hidden_timing_payload_and_package_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture=ReceiptFixture(Path(temporary));original=copy.deepcopy(fixture.receipt)
            mutations=(lambda r:r['command'].extend(['--audio-timing','legacy']),
                lambda r:r['command'].extend(['--payload','authored']),
                lambda r:r['desktop_contract']['loaded_sdl_final'].update(pid=12346),
                lambda r:r['project_verification_after']['tool'].update(source_sha256='0'*64))
            for mutate in mutations:
                with self.subTest(mutation=mutate):
                    fixture.receipt=copy.deepcopy(original);mutate(fixture.receipt);fixture.save()
                    with self.assertRaises(ValueError):fixture.qualify()

    def test_receipt_rejects_capture_origin_retier_and_protected_input_tamper(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture=ReceiptFixture(Path(temporary));original=copy.deepcopy(fixture.receipt)
            for mutate in (lambda r:r['capture_contract']['window'].update(actual_start_ticks=1),
                lambda r:r['runner'].update(native_steps=6,interpreter_steps=2),
                lambda r:r['start_proof']['fetch_readback'][0].update(observed=233),
                lambda r:r['protected_inputs_after'][0].update(sha256='0'*64)):
                with self.subTest(mutation=mutate):
                    fixture.receipt=copy.deepcopy(original);mutate(fixture.receipt);fixture.save()
                    with self.assertRaises(ValueError):fixture.qualify()

    def test_coherent_fresh_fetch_forgery_still_must_equal_actual_bios(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture=ReceiptFixture(Path(temporary));value=fixture.receipt
            for initial in (value['states'][0],value['start_proof']['status_before'],value['start_proof']['status']):
                initial['host']['cpu']['instruction_bytes'][0]=233
            value['start_proof']['fetch_readback'][0].update(expected=233,observed=233)
            fixture.save()
            with self.assertRaisesRegex(ValueError,'authentic bound BIOS'):fixture.qualify()

    def test_actual_bounded_wav_format_is_checked_after_rehashing(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'wrong-rate.wav'
            with wave.open(str(path),'wb') as audio:
                audio.setnchannels(2);audio.setsampwidth(2);audio.setframerate(48000);audio.writeframes(bytes(q.WAV_LIMIT*4))
            with self.assertRaises(ValueError):q.validate_wav(path,pcm(215397015),{})

    def test_status_comparison_keeps_every_guest_source_cd_clock_and_pcm_field(self):
        desktop,headless=state(),state(desktop=False,native=0,interpreted=8)
        counts=q.compare_state(desktop,headless)
        self.assertEqual(counts[0]['total'],counts[1]['total'])
        for mutate in (lambda s:s['host']['cpu']['mpr'].__setitem__(7,1),
            lambda s:s['host']['cpu']['instruction_bytes'].__setitem__(6,233),
            lambda s:s['host']['cpu']['instruction_generations'].__setitem__(6,1),
            lambda s:s['host']['adpcm'].update(master_ticks=s['ticks']+1),
            lambda s:s['host']['audio_output'].update(pcm_hash=0),
            lambda s:s['host']['audio_output'].update(frames=s['host']['audio_output']['frames']-1),
            lambda s:s['host']['audio_output'].update(timing='legacy'),
            lambda s:s['host']['cd_audio'].update(new_guest_field=1),
            lambda s:s['host']['debug_memory'].update(write_requests=1)):
            with self.subTest(mutation=mutate):
                changed=copy.deepcopy(desktop);mutate(changed)
                with self.assertRaises(ValueError):q.compare_state(changed,headless)

    def test_known_request_sense_and_bad_unknown_origin_are_never_removed(self):
        desktop,headless=state(),state(desktop=False,native=0,interpreted=8)
        unknown={'accepted_responses':1,'opcodes':[{'opcode':255,'attempts':1}], 'last_command':[255],
            'origin':{'pc':256,'ticks':1,'mpr':[0]*8,'physical_pc':256,'fetch':[234]*7}}
        for value in (desktop,headless):
            value['host']['unknown_commands']=1;value['host']['cd_unknown']=copy.deepcopy(unknown)
        q.compare_state(desktop,headless)
        for mutate in (lambda s:s['host']['cd_unknown']['opcodes'][0].update(opcode=3),
            lambda s:s['host']['cd_unknown']['origin'].update(physical_pc=257),
            lambda s:s['host']['cd_unknown']['origin'].update(ticks=s['ticks']+1),
            lambda s:s['host']['cd_unknown']['origin']['fetch'].__setitem__(6,233)):
            with self.subTest(mutation=mutate):
                changed=copy.deepcopy(desktop);mutate(changed)
                with self.assertRaises(ValueError):q.compare_state(changed,headless)

    def test_actual_pinned_emission_rejects_guard_source_and_manifest_tamper(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);profile=capture();path=root/'profile.json';ReceiptFixture.dump(path,profile)
            loader=q.merge.load_capture_api(TOOL_ROOT);emitter=importlib.import_module(loader.__package__+'.emitter')
            output=root/'module';manifest=emitter.emit_capture(profile,output,q.sha256(path),exclude_ranges=((1069880,6),),single_unit=True)
            info={'files':{'module_manifest':str(output/'module.json')}}
            patches=[{'frame':1,'physical':1069880,'expected':'ea'*6,'data':'80'*6},
                {'frame':2,'physical':1069880,'expected':'80'*6,'data':'ea'*6}]
            route={'assistance':{'jump_patch_active':False,'code_patches':patches},
                'last_status':{'frame':2},'steps':[{'frame':p['frame'],'memory_write':
                    {'address':p['physical'],'expected':p['expected'],'data':p['data']}} for p in patches]}
            q.verify_candidate_emission(profile,path,info,TOOL_ROOT,route,{})
            unit=output/manifest['translation_units'][0]['file'];unit.write_bytes(unit.read_bytes()+b'\n// unauthorized source\n')
            with self.assertRaises(ValueError):q.verify_candidate_emission(profile,path,info,TOOL_ROOT,route,{})
            unit.write_bytes(unit.read_bytes().split(b'\n// unauthorized source')[0])
            changed=copy.deepcopy(manifest);changed['guards'].pop();ReceiptFixture.dump(output/'module.json',changed)
            with self.assertRaises(ValueError):q.verify_candidate_emission(profile,path,info,TOOL_ROOT,route,{})

    def test_composition_keeps_original16_and_actual_reset17_tiers_without_relabelling(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);old=capture(4,4);old['runtime_abi']=16;baseline=capture(0,8)
            old_path,new_path,baseline_path,receipt_path=[root/name for name in ('old16.json','profile17.json','baseline17.json','baseline-receipt.json')]
            ReceiptFixture.dump(old_path,old);ReceiptFixture.dump(baseline_path,baseline);ReceiptFixture.dump(receipt_path,{'authored':True})
            manifest={'schema':1,'kind':'ys3-observation-union','output_runtime_abi':17,'inputs':[]}
            for label,path,start,end in (('old',old_path,0,95686),('reset',baseline_path,0,14680)):
                manifest['inputs'].append({'capture':{'path':str(path),'sha256':q.sha256(path)},
                    'epoch':{'label':label,'window':{'start_frame':start,'end_frame':end},
                        'evidence':[{'path':str(receipt_path),'sha256':q.sha256(receipt_path)}]}})
            manifest_path=root/'manifest.json';ReceiptFixture.dump(manifest_path,manifest)
            api=q.merge.load_capture_api(TOOL_ROOT);profile,summary=q.merge.merge_captures([old,baseline],17,api.validate_capture)
            ReceiptFixture.dump(new_path,profile);_,entries,bound=q.merge.read_manifest(manifest_path)
            identity={'revision':q.TOOL['revision'],'runtime_abi':17,'tracked_source_clean':True,
                'shared_source_identity':{key:q.TOOL[key] for key in ('revision','source_sha256','source_files')}}
            receipt={'schema':1,'kind':'ys3-multi-run-observation-profile','tool_identity':identity,'tool_identity_after':copy.deepcopy(identity),
                'output_capture_runtime_abi':17,'capture_sha256':q.sha256(new_path),'capture_bytes':new_path.stat().st_size,
                'input_manifest':str(manifest_path),'input_manifest_sha256':q.sha256(manifest_path),
                'inputs':[dict(path=str(path),sha256=q.sha256(path),epoch=epoch,**summary['input_epochs'][index]) for index,(path,epoch) in enumerate(entries)],
                'evidence_sha256':{str(path):digest for path,digest in bound.items()},
                'profile_format_semantics':'Output ABI names the composed observation format, not a single execution. Original input runtime ABI and hit tiers remain unchanged in each bound epoch.',
                'provenance_semantics':'Epoch labels/windows are caller declarations retained verbatim and bound to evidence bytes; this composition does not independently verify their execution meaning.',
                **{key:value for key,value in summary.items() if key!='input_epochs'}}
            paths={'merge_manifest':manifest_path,'legacy_profile':old_path,'candidate_profile':new_path}
            actual,report=q.composition(paths,{'merge_receipt':receipt},TOOL_ROOT,baseline,receipt_path,{})
            self.assertEqual(actual['observations'][0]['native_hits'],4)
            self.assertEqual(actual['observations'][0]['interpreted_hits'],12)
            self.assertFalse(report['single_execution_evidence'])
            for mutate in (lambda value:value.update(runtime_abi=16),
                lambda value:value['observations'][0].update(native_hits=5,interpreted_hits=11)):
                changed=copy.deepcopy(profile);mutate(changed);ReceiptFixture.dump(new_path,changed)
                with self.assertRaises(ValueError):q.composition(paths,{'merge_receipt':receipt},TOOL_ROOT,baseline,receipt_path,{})

    def test_png_decoding_rejects_forged_metadata_and_unreviewed_fields(self):
        from scripts import replay_reset as api
        def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'authored.png'
            path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
                +chunk(b'IDAT',zlib.compress(b'\x00\x20\x40\x60'))+chunk(b'IEND',b''))
            image=dict(path=str(path),frame=120,ticks=43079406,frame_ticks=43079400,source='guest',**api.png_identity(path))
            self.assertEqual(q.bind_images([image],{})[0]['rgb_sha256'],image['rgb_sha256'])
            for mutate in (lambda value:value.update(rgb_sha256='0'*64),lambda value:value.update(ignored_guest_field=1)):
                changed=copy.deepcopy(image);mutate(changed)
                with self.assertRaises(ValueError):q.bind_images([changed],{})

    def test_actual_helper_prefix_reference_binding_shape_order_and_hashes_are_strict(self):
        from scripts import replay_reset as api
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);receipt=root/'receipt.json';receipt.write_text('{"authored":true}')
            images=[root/'image-120.png',root/'image-600.png']
            for index,path in enumerate(images):path.write_bytes(bytes([index]))
            # Same constructor and JSON-native shape as the actual frozen writer.
            actual={'receipt':api.binding(receipt),'images':[api.binding(path) for path in images]}
            hashes={};q.validate_prefix_image_reference(actual,receipt,images,hashes)
            self.assertEqual(len(hashes),3)
            for mutate in (lambda value:value['images'].reverse(),
                lambda value:value['images'][0].update(sha256='0'*64),
                lambda value:value.update(ignored_extra=True),lambda value:value.pop('images')):
                changed=copy.deepcopy(actual);mutate(changed)
                with self.assertRaises(ValueError):q.validate_prefix_image_reference(changed,receipt,images,{})

    def test_provenance_binding_rejects_missing_roles_or_a_file_changed_after_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path=root/'provenance.json'
            ReceiptFixture.dump(path,{'schema':1,'kind':'ys3-reset-native-provenance','tool':q.TOOL,'files':{}})
            with self.assertRaises(ValueError):q.load_provenance(path,{})
            artifact=root/'source';artifact.write_bytes(b'authored original');binding={'path':str(artifact),'sha256':q.sha256(artifact)}
            artifact.write_bytes(b'authored altered')
            with self.assertRaises(ValueError):q.artifact(binding,{})

    def input_fixture(self):
        api,_=q._api();reference={'states':[state(desktop=False,native=0,interpreted=8) for _ in range(56)]}
        receipt={'states':[state() for _ in range(56)],'actions':[['status'] for _ in range(60)],'input_status_annotations':[]}
        for values,desktop in ((reference['states'],False),(receipt['states'],True)):
            for index in (53,54):
                values[index]=state(11660,4185881703,desktop,native=5 if desktop else 0,interpreted=3 if desktop else 8)
                values[index]['host']['buttons']=[1,0,0,0,0]
            values[55]=state(11662,4186599699,desktop,native=6 if desktop else 0,interpreted=3 if desktop else 9)
        receipt['states'][54]['host']['buttons']=[0]*5
        receipt['actions'][58]=['input','0'];receipt['actions'][59]=['advance','2']
        witness={'schema':1,'reference_sha256':'a'*64,'audit':{'path':'authored-audit','sha256':'b'*64},
            'case':{'state_index':54,'action_index':58,'frame':11660,'ticks':4185881703,'previous_mask':1,
                'requested_mask':0,'reference_mask':1,'actual_mask':0,'next_state_index':55,'next_action_index':59,
                'next_frame':11662,'next_advance':2}}
        _,annotation=api.input_status_latency_bridge(reference['states'][54],receipt['states'][54],receipt['states'][53],
            reference_sha256='a'*64,state_index=54,action_index=58,action=receipt['actions'][58],
            next_reference_state=reference['states'][55],bridge=witness)
        receipt['input_status_annotations']=[api.confirm_input_status_bridge(annotation,reference['states'][55],receipt['states'][55],
            state_index=55,action_index=59,action=receipt['actions'][59])]
        return reference,receipt,witness

    def test_exact_audited_input_release_retains_raw_difference_and_strict_next_state(self):
        reference,receipt,witness=self.input_fixture();raw=copy.deepcopy(receipt)
        views,annotations=q.comparison_views(receipt,reference,'a'*64,witness)
        self.assertEqual(reference['states'][54]['host']['buttons'],[1,0,0,0,0])
        self.assertEqual(receipt,raw)
        self.assertEqual(views[54]['host']['buttons'],[0]*5)
        self.assertTrue(annotations[0]['next_confirmation']['strict_guest_match'])
        q.compare_state(receipt['states'][54],views[54])
        q.compare_state(receipt['states'][55],views[55])
        with self.assertRaises(ValueError):q.comparison_views(receipt,reference,'a'*64,None)

    def test_input_release_bridge_cannot_hide_source_clock_other_masks_or_next_failure(self):
        reference,receipt,witness=self.input_fixture()
        for mutate in (lambda value:value['states'][54]['host']['cpu']['instruction_generations'].__setitem__(0,1),
            lambda value:value['states'][54].update(ticks=4185881704),
            lambda value:value['states'][54]['host']['buttons'].__setitem__(1,1),
            lambda value:value['states'][55]['host']['buttons'].__setitem__(0,1),
            lambda value:value['actions'].__setitem__(59,['advance','1']),
            lambda value:value['input_status_annotations'][0]['next_confirmation'].update(strict_guest_match=False)):
            with self.subTest(mutation=mutate):
                changed=copy.deepcopy(receipt);mutate(changed)
                with self.assertRaises(ValueError):q.comparison_views(changed,reference,'a'*64,witness)

    def test_same_verified_windows_tool_root_accepts_slashes_and_descriptor_relative_alias(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);tool=root/'tool';tool.mkdir();folder=root/'candidate';folder.mkdir()
            left_descriptor=root/'baseline.toml';right_descriptor=folder/'candidate.toml'
            left_descriptor.write_text('authored baseline');right_descriptor.write_text('authored candidate')
            left={'name':'baseline','module':{'source':'authored-old'},'tool':dict(q.TOOL,path=str(tool)),
                'boot':{'mode':'system-card-reset','profile':'super'},'runtime':{'audio':'on'}}
            right=copy.deepcopy(left);right.update(name='candidate',module={'source':'authored-new'})
            original=copy.deepcopy(left)
            for spelling in (tool.as_posix(),'../tool','../tool/../tool'):
                right['tool']['path']=spelling
                q.compare_recipes(left,right,left_descriptor=left_descriptor,right_descriptor=right_descriptor,left_tool=tool,right_tool=tool)
            self.assertEqual(left,original)
            self.assertEqual(right['tool']['path'],'../tool/../tool')

    def test_recipe_rejects_different_verified_root_or_any_other_tool_or_recipe_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);first=root/'tool-one';second=root/'tool-two';first.mkdir();second.mkdir()
            descriptor=root/'project.toml';descriptor.write_text('authored')
            left={'name':'baseline','module':{},'tool':dict(q.TOOL,path=str(first)),'runtime':{'audio':'on'}}
            right=copy.deepcopy(left);right['tool']['path']=str(second)
            with self.assertRaises(ValueError):
                q.compare_recipes(left,right,left_descriptor=descriptor,right_descriptor=descriptor,left_tool=first,right_tool=second)
            with self.assertRaises(ValueError):q.canonical_recipe(right,descriptor,first)
            for mutate in (lambda value:value['tool'].update(source_sha256='0'*64),
                lambda value:value['runtime'].update(audio='off')):
                right=copy.deepcopy(left);mutate(right)
                with self.assertRaises(ValueError):
                    q.compare_recipes(left,right,left_descriptor=descriptor,right_descriptor=descriptor,left_tool=first,right_tool=first)


if __name__=='__main__':unittest.main()
