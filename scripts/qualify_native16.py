"""Qualify measured ABI16 native gains on a restored extended TCP/audio route.

Only validated retirement tiers may differ. Full guest/source/CD diagnostics,
Gear filtered48k PCM/WAV and raw suffix source/hit identities stay exact.
"""
from __future__ import annotations

import argparse
import copy
import importlib
import json
from pathlib import Path
import subprocess
import tempfile
import tomllib
import wave

if __package__:
    from . import qualify_abi16 as abi16
    from . import qualify_native_audio as prior
    from . import qualify_dsp as shared
    from . import merge_observations as merge
    from .qualify_coverage import assert_exact, read_json, TIER_FIELDS
    from .replay_route import (sha256, unwrap_execution, project_status, capture_start_proof,
                              finish_managed_capture, managed_capture_selection,
                              validate_project_binding, validate_project_outputs)
    from .expand_native import excluded_spans, audit_assist_source
    from .desktop_contract import validate_desktop, validate_package_proof
    from .package_checks import verify_package
else:
    import qualify_abi16 as abi16
    import qualify_native_audio as prior
    import qualify_dsp as shared
    import merge_observations as merge
    from qualify_coverage import assert_exact, read_json, TIER_FIELDS
    from replay_route import (sha256, unwrap_execution, project_status, capture_start_proof,
                             finish_managed_capture, managed_capture_selection,
                             validate_project_binding, validate_project_outputs)
    from expand_native import excluded_spans, audit_assist_source
    from desktop_contract import validate_desktop, validate_package_proof
    from package_checks import verify_package

TOOL, SELECTION = abi16.TOOL, abi16.GEAR
LEGACY, GEAR = abi16.LEGACY, abi16.GEAR
PREFIX_FRAME, PREFIX_IMAGES = 94800, 39
ENDPOINTS = prior.ENDPOINTS
PROVENANCE_ROLES = {'prefix_receipt', 'prefix_qualification', 'old_profile', 'new_profile',
                    'old_selection', 'new_selection', 'merge_manifest', 'merge_receipt'}
file_hash, nonnegative, source_identity = prior.file_hash, prior.nonnegative, prior.source_identity
tiers, compare_tiers = prior.tiers, prior.compare_tiers
RecordedPause = prior.RecordedPause
compare_capture_observations = prior.compare_capture_observations


def check_command(receipt, timing='gear', mode='on', desktop=True):
    command = receipt['command']
    if not isinstance(command, list) or len(command) < 8 or any(type(v) is not str for v in command):
        raise ValueError('complete recorded command required')
    assert_exact('hybrid', command[7], 'command.tier')
    for flag, value in (('--audio-output', 'on'), ('--audio-profile', 'filtered'), ('--audio-rate', '48000'),
                        ('--audio-frames', '1440000'), ('--hidden', 'on'), ('--unthrottled', 'on'),
                        ('--code-capture-start-frame', str(PREFIX_FRAME))):
        assert_exact(value, shared.option(command, flag), 'command.' + flag)
    if any(str(v).split('=', 1)[0] in ('--audio-timing', '--capture-start-frame') for v in command):
        raise ValueError('native16 requires packaged default Gear and the reviewed capture-start flag')
    shared.option(command, '--code-capture')
    shared.option(command, '--capture-limit')


def module_files(path, hashes):
    path = Path(path).resolve(strict=True)
    manifest = read_json(path)
    file_hash(path, sha256(path), hashes)
    assert_exact(1, manifest['schema'], 'module.schema')
    assert_exact(16, manifest['runtime_abi'], 'module.runtime_abi')
    units, headers = manifest['translation_units'], manifest['generated_headers']
    if not isinstance(units, list) or not 1 <= len(units) <= 512 or not isinstance(headers, list) or len(headers) != 1:
        raise ValueError('complete bounded partitioned module artifacts required')
    result, seen = {}, set()
    for entries, suffix in ((units, '.cpp'), (headers, '.hpp')):
        for item in entries:
            shared.keys(item, {'file', 'sha256'}, 'module artifact')
            name = item['file']
            if (type(name) is not str or Path(name).name != name or '/' in name or '\\' in name
                    or not name.endswith(suffix) or name.casefold() in seen):
                raise ValueError('unique direct module artifact name required')
            seen.add(name.casefold())
            target = path.parent / name
            if target.is_symlink():
                raise ValueError('module source symlink refused')
            result[name] = file_hash(target, item['sha256'], hashes)
    assert_exact(['full_mpr_snapshot', 'exact_source_bytes_per_instruction', 'instruction_deadline'], manifest['guards'], 'module.guards')
    assert_exact([{'start': 1069880, 'length': 6}], manifest['excluded_physical_ranges'], 'module.whole_six_byte_exclusion')
    nonnegative(manifest['excluded_observations'], 'module.excluded_identities')
    nonnegative(manifest['excluded_retired_hits'], 'module.excluded_hits')
    assert_exact(0, manifest['unsupported_observations'], 'module.unsupported')
    if nonnegative(manifest['native_instructions_emitted'], 'module.identities') == 0:
        raise ValueError('nonempty guarded native module required')
    return manifest, result

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
    selected = None if mode == 'off' else dict(SELECTION)
    assert_exact(selected, receipt.get('audio_selection'), 'audio_selection')
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


def validate_managed_capture(receipt, config, run, route, prefix_frame, tool, hashes, label):
    contract = receipt['capture_contract']
    shared.keys(contract, {'schema', 'runtime_abi', 'path', 'sha256', 'start_frame', 'capacity',
                          'start_proof', 'capture', 'observations', 'window', 'scope'}, label + '.capture_contract')
    if type(contract['schema']) is not int or contract['schema'] != 1 or contract['runtime_abi'] != 16:
        raise ValueError('reviewed managed-capture schema 1 ABI16 required')
    descriptor_directory = Path(receipt['project_descriptor']).resolve().parent
    source = verify_capture_tool(config, tool, descriptor_directory)
    selected = managed_capture_selection(route, contract['start_frame'], contract['capacity'])
    assert_exact(prefix_frame, selected['start_frame'], label + '.capture_prefix_boundary')
    command = receipt['command']
    for flag, expected in (('--code-capture-start-frame', str(prefix_frame)),
                           ('--capture-limit', str(selected['capacity'])), ('--code-capture', contract['path'])):
        assert_exact(expected, shared.option(command, flag), label + '.' + flag)
    path = file_hash(contract['path'], contract['sha256'], hashes)
    proof = contract['start_proof']
    shared.keys(proof, {'status_before', 'status', 'canonical_readback', 'retired_instructions'}, 'capture proof')
    replay = RecordedPause(proof)
    checked_proof = capture_start_proof(replay, selected)
    assert_exact(proof, checked_proof, label + '.fresh_canonical_pause_proof')
    if replay.reads != len(proof['canonical_readback']):
        raise ValueError('unexpected extra canonical readback evidence')
    prefixes = [s for s in receipt['checkpoint_status'] if s['frame'] == prefix_frame]
    if len(prefixes) != 1:
        raise ValueError('one explicit capture-prefix checkpoint required')
    for status in (proof['status_before'], proof['status']):
        projected, _ = status_projection(status, checkpoint=True)
        checkpoint, _ = status_projection(prefixes[0], checkpoint=True)
        assert_exact(checkpoint, projected, label + '.capture_proof_matches_prefix_checkpoint')
    rebuilt = finish_managed_capture(path, source, selected, proof, run, expected_runtime_abi=16)
    assert_exact(contract, rebuilt, label + '.capture_contract_revalidated')
    capture, actual_hash = merge.load_capture_api(source).load_capture(path)
    assert_exact(contract['sha256'], actual_hash, label + '.shared_raw_capture_hash')
    if capture['complete'] is not True or capture['dropped_instructions'] or capture['unreadable_instructions']:
        raise ValueError('capture must be complete without dropped or unreadable retirements')
    for field, hits in (('native_steps', 'native_hits'), ('interpreter_steps', 'interpreted_hits')):
        observed = sum(item[hits] for item in capture['observations'])
        if observed != run[field] - proof['status']['host'][field]:
            raise ValueError('capture tier hits do not conserve exact start/final retirement delta')
    # Retain the original temporary-code exclusions across both generated modules.
    spans = excluded_spans(route) if selected['canonical_bytes'] else ()
    module_binding = config['module']['manifest']
    raw_manifest_path = Path(module_binding['path'])
    manifest_path = raw_manifest_path if raw_manifest_path.is_absolute() else Path(receipt['project_descriptor']).parent / raw_manifest_path
    manifest = read_json(manifest_path)
    assert_exact([{'start': start, 'length': length} for start, length in spans],
                 manifest.get('excluded_physical_ranges', []), label + '.original_code_exclusions')
    audit_assist_source(capture, route, spans)
    for item in capture['observations']:
        for physical, byte in zip(item['physical'], item['data']):
            if physical in selected['canonical_bytes'] and byte != selected['canonical_bytes'][physical]:
                raise ValueError('capture contains temporary patched program bytes')
    # Recheck public source and raw bytes after invoking its actual loader.
    assert_exact(source, verify_capture_tool(config, tool, descriptor_directory), label + '.tool_after_capture')
    file_hash(path, contract['sha256'], hashes)
    return capture, {'path': str(path), 'sha256': actual_hash, 'start_frame': prefix_frame,
                     'capacity': selected['capacity'], 'window': copy.deepcopy(run['code_capture_window']),
                     'retired_instructions': capture['retired_instructions'], 'observations': len(capture['observations']),
                     'canonical_source_exclusions': [{'start': start, 'length': length} for start, length in spans]}



def verify_capture_tool(config, tool, descriptor_directory=None):
    assert_exact(TOOL, tool, 'reviewed.capture_tool')
    abi16.live_tool(config, Path(descriptor_directory or '.') / 'recorded-descriptor.toml')
    root = Path(config['tool']['path'])
    return (root if root.is_absolute() else Path(descriptor_directory or '.') / root).resolve(strict=True)


def status_projection(state, checkpoint=False):
    if type(state.get('frame')) is not int or type(state.get('ticks')) is not int or state['ticks'] < 0:
        raise ValueError('integer guest frame/ticks required')
    if state.get('paused') is not True or type(state.get('local_paused')) is not bool:
        raise ValueError('settled paused guest checkpoint required')
    return abi16.status_projection(state, 'gear', 'on', True, checkpoint)


def run_projection(receipt, raw, final_frame):
    run = copy.deepcopy(unwrap_execution(raw, receipt['binary_sha256']))
    assert_exact('dev_quit', run['stop'], 'runner.stop')
    source_identity(run, 'runner')
    abi16.diagnostic(run, run['ticks'])
    audio = run.pop('audio_output')
    core = abi16.audio_core(audio, 'gear', 'on', True)
    abi16.gear_source_clock(core, run['ticks'], 'runner')
    assert_exact(core, receipt['audio_contract']['validated_output'], 'runner.validated_output')
    assert_exact(audio, receipt['desktop_contract']['audio_output'], 'runner.recorded_audio')
    assert_exact(validate_desktop(run.pop('desktop'), final_frame), receipt['desktop_contract']['presentation'], 'runner.presentation')
    for field, expected in (('enabled', True), ('memory_write_enabled', True),
                            ('memory_write_requests', 709), ('memory_bytes_changed', 723)):
        assert_exact(expected, run['development'][field], 'runner.original_assists.' + field)
    port = run['development'].pop('port')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('bounded actual TCP port required')
    return run, core


def load_provenance(path, prefix_receipt, hashes):
    path = Path(path).resolve(strict=True)
    file_hash(path, sha256(path), hashes)
    value = read_json(path)
    shared.keys(value, {'schema', 'kind', 'tool', 'files'}, 'native16 provenance')
    assert_exact(1, value['schema'], 'provenance.schema')
    assert_exact('ys3-native16-profile-provenance', value['kind'], 'provenance.kind')
    assert_exact(TOOL, value['tool'], 'provenance.tool')
    shared.keys(value['files'], PROVENANCE_ROLES, 'provenance.files')
    paths, loaded = {}, {}
    for role, binding in value['files'].items():
        shared.keys(binding, {'path', 'sha256'}, 'provenance binding')
        target = Path(binding['path'])
        target = file_hash(target if target.is_absolute() else path.parent / target, binding['sha256'], hashes)
        paths[role] = target
        if role not in ('old_profile', 'new_profile'):
            loaded[role] = read_json(target)
    assert_exact(Path(prefix_receipt).resolve(strict=True), paths['prefix_receipt'], 'provenance.prefix_path')
    qualification = loaded['prefix_qualification']
    assert_exact(True, qualification['passed'], 'prefix.qualified')
    assert_exact(TOOL, qualification['tool'], 'prefix.tool')
    assert_exact(PREFIX_FRAME, qualification['frames'], 'prefix.frames')
    assert_exact(PREFIX_IMAGES, qualification['images'], 'prefix.images')
    for target in (paths['prefix_receipt'], paths['prefix_receipt'].parent / 'run.stdout', paths['prefix_receipt'].parent / 'audio.wav'):
        file_hash(target, qualification['evidence_sha256'][str(target)], hashes)
    return paths, loaded


def verify_emission(module, profile, profile_path, selection, route, tool):
    """Recompute exact guarded source using the actual pinned emitter."""
    config, manifest_path, manifest, artifacts = module
    api = merge.load_capture_api(tool)
    emitter = importlib.import_module(api.__package__ + '.emitter')
    if Path(emitter.__file__).resolve() != (Path(tool) / 'pcerecomp/emitter.py').resolve(strict=True):
        raise ValueError('emitter API origin differs from verified dependency')
    spans = excluded_spans(route)
    audit = audit_assist_source(profile, route, spans)
    with tempfile.TemporaryDirectory(prefix='ys3-native16-emission-') as temporary:
        output = Path(temporary) / 'native'
        rebuilt = emitter.emit_capture(profile, output, sha256(profile_path), exclude_ranges=spans,
                                       partition_size=manifest['partition_size'], single_unit=not manifest['partitioned'])
        assert_exact(manifest, rebuilt, 'actual_emitter.complete_manifest')
        for name, actual in artifacts.items():
            if actual.read_bytes() != (output / name).read_bytes():
                raise ValueError('module source differs from pinned guarded emitter: ' + name)
    expected = {'schema': 1, 'tool_identity': selection['tool_identity'], 'route_sha256': sha256(route['_path']),
                'raw_capture_sha256': sha256(profile_path), 'capture_runtime_abi': profile['runtime_abi'],
                'module_runtime_abi': 16, 'translation_units': len(manifest['translation_units']),
                'raw_observations': len(profile['observations']), 'raw_retired_instructions': profile['retired_instructions'],
                'raw_complete': True, 'excluded_physical_ranges': manifest['excluded_physical_ranges'],
                'excluded_observations': manifest['excluded_observations'], 'excluded_retired_hits': manifest['excluded_retired_hits'],
                'native_identities': manifest['native_instructions_emitted'], 'mpr_contexts': manifest['native_contexts'],
                'unsupported_observations': manifest['unsupported_observations'], 'assist_source_audit': audit,
                'expected_native_hits': profile['retired_instructions'] - manifest['excluded_retired_hits'],
                'execution_evidence': False,
                'scope': 'Complete observed profile emitted through upstream API with entire verified-restored temporary-code spans excluded. Original capture identity, completeness and hit totals are preserved. Unknown/unvisited code and excluded source remain hybrid.'}
    shared.identity({'tool_identity': selection['tool_identity'], 'tool_identity_after': selection['tool_identity']}, TOOL, 'emission.tool')
    assert_exact(54, selection['tool_identity']['shared_source_identity']['source_files'], 'emission.source_files')
    assert_exact(expected, selection, 'emission.selection_actual_profile_and_source')
    return {'profile_sha256': sha256(profile_path), 'manifest_sha256': sha256(manifest_path),
            'artifacts': len(artifacts), 'exact_pinned_emitter_source_and_guards': True,
            'identities': manifest['native_instructions_emitted'], 'mpr_contexts': manifest['native_contexts'],
            'excluded_identities': manifest['excluded_observations'], 'excluded_retired_hits': manifest['excluded_retired_hits'],
            'excluded_physical_ranges': manifest['excluded_physical_ranges']}


def verify_composition(paths, loaded, tool, baseline_capture, baseline_receipt_path, final_frame, hashes):
    manifest, entries, manifest_hashes = merge.read_manifest(paths['merge_manifest'])
    assert_exact(16, manifest['output_runtime_abi'], 'composed.output_format_abi')
    assert_exact(2, len(entries), 'composed.old_profile_plus_suffix')
    assert_exact(paths['old_profile'], entries[0][0], 'composed.original_profile_path')
    assert_exact({'start_frame': 0, 'end_frame': PREFIX_FRAME}, entries[0][1]['window'], 'composed.retained_profile_covered_extent')
    baseline_binding = {'path': str(baseline_receipt_path), 'sha256': sha256(baseline_receipt_path)}
    if baseline_binding not in entries[1][1]['evidence']:
        raise ValueError('suffix composition must bind the actual baseline capture receipt')
    assert_exact({'start_frame': PREFIX_FRAME, 'end_frame': final_frame}, entries[1][1]['window'], 'composed.actual_suffix_window')
    for target, digest in manifest_hashes.items():
        file_hash(target, digest, hashes)
    api = merge.load_capture_api(tool)
    captures = []
    for path, _ in entries:
        capture, digest = api.load_capture(path)
        file_hash(path, digest, hashes)
        captures.append(capture)
    assert_exact(13, captures[0]['runtime_abi'], 'composed.original_input_abi_retained')
    assert_exact(16, captures[1]['runtime_abi'], 'composed.suffix_input_abi_retained')
    compare_capture_observations(captures[1], baseline_capture)
    # Per-identity native/interpreted hits must also match the actual baseline;
    # composition must not borrow a candidate's improved tier attribution.
    assert_exact(captures[1], baseline_capture, 'composed.actual_baseline_suffix_raw_data')
    rebuilt, summary = merge.merge_captures(captures, 16, api.validate_capture)
    actual, digest = api.load_capture(paths['new_profile'])
    file_hash(paths['new_profile'], digest, hashes)
    assert_exact(rebuilt, actual, 'composed.exact_profile_and_original_tier_totals')
    receipt = loaded['merge_receipt']
    expected = {'schema': 1, 'kind': 'ys3-multi-run-observation-profile', 'tool_identity': receipt['tool_identity'],
                'tool_identity_after': receipt['tool_identity'], 'output_capture_runtime_abi': 16,
                'capture_sha256': digest, 'capture_bytes': paths['new_profile'].stat().st_size,
                'input_manifest': str(paths['merge_manifest']), 'input_manifest_sha256': sha256(paths['merge_manifest']),
                'inputs': [dict(path=str(path), sha256=sha256(path), epoch=epoch, **summary['input_epochs'][index])
                           for index, (path, epoch) in enumerate(entries)],
                'evidence_sha256': {str(path): digest for path, digest in manifest_hashes.items()},
                'profile_format_semantics': 'Output ABI names the composed observation format, not a single execution. Original input runtime ABI and hit tiers remain unchanged in each bound epoch.',
                'provenance_semantics': 'Epoch labels/windows are caller declarations retained verbatim and bound to evidence bytes; this composition does not independently verify their execution meaning.',
                **{key: value for key, value in summary.items() if key != 'input_epochs'}}
    shared.identity(receipt, TOOL, 'composition.tool')
    assert_exact(54, receipt['tool_identity']['shared_source_identity']['source_files'], 'composition.source_files')
    assert_exact(expected, receipt, 'composition.complete_receipt')
    return captures[0], actual, {'actual_composition_recomputed': True, 'old_capture_abi': 13, 'suffix_capture_abi': 16,
                                'composed_profile_format_abi': 16, 'single_execution_evidence': False,
                                'actual_baseline_suffix_identity_and_tier_hits_exact': True,
                                'new_source_identities': summary['new_identities_over_first_capture']}


def measured_gain(counts, prefix_counts, minimum):
    suffix_total = [counts[i]['total'] - prefix_counts[i]['total'] for i in (0, 1)]
    suffix_native = [counts[i]['native'] - prefix_counts[i]['native'] for i in (0, 1)]
    gain = counts[1]['native'] - counts[0]['native']
    suffix_gain = suffix_native[1] - suffix_native[0]
    if (min(suffix_total) <= 0 or suffix_total[0] != suffix_total[1]
            or any(native < 0 or native > total for native, total in zip(suffix_native, suffix_total))
            or gain < minimum or suffix_gain < minimum):
        raise ValueError('positive native gain required for both complete route and94800 suffix')
    return gain, suffix_gain, suffix_total


def bind_route_image(checkpoint, recipe, recipe_path, inputs, hashes):
    """Resolve an exact checkpoint only within its declared capture origins."""
    name = checkpoint['file']
    if type(name) is not str or not name:
        raise ValueError('checkpoint requires an explicit image filename')
    roots = [recipe_path.parent]
    for value in (checkpoint.get('source_capture_root'), recipe.get('source_capture_root')):
        if value:
            root = Path(value)
            roots.append(root if root.is_absolute() else recipe_path.parent / root)
    targets = set()
    for root in roots:
        target = root / name
        if target.is_file():
            target = target.resolve(strict=True)
            if inputs.get(str(target)) == checkpoint['png_sha256']:
                targets.add(target)
    if len(targets) != 1:
        raise ValueError('checkpoint image lacks one exact declared-origin/input binding: ' + name)
    return file_hash(targets.pop(), checkpoint['png_sha256'], hashes)


def qualify_native16(baseline_receipt, candidate_receipt, *, prefix_receipt, provenance, min_native_gain=1):
    if type(min_native_gain) is not int or min_native_gain < 1:
        raise ValueError('positive integer minimum native gain required')
    paths = [Path(p).resolve(strict=True) for p in (baseline_receipt, candidate_receipt)]
    receipts = [read_json(p) for p in paths]
    hashes = {str(p): sha256(p) for p in paths}
    provenance_paths, evidence = load_provenance(provenance, prefix_receipt, hashes)
    prefix = evidence['prefix_receipt']
    abi16.receipt_contract(prefix, 'gear', 'on')
    prefix_route_path = file_hash(prefix['source_route'], prefix['source_route_sha256'], hashes)
    prefix_route = read_json(prefix_route_path)
    route_path = file_hash(receipts[0]['source_route'], receipts[0]['source_route_sha256'], hashes)
    route = read_json(route_path)
    final_frame = route['last_status']['frame']
    if type(final_frame) is not int or final_frame <= PREFIX_FRAME:
        raise ValueError('new route must extend beyond94800')
    frames = [state['frame'] for state in receipts[0]['checkpoint_status']]
    if (any(type(f) is not int for f in frames) or frames != sorted(set(frames))
            or PREFIX_FRAME not in frames or not any(f > PREFIX_FRAME for f in frames)
            or len([f for f in frames if f <= PREFIX_FRAME]) != PREFIX_IMAGES):
        raise ValueError('all39 prefix checkpoints, explicit94800 and new suffix checkpoints required')
    assert_exact([c['frame'] for c in route['checkpoints']], frames, 'complete.route_checkpoints')
    view = lambda images: [{'frame': image['frame'], 'png_sha256': image['png_sha256']} for image in images]
    assert_exact(view(route['checkpoints']), view(receipts[0]['images']), 'actual_route.all_images')
    assert_exact(prefix_route['checkpoints'], route['checkpoints'][:PREFIX_IMAGES], 'original_prefix_checkpoint_bindings')
    for index, image in enumerate(route['checkpoints']):
        if index < PREFIX_IMAGES:
            bind_route_image(prefix_route['checkpoints'][index], prefix_route, prefix_route_path, prefix['input_sha256'], hashes)
        else:
            bind_route_image(image, route, route_path, receipts[0]['input_sha256'], hashes)
    assert_exact(prefix['images'], receipts[0]['images'][:PREFIX_IMAGES], 'retained39_prefix_images')
    assert_exact(PREFIX_IMAGES, len(prefix['checkpoint_status']), 'retained39_prefix_states')
    assert_exact(prefix_route['steps'], route['steps'][:len(prefix_route['steps'])], 'original_prefix_recipe')
    edits = [s for s in route['steps'] if 'memory_write' in s]
    assert_exact(709, len(edits), 'original_assist_transactions')
    assert_exact(723, sum(sum(a != b for a, b in zip(bytes.fromhex(s['memory_write']['expected']), bytes.fromhex(s['memory_write']['data']))) for s in edits), 'original_assist_changed_bytes')
    if any(s['frame'] > PREFIX_FRAME for s in edits):
        raise ValueError('new suffix must contain no memory edits')
    prefix_run, prefix_audio = run_projection(prefix, read_json(provenance_paths['prefix_receipt'].parent / 'run.stdout'), PREFIX_FRAME)
    _, frozen_prefix_counts = tiers(prefix_run, 'qualified_prefix_runner', blocks_required=True)
    configs, modules, runs, cores, captures, capture_reports = [], [], [], [], [], []
    for label, path, receipt in zip(('old', 'new'), paths, receipts):
        receipt_contract(receipt, 'gear', 'on')
        assert_exact(final_frame, receipt['final_status']['frame'], label + '.final_frame')
        assert_exact(709, receipt['memory_edits_replayed'], label + '.assist_count')
        module = bind_descriptor(receipt, 'gear', 'on', hashes)
        modules.append(module)
        configs.append(module[0])
        for name, digest in receipt['input_sha256'].items():
            if not Path(name).is_absolute():
                raise ValueError('protected inputs must be actual absolute paths')
            file_hash(name, digest, hashes)
        binary = file_hash(receipt['command'][0], receipt['binary_sha256'], hashes)
        assert_exact(receipt['binary_sha256'], receipt['input_sha256'][str(binary)], label + '.protected_executable')
        abi16.bound_command(receipt, hashes)
        for field, digest in (('source_route', 'source_route_sha256'), ('source_binary_anchor', 'source_binary_sha256')):
            file_hash(receipt[field], receipt[digest], hashes)
        abi16.bound_wav(receipt, path)
        shared.wav(receipt, path, 48000, hashes)
        raw_path = file_hash(path.parent / 'run.stdout', sha256(path.parent / 'run.stdout'), hashes)
        run, core = run_projection(receipt, read_json(raw_path), final_frame)
        capture, report = validate_managed_capture(receipt, module[0], run, route, PREFIX_FRAME, TOOL, hashes, label)
        captures.append(capture)
        capture_reports.append(report)
        runs.append(run)
        cores.append(core)
    assert_exact(receipts[0]['tool_identity'], receipts[1]['tool_identity'], 'same_exact_tool')
    for field in shared.ROUTE | {'source_command', 'images', 'memory_edits_replayed'}:
        assert_exact(receipts[0][field], receipts[1][field], 'same_route.' + field)
    for field, target in (('initial_command', 'source_command'), ('binary_sha256', 'source_binary_sha256'), ('initial_bram_sha256', 'initial_bram_sha256')):
        assert_exact(route[field], receipts[0][target], 'actual_route.' + field)
    assert_exact(route['initial_command'], prefix['source_command'], 'original_prefix_command')
    assert_exact(prior.canonical_command(receipts[0], True), prior.canonical_command(receipts[1], True), 'same_route.actual_argv')
    protected = [{k: v for k, v in receipt['input_sha256'].items() if k != receipt['command'][0]} for receipt in receipts]
    assert_exact(*protected, 'same_actual_protected_inputs')
    fixed_configs = [{key: value for key, value in config.items() if key != 'module'} for config in configs]
    assert_exact(*fixed_configs, 'same_descriptor_except_module')
    if modules[0][2]['code_capture_sha256'] == modules[1][2]['code_capture_sha256']:
        raise ValueError('distinct original and expanded source profiles required')
    compare_capture_observations(*captures)
    windows = [copy.deepcopy(run.pop('code_capture_window')) for run in runs]
    before = [(window.pop('native_steps_before'), window.pop('interpreter_steps_before')) for window in windows]
    assert_exact(before[0], before[1], 'exact94800_prefix_tiers')
    assert_exact(*windows, 'exact_managed_capture_window')
    counts = compare_tiers(*runs, 'runner', blocks_required=True)
    assert_exact(*cores, 'same_profile.final_pcm')
    assert_exact(receipts[0]['audio_contract']['wav_sha256'], receipts[1]['audio_contract']['wav_sha256'], 'same_profile.wav_bytes')
    measured, prefix_counts = [], None
    for field in ('checkpoint_status',) + ENDPOINTS:
        groups = [r[field] if field == 'checkpoint_status' else [r[field]] for r in receipts]
        assert_exact(len(groups[0]), len(groups[1]), field + '.count')
        for index, states in enumerate(zip(*groups)):
            guests, audio = [], []
            for state in states:
                guest, core = status_projection(state, checkpoint=field == 'checkpoint_status')
                guests.append(guest)
                audio.append(core)
            assert_exact(*audio, field + '.exact_pcm')
            host_counts = compare_tiers(guests[0]['host'], guests[1]['host'], field)
            left, right = [copy.deepcopy(g) for g in guests]
            left.pop('host'); right.pop('host')
            assert_exact(left, right, field + '.clock_and_pause')
            if field == 'checkpoint_status' and index < PREFIX_IMAGES:
                original, original_audio = status_projection(prefix['checkpoint_status'][index], checkpoint=True)
                for guest, core in zip(guests, audio):
                    assert_exact(original, guest, 'exact_retained39_prefix_guest_source_tiers_cd')
                    assert_exact(original_audio, core, 'exact_retained39_prefix_pcm')
            if states[0]['frame'] == PREFIX_FRAME and field == 'checkpoint_status':
                prefix_counts = host_counts
                for counts_at_boundary in prefix_counts:
                    for key in ('native', 'interpreted', 'total'):
                        assert_exact(frozen_prefix_counts[key], counts_at_boundary[key], 'frozen_prefix.runner_tiers')
                assert_exact(prefix_audio, audio[0], 'frozen_prefix.runner_pcm')
            if field in ENDPOINTS:
                for side in (0, 1):
                    assert_exact(final_frame, states[side]['frame'], field + '.final_frame')
                    for key in ('native', 'interpreted', 'total'):
                        assert_exact(counts[side][key], host_counts[side][key], field + '.runner.' + key)
                    assert_exact(runs[side]['ticks'], states[side]['ticks'], field + '.runner_clock')
                    assert_exact(cores[side], audio[side], field + '.runner_pcm')
                    assert_exact(runs[side]['cd_unknown'], guests[side]['host']['cd_unknown'], field + '.runner_cd')
                    assert_exact({'write_enabled': True, 'write_requests': 709, 'bytes_changed': 723}, guests[side]['host']['debug_memory'], field + '.original_assists')
            measured.append({'field': field, 'frame': states[0]['frame'], 'ticks': states[0]['ticks'], 'old': host_counts[0], 'new': host_counts[1]})
    for side, name in ((0, 'old'), (1, 'new')):
        checkpoints = [m for m in measured if m['field'] == 'checkpoint_status']
        for a, b in zip(checkpoints, checkpoints[1:]):
            if b['ticks'] < a['ticks'] or any(b[name][k] < a[name][k] for k in ('native', 'interpreted', 'total')):
                raise ValueError('nonmonotonic clock or retired counters')
        if runs[side]['ticks'] < checkpoints[-1]['ticks'] or any(counts[side][key] < checkpoints[-1][name][key] for key in ('native', 'interpreted', 'total')):
            raise ValueError('final retirements precede checkpoint')
    gain, suffix_gain, suffix_total = measured_gain(counts, prefix_counts, min_native_gain)
    suffix_blocks = [counts[i]['blocks'] - frozen_prefix_counts['blocks'] for i in (0, 1)]
    if min(suffix_blocks) < 0 or suffix_blocks[0] != suffix_blocks[1]:
        raise ValueError('prefix-to-final block retirements must be conserved')
    if runs[0]['ticks'] <= receipts[0]['capture_contract']['start_proof']['status']['ticks']:
        raise ValueError('captured suffix must advance the guest clock')
    tool = verify_capture_tool(configs[0], TOOL, Path(receipts[0]['project_descriptor']).parent)
    old_profile, new_profile, composition = verify_composition(provenance_paths, evidence, tool, captures[0], paths[0], final_frame, hashes)
    prefix_module = bind_descriptor(prefix, 'gear', 'on', hashes)
    assert_exact(prefix_module[2], modules[0][2], 'baseline.retains_actual_qualified_prefix_module')
    prefix_route['_path'], route['_path'] = str(prefix_route_path), str(route_path)
    emission = [verify_emission(module, profile, provenance_paths[role + '_profile'], evidence[role + '_selection'], recipe, tool)
                for module, profile, role, recipe in ((modules[0], old_profile, 'old', prefix_route), (modules[1], new_profile, 'new', route))]
    if emission[1]['identities'] <= emission[0]['identities']:
        raise ValueError('expanded native module must contain new original source identities')
    verify_capture_tool(configs[0], TOOL, Path(receipts[0]['project_descriptor']).parent)
    for path, digest in hashes.items():
        if sha256(path) != digest:
            raise ValueError('evidence changed during native16 qualification: ' + path)
    return {'schema': 1, 'kind': 'ys3-native16-audio-qualification', 'passed': True, 'tool': TOOL, 'selection': SELECTION,
            'prefix_frame': PREFIX_FRAME, 'frames': final_frame, 'prefix_images': PREFIX_IMAGES,
            'images': len(frames), 'checkpoint_states': len(frames), 'endpoint_states': 3,
            'minimum_native_gain': min_native_gain, 'native_steps_gained': gain, 'suffix_native_steps_gained': suffix_gain,
            'suffix_total_retired': suffix_total[0], 'suffix_total_blocks': suffix_blocks[0], 'old_runner': counts[0], 'new_runner': counts[1],
            'memory_edits_replayed': 709, 'memory_bytes_changed': 723, 'measurements': measured,
            'managed_capture': {'runtime_abi': 16, 'old': capture_reports[0], 'new': capture_reports[1],
                                'exact_observation_identities_and_retired_hits': True},
            'emission': emission, 'composition': composition, 'pcm_and_bounded_wav_exact': True,
            'all_guest_source_cd_exact_except_measured_tiers': True, 'retained39_prefix_exact': True,
            'evidence_sha256': hashes, 'normalization': {'tier_fields': list(TIER_FIELDS),
                'transport': ['status.id', 'status.ok', 'development.port'], 'validated_presentation': True,
                'capture_window_tier_fields': ['native_steps_before', 'interpreter_steps_before'],
                'capture_observation_tier_fields': ['native_hits', 'interpreted_hits']},
            'scope': 'Measured native gain on the same extended assisted ABI16 Gear filtered48k route. Actual raw94800 suffix captures retain full PC/MPR/source identities and retirement totals, zero loss and restored bytes. The composed profile is not single-execution proof. Explicit gear-good, volatile BRAM, excluded full six-byte source span, independent-reference limits and unfinished campaign remain visible.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-receipt', 'candidate-receipt', 'prefix-receipt', 'provenance', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--min-native-gain', type=int, default=1)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('qualification output must be new')
    result, failure = {'passed': False}, None
    try:
        result = qualify_native16(args.baseline_receipt, args.candidate_receipt, prefix_receipt=args.prefix_receipt,
                                  provenance=args.provenance, min_native_gain=args.min_native_gain)
    except (OSError, ValueError, RuntimeError, KeyError, IndexError, TypeError, wave.Error, subprocess.SubprocessError) as error:
        result.update(error=repr(error)); failure = error
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    if failure:
        raise failure
    print('PASS: measured ABI16 native gain; ' + str(args.out))


if __name__ == '__main__':
    main()
