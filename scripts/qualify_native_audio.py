"""Qualify same-profile native gains without weakening frozen DSP qualification.

Reviewed contract: ABI 13, schema-1 official packaged desktop builds and
filtered-v1 48 kHz. Managed capture windows are reviewed for the exact pinned
source below. A future source/window or ABI contract needs another review.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import tomllib
import re
import subprocess
import sys

if __package__:
    from . import qualify_dsp as shared
    from .qualify_coverage import TIER_FIELDS, assert_exact, read_json
    from .replay_route import (sha256, unwrap_execution, managed_capture_selection,
                              capture_start_proof, finish_managed_capture)
    from .merge_observations import load_capture_api
    from .expand_native import excluded_spans, audit_assist_source
else:
    import qualify_dsp as shared
    from qualify_coverage import TIER_FIELDS, assert_exact, read_json
    from replay_route import (sha256, unwrap_execution, managed_capture_selection,
                             capture_start_proof, finish_managed_capture)
    from merge_observations import load_capture_api
    from expand_native import excluded_spans, audit_assist_source

SELECTION = {'profile': 'filtered', 'sample_rate': 48000}
ENDPOINTS = ('before_final_release', 'final_status', 'released_status')
CAPTURE_TOOL = {'revision': 'c5aa9a26125edabdbe98a68bf716bff6eacd310e',
                'source_sha256': '740f6a5f87aa865c49d538d7c424a8e5b88e903cb022ea0cfab5ab0e387e4b36',
                'runtime_abi': 13}


def file_hash(path, expected, hashes):
    shared.digest(expected)
    path = Path(path).resolve(strict=True)
    if not path.is_file() or sha256(path) != expected:
        raise ValueError('evidence file hash mismatch: ' + str(path))
    hashes[str(path)] = expected
    return path


def nonnegative(value, label):
    if type(value) is not int or not 0 <= value < 1 << 64:
        raise ValueError(label + ': unsigned integer required')
    return value


def tiers(value, label, blocks_required=False):
    if not isinstance(value, dict):
        raise ValueError(label + ': guest object required')
    result = copy.deepcopy(value)
    if 'code_capture' in result:
        raise ValueError('unreviewed capture diagnostic in ABI13 guest contract')
    native = nonnegative(result.pop('native_steps'), label + '.native_steps')
    interpreted = nonnegative(result.pop('interpreter_steps'), label + '.interpreter_steps')
    total = native + interpreted
    if total >= 1 << 64:
        raise ValueError(label + ': retirement total overflow')
    guard = result.pop('guard_misses', None)
    if 'guard_misses' in value:
        nonnegative(guard, label + '.guard_misses')
    block_keys = {'native_block_steps', 'interpreter_block_steps'} & result.keys()
    if (blocks_required or block_keys) and block_keys != {'native_block_steps', 'interpreter_block_steps'}:
        raise ValueError(label + ': complete block retirement pair required')
    blocks = None
    if block_keys:
        left = nonnegative(result.pop('native_block_steps'), label + '.native_block_steps')
        right = nonnegative(result.pop('interpreter_block_steps'), label + '.interpreter_block_steps')
        if left > native or right > interpreted:
            raise ValueError(label + ': block retirements exceed corresponding instruction tier')
        blocks = left + right
    return result, {'native': native, 'interpreted': interpreted, 'total': total, 'blocks': blocks,
                    'guard_reported': 'guard_misses' in value}


def compare_tiers(left, right, label, blocks_required=False):
    a, ca = tiers(left, 'old.' + label, blocks_required)
    b, cb = tiers(right, 'new.' + label, blocks_required)
    for field in ('total', 'blocks', 'guard_reported'):
        assert_exact(ca[field], cb[field], label + '.conserved_' + field)
    assert_exact(a, b, label + '.guest')
    return ca, cb


def source_identity(value, label, status=False):
    """Validate the known seven-byte fetch identity, including mapping wrap."""
    pc = value['pc']
    cpu = value['cpu'] if status else value
    if type(pc) is not int or not 0 <= pc <= 65535:
        raise ValueError(label + ': logical PC must be an unsigned 16-bit integer')
    mpr = cpu['mpr']
    if not isinstance(mpr, list) or len(mpr) != 8 or any(type(x) is not int or not 0 <= x <= 255 for x in mpr):
        raise ValueError(label + ': all eight unsigned MPR bytes required')
    data = cpu['instruction_bytes']
    if not isinstance(data, list) or len(data) != 7 or any(x is not None and (type(x) is not int or not 0 <= x <= 255) for x in data):
        raise ValueError(label + ': exact seven-byte nullable fetch identity required')
    if status:
        physical = [(mpr[((pc + i) & 65535) >> 13] << 13) | ((pc + i) & 8191) for i in range(7)]
        assert_exact(physical[0], cpu['physical_pc'], label + '.physical_pc')
        assert_exact(physical, cpu['instruction_physical'], label + '.instruction_physical')
        generations = cpu['instruction_generations']
        if not isinstance(generations, list) or len(generations) != 7:
            raise ValueError(label + ': all seven source generations required')
        for generation in generations:
            nonnegative(generation, label + '.source_generation')


def bound_descriptor(receipt, tool, hashes, label):
    """Use official build/package validators and rehash all declared source inputs."""
    shared.descriptor(receipt, SELECTION, tool, hashes, label)
    path = Path(receipt['project_descriptor']).resolve(strict=True)
    config = tomllib.loads(path.read_text(encoding='utf-8'))
    built = read_json(Path(receipt['project_build']) / 'build-receipt.json')
    assert_exact(built['binding'], receipt['project_binding'], label + '.recorded_project_binding')
    files = {}
    def declared(role, binding):
        shared.keys(binding, {'path', 'sha256'}, 'descriptor.' + role)
        raw = Path(binding['path'])
        files[role] = file_hash(raw if raw.is_absolute() else path.parent / raw, binding['sha256'], hashes)
    for role in ('module_source', 'module_manifest'):
        declared(role, config['module']['source' if role == 'module_source' else 'manifest'])
    payload = config['payload']
    declared('payload', {key: payload[key] for key in ('path', 'sha256')})
    for role in ('bios', 'disc', 'toc', 'libchdr', 'bram', 'input_script'):
        if role in config:
            declared(role, config[role])
    manifest = read_json(files['module_manifest'])
    if type(manifest.get('schema')) is not int or manifest['schema'] != 1:
        raise ValueError('generated module schema 1 required')
    if type(manifest.get('runtime_abi')) is not int or manifest['runtime_abi'] != 13:
        raise ValueError('generated module requires reviewed ABI 13; future ABI requires explicit review')
    if type(manifest.get('native_instructions_emitted')) is not int or not 1 <= manifest['native_instructions_emitted'] <= 1000000:
        raise ValueError('generated module requires a positive bounded instruction count')
    if {'translation_units', 'generated_headers'} & manifest.keys():
        seen = set()
        for field, prefix, suffix, minimum in (('translation_units', 'module_unit', '.cpp', 1),
                                                ('generated_headers', 'module_header', '.hpp', 0)):
            entries = manifest.get(field)
            if not isinstance(entries, list) or len(entries) < minimum:
                raise ValueError('complete module artifact list required')
            for entry in entries:
                shared.keys(entry, {'file', 'sha256'}, 'module artifact')
                name = entry['file']
                if (not isinstance(name, str) or Path(name).name != name or '/' in name or '\\' in name
                        or not name.endswith(suffix) or name.casefold() in seen):
                    raise ValueError('unique direct module artifact basename required')
                seen.add(name.casefold())
                target = files['module_manifest'].parent / name
                if target.is_symlink():
                    raise ValueError('module artifact symlink refused')
                files[prefix + ':' + name] = file_hash(target, entry['sha256'], hashes)
        if files['module_source'] not in [p for key, p in files.items() if key.startswith('module_unit:')]:
            raise ValueError('module source absent from translation units')
    actual = {role: sha256(target) for role, target in files.items()}
    assert_exact(actual, built['binding']['files'], label + '.all_bound_source_files')
    return config, actual


def canonical_command(receipt, managed=False):
    command = receipt['command'].copy()
    if '--capture-start-frame' in command or (not managed and any(flag in command for flag in
            ('--code-capture-start-frame', '--code-capture', '--capture-limit'))):
        raise ValueError('capture-bearing execution needs separate reviewed artifact qualification; ABI13 native/audio runs must be capture-free')
    command[0] = '<official-bound-binary>'
    # Only output filenames and loopback allocation are transport metadata.
    for flag, token in (('--audio-out', '<bound-wave>'), ('--dev-port', '<loopback-port>')):
        shared.option(command, flag)
        command[command.index(flag) + 1] = token
    if managed:
        shared.option(command, '--code-capture')
        command[command.index('--code-capture') + 1] = '<validated-raw-capture>'
    return command


def verify_capture_tool(config, tool, descriptor_directory=None):
    """Reverify current public source, including its exact bytes, before loading it."""
    assert_exact(CAPTURE_TOOL, tool, 'reviewed_capture_tool')
    raw = Path(config['tool']['path'])
    source = (raw if raw.is_absolute() else Path(descriptor_directory or '.') / raw).resolve(strict=True)
    checked = subprocess.run([sys.executable, str(Path(__file__).with_name('verify_tool.py')),
        '--tool-root', str(source), '--expected-revision', tool['revision'],
        '--expected-abi', '13', '--expected-source-sha256', tool['source_sha256']],
        check=True, capture_output=True, text=True, timeout=60)
    identity = json.loads(checked.stdout)
    shared.identity({'tool_identity': identity, 'tool_identity_after': identity}, tool, 'live_capture_tool')
    return source


class RecordedPause:
    """Re-run the shared proof checker over every retained status/read response."""
    def __init__(self, proof):
        self.proof, self.calls, self.reads = proof, 0, 0

    def call(self, name):
        if name != 'status' or self.calls >= 2:
            raise ValueError('unexpected recorded capture-proof request')
        self.calls += 1
        return copy.deepcopy(self.proof['status_before' if self.calls == 1 else 'status'])

    def read_memory(self, address, length):
        entry = self.proof['canonical_readback'][self.reads]
        self.reads += 1
        shared.keys(entry, {'address', 'expected', 'observed'}, 'recorded capture readback')
        if type(entry['address']) is not int or entry['address'] != address:
            raise ValueError('capture readback address differs from canonical span')
        data = bytes.fromhex(entry['observed'])
        if len(data) != length or entry['expected'] != entry['observed']:
            raise ValueError('capture readback is not verified-restored original bytes')
        return data


def validate_managed_capture(receipt, config, run, route, prefix_frame, tool, hashes, label):
    contract = receipt['capture_contract']
    shared.keys(contract, {'schema', 'runtime_abi', 'path', 'sha256', 'start_frame', 'capacity',
                          'start_proof', 'capture', 'observations', 'window', 'scope'}, label + '.capture_contract')
    if type(contract['schema']) is not int or contract['schema'] != 1 or contract['runtime_abi'] != 13:
        raise ValueError('reviewed managed-capture schema 1 ABI13 required')
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
        projected, _ = shared.guest_status(status, SELECTION, receipt['audio_contract']['wav_frame_limit'], checkpoint=True)
        checkpoint, _ = shared.guest_status(prefixes[0], SELECTION, receipt['audio_contract']['wav_frame_limit'], checkpoint=True)
        assert_exact(checkpoint, projected, label + '.capture_proof_matches_prefix_checkpoint')
    rebuilt = finish_managed_capture(path, source, selected, proof, run)
    assert_exact(contract, rebuilt, label + '.capture_contract_revalidated')
    capture, actual_hash = load_capture_api(source).load_capture(path)
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


def compare_capture_observations(left, right):
    def project(capture):
        return sorted([{'pc': item['pc'], 'mpr': item['mpr'], 'physical': item['physical'], 'data': item['data'],
                        'retired_hits': item['native_hits'] + item['interpreted_hits']}
                       for item in capture['observations']], key=lambda item: (item['mpr'], item['pc'], item['data']))
    assert_exact(project(left), project(right), 'capture.exact_source_identities_and_retired_hits')
    for field in ('capacity', 'retired_instructions', 'complete', 'dropped_instructions', 'unreadable_instructions', 'runtime_abi', 'schema'):
        assert_exact(left[field], right[field], 'capture.' + field)


def qualify_native_audio(baseline_receipt, candidate_receipt, *, prefix_frame, min_native_gain=1):
    """Read actual path-bound evidence; require whole-route and suffix native gain."""
    if type(prefix_frame) is not int or prefix_frame <= 0:
        raise ValueError('prefix_frame must be a positive integer checkpoint boundary')
    if type(min_native_gain) is not int or min_native_gain < 1:
        raise ValueError('min_native_gain must be a positive integer')
    paths = [Path(p).resolve(strict=True) for p in (baseline_receipt, candidate_receipt)]
    receipts = [read_json(p) for p in paths]
    hashes = {str(p): sha256(p) for p in paths}
    tool = receipts[0]['tool_identity']
    expected_tool = {'revision': tool['revision'], 'source_sha256': tool['shared_source_identity']['source_sha256'],
                     'runtime_abi': tool['runtime_abi']}
    if type(expected_tool['runtime_abi']) is not int or expected_tool['runtime_abi'] != 13:
        raise ValueError('only reviewed ABI 13 is accepted; future ABI requires explicit contract review')
    if not isinstance(expected_tool['revision'], str) or not re.fullmatch('[0-9a-f]{40}', expected_tool['revision']):
        raise ValueError('full tool revision required')
    shared.digest(expected_tool['source_sha256'])
    limits = [r['audio_contract']['wav_frame_limit'] for r in receipts]
    assert_exact(limits[0], limits[1], 'same_profile.wav_frame_limit')
    if limits[0] is None:
        raise ValueError('bounded WAV required')
    managed = ['capture_contract' in receipt for receipt in receipts]
    if managed[0] != managed[1]:
        raise ValueError('managed capture contracts must be present on both replays or neither')
    route = read_json(Path(receipts[0]['source_route']))
    configs, bindings, runs, cores = [], [], [], []
    for label, path, receipt in zip(('old', 'new'), paths, receipts):
        shared.clean_receipt(receipt, SELECTION, label)
        shared.identity(receipt, expected_tool, label)
        config, binding = bound_descriptor(receipt, expected_tool, hashes, label)
        configs.append(config)
        bindings.append(binding)
        for name, expected in receipt['input_sha256'].items():
            if not Path(name).is_absolute():
                raise ValueError('protected input must use an actual absolute path')
            file_hash(name, expected, hashes)
        for field, identity in (('source_route', 'source_route_sha256'), ('source_binary_anchor', 'source_binary_sha256')):
            file_hash(receipt[field], receipt[identity], hashes)
        shared.wav(receipt, path, 48000, hashes)
        assert_exact(str((path.parent / 'audio.wav').resolve()), shared.option(receipt['command'], '--audio-out'), label + '.command.wav')
        assert_exact(str(limits[0]), shared.option(receipt['command'], '--audio-frames'), label + '.command.wav_limit')
        binary = Path(receipt['command'][0]).resolve(strict=True)
        assert_exact(receipt['binary_sha256'], sha256(binary), label + '.binary')
        if receipt['input_sha256'].get(str(binary)) != receipt['binary_sha256']:
            raise ValueError('selected executable missing from protected input binding')
        for value in [receipt['command'][1]] + [shared.option(receipt['command'], flag) for flag in
                ('--bios', '--bram', '--disc', '--toc', '--libchdr', '--input-script') if flag in receipt['command']]:
            target = Path(value).resolve(strict=True)
            if receipt['input_sha256'].get(str(target)) != sha256(target):
                raise ValueError('runner asset missing from protected input binding')
        raw_path = path.parent / 'run.stdout'
        hashes[str(raw_path)] = sha256(raw_path)
        run = copy.deepcopy(unwrap_execution(read_json(raw_path), receipt['binary_sha256']))
        if run.get('stop') != 'dev_quit':
            raise ValueError('complete consumer-controlled route must stop by dev_quit')
        source_identity(run, label + '.runner')
        core = shared.audio(run.pop('audio_output'), SELECTION, limits[0])
        assert_exact(core, receipt['audio_contract']['validated_output'], label + '.validated_output')
        assert_exact(core, shared.audio(receipt['desktop_contract']['audio_output'], SELECTION, limits[0]), label + '.desktop_pcm')
        presentation = shared.validate_desktop(run.pop('desktop'), receipt['final_status']['frame'])
        assert_exact(presentation, receipt['desktop_contract']['presentation'], label + '.presentation')
        run['development'].pop('port', None)
        runs.append(run)
        cores.append(core)
    assert_exact(cores[0], cores[1], 'same_profile.final_pcm')
    assert_exact(receipts[0]['tool_identity'], receipts[1]['tool_identity'], 'same_tool.complete_source_identity')
    assert_exact(receipts[0]['audio_contract']['wav_sha256'], receipts[1]['audio_contract']['wav_sha256'], 'same_profile.wav_bytes')
    for key in shared.ROUTE | {'source_command', 'images', 'memory_edits_replayed'}:
        assert_exact(receipts[0][key], receipts[1][key], 'same_route.' + key)
    capture_reports = []
    if managed[0]:
        captures = []
        for label, receipt, config, run in zip(('old', 'new'), receipts, configs, runs):
            capture, report = validate_managed_capture(receipt, config, run, route, prefix_frame,
                                                       expected_tool, hashes, label)
            captures.append(capture)
            capture_reports.append(report)
        compare_capture_observations(*captures)
        windows = [copy.deepcopy(run.pop('code_capture_window')) for run in runs]
        before_counts = [(window.pop('native_steps_before'), window.pop('interpreter_steps_before')) for window in windows]
        assert_exact(sum(before_counts[0]), sum(before_counts[1]), 'capture.conserved_prefix_retirements')
        assert_exact(windows[0], windows[1], 'capture.exact_window')
    elif any('code_capture_window' in run for run in runs):
        raise ValueError('capture window cannot be normalized without both validated managed contracts')
    assert_exact(canonical_command(receipts[0], managed[0]), canonical_command(receipts[1], managed[1]), 'same_route.command')
    for config in configs:
        config.pop('module')
    assert_exact(configs[0], configs[1], 'same_route.descriptor_except_module')
    protected = [{k: v for k, v in r['input_sha256'].items() if k != r['command'][0]} for r in receipts]
    assert_exact(protected[0], protected[1], 'protected_inputs')
    fixed = [{k: v for k, v in binding.items() if not k.startswith('module_')} for binding in bindings]
    assert_exact(fixed[0], fixed[1], 'same_route.bound_inputs')
    if bindings[0]['module_source'] == bindings[1]['module_source']:
        raise ValueError('distinct hash-bound old and new native modules required')
    for field, target in (('initial_command', 'source_command'), ('binary_sha256', 'source_binary_sha256'),
                          ('initial_bram_sha256', 'initial_bram_sha256')):
        assert_exact(route[field], receipts[0][target], 'actual_route.' + field)
    nonnegative(receipts[0]['memory_edits_replayed'], 'route.memory_edits_replayed')
    image_view = lambda values: [{'frame': x['frame'], 'png_sha256': x['png_sha256']} for x in values]
    assert_exact(image_view(route['checkpoints']), image_view(receipts[0]['images']), 'complete_route.images')
    frames = [state['frame'] for state in receipts[0]['checkpoint_status']]
    if frames != sorted(set(frames)) or any(type(frame) is not int or frame < 0 for frame in frames):
        raise ValueError('unique ordered checkpoint frames required')
    if (len([f for f in frames if f <= prefix_frame]) < 25 or prefix_frame not in frames
            or not any(f > prefix_frame for f in frames)):
        raise ValueError('25 retained prefix checkpoints, explicit prefix boundary and new suffix checkpoints required')
    assert_exact(frames, sorted(set(x['frame'] for x in receipts[0]['images'])), 'complete_route.checkpoints')
    runner_counts = compare_tiers(runs[0], runs[1], 'runner', True)
    if runner_counts[0]['total'] <= 0:
        raise ValueError('nonempty retired work required')
    measured, prefix_counts = [], None
    for field in ('checkpoint_status',) + ENDPOINTS:
        groups = [r[field] if field == 'checkpoint_status' else [r[field]] for r in receipts]
        assert_exact(len(groups[0]), len(groups[1]), field + '.count')
        for index, (left, right) in enumerate(zip(*groups)):
            label = f'{field}[{index}]'
            guests, audio = [], []
            for state in (left, right):
                if type(state.get('frame')) is not int or type(state.get('ticks')) is not int or state['ticks'] < 0:
                    raise ValueError('integer guest frame and tick diagnostics required')
                if state.get('paused') is not True or type(state.get('local_paused')) is not bool:
                    raise ValueError('settled paused guest checkpoint required')
                source_identity(state['host'], label, status=True)
                guest, core = shared.guest_status(state, SELECTION, limits[0], checkpoint=field == 'checkpoint_status')
                guests.append(guest)
                audio.append(core)
            assert_exact(audio[0], audio[1], label + '.exact_pcm_and_wav')
            host_counts = compare_tiers(guests[0].pop('host'), guests[1].pop('host'), label)
            assert_exact(guests[0], guests[1], label + '.guest_clock')
            measured.append({'field': field, 'frame': left['frame'], 'old': host_counts[0], 'new': host_counts[1]})
            if field == 'checkpoint_status' and left['frame'] == prefix_frame:
                prefix_counts = host_counts
            if field in ENDPOINTS:
                for side, counts in enumerate(host_counts):
                    for key in ('native', 'interpreted', 'total'):
                        assert_exact(runner_counts[side][key], counts[key], label + '.runner.' + key)
                    if counts['blocks'] is not None:
                        assert_exact(runner_counts[side]['blocks'], counts['blocks'], label + '.runner.blocks')
                    assert_exact(runs[side]['ticks'], (left, right)[side]['ticks'], label + '.runner.ticks')
                    assert_exact(cores[side], audio[side], label + '.runner.pcm')
    gain = runner_counts[1]['native'] - runner_counts[0]['native']
    for side in (0, 1):
        checkpoints = [m['old' if side == 0 else 'new'] for m in measured if m['field'] == 'checkpoint_status']
        for prior, following in zip(checkpoints, checkpoints[1:] + [runner_counts[side]]):
            if any(following[key] < prior[key] for key in ('native', 'interpreted', 'total')):
                raise ValueError('nonmonotonic cumulative retirement counters')
    suffix_totals = [runner_counts[i]['total'] - prefix_counts[i]['total'] for i in (0, 1)]
    suffix_native = [runner_counts[i]['native'] - prefix_counts[i]['native'] for i in (0, 1)]
    if any(n < 0 or n > total for n, total in zip(suffix_native, suffix_totals)) or min(suffix_totals) <= 0:
        raise ValueError('invalid suffix retirement accounting')
    suffix_gain = suffix_native[1] - suffix_native[0]
    if gain < min_native_gain or suffix_gain < min_native_gain:
        raise ValueError('positive measured native gain required in both total route and suffix')
    for path, expected in hashes.items():
        if sha256(path) != expected:
            raise ValueError('evidence changed during qualification: ' + path)
    return {'schema': 1, 'kind': 'ys3-native-audio-qualification', 'passed': True,
            'tool': expected_tool, 'selection': SELECTION, 'prefix_frame': prefix_frame,
            'minimum_native_gain': min_native_gain, 'native_steps_gained': gain,
            'suffix_native_steps_gained': suffix_gain, 'suffix_total_retired': suffix_totals[0],
            'old_runner': runner_counts[0], 'new_runner': runner_counts[1],
            'images': len(receipts[0]['images']), 'checkpoint_states': len(frames), 'endpoint_states': 3,
            'memory_edits_replayed': receipts[0]['memory_edits_replayed'], 'measurements': measured,
            'managed_capture': {'enabled': managed[0], 'old': capture_reports[0] if capture_reports else None,
                                'new': capture_reports[1] if capture_reports else None,
                                'exact_observation_identities_and_retired_hits': True if managed[0] else None},
            'pcm_and_bounded_wav_exact': True, 'evidence_sha256': hashes,
            'normalization': {'tier_fields': list(TIER_FIELDS), 'transport': ['status.id', 'status.ok', 'development.port'],
                              'validated_presentation': True, 'validated_capture_window': managed[0],
                              'capture_window_tier_fields': ['native_steps_before', 'interpreter_steps_before'] if managed[0] else [],
                              'capture_observation_tier_fields': ['native_hits', 'interpreted_hits'] if managed[0] else []},
            'scope': 'Same-profile ABI13 filtered48000 exposed guest/audio reproduction with measured native gain; exact managed c5-source capture windows when present. Assisted progression, gear-good, volatile saves and independent/hardware limits remain unchanged. Future source/window or ABI contracts require explicit review.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-receipt', 'candidate-receipt', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--prefix-frame', type=int, required=True)
    parser.add_argument('--min-native-gain', type=int, default=1)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('qualification output must be new')
    result, failure = {'passed': False}, None
    try:
        result = qualify_native_audio(args.baseline_receipt, args.candidate_receipt,
                                      prefix_frame=args.prefix_frame, min_native_gain=args.min_native_gain)
    except (OSError, ValueError, RuntimeError, KeyError, IndexError, TypeError) as error:
        result.update(error=repr(error))
        failure = error
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    if failure:
        raise failure


if __name__ == '__main__':
    main()
