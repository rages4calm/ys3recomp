"""Authored source-span policy only; shared emission stays upstream."""
import copy
import unittest

from scripts.expand_native import audit_assist_source, excluded_spans


def route():
    patches = [{'frame': 10, 'physical': 4096, 'expected': 'eaea', 'data': '8080'},
               {'frame': 20, 'physical': 4096, 'expected': '8080', 'data': 'eaea'}]
    return {'assistance': {'jump_patch_active': False, 'code_patches': patches},
            'last_status': {'frame': 30},
            'steps': [{'frame': p['frame'], 'memory_write': {'address': p['physical'],
                       'expected': p['expected'], 'data': p['data']}} for p in patches]}


class ExpansionPolicyTests(unittest.TestCase):
    def test_entire_restored_span_is_excluded_without_mutating_journal(self):
        value = route()
        before = copy.deepcopy(value)
        self.assertEqual(excluded_spans(value), ((4096, 2),))
        self.assertEqual(value, before)

    def test_disjoint_source_spans_are_not_widened_to_unrelated_bytes(self):
        value = route()
        extra = copy.deepcopy(value['assistance']['code_patches'])
        for patch in extra:
            patch['physical'] += 16
        for patch in extra:
            value['steps'].append({'frame': patch['frame'], 'memory_write': {
                'address': patch['physical'], 'expected': patch['expected'], 'data': patch['data']}})
        value['assistance']['code_patches'] = sorted(value['assistance']['code_patches'] + extra,
                                                    key=lambda p: p['frame'])
        self.assertEqual(excluded_spans(value), ((4096, 2), (4112, 2)))

    def test_active_or_unrestored_patch_is_rejected(self):
        value = route()
        value['assistance']['jump_patch_active'] = True
        with self.assertRaises(ValueError):
            excluded_spans(value)
        value = route()
        value['assistance']['code_patches'].pop()
        with self.assertRaises(ValueError):
            excluded_spans(value)

    def test_all_observed_source_edits_are_excluded(self):
        value = route()
        capture = {'observations': [{'physical': [4095, 4096]}, {'physical': [4097, 5000]}]}
        result = audit_assist_source(capture, value, excluded_spans(value))
        self.assertEqual(result['edit_transactions'], 2)
        self.assertEqual(len(result['source_overlaps']), 2)
        self.assertTrue(result['all_observed_assist_source_overlaps_excluded'])

    def test_unexcluded_operand_or_other_mapping_source_edit_is_rejected(self):
        value = route()
        value['steps'].append({'frame': 25, 'memory_write': {
            'address': 8192, 'expected': 'eaea', 'data': '8080'}})
        capture = {'observations': [{'physical': [8191, 8192]}]}
        with self.assertRaisesRegex(ValueError, 'outside excluded spans'):
            audit_assist_source(capture, value, excluded_spans(value))

    def test_data_assist_outside_observed_code_does_not_widen_exclusions(self):
        value = route()
        value['steps'].append({'frame': 25, 'memory_write': {
            'address': 12288, 'expected': '01', 'data': '02'}})
        capture = {'observations': [{'physical': [4096]}]}
        result = audit_assist_source(capture, value, excluded_spans(value))
        self.assertEqual(result['edit_transactions'], 3)
        self.assertEqual(len(result['source_overlaps']), 2)
        self.assertEqual(excluded_spans(value), ((4096, 2),))


if __name__ == '__main__':
    unittest.main()
