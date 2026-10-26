"""Select observed original-code identities using the private assist journal.

The original capture is immutable. This produces a private subset and a separate
selection receipt, never relabeling excluded patch hits as capacity loss.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import re
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


def _original_require(condition, message):
    if not condition:
        raise ValueError(message)


def _original_integer(value, maximum, label):
    _original_require(type(value) is int and 0 <= value <= maximum,
                      label + ' requires a bounded exact integer')
    return value


def _original_hex(value):
    _original_require(type(value) is str and
                      re.fullmatch(r'(?:[0-9a-fA-F]{2}){1,256}', value) is not None,
                      'Journal bytes require one to 256 hexadecimal bytes')
    return bytes.fromhex(value)


def _original_journal(route):
    """Add strict typing/source-overlap checks without changing legacy journal APIs."""
    _original_require(type(route) is dict, 'Original selection requires a route')
    assistance = route.get('assistance')
    _original_require(type(assistance) is dict and
                      assistance.get('jump_patch_active') is False,
                      'Explicit restored code-patch journal required')
    patches, steps, last = assistance.get('code_patches'), route.get('steps'), route.get('last_status')
    _original_require(type(patches) is list and 0 < len(patches) <= 65536 and
                      type(steps) is list and type(last) is dict,
                      'Bounded patch journal, route steps and final status required')
    final = _original_integer(last.get('frame'), (1 << 64)-1, 'Final frame')
    previous, journal = -1, set()
    for patch in patches:
        _original_require(type(patch) is dict and
                          {'frame', 'physical', 'expected', 'data'} <= set(patch) <=
                          {'frame', 'physical', 'expected', 'data', 'reason'},
                          'Invalid code-patch journal fields')
        frame = _original_integer(patch['frame'], final, 'Patch frame')
        address = _original_integer(patch['physical'], 0x1fffff, 'Patch address')
        before, after = _original_hex(patch['expected']), _original_hex(patch['data'])
        _original_require(frame >= previous and len(before) == len(after) and
                          address+len(before) <= 0x200000 and
                          ('reason' not in patch or type(patch['reason']) is str),
                          'Invalid ordered code-patch transaction')
        key = (frame, address, patch['expected'], patch['data'])
        _original_require(key not in journal, 'Duplicate code-patch journal transaction')
        journal.add(key)
        previous = frame
    writes = []
    for step in steps:
        _original_require(type(step) is dict, 'Invalid route step')
        if 'memory_write' not in step:
            continue
        frame = _original_integer(step.get('frame'), final, 'Write frame')
        edit = step['memory_write']
        _original_require(type(edit) is dict and set(edit) == {'address', 'expected', 'data'},
                          'Invalid replay write fields')
        address = _original_integer(edit['address'], 0x1fffff, 'Write address')
        before, after = _original_hex(edit['expected']), _original_hex(edit['data'])
        _original_require(len(before) == len(after) and address+len(before) <= 0x200000,
                          'Invalid replay write range')
        writes.append((frame, address, edit['expected'], edit['data'], len(before)))
    canonical = canonical_bytes(route)
    for frame, address, before, after, length in writes:
        if any(p in canonical for p in range(address, address+length)):
            _original_require((frame, address, before, after) in journal,
                              'Unjournaled edit overlaps restored source')
    return canonical, writes


def select_original(capture, route, approved_identities, *, validate_capture):
    """Return a derived original-only profile and an explicit exclusion ledger.

    The caller supplies the verified upstream capture validator (including its
    decoder), and separately binds approval authority to fresh capture/reference
    evidence. Approval rows contain exactly pc/mpr/physical/data. This API neither
    emits code nor makes the derived subset a raw execution capture. The legacy
    select() function and CLI defaults remain unchanged.
    """
    _original_require(callable(validate_capture), 'Verified capture validator required')
    original = copy.deepcopy(capture)
    validated = validate_capture(copy.deepcopy(original))
    _original_require(type(validated) is list and type(original) is dict and
                      len(validated) == len(original['observations']),
                      'Upstream validator must return canonical observations')
    canonical, writes = _original_journal(route)
    observations = original['observations']
    _original_require(type(approved_identities) is list and
                      0 < len(approved_identities) <= len(observations),
                      'Nonempty bounded explicit identity approvals required')
    approvals = copy.deepcopy(approved_identities)
    for row in approvals:
        _original_require(type(row) is dict and set(row) == {'pc', 'mpr', 'physical', 'data'},
                          'Approval requires exact full source identity fields')
    approval_capture = dict(original, observations=[dict(row, native_hits=0, interpreted_hits=1)
                                                  for row in approvals],
                            retired_instructions=len(approvals), dropped_instructions=0,
                            unreadable_instructions=0, complete=True)
    validate_capture(approval_capture)

    def key(item):
        return item['pc'], tuple(item['mpr']), tuple(item['physical']), tuple(item['data'])

    observed = {key(item) for item in observations}
    approved = set()
    for row in approvals:
        identity = key(row)
        overlap = [p for p in row['physical'] if p in canonical]
        _original_require(identity not in approved, 'Duplicate approved identity')
        _original_require(overlap and identity in observed,
                          'Approval must be an observed journal-overlapping identity')
        _original_require(all(p not in canonical or byte == canonical[p]
                              for p, byte in zip(row['physical'], row['data'])),
                          'Approved source differs from restored canonical bytes')
        approved.add(identity)
    fetched = {p for item in observations for p in item['physical']}
    for _, address, _, _, length in writes:
        _original_require(not any(p in fetched and p not in canonical
                                  for p in range(address, address+length)),
                          'Unjournaled assist overlaps observed source outside restored spans')
    untouched, allowed, excluded = [], [], []
    for item in observations:
        overlap = any(p in canonical for p in item['physical'])
        if not overlap:
            untouched.append(item)
        elif key(item) in approved:
            allowed.append(item)
        else:
            reason = ('noncanonical-source-bytes' if any(
                p in canonical and byte != canonical[p]
                for p, byte in zip(item['physical'], item['data']))
                else 'unapproved-original-identity')
            excluded.append(dict(item, reason=reason))
    retained = {key(item) for item in untouched+allowed}
    selected = copy.deepcopy(original)
    selected['observations'] = [copy.deepcopy(item) for item in observations if key(item) in retained]
    removed = sum(item['native_hits']+item['interpreted_hits'] for item in excluded)
    selected['retired_instructions'] -= removed
    validate_capture(copy.deepcopy(selected))

    def counts(items):
        native = sum(item['native_hits'] for item in items)
        interpreted = sum(item['interpreted_hits'] for item in items)
        return {'observations': len(items), 'native_hits': native,
                'interpreted_hits': interpreted, 'retired_instructions': native+interpreted}

    spans = []
    for physical in sorted(canonical):
        if spans and spans[-1]['start']+spans[-1]['length'] == physical:
            spans[-1]['length'] += 1
        else:
            spans.append({'start': physical, 'length': 1})
    ledger = {'schema': 1, 'kind': 'original-only-source-selection',
              'derived_profile': True, 'raw_capture_unchanged': True,
              'input_counts': counts(observations),
              'selected_counts': counts(selected['observations']),
              'excluded_counts': counts(excluded), 'untouched_counts': counts(untouched),
              'approved_counts': counts(allowed), 'approved_identities': approvals,
              'excluded_identities': excluded, 'journal_spans': spans,
              'canonical_bytes': [{'physical': p, 'byte': canonical[p]} for p in sorted(canonical)],
              'input_capture_header': {k: copy.deepcopy(v) for k, v in original.items() if k != 'observations'},
              'selected_capture_header': {k: copy.deepcopy(v) for k, v in selected.items() if k != 'observations'},
              'all_untouched_keys_retained': True,
              'scope': 'Derived original-only source selection, not a raw execution capture. '
                       'Excluded source hits are explicitly subtracted; actual ABI, capacity, '
                       'dropped/unreadable counters and completeness are preserved, not relabeled.'}
    return selected, ledger


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
