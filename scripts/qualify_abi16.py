"""Qualify the finite ABI16 packaged/headless compatibility matrix.

All exposed ABI16 guest/source/CD fields are exact against frozen references.
ABI15 conservation is measured separately: an ABI upgrade is not new coverage.
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
    from . import qualify_abi15 as previous
    from . import qualify_dsp as shared
    from . import qualify_native_audio as prior
    from .compat16_contract import validate_cd_unknown
    from .desktop_contract import validate_desktop, validate_package_proof
    from .package_checks import verify_package
    from .qualify_coverage import assert_exact, read_json
    from .replay_route import sha256, unwrap_execution, project_status, validate_project_binding, validate_project_outputs
else:
    import qualify_abi15 as previous
    import qualify_dsp as shared
    import qualify_native_audio as prior
    from compat16_contract import validate_cd_unknown
    from desktop_contract import validate_desktop, validate_package_proof
    from package_checks import verify_package
    from qualify_coverage import assert_exact, read_json
    from replay_route import sha256, unwrap_execution, project_status, validate_project_binding, validate_project_outputs

TOOL = {'revision': '3bd06b5055c92e9f368aab7023098ff8aa796854',
        'source_sha256': '720e3c1e980e3ad9d03b28cb4b31db696fe3bb27e687c0cf19bc3d0f3f1c9440', 'runtime_abi': 16}
LEGACY, GEAR = previous.LEGACY, previous.GEAR
ROUTE, ENDPOINTS = previous.ROUTE, previous.ENDPOINTS
REF_ROLES = {timing + '_' + item for timing in ('legacy', 'gear') for item in ('receipt', 'run', 'wav')}
BASE_ROLES = {'baseline_' + role for role in REF_ROLES} | {'baseline_qualification'}
REVIEW_ROLES = {'upstream_qualification', 'tool_contract', 'reemission_proof'}
FILES = REF_ROLES | BASE_ROLES | REVIEW_ROLES
POINTERS = {'result', 'revision', 'source_sha256', 'runtime_abi', 'route_sha256', 'module_manifest_sha256'} | {
    role + '_sha256' for role in REF_ROLES | (REVIEW_ROLES - {'upstream_qualification'})}
EXECUTION = {'tier': 'hybrid', 'profile': 'filtered', 'sample_rate': 48000,
             'legacy_explicit': True, 'gear_default': True, 'off_explicit': True,
             'reference_host': 'headless', 'candidate_host': 'packaged-desktop'}
module_files = previous.module_files
audio_core = previous.audio_core
gear_source_clock = previous.gear_source_clock
generated_command = previous.generated_command
success = previous.success

def check_command(receipt, timing, mode, desktop):
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
        assert_exact('1440000', shared.option(command, '--audio-frames'), 'command.wav_limit')
        if timing == 'gear':
            if '--audio-timing' in command:
                if desktop:
                    raise ValueError('packaged default Gear must omit timing override')
                assert_exact('gear', shared.option(command, '--audio-timing'), 'command.reference_explicit_gear')
        else:
            assert_exact('legacy', shared.option(command, '--audio-timing'), 'command.explicit_legacy')
    for flag in ('--hidden', '--unthrottled'):
        if desktop:
            assert_exact('on', shared.option(command, flag), 'command.' + flag)
        elif flag in command:
            raise ValueError('headless reference contains desktop override')
    if any(str(x).split('=', 1)[0] in ('--code-capture', '--capture-limit', '--code-capture-start-frame') for x in command):
        raise ValueError('ABI16 qualification runs must be capture-free')


def receipt_contract(receipt, timing, mode, desktop=True):
    if receipt.get('passed') is not True or type(receipt.get('exit_code')) is not int or receipt['exit_code'] != 0:
        raise ValueError('passed clean-exit route required')
    shared.identity(receipt, TOOL, 'receipt')
    assert_exact(54, receipt['tool_identity']['shared_source_identity']['source_files'], 'receipt.source_files')
    check_command(receipt, timing, mode, desktop)
    contract = receipt['audio_contract']
    assert_exact(16, contract['runtime_abi'], 'audio_contract.abi')
    assert_exact(mode, contract['mode'], 'audio_contract.mode')
    assert_exact(not desktop, contract['headless_pcm_only'], 'audio_contract.host')
    selected = None if mode == 'off' else dict(LEGACY if timing == 'legacy' else GEAR)
    assert_exact(selected, receipt.get('audio_selection'), 'audio_selection')
    if 'capture_contract' in receipt:
        raise ValueError('ABI16 matrix runs must be capture-free')
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


def bind_descriptor(receipt, timing, mode, hashes, desktop=True):
    descriptor = prior.file_hash(receipt['project_descriptor'], receipt['project_descriptor_sha256'], hashes)
    config = tomllib.loads(descriptor.read_text(encoding='utf-8'))
    tool = TOOL
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
        if timing == 'gear':
            if 'audio_timing' in runtime:
                if desktop:
                    raise ValueError('packaged default Gear descriptor must omit timing override')
                assert_exact('gear', runtime['audio_timing'], 'descriptor.reference_explicit_gear')
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
    assert_exact(desktop, built['desktop'], 'official.build_host')
    assert_exact(receipt['project_verification_before'], receipt['project_verification_after'], 'official.verification_after')
    assert_exact(receipt['project_output_files_before'], receipt['project_output_files_after'], 'official.outputs_after')
    if desktop:
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
    assert_exact(15, left.pop('runtime_abi'), 'old.module_abi')
    assert_exact(16, right.pop('runtime_abi'), 'new.module_abi')
    for field in ('translation_units', 'generated_headers'):
        assert_exact([v['file'] for v in left.pop(field)], [v['file'] for v in right.pop(field)], 'reemitted.' + field)
    assert_exact(left, right, 'reemitted.complete_manifest_provenance')
    assert_exact(44879, right['native_instructions_emitted'], 'reemitted.identities')
    assert_exact(57, right['native_contexts'], 'reemitted.contexts')
    assert_exact(0, right['unsupported_observations'], 'reemitted.unsupported')
    assert_exact(13, right['capture_runtime_abi'], 'reemitted.input_capture_abi')
    assert_exact(4, right['excluded_observations'], 'reemitted.excluded_identities')
    assert_exact(981, right['excluded_retired_hits'], 'reemitted.excluded_hits')
    assert_exact([{'start': 1069880, 'length': 6}], right['excluded_physical_ranges'], 'reemitted.excluded_full_span')
    assert_exact(['full_mpr_snapshot', 'exact_source_bytes_per_instruction', 'instruction_deadline'], right['guards'], 'reemitted.guards')
    old_assert, new_assert = b'static_assert(abi_version == 15);', b'static_assert(abi_version == 16);'
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
            'capture_runtime_abi': 13, 'module_runtime_abi': 16}


def check_reemission_proof(proof, old_module, new_module, recomputed, hashes):
    shared.identity({'tool_identity': proof['tool'], 'tool_identity_after': proof['tool']}, TOOL, 'reemission.tool')
    assert_exact(54, proof['tool']['shared_source_identity']['source_files'], 'reemission.source_files')
    for field, module in (('old_manifest', old_module), ('new_manifest', new_module)):
        binding = proof[field]
        target = prior.file_hash(binding['path'], binding['sha256'], hashes)
        assert_exact(module[1], target, 'reemission.' + field + '.path')
    capture = prior.file_hash(proof['capture']['path'], proof['capture']['sha256'], hashes)
    assert_exact(new_module[2]['code_capture_sha256'], sha256(capture), 'reemission.unchanged_input_capture')
    assert_exact(13, proof['source_capture_runtime_abi'], 'reemission.input_abi')
    assert_exact(16, proof['module_runtime_abi'], 'reemission.output_abi')
    assert_exact(209, proof['artifact_count'], 'reemission.artifact_count')
    assert_exact(len(recomputed['exact_abi_static_assert_changes']), proof['assertion_only_changed_artifacts'], 'reemission.assertion_change_count')
    assert_exact({'only_bytes_from': 'static_assert(abi_version == 15);',
                  'only_bytes_to': 'static_assert(abi_version == 16);',
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
        '--tool-root', str(target), '--expected-revision', TOOL['revision'], '--expected-abi', '16',
        '--expected-source-sha256', TOOL['source_sha256']], check=True, capture_output=True, text=True, timeout=60)
    value = json.loads(completed.stdout)
    shared.identity({'tool_identity': value, 'tool_identity_after': value}, TOOL, 'live16tool')
    assert_exact(54, value['shared_source_identity']['source_files'], 'live16tool.source_files')
    return value



def load_expectation(path):
    path = Path(path).resolve(strict=True)
    value = read_json(path)
    shared.keys(value, {'schema', 'kind', 'tool', 'route', 'files', 'reviewed_binding',
                        'qualification_pointers', 'qualification_success', 'success_bindings'}, 'ABI16 expectation')
    assert_exact(1, value['schema'], 'expectation.schema')
    assert_exact('ys3-reviewed-abi16-matrix', value['kind'], 'expectation.kind')
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
                         'cd_origin_is_initial_latch_not_retirement', 'no_new_native_coverage_claim'}, 'reviewed binding')
    for field in ('qualified', 'cd_origin_is_initial_latch_not_retirement', 'no_new_native_coverage_claim'):
        assert_exact(True, review[field], 'reviewed.' + field)
    for field in ('tool', 'route'):
        assert_exact(value[field], review[field], 'reviewed.' + field)
    assert_exact({role: binding['sha256'] for role, binding in value['files'].items()}, review['evidence_sha256'], 'reviewed.evidence')
    assert_exact(EXECUTION, review['execution'], 'reviewed.execution')
    if not isinstance(review['independent_scope'], str) or not review['independent_scope'].strip():
        raise ValueError('actual independent evidence scope required')
    shared.keys(value['qualification_pointers'], POINTERS, 'qualification pointers')
    if not success(value['qualification_success']):
        raise ValueError('qualified upstream result required')
    expected = {'result': value['qualification_success'], 'revision': TOOL['revision'],
                'source_sha256': TOOL['source_sha256'], 'runtime_abi': 16,
                'route_sha256': value['route']['source_route_sha256'],
                'module_manifest_sha256': loaded['reemission_proof']['new_manifest']['sha256']}
    expected.update({role + '_sha256': value['files'][role]['sha256']
                     for role in REF_ROLES | (REVIEW_ROLES - {'upstream_qualification'})})
    for role, pointer in value['qualification_pointers'].items():
        assert_exact(expected[role], shared.at(loaded['upstream_qualification'], pointer), 'upstream.' + role)
    shared.keys(value['success_bindings'], REVIEW_ROLES - {'upstream_qualification'}, 'evidence success')
    for role, binding in value['success_bindings'].items():
        shared.keys(binding, {'pointer', 'value'}, 'success binding')
        if not success(binding['value']):
            raise ValueError('each reviewed qualification must explicitly pass')
        assert_exact(binding['value'], shared.at(loaded[role], binding['pointer']), role + '.passed')
    for role in REVIEW_ROLES:
        for field in ('evidence_sha256', 'actual_hashed_artifacts', 'artifacts', 'tool_bindings'):
            if field not in loaded[role]:
                continue
            bindings = loaded[role][field]
            if not isinstance(bindings, dict):
                raise ValueError('reviewed artifacts must be a path/hash map')
            for artifact, digest in bindings.items():
                target = Path(artifact)
                prior.file_hash(target if target.is_absolute() else paths[role].parent / target, digest, hashes)
    contract = loaded['tool_contract']
    assert_exact(16, contract['runtime_abi'], 'official_contract.abi')
    assert_exact(1, contract['descriptor_schema'], 'official_contract.schema')
    for key in ('revision', 'source_sha256'):
        assert_exact(TOOL[key], contract['tool_identity'][key], 'official_contract.' + key)
    baseline = loaded['baseline_qualification']
    assert_exact(True, baseline['passed'], 'frozen15.passed')
    assert_exact(previous.TOOL, baseline['tool'], 'frozen15.tool')
    for role in BASE_ROLES - {'baseline_qualification'}:
        assert_exact(value['files'][role]['sha256'], baseline['evidence_sha256'][str(paths[role])], 'frozen15.' + role)
    return value, loaded, paths, hashes


def diagnostic(value, ticks, status=False):
    """Validate in place without dropping the newly exposed diagnostic."""
    accepted = value['unknown_commands'] if status else value['scsi']['unknown_commands']
    return validate_cd_unknown(value['cd_unknown'], accepted, observed_ticks=ticks)


def run_projection(receipt, run, timing, mode, desktop):
    run = copy.deepcopy(unwrap_execution(run, receipt['binary_sha256']))
    assert_exact('dev_quit', run['stop'], 'runner.stop')
    prior.source_identity(run, 'runner')
    _, counts = prior.tiers(run, 'runner', blocks_required=True)
    if counts['native'] == 0:
        raise ValueError('actual positive native execution required')
    diagnostic(run, run['ticks'])
    if mode == 'off' and 'audio_output' in run:
        raise ValueError('off runner must omit audio_output')
    raw = run.pop('audio_output', None)
    core = audio_core(raw, timing, mode, desktop)
    if timing == 'gear' and mode == 'on':
        gear_source_clock(core, run['ticks'], 'runner')
    assert_exact(core, receipt['audio_contract']['validated_output'], 'runner.validated_output')
    if desktop:
        presentation = validate_desktop(run.pop('desktop'), 94800)
        assert_exact(presentation, receipt['desktop_contract']['presentation'], 'runner.presentation')
        if mode == 'on':
            assert_exact(raw, receipt['desktop_contract']['audio_output'], 'runner.desktop_audio')
    if 'code_capture_window' in run:
        raise ValueError('ABI16 matrix must be capture-free')
    for field, expected in (('enabled', True), ('memory_write_enabled', True),
                            ('memory_write_requests', 709), ('memory_bytes_changed', 723)):
        assert_exact(expected, run['development'][field], 'runner.original_assists.' + field)
    port = run['development'].pop('port')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('actual bounded development port required')
    return run, core


def status_projection(state, timing, mode, desktop, checkpoint):
    if not isinstance(state, dict) or not set(state) <= {'frame', 'ticks', 'paused', 'local_paused', 'host', 'id', 'ok'}:
        raise ValueError('unknown checkpoint schema field')
    prior.source_identity(state['host'], 'checkpoint', status=True)
    diagnostic(state['host'], state['ticks'], status=True)
    projected = project_status(state)
    raw = projected['host'].pop('audio_output', None)
    if mode == 'off' and 'audio_output' in state['host']:
        raise ValueError('off checkpoint must omit audio_output')
    core = audio_core(raw, timing, mode, desktop, checkpoint)
    if timing == 'gear' and mode == 'on':
        gear_source_clock(core, state['ticks'], 'checkpoint')
    return projected, core


def different_paths(left, right, path=''):
    """Report every cross-ABI difference, with type-exact comparison."""
    if type(left) is not type(right):
        return [path or '/']
    if isinstance(left, dict):
        result = []
        for key in sorted(set(left) | set(right)):
            child = path + '/' + str(key).replace('~', '~0').replace('/', '~1')
            result += ([child] if key not in left or key not in right else different_paths(left[key], right[key], child))
        return result
    if isinstance(left, list):
        if len(left) != len(right):
            return [path or '/']
        return [child for index, (a, b) in enumerate(zip(left, right))
                for child in different_paths(a, b, path + '/' + str(index))]
    return [] if left == right else [path or '/']


def without_validated_cd(value, status=False):
    """Only the declared, independently checked addition crosses ABI15."""
    result = copy.deepcopy(value)
    host = result['host'] if status else result
    ticks = result['ticks']
    diagnostic(host, ticks, status=status)
    host.pop('cd_unknown')
    return result


def bound_wav(receipt, path):
    """The actual WAV must be both the recorded output and argv destination."""
    expected = (path.parent / 'audio.wav').resolve(strict=True)
    for recorded in (receipt['audio_contract']['wav_path'], shared.option(receipt['command'], '--audio-out')):
        target = Path(recorded)
        if not target.is_absolute():
            cwd = Path(receipt['launch_cwd'])
            if not cwd.is_absolute():
                raise ValueError('relative WAV requires actual absolute launch_cwd')
            target = cwd / target
        assert_exact(expected, target.resolve(strict=True), 'WAV.actual_argv_destination')


def bound_command(receipt, hashes):
    """Resolve only known file arguments through the recorded launch cwd."""
    command = generated_command(receipt)
    positions = [1] + [command.index(flag) + 1 for flag in
                      ('--bios', '--toc', '--disc', '--libchdr', '--input-script', '--bram') if flag in command]
    for index in positions:
        target = Path(command[index])
        if not target.is_absolute():
            cwd = Path(receipt['launch_cwd'])
            if not cwd.is_absolute():
                raise ValueError('relative argv requires actual absolute launch_cwd')
            target = cwd / target
        target = target.resolve(strict=True)
        digest = receipt['input_sha256'][str(target)]
        prior.file_hash(target, digest, hashes)
        command[index] = str(target)
    return command


def qualify_abi16(legacy_receipt, gear_receipt, off_receipt, expectation_path):
    expectation, references, reference_paths, hashes = load_expectation(expectation_path)
    paths = [Path(p).resolve(strict=True) for p in (legacy_receipt, gear_receipt, off_receipt)]
    live_config = tomllib.loads(Path(read_json(paths[0])['project_descriptor']).read_text(encoding='utf-8'))
    live_before = live_tool(live_config, read_json(paths[0])['project_descriptor'])
    receipts = [read_json(path) for path in paths] + [references[timing + '_receipt'] for timing in ('legacy', 'gear')]
    timings, modes, packaged = ['legacy', 'gear', 'gear', 'legacy', 'gear'], ['on', 'on', 'off', 'on', 'on'], [True] * 3 + [False] * 2
    runs, cores, modules = [], [], []
    route, protected_inputs, original_command = None, None, None
    for index, (receipt, timing, mode, desktop) in enumerate(zip(receipts, timings, modes, packaged)):
        if index < 3:
            path = prior.file_hash(paths[index], sha256(paths[index]), hashes)
            raw_path = prior.file_hash(path.parent / 'run.stdout', sha256(path.parent / 'run.stdout'), hashes)
        else:
            path, raw_path = reference_paths[timing + '_receipt'], reference_paths[timing + '_run']
        receipt_contract(receipt, timing, mode, desktop)
        for key in ROUTE:
            assert_exact(expectation['route'][key], receipt[key], 'retained.' + key)
        binary = prior.file_hash(receipt['command'][0], receipt['binary_sha256'], hashes)
        assert_exact(receipt['binary_sha256'], receipt['input_sha256'][str(binary)], 'bound.command_executable')
        for name, digest in receipt['input_sha256'].items():
            prior.file_hash(name, digest, hashes)
        protected = receipt['input_sha256'].copy()
        protected.pop(str(binary))
        if index == 0:
            protected_inputs, original_command = protected, bound_command(receipt, hashes)
            route_path = prior.file_hash(receipt['source_route'], receipt['source_route_sha256'], hashes)
            route = read_json(route_path)
        else:
            assert_exact(protected_inputs, protected, 'protected_inputs')
            assert_exact(original_command, bound_command(receipt, hashes), 'original_guest_command')
        assert_exact(route['initial_command'], receipt['source_command'], 'original_source_command')
        assert_exact(709, receipt['memory_edits_replayed'], 'original_assist_count')
        assert_exact(94800, receipt['final_status']['frame'], 'full_route_frames')
        assert_exact(39, len(receipt['images']), 'all_route_images')
        assert_exact([x['frame'] for x in route['checkpoints']], [x['frame'] for x in receipt['images']], 'all_route_image_frames')
        modules.append(bind_descriptor(receipt, timing, mode, hashes, desktop=desktop))
        if mode == 'on':
            bound_wav(receipt, path)
            shared.wav(receipt, path, 48000, hashes, artifact=reference_paths[timing + '_wav'] if index >= 3 else None)
        elif (path.parent / 'audio.wav').exists():
            raise ValueError('off run must not create WAV')
        run, core = run_projection(receipt, read_json(raw_path), timing, mode, desktop)
        runs.append(run)
        cores.append(core)
    for run in runs[1:]:
        assert_exact(runs[0], run, 'ABI16.all_guest_runner_and_native_tiers')
    for receipt in receipts[1:]:
        assert_exact(receipts[0]['images'], receipt['images'], 'ABI16.all_images')
    for candidate, reference in ((0, 3), (1, 4)):
        assert_exact(cores[reference], cores[candidate], 'ABI16.reference.exact_pcm')
        assert_exact(receipts[reference]['audio_contract']['wav_sha256'], receipts[candidate]['audio_contract']['wav_sha256'], 'ABI16.reference.exact_wav')
    for module in modules[1:]:
        assert_exact(modules[0][2], module[2], 'ABI16.all_same_module')
    measurements, new_states = [], {timing: [] for timing in ('legacy', 'gear')}
    for field in ('checkpoint_status',) + ENDPOINTS:
        groups = [receipt[field] if field == 'checkpoint_status' else [receipt[field]] for receipt in receipts]
        for group in groups:
            assert_exact(39 if field == 'checkpoint_status' else 1, len(group), 'complete.' + field)
        if field == 'checkpoint_status':
            for group in groups:
                assert_exact([x['frame'] for x in route['checkpoints']], [x['frame'] for x in group], 'checkpoint.frames')
        for states in zip(*groups):
            guests, outputs = [], []
            for state, timing, mode, desktop in zip(states, timings, modes, packaged):
                guest, core = status_projection(state, timing, mode, desktop, field == 'checkpoint_status')
                guests.append(guest)
                outputs.append(core)
            for guest in guests[1:]:
                assert_exact(guests[0], guest, field + '.all_guest_native_source_cd')
            compare = shared.no_wav if field == 'checkpoint_status' else lambda value: value
            for candidate, reference in ((0, 3), (1, 4)):
                assert_exact(compare(outputs[reference]), compare(outputs[candidate]), field + '.exact_pcm')
            if field != 'checkpoint_status':
                for run, guest, core, output in zip(runs, guests, cores, outputs):
                    assert_exact(core, output, field + '.runner_audio')
                    assert_exact(run['cd_unknown'], guest['host']['cd_unknown'], field + '.runner_cd')
                    assert_exact({'write_enabled': True, 'write_requests': 709, 'bytes_changed': 723}, guest['host']['debug_memory'], field + '.original_assists')
            for timing, index in (('legacy', 0), ('gear', 1)):
                new_states[timing].append((field, guests[index], outputs[index]))
            measurements.append({'field': field, 'frame': states[0]['frame'], 'legacy_pcm': outputs[0],
                                 'gear_pcm': outputs[1], 'cd_unknown': guests[0]['host']['cd_unknown'], 'off_pcm_absent': outputs[2] is None})
    conservation, old_modules = {}, []
    for timing, candidate in (('legacy', 0), ('gear', 1)):
        old = references['baseline_' + timing + '_receipt']
        path = reference_paths['baseline_' + timing + '_receipt']
        previous.receipt_contract(old, timing, 'on')
        protected = old['input_sha256'].copy()
        protected.pop(old['command'][0])
        assert_exact(protected_inputs, protected, 'baseline15.protected_inputs')
        assert_exact(original_command, bound_command(old, hashes), 'baseline15.original_guest_command')
        assert_exact(route['initial_command'], old['source_command'], 'baseline15.original_source_command')
        assert_exact(709, old['memory_edits_replayed'], 'baseline15.original_assists')
        for key in ROUTE:
            assert_exact(expectation['route'][key], old[key], 'baseline15.' + key)
        old_modules.append(previous.bind_descriptor(old, timing, 'on', hashes))
        for name, digest in old['input_sha256'].items():
            prior.file_hash(name, digest, hashes)
        shared.wav(old, path, 48000, hashes, artifact=reference_paths['baseline_' + timing + '_wav'])
        old_run, old_core = previous.run_projection(old, references['baseline_' + timing + '_run'], timing, 'on', True, hashes)
        guest_diff = different_paths(old_run, without_validated_cd(runs[candidate]))
        observations = []
        for field, guest, core in new_states[timing]:
            old_group = old[field] if field == 'checkpoint_status' else [old[field]]
            # Consume each checkpoint exactly once rather than matching by value.
            offset = sum(1 for item in observations if item['field'] == field)
            old_guest, old_output = previous.status_projection(old_group[offset], timing, 'on', True, field == 'checkpoint_status')
            observations.append({'field': field, 'frame': guest['frame'],
                                 'guest_differences': different_paths(old_guest, without_validated_cd(guest, status=True)),
                                 'pcm_differences': different_paths(old_output, core)})
        assert_exact(39, len(old['checkpoint_status']), 'baseline15.complete_checkpoints')
        conservation[timing] = {'all_guest_native_source_exact': not guest_diff and all(not item['guest_differences'] for item in observations),
                               'all_pcm_exact': old_core == cores[candidate] and all(not item['pcm_differences'] for item in observations),
                               'all_images_exact': old['images'] == receipts[candidate]['images'],
                               'runner_guest_differences': guest_diff, 'runner_pcm_differences': different_paths(old_core, cores[candidate]),
                               'image_differences': different_paths(old['images'], receipts[candidate]['images']),
                               'wav_exact': old['audio_contract']['wav_sha256'] == receipts[candidate]['audio_contract']['wav_sha256'],
                               'observations': observations}
    assert_exact(old_modules[0][2], old_modules[1][2], 'baseline15.same_module')
    regeneration = regenerated_module(old_modules[0], modules[0])
    check_reemission_proof(references['reemission_proof'], old_modules[0], modules[0], regeneration, hashes)
    assert_exact(live_before, live_tool(live_config, receipts[0]['project_descriptor']), 'live16tool.after')
    for path, digest in hashes.items():
        if sha256(path) != digest:
            raise ValueError('evidence changed during ABI16 qualification: ' + path)
    return {'schema': 1, 'kind': 'ys3-abi16-matrix-qualification', 'passed': True, 'tool': TOOL,
            'legacy_exact_new_headless_reference': True, 'gear_exact_new_headless_reference': True,
            'gear_timing_bridge': {'candidate_argv': 'default-omitted', 'candidate_descriptor': 'default-omitted',
                                   'headless_argv': 'explicit-gear' if '--audio-timing' in receipts[4]['command'] else 'default-omitted',
                                   'headless_descriptor': 'explicit-gear' if 'audio_timing' in modules[4][0]['runtime'] else 'default-omitted'},
            'off_exact_gear_guest_and_pcm_absent': True, 'all_cd_unknown_fields_validated_and_exact': True,
            'images': 39, 'checkpoint_states': 39, 'endpoint_states': 3, 'frames': 94800, 'memory_edits_replayed': 709,
            'native_counts': {key: runs[0][key] for key in ('native_steps', 'interpreter_steps', 'native_block_steps', 'interpreter_block_steps', 'guard_misses')},
            'reemission': regeneration, 'abi15_conservation': conservation, 'measurements': measurements,
            'final_audio': {'legacy': cores[0], 'gear': cores[1], 'off': None},
            'reviewed_binding': expectation['reviewed_binding'], 'evidence_sha256': hashes,
            'scope': 'Finite assisted hybrid route; all exposed ABI16 guest/source/CD fields match separately frozen headless routes. Cross-ABI15 differences are reported independently. CD origin is the last CPU latch write supplying the initial CDB byte before its first ACK, not retirement/ACK context. The explicit gear-good response remains compatibility behavior; REQUEST SENSE remains unsupported. No new native coverage, independent retail mix, listening, hardware, reset-boot, persistence or campaign claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('legacy-receipt', 'gear-receipt', 'off-receipt', 'expectation', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('qualification output must be new')
    result, failure = {'passed': False}, None
    try:
        result = qualify_abi16(args.legacy_receipt, args.gear_receipt, args.off_receipt, args.expectation)
    except (OSError, ValueError, RuntimeError, KeyError, IndexError, TypeError, wave.Error, subprocess.SubprocessError) as error:
        result.update(error=repr(error))
        failure = error
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    if failure:
        raise failure
    print('PASS: ABI16 legacy/default Gear/off matrix; ' + str(args.out))


if __name__ == '__main__':
    main()
