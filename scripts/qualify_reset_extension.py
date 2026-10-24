"""Qualify measured native gains on one unchanged ABI17 reset extension.

Immediate extension input acknowledgments are typed transport observations,
validated within each run. Advancing/capture/terminal guest states stay exact.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,math,subprocess,sys,tomllib,wave
from pathlib import Path

if not __package__:
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import qualify_reset_native as old, replay_reset as replay
from scripts import merge_observations as merge,qualify_native_audio as tiers
from scripts.prepare_reset_descriptor import validate_reset_descriptor
from scripts.replay_route import validate_project_binding,validate_project_outputs
from scripts.package_checks import verify_package
from scripts.desktop_contract import validate_package_proof
from scripts.qualify_coverage import assert_exact as exact

TOOL=dict(old.TOOL)
ROOT=Path(__file__).resolve().parents[1]
PREFIX_FRAME=14680
PREFIX_NATIVE=432875213
ROLES={'prefix_qualification','prefix_receipt','prefix_profile','prefix_module','prefix_merge_manifest',
       'prefix_merge_receipt','root_prefix_receipt','input_witness','legacy_route',
       'merge_manifest','merge_receipt','expanded_profile','expanded_selection'}
PREFIX_SHA='0a4ab6650d513d8d7b4972a0daa1d07eca8ec476dba3abc9652848eb80bf6b42'
PROFILE_SHA='8aafe2b9b8311b2298a7285c0e97e7bd12de29d7f4bb5efbf9b3d4afe277c214'
KINDS=('ys3-reset-interactive-discovery','ys3-reset-extension-replay')


def require(value,label):
    if not value:raise ValueError(label)


def artifact(value,hashes):return old.artifact(value,hashes)


def baseline_link(value,actual_path,hashes):
    """The replay CLI records its original repository-relative spelling."""
    replay.keys(value,{'path','sha256'},'actual baseline link')
    require(type(value['path'])is str and value['path'],'recorded baseline path required')
    target=(ROOT/Path(value['path'])).resolve(strict=True)
    exact(Path(actual_path).resolve(strict=True),target,'actual baseline link target')
    old.file_hash(target,value['sha256'],hashes)
    return {'path':str(target),'sha256':value['sha256']}


def load_provenance(path,hashes):
    path=Path(path).resolve(strict=True);old.file_hash(path,replay.sha256(path),hashes)
    value=replay.strict_json(path)
    replay.keys(value,{'schema','kind','tool','prefix_frame','minimum_native_gain','files'},'extension provenance')
    exact(1,value['schema'],'provenance.schema');exact('ys3-reset-extension-provenance',value['kind'],'provenance.kind')
    exact(TOOL,value['tool'],'provenance.tool');exact(PREFIX_FRAME,value['prefix_frame'],'provenance.prefix')
    replay.integer(value['minimum_native_gain'],minimum=1,label='minimum native gain')
    replay.keys(value['files'],ROLES,'provenance roles')
    paths={name:artifact(row,hashes)for name,row in value['files'].items()}
    exact(PREFIX_SHA,value['files']['prefix_qualification']['sha256'],'frozen011.qualification')
    exact(PROFILE_SHA,value['files']['prefix_profile']['sha256'],'frozen011.profile')
    documents={name:replay.strict_json(target)for name,target in paths.items()if name not in('prefix_profile','expanded_profile')}
    q=documents['prefix_qualification'];require(q['passed']is True,'passed frozen011 qualification')
    exact(TOOL,q['tool'],'prefix.tool')
    exact(q['candidate_receipt'],value['files']['prefix_receipt'],'prefix.actual_receipt')
    exact(q['candidate_module']['manifest'],value['files']['prefix_module'],'prefix.actual_module')
    for name in ROLES-{'merge_manifest','merge_receipt','expanded_profile','expanded_selection','prefix_qualification'}:
        exact(q['evidence_sha256'][str(paths[name])],value['files'][name]['sha256'],'frozen011.role.'+name)
    return value,paths,documents


def source_key(row):return old.source_key(row)


def excluded(row):return any(1069880<=address<1069886 for address in row['physical'])


def measured_gain(baseline,candidate,prefix,old_profile,new_profile,minimum):
    replay.integer(minimum,minimum=1,label='positive minimum gain')
    tiers.compare_capture_observations(baseline,candidate)
    indexed=[{source_key(row):row for row in value['observations']}for value in(baseline,candidate)]
    inherited={source_key(row):row for row in prefix['observations']}
    old_keys={source_key(row)for row in old_profile['observations']if not excluded(row)}
    new_keys={source_key(row)for row in new_profile['observations']if not excluded(row)}
    require(old_keys<=new_keys and len(new_keys)>len(old_keys),'expanded eligible source identities required')
    fresh=new_keys-old_keys;gain=0;gained=[];suffix=[]
    exact(PREFIX_NATIVE,sum(row['native_hits']for row in prefix['observations']),'original prefix native histogram')
    exact(0,sum(row['interpreted_hits']for row in prefix['observations']),'original prefix interpreted histogram')
    for side,table in enumerate(indexed):
        native=interpreted=0
        for key,row in inherited.items():
            require(key in table and table[key]['native_hits']>=row['native_hits'],
                'full capture must retain original per-source prefix native hits')
        for key,row in table.items():
            before=inherited.get(key,{'native_hits':0,'interpreted_hits':0})
            native+=row['native_hits']-before['native_hits'];interpreted+=row['interpreted_hits']-before['interpreted_hits']
            require(row['native_hits']>=before['native_hits']and row['interpreted_hits']>=before['interpreted_hits'],
                'negative derived suffix tier hits')
            if row['native_hits']:require(key in(old_keys if side==0 else new_keys),'native source absent from emitted eligible profile')
            if excluded(row):exact(0,row['native_hits'],'whole six-byte source exclusion at execution')
        suffix.append({'native':native,'interpreted':interpreted,'total':native+interpreted})
    for key,left in indexed[0].items():
        right=indexed[1][key];delta=right['native_hits']-left['native_hits']
        require(delta>=0 and right['interpreted_hits']<=left['interpreted_hits'],'per-source native coverage regression')
        exact(delta,left['interpreted_hits']-right['interpreted_hits'],'per-source tier redistribution')
        if delta:
            require(key in fresh,'native gain must retire newly emitted eligible source identities')
            gained.append({'pc':left['pc'],'mpr':left['mpr'],'physical':left['physical'],'data':left['data'],'native_hits_gained':delta})
            gain+=delta
    exact(suffix[0]['total'],suffix[1]['total'],'suffix retirement conservation')
    exact(gain,suffix[1]['native']-suffix[0]['native'],'suffix-only native gain')
    exact(gain,suffix[0]['interpreted']-suffix[1]['interpreted'],'suffix interpreted reduction')
    require(gain>=minimum and gained,'positive executed new-source suffix gain required')
    return {'native_steps_gained':gain,'suffix_native_steps_gained':gain,'prefix_native_steps_gained':0,
        'old_suffix':suffix[0],'new_suffix':suffix[1],'new_eligible_identities':len(fresh),
        'newly_executed_native_identities':len(gained),'gained_sources':gained,
        'derived_suffix_histograms_are_raw_execution_captures':False}


def _extension_api():
    from scripts import replay_reset_extension
    return replay_reset_extension


def validate_timeline(receipt,observations,prefix):
    """Consume every phase row; the only cross-run mask view is explicitly typed."""
    helper=_extension_api();states=receipt['states'];actions=receipt['actions'];images=receipt['images']
    exact(states,[row['state']for row in observations],'raw flat state journal')
    if 'state_observations'in receipt:exact(observations,receipt['state_observations'],'inline phase observations')
    for row in observations:replay.keys(row,{'phase','state'},'state observation')
    for row in actions:replay.keys(row,{'phase','action','frame_before'},'phase action')
    expected_plan=replay.route_plan(prefix);plan=receipt['prefix_plan']
    expected_plan={**expected_plan,'actions':expected_plan['actions'][:-1],
        'deferred_terminal_action':{'source_index':114,'action':['quit']},'source_action_mapping':list(range(114)),'executed_prefix_actions':114}
    exact(expected_plan,plan,'literal114 prefix with deferred quit')
    ai=si=ii=0;views=[];diagnostics=[];settled_indices=[]
    def state(phase):
        nonlocal si
        require(si<len(observations),'missing raw state');row=observations[si]
        exact(phase,row['phase'],'state.phase');value=row['state']
        replay.normalize_status(value,desktop=True);si+=1
        return value
    def action(phase,words,before):
        nonlocal ai
        require(ai<len(actions),'missing actual control action')
        exact({'phase':phase,'action':words,'frame_before':before['frame']},actions[ai],'exact control timeline');ai+=1
    def image(phase,at):
        nonlocal ii
        require(ii<len(images),'missing actual guest image');value=images[ii]
        exact(phase,value['phase'],'image.phase');exact('guest',value['source'],'image.source')
        exact((at['frame'],at['ticks']),(value['frame'],value['ticks']),'paused image boundary');ii+=1
    latest=state('prefix');settled_indices.append(0)
    for words in plan['actions']:
        previous=latest;action('prefix',words,previous)
        if words[0]in('advance','input','status'):
            latest=state('prefix');settled_indices.append(si-1)
            exact(previous['frame']+(int(words[1])if words[0]=='advance'else 0),latest['frame'],'prefix action frame')
        elif words[0]=='capture':image('prefix',latest)
        else:raise ValueError('unexpected prefix action')
    exact((105,114,10),(si,ai,ii),'all retained prefix observations')
    exact(PREFIX_FRAME,latest['frame'],'prefix frame')
    boundary=receipt['prefix_boundary']
    for field,value in (('frames',PREFIX_FRAME),('state_index',104),('states',105),('actions_executed',114),
        ('deferred_source_quit_index',114),('source_action_mapping',list(range(114))),('native_steps',PREFIX_NATIVE),('interpreter_steps',0)):
        exact(value,boundary[field],'prefix_boundary.'+field)
    exact(latest,boundary['status'],'actual prefix status')
    action('boundary',['status'],latest);fresh=state('boundary')
    exact(replay.normalize_status(latest,desktop=True),replay.normalize_status(fresh,desktop=True),'fresh prefix boundary frozen')
    exact(fresh,boundary['fresh_status'],'actual fresh prefix status');latest=fresh;settled_indices.append(si-1);image('boundary',latest)
    finished=False
    for index,request in enumerate(receipt['requests'],1):
        replay.keys(request,{'binding','value'},'bound control request');value=request['value']
        op=value['op'];exact(index,value['id'],'sequential request IDs')
        replay.keys(value,{'id','op','mask','frames'}if op=='advance'else{'id','op'},'control request')
        require(not finished and op in('advance','capture','finish'),'ordinary controls until one finish')
        if op=='finish':
            action('terminal-proof',['status'],latest);final=state('terminal-proof')
            exact(replay.normalize_status(latest,desktop=True),replay.normalize_status(final,desktop=True),'terminal guest frozen')
            latest=final;settled_indices.append(si-1);action('terminal',['quit'],latest);finished=True;continue
        if op=='advance':
            replay.integer(value['mask'],255,label='joypad mask');replay.integer(value['frames'],600,1,'advance frames')
            previous=latest;action('extension',['input',str(value['mask'])],previous)
            action('extension-input-status',['status'],previous);immediate=state('extension-input-status')
            proof=helper.validate_input_status(previous,immediate,value['mask'])
            diagnostics.append({'state_index':si-1,'request_id':index,'proof':proof})
            action('extension',['advance',str(value['frames'])],immediate);latest=state('extension')
            helper.validate_advance(previous,latest,value['mask'],value['frames'])
        else:
            action('extension-capture-status',['status'],latest);actual=state('extension-capture-status')
            exact(replay.normalize_status(latest,desktop=True),replay.normalize_status(actual,desktop=True),'capture request guest frozen');latest=actual
        settled_indices.append(si-1);action('extension',['capture'],latest);image('extension',latest)
    require(finished,'explicit final request required');exact((len(states),len(actions),len(images)),(si,ai,ii),'no unclassified raw observation')
    exact(receipt['final_status'],latest,'actual terminal status')
    require(PREFIX_FRAME<latest['frame']<=30000 and len(receipt['requests'])<=512,'bounded actual extended route')
    typed={row['state_index']:row for row in diagnostics}
    for index,row in enumerate(observations):
        view=replay.normalize_status(row['state'],desktop=True,project_tiers=True)
        if index in typed:
            # Only after the full static same-run validator accepts prior/requested.
            view['host']['buttons']=[receipt['requests'][typed[index]['request_id']-1]['value']['mask'],0,0,0,0]
        views.append({'phase':row['phase'],'state':view})
    if receipt['kind']==KINDS[1]or 'extension_input_diagnostics'in receipt:
        exact([{'state_index':row['state_index'],**row['proof']}for row in diagnostics],
            receipt['extension_input_diagnostics'],'retained exact input transport proofs')
    return {'views':views,'input_diagnostics':diagnostics,'settled_state_indices':settled_indices,'frames':latest['frame']}


def image_views(images,hashes):
    result=[]
    for image in images:
        require('phase'in image,'explicit image phase required')
        body={key:value for key,value in image.items()if key!='phase'}
        result.append({'phase':image['phase'],**old.bind_images([body],hashes)[0]})
    return result


def bind_receipt(path,kind,hashes):
    """One real two-kind reader; no source receipt conversion or tool override."""
    path=Path(path).resolve(strict=True);old.file_hash(path,replay.sha256(path),hashes);value=replay.strict_json(path)
    exact(1,value['schema'],'receipt.schema');exact(kind,value['kind'],'actual receipt kind')
    for field,wanted in (('passed',True),('error',None),('memory_edits',0),('natural_quit',True),('child_stopped',True),
        ('exit_code',0),('cwd_initially_empty',True),('cwd_finally_empty',True)):
        exact(wanted,value[field],'receipt.'+field)
    require(value.get('closeout_error')is None,'successful actual closeout')
    old.identity(value['tool_identity_before']);exact(value['tool_identity_before'],value['tool_identity_after'],'same tool after')
    descriptor=artifact(value['project_descriptor'],hashes);config=tomllib.loads(descriptor.read_text(encoding='utf-8'))
    info=validate_reset_descriptor(config,descriptor);tool=Path(info['tool']['path']).resolve(strict=True)
    for field in('revision','source_sha256','runtime_abi'):exact(TOOL[field],info['tool'][field],'exact old coverage pin')
    exact(old.live_tool(tool),value['tool_identity_before'],'actual clean tool')
    project,_,_=replay.load_shared(tool);verified=project.verify(descriptor)
    exact(project._binding(verified),value['project_verification_before'],'actual official before')
    exact(value['project_verification_before'],value['project_verification_after'],'actual official after')
    built_path=artifact(value['project_build_receipt'],hashes);built=replay.strict_json(built_path)
    validate_project_binding(built,{'schema':1,'verified':True,**value['project_verification_before']})
    binary=Path(built['binary']).resolve(strict=True);validate_project_outputs(built,binary)
    proof={'package_before':value['package_before'],'environment':value['environment'],
        'loaded_sdl_before':value['loaded_sdl_before'],'loaded_sdl_final':value['loaded_sdl_final']}
    validate_package_proof(proof,built['binary_sha256']);exact(verify_package(built,binary),value['package_before'],'actual adjacent package')
    exact(value['package_before'],value['package_after'],'package after')
    for name,digest in built['output_files'].items():old.file_hash(binary.parent/name,digest,hashes)
    for role,target in info['files'].items():old.file_hash(target,info['identities'][role],hashes)
    exact(info['identities'],value['asset_hashes_before'],'actual asset before');exact(info['identities'],value['asset_hashes_after'],'actual asset after')
    exact(replay.reset_command(project,verified,binary,path.parent),value['command'],'actual official argv')
    cwd=Path(value['cwd']).resolve(strict=True);require(cwd==path.parent/'cwd'and not any(cwd.iterdir()),'retained isolated empty cwd')
    exact(value['protected_inputs_before'],value['protected_inputs_after'],'seven originals after')
    for row in replay.protected_inputs({'protected_inputs':value['protected_inputs_before']}):old.file_hash(row['path'],row['sha256'],hashes)
    names={'run.stdout','run.stderr','states.jsonl','actions.jsonl','heartbeats.jsonl','audio.wav','observed-code.json'}
    replay.keys(value['raw_files'],names,'actual raw files')
    raw={name:artifact(row,hashes)for name,row in value['raw_files'].items()}
    for name,target in raw.items():exact(path.parent/name,target,'raw actual path')
    journal=lambda name:[merge.strict_json(line)for line in raw[name].read_text(encoding='utf-8').splitlines()]
    observations=journal('states.jsonl');exact(value['states'],[row['state']for row in observations],'all raw states')
    exact(value['actions'],journal('actions.jsonl'),'all raw actions')
    run=replay.strict_json(raw['run.stdout']);exact(run,value['runner'],'raw runner')
    capture,report=old.load_capture(tool,raw['observed-code.json'],run,65536,hashes)
    contract=value['capture_contract'];replay.validate_capture_contract(contract,run,capture)
    exact(str(raw['observed-code.json']),contract['path'],'actual capture path');exact(replay.sha256(raw['observed-code.json']),contract['sha256'],'actual capture SHA')
    exact(raw['observed-code.json'].stat().st_size,contract['bytes'],'actual capture bytes');exact(value['start_proof'],contract['start_proof'],'actual reset proof')
    replay.validate_initial_status(value['states'][0],info['boot'])
    for field in('status_before','status'):exact(replay.normalize_status(value['states'][0],desktop=True),replay.normalize_status(value['start_proof'][field],desktop=True),'fresh reset0 source')
    bios=Path(info['files']['bios']).read_bytes()
    for row in value['start_proof']['fetch_readback']:require(0<=row['address']<len(bios)and bios[row['address']]==row['observed'],'authentic BIOS fetch')
    normalized=replay.normalize_runner(run,desktop=True,project_tiers=True,capture_contract=contract)
    exact({'valid':True},value['boot_validation'],'recorded reset provenance');exact({'valid':True},project._boot_provenance(verified,run),'actual reset provenance')
    old.validate_wav(raw['audio.wav'],normalized['audio_output'],hashes)
    for state in value['states']:replay.normalize_status(state,desktop=True)
    final=value['final_status'];exact(final,value['states'][-1],'raw terminal status')
    for key in('native_steps','interpreter_steps'):exact(run[key],final['host'][key],'runner terminal tier')
    exact(run['ticks'],final['ticks'],'runner terminal clock');exact(run['raster']['frames'],final['frame'],'runner terminal frame')
    exact(normalized['audio_output'],dict(replay.normalize_status(final,desktop=True)['host']['audio_output'],wav_frames=old.WAV_LIMIT,wav_truncated=True),'runner terminal PCM')
    exact(value['frozen_before'],value['frozen_after'],'actual executed helper/source epoch')
    for guard in('readiness','helper'):artifact(value['frozen_before'][guard],hashes)
    for row in value['frozen_before']['frozen_files']:artifact(row,hashes)
    readiness=replay.strict_json(value['frozen_before']['readiness']['path']);require(readiness['ready']is True,'closed executed readiness')
    exact(readiness['helper'],value['frozen_before']['helper'],'executed source binding')
    exact(readiness['frozen_files'],value['frozen_before']['frozen_files'],'exact executed dependency list')
    if kind==KINDS[1]:
        exact(value['helper_bindings_before'],value['helper_bindings_after'],'actual helper dependencies after')
        exact(value['frozen_before']['frozen_files'],value['helper_bindings_before'],'actual prelaunch helper dependencies')
    for index,row in enumerate(value['requests'],1):
        request_path=artifact(row['binding'],hashes);exact(replay.strict_json(request_path,4096),row['value'],'original control request bytes')
        if kind==KINDS[0]:exact(path.parent/'requests'/f'{index:06}.json',request_path,'original sequential request source')
    return {'path':path,'receipt':value,'config':config,'info':info,'tool':tool,'capture':capture,'capture_report':report,
        'runner':run,'normalized_runner':normalized,'observations':observations,'heartbeats':journal('heartbeats.jsonl')}


def validate_heartbeats(bundle,timeline):
    value=bundle['receipt'];rows=bundle['heartbeats']
    exact(len(rows),value.get('idle_heartbeat_count',0),'raw heartbeat count')
    settled={json.dumps(replay.normalize_status(value['states'][index],desktop=True),sort_keys=True)
             for index in timeline['settled_state_indices']}
    previous=-1
    for row in rows:
        replay.keys(row,{'phase','monotonic','status'},'raw lease observation')
        exact('idle-status-heartbeat',row['phase'],'lease observation phase')
        now=row['monotonic'];require(type(now)in(int,float)and math.isfinite(now)and now>=previous,'monotonic heartbeat timestamp');previous=now
        require(json.dumps(replay.normalize_status(row['status'],desktop=True),sort_keys=True)in settled,
            'heartbeat must equal a settled same-run guest/source/PCM/tier state')
    return {'count':len(rows),'raw_retained':True,'all_equal_settled_same_run_states':True,
        'cross_run_heartbeat_count_equality_claim':False}


def prefix_comparison(receipt,root,selected,witness,reference_sha,timeline):
    helper=_extension_api();checker=helper.PrefixCheck(root,selected,witness,reference_sha)
    view=checker.state(receipt['states'][0],-1,None)
    timeline['views'][0]['state']=replay.normalize_status(view,desktop=True,project_tiers=True)
    index=0
    for action_index,words in enumerate(receipt['prefix_plan']['actions']):
        if words[0]in('advance','input','status'):
            index+=1;view=checker.state(receipt['states'][index],action_index,words)
            timeline['views'][index]['state']=replay.normalize_status(view,desktop=True,project_tiers=True)
    result=checker.finish();boundary=receipt['prefix_boundary']
    for field,value in result.items():
        exact(value,boundary.get(field,[])if field=='selected_input_status_annotations'else boundary[field],
            'actual prefix proof.'+field)
    return {'original_reference':result['input_status_annotations'],'selected_native_prefix':result['selected_input_status_annotations']}


def composition(paths,documents,baseline,hashes):
    tool=baseline['tool'];api=merge.load_capture_api(tool)
    manifest,entries,bindings=merge.read_manifest(paths['merge_manifest'])
    exact(17,manifest['output_runtime_abi'],'profile format17');exact(2,len(entries),'exact retained profile plus actual baseline')
    exact(paths['prefix_profile'],entries[0][0],'original17 profile path')
    exact({'start_frame':0,'end_frame':95686},entries[0][1]['window'],'retained multi-route aggregate envelope')
    exact(Path(baseline['receipt']['capture_contract']['path']).resolve(),entries[1][0],'actual baseline capture path')
    exact({'start_frame':0,'end_frame':baseline['receipt']['final_status']['frame']},entries[1][1]['window'],'actual new reset window')
    expected_baseline={'path':str(baseline['path']),'sha256':replay.sha256(baseline['path'])}
    require(expected_baseline in entries[1][1]['evidence'],'actual baseline receipt must bind new epoch')
    expected_prior={'path':str(paths['prefix_qualification']),'sha256':PREFIX_SHA}
    require(expected_prior in entries[0][1]['evidence'],'retained qualified profile provenance required')
    for path,digest in bindings.items():old.file_hash(path,digest,hashes)
    inputs=[]
    for path,_ in entries:
        capture,digest=api.load_capture(path);old.file_hash(path,digest,hashes);exact(17,capture['runtime_abi'],'original input ABI17 retained');inputs.append(capture)
    exact(baseline['capture'],inputs[1],'original baseline source and tier hits')
    rebuilt,summary=merge.merge_captures(inputs,17,api.validate_capture)
    profile,digest=api.load_capture(paths['expanded_profile']);old.file_hash(paths['expanded_profile'],digest,hashes)
    exact(rebuilt,profile,'complete17+17 union without source/hit rewriting')
    receipt=documents['merge_receipt'];old.identity(receipt['tool_identity'])
    expected={'schema':1,'kind':'ys3-multi-run-observation-profile','tool_identity':receipt['tool_identity'],
        'tool_identity_after':receipt['tool_identity'],'output_capture_runtime_abi':17,'capture_sha256':digest,
        'capture_bytes':paths['expanded_profile'].stat().st_size,'input_manifest':str(paths['merge_manifest']),
        'input_manifest_sha256':replay.sha256(paths['merge_manifest']),
        'inputs':[dict(path=str(path),sha256=replay.sha256(path),epoch=epoch,**summary['input_epochs'][index])for index,(path,epoch)in enumerate(entries)],
        'evidence_sha256':{str(path):digest for path,digest in bindings.items()},
        'profile_format_semantics':'Output ABI names the composed observation format, not a single execution. Original input runtime ABI and hit tiers remain unchanged in each bound epoch.',
        'provenance_semantics':'Epoch labels/windows are caller declarations retained verbatim and bound to evidence bytes; this composition does not independently verify their execution meaning.',
        **{key:value for key,value in summary.items()if key!='input_epochs'}}
    exact(expected,receipt,'complete actual merge receipt')
    old.prefix_subset(inputs[0],profile)
    original_excluded=[row for row in inputs[0]['observations']if excluded(row)]
    exact(4,len(original_excluded),'retained four excluded identities')
    exact(981,sum(row['native_hits']+row['interpreted_hits']for row in original_excluded),'retained981 excluded original profile hits')
    return inputs[0],profile,{'input_runtime_abis':[17,17],'profile_format_abi':17,'actual_composition_recomputed':True,
        'single_execution_evidence':False,'retained_profile_multi_route_envelope':[0,95686],
        'actual_new_epoch':[0,baseline['receipt']['final_status']['frame']],
        'new_source_identities':summary['new_identities_over_first_capture']}


def qualify_reset_extension(baseline_receipt,candidate_receipt,*,provenance):
    hashes={}
    for module in(sys.modules[__name__],old,replay,merge):old.file_hash(module.__file__,replay.sha256(module.__file__),hashes)
    declaration,paths,documents=load_provenance(provenance,hashes)
    prefix_bundle=old.bind_receipt(paths['prefix_receipt'],hashes)
    selected=prefix_bundle[0];root=documents['root_prefix_receipt'];witness=old.bind_input_bridge(selected,paths['root_prefix_receipt'],hashes)
    exact(documents['input_witness'],witness,'retained exact input witness')
    baseline=bind_receipt(baseline_receipt,KINDS[0],hashes);candidate=bind_receipt(candidate_receipt,KINDS[1],hashes)
    exact({'path':str(baseline['path']),'sha256':replay.sha256(baseline['path'])},
        baseline_link(candidate['receipt']['baseline_receipt'],baseline['path'],hashes),'candidate executed exact baseline recipe')
    old.compare_recipes(baseline['config'],candidate['config'],left_descriptor=baseline['receipt']['project_descriptor']['path'],
        right_descriptor=candidate['receipt']['project_descriptor']['path'],left_tool=baseline['tool'],right_tool=candidate['tool'])
    exact(selected['project_descriptor'],baseline['receipt']['project_descriptor']['path'],'actual original package descriptor')
    exact(selected['project_descriptor_sha256'],baseline['receipt']['project_descriptor']['sha256'],'original descriptor bytes')
    exact(selected['project_build_receipt'],baseline['receipt']['project_build_receipt'],'actual original build receipt')
    exact(selected['desktop_contract']['package_before'],baseline['receipt']['package_before'],'actual qualified old package')
    actual_min=declaration['minimum_native_gain'];timelines=[];beats=[];input_annotations={}
    for label,bundle in(('old',baseline),('new',candidate)):
        receipt=bundle['receipt']
        exact({'path':str(paths['prefix_receipt']),'sha256':replay.sha256(paths['prefix_receipt'])},receipt['selected_prefix'],label+'.selected prefix')
        exact(selected['reference'],receipt['reference'],label+'.original root reference')
        exact(selected['protected_inputs_before'],receipt['protected_inputs_before'],label+'.same seven originals')
        typed=validate_timeline(receipt,bundle['observations'],root);timelines.append(typed);beats.append(validate_heartbeats(bundle,typed))
        input_annotations[label]=prefix_comparison(receipt,root,selected,witness,replay.sha256(paths['root_prefix_receipt']),typed)
        original_images=[{'phase':'prefix',**image}for image in old.bind_images(selected['images'],hashes)]
        exact(original_images,image_views(receipt['images'][:10],hashes),label+'.original ten images')
        for field in('native_steps','interpreter_steps'):
            values=[row['host'][field]for row in receipt['states']]
            require(all(a<=b for a,b in zip(values,values[1:])),label+'.monotonic retired tier')
    exact(baseline['receipt']['actions'],candidate['receipt']['actions'],'same actual action phases')
    exact(baseline['receipt']['requests'],candidate['receipt']['requests'],'same original requested controls')
    exact(timelines[0]['views'],timelines[1]['views'],'all settled guest/source/CD/PCM and validated input transport views')
    exact(image_views(baseline['receipt']['images'],hashes),image_views(candidate['receipt']['images'],hashes),'all decoded guest PNG identities')
    counts=[]
    for bundle in(baseline,candidate):
        _,count=tiers.tiers(bundle['runner'],'actual runner',blocks_required=True);counts.append(count)
    for field in('total','blocks'):exact(counts[0][field],counts[1][field],'conserved runner.'+field)
    for left,right in zip(baseline['receipt']['states'],candidate['receipt']['states']):
        exact(left['host']['native_steps']+left['host']['interpreter_steps'],right['host']['native_steps']+right['host']['interpreter_steps'],'every raw status retirement total')
    exact(baseline['normalized_runner'],candidate['normalized_runner'],'all final guest/source/CD/PCM except measured tiers')
    exact(replay.sha256(baseline['receipt']['raw_files']['audio.wav']['path']),
        replay.sha256(candidate['receipt']['raw_files']['audio.wav']['path']),'actual settled bounded WAV bytes')
    original,profile,merged=composition(paths,documents,baseline,hashes)
    emission=old.verify_candidate_emission(profile,paths['expanded_profile'],candidate['info'],candidate['tool'],documents['legacy_route'],hashes)
    old.validate_selection(documents['expanded_selection'],profile,paths['expanded_profile'],candidate['info'],documents['legacy_route'],paths['legacy_route'],candidate['tool'])
    gain=measured_gain(baseline['capture'],candidate['capture'],prefix_bundle[4],original,profile,actual_min)
    for bundle in(baseline,candidate):exact(old.live_tool(bundle['tool']),bundle['receipt']['tool_identity_before'],'tool closeout')
    for path,digest in hashes.items():require(replay.sha256(path)==digest,'extension evidence changed: '+path)
    return {'schema':1,'kind':'ys3-reset-native-extension-qualification','passed':True,'tool':TOOL,'selection':old.SELECTION,
        'frames':timelines[0]['frames'],'prefix_frame':PREFIX_FRAME,'prefix_states':105,'prefix_images':10,
        'prefix_source_actions':115,'prefix_executed_actions':114,'old_terminal_quit_explicitly_deferred':True,
        'states':len(baseline['receipt']['states']),'images':len(baseline['receipt']['images']),
        'requests':len(baseline['receipt']['requests']),'minimum_native_gain':actual_min,'old_runner':counts[0],'new_runner':counts[1],
        **gain,'composition':merged,'emission':emission,'managed_capture':{'runtime_abi':17,'old':baseline['capture_report'],'new':candidate['capture_report']},
        'input_status_latency':input_annotations,'extension_input_transport':{'old':timelines[0]['input_diagnostics'],'new':timelines[1]['input_diagnostics'],
            'raw_snapshots_retained':True,'all_raw_input_snapshots_identical_claim':False,'all_other_fields_static_within_run':True},
        'heartbeats':beats,'memory_edits':0,'baseline_receipt':{'path':str(baseline['path']),'sha256':replay.sha256(baseline['path'])},
        'candidate_receipt':{'path':str(candidate['path']),'sha256':replay.sha256(candidate['path'])},
        'candidate_module':{'manifest':{'path':candidate['info']['files']['module_manifest'],'sha256':candidate['info']['identities']['module_manifest']},
            'source':{'path':candidate['info']['files']['module_source'],'sha256':candidate['info']['identities']['module_source']},
            'artifacts':{path:candidate['info']['identities'][role]for role,path in candidate['info']['files'].items()if role.startswith(('module_unit:','module_header:'))}},
        'evidence_sha256':hashes,'scope':'Same old-pin ordinary reset/town extension, actual native gains only after14680. No new assists. Immediate extension input statuses are separately validated intent-transport snapshots; every other guest/source/IRQ/generation/CD/clock/PCM field is retained and all settled controls/states are strict. Profile union remains multi-run; all original source variants and whole six-byte exclusions retained. gear-good, volatile BRAM, unfinished campaign, no independent suffix/hardware/listening claim. Toolkit/media migration is separate.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in('baseline-receipt','candidate-receipt','provenance','out'):parser.add_argument('--'+name,type=Path,required=True,action=replay.Once)
    args=parser.parse_args();require(not args.out.exists(),'fresh qualification output required')
    result={'passed':False};failure=None
    try:result=qualify_reset_extension(args.baseline_receipt,args.candidate_receipt,provenance=args.provenance)
    except(OSError,ValueError,RuntimeError,KeyError,IndexError,TypeError,wave.Error,subprocess.SubprocessError)as error:result['error']=repr(error);failure=error
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x',encoding='utf-8')as stream:stream.write(json.dumps(result,indent=2)+'\n')
    if failure:raise failure
    print('PASS: measured same-pin reset extension native gain; '+str(args.out))


if __name__=='__main__':main()
