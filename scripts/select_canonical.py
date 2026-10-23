"""Select observed original-code identities using the private assist journal.

The original capture is immutable. This produces a private subset and a separate
selection receipt, never relabeling excluded patch hits as capacity loss.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def canonical_bytes(route):
    original, current = {}, {}
    patches = route.get('assistance', {}).get('code_patches', [])
    if route.get('assistance', {}).get('jump_patch_active') is not False or not patches:
        raise ValueError('explicit restored code-patch journal required')
    previous = -1
    for patch in patches:
        frame, address = patch['frame'], patch['physical']
        before, after = bytes.fromhex(patch['expected']), bytes.fromhex(patch['data'])
        if type(frame) is not int or frame < previous or frame > route['last_status']['frame']:
            raise ValueError('code-patch journal frame order invalid')
        if type(address) is not int or not before or len(before) != len(after) or address < 0 or address+len(before)>0x200000:
            raise ValueError('code-patch journal range invalid')
        matches = [s for s in route['steps'] if s.get('frame') == frame and
                   s.get('memory_write') == {'address': address, 'expected': patch['expected'], 'data': patch['data']}]
        if len(matches) != 1:
            raise ValueError('code patch does not match exactly one replay transaction')
        for offset, (old, new) in enumerate(zip(before, after)):
            physical = address+offset
            original.setdefault(physical, old)
            if current.get(physical, old) != old:
                raise ValueError('code-patch expected-byte chain is inconsistent')
            current[physical] = new
        previous = frame
    if current != original:
        raise ValueError('temporary code patch was not restored')
    return original


def select(capture, canonical, max_identities=None):
    retained, excluded = [], []
    for observation in capture['observations']:
        bad = any(p in canonical and value != canonical[p]
                  for p, value in zip(observation['physical'], observation['data']))
        (excluded if bad else retained).append(observation)
    excluded_hits = sum(o['native_hits']+o['interpreted_hits'] for o in excluded)
    selected = dict(capture, observations=retained,
                    retired_instructions=capture['retired_instructions']-excluded_hits)
    if max_identities is not None:
        if type(max_identities) is not int or not 1 <= max_identities <= 65536:
            raise ValueError('identity limit must be 1..65536')
        ranked = sorted(retained, key=lambda o: (-(o['native_hits']+o['interpreted_hits']),
                                                o['mpr'], o['pc'], o['data']))
        cold = ranked[max_identities:]
        selected['observations'] = ranked[:max_identities]
        selected['retired_instructions'] -= sum(o['native_hits']+o['interpreted_hits'] for o in cold)
    return selected, excluded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('tool-root', 'route', 'capture', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--max-identities', type=int, default=2048)
    parser.add_argument('--expected-revision', help='explicit clean development tool commit')
    args = parser.parse_args()
    tool = args.tool_root.resolve(strict=True)
    verification = [sys.executable, str(ROOT/'scripts/verify_tool.py'), '--tool-root', str(tool)]
    if args.expected_revision:
        verification += ['--expected-revision', args.expected_revision]
    identity = json.loads(subprocess.check_output(verification, text=True))
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(tool))
    from pcerecomp.capture import load_capture, validate_capture
    capture, capture_hash = load_capture(args.capture)
    route_raw = args.route.read_bytes()
    if len(route_raw) > 4*1024*1024:
        raise ValueError('route exceeds four MiB')
    route = json.loads(route_raw)
    canonical = canonical_bytes(route)
    selected, excluded = select(capture, canonical, args.max_identities)
    validate_capture(selected)
    args.out.mkdir(parents=True, exist_ok=False)
    raw = (json.dumps(selected, separators=(',', ':'))+'\n').encode()
    (args.out/'selected.json').write_bytes(raw)
    receipt = {'schema': 1, 'tool_identity': identity, 'route_sha256': hashlib.sha256(route_raw).hexdigest(),
               'capture_sha256': capture_hash, 'selected_sha256': hashlib.sha256(raw).hexdigest(),
               'original_observations': len(capture['observations']),
               'retained_observations': len(selected['observations']),
               'maximum_identities': args.max_identities,
               'excluded_observations': len(excluded),
               'excluded_hits': sum(o['native_hits']+o['interpreted_hits'] for o in excluded),
               'excluded_identities': excluded, 'canonical_patch_bytes': canonical,
               'observed_hit_fraction': sum(o['native_hits']+o['interpreted_hits'] for o in selected['observations']) / capture['retired_instructions'],
               'cold_identities_not_selected': len(capture['observations'])-len(excluded)-len(selected['observations']),
               'hottest_identities': [dict(pc=o['pc'], mpr=o['mpr'], physical=o['physical'],
                                           source_sha256=hashlib.sha256(bytes(o['data'])).hexdigest(),
                                           native_hits=o['native_hits'], interpreted_hits=o['interpreted_hits'])
                                      for o in selected['observations'][:16]],
               'scope': 'Frequency-ranked subset of observed original-code identities. Identities conflicting with verified restored original bytes are excluded, then cold identities outside the selected limit are left interpreted. Selected retirement total subtracts all removed hits; original dropped/unreadable counts remain unchanged. This subset is not a complete-route profile or campaign proof.'}
    (args.out/'selection.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('Selected', len(selected['observations']), 'identities; excluded',len(excluded))


if __name__ == '__main__':
    main()
