"""Real frozen-loader/emitter authored ABI16 native-gain qualification graphs."""
import copy
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import qualify_native16 as q
from scripts.replay_route import finish_managed_capture, managed_capture_selection
from tests.test_abi16_qualification import Matrix as Matrix16
from tests.test_dsp_qualification import dump, sha, DspEvidence

TOOL_ROOT = Path(__file__).resolve().parents[1] / '.deps/pcenginerecomp-abi16'


class Evidence:
    def __init__(self, root, extra_excluded=False):
        self.root, self.tool = root, TOOL_ROOT.resolve(strict=True)
        scaffold = Matrix16(root)
        template, raw_template = copy.deepcopy(scaffold.receipts[1]), copy.deepcopy(scaffold.runs[1])
        self.identity = template['tool_identity']
        self.frames = list(range(1, 39)) + [94800, 94900]
        payload, seed, historical = root/'authored-payload', root/'authored-seed', root/'authored-historical'
        command = [str(historical), str(payload), '0x100000', '0x4000', '255,248,128,129,130,131,132,0', '20000000000', '100000000000', 'hybrid',
                   '--dev-port', '0', '--dev-start-paused', 'on', '--dev-memory-write', 'on', '--bram', str(seed),
                   '--video-output', 'continuous', '--cd-unknown-status', 'gear-good']
        images=[]
        protected={str(p):sha(p) for p in (payload,seed,historical)}
        for frame in self.frames:
            path=root/f'checkpoint-{frame}.png';path.write_bytes(('authored image '+str(frame)).encode())
            images.append({'frame':frame,'file':str(path),'png_sha256':sha(path)});protected[str(path)]=sha(path)
        patches=[{'frame':1,'physical':1069880,'expected':'ea'*6,'data':'80'*6},
                 {'frame':2,'physical':1069880,'expected':'80'*6,'data':'ea'*6}]
        steps=[];at=0
        for target in self.frames:
            while at<target:
                count=min(600,target-at);at+=count;steps.append({'frames':count,'mask':0,'target_frame':at})
            if at in (1,2):
                p=patches[at-1]
                steps.append({'frame':at,'memory_write':{'address':p['physical'],'expected':p['expected'],'data':p['data']}})
            if at==2:
                for index in range(707):
                    length=2 if index<4 else 1
                    steps.append({'frame':2,'memory_write':{'address':8192+index*4,'expected':'00'*length,'data':'01'*length}})
        route={'initial_command':command,'binary_sha256':sha(historical),'initial_bram_sha256':sha(seed),
               'checkpoints':images,'steps':steps,'last_status':{'frame':94900,'paused':True,'host':{'cd_control':{'bram_seeded':True}}},
               'assistance':{'jump_patch_active':False,'code_patches':patches}}
        prefix=copy.deepcopy(route);prefix['checkpoints']=images[:39];prefix['steps']=steps[:-1];prefix['last_status']['frame']=94800
        self.route_path,self.prefix_route_path=root/'extended-route.json',root/'prefix-route.json'
        dump(self.route_path,route);dump(self.prefix_route_path,prefix)
        self.route,self.prefix_route=route,prefix
        mpr=[255,248,128,129,130,131,132,0]
        def observation(pc,native,interpreted):
            banks=mpr.copy()
            if pc>=0x5000:banks[2]=130
            return {'pc':pc,'mpr':banks,'physical':[(banks[pc>>13]<<13)|(pc&8191)],'data':[234],
                    'native_hits':native,'interpreted_hits':interpreted}
        old={'schema':1,'runtime_abi':13,'capacity':512,'retired_instructions':1981,'dropped_instructions':0,'unreadable_instructions':0,'complete':True,
             'observations':[observation(16384,500,0),observation(16640,500,0)]+[observation(21304+i,0,hits) for i,hits in enumerate((245,245,245,246))]}
        self.old_profile=root/'original13.json';dump(self.old_profile,old)
        self.captures=[{'schema':1,'runtime_abi':16,'capacity':512,'retired_instructions':10,'dropped_instructions':0,'unreadable_instructions':0,'complete':True,
                        'observations':[observation(16384,5,0),observation(16896,0,5)]},
                       {'schema':1,'runtime_abi':16,'capacity':512,'retired_instructions':10,'dropped_instructions':0,'unreadable_instructions':0,'complete':True,
                        'observations':[observation(16384,5,0),observation(16896,5,0)]}]
        if extra_excluded:
            for capture in self.captures:
                capture['retired_instructions']+=5
                capture['observations'].append(observation(21304,0,5))
        api=q.merge.load_capture_api(self.tool)
        merged,self.summary=q.merge.merge_captures([old,self.captures[0]],16,api.validate_capture)
        self.new_profile=root/'composed16.json';dump(self.new_profile,merged)
        emitter=importlib.import_module(api.__package__+'.emitter')
        self.modules=[];self.selections=[]
        for profile,profile_path,recipe,recipe_path,label in ((old,self.old_profile,prefix,self.prefix_route_path,'old'),(merged,self.new_profile,route,self.route_path,'new')):
            folder=root/('native-'+label)
            manifest=emitter.emit_capture(profile,folder,sha(profile_path),exclude_ranges=((1069880,6),),partition_size=1)
            files={entry['file']:folder/entry['file'] for field in ('translation_units','generated_headers') for entry in manifest[field]}
            self.modules.append((folder/'module.json',files))
            selection={'schema':1,'tool_identity':self.identity,'route_sha256':sha(recipe_path),'raw_capture_sha256':sha(profile_path),
                       'capture_runtime_abi':profile['runtime_abi'],'module_runtime_abi':16,'translation_units':len(manifest['translation_units']),
                       'raw_observations':len(profile['observations']),'raw_retired_instructions':profile['retired_instructions'],'raw_complete':True,
                       'excluded_physical_ranges':manifest['excluded_physical_ranges'],'excluded_observations':manifest['excluded_observations'],
                       'excluded_retired_hits':manifest['excluded_retired_hits'],'native_identities':manifest['native_instructions_emitted'],
                       'mpr_contexts':manifest['native_contexts'],'unsupported_observations':0,'assist_source_audit':q.audit_assist_source(profile,recipe,((1069880,6),)),
                       'expected_native_hits':profile['retired_instructions']-manifest['excluded_retired_hits'],'execution_evidence':False,
                       'scope':'Complete observed profile emitted through upstream API with entire verified-restored temporary-code spans excluded. Original capture identity, completeness and hit totals are preserved. Unknown/unvisited code and excluded source remain hybrid.'}
            selection_path=folder/'selection.json';dump(selection_path,selection);self.selections.append(selection_path)
        self.paths,self.receipts,self.runs=[],[],[]
        for index,name in enumerate(('qualified-prefix','coverage-baseline','coverage-candidate')):
            folder=root/name;folder.mkdir();binary=folder/'bin/game.exe';binary.parent.mkdir()
            binary.write_bytes(('authored executable '+name).encode());dll=binary.with_name('SDL3.dll');dll.write_bytes(b'authored adjacent SDL')
            receipt,run=copy.deepcopy(template),copy.deepcopy(raw_template)
            receipt['command']=command.copy();receipt['command'][0]=str(binary)
            receipt['command']+=['--audio-output','on','--audio-profile','filtered','--audio-rate','48000','--audio-out',str(folder/'audio.wav'),'--audio-frames','1440000','--hidden','on','--unthrottled','on']
            receipt.update(source_command=command.copy(),source_binary_anchor=str(historical),source_binary_sha256=sha(historical),
                           source_route=str(self.prefix_route_path if index==0 else self.route_path),source_route_sha256=sha(self.prefix_route_path if index==0 else self.route_path),
                           initial_bram_sha256=sha(seed),binary_sha256=sha(binary),memory_edits_replayed=709)
            receipt['input_sha256']=dict(protected,**{str(binary):sha(binary),receipt['source_route']:receipt['source_route_sha256']})
            count_frames=self.frames[:39] if index==0 else self.frames
            receipt['images']=[{k:v for k,v in item.items() if k!='file'} for item in images[:len(count_frames)]]
            core=copy.deepcopy(receipt['audio_contract']['validated_output'])
            def audio(source):
                output=copy.deepcopy(core);output['processing']['source_frames']=source;output['frames']=source*160//147
                output['wav_frames']=output['frames'];output['wav_truncated']=False
                full=copy.deepcopy(output);full.update(device_open=True,fast_forward_muted=True,
                    host={'submitted_frames':output['frames'],'dropped_frames':output['frames'],'clears':1,'pauses':1,'queued_frames':0,'peak_queue_frames':0,
                          'input_rate':48000,'device_rate':48000,'device_channels':2,'device_format':33056})
                return output,full
            def state(frame):
                status=copy.deepcopy(template['final_status']);suffix=frame>94800
                pcm,full=audio(110 if suffix else 100)
                status.update(frame=frame,ticks=((110 if suffix else 100)*21477273+44099)//44100)
                native=1000 if not suffix else (1005 if index==1 else 1010)
                interpreted=981 if not suffix or index==2 else 986
                if suffix and extra_excluded:interpreted+=5
                status['host'].update(native_steps=native,interpreter_steps=interpreted,audio_output=full,
                    debug_memory={'write_enabled':True,'write_requests':709,'bytes_changed':723})
                return status
            receipt['checkpoint_status']=[state(frame) for frame in count_frames]
            for field in q.ENDPOINTS:receipt[field]=copy.deepcopy(receipt['checkpoint_status'][-1])
            final=receipt['final_status'];final_core,final_full=audio(100 if index==0 else 110)
            receipt['audio_contract'].update(validated_output=final_core,wav_path=str(folder/'audio.wav'))
            DspEvidence.write_wave(folder/'audio.wav',48000,final_core['wav_frames'],True)
            receipt['audio_contract'].update(wav_sha256=sha(folder/'audio.wav'),wav_bytes=(folder/'audio.wav').stat().st_size)
            run.update(native_steps=final['host']['native_steps'],interpreter_steps=final['host']['interpreter_steps'],
                       native_block_steps=2 if index<2 else 3,interpreter_block_steps=3 if index<2 else 2,
                       guard_misses=final['host']['interpreter_steps'],ticks=final['ticks'],audio_output=final_full)
            run['desktop'].update(presented=count_frames[-1],polls=count_frames[-1]+1)
            receipt['desktop_contract'].update(presentation=copy.deepcopy(run['desktop']),audio_output=copy.deepcopy(final_full))
            package=receipt['desktop_contract']['package_before'];outputs={p.name:sha(p) for p in binary.parent.iterdir()}
            package.update(binary=str(binary),binary_sha256=sha(binary),dll=str(dll),dll_sha256=sha(dll),output_files=outputs)
            receipt['desktop_contract']['package_after']=copy.deepcopy(package)
            for field in ('loaded_sdl_before','loaded_sdl_final'):
                receipt['desktop_contract'][field].update(executable=str(binary),binary_sha256=sha(binary),loaded_sdl=str(dll),dll_sha256=sha(dll))
            scaffold.old.descriptor(folder,receipt,q.TOOL,self.modules[0 if index<2 else 1],False,True,False,outputs)
            descriptor=Path(receipt['project_descriptor']);descriptor.write_text(descriptor.read_text().replace('path='+json.dumps(str(root))+'\nrevision=', 'path='+json.dumps(str(self.tool))+'\nrevision='))
            self.rebind_descriptor(receipt)
            if index:
                boundary=copy.deepcopy(receipt['checkpoint_status'][38]);proof={'status_before':copy.deepcopy(boundary),'status':boundary,
                     'canonical_readback':[{'address':1069880,'expected':'ea'*6,'observed':'ea'*6}],
                     'retired_instructions':1981}
                run['code_capture_window']={'requested_start_frame':94800,'started':True,'actual_start_frame':94800,'actual_start_ticks':boundary['ticks'],
                                          'native_steps_before':1000,'interpreter_steps_before':981}
                capture_path=folder/'observed-code.json';dump(capture_path,self.captures[index-1])
                receipt['command']+=['--code-capture',str(capture_path),'--capture-limit','512','--code-capture-start-frame','94800']
                selected=managed_capture_selection(route,94800,512)
                receipt['capture_contract']=finish_managed_capture(capture_path,self.tool,selected,proof,run,expected_runtime_abi=16)
            self.paths.append(folder/'receipt.json');self.receipts.append(receipt);self.runs.append(run)
        self.manifest_path=root/'merge-manifest.json'
        self.merge_receipt_path=root/'merge-receipt.json'
        self.prefix_q=root/'prefix-qualified.json';self.provenance=root/'provenance.json'
        self.write()

    def rebind_descriptor(self,receipt):
        descriptor=Path(receipt['project_descriptor']);digest=sha(descriptor)
        receipt['project_descriptor_sha256']=digest;receipt['project_binding']['descriptor_sha256']=digest
        for field in ('project_verification_before','project_verification_after'):receipt[field]['descriptor_sha256']=digest
        path=Path(receipt['project_build'])/'build-receipt.json';built=json.loads(path.read_text());built['binding']['descriptor_sha256']=digest
        dump(path,built);receipt['project_build_receipt_sha256']=sha(path)

    def write(self):
        for path,receipt,run in zip(self.paths,self.receipts,self.runs):dump(path,receipt);dump(path.parent/'run.stdout',run)
        dump(self.prefix_q,{'passed':True,'tool':q.TOOL,'frames':94800,'images':39,'evidence_sha256':{str(p):sha(p) for p in (self.paths[0],self.paths[0].parent/'run.stdout',self.paths[0].parent/'audio.wav')}})
        manifest={'schema':1,'kind':'ys3-observation-union','output_runtime_abi':16,'inputs':[
            {'capture':{'path':str(self.old_profile),'sha256':sha(self.old_profile)},'epoch':{'label':'retained composed13 profile, not one execution','window':{'start_frame':0,'end_frame':94800},'evidence':[{'path':str(self.paths[0]),'sha256':sha(self.paths[0])}]}},
            {'capture':{'path':self.receipts[1]['capture_contract']['path'],'sha256':self.receipts[1]['capture_contract']['sha256']},'epoch':{'label':'actual16 baseline suffix','window':{'start_frame':94800,'end_frame':94900},'evidence':[{'path':str(self.paths[1]),'sha256':sha(self.paths[1])}]}}]}
        dump(self.manifest_path,manifest)
        _,entries,hashes=q.merge.read_manifest(self.manifest_path)
        receipt={'schema':1,'kind':'ys3-multi-run-observation-profile','tool_identity':self.identity,'tool_identity_after':self.identity,
            'output_capture_runtime_abi':16,'capture_sha256':sha(self.new_profile),'capture_bytes':self.new_profile.stat().st_size,
            'input_manifest':str(self.manifest_path),'input_manifest_sha256':sha(self.manifest_path),
            'inputs':[dict(path=str(path),sha256=sha(path),epoch=epoch,**self.summary['input_epochs'][index]) for index,(path,epoch) in enumerate(entries)],
            'evidence_sha256':{str(p):d for p,d in hashes.items()},
            'profile_format_semantics':'Output ABI names the composed observation format, not a single execution. Original input runtime ABI and hit tiers remain unchanged in each bound epoch.',
            'provenance_semantics':'Epoch labels/windows are caller declarations retained verbatim and bound to evidence bytes; this composition does not independently verify their execution meaning.',
            **{k:v for k,v in self.summary.items() if k!='input_epochs'}}
        dump(self.merge_receipt_path,receipt)
        roles={'prefix_receipt':self.paths[0],'prefix_qualification':self.prefix_q,'old_profile':self.old_profile,'new_profile':self.new_profile,
               'old_selection':self.selections[0],'new_selection':self.selections[1],'merge_manifest':self.manifest_path,'merge_receipt':self.merge_receipt_path}
        dump(self.provenance,{'schema':1,'kind':'ys3-native16-profile-provenance','tool':q.TOOL,'files':{role:{'path':str(path),'sha256':sha(path)} for role,path in roles.items()}})

    def qualify(self,**kwargs):
        with patch.object(q.abi16,'live_tool',return_value=self.identity):
            return q.qualify_native16(*self.paths[1:],prefix_receipt=self.paths[0],provenance=self.provenance,**kwargs)


class Native16QualificationTests(unittest.TestCase):
    def fixture(self, **kwargs):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        return Evidence(Path(temporary.name), **kwargs)

    def test_actual_loader_emitter_package_source_pcm_and_suffix_gain(self):
        result=self.fixture().qualify()
        self.assertTrue(result['passed']);self.assertEqual(result['native_steps_gained'],5)
        self.assertEqual(result['suffix_native_steps_gained'],5);self.assertEqual(result['images'],40)
        self.assertTrue(result['managed_capture']['exact_observation_identities_and_retired_hits'])
        self.assertTrue(result['emission'][1]['exact_pinned_emitter_source_and_guards'])
        self.assertFalse(result['composition']['single_execution_evidence'])

    def test_additional_original_excluded_work_stays_interpreted_and_in_provenance(self):
        result=self.fixture(extra_excluded=True).qualify()
        self.assertEqual(result['native_steps_gained'],5)
        self.assertEqual(result['emission'][0]['excluded_retired_hits'],981)
        self.assertEqual(result['emission'][1]['excluded_retired_hits'],986)
        self.assertEqual(result['emission'][1]['excluded_identities'],4)
        self.assertEqual(result['new_runner']['interpreted'],986)

    def test_timing_cd_clock_source_mpr_and_audio_must_remain_exact(self):
        fixture=self.fixture();original=copy.deepcopy((fixture.receipts,fixture.runs))
        mutations=(lambda f:f.receipts[2]['command'].extend(['--audio-timing','legacy']),
                   lambda f:f.runs[2]['cd_unknown']['origin']['fetch'].__setitem__(0,9),
                   lambda f:f.receipts[2]['checkpoint_status'][-1]['host']['cpu']['mpr'].__setitem__(0,9),
                   lambda f:f.runs[2].update(ticks=f.runs[2]['ticks']+488),
                   lambda f:f.receipts[2]['final_status']['host']['audio_output'].update(pcm_hash=17))
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                fixture.receipts,fixture.runs=copy.deepcopy(original);mutate(fixture);fixture.write()
                with self.assertRaises((ValueError,KeyError)):fixture.qualify()

    def test_loss_or_relabelled_capture_and_restore_proof_rejected(self):
        fixture=self.fixture()
        for field,value in (('dropped_instructions',1),('runtime_abi',13)):
            original=copy.deepcopy(fixture.receipts[2]['capture_contract'])
            fixture.receipts[2]['capture_contract']['capture'][field]=value;fixture.write()
            with self.assertRaises(ValueError):fixture.qualify()
            fixture.receipts[2]['capture_contract']=original
        fixture.receipts[2]['capture_contract']['start_proof']['canonical_readback'][0]['observed']='80'*6;fixture.write()
        with self.assertRaises(ValueError):fixture.qualify()

    def test_guard_source_and_original_hit_provenance_cannot_be_forged(self):
        fixture=self.fixture()
        selection=json.loads(fixture.selections[1].read_text());selection['raw_retired_instructions']+=1
        dump(fixture.selections[1],selection);fixture.write()
        with self.assertRaises(ValueError):fixture.qualify()
        fixture=self.fixture();path=fixture.modules[1][1]['module.cpp'];path.write_bytes(path.read_bytes()+b'changed guard')
        with self.assertRaises(ValueError):fixture.qualify()

    def test_no_suffix_gain_or_changed_total_blocks_is_rejected(self):
        fixture=self.fixture();fixture.runs[2]['interpreter_block_steps']+=1;fixture.write()
        with self.assertRaises(ValueError):fixture.qualify()
        fixture=self.fixture()
        # A purported improvement before94800 cannot qualify the new suffix.
        for state in fixture.receipts[2]['checkpoint_status']:
            state['host']['native_steps']+=5;state['host']['interpreter_steps']-=5
        fixture.write()
        with self.assertRaises(ValueError):fixture.qualify()

    def test_prefix_gain_does_not_replace_positive_suffix_gain(self):
        # Whole-route native gain5, but all5 already existed at the prefix.
        old={'native':1005,'interpreted':986,'total':1991}
        new={'native':1010,'interpreted':981,'total':1991}
        prefixes=({'native':1000,'interpreted':981,'total':1981},
                  {'native':1005,'interpreted':976,'total':1981})
        with self.assertRaisesRegex(ValueError,'94800 suffix'):
            q.measured_gain((old,new),prefixes,1)

    def test_actual_loader_rejects_loss_and_wrong_raw_source_mapping(self):
        for change in ('loss','mapping'):
            with self.subTest(change=change):
                fixture=self.fixture();contract=fixture.receipts[2]['capture_contract'];path=Path(contract['path'])
                value=json.loads(path.read_text())
                if change=='loss':value.update(dropped_instructions=1,retired_instructions=11)
                else:value['observations'][0]['physical'][0]+=1
                dump(path,value);contract['sha256']=sha(path)
                fixture.write()
                with self.assertRaises((ValueError,KeyError,q.subprocess.SubprocessError)):
                    fixture.qualify()

    def test_guarded_source_is_recomputed_not_only_trusted_from_hash_metadata(self):
        fixture=self.fixture();manifest_path,files=fixture.modules[1]
        manifest,artifacts=q.module_files(manifest_path,{})
        module=({},manifest_path,manifest,artifacts)
        profile,_=q.merge.load_capture_api(fixture.tool).load_capture(fixture.new_profile)
        selection=json.loads(fixture.selections[1].read_text())
        recipe=copy.deepcopy(fixture.route);recipe['_path']=str(fixture.route_path)
        files['module.cpp'].write_bytes(files['module.cpp'].read_bytes()+b'// guard changed')
        with self.assertRaisesRegex(ValueError,'differs from pinned guarded emitter'):
            q.verify_emission(module,profile,fixture.new_profile,selection,recipe,fixture.tool)

    def test_qualification_and_composed_execution_provenance_are_not_relabelled(self):
        fixture=self.fixture()
        value=json.loads(fixture.prefix_q.read_text());value['passed']=False;dump(fixture.prefix_q,value)
        bundle=json.loads(fixture.provenance.read_text());bundle['files']['prefix_qualification']['sha256']=sha(fixture.prefix_q);dump(fixture.provenance,bundle)
        with self.assertRaisesRegex(ValueError,'prefix.qualified'):fixture.qualify()
        fixture=self.fixture()
        value=json.loads(fixture.merge_receipt_path.read_text());value['execution_evidence']=True;dump(fixture.merge_receipt_path,value)
        bundle=json.loads(fixture.provenance.read_text());bundle['files']['merge_receipt']['sha256']=sha(fixture.merge_receipt_path);dump(fixture.provenance,bundle)
        with self.assertRaisesRegex(ValueError,'composition.complete_receipt'):fixture.qualify()

    def test_inherited_relative_images_keep_the_exact_bound_prefix_origin(self):
        fixture=self.fixture()
        extension=fixture.root/'extension';extension.mkdir()
        old_route_path=fixture.route_path
        fixture.route_path=extension/'route.json'
        # The inherited filename belongs to the prefix route's parent. The
        # extended route has a different parent and must not rebase that file.
        filename='checkpoint-1.png'
        fixture.prefix_route['checkpoints'][0]['file']=filename
        fixture.route['checkpoints'][0]['file']=filename
        # Another inherited image has an explicit per-checkpoint origin.
        inherited=fixture.root/'captured-origin';inherited.mkdir()
        original=fixture.root/'checkpoint-2.png'
        copied=inherited/original.name;copied.write_bytes(original.read_bytes())
        for recipe in (fixture.prefix_route,fixture.route):
            recipe['checkpoints'][1]['file']=original.name
            recipe['checkpoints'][1]['source_capture_root']=str(inherited)
        # New suffix images belong to the extended route's declared origin.
        suffix=extension/'suffix.png'
        suffix.write_bytes((fixture.root/'checkpoint-94900.png').read_bytes())
        fixture.route['checkpoints'][-1]['file']='suffix.png'
        dump(fixture.prefix_route_path,fixture.prefix_route);dump(fixture.route_path,fixture.route)
        for index,receipt in enumerate(fixture.receipts):
            receipt['input_sha256'].pop(str(original))
            receipt['input_sha256'][str(copied)]=sha(copied)
            if index==0:
                receipt['source_route_sha256']=sha(fixture.prefix_route_path)
            else:
                receipt['input_sha256'].pop(str(old_route_path))
                receipt['source_route']=str(fixture.route_path)
                receipt['source_route_sha256']=sha(fixture.route_path)
                receipt['input_sha256'][str(suffix)]=sha(suffix)
            receipt['input_sha256'][receipt['source_route']]=receipt['source_route_sha256']
        for path,recipe_path in zip(fixture.selections,(fixture.prefix_route_path,fixture.route_path)):
            value=json.loads(path.read_text());value['route_sha256']=sha(recipe_path);dump(path,value)
        fixture.write()
        self.assertTrue(fixture.qualify()['passed'])
        # A changed inherited origin cannot be substituted by matching a
        # basename elsewhere, even when the same image bytes exist there.
        fixture.route['checkpoints'][0]['source_capture_root']=str(inherited)
        dump(fixture.route_path,fixture.route)
        for receipt in fixture.receipts[1:]:
            receipt['source_route_sha256']=sha(fixture.route_path)
            receipt['input_sha256'][str(fixture.route_path)]=sha(fixture.route_path)
        fixture.write()
        with self.assertRaisesRegex(ValueError,'original_prefix_checkpoint_bindings'):
            fixture.qualify()

    def test_image_binding_never_searches_an_undeclared_matching_basename(self):
        fixture=self.fixture()
        unrelated=fixture.root/'unrelated';unrelated.mkdir()
        filename='checkpoint-1.png';original=fixture.root/filename
        impostor=unrelated/filename;impostor.write_bytes(original.read_bytes())
        checkpoint=fixture.prefix_route['checkpoints'][0].copy()
        checkpoint['file']='missing/'+filename
        inputs={str(impostor):sha(impostor)}
        with self.assertRaisesRegex(ValueError,'declared-origin/input binding'):
            q.bind_route_image(checkpoint,fixture.prefix_route,fixture.prefix_route_path,inputs,{})

    def test_original39_images_no_new_assists_and_actual_package_are_required(self):
        fixture=self.fixture();original=copy.deepcopy(fixture.receipts)
        for mutate in (lambda f:f.receipts[2]['images'][0].update(png_sha256='f'*64),
                       lambda f:f.receipts[2].update(memory_edits_replayed=710),
                       lambda f:f.receipts[2]['capture_contract']['window'].update(actual_start_frame=94799)):
            fixture.receipts=copy.deepcopy(original);mutate(fixture);fixture.write()
            with self.assertRaises(ValueError):fixture.qualify()
        fixture=self.fixture();Path(fixture.receipts[2]['command'][0]).with_name('SDL3.dll').write_bytes(b'wrong DLL')
        with self.assertRaises(ValueError):fixture.qualify()


if __name__=='__main__':unittest.main()
