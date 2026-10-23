"""Compose private complete source profiles through the pinned capture validator.

This is a union of observations from multiple runs, never a single execution or
native-coverage qualification. Source exclusions remain a separate emitter step.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
U64 = (1 << 64) - 1
MAX_IDENTITIES = 65536
MAX_MANIFEST_BYTES = 1024 * 1024


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON number')))


def exact(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(label + ': missing or unknown fields')


def add(left, right, label):
    if type(right) is not int or right < 0 or left + right > U64:
        raise ValueError(label + ': uint64 overflow or invalid count')
    return left + right


def load_capture_api(tool):
    """Import the actual dependency in its own namespace, avoiding cached peers."""
    package = Path(tool).resolve(strict=True) / 'pcerecomp'
    name = '_ys3_capture_' + hashlib.sha256(str(package).encode()).hexdigest()[:16]
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(name, package / '__init__.py',
                                                        submodule_search_locations=[str(package)])
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        api = importlib.import_module(name + '.capture')
        if Path(api.__file__).resolve() != (package / 'capture.py').resolve():
            raise ValueError('capture API origin differs from verified dependency')
        return api
    finally:
        sys.dont_write_bytecode = previous


def merge_captures(captures, output_runtime_abi, validate_capture):
    """Exact full-MPR/source union; validation is the actual upstream API."""
    if type(output_runtime_abi) is not int or output_runtime_abi not in (12, 13):
        raise ValueError('explicit reviewed output capture ABI 12 or 13 required')
    if not isinstance(captures, list) or not 2 <= len(captures) <= 16:
        raise ValueError('two to sixteen complete input captures required')
    union, epochs = {}, []
    retired = native = interpreted = dropped = unreadable = 0
    capacity = 1
    first_keys = set()
    for index, capture in enumerate(captures):
        validate_capture(capture)
        if type(capture['runtime_abi']) is not int or capture['runtime_abi'] not in (12, 13):
            raise ValueError('unreviewed input capture ABI')
        if not capture['complete'] or capture['dropped_instructions'] or capture['unreadable_instructions']:
            raise ValueError('incomplete or lossy captures cannot qualify a native profile union')
        capacity = max(capacity, capture['capacity'])
        retired = add(retired, capture['retired_instructions'], 'retirement total')
        dropped = add(dropped, capture['dropped_instructions'], 'dropped total')
        unreadable = add(unreadable, capture['unreadable_instructions'], 'unreadable total')
        epoch_native = epoch_interpreted = 0
        before = len(union)
        for observation in capture['observations']:
            key = (observation['pc'], tuple(observation['mpr']), tuple(observation['physical']),
                   tuple(observation['data']))
            if index == 0:
                first_keys.add(key)
            epoch_native = add(epoch_native, observation['native_hits'], 'epoch native total')
            epoch_interpreted = add(epoch_interpreted, observation['interpreted_hits'], 'epoch interpreted total')
            if key not in union:
                if len(union) >= MAX_IDENTITIES:
                    raise ValueError('joint source identity capacity exceeds 65536; no truncation permitted')
                union[key] = copy.deepcopy(observation)
            else:
                target = union[key]
                for field in ('native_hits', 'interpreted_hits'):
                    target[field] = add(target[field], observation[field], 'identity ' + field)
                add(target['native_hits'], target['interpreted_hits'], 'identity combined hits')
        native = add(native, epoch_native, 'native total')
        interpreted = add(interpreted, epoch_interpreted, 'interpreted total')
        epochs.append({'runtime_abi': capture['runtime_abi'], 'capacity': capture['capacity'],
                       'observations': len(capture['observations']), 'new_union_identities': len(union) - before,
                       'retired_instructions': capture['retired_instructions'],
                       'native_hits': epoch_native, 'interpreted_hits': epoch_interpreted,
                       'dropped_instructions': capture['dropped_instructions'],
                       'unreadable_instructions': capture['unreadable_instructions'],
                       'complete': capture['complete']})
    if add(add(native, interpreted, 'combined tier totals'), add(dropped, unreadable, 'loss totals'),
           'conserved retirement total') != retired:
        raise ValueError('union retirement conservation failed')
    result = {'schema': 1, 'runtime_abi': output_runtime_abi, 'capacity': max(capacity, len(union)),
              'dropped_instructions': dropped, 'unreadable_instructions': unreadable,
              'retired_instructions': retired, 'complete': True,
              'observations': [union[key] for key in sorted(union)]}
    validate_capture(result)
    return result, {'input_epochs': epochs, 'union_identities': len(union),
                    'new_identities_over_first_capture': len(set(union) - first_keys),
                    'retired_instructions': retired, 'native_hits': native, 'interpreted_hits': interpreted,
                    'dropped_instructions': dropped, 'unreadable_instructions': unreadable,
                    'complete': True, 'hit_totals_conserved': True,
                    'execution_evidence': False, 'native_gain_qualified': False,
                    'scope': 'Multi-run observation profile; repeated identities retain summed original tier hits. No source exclusions, patch-hit subtraction or variant dropping. Separate TCP replay is required to qualify native gains.'}


def read_manifest(path):
    path = Path(path).resolve(strict=True)
    with path.open('rb') as stream:
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError('merge manifest exceeds one MiB')
    manifest = strict_json(raw)
    exact(manifest, {'schema', 'kind', 'output_runtime_abi', 'inputs'}, 'merge manifest')
    if type(manifest['schema']) is not int or manifest['schema'] != 1 or manifest['kind'] != 'ys3-observation-union':
        raise ValueError('unknown merge manifest schema/kind')
    if type(manifest['output_runtime_abi']) is not int or manifest['output_runtime_abi'] not in (12, 13):
        raise ValueError('explicit reviewed output capture ABI required')
    if not isinstance(manifest['inputs'], list) or not 2 <= len(manifest['inputs']) <= 16:
        raise ValueError('two to sixteen capture epochs required')
    hashes, entries, labels, captures = {path: hashlib.sha256(raw).hexdigest()}, [], set(), set()
    def binding(value):
        exact(value, {'path', 'sha256'}, 'artifact binding')
        if not isinstance(value['path'], str) or not value['path'] or '\0' in value['path']:
            raise ValueError('artifact path required')
        if not isinstance(value['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', value['sha256']):
            raise ValueError('artifact SHA256 required')
        target = (path.parent / value['path']).resolve(strict=True)
        if not target.is_file() or sha256(target) != value['sha256']:
            raise ValueError('bound merge input hash mismatch: ' + str(target))
        hashes[target] = value['sha256']
        return target
    for item in manifest['inputs']:
        exact(item, {'capture', 'epoch'}, 'input epoch')
        capture = binding(item['capture'])
        if capture in captures:
            raise ValueError('duplicate capture input path')
        captures.add(capture)
        epoch = item['epoch']
        exact(epoch, {'label', 'window', 'evidence'}, 'epoch provenance')
        if not isinstance(epoch['label'], str) or not epoch['label'].strip() or epoch['label'] in labels:
            raise ValueError('unique nonempty epoch label required')
        labels.add(epoch['label'])
        exact(epoch['window'], {'start_frame', 'end_frame'}, 'declared capture window')
        start, end = epoch['window']['start_frame'], epoch['window']['end_frame']
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= U64:
            raise ValueError('declared capture window must have increasing uint64 frame boundaries')
        if not isinstance(epoch['evidence'], list) or not 1 <= len(epoch['evidence']) <= 16:
            raise ValueError('hash-bound window/provenance evidence required')
        for artifact in epoch['evidence']:
            binding(artifact)
        entries.append((capture, copy.deepcopy(epoch)))
    return manifest, entries, hashes


def verify_inputs(hashes):
    for path, expected in hashes.items():
        if sha256(path) != expected:
            raise ValueError('merge evidence changed during composition: ' + str(path))


def compose(manifest_path, tool_root, output):
    manifest_path, tool = Path(manifest_path).resolve(strict=True), Path(tool_root).resolve(strict=True)
    output = Path(output).resolve()
    manifest, entries, hashes = read_manifest(manifest_path)
    if output.exists():
        raise ValueError('merge output must be a fresh directory')
    if (output.is_relative_to(tool) or tool.is_relative_to(output)
            or any(output.is_relative_to(path.parent) or path.is_relative_to(output) for path in hashes)):
        raise ValueError('merge output must be separate from read-only tool and input roots')
    command = [sys.executable, str(ROOT / 'scripts/verify_tool.py'), '--tool-root', str(tool)]
    identity = strict_json(subprocess.check_output(command, text=True))
    api = load_capture_api(tool)
    captures = []
    for path, _ in entries:
        capture, actual_hash = api.load_capture(path)
        if actual_hash != hashes[path]:
            raise ValueError('capture changed while loading')
        captures.append(capture)
    merged, summary = merge_captures(captures, manifest['output_runtime_abi'], api.validate_capture)
    verify_inputs(hashes)
    after = strict_json(subprocess.check_output(command, text=True))
    if after != identity:
        raise ValueError('verified tool changed during composition')
    raw = (json.dumps(merged, separators=(',', ':')) + '\n').encode()
    if len(raw) > api.MAX_CAPTURE_BYTES:
        raise ValueError('merged capture exceeds upstream file size bound')
    receipt = {'schema': 1, 'kind': 'ys3-multi-run-observation-profile', 'tool_identity': identity,
               'tool_identity_after': after, 'output_capture_runtime_abi': manifest['output_runtime_abi'],
               'capture_sha256': hashlib.sha256(raw).hexdigest(), 'capture_bytes': len(raw),
               'input_manifest': str(manifest_path), 'input_manifest_sha256': hashes[manifest_path],
               'inputs': [dict(path=str(path), sha256=hashes[path], epoch=epoch, **summary['input_epochs'][index])
                          for index, (path, epoch) in enumerate(entries)],
               'evidence_sha256': {str(path): digest for path, digest in hashes.items()},
               'provenance_semantics': 'Epoch labels/windows are caller declarations retained verbatim and bound to evidence bytes; this composition does not independently verify their execution meaning.',
               **{key: value for key, value in summary.items() if key != 'input_epochs'}}
    verify_inputs(hashes)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'observations.json').write_bytes(raw)
    verify_inputs(hashes)
    with (output / 'merge-receipt.json').open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'tool-root', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = compose(args.manifest, args.tool_root, args.out)
    print('Composed', result['union_identities'], 'identities across', len(result['inputs']),
          'epochs; native execution gains remain unqualified.')


if __name__ == '__main__':
    main()
