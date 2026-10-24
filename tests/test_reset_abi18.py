"""Authored ABI migration checks; no game assets or runtime hosts execute."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import replay_reset as r
from tests.test_reset_replay import contract as capture_contract, runner


class CaptureMigrationTests(unittest.TestCase):
    def test_explicit18_capture_preserves17_default_and_original_data(self):
        value, run, raw = capture_contract()
        original = copy.deepcopy((value, run, raw))
        r.validate_capture_contract(value, run, raw)
        with self.assertRaises(ValueError):
            r.validate_capture_contract(value, run, raw, expected_abi=18)
        self.assertEqual(original, (value, run, raw))
        value['runtime_abi'] = value['capture']['runtime_abi'] = raw['runtime_abi'] = 18
        r.validate_capture_contract(value, run, raw, expected_abi=18)
        with self.assertRaises(ValueError):
            r.validate_capture_contract(value, run, raw)

    def test_mixed_capture_headers_loss_and_unsupported_abi_reject(self):
        for mutation in ('header', 'raw', 'loss', 'tier'):
            value, run, raw = capture_contract()
            value['runtime_abi'] = value['capture']['runtime_abi'] = raw['runtime_abi'] = 18
            if mutation == 'header': value['capture']['runtime_abi'] = 17
            if mutation == 'raw': raw['runtime_abi'] = 17
            if mutation == 'loss': value['capture']['dropped_instructions'] = 1
            if mutation == 'tier': raw['observations'][0]['native_hits'] = 0
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                r.validate_capture_contract(value, run, raw, expected_abi=18)
        for abi in (True, 18.0, 16, 19):
            with self.subTest(abi=abi), self.assertRaises(ValueError):
                r.validate_capture_contract(value, run, raw, expected_abi=abi)

    def test_runner_forwards_selected_capture_abi_and_retains_guest_fields(self):
        value, _, raw = capture_contract()
        value['runtime_abi'] = value['capture']['runtime_abi'] = raw['runtime_abi'] = 18
        actual = runner(desktop=True)
        actual['code_capture_window'] = copy.deepcopy(value['window'])
        expected = r.normalize_runner(runner(desktop=True), desktop=True)
        self.assertEqual(expected, r.normalize_runner(actual, desktop=True,
                         capture_contract=value, expected_abi=18))
        with self.assertRaises(ValueError):
            r.normalize_runner(actual, desktop=True, capture_contract=value)
        actual['boot']['mapper'] = 'unexpected'
        with self.assertRaises(ValueError):
            r.normalize_runner(actual, desktop=True, capture_contract=value, expected_abi=18)


class ReviewedToolTests(unittest.TestCase):
    def test_cli_selects_finite_reviewed_tool_without_changing_default(self):
        argv = []
        for name in ('descriptor','build-dir','reference-launch','reference-receipt','protected-inputs','out',
                     'reference-launch-sha256','reference-receipt-sha256'):
            argv += ['--'+name, 'authored']
        self.assertIsNone(r.argument_parser().parse_args(argv).reviewed_tool)
        self.assertEqual('abi18', r.argument_parser().parse_args(argv+['--reviewed-tool','abi18']).reviewed_tool)

    def test_no_abi_only_or_crossed_source_trust(self):
        expected = copy.deepcopy(r.ABI18_TOOL)
        self.assertEqual(expected, r.reviewed_tool(expected))
        for key, bad in (('revision', 'a'*40), ('source_sha256', 'b'*64),
                         ('source_files', 57), ('source_files', 60.0), ('runtime_abi', 17)):
            value = dict(expected, **{key: bad})
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                r.reviewed_tool(value)
        self.assertEqual(17, r.TOOL['runtime_abi'])

    def test_verifier_receives_full18_identity_and_keeps17_default(self):
        for selected, explicit in ((r.TOOL, False), (r.ABI18_TOOL, True)):
            result = {'revision': selected['revision'], 'runtime_abi': selected['runtime_abi'],
                      'tracked_source_clean': True,
                      'shared_source_identity': {k: selected[k] for k in
                                                ('revision','source_sha256','source_files')}}
            with patch.object(r.subprocess, 'check_output', return_value=json.dumps(result)) as call:
                actual = r.verify_tool(Path('authored-tool'), selected) if explicit else r.verify_tool(Path('authored-tool'))
                self.assertEqual(result, actual)
                command = call.call_args.args[0]
                for flag, wanted in (('--expected-revision', selected['revision']),
                                     ('--expected-abi', str(selected['runtime_abi'])),
                                     ('--expected-source-sha256', selected['source_sha256'])):
                    self.assertEqual(wanted, command[command.index(flag)+1])


if __name__ == '__main__': unittest.main()
