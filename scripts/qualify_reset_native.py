"""Qualify actual native System Card reset boot, with finite source evidence.

Native BIOS work before the menu is measured by a separate reset0 prefix
capture, not inferred from emission counts or an authored native example.
"""
from __future__ import annotations

import argparse
import copy
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import wave

if __package__:
    from . import qualify_native_audio as prior
    from . import qualify_dsp as shared
    from . import merge_observations as merge
    from .qualify_coverage import assert_exact, read_json
    from .replay_route import sha256, validate_project_binding, validate_project_outputs
    from .desktop_contract import validate_package_proof
    from .package_checks import verify_package
    from .expand_native import excluded_spans, audit_assist_source
else:
    import qualify_native_audio as prior
    import qualify_dsp as shared
    import merge_observations as merge
    from qualify_coverage import assert_exact, read_json
    from replay_route import sha256, validate_project_binding, validate_project_outputs
    from desktop_contract import validate_package_proof
    from package_checks import verify_package
    from expand_native import excluded_spans, audit_assist_source

TOOL = {'revision':'bb3b695b782352bdfacd8db877f2a843bd1242f1',
        'source_sha256':'5d3551481d1245d8cec9011d0f390ad0b464720c2d1f37a0fce601d0888e7a0d',
        'runtime_abi':17,'source_files':54}
REFERENCE_TOOL = {'revision':'df110529bd79cded48d9607653c8b6218bce4b3b',
                  'source_sha256':'c3dd7c6de6bba4abdb92eb3f90c1c5dbecf387790a15db654b597eda0225f1d7',
                  'runtime_abi':17,'source_files':54}
SELECTION = {'profile':'raw','sample_rate':44100,'timing':'gear'}
FRAMES, STATES, ACTIONS, IMAGES, MENU_FRAME = 14680,105,115,10,600
WAV_LIMIT = 441000
BIOS_BYTES = 0x40000
SELECTION_SCOPES = (
    'Complete observed profile emitted through upstream API with entire verified-restored temporary-code spans excluded. Original capture identity, completeness and hit totals are preserved. Unknown/unvisited code and excluded source remain hybrid.',
    'Upstream17 emission from retained16composed profile plusactualzeroassist17reset capture, originalepochs retained. Inheritedentire6byte physicalsource span excluded acrossallvariants. Emission alone does not prove execution.')


def file_hash(path, digest, hashes):
    path = Path(path).resolve(strict=True)
    if str(path) in hashes and hashes[str(path)] != digest:
        raise ValueError('conflicting evidence epochs require an explicit preserved path: ' + str(path))
    return prior.file_hash(path,digest,hashes)


def identity(value):
    shared.identity({'tool_identity':value,'tool_identity_after':value},TOOL,'reset.tool')
    assert_exact(TOOL['source_files'],value['shared_source_identity']['source_files'],'reset.source_files')


def live_tool(root):
    completed=subprocess.run([sys.executable,str(Path(__file__).with_name('verify_tool.py')),'--tool-root',str(root),
        '--expected-revision',TOOL['revision'],'--expected-abi','17','--expected-source-sha256',TOOL['source_sha256']],
        check=True,capture_output=True,text=True,timeout=60)
    value=json.loads(completed.stdout);identity(value)
    return value


def load_capture(tool,path,run,capacity,hashes):
    api=merge.load_capture_api(tool)
    capture,digest=api.load_capture(Path(path))
    file_hash(path,digest,hashes)
    assert_exact(17,capture['runtime_abi'],'reset.capture.actual_abi')
    assert_exact(1,capture['schema'],'reset.capture.schema')
    if type(capacity) is not int or not 1<=capacity<=65536:
        raise ValueError('bounded explicit capture capacity required')
    assert_exact(capacity,capture['capacity'],'reset.capture.capacity')
    assert_exact(True,capture['complete'],'reset.capture.complete')
    for field in ('dropped_instructions','unreadable_instructions'):
        assert_exact(0,capture[field],'reset.capture.'+field)
    _,counts=prior.tiers(run,'reset.capture.runner',blocks_required=True)
    native=sum(item['native_hits'] for item in capture['observations'])
    interpreted=sum(item['interpreted_hits'] for item in capture['observations'])
    for label,expected,actual in (('native',counts['native'],native),('interpreted',counts['interpreted'],interpreted),
                                 ('total',counts['total'],capture['retired_instructions'])):
        assert_exact(expected,actual,'reset.capture.'+label)
    assert_exact(native+interpreted,capture['retired_instructions'],'reset.capture.exact_hit_conservation')
    return capture,{'path':str(Path(path).resolve()),'sha256':digest,'runtime_abi':17,'capacity':capacity,
                    'observations':len(capture['observations']),'native':native,'interpreted':interpreted,
                    'total':capture['retired_instructions'],'complete':True,'dropped_instructions':0,'unreadable_instructions':0}


def source_key(observation):
    return (observation['pc'],tuple(observation['mpr']),tuple(observation['physical']),tuple(observation['data']))


def bios_hits(capture,bios):
    if len(bios)!=BIOS_BYTES:
        raise ValueError('System Card BIOS must contain256KiB')
    native=interpreted=identities=0
    for item in capture['observations']:
        if all(0<=address<BIOS_BYTES for address in item['physical']):
            if any(bios[address]!=byte for address,byte in zip(item['physical'],item['data'])):
                raise ValueError('observed BIOS source bytes differ from immutable BIOS')
            native+=item['native_hits'];interpreted+=item['interpreted_hits'];identities+=1
    return {'native':native,'interpreted':interpreted,'total':native+interpreted,'identities':identities,
            'physical_range':{'start':0,'length':BIOS_BYTES}}


def prefix_subset(prefix,full):
    indexed={source_key(item):item for item in full['observations']}
    for item in prefix['observations']:
        retained=indexed.get(source_key(item))
        if retained is None or any(item[field]>retained[field] for field in ('native_hits','interpreted_hits')):
            raise ValueError('boot prefix source/tier hits are not retained in full-route capture')


def prove_native_bios(prefix,full,profile,bios):
    prefix_subset(prefix,full)
    compiled={source_key(item) for item in profile['observations']}
    for item in prefix['observations']:
        if item['native_hits'] and source_key(item) not in compiled:
            raise ValueError('boot native source identity absent from actual compiled profile')
    before=bios_hits(prefix,bios);overall=bios_hits(full,bios)
    if before['native']<=0 or overall['native']<before['native']:
        raise ValueError('actual native BIOS instructions must retire before the System Card menu')
    return {'before_menu_frame':MENU_FRAME,'before_menu':before,'full_route':overall,
            'prefix_source_and_tier_hits_retained_in_full_capture':True,
            'scope':'Native BIOS retirements measured in an actual reset0-to-menu capture using the identical candidate package; emission alone is not execution.'}

SEALED = {
    'final_tool_qualification':'9293a21194b7b5026d9f8a7bd2c48bad17fa04e0e283fe70833c46b5266badf7',
    'source_delta':'d1dcfdf2a0c8b0c0867c284c1fc25a0b73913ff2a8687a604e93e65e4bae0035',
    'reference_preservation':'c269770153e2bb2c12c243a3993530ebdf5276e6183c3aab17adf27b555f9f50',
    'authored_native_result':'ad3a6a2d988c09f86cc7ed1928131f6c7dd1eb3fdd284212f38524f87a7b7bb5',
    'authored_native_audit':'502d809ce2a771f9d5db734a57ac753608515e5baed9582d8b3da8e567566f81'}
PROVENANCE_ROLES = set(SEALED) | {'reference_launch','reference_run','reference_wav','candidate_profile',
    'candidate_selection','legacy_profile','legacy_route','merge_manifest','merge_receipt','boot_prefix_receipt',
    'viewport_diagnostic','menu_image_120','menu_image_600','input_contract'}
INPUT_CONTRACT_SHA256='dfec6ed211ab31408189daee641e60e2cc7c75ef194a38569d50e5086322827a'


def _api():
    if __package__:
        from . import replay_reset, prepare_reset_descriptor
    else:
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from scripts import replay_reset,prepare_reset_descriptor
    return replay_reset,prepare_reset_descriptor


def artifact(binding,hashes):
    shared.keys(binding,{'path','sha256'},'reset artifact')
    if type(binding['path']) is not str or not Path(binding['path']).is_absolute():
        raise ValueError('reset artifacts require exact absolute paths')
    return file_hash(binding['path'],binding['sha256'],hashes)


def load_provenance(path,hashes):
    path=Path(path).resolve(strict=True);file_hash(path,sha256(path),hashes)
    value=read_json(path)
    shared.keys(value,{'schema','kind','tool','files'},'reset provenance')
    assert_exact(1,value['schema'],'provenance.schema')
    assert_exact('ys3-reset-native-provenance',value['kind'],'provenance.kind')
    assert_exact(TOOL,value['tool'],'provenance.tool')
    shared.keys(value['files'],PROVENANCE_ROLES,'provenance.files')
    paths={role:artifact(binding,hashes) for role,binding in value['files'].items()}
    for role,digest in SEALED.items():
        assert_exact(digest,value['files'][role]['sha256'],'sealed.'+role)
    assert_exact(INPUT_CONTRACT_SHA256,value['files']['input_contract']['sha256'],'sealed.input_contract')
    for role,digest in (
        ('legacy_profile','c14be659964ba99614f173fb6a26a84c91571998d17ba7a7998618bb2b2596ed'),
        ('legacy_route','a200f5c29f9aac37cd6d7a7494e5bb305a51440e9dbd92fa57003e5ffa549cd5')):
        assert_exact(digest,value['files'][role]['sha256'],'frozen010.'+role)
    loaded={role:read_json(path) for role,path in paths.items() if role not in
            ('candidate_profile','legacy_profile','reference_wav','menu_image_120','menu_image_600')}
    return paths,loaded


def upstream_proofs(loaded,reference_path,paths,hashes):
    delta,preserved,audit=loaded['source_delta'],loaded['reference_preservation'],loaded['authored_native_audit']
    for role in SEALED:assert_exact('pass',loaded[role]['result'],'sealed.passed.'+role)
    for field,tool in (('old_source',REFERENCE_TOOL),('new_source',TOOL)):
        assert_exact({k:tool[k] for k in ('revision','source_sha256','source_files')},delta[field],'source_delta.'+field)
    assert_exact(['pcerecomp/project.py'],delta['changed_source_files'],'source_delta.changed_files')
    assert_exact(54,len(delta['files']),'source_delta.all54')
    names=set();changed=[]
    for entry in delta['files']:
        name=entry['relative_path']
        if name in names:raise ValueError('duplicate source delta path')
        names.add(name)
        old=file_hash(entry['old_path'],entry['old_sha256'],hashes)
        new=file_hash(entry['new_path'],entry['new_sha256'],hashes)
        assert_exact(entry['old_bytes'],old.stat().st_size,'source_delta.old_size')
        assert_exact(entry['new_bytes'],new.stat().st_size,'source_delta.new_size')
        equal=old.read_bytes()==new.read_bytes()
        assert_exact(equal,entry['bytes_equal'],'source_delta.actual_bytes')
        if not equal:changed.append(name)
    assert_exact(['pcerecomp/project.py'],changed,'source_delta.actual_changed_files')
    old_audit_path=artifact(delta['old_retail'],hashes)
    assert_exact(delta['old_retail'],{k:preserved['old_retail'][k] for k in ('path','sha256')},'old_retail.link')
    old_audit=read_json(old_audit_path)
    assert_exact('pass',old_audit['result'],'old_retail.passed')
    relocations={}
    for row in preserved['relocations']:
        assert_exact(row['expected_sha256'],row['preserved_sha256'],'preserved.old_source_digest')
        relocations[(row['original_path'],row['expected_sha256'])]=row['preserved_path']
    for row in loaded['authored_native_result']['source_epoch_mappings']:
        key=(row['original'],row['sha256'])
        if key in relocations and relocations[key]!=row['preserved']:
            raise ValueError('ambiguous historical source relocation')
        relocations[key]=row['preserved']
    def historical(path,digest):
        return file_hash(relocations.get((path,digest),path),digest,hashes)
    edge_map={};inherited=[]
    for row in preserved['edges']:
        key=row['original_path'];digest=row['expected_sha256']
        if key in edge_map:raise ValueError('duplicate old reference graph edge')
        edge_map[key]=digest
        if row['status']=='inherited-owner-input-not-rehashed':
            inherited.append({'path':key,'sha256':digest});continue
        if row['status'] not in ('current-path-exact','resolved-explicit-old-source-epoch'):
            raise ValueError('unreviewed reference preservation status')
        historical(key,digest)
    assert_exact(old_audit['evidence_sha256'],edge_map,'old_retail.exact139_graph')
    assert_exact(139,len(edge_map),'old_retail.edges')
    assert_exact(1,len(inherited),'old_retail.disclosed_inherited_input')
    for path in (reference_path,paths['reference_launch'],paths['reference_run'],paths['reference_wav']):
        file_hash(path,edge_map[str(path)],hashes)
    for field in ('bindings','extra_bindings'):
        for path,digest in audit[field].items():historical(path,digest)
    assert_exact(sha256(paths['authored_native_result']),audit['result_sha256'],'authored.result_link')
    assert_exact({k:TOOL[k] for k in ('revision','source_sha256','source_files')},audit['tool_identity'],'authored.tool')
    assert_exact(0,audit['interpreter_steps'],'authored.interpreter_scope')
    final=loaded['final_tool_qualification']
    assert_exact({k:TOOL[k] for k in ('revision','source_sha256','source_files')},final['production_source'],'sealed.final_source')
    assert_exact(17,final['runtime_abi'],'sealed.final_abi')
    assert_exact([],final['material_findings'],'sealed.findings')
    assert_exact([],final['owned_proof_processes_remaining'],'sealed.processes')
    for field,expected in (('suites',34),('python_tests',386),('python_skips',0),('exit_code',0)):
        assert_exact(expected,final['full_check'][field],'sealed.full_check.'+field)
    assert_exact(772,len(final['bindings']),'sealed.final_graph_count')
    for path,entry in final['bindings'].items():
        digest=entry['sha256'] if isinstance(entry,dict) else entry
        bound=historical(path,digest)
        if isinstance(entry,dict):assert_exact(entry['bytes'],bound.stat().st_size,'sealed.bound_size')
    input_contract=loaded['input_contract']
    assert_exact('pass-contract-diagnosis-only',input_contract['result'],'sealed.input_contract_diagnosis')
    assert_exact(False,input_contract['upstream_barrier_required_for_existing_contract'],'sealed.input_contract_scope')
    assert_exact(False,input_contract['actual_closed_failure']['route_qualified'],'failed_route_not_promoted')
    assert_exact(False,input_contract['actual_closed_failure']['next_advance_recorded'],'failed_route_next_advance_unobserved')
    assert_exact(9,len(input_contract['bindings']),'sealed.input_contract_bound_files')
    for target,digest in input_contract['bindings'].items():file_hash(target,digest,hashes)
    return {'root_source_delta_exact':True,'canonical_source_files':54,'changed_source_files':changed,
            'old_reference_direct_edges':139,'root_inherited_owner_inputs':inherited,
            'authored_native_steps':audit['native_steps'],'authored_interpreted_steps':0,
            'authored_scope':audit['scope'],'retail_hardware_or_mix_claim':False,
            'input_status_contract_diagnosis_bound':True,'failed_initial_route_not_qualified':True,
            'source_epoch_relocations':[{'original':key[0],'sha256':key[1],'preserved':value} for key,value in relocations.items()]}


def module_manifest(descriptor_info):
    """The descriptor API deliberately returns JSON-safe path strings."""
    return read_json(Path(descriptor_info['files']['module_manifest']))


def verify_candidate_emission(profile,profile_path,descriptor_info,tool,legacy_route,hashes):
    files=descriptor_info['files'];manifest_path=Path(files['module_manifest']);manifest=module_manifest(descriptor_info)
    assert_exact(17,manifest['capture_runtime_abi'],'candidate.capture_format_abi')
    assert_exact(17,manifest['runtime_abi'],'candidate.runtime_abi')
    assert_exact(['full_mpr_snapshot','exact_source_bytes_per_instruction','instruction_deadline'],manifest['guards'],'candidate.guards')
    spans=excluded_spans(legacy_route)
    assert_exact(((1069880,6),),spans,'inherited.whole_six_byte_source_exclusion')
    source_audit=audit_assist_source(profile,legacy_route,spans)
    api=merge.load_capture_api(tool);emitter=importlib.import_module(api.__package__+'.emitter')
    if Path(emitter.__file__).resolve()!=(Path(tool)/'pcerecomp/emitter.py').resolve(strict=True):
        raise ValueError('emitter origin differs from actual final pin')
    with tempfile.TemporaryDirectory(prefix='ys3-reset-native-') as temporary:
        output=Path(temporary)/'native'
        rebuilt=emitter.emit_capture(profile,output,sha256(profile_path),exclude_ranges=spans,
            partition_size=manifest['partition_size'],single_unit=not manifest['partitioned'])
        assert_exact(rebuilt,manifest,'candidate.actual_pinned_emitter_manifest')
        for field in ('translation_units','generated_headers'):
            for entry in manifest[field]:
                actual=manifest_path.parent/entry['file'];file_hash(actual,entry['sha256'],hashes)
                if actual.read_bytes()!=(output/entry['file']).read_bytes():
                    raise ValueError('candidate source differs from actual upstream guarded emission')
    assert_exact(0,manifest['unsupported_observations'],'candidate.unsupported_source')
    return {'identities':manifest['native_instructions_emitted'],'mpr_contexts':manifest['native_contexts'],
            'artifacts':len(manifest['translation_units'])+len(manifest['generated_headers']),
            'excluded_physical_ranges':manifest['excluded_physical_ranges'],
            'excluded_identities':manifest['excluded_observations'],'excluded_retired_hits':manifest['excluded_retired_hits'],
            'exact_upstream_emission_and_guards':True,'emission_is_execution_proof':False,
            'assist_source_audit':source_audit}


def compare_state(left,right,*,right_desktop=False):
    api,_=_api()
    a=api.normalize_status(left,desktop=True,project_tiers=True)
    b=api.normalize_status(right,desktop=right_desktop,project_tiers=True)
    assert_exact(a,b,'all_guest_source_device_cd_clock_pcm')
    counts=[]
    for value in (left,right):
        _,count=prior.tiers(value['host'],'status')
        counts.append(count)
    assert_exact(counts[0]['total'],counts[1]['total'],'status.retirement_conservation')
    return counts


def bind_input_bridge(receipt,reference_path,hashes):
    api,_=_api();selected=receipt['input_status_bridge'];witness=receipt['input_status_bridge_witness']
    if selected is None:
        assert_exact(None,witness,'absent_input_bridge_witness')
        assert_exact([],receipt['input_status_annotations'],'absent_input_bridge_annotations')
        return None
    path=artifact(selected,hashes);actual=api.strict_json(path)
    assert_exact(actual,witness,'actual_input_status_bridge_witness')
    api.validate_input_status_bridge(actual,sha256(reference_path))
    audit_path=artifact(actual['audit'],hashes)
    assert_exact('8b9470d98118a12208c42c54e22b35c7ac9684a8ac48b112cae0a1af36c15710',sha256(audit_path),'exact_original_input_snapshot_audit')
    audit=api.strict_json(audit_path)
    assert_exact('pass',audit['result'],'input_snapshot_original_audit_passed')
    assert_exact([{'action':58,'state':54,'frame':11660,'requested_mask':0,'observed_mask':1,'guest_time_advanced':False}],
        audit['deferred_button_status_snapshots'],'single_original_documented_input_snapshot')
    return actual


def comparison_views(receipt,reference,reference_sha256,bridge):
    """Only the one witnessed immediate release may have a comparison view.

    Raw states remain unchanged. The following advance must be present and
    strict, and the complete recomputed annotation must equal the raw receipt.
    """
    api,_=_api();views=copy.deepcopy(reference['states']);annotations=[]
    if bridge is not None and receipt['states'][54]['host']['buttons']!=reference['states'][54]['host']['buttons']:
        views[54],annotation=api.input_status_latency_bridge(reference['states'][54],receipt['states'][54],receipt['states'][53],
            reference_sha256=reference_sha256,state_index=54,action_index=58,action=receipt['actions'][58],
            next_reference_state=reference['states'][55],bridge=bridge)
        annotation=api.confirm_input_status_bridge(annotation,reference['states'][55],receipt['states'][55],
            state_index=55,action_index=59,action=receipt['actions'][59])
        annotations.append(annotation)
    assert_exact(annotations,receipt['input_status_annotations'],'actual_recomputed_input_status_annotations')
    return views,annotations


def canonical_recipe(config,descriptor_path,verified_tool):
    """Resolve only the actual verified tool path; retain every recipe value.

    Raw descriptor spelling stays bound and unchanged. Relative paths resolve
    from that descriptor's own directory, as the official verifier does.
    """
    root=(Path(descriptor_path).resolve(strict=True).parent/config['tool']['path']).resolve(strict=True)
    assert_exact(Path(verified_tool).resolve(strict=True),root,'recipe.actual_verified_tool_root')
    result={key:copy.deepcopy(value) for key,value in config.items() if key not in ('name','module')}
    result['tool']['path']=str(root)
    return result


def compare_recipes(left,right,*,left_descriptor,right_descriptor,left_tool,right_tool):
    assert_exact(Path(left_tool).resolve(strict=True),Path(right_tool).resolve(strict=True),'recipe.same_actual_verified_tool_root')
    assert_exact(canonical_recipe(left,left_descriptor,left_tool),canonical_recipe(right,right_descriptor,right_tool),
        'same_reset_recipe_except_module_name')


def bind_images(images,hashes):
    api,_=_api();result=[]
    for image in images:
        required={'path','width','height','frame','ticks','frame_ticks','source','rgb_sha256'}
        if set(image) not in (required,required|{'png_sha256','bytes'}):
            raise ValueError('image metadata has missing or unreviewed fields')
        path=Path(image['path']).resolve(strict=True);actual=api.png_identity(path)
        for field in ('width','height','rgb_sha256'):
            assert_exact(actual[field],image[field],'decoded_image.'+field)
        for field in ('png_sha256','bytes'):
            if field in image:assert_exact(actual[field],image[field],'decoded_image.'+field)
        file_hash(path,actual['png_sha256'],hashes)
        result.append({k:image[k] for k in ('width','height','frame','ticks','frame_ticks','source','rgb_sha256')})
    return result


def validate_wav(path,core,hashes):
    file_hash(path,sha256(path),hashes)
    with wave.open(str(path),'rb') as audio:
        assert_exact((2,2,44100,WAV_LIMIT,'NONE'),
            (audio.getnchannels(),audio.getsampwidth(),audio.getframerate(),audio.getnframes(),audio.getcomptype()),'bounded.raw_pcm_wav')
    assert_exact(WAV_LIMIT,core['wav_frames'],'wav.runner_frames')
    assert_exact(True,core['wav_truncated'],'wav.runner_truncated')


def bind_receipt(path,hashes):
    """Recheck recorded official bindings through the same pinned read-only API."""
    api,descriptor_api=_api();path=Path(path).resolve(strict=True)
    file_hash(path,sha256(path),hashes);receipt=api.strict_json(path)
    for field,expected in (('schema',1),('kind','ys3-reset-replay'),('passed',True),('error',None),
                           ('exit_code',0),('child_stopped',True),('natural_quit',True),('supervisor_failure',None),
                           ('shared_project_run_used',False),('execution_mode','shared-verify-command-consumer-tcp')):
        assert_exact(expected,receipt[field],'receipt.'+field)
    identity(receipt['tool_identity_before']);assert_exact(receipt['tool_identity_before'],receipt['tool_identity_after'],'receipt.tool_after')
    assert_exact(receipt['tool_identity_before'],receipt['tool_identity'],'receipt.tool_alias')
    descriptor=file_hash(receipt['project_descriptor'],receipt['project_descriptor_sha256'],hashes)
    config=tomllib.loads(descriptor.read_text(encoding='utf-8'))
    info=descriptor_api.validate_reset_descriptor(config,descriptor)
    for key in ('revision','source_sha256','runtime_abi'):assert_exact(TOOL[key],info['tool'][key],'descriptor.tool.'+key)
    tool=Path(info['tool']['path']).resolve(strict=True)
    verified_identity=live_tool(tool)
    assert_exact(verified_identity,receipt['tool_identity_before'],'actual_clean_tool_before_loading_shared_api')
    project,capture_api,_=api.load_shared(tool)
    verified=project.verify(descriptor)
    actual_verification={'schema':1,'verified':True,**project._binding(verified)}
    for field in ('project_verification_before','project_verification_after'):
        assert_exact(actual_verification,receipt[field],'actual_official.'+field)
    built_path=artifact(receipt['project_build_receipt'],hashes)
    assert_exact(built_path,Path(receipt['project_build']).resolve(strict=True)/'build-receipt.json','actual_build_path')
    assert_exact(sha256(built_path),receipt['project_build_receipt_sha256'],'build_hash_alias')
    built=api.strict_json(built_path);validate_project_binding(built,actual_verification)
    binary=Path(built['binary']).resolve(strict=True)
    validate_project_outputs(built,binary)
    assert_exact(True,built['desktop'],'official_desktop')
    proof=receipt['desktop_contract'];validate_package_proof(proof,built['binary_sha256'])
    for field in ('packaged','hidden','unthrottled','working_directory_initially_empty','working_directory_finally_empty'):
        assert_exact(True,proof[field],'package.'+field)
    actual_package=verify_package(built,binary)
    assert_exact(actual_package,proof['package_before'],'actual_adjacent_package')
    assert_exact(actual_package,proof['package_after'],'actual_adjacent_package_after')
    cwd=Path(proof['working_directory']).resolve(strict=True)
    if any(cwd.iterdir()):raise ValueError('retained isolated cwd must remain empty')
    for name,digest in built['output_files'].items():file_hash(binary.parent/name,digest,hashes)
    for role,target in info['files'].items():file_hash(target,info['identities'][role],hashes)
    assert_exact(info['identities'],receipt['asset_hashes_before'],'assets.before')
    assert_exact(info['identities'],receipt['asset_hashes_after'],'assets.after')
    assert_exact(info['boot'],receipt['initial_boot'],'authentic_vector_boot')
    command=api.reset_command(project,verified,binary,path.parent)
    assert_exact(command,receipt['command'],'actual_official_reset_argv')
    assert_exact(receipt['protected_inputs_before'],receipt['protected_inputs_after'],'protected_after')
    originals=api.protected_inputs({'protected_inputs':receipt['protected_inputs_before']})
    for entry in originals:file_hash(entry['path'],entry['sha256'],hashes)
    expected_raw={'stdout':'run.stdout','stderr':'run.stderr','wav':'audio.wav','states':'states.jsonl','actions':'actions.jsonl'}
    shared.keys(receipt['raw_files'],expected_raw,'raw_files')
    raw_paths={role:artifact(value,hashes) for role,value in receipt['raw_files'].items()}
    for role,name in expected_raw.items():assert_exact(path.parent/name,raw_paths[role],'raw_path.'+role)
    for role in ('states','actions'):
        values=[merge.strict_json(line) for line in raw_paths[role].read_text(encoding='utf-8').splitlines()]
        assert_exact(receipt[role],values,'raw_journal.'+role)
    runner=api.strict_json(raw_paths['stdout']);assert_exact(runner,receipt['runner'],'retained_raw_runner')
    prior.source_identity(runner,'runner')
    capture,report=load_capture(tool,receipt['capture_contract']['path'],runner,65536,hashes)
    api.validate_capture_contract(receipt['capture_contract'],runner,capture)
    assert_exact(receipt['start_proof'],receipt['capture_contract']['start_proof'],'raw_start_proof')
    for field in ('status_before','status'):
        assert_exact(api.normalize_status(receipt['states'][0],desktop=True),
            api.normalize_status(receipt['start_proof'][field],desktop=True),'first_actual_state_matches_fresh_capture_proof')
    bios=Path(info['files']['bios']).read_bytes()
    for row in receipt['start_proof']['fetch_readback']:
        if not 0<=row['address']<len(bios) or row['observed']!=bios[row['address']]:
            raise ValueError('fresh reset pure-fetch bytes differ from authentic bound BIOS')
    assert_exact(Path(receipt['capture_contract']['path']).resolve(),path.parent/'observed-code.json','actual_capture_path')
    assert_exact(receipt['capture_contract']['bytes'],Path(receipt['capture_contract']['path']).stat().st_size,'capture.bytes')
    assert_exact(sha256(receipt['capture_contract']['path']),receipt['capture_contract']['sha256'],'capture.hash')
    normalized=api.normalize_runner(runner,desktop=True,project_tiers=True,capture_contract=receipt['capture_contract'])
    assert_exact({'valid':True},receipt['boot_validation'],'shared_boot_validation')
    assert_exact({'valid':True},project._boot_provenance(verified,runner),'actual_shared_boot_validation')
    validate_wav(raw_paths['wav'],normalized['audio_output'],hashes)
    for state in receipt['states']:api.normalize_status(state,desktop=True)
    api.validate_initial_status(receipt['states'][0],info['boot'])
    for state in (receipt['final_status'],receipt['states'][-1]):
        compare_state(state,receipt['states'][-1],right_desktop=True)
        assert_exact(runner['ticks'],state['ticks'],'endpoint.clock')
        assert_exact(runner['native_steps'],state['host']['native_steps'],'endpoint.native')
        assert_exact(runner['interpreter_steps'],state['host']['interpreter_steps'],'endpoint.interpreted')
        assert_exact(normalized['audio_output'],dict(api.normalize_status(state,desktop=True)['host']['audio_output'],
            wav_frames=WAV_LIMIT,wav_truncated=True),'endpoint.pcm')
    return receipt,config,info,tool,capture,report,normalized


def composition(paths,loaded,tool,baseline,baseline_path,hashes):
    manifest,entries,bound=merge.read_manifest(paths['merge_manifest'])
    assert_exact(17,manifest['output_runtime_abi'],'composition.format')
    assert_exact(2,len(entries),'composition.two_original_epochs')
    assert_exact(paths['legacy_profile'],entries[0][0],'composition.retained_profile_path')
    assert_exact({'start_frame':0,'end_frame':95686},entries[0][1]['window'],'composition.original_route_extent')
    assert_exact({'start_frame':0,'end_frame':FRAMES},entries[1][1]['window'],'composition.actual_reset_extent')
    actual_binding={'path':str(baseline_path),'sha256':sha256(baseline_path)}
    if actual_binding not in entries[1][1]['evidence']:raise ValueError('composition must bind actual reset baseline receipt')
    for target,digest in bound.items():file_hash(target,digest,hashes)
    api=merge.load_capture_api(tool);captures=[]
    for target,_ in entries:
        value,digest=api.load_capture(target);file_hash(target,digest,hashes);captures.append(value)
    assert_exact(16,captures[0]['runtime_abi'],'composition.original16_not_relabelled')
    assert_exact(17,captures[1]['runtime_abi'],'composition.actual_reset17')
    assert_exact(baseline,captures[1],'composition.actual_raw_baseline_capture')
    rebuilt,summary=merge.merge_captures(captures,17,api.validate_capture)
    profile,digest=api.load_capture(paths['candidate_profile']);file_hash(paths['candidate_profile'],digest,hashes)
    assert_exact(rebuilt,profile,'composition.exact_all_source_identities_and_tier_hits')
    receipt=loaded['merge_receipt'];identity(receipt['tool_identity'])
    expected={'schema':1,'kind':'ys3-multi-run-observation-profile','tool_identity':receipt['tool_identity'],
        'tool_identity_after':receipt['tool_identity'],'output_capture_runtime_abi':17,
        'capture_sha256':digest,'capture_bytes':paths['candidate_profile'].stat().st_size,
        'input_manifest':str(paths['merge_manifest']),'input_manifest_sha256':sha256(paths['merge_manifest']),
        'inputs':[dict(path=str(target),sha256=sha256(target),epoch=epoch,**summary['input_epochs'][index]) for index,(target,epoch) in enumerate(entries)],
        'evidence_sha256':{str(target):digest for target,digest in bound.items()},
        'profile_format_semantics':'Output ABI names the composed observation format, not a single execution. Original input runtime ABI and hit tiers remain unchanged in each bound epoch.',
        'provenance_semantics':'Epoch labels/windows are caller declarations retained verbatim and bound to evidence bytes; this composition does not independently verify their execution meaning.',
        **{key:value for key,value in summary.items() if key!='input_epochs'}}
    assert_exact(expected,receipt,'composition.complete_receipt')
    return profile,{'exact_composition_recomputed':True,'input_runtime_abis':[16,17],'composed_format_abi':17,
        'single_execution_evidence':False,'new_source_identities':summary['new_identities_over_first_capture']}


def validate_prefix_image_reference(value,receipt_path,image_paths,hashes):
    def bound(path):
        path=Path(path).resolve(strict=True);digest=sha256(path)
        file_hash(path,digest,hashes)
        return {'path':str(path),'sha256':digest}
    expected={'receipt':bound(receipt_path),'images':[bound(path) for path in image_paths]}
    assert_exact(expected,value,'prefix.actual_visual_reference')


def prefix_visuals(prefix,paths,loaded,hashes):
    assert_exact([['advance','120'],['capture'],['advance','480'],['capture']],prefix['actions'],'neutral_prefix_actions')
    assert_exact([0,120,600],[s['frame'] for s in prefix['states']],'neutral_prefix_states')
    if any(state['host']['buttons']!=[0]*5 for state in prefix['states']):
        raise ValueError('No Run/input changes permitted before menu prefix completes')
    images=bind_images(prefix['images'],hashes)
    assert_exact([120,600],[image['frame'] for image in images],'prefix_visual_frames')
    api,_=_api()
    for image,frame in zip(images,(120,600)):
        original=api.png_identity(paths['menu_image_'+str(frame)])
        for key in ('width','height','rgb_sha256'):assert_exact(original[key],image[key],'actual_tool_menu_image.'+key)
    diagnostic=loaded['viewport_diagnostic']
    assert_exact('20fb8609fcf53aa8d914bb5647aa0410207a800e3e781b908b4661a24fcbf546',sha256(paths['viewport_diagnostic']),'sealed_viewport_diagnostic')
    assert_exact('pass',diagnostic['result'],'viewport.result')
    assert_exact(False,diagnostic['unaltered_full_frame_parity'],'viewport.raw_unequal')
    assert_exact(False,diagnostic['guest_device_clock_or_state_adjusted'],'viewport.no_state_adjustment')
    assert_exact([120,600],[row['frame'] for row in diagnostic['rows']],'viewport.frames')
    for row in diagnostic['rows']:
        for field,wanted in (('unaltered_original_rgb_equal',False),('reference_rows',[3,239]),('tool_rows',[0,236]),
            ('compared_pixels',60672),('viewport_rows_equal',True),('reference_top_three_rows_black',True),('tool_bottom_three_rows_black',True)):
            assert_exact(wanted,row[field],'viewport.'+field)
    for target,digest in diagnostic['evidence_sha256'].items():file_hash(target,digest,hashes)
    for frame in (120,600):
        target=paths['menu_image_'+str(frame)]
        file_hash(target,diagnostic['evidence_sha256'][str(target)],hashes)
    menu_receipt=paths['menu_image_120'].parent/'receipt.json'
    assert_exact(menu_receipt.parent,paths['menu_image_600'].parent,'both_retained_menu_image_origins')
    file_hash(menu_receipt,diagnostic['evidence_sha256'][str(menu_receipt)],hashes)
    validate_prefix_image_reference(prefix['prefix_image_reference'],menu_receipt,
        [paths['menu_image_'+str(frame)] for frame in (120,600)],hashes)
    menu=api.strict_json(menu_receipt)
    assert_exact(None,menu['error'],'retained_menu_completed')
    assert_exact(True,menu['child_stopped'],'retained_menu_stopped')
    assert_exact(images,bind_images(menu['images'],hashes),'prefix_exact_retained_menu_image_metadata')
    for image,state in zip(images,prefix['states'][1:]):
        assert_exact((state['frame'],state['ticks']),(image['frame'],image['ticks']),'prefix_image_status_boundary')
    return {'candidate_menu_images_exact_retained_tool_rgb':True,'frames':[120,600],
        'external_gear_raw_full_frames_equal':False,'aligned_external_gear_pixels_per_frame':60672,
        'gear_rows_inclusive':[3,239],'tool_rows_inclusive':[0,236],'omitted_borders_black':True,
        'scope':diagnostic['scope'],'guest_clock_or_hardware_equivalence_claim':False}


def validate_selection(selection,profile,profile_path,info,legacy_route,legacy_path,tool):
    manifest=module_manifest(info);identity(selection['tool_identity'])
    if type(selection['scope'])is not str or selection['scope'] not in SELECTION_SCOPES:
        raise ValueError('selection requires an exact reviewed public or ABI17-union scope statement')
    expected={'schema':1,'tool_identity':selection['tool_identity'],'route_sha256':sha256(legacy_path),
        'raw_capture_sha256':sha256(profile_path),'capture_runtime_abi':17,'module_runtime_abi':17,
        'translation_units':len(manifest['translation_units']),'raw_observations':len(profile['observations']),
        'raw_retired_instructions':profile['retired_instructions'],'raw_complete':True,
        'excluded_physical_ranges':manifest['excluded_physical_ranges'],'excluded_observations':manifest['excluded_observations'],
        'excluded_retired_hits':manifest['excluded_retired_hits'],'native_identities':manifest['native_instructions_emitted'],
        'mpr_contexts':manifest['native_contexts'],'unsupported_observations':manifest['unsupported_observations'],
        'assist_source_audit':audit_assist_source(profile,legacy_route,excluded_spans(legacy_route)),
        'expected_native_hits':profile['retired_instructions']-manifest['excluded_retired_hits'],'execution_evidence':False,
        'scope':selection['scope']}
    assert_exact(expected,selection,'selection.complete_actual_source_receipt')


def qualify_reset_native(baseline_receipt,candidate_receipt,*,reference_receipt,provenance):
    api,descriptor_api=_api();hashes={}
    for source in (__file__,api.__file__,descriptor_api.__file__,merge.__file__,prior.__file__,shared.__file__):
        file_hash(source,sha256(source),hashes)
    baseline_path,candidate_path,reference_path=[Path(p).resolve(strict=True) for p in
        (baseline_receipt,candidate_receipt,reference_receipt)]
    paths,loaded=load_provenance(provenance,hashes)
    file_hash(reference_path,sha256(reference_path),hashes)
    upstream=upstream_proofs(loaded,reference_path,paths,hashes)
    reference=api.strict_json(reference_path)
    shared.keys(reference,{'error','states','actions','images','inputs_unchanged','child_stopped','returncode'},'sealed_reference')
    ref_info=descriptor_api.load_reference(paths['reference_launch'],reference_path)
    assert_exact({k:REFERENCE_TOOL[k] for k in ('revision','source_sha256','source_files')},ref_info['reference_source'],'actual_reference_tool')
    for target,digest in loaded['reference_launch']['inputs'].items():file_hash(target,digest,hashes)
    reference_plan=api.route_plan(reference)
    assert_exact((STATES,ACTIONS,IMAGES,FRAMES),(len(reference['states']),len(reference['actions']),len(reference['images']),reference_plan['frames']),'complete_ordinary_reset_route')
    reference_runner=api.strict_json(paths['reference_run']);prior.source_identity(reference_runner,'reference.runner')
    ref_run=api.normalize_runner(reference_runner,desktop=False,project_tiers=True)
    validate_wav(paths['reference_wav'],ref_run['audio_output'],hashes)
    ref_images=bind_images(reference['images'],hashes)
    for state in reference['states']:api.normalize_status(state,desktop=False)
    baseline=bind_receipt(baseline_path,hashes);candidate=bind_receipt(candidate_path,hashes)
    prefix=bind_receipt(paths['boot_prefix_receipt'],hashes)
    receipts=[baseline[0],candidate[0],prefix[0]]
    tools=[item[3] for item in (baseline,candidate,prefix)]
    assert_exact(tools[0],tools[1],'same_final_tool_path');assert_exact(tools[1],tools[2],'prefix.same_tool_path')
    before=live_tool(tools[0])
    for value in receipts:assert_exact(before,value['tool_identity_before'],'actual_current_clean_tool')
    reference_bindings={'launch':{'path':str(paths['reference_launch']),'sha256':sha256(paths['reference_launch'])},
        'receipt':{'path':str(reference_path),'sha256':sha256(reference_path)},
        'runner':{'path':str(paths['reference_run']),'sha256':sha256(paths['reference_run'])},
        'wav':{'path':str(paths['reference_wav']),'sha256':sha256(paths['reference_wav'])}}
    for value in receipts:
        assert_exact(reference_bindings,value['reference'],'actual_reference_links')
        assert_exact(ref_info['reference_source'],value['reference_source'],'reference_source_epoch')
        assert_exact(baseline[0]['protected_inputs_before'],value['protected_inputs_before'],'same_seven_originals')
    bridges=[bind_input_bridge(value,reference_path,hashes) for value in receipts]
    assert_exact([],prefix[0]['input_status_annotations'],'neutral_prefix_has_no_input_latency_annotation')
    # Names/module selections may differ; the complete boot/media/runtime recipe may not.
    compare_recipes(baseline[1],candidate[1],left_descriptor=baseline[0]['project_descriptor'],
        right_descriptor=candidate[0]['project_descriptor'],left_tool=tools[0],right_tool=tools[1])
    assert_exact(candidate[1],prefix[1],'prefix.identical_candidate_descriptor')
    for field in ('project_descriptor','project_descriptor_sha256','project_build_receipt','asset_hashes_before'):
        assert_exact(candidate[0][field],prefix[0][field],'prefix.identical_candidate_package.'+field)
    assert_exact(candidate[0]['desktop_contract']['package_before'],prefix[0]['desktop_contract']['package_before'],'prefix.same_binary_and_adjacent_dll')
    measurements=[];input_annotations={}
    for side,(label,bundle) in enumerate((('baseline',baseline),('candidate',candidate))):
        receipt,config,info,tool,capture,report,run=bundle
        assert_exact(reference_plan,receipt['route_plan'],label+'.complete_route_plan')
        assert_exact(None,receipt['prefix_image_reference'],label+'.full_route_has_no_prefix_visual_reference')
        assert_exact(reference['actions'],receipt['actions'],label+'.literal_unassisted_actions')
        assert_exact(STATES,len(receipt['states']),label+'.all105_states')
        views,annotations=comparison_views(receipt,reference,sha256(reference_path),bridges[side])
        input_annotations[label]=annotations
        assert_exact(ref_images,bind_images(receipt['images'],hashes),label+'.all10_images')
        assert_exact(FRAMES,receipt['states'][-1]['frame'],label+'.final14680')
        assert_exact(ref_run,run,label+'.all_final_guest_source_cd_pcm_wav')
        assert_exact(sha256(paths['reference_wav']),sha256(Path(receipt['raw_files']['wav']['path'])),label+'.exact_wav_bytes')
        _,run_counts=prior.tiers(receipt['runner'],label+'.runner',blocks_required=True)
        assert_exact(reference_runner['native_steps']+reference_runner['interpreter_steps'],run_counts['total'],label+'.runner_retirements')
        if label=='baseline':
            assert_exact(0,run_counts['native'],'baseline.actual_native_zero')
            assert_exact(1,module_manifest(info)['native_instructions_emitted'],'baseline.one_unreachable_authored_identity')
        previous_counts=None
        for index,(actual,expected) in enumerate(zip(receipt['states'],views)):
            counts=compare_state(actual,expected)
            if label=='baseline':assert_exact(0,counts[0]['native'],'baseline.all_states_native_zero')
            if previous_counts is not None and any(counts[0][key]<previous_counts[key] for key in ('native','interpreted','total')):
                raise ValueError('checkpoint retirement counters moved backwards')
            previous_counts=counts[0]
            measurements.append({'run':label,'state':index,'frame':actual['frame'],'ticks':actual['ticks'],**counts[0]})
        compare_state(receipt['final_status'],reference['states'][-1])
    prior.compare_capture_observations(baseline[4],candidate[4])
    profile,composed=composition(paths,loaded,tools[0],baseline[4],baseline_path,hashes)
    emission=verify_candidate_emission(profile,paths['candidate_profile'],candidate[2],tools[0],loaded['legacy_route'],hashes)
    validate_selection(loaded['candidate_selection'],profile,paths['candidate_profile'],candidate[2],loaded['legacy_route'],paths['legacy_route'],tools[0])
    # Every old excluded source identity and its original hit provenance survives composition.
    api_capture=merge.load_capture_api(tools[0]);old_profile,_=api_capture.load_capture(paths['legacy_profile'])
    excluded=[item for item in old_profile['observations'] if any(1069880<=p<1069886 for p in item['physical'])]
    assert_exact(4,len(excluded),'old_original_excluded_variants')
    assert_exact(981,sum(item['native_hits']+item['interpreted_hits'] for item in excluded),'old_original_excluded_hits')
    prefix_subset(old_profile,profile)
    visuals=prefix_visuals(prefix[0],paths,loaded,hashes)
    assert_exact(api.boot_prefix_plan(reference),prefix[0]['route_plan'],'prefix.explicit_neutral_visual_plan')
    # Neutral split changes the journal, not the original 600-frame guest boundary.
    compare_state(prefix[0]['states'][-1],candidate[0]['states'][1],right_desktop=True)
    assert_exact(api.normalize_status(prefix[0]['states'][-1],desktop=True),
        api.normalize_status(candidate[0]['states'][1],desktop=True),'prefix.same_guest_source_and_actual_tiers_at600')
    compare_state(prefix[0]['states'][-1],reference['states'][1])
    bios=Path(candidate[2]['files']['bios']).read_bytes()
    boot=prove_native_bios(prefix[4],candidate[4],profile,bios)
    # Native observations must be actual emitted, non-excluded source identities.
    compiled={source_key(item) for item in profile['observations'] if not any(1069880<=p<1069886 for p in item['physical'])}
    for item in candidate[4]['observations']:
        if item['native_hits'] and source_key(item) not in compiled:raise ValueError('actual native work absent from emitted source/guards')
    assert_exact(before,live_tool(tools[0]),'actual_tool_unchanged_after_qualification')
    for target,digest in hashes.items():
        if sha256(target)!=digest:raise ValueError('reset qualification evidence changed: '+target)
    manifest_path=Path(candidate[2]['files']['module_manifest']);source_path=Path(candidate[2]['files']['module_source'])
    module={'manifest':{'path':str(manifest_path),'sha256':sha256(manifest_path)},
        'source':{'path':str(source_path),'sha256':sha256(source_path)},
        'artifacts':{target:candidate[2]['identities'][role] for role,target in candidate[2]['files'].items()
                     if role.startswith(('module_unit:','module_header:'))}}
    return {'schema':1,'kind':'ys3-reset-native-qualification','passed':True,'tool':TOOL,
        'selection':SELECTION,'frames':FRAMES,'states':STATES,'actions':ACTIONS,'images':IMAGES,
        'baseline_receipt':{'path':str(baseline_path),'sha256':sha256(baseline_path)},
        'candidate_receipt':{'path':str(candidate_path),'sha256':sha256(candidate_path)},'candidate_module':module,
        'baseline':baseline[5],'candidate':candidate[5],'boot_prefix':prefix[5],'native_bios':boot,
        'all_guest_source_cd_pcm_and_bounded_wav_exact_except_validated_input_status_latency':True,
        'all105_raw_button_snapshots_literal_equal':not any(input_annotations.values()),
        'input_status_latency':input_annotations,'memory_edits':0,
        'measurements':measurements,'emission':emission,'composition':composed,'upstream':upstream,'visuals':visuals,
        'normalization':{'status':['validated id','validated audio host presentation','validated WAV drain phase'],
            'runner':['validated desktop presentation','validated development.port','validated reset0 capture window'],
            'descriptor_tool_path':'Canonical actual verified root from each descriptor directory; raw descriptor bytes and all other tool/recipe fields remain bound.',
            'retirement_tiers':sorted(api.TIER_FIELDS),'input_status':'Only witnessed reference state54/action58 immediate release, with all other fields exact and strict following state55; every raw difference retained.'},'evidence_sha256':hashes,
        'scope':'Actual ordinary reset-super BIOS/menu/Run/Beginning/BRAM Proceed/town-opening route, with native BIOS retirements proved within same-package reset0-to600 original reference boundary;120 is an additional visual checkpoint, not a before120 per-source retirement proof. The one audited paused input-release snapshot may differ only under the retained narrow annotation and strict next advancing checkpoint. Unformatted BRAM remains volatile; gear-good unknown-CD compatibility is explicit. Complete guarded source profile is multi-run evidence, and uncovered instructions remain interpreted. External Gear evidence is finite authored parity and aligned menu viewport pixels; no retail CPU/device/hardware timing equivalence, listening test or campaign completion is claimed.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-receipt','candidate-receipt','reference-receipt','provenance','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():raise ValueError('qualification output must be new')
    result={'passed':False};failure=None
    try:result=qualify_reset_native(args.baseline_receipt,args.candidate_receipt,reference_receipt=args.reference_receipt,provenance=args.provenance)
    except (OSError,ValueError,RuntimeError,KeyError,IndexError,TypeError,wave.Error,subprocess.SubprocessError) as error:
        result['error']=repr(error);failure=error
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x',encoding='utf-8') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    if failure:raise failure
    print('PASS: native System Card reset qualification; '+str(args.out))


if __name__=='__main__':main()
