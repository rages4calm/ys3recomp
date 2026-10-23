"""Schema-2 qualification of a raw bridge and a finite opt-in DSP profile.

No schema-1 audio-accuracy allowance is inherited. The original guest work and
raw source PCM must remain exact; processed PCM must match a pinned new route.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re
import tomllib
import wave

if __package__:
    from . import dsp_contract as dsp
    from .desktop_contract import validate_desktop, validate_package_proof
    from .package_checks import verify_package
    from .qualify_coverage import assert_exact, read_json
    from .replay_route import (project_status, sha256, unwrap_execution,
                               validate_project_binding, validate_project_outputs)
else:
    import dsp_contract as dsp
    from desktop_contract import validate_desktop, validate_package_proof
    from package_checks import verify_package
    from qualify_coverage import assert_exact, read_json
    from replay_route import (project_status, sha256, unwrap_execution,
                              validate_project_binding, validate_project_outputs)

RAW = {'profile': 'raw', 'sample_rate': 44100}
FILTERED = {'profile': 'filtered', 'sample_rate': 48000}
ROUTE = {'source_route_sha256', 'source_binary_sha256', 'initial_bram_sha256'}
FILES = {'run', 'receipt', 'wav', 'upstream_qualification', 'independent_gear'}
POINTERS = {'result', 'tool_revision', 'source_sha256', 'runtime_abi', 'route_sha256',
            'profile', 'sample_rate', 'run_sha256', 'receipt_sha256', 'wav_sha256', 'independent_gear_sha256'}
WAV_METADATA = {'wav_frames', 'wav_truncated'}


def keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(label + ': missing or unknown schema field')


def at(value, pointer):
    if not isinstance(pointer, str) or not pointer.startswith('/'):
        raise ValueError('explicit JSON pointer required')
    for token in pointer[1:].split('/'):
        if re.search(r'~(?![01])', token):
            raise ValueError('invalid JSON pointer escape')
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) and token.isdigit() else value[token]
    return value


def digest(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('exact lowercase SHA256 required')


def expectation(path):
    value = read_json(path)
    keys(value, {'schema', 'kind', 'tool', 'route', 'selection', 'wav_frame_limit', 'raw_bridge',
                 'files', 'reviewed_binding', 'qualification_pointers', 'qualification_success',
                 'gear_pointers', 'gear_success'}, 'DSP expectation')
    if type(value['schema']) is not int or value['schema'] != 2 or value['kind'] != 'ys3-reviewed-dsp-profile':
        raise ValueError('only the distinct schema-2 DSP expectation is accepted')
    keys(value['tool'], {'revision', 'source_sha256', 'runtime_abi'}, 'tool')
    tool = value['tool']
    if (not isinstance(tool['revision'], str) or not re.fullmatch(r'[0-9a-f]{40}', tool['revision'])
            or type(tool['runtime_abi']) is not int or tool['runtime_abi'] != 13):
        raise ValueError('exact reviewed tool revision and ABI 13 required')
    digest(tool['source_sha256'])
    keys(value['route'], ROUTE, 'route')
    for item in value['route'].values():
        digest(item)
    assert_exact(FILTERED, value['selection'], 'selection')
    dsp.selection('on', 'filtered', 48000, value['wav_frame_limit'])
    if value['wav_frame_limit'] is None:
        raise ValueError('bounded processed WAV required')
    keys(value['raw_bridge'], {'receipt_sha256', 'run_sha256', 'wav_sha256'}, 'raw bridge')
    for item in value['raw_bridge'].values():
        digest(item)
    file_roles = set(value['files']) if isinstance(value['files'], dict) else set()
    if not FILES <= file_roles or not file_roles <= FILES | {'raw_upstream_qualification'}:
        raise ValueError('missing or unknown reference artifact role')
    for binding in value['files'].values():
        keys(binding, {'path', 'sha256'}, 'reference artifact')
        if not isinstance(binding['path'], str) or not binding['path']:
            raise ValueError('reference artifact path required')
        digest(binding['sha256'])
    review = value['reviewed_binding']
    keys(review, {'qualified', 'tool', 'route', 'selection', 'execution', 'raw_bridge',
                  'evidence_sha256', 'independent_scope'}, 'reviewed binding')
    if review['qualified'] is not True or not isinstance(review['independent_scope'], str) or not review['independent_scope'].strip():
        raise ValueError('qualified reviewed evidence and its actual independent scope required')
    for key in ('tool', 'route', 'selection', 'raw_bridge'):
        assert_exact(value[key], review[key], 'reviewed.' + key)
    assert_exact({'tier': 'hybrid', 'audio': 'on', 'raw_bridge_host': 'packaged-desktop',
                  'candidate_host': 'packaged-desktop', 'reference_host': 'headless'}, review['execution'], 'reviewed.execution')
    assert_exact({role: item['sha256'] for role, item in value['files'].items()}, review['evidence_sha256'], 'reviewed.evidence_sha256')
    keys(value['qualification_pointers'], POINTERS, 'qualification pointers')
    keys(value['gear_pointers'], {'result', 'source_sha256', 'runtime_abi'}, 'independent pointers')
    for key in ('qualification_success', 'gear_success'):
        if value[key] is not True and value[key] not in ('pass', 'passed', 'qualified'):
            raise ValueError('explicit qualified success value required')
    hashes = {str(path.resolve()): sha256(path)}
    loaded = {}
    for role, binding in value['files'].items():
        target = Path(binding['path'])
        target = (target if target.is_absolute() else path.parent / target).resolve(strict=True)
        if not target.is_file() or sha256(target) != binding['sha256']:
            raise ValueError('reference artifact hash mismatch: ' + role)
        hashes[str(target)] = binding['sha256']
        loaded[role] = target if role == 'wav' else read_json(target)
    bindings = {'result': value['qualification_success'], 'tool_revision': tool['revision'],
                'source_sha256': tool['source_sha256'], 'runtime_abi': 13,
                'route_sha256': value['route']['source_route_sha256'], 'profile': 'filtered', 'sample_rate': 48000}
    bindings.update({role + '_sha256': value['files'][role]['sha256'] for role in ('run', 'receipt', 'wav', 'independent_gear')})
    for role, pointer in value['qualification_pointers'].items():
        assert_exact(bindings[role], at(loaded['upstream_qualification'], pointer), 'upstream_qualification.' + role)
    independent = {'result': value['gear_success'], 'source_sha256': tool['source_sha256'], 'runtime_abi': 13}
    for role, pointer in value['gear_pointers'].items():
        assert_exact(independent[role], at(loaded['independent_gear'], pointer), 'independent_qualification.' + role)
    return value, loaded, hashes


def option(command, flag):
    if command.count(flag) != 1 or command.index(flag) + 1 >= len(command):
        raise ValueError('one explicit argument required: ' + flag)
    return command[command.index(flag) + 1]


def audio_selection(receipt, chosen, label, legacy=False):
    actual = receipt.get('audio_selection')
    if actual is None and legacy:
        actual = RAW
    assert_exact(chosen, actual, label + '.audio_selection')
    command = receipt['command']
    if not isinstance(command, list) or len(command) < 8 or command[7] != 'hybrid' or option(command, '--audio-output') != 'on':
        raise ValueError(label + ': explicit hybrid/audio-on command required')
    for flag, expected in (('--audio-profile', chosen['profile']), ('--audio-rate', str(chosen['sample_rate']))):
        if flag in command:
            assert_exact(expected, option(command, flag), label + '.' + flag)
        elif not legacy:
            raise ValueError(label + ': both explicit DSP profile and rate required')


def identity(receipt, tool, label):
    value = receipt['tool_identity']
    assert_exact(value, receipt['tool_identity_after'], label + '.tool_identity_after')
    for key in ('revision', 'runtime_abi'):
        assert_exact(tool[key], value[key], label + '.tool.' + key)
    for key in ('revision', 'source_sha256'):
        assert_exact(tool[key], value['shared_source_identity'][key], label + '.source.' + key)
    if value.get('tracked_source_clean') is not True:
        raise ValueError(label + ': clean verified source required')


def clean_receipt(receipt, chosen, label, headless=False, legacy=False):
    if receipt.get('passed') is not True or type(receipt.get('exit_code')) is not int or receipt['exit_code'] != 0:
        raise ValueError(label + ': passed clean-exit replay required')
    audio = receipt['audio_contract']
    if type(audio.get('runtime_abi')) is not int or audio['runtime_abi'] != 13 or audio.get('mode') != 'on' or audio.get('headless_pcm_only') is not headless:
        raise ValueError(label + ': known ABI-13 host/audio contract required')
    audio_selection(receipt, chosen, label, legacy)
    if headless:
        if any(flag in receipt['command'] for flag in ('--hidden', '--unthrottled')):
            raise ValueError('headless reference contains desktop-only flags')
        return
    proof = receipt['desktop_contract']
    for key in ('packaged', 'hidden', 'unthrottled', 'working_directory_initially_empty', 'working_directory_finally_empty'):
        if proof.get(key) is not True:
            raise ValueError(label + ': packaged proof required: ' + key)
    for flag in ('--hidden', '--unthrottled'):
        assert_exact('on', option(receipt['command'], flag), label + '.' + flag)
    validate_package_proof(proof, receipt['binary_sha256'])
    assert_exact(proof['package_before'], proof['package_after'], label + '.package_after')
    assert_exact(proof['package_before']['binary'], receipt['command'][0], label + '.package_binary')
    if receipt.get('shared_project_run_used') is not False or receipt.get('project_execution_mode') != 'shared-verify-then-consumer-route':
        raise ValueError(label + ': official verify/consumer execution mode required')
    assert_exact(receipt['project_verification_before'], receipt['project_verification_after'], label + '.verification_after')
    if receipt['project_verification_before'].get('verified') is not True:
        raise ValueError(label + ': official project verification required')
    assert_exact(receipt['project_output_files_before'], receipt['project_output_files_after'], label + '.outputs_after')
    assert_exact(proof['package_before']['output_files'], receipt['project_output_files_before'], label + '.package_outputs')


def descriptor(receipt, chosen, tool, hashes, label):
    path = Path(receipt['project_descriptor']).resolve(strict=True)
    if sha256(path) != receipt['project_descriptor_sha256']:
        raise ValueError(label + ': descriptor hash changed')
    hashes[str(path)] = receipt['project_descriptor_sha256']
    config = tomllib.loads(path.read_text(encoding='utf-8'))
    if type(config.get('schema')) is not int or config['schema'] != 1:
        raise ValueError(label + ': descriptor schema 1 required')
    for key in ('revision', 'source_sha256', 'runtime_abi'):
        assert_exact(tool[key], config['tool'][key], label + '.descriptor.tool.' + key)
    runtime = config['runtime']
    if runtime.get('audio') != 'on' or runtime.get('tier') != 'hybrid':
        raise ValueError(label + ': descriptor must select hybrid/audio on')
    declared = dsp.selection('on', runtime.get('audio_profile'), runtime.get('audio_rate')) or RAW
    assert_exact(chosen, declared, label + '.descriptor.selection')
    build_path = Path(receipt['project_build']).resolve(strict=True) / 'build-receipt.json'
    if sha256(build_path) != receipt['project_build_receipt_sha256']:
        raise ValueError(label + ': build receipt hash changed')
    hashes[str(build_path)] = receipt['project_build_receipt_sha256']
    built = read_json(build_path)
    binding = validate_project_binding(built, receipt['project_verification_before'])
    assert_exact(receipt['project_descriptor_sha256'], binding['descriptor_sha256'], label + '.build_descriptor')
    for key in ('revision', 'source_sha256'):
        assert_exact(tool[key], binding['tool'][key], label + '.build_tool.' + key)
    outputs = validate_project_outputs(built, Path(receipt['command'][0]))
    assert_exact(receipt['project_output_files_before'], outputs, label + '.actual_outputs')
    for name, expected in outputs.items():
        hashes[str(Path(receipt['command'][0]).parent / name)] = expected
    assert_exact(receipt['desktop_contract']['package_before'], verify_package(built, Path(receipt['command'][0])), label + '.actual_package')


def wav(receipt, path, rate, hashes, artifact=None):
    audio = receipt['audio_contract']
    target = Path(audio['wav_path']).resolve(strict=True) if artifact is None else artifact
    if artifact is None and target != (path.parent / 'audio.wav').resolve(strict=True):
        raise ValueError('WAV must be the replay output bound by its receipt')
    actual = sha256(target)
    assert_exact(audio['wav_sha256'], actual, 'wav.sha256')
    hashes[str(target)] = actual
    try:
        with wave.open(str(target), 'rb') as stream:
            geometry = (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes())
    except (wave.Error, EOFError) as error:
        raise ValueError('invalid bounded PCM WAV') from error
    frames = audio['validated_output']['wav_frames']
    assert_exact((2, 2, rate, frames), geometry, 'wav.geometry')
    assert_exact(44 + 4 * frames, target.stat().st_size, 'wav.byte_geometry')
    assert_exact(target.stat().st_size, audio['wav_bytes'], 'wav.bytes')


def no_wav(core):
    return {key: copy.deepcopy(value) for key, value in core.items() if key not in WAV_METADATA}


def audio(value, chosen, limit, reference=False, checkpoint=False):
    return (dsp.headless_audio(value, chosen, limit, allow_pending=checkpoint) if reference
            else dsp.desktop_audio(value, chosen, limit, allow_pending=checkpoint))


def guest_status(value, chosen, limit, reference=False, checkpoint=False):
    if not set(value) <= {'frame', 'ticks', 'paused', 'local_paused', 'host', 'id', 'ok'}:
        raise ValueError('unknown status schema field')
    projected = project_status(value)
    core = audio(projected['host'].pop('audio_output'), chosen, limit, reference, checkpoint)
    return projected, core


def qualify_dsp(baseline_receipt, raw_receipt, candidate_receipt, audio_expectation):
    """Public API accepts paths and always verifies the complete evidence graph."""
    paths = [Path(path).resolve(strict=True) for path in (baseline_receipt, raw_receipt, candidate_receipt)]
    manifest, reference, hashes = expectation(Path(audio_expectation).resolve(strict=True))
    receipts = [read_json(path) for path in paths] + [reference['receipt']]
    stdout_paths = [path.parent / 'run.stdout' for path in paths]
    runs = [read_json(path) for path in stdout_paths] + [reference['run']]
    hashes.update({str(path): sha256(path) for path in paths + stdout_paths})
    for role, path in (('receipt', paths[1]), ('run', stdout_paths[1])):
        assert_exact(manifest['raw_bridge'][role + '_sha256'], hashes[str(path)], 'raw_bridge.' + role)
    selected = [RAW, RAW, FILTERED, FILTERED]
    labels = ['old_raw', 'new_raw', 'processed', 'reference']
    limits = [receipt['audio_contract']['wav_frame_limit'] for receipt in receipts]
    if limits[0] is None:
        raise ValueError('retained raw bounded WAV required')
    assert_exact(limits[0], limits[1], 'raw_bridge.wav_frame_limit')
    assert_exact(manifest['wav_frame_limit'], limits[2], 'processed.wav_frame_limit')
    assert_exact(limits[2], limits[3], 'reference.wav_frame_limit')
    for index, (label, receipt, chosen) in enumerate(zip(labels, receipts, selected)):
        clean_receipt(receipt, chosen, label, headless=index == 3, legacy=index == 0)
        for key in ROUTE:
            assert_exact(manifest['route'][key], receipt[key], label + '.' + key)
        if index:
            identity(receipt, manifest['tool'], label)
        if index in (1, 2):
            descriptor(receipt, chosen, manifest['tool'], hashes, label)
        if index < 3:
            wav(receipt, paths[index], chosen['sample_rate'], hashes)
        else:
            wav(receipt, Path(audio_expectation), 48000, hashes, artifact=reference['wav'])
    assert_exact(receipts[0]['audio_contract']['wav_sha256'], receipts[1]['audio_contract']['wav_sha256'], 'raw_bridge.old_wav')
    assert_exact(manifest['raw_bridge']['wav_sha256'], receipts[1]['audio_contract']['wav_sha256'], 'raw_bridge.pinned_wav')
    assert_exact(receipts[3]['audio_contract']['wav_sha256'], receipts[2]['audio_contract']['wav_sha256'], 'processed.reference_wav')
    def protected(receipt):
        values = receipt['input_sha256'].copy()
        values.pop(receipt['command'][0], None)
        return values
    for receipt in receipts[1:]:
        for key in ('images', 'source_command', 'memory_edits_replayed'):
            assert_exact(receipts[0][key], receipt[key], 'retained.' + key)
        assert_exact(protected(receipts[0]), protected(receipt), 'retained.protected_inputs')
    projected_runs, final_audio, full_final_audio = [], [], []
    for index, (label, receipt, chosen, run) in enumerate(zip(labels, receipts, selected, runs)):
        run = copy.deepcopy(unwrap_execution(run, receipt['binary_sha256']))
        raw_audio = run.pop('audio_output')
        full_final_audio.append(copy.deepcopy(raw_audio))
        core = audio(raw_audio, chosen, limits[index], reference=index == 3)
        assert_exact(receipt['audio_contract']['validated_output'], core, label + '.validated_output')
        if index < 3:
            assert_exact(receipt['desktop_contract']['audio_output'], raw_audio, label + '.desktop_audio')
            presentation = validate_desktop(run.pop('desktop'), receipt['final_status']['frame'])
            assert_exact(receipt['desktop_contract']['presentation'], presentation, label + '.presentation')
        run['development'].pop('port', None)
        projected_runs.append(run)
        final_audio.append(core)
    for run in projected_runs[1:]:
        assert_exact(projected_runs[0], run, 'retained.guest_runner_and_tiers')
    assert_exact(final_audio[0], final_audio[1], 'raw_bridge.final_pcm')
    assert_exact(final_audio[2], final_audio[3], 'processed.reference_final_pcm')
    for core in final_audio[2:]:
        assert_exact(no_wav(final_audio[0]), dsp.raw_projection(core), 'processed.final_raw_projection')
    measurements = {label: {'final': core, 'full_final': full, 'checkpoints': [], 'endpoint_status': []}
                    for label, core, full in zip(labels, final_audio, full_final_audio)}
    for field in ('before_final_release', 'final_status', 'released_status', 'checkpoint_status'):
        groups = [receipt[field] if field == 'checkpoint_status' else [receipt[field]] for receipt in receipts]
        for group in groups[1:]:
            assert_exact(len(groups[0]), len(group), field + '.count')
        if field == 'checkpoint_status' and (not groups[0] or len(groups[0]) != len(receipts[0]['images'])):
            raise ValueError('complete retained checkpoint/image evidence required')
        for states in zip(*groups):
            outputs, guests = [], []
            for index, (state, chosen) in enumerate(zip(states, selected)):
                if set(state) != set(states[0]):
                    raise ValueError('missing or added status schema field')
                guest, core = guest_status(state, chosen, limits[index], index == 3, field == 'checkpoint_status')
                outputs.append(core)
                guests.append(guest)
                measurements[labels[index]]['checkpoints' if field == 'checkpoint_status' else 'endpoint_status'].append(
                    {'field': field, 'frame': state['frame'], 'audio': core,
                     'pending_output_frames': None if index == 3 else core['frames'] - state['host']['audio_output']['host']['submitted_frames']})
            for guest in guests[1:]:
                assert_exact(guests[0], guest, field + '.guest')
            compare = no_wav if field == 'checkpoint_status' else lambda value: value
            assert_exact(compare(outputs[0]), compare(outputs[1]), field + '.raw_bridge_pcm')
            assert_exact(compare(outputs[2]), compare(outputs[3]), field + '.processed_reference_pcm')
            for core in outputs[2:]:
                assert_exact(no_wav(outputs[0]), dsp.raw_projection(core), field + '.raw_projection')
            if field != 'checkpoint_status':
                for final, measured in zip(final_audio, outputs):
                    assert_exact(final, measured, field + '.final_audio')
    for path, expected in hashes.items():
        if sha256(path) != expected:
            raise ValueError('evidence changed during qualification: ' + path)
    result = {'schema': 2, 'kind': 'ys3-dsp-qualification', 'passed': True,
              'tool': manifest['tool'], 'selection': FILTERED, 'source_route_sha256': manifest['route']['source_route_sha256'],
              'raw_bridge_exact': True, 'processed_matches_new_reference': True,
              'raw_source_projection_exact': True, 'guest_and_native_tiers_exact': True,
              'measurements': measurements, 'images': len(receipts[0]['images']),
              'checkpoint_states': len(receipts[0]['checkpoint_status']),
              'memory_edits_replayed': receipts[0]['memory_edits_replayed'],
              'reviewed_binding': manifest['reviewed_binding'], 'evidence_sha256': hashes,
              'scope': 'Finite opt-in filtered-v1 48000 Hz route, unflushed 31-source-frame sinc64-q30-v1 latency. Raw 44100 Hz bridge/source PCM and all retained guest work stay exact. Gear filter-stage evidence and independent FIR vectors retain their declared scopes; neither is Gear resampler, listening, analog or hardware parity.'}
    for key in ('native_steps', 'interpreter_steps', 'native_block_steps', 'interpreter_block_steps', 'guard_misses'):
        result[key] = projected_runs[2][key]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-receipt', 'raw-receipt', 'candidate-receipt', 'audio-expectation', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('qualification output must be new')
    result, failure = {'schema': 2, 'passed': False}, None
    try:
        result = qualify_dsp(args.baseline_receipt, args.raw_receipt, args.candidate_receipt, args.audio_expectation)
    except (OSError, ValueError, RuntimeError, KeyError, IndexError, TypeError, wave.Error) as error:
        result.update(passed=False, error=repr(error))
        failure = error
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as output:
        output.write(json.dumps(result, indent=2) + '\n')
    if failure is not None:
        raise failure
    print('PASS: raw bridge, filtered PCM/reference and original guest work; ' + str(args.out))


if __name__ == '__main__':
    main()
