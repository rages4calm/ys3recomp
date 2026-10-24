"""Authored source-profile unions validated by the unchanged shared decoder."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.merge_observations import (ROOT, U64, compose, load_capture_api, merge_captures,
                                        read_manifest, strict_json, verify_inputs)

TOOL = ROOT / json.loads((ROOT / 'toolchain.json').read_text(encoding='utf-8'))['tool']['checkout']


def observation(pc=0x4000, mpr=None, data=None, native=2, interpreted=3):
    mapping = [0, 1, 2, 3, 4, 5, 6, 7] if mpr is None else mpr.copy()
    raw = [0xEA] if data is None else data.copy()
    return {'pc': pc, 'mpr': mapping,
            'physical': [mapping[((pc + offset) & 65535) >> 13] * 8192 + ((pc + offset) & 8191)
                         for offset in range(len(raw))],
            'data': raw, 'native_hits': native, 'interpreted_hits': interpreted}


def capture(items=None, abi=13, capacity=65536):
    items = [observation()] if items is None else copy.deepcopy(items)
    return {'schema': 1, 'runtime_abi': abi, 'capacity': capacity, 'complete': True,
            'dropped_instructions': 0, 'unreadable_instructions': 0,
            'retired_instructions': sum(item['native_hits'] + item['interpreted_hits'] for item in items),
            'observations': items}


def write(path, value):
    path.write_text(json.dumps(value) + '\n', encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MergeObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (TOOL / 'pcerecomp/capture.py').is_file():
            raise unittest.SkipTest('The pinned upstream checkout is required for shared-decoder profile tests')
        cls.api = load_capture_api(TOOL)

    def merge(self, captures, abi=13):
        return merge_captures(captures, abi, self.api.validate_capture)

    def test_exact_identity_shared_variant_and_full_mpr_preserved(self):
        first = capture([observation(), observation(pc=0x4001)], abi=12)
        mapping = [0, 1, 2, 3, 4, 5, 6, 99]  # Same fetched bank, distinct full context.
        second = capture([observation(native=7, interpreted=11),
                          observation(data=[0x18]), observation(mpr=mapping)])
        before = copy.deepcopy([first, second])
        merged, summary = self.merge([first, second])
        self.assertEqual([first, second], before)
        self.assertEqual(len(merged['observations']), 4)
        shared = next(item for item in merged['observations'] if item['pc'] == 0x4000
                      and item['data'] == [0xEA] and item['mpr'][-1] == 7)
        self.assertEqual((shared['native_hits'], shared['interpreted_hits']), (9, 14))
        self.assertEqual(merged['retired_instructions'], 38)
        self.assertEqual(summary['native_hits'] + summary['interpreted_hits'], 38)
        self.assertEqual(summary['new_identities_over_first_capture'], 2)
        self.assertEqual([epoch['runtime_abi'] for epoch in summary['input_epochs']], [12, 13])
        self.assertFalse(summary['execution_evidence'])
        self.assertFalse(summary['native_gain_qualified'])

    def test_explicit_output_abi_default_does_not_follow_first_input(self):
        inputs = [capture(abi=12), capture([observation(pc=0x4001)], abi=13)]
        for abi in (12, 13):
            self.assertEqual(self.merge(inputs, abi)[0]['runtime_abi'], abi)
        for abi in (True, 14, None, '13'):
            with self.subTest(abi=abi), self.assertRaises(ValueError):
                self.merge(inputs, abi)
        inputs[1]['runtime_abi'] = 14
        with self.assertRaises(ValueError):
            self.merge(inputs)

    def test_abi16_union_retains_original_epochs_and_brk_signature(self):
        first = capture(abi=13)
        mapping = [248, 249, 250, 251, 0, 0, 0, 1]
        second = capture([observation(pc=65535, mpr=mapping, data=[0, 0x7F],
                                      native=0, interpreted=9)], abi=16)
        before = copy.deepcopy([first, second])
        merged, summary = self.merge([first, second], 16)
        self.assertEqual([first, second], before)
        self.assertEqual(merged['runtime_abi'], 16)
        self.assertEqual([x['runtime_abi'] for x in summary['input_epochs']], [13, 16])
        self.assertEqual(merged['retired_instructions'], 14)
        brk = next(x for x in merged['observations'] if x['pc'] == 65535)
        self.assertEqual(brk, second['observations'][0])
        self.assertEqual(brk['physical'], [16383, 248 << 13])
        for output in (12, 13):
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.merge([first, second], output)
        second['observations'][0]['data'].pop()
        second['observations'][0]['physical'].pop()
        with self.assertRaises(ValueError):
            self.merge([first, second], 16)

    def test_abi16_manifest_requires_exact_reviewed_source_before_composition(self):
        with tempfile.TemporaryDirectory() as folder:
            path, manifest, output = self.fixture(folder)
            manifest['output_runtime_abi'] = 16
            write(path, manifest)
            identity = {'runtime_abi': 16, 'revision':
                '3bd06b5055c92e9f368aab7023098ff8aa796854', 'tracked_source_clean': True,
                'shared_source_identity': {'revision': '3bd06b5055c92e9f368aab7023098ff8aa796854',
                'source_sha256': '720e3c1e980e3ad9d03b28cb4b31db696fe3bb27e687c0cf19bc3d0f3f1c9440',
                'source_files': 54}}
            for mutate in (lambda x: x.update(runtime_abi=13),
                           lambda x: x.update(revision='0' * 40),
                           lambda x: x.update(tracked_source_clean=False),
                           lambda x: x['shared_source_identity'].update(source_sha256='0' * 64),
                           lambda x: x['shared_source_identity'].update(source_files=54.0)):
                changed = copy.deepcopy(identity)
                mutate(changed)
                with patch('scripts.merge_observations.subprocess.check_output',
                           return_value=json.dumps(changed)):
                    with self.assertRaisesRegex(ValueError, 'exact reviewed'):
                        compose(path, TOOL, output)
                self.assertFalse(output.exists())
            with patch('scripts.merge_observations.subprocess.check_output',
                       return_value=json.dumps(identity)):
                result = compose(path, TOOL, output)
            self.assertEqual(result['output_capture_runtime_abi'], 16)
            self.assertEqual([x['runtime_abi'] for x in result['inputs']], [12, 13])
            self.assertIn('not a single execution', result['profile_format_semantics'])
            self.assertFalse(result['execution_evidence'])

    def test_incomplete_loss_inconsistent_totals_and_bad_mapping_rejected(self):
        for mutate in (lambda value: value.update(complete=False, dropped_instructions=1,
                                                   retired_instructions=6),
                       lambda value: value.update(complete=False, unreadable_instructions=1,
                                                   retired_instructions=6),
                       lambda value: value.update(retired_instructions=6),
                       lambda value: value['observations'][0]['physical'].__setitem__(0, 0),
                       lambda value: value['observations'][0].update(extra_field=1)):
            value = capture()
            mutate(value)
            with self.assertRaises(ValueError):
                self.merge([capture(), value])

    def test_retired_and_identity_combined_counts_overflow_rejected(self):
        for inputs in ([capture([observation(native=U64, interpreted=0)]), capture()],
                       [capture([observation(native=U64 - 2, interpreted=2)]),
                        capture([observation(native=0, interpreted=1)])]):
            with self.assertRaisesRegex(ValueError, 'overflow'):
                self.merge(inputs)

    def test_uint64_boundary_is_exact_and_no_tier_reclassification(self):
        merged, summary = self.merge([capture([observation(native=U64 - 1, interpreted=0)]),
                                      capture([observation(native=0, interpreted=1)])])
        self.assertEqual(merged['retired_instructions'], U64)
        self.assertEqual(summary['native_hits'], U64 - 1)
        self.assertEqual(summary['interpreted_hits'], 1)

    def test_capacity_exact_boundary_and_overflow_fail_without_truncation(self):
        # One-byte authored NOPs across the logical address space, then a new
        # full-MPR context for an already used logical address.
        values = [observation(pc=pc, native=1, interpreted=0) for pc in range(65536)]
        first = capture(values)
        merged, _ = self.merge([first, capture([observation(native=1, interpreted=0)])])
        self.assertEqual(len(merged['observations']), 65536)
        self.assertEqual(merged['capacity'], 65536)
        mapping = [0, 1, 2, 3, 4, 5, 6, 99]
        with self.assertRaisesRegex(ValueError, 'capacity exceeds'):
            self.merge([first, capture([observation(mpr=mapping)])])

    def fixture(self, folder):
        root = Path(folder)
        source = root / 'input'
        source.mkdir()
        proof = source / 'execution.json'
        proof_hash = write(proof, {'synthetic': True, 'window': [0, 10]})
        inputs = []
        for index in range(2):
            path = source / ('capture' + str(index) + '.json')
            digest = write(path, capture([observation(pc=0x4000 + index)], abi=12 + index))
            inputs.append({'capture': {'path': path.name, 'sha256': digest},
                           'epoch': {'label': 'authored-' + str(index),
                                     'window': {'start_frame': 0, 'end_frame': 10},
                                     'evidence': [{'path': proof.name, 'sha256': proof_hash}]}})
        manifest = {'schema': 1, 'kind': 'ys3-observation-union', 'output_runtime_abi': 13, 'inputs': inputs}
        path = source / 'manifest.json'
        write(path, manifest)
        return path, manifest, root / 'output'

    def test_manifest_exact_schema_hash_provenance_and_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            path, value, _ = self.fixture(folder)
            loaded, entries, hashes = read_manifest(path)
            self.assertEqual(loaded, value)
            self.assertEqual(entries[0][1], value['inputs'][0]['epoch'])
            self.assertEqual(len(hashes), 4)
            for mutate in (lambda data: data.update(unexpected=1),
                           lambda data: data['inputs'][0]['epoch'].update(extra=1),
                           lambda data: data['inputs'][0]['epoch']['window'].update(end_frame=0),
                           lambda data: data['inputs'][0]['capture'].update(sha256='a' * 64),
                           lambda data: data['inputs'][1].update(capture=data['inputs'][0]['capture']),
                           lambda data: data['inputs'][0]['epoch'].update(evidence=[])):
                changed = copy.deepcopy(value)
                mutate(changed)
                write(path, changed)
                with self.assertRaises(ValueError):
                    read_manifest(path)
        for raw in ('{"schema":1,"schema":1}', '{"number":NaN}'):
            with self.assertRaises(ValueError):
                strict_json(raw)

    def test_inputs_rehashed_and_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path, _, _ = self.fixture(folder)
            _, entries, hashes = read_manifest(path)
            verify_inputs(hashes)
            entries[0][0].write_text('{}')
            with self.assertRaisesRegex(ValueError, 'changed during'):
                verify_inputs(hashes)

    def test_fresh_output_and_all_epochs_retained_with_unchanged_upstream_api(self):
        with tempfile.TemporaryDirectory() as folder:
            path, value, output = self.fixture(folder)
            # Mock only Git/source-verification transport; all capture parsing
            # and instruction validation uses the real pinned upstream module.
            with patch('scripts.merge_observations.subprocess.check_output', return_value='{"fixture":"tool"}'):
                result = compose(path, TOOL, output)
                self.assertEqual(len(result['inputs']), 2)
                self.assertEqual(result['inputs'][0]['epoch'], value['inputs'][0]['epoch'])
                self.assertEqual(result['tool_identity'], result['tool_identity_after'])
                merged, digest = self.api.load_capture(output / 'observations.json')
                self.assertEqual(digest, result['capture_sha256'])
                self.assertEqual(merged['retired_instructions'], 10)
                self.assertEqual(json.loads((output / 'merge-receipt.json').read_text()), result)
                with self.assertRaisesRegex(ValueError, 'fresh'):
                    compose(path, TOOL, output)

    def test_output_inside_input_roots_and_tool_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path, _, output = self.fixture(folder)
            with self.assertRaisesRegex(ValueError, 'separate'):
                compose(path, TOOL, path.parent / 'output')
            with patch('scripts.merge_observations.subprocess.check_output', side_effect=['{"tool":1}', '{"tool":2}']):
                with self.assertRaisesRegex(ValueError, 'tool changed'):
                    compose(path, TOOL, output)
            self.assertFalse(output.exists())

    def test_input_mutation_after_tool_verification_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path, value, output = self.fixture(folder)
            calls = 0
            def identity(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    (path.parent / value['inputs'][0]['capture']['path']).write_text('{}')
                return '{"tool":1}'
            with patch('scripts.merge_observations.subprocess.check_output', side_effect=identity):
                with self.assertRaisesRegex(ValueError, 'changed during'):
                    compose(path, TOOL, output)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
