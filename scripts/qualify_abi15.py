"""Qualify the finite ABI13/15 legacy, default Gear and audio-off matrix.

Every exposed guest/source field stays exact. ABI15 held-DAC/CDDA-latch state
is not exposed by this pin's runner; reviewed finite upstream checks retain
their separate scope. No retail hardware or independent whole-mix claim.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tomllib
import wave

if __package__:
    from . import audio15_contract as audio15
    from . import dsp_contract as dsp
    from . import qualify_dsp as shared
    from . import qualify_native_audio as prior
    from .desktop_contract import validate_desktop, validate_package_proof
    from .package_checks import verify_package
    from .qualify_coverage import assert_exact, read_json
    from .replay_route import sha256, unwrap_execution, project_status, validate_project_binding, validate_project_outputs
else:
    import audio15_contract as audio15
    import dsp_contract as dsp
    import qualify_dsp as shared
    import qualify_native_audio as prior
    from desktop_contract import validate_desktop, validate_package_proof
    from package_checks import verify_package
    from qualify_coverage import assert_exact, read_json
    from replay_route import sha256, unwrap_execution, project_status, validate_project_binding, validate_project_outputs

TOOL = {'revision': 'e0f67bf64fe670723acd4443b0da76f3bfe8276f',
        'source_sha256': '38573f59cd17b1b9c640337ac6c1d9db80b3dc926d42312f8cedfd28d7959dd7', 'runtime_abi': 15}
OLD_TOOL = prior.CAPTURE_TOOL
LEGACY = {'profile': 'filtered', 'sample_rate': 48000, 'timing': 'legacy'}
GEAR = dict(LEGACY, timing='gear')
ROUTE = {'source_route_sha256', 'source_binary_sha256', 'initial_bram_sha256'}
BASE_ROLES = {'baseline_receipt', 'baseline_run', 'baseline_wav', 'baseline_qualification'}
REF_ROLES = {timing + '_' + item for timing in ('legacy', 'gear') for item in ('receipt', 'run', 'wav')}
REVIEW_ROLES = {'upstream_qualification', 'tool_contract', 'finite_state_evidence', 'independent_timing_evidence', 'reemission_proof'}
FILES = BASE_ROLES | REF_ROLES | REVIEW_ROLES
POINTERS = {'result', 'revision', 'source_sha256', 'runtime_abi', 'route_sha256', 'module_manifest_sha256'} | {
    role + '_sha256' for role in (REF_ROLES | (REVIEW_ROLES - {'upstream_qualification'}))}
ENDPOINTS = ('before_final_release', 'final_status', 'released_status')
FINAL_TIERS = {'native_steps': 2953438406, 'interpreter_steps': 981,
               'native_block_steps': 466118, 'interpreter_block_steps': 0, 'guard_misses': 981}


def success(value):
    return value is True or (type(value) is str and value in ('pass', 'passed', 'qualified'))


def load_expectation(path):
    path = Path(path).resolve(strict=True)
    value = read_json(path)
    shared.keys(value, {'schema', 'kind', 'tool', 'route', 'files', 'reviewed_binding',
                        'qualification_pointers', 'qualification_success', 'success_bindings'}, 'ABI15 expectation')
    assert_exact(1, value['schema'], 'expectation.schema')
    assert_exact('ys3-reviewed-abi15-matrix', value['kind'], 'expectation.kind')
    assert_exact(TOOL, value['tool'], 'expectation.tool')
    shared.keys(value['route'], ROUTE, 'expectation.route')
    for digest in value['route'].values():
        shared.digest(digest)
    shared.keys(value['files'], FILES, 'expectation.files')
    hashes, loaded, paths = {str(path): sha256(path)}, {}, {}
    for role, binding in value['files'].items():
        shared.keys(binding, {'path', 'sha256'}, role)
        if not isinstance(binding['path'], str) or not binding['path']:
            raise ValueError('explicit evidence path required')
        target = Path(binding['path'])
        target = prior.file_hash(target if target.is_absolute() else path.parent / target, binding['sha256'], hashes)
        paths[role] = target
        loaded[role] = target if role.endswith('_wav') else read_json(target)
    review = value['reviewed_binding']
    shared.keys(review, {'qualified', 'tool', 'route', 'evidence_sha256', 'execution', 'independent_scope',
                         'unexposed_internal_state_not_retail_verified'}, 'reviewed binding')
    assert_exact(True, review['qualified'], 'reviewed.qualified')
    assert_exact(True, review['unexposed_internal_state_not_retail_verified'], 'reviewed.unexposed_state')
    assert_exact(TOOL, review['tool'], 'reviewed.tool')
    assert_exact(value['route'], review['route'], 'reviewed.route')
    assert_exact({role: item['sha256'] for role, item in value['files'].items()}, review['evidence_sha256'], 'reviewed.evidence')
    assert_exact({'tier': 'hybrid', 'profile': 'filtered', 'sample_rate': 48000,
                  'legacy_explicit': True, 'gear_default': True, 'off_explicit': True,
                  'reference_host': 'headless', 'candidate_host': 'packaged-desktop'}, review['execution'], 'reviewed.execution')
    if not isinstance(review['independent_scope'], str) or not review['independent_scope'].strip():
        raise ValueError('actual reviewed independent scope required')
    shared.keys(value['qualification_pointers'], POINTERS, 'qualification pointers')
    if not success(value['qualification_success']):
        raise ValueError('explicit qualified upstream result required')
    expected = {'result': value['qualification_success'], 'revision': TOOL['revision'],
                'source_sha256': TOOL['source_sha256'], 'runtime_abi': 15,
                'route_sha256': value['route']['source_route_sha256'],
                'module_manifest_sha256': loaded['reemission_proof']['new_manifest']['sha256']}
    expected.update({role + '_sha256': value['files'][role]['sha256'] for role in
                     REF_ROLES | (REVIEW_ROLES - {'upstream_qualification'})})
    for role, pointer in value['qualification_pointers'].items():
        assert_exact(expected[role], shared.at(loaded['upstream_qualification'], pointer), 'upstream.' + role)
    shared.keys(value['success_bindings'], REVIEW_ROLES - {'upstream_qualification'}, 'evidence success bindings')
    for role, binding in value['success_bindings'].items():
        shared.keys(binding, {'pointer', 'value'}, 'evidence success')
        if not success(binding['value']):
            raise ValueError('each reviewed evidence result must explicitly pass')
        assert_exact(binding['value'], shared.at(loaded[role], binding['pointer']), role + '.passed')
    # Known audit graph fields are rehashed as actual artifacts, not merely
    # trusted because a JSON document lists them. Historical evidence must
    # point at explicit preserved bytes if its original source has moved on.
    for role in REVIEW_ROLES:
        for field in ('evidence_sha256', 'actual_hashed_artifacts', 'artifacts', 'tool_bindings'):
            if field not in loaded[role]:
                continue
            bindings = loaded[role][field]
            if not isinstance(bindings, dict):
                raise ValueError('review evidence requires a path/hash map: ' + role + '.' + field)
            for artifact, digest in bindings.items():
                target = Path(artifact)
                prior.file_hash(target if target.is_absolute() else paths[role].parent / target, digest, hashes)
    contract = loaded['tool_contract']
    assert_exact(15, contract['runtime_abi'], 'official_contract.abi')
    assert_exact(1, contract['descriptor_schema'], 'official_contract.schema')
    for key in ('revision', 'source_sha256'):
        assert_exact(TOOL[key], contract['tool_identity'][key], 'official_contract.' + key)
    baseline_q = loaded['baseline_qualification']
    if baseline_q.get('result') != 'pass':
        raise ValueError('completed frozen007 qualification required')
    for role in ('baseline_receipt', 'baseline_run', 'baseline_wav'):
        assert_exact(value['files'][role]['sha256'], baseline_q['evidence_sha256'][str(paths[role])], 'frozen007.' + role)
    return value, loaded, paths, hashes


def check_command(receipt, timing, mode, desktop, old=False):
    command = receipt['command']
    if not isinstance(command, list) or len(command) < 8 or not all(type(x) is str for x in command):
        raise ValueError('complete recorded argv required')
    assert_exact('hybrid', command[7], 'command.tier')
    assert_exact(mode, shared.option(command, '--audio-output'), 'command.audio')
    if mode == 'off':
        if any(flag in command for flag in ('--audio-profile', '--audio-rate', '--audio-timing', '--audio-out', '--audio-frames')):
            raise ValueError('off command cannot select PCM, timing, WAV or device production')
    else:
        assert_exact('filtered', shared.option(command, '--audio-profile'), 'command.profile')
        assert_exact('48000', shared.option(command, '--audio-rate'), 'command.rate')
        if old or timing == 'gear':
            if '--audio-timing' in command:
                raise ValueError('old schema/default Gear must omit timing override')
        else:
            assert_exact('legacy', shared.option(command, '--audio-timing'), 'command.explicit_legacy')
    for flag in ('--hidden', '--unthrottled'):
        if desktop:
            assert_exact('on', shared.option(command, flag), 'command.' + flag)
        elif flag in command:
            raise ValueError('headless reference contains desktop override')
    if not old and any(str(x).split('=', 1)[0] in ('--code-capture', '--capture-limit', '--code-capture-start-frame') for x in command):
        raise ValueError('ABI15 qualification runs must be capture-free')


def receipt_contract(receipt, timing, mode, desktop=True, old=False):
    if receipt.get('passed') is not True or type(receipt.get('exit_code')) is not int or receipt['exit_code'] != 0:
        raise ValueError('passed clean-exit route required')
    shared.identity(receipt, OLD_TOOL if old else TOOL, 'receipt')
    check_command(receipt, timing, mode, desktop, old)
    contract = receipt['audio_contract']
    assert_exact(13 if old else 15, contract['runtime_abi'], 'audio_contract.abi')
    assert_exact(mode, contract['mode'], 'audio_contract.mode')
    assert_exact(not desktop, contract['headless_pcm_only'], 'audio_contract.host')
    selected = None if mode == 'off' else dict(LEGACY if timing == 'legacy' else GEAR)
    if not old:
        # These separately frozen root headless references recorded the older
        # exact profile/rate selection metadata. Their timing remains bound by
        # explicit legacy/default Gear argv, validated marker and root review.
        # The consumer's packaged ABI15 records must retain all three keys.
        recorded = ({key: selected[key] for key in ('profile', 'sample_rate')}
                    if not desktop and selected is not None else selected)
        assert_exact(recorded, receipt.get('audio_selection'), 'audio_selection')
        if 'capture_contract' in receipt:
            raise ValueError('no ABI15 managed capture contract accepted')
    if mode == 'off':
        assert_exact(None, contract['wav_frame_limit'], 'off.wav_limit')
        assert_exact(None, contract['validated_output'], 'off.validated_output')
        assert_exact(True, contract['audio_output_absent'], 'off.absence')
        if any(key in contract for key in ('wav_path', 'wav_sha256', 'wav_bytes')):
            raise ValueError('off receipt must not contain WAV evidence')
    else:
        assert_exact(1440000, contract['wav_frame_limit'], 'bounded_30_second_wav')
    if not desktop:
        return
    proof = receipt['desktop_contract']
    for key in ('packaged', 'hidden', 'unthrottled', 'working_directory_initially_empty', 'working_directory_finally_empty'):
        assert_exact(True, proof[key], 'desktop.' + key)
    validate_package_proof(proof, receipt['binary_sha256'])
    assert_exact(proof['package_before'], proof['package_after'], 'desktop.package_after')
    assert_exact(proof['package_before']['binary'], receipt['command'][0], 'desktop.command_binary')
    assert_exact(False, receipt['shared_project_run_used'], 'official.consumer_supervision')
    assert_exact('shared-verify-then-consumer-route', receipt['project_execution_mode'], 'official.execution_mode')
    assert_exact(receipt['project_verification_before'], receipt['project_verification_after'], 'official.verification_after')
    assert_exact(receipt['project_output_files_before'], receipt['project_output_files_after'], 'official.outputs_after')
    assert_exact(proof['package_before']['output_files'], receipt['project_output_files_before'], 'official.package_outputs')
    if mode == 'off' and 'audio_output' in proof:
        raise ValueError('off desktop receipt must not invent device/audio state')


def module_files(manifest_path, hashes):
    manifest_path = Path(manifest_path).resolve(strict=True)
    manifest = read_json(manifest_path)
    prior.file_hash(manifest_path, sha256(manifest_path), hashes)
    units, headers = manifest['translation_units'], manifest['generated_headers']
    assert_exact(208, len(units), 'module.translation_units')
    assert_exact(1, len(headers), 'module.generated_headers')
    result, seen = {}, set()
    for field, suffix in ((units, '.cpp'), (headers, '.hpp')):
        for item in field:
            shared.keys(item, {'file', 'sha256'}, 'module artifact')
            name = item['file']
            if (not isinstance(name, str) or Path(name).name != name or '/' in name or '\\' in name
                    or not name.endswith(suffix) or name.casefold() in seen):
                raise ValueError('unique direct module artifact basename required')
            seen.add(name.casefold())
            target = manifest_path.parent / name
            if target.is_symlink():
                raise ValueError('module symlink refused')
            result[name] = prior.file_hash(target, item['sha256'], hashes)
    return manifest, result


def bind_descriptor(receipt, timing, mode, hashes, old=False):
    descriptor = prior.file_hash(receipt['project_descriptor'], receipt['project_descriptor_sha256'], hashes)
    config = tomllib.loads(descriptor.read_text(encoding='utf-8'))
    tool = OLD_TOOL if old else TOOL
    assert_exact(1, config['schema'], 'descriptor.schema')
    for key in tool:
        assert_exact(tool[key], config['tool'][key], 'descriptor.tool.' + key)
    runtime = config['runtime']
    assert_exact('hybrid', runtime['tier'], 'descriptor.tier')
    assert_exact(mode, runtime['audio'], 'descriptor.audio')
    if mode == 'off':
        if any(key in runtime for key in ('audio_profile', 'audio_rate', 'audio_timing')):
            raise ValueError('off descriptor cannot select synthesis')
    else:
        assert_exact('filtered', runtime['audio_profile'], 'descriptor.profile')
        assert_exact(48000, runtime['audio_rate'], 'descriptor.rate')
        if old or timing == 'gear':
            if 'audio_timing' in runtime:
                raise ValueError('default Gear/old descriptor must omit timing override')
        else:
            assert_exact('legacy', runtime['audio_timing'], 'descriptor.explicit_legacy')
    build_path = prior.file_hash(Path(receipt['project_build']) / 'build-receipt.json', receipt['project_build_receipt_sha256'], hashes)
    built = read_json(build_path)
    binding = validate_project_binding(built, receipt['project_verification_before'])
    assert_exact(binding, receipt['project_binding'], 'official.recorded_binding')
    assert_exact(receipt['project_descriptor_sha256'], binding['descriptor_sha256'], 'official.descriptor')
    for key in ('revision', 'source_sha256'):
        assert_exact(tool[key], binding['tool'][key], 'official.tool.' + key)
    binary = Path(receipt['command'][0]).resolve(strict=True)
    outputs = validate_project_outputs(built, binary)
    assert_exact(outputs, receipt['project_output_files_before'], 'official.actual_outputs')
    for name, digest in outputs.items():
        prior.file_hash(binary.parent / name, digest, hashes)
    assert_exact(verify_package(built, binary), receipt['desktop_contract']['package_before'], 'official.actual_package')
    declared = {}
    def file(role, value):
        target = Path(value['path'])
        target = prior.file_hash(target if target.is_absolute() else descriptor.parent / target, value['sha256'], hashes)
        declared[role] = value['sha256']
        return target
    source = file('module_source', config['module']['source'])
    manifest_path = file('module_manifest', config['module']['manifest'])
    module, artifacts = module_files(manifest_path, hashes)
    assert_exact(tool['runtime_abi'], module['runtime_abi'], 'module.abi')
    if source != artifacts.get('module.cpp'):
        raise ValueError('module source must be actual bound entry translation unit')
    for name, target in artifacts.items():
        declared[('module_header:' if name.endswith('.hpp') else 'module_unit:') + name] = sha256(target)
    file('payload', config['payload'])
    for role in ('bios', 'disc', 'toc', 'libchdr', 'bram', 'input_script'):
        if role in config:
            file(role, config[role])
    assert_exact(declared, binding['files'], 'official.all_actual_source_files')
    return config, manifest_path, module, artifacts


def regenerated_module(old_module, new_module):
    """Recompute direct source equality; no old output hash is reassigned."""
    _, _, old_manifest, old_files = old_module
    _, _, new_manifest, new_files = new_module
    left, right = copy.deepcopy(old_manifest), copy.deepcopy(new_manifest)
    assert_exact(13, left.pop('runtime_abi'), 'old.module_abi')
    assert_exact(15, right.pop('runtime_abi'), 'new.module_abi')
    for field in ('translation_units', 'generated_headers'):
        assert_exact([v['file'] for v in left.pop(field)], [v['file'] for v in right.pop(field)], 'reemitted.' + field)
    assert_exact(left, right, 'reemitted.complete_manifest_provenance')
    assert_exact(44879, right['native_instructions_emitted'], 'reemitted.identities')
    assert_exact(13, right['capture_runtime_abi'], 'reemitted.input_capture_abi')
    assert_exact(4, right['excluded_observations'], 'reemitted.excluded_identities')
    assert_exact(981, right['excluded_retired_hits'], 'reemitted.excluded_hits')
    assert_exact([{'start': 1069880, 'length': 6}], right['excluded_physical_ranges'], 'reemitted.excluded_full_span')
    assert_exact(['full_mpr_snapshot', 'exact_source_bytes_per_instruction', 'instruction_deadline'], right['guards'], 'reemitted.guards')
    old_assert, new_assert = b'static_assert(abi_version == 13);', b'static_assert(abi_version == 15);'
    changed, unchanged = [], []
    assert_exact(set(old_files), set(new_files), 'reemitted.artifact_set')
    for name in sorted(old_files):
        before, after = old_files[name].read_bytes(), new_files[name].read_bytes()
        if before == after:
            unchanged.append(name)
        else:
            if before.count(old_assert) != 1 or after.count(new_assert) != 1 or before.replace(old_assert, new_assert) != after:
                raise ValueError('reemitted translated operations/guards changed: ' + name)
            changed.append(name)
    return {'artifacts': len(old_files), 'unchanged_artifacts': unchanged,
            'exact_abi_static_assert_changes': changed, 'translated_operations_and_guards_exact': True,
            'capture_runtime_abi': 13, 'module_runtime_abi': 15}


def check_reemission_proof(proof, old_module, new_module, recomputed, hashes):
    shared.identity({'tool_identity': proof['tool'], 'tool_identity_after': proof['tool']}, TOOL, 'reemission.tool')
    for field, module in (('old_manifest', old_module), ('new_manifest', new_module)):
        binding = proof[field]
        target = prior.file_hash(binding['path'], binding['sha256'], hashes)
        assert_exact(module[1], target, 'reemission.' + field + '.path')
    capture = prior.file_hash(proof['capture']['path'], proof['capture']['sha256'], hashes)
    assert_exact(new_module[2]['code_capture_sha256'], sha256(capture), 'reemission.unchanged_input_capture')
    assert_exact(13, proof['source_capture_runtime_abi'], 'reemission.input_abi')
    assert_exact(15, proof['module_runtime_abi'], 'reemission.output_abi')
    assert_exact(209, proof['artifact_count'], 'reemission.artifact_count')
    assert_exact(len(recomputed['exact_abi_static_assert_changes']), proof['assertion_only_changed_artifacts'], 'reemission.assertion_change_count')
    assert_exact({'only_bytes_from': 'static_assert(abi_version == 13);',
                  'only_bytes_to': 'static_assert(abi_version == 15);',
                  'all_other_source_bytes_exact': True, 'all_other_manifest_metadata_exact': True}, proof['normalization'], 'reemission.normalization')
    expected_names = set(old_module[3])
    names = [item['file'] for item in proof['files']]
    assert_exact(expected_names, set(names), 'reemission.proof_artifacts')
    assert_exact(209, len(names), 'reemission.proof_unique_artifacts')
    for item in proof['files']:
        name = item['file']
        for side, module in (('old', old_module), ('new', new_module)):
            target = prior.file_hash(item[side]['path'], item[side]['sha256'], hashes)
            assert_exact(module[3][name], target, 'reemission.' + side + '.actual_artifact')
        assert_exact(1 if name in recomputed['exact_abi_static_assert_changes'] else 0,
                     item['abi_assertions_replaced'], 'reemission.proof_assertion_count')
        assert_exact(True, item['translated_operations_and_guards_exact'], 'reemission.proof_operations')
    for path, digest in proof['evidence_sha256'].items():
        prior.file_hash(path, digest, hashes)


def live_tool(config, descriptor):
    target = Path(config['tool']['path'])
    target = (target if target.is_absolute() else Path(descriptor).parent / target).resolve(strict=True)
    completed = subprocess.run([sys.executable, str(Path(__file__).with_name('verify_tool.py')),
        '--tool-root', str(target), '--expected-revision', TOOL['revision'], '--expected-abi', '15',
        '--expected-source-sha256', TOOL['source_sha256']], check=True, capture_output=True, text=True, timeout=60)
    value = json.loads(completed.stdout)
    shared.identity({'tool_identity': value, 'tool_identity_after': value}, TOOL, 'live15tool')
    return value


def audio_core(value, timing, mode, desktop, checkpoint=False, old=False):
    if mode == 'off':
        return audio15.validate_headless(value, None)
    if old:
        return dsp.desktop_audio(value, {'profile': 'filtered', 'sample_rate': 48000}, 1440000, checkpoint)
    chosen = LEGACY if timing == 'legacy' else GEAR
    return (audio15.validate_desktop(value, chosen, 1440000, checkpoint) if desktop else
            audio15.validate_headless(value, chosen, 1440000, checkpoint))


def gear_source_clock(core, ticks, label):
    """Gear ceiling-edge source n is due exactly when n*master <=ticks*rate."""
    prior.nonnegative(ticks, label + '.guest_ticks')
    assert_exact(ticks * 44100 // 21477273, core['processing']['source_frames'], label + '.gear_source_clock')


def run_projection(receipt, run, timing, mode, desktop, hashes, old=False, module=None):
    run = copy.deepcopy(unwrap_execution(run, receipt['binary_sha256']))
    if run.get('stop') != 'dev_quit':
        raise ValueError('completed TCP controlled quit required')
    prior.source_identity(run, 'runner')
    for field, expected in FINAL_TIERS.items():
        assert_exact(expected, run[field], 'retained.' + field)
    if mode == 'off' and 'audio_output' in run:
        raise ValueError('off runner must omit audio_output')
    raw = run.pop('audio_output', None)
    core = audio_core(raw, timing, mode, desktop, old=old)
    if not old and timing == 'gear' and mode == 'on':
        gear_source_clock(core, run['ticks'], 'runner')
    assert_exact(core, receipt['audio_contract']['validated_output'], 'runner.validated_output')
    if desktop:
        presentation = validate_desktop(run.pop('desktop'), 94800)
        assert_exact(presentation, receipt['desktop_contract']['presentation'], 'runner.presentation')
        if mode != 'off':
            assert_exact(raw, receipt['desktop_contract']['audio_output'], 'runner.desktop_audio')
    if old:
        # This original ABI13 capture is validated in its own reviewed epoch.
        original = copy.deepcopy(unwrap_execution(read_json(Path(receipt['_path']).parent / 'run.stdout'), receipt['binary_sha256']))
        route = read_json(Path(receipt['source_route']))
        _, report = prior.validate_managed_capture(receipt, module[0], original, route, 93735, OLD_TOOL, hashes, 'frozen007')
        window = run.pop('code_capture_window')
        assert_exact({'requested_start_frame': 93735, 'started': True, 'actual_start_frame': 93735,
                      'actual_start_ticks': 33650360835, 'native_steps_before': 2920491782,
                      'interpreter_steps_before': 981}, window, 'frozen007.capture_window')
        assert_exact(32946624, report['retired_instructions'], 'frozen007.capture_retirements')
    elif 'code_capture_window' in run:
        raise ValueError('capture-free ABI15 runner cannot contain a capture window')
    run['development'].pop('port', None)
    return run, core


def status_projection(state, timing, mode, desktop, checkpoint, old=False):
    if not isinstance(state, dict) or not set(state) <= {'frame', 'ticks', 'paused', 'local_paused', 'host', 'id', 'ok'}:
        raise ValueError('unknown checkpoint schema field')
    prior.source_identity(state['host'], 'checkpoint', status=True)
    projected = project_status(state)
    raw = projected['host'].pop('audio_output', None)
    if mode == 'off' and 'audio_output' in state['host']:
        raise ValueError('off checkpoint must omit audio_output')
    core = audio_core(raw, timing, mode, desktop, checkpoint, old)
    if not old and timing == 'gear' and mode == 'on':
        gear_source_clock(core, state['ticks'], 'checkpoint')
    return projected, core


def generated_command(receipt, old=False):
    command = receipt['command'].copy()
    command[0] = '<bound-executable>'
    for flag in ('--audio-output', '--audio-profile', '--audio-rate', '--audio-timing', '--audio-out', '--audio-frames',
                 '--hidden', '--unthrottled') + (('--code-capture', '--capture-limit', '--code-capture-start-frame') if old else ()):
        if flag in command:
            shared.option(command, flag)
            index = command.index(flag)
            del command[index:index + 2]
    return command


def qualify_abi15(baseline_receipt, legacy_receipt, gear_receipt, off_receipt, expectation_path):
    expectation, references, reference_paths, hashes = load_expectation(expectation_path)
    paths = [Path(p).resolve(strict=True) for p in (baseline_receipt, legacy_receipt, gear_receipt, off_receipt)]
    assert_exact(reference_paths['baseline_receipt'], paths[0], 'bound_old_receipt')
    assert_exact(reference_paths['baseline_run'], paths[0].parent / 'run.stdout', 'bound_old_run')
    assert_exact(reference_paths['baseline_wav'], paths[0].parent / 'audio.wav', 'bound_old_wav')
    live_config = tomllib.loads(Path(read_json(paths[1])['project_descriptor']).read_text(encoding='utf-8'))
    live_before = live_tool(live_config, read_json(paths[1])['project_descriptor'])
    receipts = [read_json(path) for path in paths] + [references['legacy_receipt'], references['gear_receipt']]
    timings, modes, desktop = ['legacy', 'legacy', 'gear', 'gear', 'legacy', 'gear'], ['on', 'on', 'on', 'off', 'on', 'on'], [True] * 4 + [False] * 2
    runs, cores, modules = [], [], []
    baseline_inputs, baseline_command, baseline_route = None, None, None
    for index, (receipt, timing, mode, packaged) in enumerate(zip(receipts, timings, modes, desktop)):
        old = index == 0
        if index < 4:
            path = prior.file_hash(paths[index], sha256(paths[index]), hashes)
            raw_path = prior.file_hash(path.parent / 'run.stdout', sha256(path.parent / 'run.stdout'), hashes)
        else:
            path = reference_paths[timing + '_receipt']
            raw_path = reference_paths[timing + '_run']
        receipt['_path'] = str(path)
        receipt_contract(receipt, timing, mode, packaged, old)
        for key in ROUTE:
            assert_exact(expectation['route'][key], receipt[key], 'retained.' + key)
        for name, digest in receipt['input_sha256'].items():
            prior.file_hash(name, digest, hashes)
        if packaged:
            module = bind_descriptor(receipt, timing, mode, hashes, old)
            modules.append(module)
        else:
            module = None
        if mode == 'on':
            shared.wav(receipt, path, 48000, hashes, artifact=reference_paths[timing + '_wav'] if index >= 4 else None)
        elif (path.parent / 'audio.wav').exists():
            raise ValueError('audio-off run must not create a WAV')
        run, core = run_projection(receipt, read_json(raw_path), timing, mode, packaged, hashes, old, module)
        runs.append(run)
        cores.append(core)
        protected = receipt['input_sha256'].copy()
        protected.pop(receipt['command'][0], None)
        if index == 0:
            baseline_inputs, baseline_command = protected, generated_command(receipt, True)
            route_path = prior.file_hash(receipt['source_route'], receipt['source_route_sha256'], hashes)
            baseline_route = read_json(route_path)
            assert_exact(baseline_route['initial_command'], receipt['source_command'], 'original_source_command')
            assert_exact(709, receipt['memory_edits_replayed'], 'original_assist_count')
            assert_exact(94800, receipt['final_status']['frame'], 'full_route_frames')
        else:
            assert_exact(baseline_inputs, protected, 'protected_inputs')
            if packaged:
                assert_exact(baseline_command, generated_command(receipt), 'original_guest_command')
            for field in ('images', 'source_command', 'memory_edits_replayed'):
                assert_exact(receipts[0][field], receipt[field], 'retained.' + field)
    assert_exact(39, len(receipts[0]['images']), 'all_route_images')
    assert_exact([{'frame': x['frame'], 'png_sha256': x['png_sha256']} for x in baseline_route['checkpoints']],
                 [{'frame': x['frame'], 'png_sha256': x['png_sha256']} for x in receipts[0]['images']], 'actual_route_images')
    for run in runs[1:]:
        assert_exact(runs[0], run, 'all_exposed_guest_runner_and_native_tiers')
    assert_exact(cores[0], cores[1], 'legacy.exact_old_pcm')
    assert_exact(cores[1], cores[4], 'legacy.exact_new_headless_pcm')
    assert_exact(cores[2], cores[5], 'gear.exact_new_headless_pcm')
    assert_exact(receipts[0]['audio_contract']['wav_sha256'], receipts[1]['audio_contract']['wav_sha256'], 'legacy.exact_old_wav')
    for candidate, reference in ((1, 4), (2, 5)):
        assert_exact(receipts[reference]['audio_contract']['wav_sha256'], receipts[candidate]['audio_contract']['wav_sha256'], 'new_reference.exact_wav')
    regeneration = [regenerated_module(modules[0], module) for module in modules[1:]]
    check_reemission_proof(references['reemission_proof'], modules[0], modules[1], regeneration[0], hashes)
    for module in modules[2:]:
        assert_exact(modules[1][2], module[2], 'all_new15_same_module')
    measurements = []
    for field in ('checkpoint_status',) + ENDPOINTS:
        groups = [receipt[field] if field == 'checkpoint_status' else [receipt[field]] for receipt in receipts]
        assert_exact(39 if field == 'checkpoint_status' else 1, len(groups[0]), 'complete.' + field)
        for group in groups[1:]:
            assert_exact(len(groups[0]), len(group), 'complete.reference.' + field)
        for states in zip(*groups):
            guests, outputs = [], []
            for index, (state, timing, mode, packaged) in enumerate(zip(states, timings, modes, desktop)):
                assert_exact(set(states[0]), set(state), 'status.complete_schema')
                guest, core = status_projection(state, timing, mode, packaged, field == 'checkpoint_status', index == 0)
                guests.append(guest)
                outputs.append(core)
            for guest in guests[1:]:
                assert_exact(guests[0], guest, field + '.all_guest_native_source')
            # WAV phase is validated separately before comparing generated PCM.
            compare = shared.no_wav if field == 'checkpoint_status' else lambda x: x
            for left, right in ((0, 1), (1, 4), (2, 5)):
                assert_exact(compare(outputs[left]), compare(outputs[right]), field + '.exact_pcm')
            if field != 'checkpoint_status':
                for core, output in zip(cores, outputs):
                    assert_exact(core, output, field + '.runner_audio')
            measurements.append({'field': field, 'frame': states[0]['frame'], 'legacy_pcm': outputs[1], 'gear_pcm': outputs[2], 'off_pcm_absent': outputs[3] is None})
    assert_exact(live_before, live_tool(live_config, receipts[1]['project_descriptor']), 'live15tool.after')
    for path, digest in hashes.items():
        if sha256(path) != digest:
            raise ValueError('evidence changed during ABI15 qualification: ' + path)
    return {'schema': 1, 'kind': 'ys3-abi15-matrix-qualification', 'passed': True,
            'tool': TOOL, 'legacy_exact_old_guest_native_source_pcm_wav': True,
            'gear_exact_new_headless_reference': True, 'off_exact_gear_guest_and_pcm_absent': True,
            'images': 39, 'checkpoint_states': 39, 'endpoint_states': 3, 'frames': 94800,
            'memory_edits_replayed': 709, 'retained_native_counts': FINAL_TIERS,
            'reemission': regeneration, 'final_audio': {'legacy': cores[1], 'gear': cores[2], 'off': None},
            'measurements': measurements, 'reviewed_binding': expectation['reviewed_binding'], 'evidence_sha256': hashes,
            'scope': 'All exposed guest/source fields retained; explicit legacy PCM/WAV reproduces frozen007, default Gear matches a separately qualified headless route, and off preserves exposed guest execution without PCM/WAV/device telemetry. Unexposed held-DAC/CDDA clock/latch state relies on separately scoped finite upstream evidence, not retail observation. No independent retail-mix, listening, analog, hardware or campaign claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-receipt', 'legacy-receipt', 'gear-receipt', 'off-receipt', 'expectation', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('qualification output must be new')
    result, failure = {'passed': False}, None
    try:
        result = qualify_abi15(args.baseline_receipt, args.legacy_receipt, args.gear_receipt, args.off_receipt, args.expectation)
    except (OSError, ValueError, RuntimeError, KeyError, IndexError, TypeError, wave.Error, subprocess.SubprocessError) as error:
        result.update(error=repr(error))
        failure = error
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    if failure:
        raise failure
    print('PASS: ABI15 legacy/default Gear/off matrix; ' + str(args.out))


if __name__ == '__main__':
    main()
