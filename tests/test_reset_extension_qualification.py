"""Authored extension evidence; no game, retail inputs or compiler runs."""
import contextlib,copy,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

from scripts import qualify_reset_extension as q,replay_reset as r,replay_reset_extension as driver
from tests.test_reset_native import ReceiptFixture,state,capture

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/'.deps/pcenginerecomp-abi17'


def raw(rows):
    return {'schema':1,'runtime_abi':17,'capacity':65536,'complete':True,'dropped_instructions':0,'unreadable_instructions':0,
        'retired_instructions':sum(row['native_hits']+row['interpreted_hits']for row in rows),'observations':rows}


def observation(pc,native,interpreted,*,excluded=False,variant=0):
    mpr=[0]*8
    if excluded:mpr[pc>>13]=130
    mpr[7]=variant
    return {'pc':pc,'mpr':mpr,'physical':[(mpr[pc>>13]<<13)|(pc&8191)],'data':[234],
        'native_hits':native,'interpreted_hits':interpreted}


def sources():
    prefix=raw([observation(256,q.PREFIX_NATIVE,0)])
    old=raw(copy.deepcopy(prefix['observations'])+[observation(21304,0,hits,excluded=True,variant=index)
        for index,hits in enumerate((245,245,245,246))])
    baseline=raw(copy.deepcopy(prefix['observations'])+[observation(512,0,10),observation(21304,0,3,excluded=True)])
    candidate=raw(copy.deepcopy(prefix['observations'])+[observation(512,10,0),observation(21304,0,3,excluded=True)])
    api=q.merge.load_capture_api(TOOL)
    expanded,_=q.merge.merge_captures([old,baseline],17,api.validate_capture)
    return baseline,candidate,prefix,old,expanded


def timeline_fixture():
    actions=[];prefix_states=[state(0,0,native=0,interpreted=0)];images=[];frame=0
    for index in range(1,105):
        delta=140 if index<=100 else 170;actions.append(['advance',str(delta)]);frame+=delta
        prefix_states.append(state(frame,frame*400000,native=frame*q.PREFIX_NATIVE//14680,interpreted=0))
        if index<=10:
            actions.append(['capture']);images.append({'phase':'prefix','source':'guest','frame':frame,'ticks':frame*400000})
    root={'error':None,'states':copy.deepcopy(prefix_states),'actions':actions+[['quit']],
        'images':[{'frame':image['frame']}for image in images],'inputs_unchanged':{'authored':True},'child_stopped':True,'returncode':0}
    root['states']=[dict(s,host={**s['host'],'native_steps':0,'interpreter_steps':s['host']['native_steps']})for s in root['states']]
    plan=r.route_plan(root);plan={**plan,'actions':plan['actions'][:-1],
        'deferred_terminal_action':{'source_index':114,'action':['quit']},'source_action_mapping':list(range(114)),'executed_prefix_actions':114}
    boundary=copy.deepcopy(prefix_states[-1]);immediate=copy.deepcopy(boundary);immediate['host']['buttons'][0]=8
    advance=state(14690,14690*400000,native=q.PREFIX_NATIVE,interpreted=10);advance['host']['buttons'][0]=8
    rows=[{'phase':'prefix','state':s}for s in prefix_states]+[
        {'phase':'boundary','state':boundary},{'phase':'extension-input-status','state':immediate},
        {'phase':'extension','state':advance},{'phase':'extension-capture-status','state':copy.deepcopy(advance)},
        {'phase':'terminal-proof','state':copy.deepcopy(advance)}]
    requests=[{'binding':{'path':'authored-request','sha256':'a'*64},'value':value}for value in(
        {'id':1,'op':'advance','mask':8,'frames':10},{'id':2,'op':'capture'},{'id':3,'op':'finish'})]
    images+=[{'phase':'boundary','source':'guest','frame':14680,'ticks':boundary['ticks']}]
    images+=[{'phase':'extension','source':'guest','frame':14690,'ticks':advance['ticks']}for _ in range(2)]
    receipt={'schema':1,'kind':q.KINDS[0],'prefix_plan':plan,'states':[row['state']for row in rows],
        'requests':requests,'images':images,'final_status':rows[-1]['state'],
        'prefix_boundary':{'frames':14680,'state_index':104,'states':105,'actions_executed':114,'deferred_source_quit_index':114,
            'source_action_mapping':list(range(114)),'native_steps':q.PREFIX_NATIVE,'interpreter_steps':0,
            'status':prefix_states[-1],'fresh_status':boundary,'input_status_annotations':[]}}
    receipt['actions']=driver.expected_action_journal(plan,requests)
    return receipt,rows,root


class CommonProofFixture:
    """Real descriptor/package/capture bindings; fake PE is never executed."""
    def __init__(self,root):
        self.base=ReceiptFixture(root);base=self.base.receipt;desktop=base['desktop_contract'];self.out=self.base.out
        helper=r.binding(Path(q.__file__));guarded=[r.binding(Path(r.__file__))]
        readiness=self.out/'execution-inputs.json'
        self.base.dump(readiness,{'ready':True,'helper':helper,'frozen_files':guarded})
        frozen={'readiness':r.binding(readiness),'helper':helper,'frozen_files':guarded}
        self.value={'schema':1,'kind':q.KINDS[0],'passed':True,'error':None,'memory_edits':0,'natural_quit':True,
            'child_stopped':True,'exit_code':0,'cwd_initially_empty':True,'cwd_finally_empty':True,'cwd':desktop['working_directory'],
            'tool_identity_before':base['tool_identity_before'],'tool_identity_after':base['tool_identity_after'],
            'project_descriptor':{'path':base['project_descriptor'],'sha256':base['project_descriptor_sha256']},
            'project_build_receipt':base['project_build_receipt'],
            'project_verification_before':{k:v for k,v in base['project_verification_before'].items()if k not in('schema','verified')},
            'project_verification_after':{k:v for k,v in base['project_verification_after'].items()if k not in('schema','verified')},
            'package_before':desktop['package_before'],'package_after':desktop['package_after'],
            'loaded_sdl_before':desktop['loaded_sdl_before'],'loaded_sdl_final':desktop['loaded_sdl_final'],'environment':desktop['environment'],
            'asset_hashes_before':base['asset_hashes_before'],'asset_hashes_after':base['asset_hashes_after'],
            'protected_inputs_before':base['protected_inputs_before'],'protected_inputs_after':base['protected_inputs_after'],
            'command':base['command'],'runner':base['runner'],'capture_contract':base['capture_contract'],'start_proof':base['start_proof'],
            'boot_validation':base['boot_validation'],'states':base['states'],'final_status':base['final_status'],
            'frozen_before':frozen,'frozen_after':copy.deepcopy(frozen),'requests':[],'actions':[],'idle_heartbeat_count':0}
        self.save()

    def save(self):
        self.base.dump(self.out/'run.stdout',self.value['runner'])
        (self.out/'states.jsonl').write_text(''.join(json.dumps({'phase':'prefix','state':s})+'\n'for s in self.value['states']))
        (self.out/'actions.jsonl').write_text(''.join(json.dumps(s)+'\n'for s in self.value['actions']))
        (self.out/'heartbeats.jsonl').write_text('')
        self.value['raw_files']={name:r.binding(self.out/name)for name in
            ('run.stdout','run.stderr','states.jsonl','actions.jsonl','heartbeats.jsonl','audio.wav','observed-code.json')}
        self.base.dump(self.base.path,self.value)

    def bind(self):
        with patch.object(self.base.desc,'USA_BIOS_SHA256',self.base.bios_hash):return q.bind_receipt(self.base.path,q.KINDS[0],{})


class ExtensionSourcesTests(unittest.TestCase):
    def test_actual_shared_loader_and_positive_new_source_gain_preserve_exclusions(self):
        baseline,candidate,prefix,old,expanded=sources()
        report=q.measured_gain(baseline,candidate,prefix,old,expanded,10)
        self.assertEqual(report['native_steps_gained'],10)
        self.assertEqual(report['newly_executed_native_identities'],1)
        self.assertEqual(report['new_suffix']['interpreted'],3)
        self.assertEqual(sum(row['native_hits']+row['interpreted_hits']for row in expanded['observations']if q.excluded(row)),984)
        with tempfile.TemporaryDirectory()as temporary:
            path=Path(temporary)/'capture.json';path.write_text(json.dumps(candidate))
            run={'native_steps':q.PREFIX_NATIVE+10,'interpreter_steps':3,'native_block_steps':0,'interpreter_block_steps':0,'guard_misses':3}
            self.assertEqual(q.old.load_capture(TOOL,path,run,65536,{})[1]['total'],q.PREFIX_NATIVE+13)

    def test_prefix_only_gain_or_emitted_but_unexecuted_identity_cannot_qualify(self):
        b,c,p,o,n=sources()
        with self.assertRaises(ValueError):q.measured_gain(b,copy.deepcopy(b),p,o,n,1)
        forged=copy.deepcopy(c);forged['observations'][0]['native_hits']+=10;forged['observations'][0]['interpreted_hits']-=0
        forged['observations'][1].update(native_hits=0,interpreted_hits=10)
        with self.assertRaises(ValueError):q.measured_gain(b,forged,p,o,n,1)
        for minimum in(True,1.0,0,11):
            with self.subTest(minimum=minimum),self.assertRaises(ValueError):q.measured_gain(b,c,p,o,n,minimum)

    def test_counterbalanced_native_regression_and_source_mpr_or_byte_forgery_reject(self):
        b,c,p,o,n=sources()
        mutations=(lambda x:x['observations'][0].update(native_hits=q.PREFIX_NATIVE-1,interpreted_hits=1),
            lambda x:x['observations'][1]['mpr'].__setitem__(7,1),
            lambda x:x['observations'][1]['data'].__setitem__(0,233),
            lambda x:x['observations'][2].update(native_hits=1,interpreted_hits=2))
        for mutate in mutations:
            changed=copy.deepcopy(c);mutate(changed)
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):q.measured_gain(b,changed,p,o,n,1)

    def test_newly_executed_source_must_exist_in_actual_emitted_eligible_set(self):
        b,c,p,o,n=sources();n['observations']=[row for row in n['observations']if row['pc']!=512]
        n['observations'].append(observation(768,0,10))
        with self.assertRaises(ValueError):q.measured_gain(b,c,p,o,n,1)

    def test_gain_on_existing_source_cannot_substitute_for_new_emitted_execution(self):
        b,c,p,o,n=sources()
        b['observations'][0]['interpreted_hits']=10
        c['observations'][0]['native_hits']+=10;c['observations'][1].update(native_hits=0,interpreted_hits=10)
        b=raw(b['observations']);c=raw(c['observations'])
        n,_=q.merge.merge_captures([o,b],17,q.merge.load_capture_api(TOOL).validate_capture)
        with self.assertRaisesRegex(ValueError,'newly emitted'):q.measured_gain(b,c,p,o,n,1)

    def test_loss_runtime_relabel_and_per_tier_redistribution_are_not_capacity(self):
        b,c,p,o,n=sources()
        run={'native_steps':q.PREFIX_NATIVE+10,'interpreter_steps':3,'native_block_steps':0,'interpreter_block_steps':0,'guard_misses':3}
        with tempfile.TemporaryDirectory()as temporary:
            path=Path(temporary)/'capture.json'
            for mutate in(lambda x:x.update(runtime_abi=16),lambda x:x.update(complete=False),
                lambda x:x.update(dropped_instructions=1,retired_instructions=x['retired_instructions']+1),
                lambda x:x['observations'][1].update(native_hits=9,interpreted_hits=1)):
                changed=copy.deepcopy(c);mutate(changed);path.write_text(json.dumps(changed))
                with self.subTest(mutation=mutate),self.assertRaises(ValueError):q.old.load_capture(TOOL,path,run,65536,{})


class ExtensionTimelineTests(unittest.TestCase):
    def test_literal_prefix_deferred_quit_and_typed_input_observation(self):
        value,rows,root=timeline_fixture();raw=copy.deepcopy(value)
        report=q.validate_timeline(value,rows,root)
        self.assertEqual(report['frames'],14690);self.assertEqual(len(report['input_diagnostics']),1)
        self.assertEqual(report['input_diagnostics'][0]['proof']['observed_buttons'],[8,0,0,0,0])
        self.assertEqual(value,raw)
        prior=copy.deepcopy(value);observed=copy.deepcopy(rows);observed[106]['state']['host']['buttons'][0]=0
        prior['states']=[row['state']for row in observed]
        other=q.validate_timeline(prior,observed,root)
        self.assertEqual(report['views'],other['views'])

    def test_immediate_input_cannot_hide_any_clock_generation_pcm_cd_or_tier_change(self):
        value,rows,root=timeline_fixture()
        mutations=(lambda s:s.update(ticks=s['ticks']+1),lambda s:s['host']['cpu']['instruction_generations'].__setitem__(0,1),
            lambda s:s['host']['audio_output'].update(pcm_hash=7),lambda s:s['host']['cd_audio'].update(unreviewed=1),
            lambda s:s['host'].update(native_steps=q.PREFIX_NATIVE+1),lambda s:s['host']['buttons'].__setitem__(0,2))
        for mutate in mutations:
            changed,observed=copy.deepcopy(value),copy.deepcopy(rows);mutate(observed[106]['state']);changed['states']=[row['state']for row in observed]
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):q.validate_timeline(changed,observed,root)

    def test_settled_mask_extra_action_omitted_state_or_faked115_prefix_reject(self):
        value,rows,root=timeline_fixture()
        for mutate in(lambda v,s:v['actions'].insert(114,{'phase':'prefix','action':['quit'],'frame_before':14680}),
            lambda v,s:s.pop(),lambda v,s:v['prefix_plan']['actions'].append(['quit']),
            lambda v,s:s[107]['state']['host']['buttons'].__setitem__(0,0),
            lambda v,s:v['requests'][0]['value'].update(frames=10.0)):
            changed,observed=copy.deepcopy(value),copy.deepcopy(rows);mutate(changed,observed);changed['states']=[row['state']for row in observed]
            with self.subTest(mutation=mutate),self.assertRaises((ValueError,IndexError)):q.validate_timeline(changed,observed,root)

    def test_raw_input_proof_is_recomputed_not_trusted(self):
        value,rows,root=timeline_fixture();value['kind']=q.KINDS[1]
        computed=q.validate_timeline({**value,'kind':q.KINDS[0]},rows,root)
        value['extension_input_diagnostics']=[{'state_index':row['state_index'],**row['proof']}for row in computed['input_diagnostics']]
        q.validate_timeline(value,rows,root)
        value['extension_input_diagnostics'][0]['static_guest_source_pcm']=False
        with self.assertRaises(ValueError):q.validate_timeline(value,rows,root)

    def test_heartbeats_are_exact_same_run_paused_states_not_deterministic_route_steps(self):
        value,rows,root=timeline_fixture();typed=q.validate_timeline(value,rows,root)
        value['idle_heartbeat_count']=1;beat={'phase':'idle-status-heartbeat','monotonic':1.0,'status':copy.deepcopy(value['states'][105])}
        report=q.validate_heartbeats({'receipt':value,'heartbeats':[beat]},typed)
        self.assertTrue(report['all_equal_settled_same_run_states'])
        beat['status']['host']['cpu']['instruction_bytes'][0]=233
        with self.assertRaises(ValueError):q.validate_heartbeats({'receipt':value,'heartbeats':[beat]},typed)

    def prefix_visibility_fixture(self,prior_variant):
        from tests.test_reset_replay import latency_fixture,pcm
        reference,released,previous,following,options=latency_fixture()
        after=copy.deepcopy(following);after['host']['audio_output']=pcm(after['ticks'],True)
        root={'states':[copy.deepcopy(reference if i<55 else following)for i in range(105)]}
        selected={'states':[copy.deepcopy(previous if i<54 else released if i==54 else after)for i in range(105)]}
        actual=copy.deepcopy(selected['states'])
        if prior_variant:actual[54]=copy.deepcopy(previous)
        actions=[]
        for index in range(1,105):
            actions.append(['input','0']if index==54 else ['advance','2']if index==55 else ['status'])
            if index<=5 or 56<=index<=60:actions.append(['capture'])
        checker=driver.PrefixCheck(root,selected,options['bridge'],options['reference_sha256'])
        checker.state(actual[0],-1,None);index=0
        for ai,words in enumerate(actions):
            if words[0]in('advance','input','status'):index+=1;checker.state(actual[index],ai,words)
        receipt={'states':actual,'prefix_plan':{'actions':actions},'prefix_boundary':checker.finish()}
        return receipt,root,selected,options

    def test_both_exact_prefix54_raw_variants_retain_separate_confirmed_proofs(self):
        for variant in(False,True):
            with self.subTest(prior_variant=variant):
                value,root,selected,options=self.prefix_visibility_fixture(variant);original=copy.deepcopy(value['states'])
                timeline={'views':[{'state':None}for _ in range(105)]}
                proofs=q.prefix_comparison(value,root,selected,options['bridge'],options['reference_sha256'],timeline)
                self.assertEqual(value['states'],original)
                self.assertEqual(len(proofs['selected_native_prefix']),int(variant))
                self.assertEqual(len(proofs['original_reference']),int(not variant))
                self.assertEqual(timeline['views'][54]['state']['host']['buttons'],[0]*5)
                for group in proofs.values():
                    for proof in group:self.assertTrue(proof['next_confirmation']['strict_guest_match'])

    def test_prefix54_visibility_does_not_hide_source_or_native_counter_drift(self):
        for mutate in(lambda s:s['host']['cpu']['instruction_generations'].__setitem__(0,2),
            lambda s:s['host'].update(native_steps=1),lambda s:s['host']['buttons'].__setitem__(1,1)):
            value,root,selected,options=self.prefix_visibility_fixture(True);mutate(value['states'][54])
            with self.subTest(mutation=mutate),self.assertRaises(ValueError):
                q.prefix_comparison(value,root,selected,options['bridge'],options['reference_sha256'],{'views':[{}for _ in range(105)]})


class ExtensionBindingsTests(unittest.TestCase):
    def test_recorded_baseline_pointer_resolves_only_to_exact_actual_target_and_hash(self):
        with tempfile.TemporaryDirectory()as temporary:
            root=Path(temporary);path=root/'receipt.json';path.write_text('{"authored":true}')
            other=root/'other.json';other.write_text('{"authored":true}')
            for spelling in(str(path),'receipt.json','./receipt.json'):
                with self.subTest(spelling=spelling),patch.object(q,'ROOT',root):
                    value={'path':spelling,'sha256':r.sha256(path)};original=copy.deepcopy(value)
                    self.assertEqual(q.baseline_link(value,path,{})['path'],str(path));self.assertEqual(value,original)
            for value in({'path':'other.json','sha256':r.sha256(path)},{'path':'receipt.json','sha256':'0'*64},
                {'path':'receipt.json','sha256':r.sha256(path),'ignored':True}):
                with self.subTest(binding=value),patch.object(q,'ROOT',root),self.assertRaises(ValueError):q.baseline_link(value,path,{})

    def test_actual_official_json_native_descriptor_package_and_capture_reader(self):
        with tempfile.TemporaryDirectory()as temporary:
            fixture=CommonProofFixture(Path(temporary));bound=fixture.bind()
            self.assertTrue(all(type(path)is str for path in bound['info']['files'].values()))
            self.assertEqual(bound['capture_report']['native'],5);self.assertEqual(bound['capture_report']['interpreted'],3)
            self.assertEqual(bound['receipt']['kind'],q.KINDS[0])

    def test_actual_bindings_reject_wrong_argv_pin_pid_and_raw_source_proof(self):
        with tempfile.TemporaryDirectory()as temporary:
            fixture=CommonProofFixture(Path(temporary));original=copy.deepcopy(fixture.value)
            for mutate in(lambda v:v['command'].extend(['--audio-timing','legacy']),
                lambda v:v['tool_identity_before']['shared_source_identity'].update(source_files=54.0),
                lambda v:v['loaded_sdl_final'].update(pid=12346),
                lambda v:v['start_proof']['fetch_readback'][0].update(observed=233)):
                fixture.value=copy.deepcopy(original);mutate(fixture.value);fixture.save()
                with self.subTest(mutation=mutate):
                    with self.assertRaises(ValueError):fixture.bind()
            fixture.value=copy.deepcopy(original);fixture.save()
            fixture.value['raw_files']['arbitrary_capture']={'path':'authored','sha256':'0'*64}
            fixture.base.dump(fixture.base.path,fixture.value)
            with self.assertRaises(ValueError):fixture.bind()

    def test_raw_journal_duplicate_keys_are_rejected_even_with_matching_file_hash(self):
        with tempfile.TemporaryDirectory()as temporary:
            fixture=CommonProofFixture(Path(temporary));path=fixture.out/'states.jsonl'
            line=json.dumps(fixture.value['states'][0]);path.write_text('{"phase":"prefix","phase":"extension","state":'+line+'}\n')
            fixture.value['raw_files']['states.jsonl']=r.binding(path);fixture.base.dump(fixture.base.path,fixture.value)
            with self.assertRaisesRegex(ValueError,'duplicate JSON key'):fixture.bind()

    def test_provenance_types_and_unknown_roles_fail_before_any_source_lookup(self):
        base={'schema':1,'kind':'ys3-reset-extension-provenance','tool':copy.deepcopy(q.TOOL),'prefix_frame':14680,
            'minimum_native_gain':1,'files':{name:{'path':'unread','sha256':'0'*64}for name in q.ROLES}}
        with tempfile.TemporaryDirectory()as temporary:
            path=Path(temporary)/'provenance.json'
            for mutate,pattern in((lambda v:v.update(minimum_native_gain=True),'minimum native gain'),
                (lambda v:v.update(minimum_native_gain=1.0),'minimum native gain'),
                (lambda v:v.update(prefix_frame=14680.0),'prefix'),
                (lambda v:v['tool'].update(runtime_abi=True),'tool'),
                (lambda v:v['files'].update(ignored_role={}),'provenance roles')):
                changed=copy.deepcopy(base);mutate(changed);path.write_text(json.dumps(changed))
                with self.subTest(mutation=mutate),self.assertRaisesRegex(ValueError,pattern):q.load_provenance(path,{})

    def test_qualifier_duplicate_cli_or_runtime_override_is_rejected_before_reading(self):
        base=['qualify']+sum((['--'+name,'authored']for name in('baseline-receipt','candidate-receipt','provenance','out')),[])
        for extra in(['--provenance','other'],['--tool-root','other']):
            with self.subTest(extra=extra),patch.object(sys,'argv',base+extra),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):q.main()
