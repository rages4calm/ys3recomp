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


if __name__ == '__main__': unittest.main()
