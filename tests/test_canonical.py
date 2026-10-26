import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('canonical', Path(__file__).resolve().parents[1]/'scripts/select_canonical.py')
canonical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(canonical)


def route():
    patches = [{'frame': 10, 'physical': 4096, 'expected': 'eaea', 'data': '8080'},
               {'frame': 20, 'physical': 4096, 'expected': '8080', 'data': 'eaea'}]
    return {'assistance': {'jump_patch_active': False, 'code_patches': patches},
            'last_status': {'frame': 30},
            'steps': [{'frame': p['frame'], 'memory_write': {'address': p['physical'],
                       'expected': p['expected'], 'data': p['data']}} for p in patches]}


class CanonicalSelectionTests(unittest.TestCase):
    def test_restored_expected_byte_chain(self):
        self.assertEqual(canonical.canonical_bytes(route()), {4096: 234, 4097: 234})

    def test_unrestored_or_unjournaled_code_refused(self):
        r = route()
        r['assistance']['code_patches'].pop()
        with self.assertRaises(ValueError): canonical.canonical_bytes(r)
        r = route()
        r['steps'].pop()
        with self.assertRaises(ValueError): canonical.canonical_bytes(r)

    def test_stale_expected_chain_refused(self):
        r = route()
        r['assistance']['code_patches'][1]['expected'] = '8181'
        r['steps'][1]['memory_write']['expected'] = '8181'
        with self.assertRaises(ValueError): canonical.canonical_bytes(r)

    def test_only_noncanonical_identity_excluded_and_counts_conserved(self):
        clean = {'physical': [4096], 'data': [234], 'native_hits': 2, 'interpreted_hits': 3}
        patch = dict(clean, data=[128], native_hits=0, interpreted_hits=7)
        other = dict(clean, physical=[8192], data=[128], native_hits=0, interpreted_hits=11)
        capture = {'observations': [clean, patch, other], 'retired_instructions': 26,
                   'dropped_instructions': 2, 'unreadable_instructions': 1, 'complete': False}
        before = copy.deepcopy(capture)
        selected, removed = canonical.select(capture, {4096: 234})
        self.assertEqual(removed, [patch])
        self.assertEqual(selected['observations'], [clean, other])
        self.assertEqual(selected['retired_instructions'], 19)
        self.assertEqual(selected['dropped_instructions'], 2)
        self.assertEqual(capture, before)

    def test_frequency_ranking_keeps_hot_original_identity(self):
        clean = {'pc': 1, 'mpr': [0]*8, 'physical': [4096], 'data': [234], 'native_hits': 2, 'interpreted_hits': 3}
        hot = dict(clean, pc=2, physical=[4097], interpreted_hits=9)
        capture = {'observations': [clean, hot], 'retired_instructions': 16}
        selected, excluded = canonical.select(capture, {}, 1)
        self.assertEqual(selected['observations'], [hot])
        self.assertEqual(selected['retired_instructions'], 11)
        self.assertEqual(excluded, [])


def original_route():
    patches = [{'frame': 5, 'physical': 0x4000, 'expected': 'eaea', 'data': '80fe'},
               {'frame': 10, 'physical': 0x4000, 'expected': '80fe', 'data': 'eaea'}]
    return {'assistance': {'jump_patch_active': False, 'code_patches': patches},
            'last_status': {'frame': 20}, 'steps': [
                {'frame': p['frame'], 'memory_write': {'address': p['physical'],
                 'expected': p['expected'], 'data': p['data']}} for p in patches]}


def original_capture():
    mapping = [0, 2, 3, 4, 5, 6, 7, 8]
    def observation(pc, data, native, interpreted, mpr=None):
        mpr = mapping if mpr is None else mpr
        return {'pc': pc, 'mpr': list(mpr), 'data': data,
                'physical': [(mpr[((pc+i)&65535)>>13]<<13) | ((pc+i)&8191)
                             for i in range(len(data))],
                'native_hits': native, 'interpreted_hits': interpreted}
    observations = [observation(0x2000, [0xea], 2, 3),
                    observation(0x2001, [0xea], 0, 7),
                    observation(0x2000, [0x80, 0xfe], 0, 11),
                    observation(0x2000, [0xea], 0, 13, mapping[:-1]+[9]),
                    observation(0x4000, [0xea], 17, 19)]
    return {'schema': 1, 'runtime_abi': 18, 'capacity': 32,
            'dropped_instructions': 0, 'unreadable_instructions': 0,
            'retired_instructions': 72, 'complete': True, 'observations': observations}


def approvals(capture):
    return [{key: copy.deepcopy(row[key]) for key in ('pc', 'mpr', 'physical', 'data')}
            for row in capture['observations'][:2]]


def fixture_validator(value):
    """Authored fixture schema/decoder stand-in; production supplies upstream's API.

    Only synthetic NOP, immediate-load and branch encodings are used here. This
    is not a replacement for the pinned toolkit's general instruction decoder.
    """
    def require(ok):
        if not ok: raise ValueError('Invalid authored capture fixture')
    def integer(x, limit): return type(x) is int and 0 <= x <= limit
    require(type(value) is dict and set(value) == {'schema', 'runtime_abi', 'capacity',
        'dropped_instructions', 'unreadable_instructions', 'retired_instructions', 'complete', 'observations'})
    require(type(value['schema']) is int and value['schema'] == 1)
    require(type(value['runtime_abi']) is int and value['runtime_abi'] in (17, 18))
    require(integer(value['capacity'], 65536) and value['capacity'] > 0)
    for field in ('dropped_instructions', 'unreadable_instructions', 'retired_instructions'):
        require(integer(value[field], (1 << 64)-1))
    require(type(value['complete']) is bool and value['complete'] ==
            (value['dropped_instructions'] == value['unreadable_instructions'] == 0))
    require(type(value['observations']) is list and len(value['observations']) <= value['capacity'])
    total = value['dropped_instructions'] + value['unreadable_instructions']; seen = set()
    for row in value['observations']:
        require(type(row) is dict and set(row) == {'pc', 'mpr', 'physical', 'data', 'native_hits', 'interpreted_hits'})
        require(integer(row['pc'], 65535) and type(row['mpr']) is list and len(row['mpr']) == 8)
        require(all(integer(x, 255) for x in row['mpr']))
        require(type(row['data']) is list and row['data'] and all(integer(x, 255) for x in row['data']))
        require(row['data'][0] in (0xea, 0xa9, 0x80))
        require(len(row['data']) == (1 if row['data'][0] == 0xea else 2))
        require(type(row['physical']) is list and all(integer(x, 0x1fffff) for x in row['physical']))
        require(row['physical'] == [
            (row['mpr'][((row['pc']+i)&65535)>>13]<<13) | ((row['pc']+i)&8191)
            for i in range(len(row['data']))])
        require(all(integer(row[k], (1 << 64)-1) for k in ('native_hits', 'interpreted_hits')))
        hits = row['native_hits']+row['interpreted_hits']; require(0 < hits <= (1 << 64)-1)
        key = row['pc'], tuple(row['mpr']), tuple(row['data']); require(key not in seen)
        seen.add(key); total += hits
    require(total == value['retired_instructions'])
    return copy.deepcopy(value['observations'])


class OriginalOnlySelectionTests(unittest.TestCase):
    def run_selection(self, capture=None, journal=None, approved=None, validator=fixture_validator):
        capture = original_capture() if capture is None else capture
        return canonical.select_original(capture, original_route() if journal is None else journal,
            approvals(capture) if approved is None else approved, validate_capture=validator)

    def test_exact_approved_originals_and_every_untouched_key_retained(self):
        capture = original_capture(); before = copy.deepcopy(capture)
        selected, ledger = self.run_selection(capture)
        self.assertEqual(selected['observations'], capture['observations'][:2]+capture['observations'][4:])
        self.assertEqual(selected['retired_instructions'], 48)
        self.assertEqual(ledger['excluded_counts'], {'observations': 2, 'native_hits': 0,
            'interpreted_hits': 24, 'retired_instructions': 24})
        self.assertEqual([r['reason'] for r in ledger['excluded_identities']],
                         ['noncanonical-source-bytes', 'unapproved-original-identity'])
        self.assertTrue(ledger['derived_profile']); self.assertTrue(ledger['all_untouched_keys_retained'])
        self.assertEqual(capture, before)
        selected['observations'][0]['mpr'][0] = 99
        self.assertEqual(capture, before)

    def test_loss_completeness_capacity_and_original_ABI_preserved(self):
        capture = original_capture(); capture.update(runtime_abi=17,
            dropped_instructions=2, unreadable_instructions=3, complete=False, retired_instructions=77)
        selected, ledger = self.run_selection(capture)
        for key in ('runtime_abi', 'capacity', 'dropped_instructions', 'unreadable_instructions', 'complete'):
            self.assertEqual(selected[key], capture[key])
        self.assertEqual(selected['retired_instructions'], 53)
        self.assertEqual(ledger['input_capture_header']['retired_instructions'], 77)
        self.assertEqual(ledger['selected_capture_header']['retired_instructions'], 53)

    def test_unapproved_canonical_overlap_excluded_not_silently_promoted(self):
        capture = original_capture(); selected, ledger = self.run_selection(capture, approved=approvals(capture)[:1])
        self.assertEqual(len(selected['observations']), 2)
        self.assertEqual(ledger['approved_counts']['retired_instructions'], 5)
        self.assertEqual(ledger['untouched_counts']['retired_instructions'], 36)

    def test_invalid_duplicate_unknown_or_noncanonical_approvals_rejected(self):
        capture = original_capture(); good = approvals(capture)
        bad = [[], good+[good[0]], [dict(good[0], pc=0x2002)],
               [dict(good[0], data=[0x80, 0xfe], physical=[0x4000, 0x4001])],
               [dict(good[0], extra='not-authority')],
               [{k: v for k, v in capture['observations'][4].items() if k not in ('native_hits', 'interpreted_hits')}]]
        for rows in bad:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.run_selection(capture, approved=rows)

    def test_wrong_MPR_approval_and_fetch_mapping_rejected(self):
        capture = original_capture(); good = approvals(capture)
        for mutation in (lambda r: r['mpr'].__setitem__(0, 33),
                         lambda r: r['mpr'].__setitem__(1, 4),
                         lambda r: r['physical'].__setitem__(0, 0x4001)):
            bad = copy.deepcopy(good); mutation(bad[0])
            with self.assertRaises(ValueError): self.run_selection(capture, approved=bad)

    def test_malformed_capture_and_counter_types_rejected(self):
        for mutate in (lambda c: c.update(complete=1), lambda c: c.update(runtime_abi=18.0),
                       lambda c: c.update(retired_instructions=73),
                       lambda c: c['observations'][0].update(native_hits=True),
                       lambda c: c['observations'][0].update(pc=8192.0),
                       lambda c: c['observations'][0]['data'].__setitem__(0, 0xa9),
                       lambda c: c['observations'].append(copy.deepcopy(c['observations'][0]))):
            capture = original_capture(); mutate(capture)
            with self.subTest(capture=capture), self.assertRaises(ValueError): self.run_selection(capture)

    def test_malformed_unrestored_stale_or_duplicate_journal_rejected(self):
        for mutate in (lambda r: r['assistance'].update(jump_patch_active=True),
                       lambda r: r['assistance']['code_patches'].pop(),
                       lambda r: r['assistance']['code_patches'][0].update(frame=True),
                       lambda r: r['assistance']['code_patches'][0].update(physical=16384.0),
                       lambda r: r['last_status'].update(frame=20.0),
                       lambda r: r['steps'][0].update(frame=5.0),
                       lambda r: r['assistance']['code_patches'][0].update(expected='ea ea'),
                       lambda r: r['assistance']['code_patches'][0].update(expected=True),
                       lambda r: r['assistance']['code_patches'].insert(1, copy.deepcopy(r['assistance']['code_patches'][0])),
                       lambda r: r['steps'].pop()):
            journal = original_route(); mutate(journal)
            with self.subTest(journal=journal), self.assertRaises(ValueError): self.run_selection(journal=journal)

    def test_unjournaled_write_inside_or_outside_canonical_source_rejected(self):
        for address in (0x4000, 0x6000):
            journal = original_route(); journal['steps'].append({'frame': 12,
                'memory_write': {'address': address, 'expected': 'ea', 'data': 'ea'}})
            with self.assertRaises(ValueError): self.run_selection(journal=journal)

    def test_non_source_data_assist_does_not_drop_untouched_code(self):
        journal = original_route(); journal['steps'].append({'frame': 12,
            'memory_write': {'address': 0x8000, 'expected': '01', 'data': '02'}})
        selected, ledger = self.run_selection(journal=journal)
        self.assertEqual(selected['observations'][-1]['pc'], 0x4000)
        self.assertEqual(ledger['untouched_counts']['observations'], 1)

    def test_all_eight_MPRs_remain_distinct_even_when_fetch_bytes_match(self):
        capture = original_capture(); selected, ledger = self.run_selection(capture)
        excluded = ledger['excluded_identities'][1]
        self.assertEqual(excluded['physical'], capture['observations'][0]['physical'])
        self.assertNotEqual(excluded['mpr'], capture['observations'][0]['mpr'])
        self.assertNotIn(excluded['mpr'], [r['mpr'] for r in selected['observations']])

    def test_full_cross_page_instruction_identity_not_just_overlap_byte(self):
        mapping = [0, 2, 7, 4, 5, 6, 7, 8]
        row = {'pc': 0x3fff, 'mpr': mapping, 'physical': [0x5fff, 0xe000],
               'data': [0xa9, 7], 'native_hits': 0, 'interpreted_hits': 2}
        capture = dict(original_capture(), observations=[row], retired_instructions=2)
        journal = original_route()
        for p in journal['assistance']['code_patches']:
            p['physical'] = 0x5fff
            p['expected'], p['data'] = ('a9', 'ea') if p['frame'] == 5 else ('ea', 'a9')
        journal['steps'] = [{'frame': p['frame'], 'memory_write': {'address': p['physical'],
            'expected': p['expected'], 'data': p['data']}} for p in journal['assistance']['code_patches']]
        approval = [{k: copy.deepcopy(v) for k, v in row.items() if k not in ('native_hits', 'interpreted_hits')}]
        selected, ledger = self.run_selection(capture, journal, approval)
        self.assertEqual(selected['observations'], [row])
        self.assertEqual(ledger['canonical_bytes'], [{'physical': 0x5fff, 'byte': 0xa9}])

    def test_verified_shared_validator_dependency_is_required_and_used(self):
        calls = []
        def validate(value):
            calls.append(copy.deepcopy(value)); return fixture_validator(value)
        self.run_selection(validator=validate)
        self.assertEqual(len(calls), 3)
        with self.assertRaises(ValueError): self.run_selection(validator=None)
        with self.assertRaises(ValueError): self.run_selection(validator=lambda value: None)


if __name__ == '__main__': unittest.main()
