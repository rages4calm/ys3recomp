"""Synthetic declared-output checks; no ABI16 runtime or retail execution."""
import copy
import unittest

from scripts.compat16_contract import U64, validate_cd_unknown


def fixture():
    return {'accepted_responses': 2,
            'opcodes': [{'opcode': 0x42, 'attempts': 1}, {'opcode': 0xFE, 'attempts': 1}],
            'last_command': [0x42],
            'origin': {'pc': 0x1FFF, 'ticks': 90, 'mpr': [249, 250, 251, 248, 0, 0, 0, 0],
                       'physical_pc': (249 << 13) | 8191,
                       'fetch': [0x8D, 1, 0x18, None, 0xEA, None, 0]}}


class UnknownCdDiagnosticsTests(unittest.TestCase):
    def test_idle_diagnostics_and_copy_preserve_exact_fields(self):
        idle = {'accepted_responses': 0, 'opcodes': [], 'last_command': [], 'origin': None}
        self.assertEqual(validate_cd_unknown(idle, 0, observed_ticks=0), idle)
        original = fixture()
        checked = validate_cd_unknown(original, 2, observed_ticks=100)
        self.assertEqual(checked, original)
        checked['origin']['fetch'][0] = 0
        self.assertEqual(original['origin']['fetch'][0], 0x8D)

    def test_strict_fault_attempt_is_distinct_from_accepted_responses(self):
        value = fixture()
        value['accepted_responses'] = 0
        self.assertEqual(validate_cd_unknown(value, 0)['accepted_responses'], 0)
        value['origin'] = None
        self.assertIsNone(validate_cd_unknown(value, 0)['origin'])

    def test_last_unknown_need_not_be_latest_histogram_opcode(self):
        value = fixture()
        self.assertEqual(validate_cd_unknown(value, 2)['last_command'], [0x42])
        value['last_command'] = [0xFE]
        self.assertEqual(validate_cd_unknown(value, 2)['last_command'], [0xFE])

    def test_nullable_pure_fetch_is_retained_without_decoding_cdb(self):
        value = fixture()
        value['origin']['fetch'] = [None] * 7
        self.assertEqual(validate_cd_unknown(value, 2)['origin']['fetch'], [None] * 7)
        self.assertNotEqual(value['origin']['fetch'][0], value['last_command'][0])

    def test_mapped_alias_identity_is_not_canonical_backing_address(self):
        value = fixture()
        checked = validate_cd_unknown(value, 2, observed_ticks=90)
        self.assertEqual(checked['origin']['physical_pc'], (249 << 13) | 8191)
        value['origin']['physical_pc'] = (248 << 13) | 8191
        with self.assertRaises(ValueError):
            validate_cd_unknown(value, 2)

    def test_count_types_bounds_and_correlation_are_strict(self):
        for accepted in (True, 2.0, '2', -1, U64 + 1):
            with self.subTest(accepted=accepted), self.assertRaises(ValueError):
                validate_cd_unknown(fixture(), accepted)
            changed = fixture()
            changed['accepted_responses'] = accepted
            with self.assertRaises(ValueError):
                validate_cd_unknown(changed, 2)
        with self.assertRaises(ValueError):
            validate_cd_unknown(fixture(), 1)
        value = fixture()
        value['accepted_responses'] = 3
        with self.assertRaises(ValueError):
            validate_cd_unknown(value, 3)
        for count in (0, -1, True, 1.0, U64 + 1):
            value = fixture()
            value['opcodes'][0]['attempts'] = count
            with self.subTest(attempts=count), self.assertRaises(ValueError):
                validate_cd_unknown(value, 2)

    def test_unknown_histogram_rejects_known_duplicate_unsorted_and_invalid_opcodes(self):
        for opcode in (0, 3, 8, 0xD8, 0xD9, 0xDA, 0xDD, 0xDE, -1, 256, True, 2.0):
            value = fixture()
            value['opcodes'][0]['opcode'] = opcode
            with self.subTest(opcode=opcode), self.assertRaises(ValueError):
                validate_cd_unknown(value, 2)
        for change in (lambda v: v['opcodes'].reverse(),
                       lambda v: v['opcodes'].append(copy.deepcopy(v['opcodes'][-1])),
                       lambda v: v['opcodes'][0].update(extra=0)):
            value = fixture()
            change(value)
            with self.assertRaises(ValueError):
                validate_cd_unknown(value, 2)

    def test_last_command_must_be_bounded_and_counted(self):
        for command in (None, (), [], [0], [0x41], [True], [256], [0x42] * 17):
            value = fixture()
            value['last_command'] = command
            with self.subTest(command=command), self.assertRaises(ValueError):
                validate_cd_unknown(value, 2)
        value = fixture()
        value.update(accepted_responses=0, opcodes=[])
        with self.assertRaises(ValueError):
            validate_cd_unknown(value, 0)
        value['last_command'] = []
        with self.assertRaises(ValueError):
            validate_cd_unknown(value, 0)

    def test_origin_requires_exact_complete_mpr_fetch_and_mapped_pc(self):
        for key, invalid in (('pc', True), ('pc', 65536), ('ticks', -1), ('ticks', U64 + 1),
                             ('mpr', [0] * 7), ('mpr', [0] * 7 + [256]),
                             ('physical_pc', True), ('physical_pc', 0), ('fetch', None),
                             ('fetch', [0] * 6), ('fetch', [0] * 6 + [True]),
                             ('fetch', [0] * 6 + [256]), ('extra', 0)):
            value = fixture()
            value['origin'][key] = invalid
            with self.subTest(field=key, invalid=invalid), self.assertRaises(ValueError):
                validate_cd_unknown(value, 2)

    def test_origin_and_observation_clock_validation(self):
        for ticks in (True, 90.0, -1, U64 + 1):
            with self.subTest(ticks=ticks), self.assertRaises(ValueError):
                validate_cd_unknown(fixture(), 2, observed_ticks=ticks)
        with self.assertRaises(ValueError):
            validate_cd_unknown(fixture(), 2, observed_ticks=89)
        self.assertEqual(validate_cd_unknown(fixture(), 2, observed_ticks=90), fixture())

    def test_top_level_schema_extensions_do_not_disappear(self):
        for change in (lambda v: v.update(extra=0), lambda v: v.pop('origin'),
                       lambda v: v.update(opcodes={}), lambda v: v.update(origin=[])):
            value = fixture()
            change(value)
            with self.assertRaises(ValueError):
                validate_cd_unknown(value, 2)


if __name__ == '__main__':
    unittest.main()
