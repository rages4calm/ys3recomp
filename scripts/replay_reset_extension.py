"""Repeat a closed, unassisted reset discovery recipe with strict raw evidence.

The original terminal quit is deferred until after the explicit extension.
Only reviewed exact ABI17/18 source identities are accepted. No private helper,
input search, memory-write feature or runtime fork is required.
"""
from __future__ import annotations
import argparse,copy,hashlib,importlib,importlib.util,json,os,subprocess,sys,tomllib
from pathlib import Path
from . import replay_reset as reset
from .prepare_reset_descriptor import validate_reset_descriptor
from .desktop_contract import validate_package_proof
ROOT=Path(__file__).resolve().parents[1]
TOOLS={
 'bb3b695b782352bdfacd8db877f2a843bd1242f1':('5d3551481d1245d8cec9011d0f390ad0b464720c2d1f37a0fce601d0888e7a0d',54),
 '95fe3e07e63b0869de8c9d7b70681b5c557abf01':('60c37d9fb5b1a1318cd2509c7ac1cc45c03a9939116d04e836aa67e0e03c4ffb',57),
 '6935e46ff8aefacf8ea058a385198299c4e2cd5c':('9414ed390229b8d411f2f79f6c22080d68fef7b09aef2bf99db0046751e34cf0',60)}
TOOL_ABIS={
 'bb3b695b782352bdfacd8db877f2a843bd1242f1':17,
 '95fe3e07e63b0869de8c9d7b70681b5c557abf01':17,
 '6935e46ff8aefacf8ea058a385198299c4e2cd5c':18}
KINDS={'ys3-reset-interactive-discovery','ys3-reset-extension-replay'}


def require(ok,label):reset.require(ok,label)


def counts(value):
    host=value['host'];native=reset.integer(host['native_steps']);interpreted=reset.integer(host['interpreter_steps'])
    return {'native':native,'interpreted':interpreted,'total':native+interpreted}


def validate_input_status(previous_settled,immediate,requested_mask):
    """Validate an ACK-adjacent observation within its own paused execution."""
    reset.integer(requested_mask,255,label='requested input mask')
    before=reset.normalize_status(previous_settled,desktop=True)
    after=reset.normalize_status(immediate,desktop=True)
    prior=before['host']['buttons'];observed=after['host']['buttons'];requested=[requested_mask,0,0,0,0]
    require(observed in(prior,requested),'Immediate input status must retain prior or requested mask')
    after['host']['buttons']=copy.deepcopy(prior)
    require(before==after,'Input intent cannot advance CPU/time/source/CD/PCM or retirement counts')
    return {'classification':'input-intent-status','previous_buttons':copy.deepcopy(prior),
            'requested_buttons':requested,'observed_buttons':copy.deepcopy(observed),
            'guest_time_advanced':False,'static_guest_source_pcm':True}


def validate_advance(previous,actual,requested_mask,frames):
    reset.integer(frames,600,1,'advance frames');reset.integer(requested_mask,255,label='advance mask')
    reset.normalize_status(previous,desktop=True);reset.normalize_status(actual,desktop=True)
    require(actual['frame']==previous['frame']+frames and actual['ticks']>previous['ticks'],
            'Exact advancing frame boundary required')
    require(actual['host']['buttons']==[requested_mask,0,0,0,0],'Settled advancing input must match requested mask')
    a,b=counts(previous),counts(actual)
    require(b['total']>a['total']and b['native']>=a['native']and b['interpreted']>=a['interpreted'],
            'Advancing retirement counters must conserve monotonic work')
    return counts(actual)


def compare_state(actual,expected,*,phase,previous_settled=None,requested_mask=None):
    actual_counts=counts(actual);expected_counts=counts(expected)
    if phase=='extension-input-status':
        require(previous_settled is not None and requested_mask is not None,'Typed immediate input context required')
        proof=validate_input_status(previous_settled,actual,requested_mask)
        reset.normalize_status(expected,desktop=True)
        return {'classification':'input-intent-status','actual_counts':actual_counts,'expected_counts':expected_counts,'diagnostic':proof}
    require(phase in('prefix','boundary','extension','extension-capture-status','terminal-proof'),
            'Unknown deterministic state phase')
    require(reset.normalize_status(actual,desktop=True,project_tiers=True)
            ==reset.normalize_status(expected,desktop=True,project_tiers=True),'Settled guest/source/CD/PCM state differs')
    require(actual_counts['total']==expected_counts['total'],'Total retired work differs at settled checkpoint')
    return {'classification':'settled','actual_counts':actual_counts,'expected_counts':expected_counts,'diagnostic':None}


def identity_abi(value):
    """Validate a recorded exact reviewed identity without relabelling its ABI."""
    reset.keys(value,{'revision','runtime_abi','tracked_source_clean','shared_source_identity'},'verified tool identity')
    revision=value['revision']
    require(type(revision)is str and revision in TOOLS,'Unreviewed exact toolkit revision')
    source,files=TOOLS[revision];abi=TOOL_ABIS[revision]
    reset.keys(value['shared_source_identity'],{'revision','source_sha256','source_files'},'canonical shared identity')
    require(type(value['runtime_abi'])is int and type(value['shared_source_identity']['source_files'])is int
            and value['runtime_abi']==abi and value['tracked_source_clean']is True
            and value['shared_source_identity']=={'revision':revision,'source_sha256':source,'source_files':files},
            'Exact clean reviewed source/ABI/file count required')
    return abi


def verify_identity(tool,revision=None):
    if revision is None:revision=json.loads((ROOT/'toolchain.json').read_text())['tool']['revision']
    require(type(revision)is str and revision in TOOLS,'Unreviewed exact toolkit revision')
    source,_=TOOLS[revision];abi=TOOL_ABIS[revision]
    command=[sys.executable,'-B',str(ROOT/'scripts/verify_tool.py'),'--tool-root',str(tool),
             '--expected-revision',revision,'--expected-abi',str(abi),'--expected-source-sha256',source]
    value=json.loads(subprocess.check_output(command,cwd=ROOT,text=True,timeout=60))
    require(value.get('revision')==revision,'Verified revision differs from selection')
    identity_abi(value)
    return value


def normalize_recipe_runner(value,*,project_tiers=False,capture=None):
    """Validate each receipt's capture against its own reviewed execution ABI."""
    abi=identity_abi(value['tool_identity_before'])
    require(value['tool_identity_before']==value['tool_identity_after'],'Recipe tool identity changed')
    reset.validate_capture_contract(value['capture_contract'],value['runner'],capture,expected_abi=abi)
    return reset.normalize_runner(value['runner'],desktop=True,project_tiers=project_tiers,
                                  capture_contract=value['capture_contract'],expected_abi=abi)


def load_shared(tool):
    tool=Path(tool).resolve(strict=True);name='_ys3_reset_extension_'+hashlib.sha256(str(tool).encode()).hexdigest()[:16]
    package=tool/'pcerecomp'
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,package/'__init__.py',submodule_search_locations=[str(package)])
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    else:require(Path(sys.modules[name].__file__).resolve()==package/'__init__.py','Shared namespace path collision')
    project=importlib.import_module(name+'.project');capture=importlib.import_module(name+'.capture')
    spec=importlib.util.spec_from_file_location(name+'_dev_client',tool/'scripts/dev_client.py')
    client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
    return project,capture,client


def epoch_map(path):
    if path is None:return {}
    value=reset.strict_json(path);reset.keys(value,{'schema','mappings'},'source epoch map')
    require(type(value['schema'])is int and value['schema']==1 and isinstance(value['mappings'],list),'Explicit epoch schema1')
    result={}
    for row in value['mappings']:
        reset.keys(row,{'original','sha256','preserved'},'source epoch')
        original=str(Path(row['original']).resolve());key=(original,row['sha256'])
        require(key not in result,'Duplicate original/hash epoch')
        result[key]=reset.check_binding({'path':row['preserved'],'sha256':row['sha256']})
    return result


def bound(value,epochs):
    reset.keys(value,{'path','sha256'},'artifact binding')
    key=(str(Path(value['path']).resolve()),value['sha256'])
    return reset.check_binding({'path':str(epochs[key])if key in epochs else value['path'],'sha256':value['sha256']})


def closed_recipe(value,observations):
    require(value.get('schema')==1 and type(value['schema'])is int and value.get('kind')in KINDS
            and value.get('passed')is True and value.get('natural_quit')is True and value.get('child_stopped')is True
            and type(value.get('exit_code'))is int and value['exit_code']==0
            and type(value.get('memory_edits'))is int and value['memory_edits']==0,
            'Closed zero-assist reset recipe required')
    require(value['prefix_plan']['actions']==value['prefix_plan']['actions'][:114]
            and len(value['prefix_plan']['actions'])==114
            and value['prefix_plan']['deferred_terminal_action']=={'source_index':114,'action':['quit']},'Exact deferred terminal quit')
    require(isinstance(value['requests'],list)and 1<=len(value['requests'])<=512,'Bounded closed request recipe')
    frame=14680
    for index,row in enumerate(value['requests'],1):
        reset.keys(row,{'binding','value'},'request journal row');item=row['value'];op=item.get('op')
        reset.keys(item,{'id','op','mask','frames'}if op=='advance'else{'id','op'},'request control')
        require(type(item['id'])is int and item['id']==index and op in('advance','capture','finish'),'Sequential ordinary request')
        if op=='advance':
            reset.integer(item['mask'],255,label='request mask');reset.integer(item['frames'],600,1,'request frames');frame+=item['frames']
        require(frame<=30000,'Closed recipe frame bound')
        require((op=='finish')==(index==len(value['requests'])),'Exactly one final finish required')
    require(observations and [x['state']for x in observations]==value['states'],'Raw phase journal must match every stored state')
    expected_phases=['prefix']*105+['boundary']
    for row in value['requests']:
        op=row['value']['op']
        expected_phases+=['extension-input-status','extension']if op=='advance'else(['extension-capture-status']if op=='capture'else['terminal-proof'])
    require([x['phase']for x in observations]==expected_phases,'Complete exact phase/state recipe required')
    require(value['states'][104]['frame']==value['states'][105]['frame']==14680
            and value['states'][-1]['frame']==frame,'Opening and final settled frames required')
    require(value['prefix_boundary']['status']==value['states'][104]
            and value['prefix_boundary']['fresh_status']==value['states'][105],'Exact raw prefix boundary mapping')
    require(value['actions']==expected_action_journal(value['prefix_plan'],value['requests']),
            'Exact complete ordinary action journal required before launch')
    previous=value['states'][105];index=106
    for row in value['requests']:
        item=row['value'];op=item['op']
        if op=='advance':
            validate_input_status(previous,value['states'][index],item['mask'])
            validate_advance(previous,value['states'][index+1],item['mask'],item['frames'])
            previous=value['states'][index+1];index+=2
        else:
            require(reset.normalize_status(previous,desktop=True)==reset.normalize_status(value['states'][index],desktop=True),
                    'Capture/terminal raw state cannot advance guest/source/PCM')
            previous=value['states'][index];index+=1
    require(len(value['images'])==11+len(value['requests'])-1
            and [x['phase']for x in value['images']]==['prefix']*10+['boundary']+['extension']*(len(value['requests'])-1),
            'Exact prefix/boundary/request image mapping required')
    return copy.deepcopy(value['requests'])


def expected_action_journal(plan,requests):
    result=[];frame=0
    def add(words,phase):result.append({'phase':phase,'action':words,'frame_before':frame})
    for words in plan['actions']:
        add(copy.deepcopy(words),'prefix')
        if words[0]=='advance':frame+=int(words[1])
    require(frame==14680,'Exact prefix timeline')
    add(['status'],'boundary')
    for row in requests:
        item=row['value'];op=item['op']
        if op=='finish':add(['status'],'terminal-proof');add(['quit'],'terminal')
        elif op=='advance':
            add(['input',str(item['mask'])],'extension');add(['status'],'extension-input-status')
            add(['advance',str(item['frames'])],'extension');frame+=item['frames'];add(['capture'],'extension')
        elif op=='capture':add(['status'],'extension-capture-status');add(['capture'],'extension')
        else:raise ValueError('Unexpected closed control')
    return result


def read_recipe(binding,epochs):
    path=bound(binding,epochs);value=reset.strict_json(path)
    for item in value['raw_files'].values():bound(item,epochs)
    journal=value['raw_files'].get('states.jsonl',value['raw_files'].get('states'))
    require(journal is not None,'Raw phase journal binding required')
    observations=[json.loads(line)for line in bound(journal,epochs).read_text().splitlines()]
    for row in observations:reset.keys(row,{'phase','state'},'raw state observation')
    requests=closed_recipe(value,observations)
    for row in requests:bound(row['binding'],epochs)
    require(value['package_before']==value['package_after']and value['project_verification_before']==value['project_verification_after']
            and value['asset_hashes_before']==value['asset_hashes_after']and value['tool_identity_before']==value['tool_identity_after']
            and value['frozen_before']==value['frozen_after'],'Baseline bindings changed during execution')
    require(value['protected_inputs_before']==value['protected_inputs_after']and len(value['protected_inputs_before'])==7,
            'Seven preserved baseline originals required')
    validate_package_proof({'package_before':value['package_before'],'environment':value['environment'],
        'loaded_sdl_before':value['loaded_sdl_before'],'loaded_sdl_final':value['loaded_sdl_final']},value['package_before']['binary_sha256'])
    for role in ('helper','readiness'):bound(value['frozen_before'][role],epochs)
    for item in value['frozen_before']['frozen_files']:bound(item,epochs)
    for image in value['images']:
        png=reset.png_identity(bound({'path':image['path'],'sha256':image['png_sha256']},epochs))
        require(all(png[k]==image[k]for k in('width','height','rgb_sha256')),'Bound decoded discovery PNG')
    abi=identity_abi(value['tool_identity_before'])
    declaration=tomllib.loads(bound(value['project_descriptor'],epochs).read_text())['tool']
    recorded=value['tool_identity_before'];shared=recorded['shared_source_identity']
    require(declaration['revision']==recorded['revision']and declaration['source_sha256']==shared['source_sha256']
            and type(declaration['runtime_abi'])is int and declaration['runtime_abi']==abi,'Recipe descriptor/tool identity differs')
    tool=Path(declaration['path'])
    require(verify_identity(tool,recorded['revision'])==recorded,'Recipe shared loader source differs')
    _,capture,_=load_shared(tool);raw,digest=capture.load_capture(bound({'path':value['capture_contract']['path'],'sha256':value['capture_contract']['sha256']},epochs))
    require(digest==value['capture_contract']['sha256'],'Original baseline capture hash')
    normalize_recipe_runner(value,capture=raw)
    return value,observations,requests


def selected_prefix_status_view(reference_state,actual_state,selected_state,previous_actual_state,*,
                               reference_sha256,state_index,action_index,action,next_reference_state,witness):
    """Validate only the witnessed state54 prior-mask variant against selected0."""
    _,proof=reset.input_status_latency_bridge(reference_state,selected_state,previous_actual_state,
        reference_sha256=reference_sha256,state_index=state_index,action_index=action_index,action=action,
        next_reference_state=next_reference_state,bridge=witness)
    require(actual_state['host']['buttons']==reference_state['host']['buttons']==[1,0,0,0,0]
            and selected_state['host']['buttons']==[0]*5,'Only exact prior1 versus selected-release0 is eligible')
    require(reset.normalize_status(actual_state,desktop=True)==reset.normalize_status(previous_actual_state,desktop=True),
            'Candidate prior-mask snapshot cannot change any guest/source/PCM/tier field')
    view=copy.deepcopy(actual_state);view['host']['buttons']=[0]*5
    require(reset.normalize_status(view,desktop=True)==reset.normalize_status(selected_state,desktop=True),
            'Selected prefix mismatch extends beyond the witnessed input phase')
    annotation={'kind':'audited-selected-prefix-input-status','reference_sha256':reference_sha256,
                'case':proof['case'],'action':copy.deepcopy(action),'reference_state':copy.deepcopy(reference_state),
                'actual_state':copy.deepcopy(actual_state),'selected_state':copy.deepcopy(selected_state),
                'previous_actual_state':copy.deepcopy(previous_actual_state),'next_confirmation':None}
    return view,annotation


class PrefixCheck:
    def __init__(self,reference,selected,witness,reference_sha):
        self.reference=reference;self.selected=selected;self.witness=witness;self.reference_sha=reference_sha
        self.states=[];self.annotations=[];self.selected_annotations=[]
    def state(self,actual,action_index,action):
        index=len(self.states);self.states.append(actual);expected=self.reference['states'][index]
        view=reset.normalize_status(actual,desktop=True,project_tiers=True)
        if self.annotations and index==55:self.annotations[0]=reset.confirm_input_status_bridge(self.annotations[0],expected,actual,state_index=index,action_index=action_index,action=action)
        if self.selected_annotations and index==55:self.selected_annotations[0]=reset.confirm_input_status_bridge(self.selected_annotations[0],expected,actual,state_index=index,action_index=action_index,action=action)
        if view!=reset.normalize_status(expected,desktop=False,project_tiers=True):
            require(index==54 and self.witness is not None,'Only the original audited prefix snapshot may differ')
            expected,annotation=reset.input_status_latency_bridge(expected,actual,self.states[-2],reference_sha256=self.reference_sha,
                state_index=index,action_index=action_index,action=action,next_reference_state=self.reference['states'][index+1],bridge=self.witness)
            require(not self.annotations,'One audited prefix exception');self.annotations.append(annotation)
        require(view==reset.normalize_status(expected,desktop=False,project_tiers=True),'Original reset prefix mismatch')
        selected_view=actual
        if reset.normalize_status(actual,desktop=True)!=reset.normalize_status(self.selected['states'][index],desktop=True):
            require(index==54 and not self.selected_annotations,'Only witnessed selected prefix state54 may differ')
            selected_view,annotation=selected_prefix_status_view(self.reference['states'][index],actual,self.selected['states'][index],self.states[-2],
                reference_sha256=self.reference_sha,state_index=index,action_index=action_index,action=action,
                next_reference_state=self.reference['states'][index+1],witness=self.witness)
            self.selected_annotations.append(annotation)
        require(reset.normalize_status(selected_view,desktop=True)==reset.normalize_status(self.selected['states'][index],desktop=True),
                'Selected qualified prefix source/guest/PCM/native counts differ')
        return selected_view
    def finish(self):
        require(len(self.states)==105 and all(a['next_confirmation']is not None for a in self.annotations+self.selected_annotations),'Exact complete prefix required')
        return {'frames':14680,'state_index':104,'states':105,'actions_executed':114,'deferred_source_quit_index':114,
                'source_action_mapping':list(range(114)),'status':copy.deepcopy(self.states[-1]),
                'input_status_annotations':copy.deepcopy(self.annotations),
                'selected_input_status_annotations':copy.deepcopy(self.selected_annotations),
                'native_steps':self.states[-1]['host']['native_steps'],'interpreter_steps':self.states[-1]['host']['interpreter_steps']}


def preflight(args):
    epochs=epoch_map(args.baseline_epochs);baseline_binding={'path':str(args.baseline_receipt),'sha256':args.baseline_receipt_sha256}
    baseline,observations,requests=read_recipe(baseline_binding,epochs)
    tool=args.tool_root.resolve(strict=True);identity=verify_identity(tool,args.expected_revision);api,capture,module=load_shared(tool)
    descriptor=args.descriptor.resolve(strict=True);build=args.build_dir.resolve(strict=True);out=args.out.resolve()
    require(out.is_relative_to(ROOT/'.local')and not out.exists(),'Fresh private output required')
    verified=api.verify(descriptor);selected=validate_reset_descriptor(tomllib.loads(descriptor.read_text()),descriptor)
    built=reset.strict_json(build/'build-receipt.json');require(built['binding']==api._binding(verified),'Official candidate build binding')
    require(Path(selected['tool']['path']).resolve()==tool,'Candidate descriptor tool differs')
    require(selected['tool']['revision']==identity['revision']
            and selected['tool']['source_sha256']==identity['shared_source_identity']['source_sha256']
            and selected['tool']['runtime_abi']==identity_abi(identity),'Candidate descriptor/source/ABI differs')
    binary=Path(built['binary']);package=reset.package_checks.verify_package(built,binary)
    old_config=tomllib.loads(bound(baseline['project_descriptor'],epochs).read_text());new_config=tomllib.loads(descriptor.read_text())
    for key in ('boot','runtime','limits','bios','toc','disc','libchdr'):require(new_config[key]==old_config[key],'Candidate recipe changed '+key)
    reference=reset.strict_json(bound(baseline['reference']['receipt'],epochs));prefix=reset.strict_json(bound(baseline['selected_prefix'],epochs))
    plan=copy.deepcopy(baseline['prefix_plan']);require(plan['actions']==reset.route_plan(reference)['actions'][:-1],'Original114 action prefix required')
    witness=prefix['input_status_bridge_witness'];reset.validate_input_status_bridge(witness,baseline['reference']['receipt']['sha256'])
    baseline_check=PrefixCheck(reference,prefix,witness,baseline['reference']['receipt']['sha256'])
    baseline_check.state(baseline['states'][0],-1,None);state_index=0
    for action_index,words in enumerate(plan['actions']):
        if words[0]in('advance','input','status'):
            state_index+=1;baseline_check.state(baseline['states'][state_index],action_index,words)
    baseline_prefix_validation=baseline_check.finish()
    for actual,expected in zip(baseline['images'][:10],prefix['images']):
        require(all(actual[k]==expected[k]for k in('width','height','frame','ticks','frame_ticks','source','rgb_sha256')),'Selected011 prefix image changed')
    originals=reset.protected_inputs({'protected_originals':baseline['protected_inputs_before']})
    guarded=[reset.binding(ROOT/'scripts'/name)for name in('replay_reset_extension.py','replay_reset.py','replay_route.py',
             'verify_tool.py','prepare_reset_descriptor.py','package_checks.py','desktop_contract.py','audio_contract.py',
             'audio15_contract.py','dsp_contract.py','compat16_contract.py')]
    guarded+=[reset.binding(descriptor),reset.binding(build/'build-receipt.json'),reset.binding(bound(baseline_binding,epochs))]
    return (epochs,baseline_binding,baseline,observations,requests,tool,identity,api,capture,module,descriptor,build,out,
            verified,selected,built,binary,package,reference,prefix,plan,witness,originals,guarded,baseline_prefix_validation)


def run(args):
    (epochs,baseline_binding,baseline,observations,requests,tool,identity,api,capture,module,descriptor,build,out,
     verified,selected,built,binary,package,reference,prefix,plan,witness,originals,guarded,baseline_prefix_validation)=preflight(args)
    out.mkdir();cwd=out/'cwd';cwd.mkdir();command=reset.reset_command(api,verified,binary,out)
    env,isolation=reset.package_checks.packaged_environment(binary);env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONSAFEPATH='1',PYTHONPATH=str(tool))
    result={'schema':1,'kind':'ys3-reset-extension-replay','passed':False,'error':None,'baseline_receipt':baseline_binding,
            'tool_identity_before':identity,'project_descriptor':reset.binding(descriptor),'project_build_receipt':reset.binding(build/'build-receipt.json'),
            'project_verification_before':api._binding(verified),'package_before':package,'environment':isolation,
            'protected_inputs_before':originals,'asset_hashes_before':verified['identities'],'helper_bindings_before':guarded,
            'command':command,'cwd':str(cwd),'cwd_initially_empty':True,'prefix_plan':plan,'selected_prefix':baseline['selected_prefix'],
            'reference':baseline['reference'],'states':[],'state_observations':[],'actions':[],'images':[],'requests':[],
            'extension_input_diagnostics':[],'memory_edits':0,'natural_quit':False,
            'baseline_prefix_validation':baseline_prefix_validation,
            'scope':'Same closed ordinary reset-extension recipe; no campaign, listening or hardware claim.'}
    execution_inputs={'schema':1,'kind':'ys3-reset-extension-launch-inputs','ready':True,'tool_identity':identity,
                      'baseline_receipt':baseline_binding,'helper':reset.binding(Path(__file__)),'frozen_files':guarded}
    (out/'execution-inputs.json').open('x').write(json.dumps(execution_inputs,indent=2)+'\n')
    frozen={'readiness':reset.binding(out/'execution-inputs.json'),'helper':reset.binding(Path(__file__)),'frozen_files':guarded}
    result['frozen_before']=frozen
    (out/'launch.json').open('x').write(json.dumps(result,indent=2)+'\n')
    states=(out/'states.jsonl').open('x');actions=(out/'actions.jsonl').open('x');child=None;problem=None
    (out/'heartbeats.jsonl').open('x').close()  # No interactive idle states in a closed deterministic replay.
    checker=PrefixCheck(reference,prefix,witness,baseline['reference']['receipt']['sha256'])
    try:
        child=reset.ResetChild(command,cwd,out,env,600);require(child.ready.wait(15)and child.process.poll()is None and not child.failure,'Candidate TCP startup')
        result['loaded_sdl_before']=reset.package_checks.inspect_loaded_sdl(child.process.pid,binary.with_name('SDL3.dll'),binary)
        with module.DevClient(child.port,timeout=90)as client:
            def action(words,phase):
                row={'phase':phase,'action':copy.deepcopy(words),'frame_before':result['states'][-1]['frame']if result['states']else 0}
                result['actions'].append(row);actions.write(json.dumps(row)+'\n');actions.flush()
                require(row==baseline['actions'][len(result['actions'])-1],'Exact deterministic action journal required')
            def state(raw,phase,previous=None,mask=None):
                index=len(result['states']);row={'phase':phase,'state':raw};result['states'].append(raw);result['state_observations'].append(row)
                states.write(json.dumps(row)+'\n');states.flush();require(observations[index]['phase']==phase,'Exact state phase')
                comparison_actual=raw
                if phase=='prefix':
                    ai=len(result['actions'])-1
                    comparison_actual=checker.state(raw,ai,None if ai<0 else plan['actions'][ai])
                expected_state=prefix['states'][index]if phase=='prefix'else observations[index]['state']
                comparison=compare_state(comparison_actual,expected_state,phase=phase,previous_settled=previous,requested_mask=mask)
                if comparison['diagnostic']is not None:result['extension_input_diagnostics'].append({'state_index':index,**comparison['diagnostic']})
                return raw
            def image(phase):
                metadata,rgb=client.capture('guest');index=len(result['images']);path=out/f'frame-{metadata["frame"]}-{index}.png'
                module.write_capture(path,metadata,rgb);decoded=reset.png_identity(path)
                row={'path':str(path),**metadata,**{k:v for k,v in decoded.items()if k not in('width','height')},'phase':phase};result['images'].append(row)
                expected=baseline['images'][index]
                require(all(row[k]==expected[k]for k in('width','height','frame','ticks','frame_ticks','source','rgb_sha256','phase')),'Strict guest image/meta')
            initial=state(client.call('status'),'prefix');reset.validate_initial_status(initial,selected['boot'])
            bios=Path(selected['files']['bios']);vector=bios.read_bytes()[8190:8192];actual_vector=client.read_memory(8190,2);reads=[]
            for address,expected in zip(initial['host']['cpu']['instruction_physical'],initial['host']['cpu']['instruction_bytes']):
                observed=client.read_memory(address,1)[0];require(observed==expected,'Original source fetch proof');reads.append({'address':address,'expected':expected,'observed':observed})
            proof_status=client.call('status');result['start_proof']={'status_before':initial,'status':proof_status,'retired_instructions':0,
                'vector_readback':{'address':8190,'expected':vector.hex(),'observed':actual_vector.hex()},'fetch_readback':reads}
            require(vector==actual_vector and reset.normalize_status(initial,desktop=True)==reset.normalize_status(proof_status,desktop=True),'Fresh unmodified reset0 proof')
            for index,words in enumerate(plan['actions']):
                action(words,'prefix');name=words[0]
                if name=='advance':raw=state(client.advance(int(words[1])),'prefix')
                elif name=='input':client.call('set_input',port=0,mask=int(words[1]));raw=state(client.call('status'),'prefix')
                elif name=='status':raw=state(client.call('status'),'prefix')
                elif name=='capture':image('prefix')
                else:raise ValueError('Original terminal quit must be deferred')
            result['prefix_boundary']=checker.finish();action(['status'],'boundary');latest=state(client.call('status'),'boundary')
            require(reset.normalize_status(latest,desktop=True)==reset.normalize_status(result['states'][104],desktop=True),'Fresh exact14680 boundary')
            result['prefix_boundary']['fresh_status']=latest;image('boundary')
            for row in requests:
                item=row['value'];result['requests'].append(copy.deepcopy(row));op=item['op']
                if op=='finish':
                    action(['status'],'terminal-proof');latest=state(client.call('status'),'terminal-proof')
                    result['loaded_sdl_final']=reset.package_checks.inspect_loaded_sdl(child.process.pid,binary.with_name('SDL3.dll'),binary)
                    action(['quit'],'terminal');client.call('quit');result['natural_quit']=True;break
                if op=='advance':
                    previous=latest;action(['input',str(item['mask'])],'extension');client.call('set_input',port=0,mask=item['mask'])
                    action(['status'],'extension-input-status');state(client.call('status'),'extension-input-status',previous,item['mask'])
                    action(['advance',str(item['frames'])],'extension');latest=state(client.advance(item['frames']),'extension')
                    validate_advance(previous,latest,item['mask'],item['frames'])
                else:
                    action(['status'],'extension-capture-status');latest=state(client.call('status'),'extension-capture-status')
                action(['capture'],'extension');image('extension')
            result['final_status']=latest;child.process.wait(timeout=15);require(child.process.returncode==0 and not child.failure,'Natural candidate exit')
        require(len(result['states'])==len(observations)and len(result['images'])==len(baseline['images'])
                and result['actions']==baseline['actions'],'Complete exact closed recipe required')
        result['passed']=True
    except BaseException as error:problem=error;result['error']=repr(error)
    finally:
        states.close();actions.close()
        if child is not None:child.close();result['child_stopped']=child.process.poll()is not None;result['exit_code']=child.process.returncode
        try:
            result['protected_inputs_after']=reset.protected_inputs({'protected_originals':originals});require(result['protected_inputs_after']==originals,'Originals changed')
            after=api.verify(descriptor);result['project_verification_after']=api._binding(after);result['asset_hashes_after']=after['identities']
            require(result['project_verification_after']==result['project_verification_before'],'Candidate bindings changed')
            result['package_after']=reset.package_checks.verify_package(built,binary);require(result['package_after']==package,'PE/DLL package changed')
            result['tool_identity_after']=verify_identity(tool,identity['revision']);require(result['tool_identity_after']==identity,'Tool source changed')
            for binding in guarded:reset.check_binding(binding)
            result['helper_bindings_after']=[reset.binding(item['path'])for item in guarded]
            require(result['helper_bindings_after']==guarded,'Helper/config epochs changed')
            reset.check_binding(frozen['readiness']);result['frozen_after']=copy.deepcopy(frozen)
            result['cwd_finally_empty']=not any(cwd.iterdir());require(result['cwd_finally_empty'],'Private cwd acquired files')
            if problem is None:
                runner=reset.strict_json(out/'run.stdout');result['runner']=runner;raw,digest=capture.load_capture(out/'observed-code.json')
                contract={'schema':1,'runtime_abi':identity_abi(identity),'path':str(out/'observed-code.json'),'sha256':digest,'bytes':(out/'observed-code.json').stat().st_size,
                    'start_frame':0,'capacity':65536,'start_proof':result['start_proof'],'capture':{k:v for k,v in raw.items()if k!='observations'},'observations':len(raw['observations']),'window':runner['code_capture_window']}
                result['capture_contract']=reset.validate_capture_contract(contract,runner,raw,expected_abi=identity_abi(identity))
                actual=normalize_recipe_runner(result,project_tiers=True,capture=raw)
                expected=normalize_recipe_runner(baseline,project_tiers=True)
                require(actual==expected,'Final guest/source/device/PCM/WAV counters differ')
                require(all(runner[k]==result['final_status']['host'][k]for k in('native_steps','interpreter_steps')),'Final paused per-tier retirement counts')
                require(reset.sha256(out/'audio.wav')==baseline['raw_files']['audio.wav']['sha256'],'Exact capped prefix WAV bytes required')
                result['boot_validation']=api._boot_provenance(verified,runner);require(result['boot_validation']=={'valid':True},'Official reset provenance')
                require(result['natural_quit']and result['child_stopped']and result['exit_code']==0,'Natural owned closure required')
        except BaseException as error:
            result['passed']=False;result['closeout_error']=repr(error)
            if problem is None:problem=error
        result['raw_files']={name:reset.binding(out/name)for name in('run.stdout','run.stderr','states.jsonl','actions.jsonl','heartbeats.jsonl','audio.wav','observed-code.json')if(out/name).is_file()}
        (out/'receipt.json').open('x').write(json.dumps(result,indent=2)+'\n')
    if problem is not None:raise problem
    return result


def argument_parser():
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    for name in('descriptor','build-dir','tool-root','baseline-receipt','out'):parser.add_argument('--'+name,type=Path,required=True,action=reset.Once)
    parser.add_argument('--baseline-receipt-sha256',required=True,action=reset.Once)
    parser.add_argument('--expected-revision',action=reset.Once);parser.add_argument('--baseline-epochs',type=Path,action=reset.Once)
    parser.add_argument('--verify-only',action='store_true')
    return parser


if __name__=='__main__':
    args=argument_parser().parse_args()
    if args.verify_only:
        values=preflight(args);print(json.dumps({'verified':True,'no_host_started':True,'tool_identity':values[6],
            'package':values[17],'baseline_states':len(values[3]),'requests':len(values[4])}))
    else:
        result=run(args);print(json.dumps({'passed':result['passed'],'frames':result['final_status']['frame'],
            'native_steps':result['runner']['native_steps'],'interpreter_steps':result['runner']['interpreter_steps']}))
