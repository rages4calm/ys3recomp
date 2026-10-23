"""Emit the complete observed route through the pinned upstream tool.

All output is private. Entire journaled temporary-code spans are excluded,
including original variants, so their execution remains explicitly interpreted.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

try:
    from .select_canonical import canonical_bytes
except ImportError:
    from select_canonical import canonical_bytes

ROOT = Path(__file__).resolve().parents[1]


def excluded_spans(route):
    """Validate restoration, then coalesce the exact journaled source bytes."""
    addresses = sorted(canonical_bytes(route))
    spans = []
    for address in addresses:
        if spans and spans[-1][0] + spans[-1][1] == address:
            start, length = spans[-1]
            spans[-1] = (start, length + 1)
        else:
            spans.append((address, 1))
    return tuple(spans)


def audit_assist_source(capture, route, spans):
    """Refuse promotion of any observed source touched by an unexcluded edit."""
    fetched = {address for observation in capture['observations']
               for address in observation['physical']}
    overlaps, count = [], 0
    for step in route['steps']:
        if 'memory_write' not in step:
            continue
        count += 1
        edit = step['memory_write']
        address = edit['address']
        data, expected = bytes.fromhex(edit['data']), bytes.fromhex(edit['expected'])
        if type(address) is not int or not 1 <= len(data) <= 256 or len(data) != len(expected) \
                or address < 0 or address + len(data) > 0x200000:
            raise ValueError('invalid assist edit range')
        common = sorted(fetched.intersection(range(address, address+len(data))))
        if common:
            if any(not any(start <= p < start+length for start, length in spans) for p in common):
                raise ValueError('assist overlaps observed source outside excluded spans')
            overlaps.append({'frame': step['frame'], 'reason': step.get('reason'),
                             'address': address, 'length': len(data),
                             'observed_source_addresses': common})
    return {'edit_transactions': count, 'source_overlaps': overlaps,
            'all_observed_assist_source_overlaps_excluded': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('tool-root', 'route', 'capture', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    tool = args.tool_root.resolve(strict=True)
    verify = [sys.executable, str(ROOT/'scripts/verify_tool.py'), '--tool-root', str(tool)]
    identity = json.loads(subprocess.check_output(verify, text=True))
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(tool))
    from pcerecomp.capture import load_capture
    from pcerecomp.emitter import emit_capture
    capture, capture_hash = load_capture(args.capture)
    with args.route.open('rb') as stream:
        route_raw = stream.read(4*1024*1024 + 1)
    if len(route_raw) > 4*1024*1024:
        raise ValueError('route exceeds four MiB')
    route = json.loads(route_raw)
    spans = excluded_spans(route)
    assist_audit = audit_assist_source(capture, route, spans)
    output = args.out.resolve()
    if output.is_relative_to(tool) or output.is_relative_to(args.capture.resolve().parent):
        raise ValueError('output must be separate from read-only tool and capture roots')
    manifest = emit_capture(capture, output, capture_hash, exclude_ranges=spans)
    # The upstream manifest preserves the complete original profile, including
    # its hit totals, while recording source exclusions separately.
    if manifest['capture_retired_instructions'] != capture['retired_instructions']:
        raise ValueError('emitter changed original capture retirement provenance')
    if manifest['code_capture_sha256'] != capture_hash:
        raise ValueError('emitter changed original capture identity')
    after = json.loads(subprocess.check_output(verify, text=True))
    if after != identity or hashlib.sha256(args.capture.read_bytes()).hexdigest() != capture_hash:
        raise ValueError('tool or raw capture changed during emission')
    receipt = {'schema': 1, 'tool_identity': identity,
               'route_sha256': hashlib.sha256(route_raw).hexdigest(),
               'raw_capture_sha256': capture_hash,
               'capture_runtime_abi': capture['runtime_abi'],
               'module_runtime_abi': manifest['runtime_abi'],
               'translation_units': len(manifest.get('translation_units', [manifest])),
               'raw_observations': len(capture['observations']),
               'raw_retired_instructions': capture['retired_instructions'],
               'raw_complete': capture['complete'],
               'excluded_physical_ranges': manifest['excluded_physical_ranges'],
               'excluded_observations': manifest['excluded_observations'],
               'excluded_retired_hits': manifest['excluded_retired_hits'],
               'native_identities': manifest['native_instructions_emitted'],
               'mpr_contexts': manifest['native_contexts'],
               'unsupported_observations': manifest['unsupported_observations'],
               'assist_source_audit': assist_audit,
               'expected_native_hits': capture['retired_instructions'] - manifest['excluded_retired_hits'],
               'execution_evidence': False,
               'scope': 'Complete observed profile emitted through upstream API with entire verified-restored temporary-code spans excluded. Original capture identity, completeness and hit totals are preserved. Unknown/unvisited code and excluded source remain hybrid.'}
    (output/'selection.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
