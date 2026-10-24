"""Reviewed ABI17 payload regression keeps existing guest/audio contracts strict."""
import copy
from pathlib import Path
import unittest

from scripts.replay_route import (ABI17_TOOL, compare_status,
    runtime_audio_command, runtime_audio_selection, selected_audio,
    validate_runtime_desktop_mode, verify_tool_root)
from tests.test_abi15_replay import audio, selection
from tests.test_abi16_replay import status
from tests.test_compat16_contract import fixture as diagnostic


def identity():
    return {'runtime_abi': 17, 'revision': ABI17_TOOL['revision'], 'tracked_source_clean': True,
            'shared_source_identity': {'revision': ABI17_TOOL['revision'], 'source_files': 54,
                                      'source_sha256': ABI17_TOOL['source_sha256']}}


class Abi17ReplayTests(unittest.TestCase):
    def test_exact_source_required_for_payload_audio_and_off(self):
        self.assertEqual(runtime_audio_selection(identity(), 'on', 'filtered', 48000), selection())
        self.assertIsNone(runtime_audio_selection(identity(), 'off'))
        for change in (lambda x: x.update(runtime_abi=17.0), lambda x: x.update(runtime_abi=18),
                       lambda x: x.update(revision='0' * 40), lambda x: x.update(tracked_source_clean=False),
                       lambda x: x['shared_source_identity'].update(source_files=54.0),
                       lambda x: x['shared_source_identity'].update(source_sha256='0' * 64),
                       lambda x: x['shared_source_identity'].update(revision='0' * 40)):
            value=identity(); change(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                runtime_audio_selection(value, 'off')

    def test_same_audio_schema_is_fully_validated_and_forwarded(self):
        for timing in ('gear', 'legacy'):
            value=audio(timing)
            self.assertEqual(selected_audio(value, selection(timing), 100, runtime_abi=17), value)
            command=runtime_audio_command(['host'], 'on', 'result.wav', 100,
                'filtered', 48000, timing, runtime_abi=17)
            self.assertEqual(command[-2:], ['--audio-timing', timing])
            value['processing']['latency_source_frames']=0
            with self.assertRaises(ValueError):
                selected_audio(value, selection(timing), 100, runtime_abi=17)
        validate_runtime_desktop_mode(True, True, 'authored.toml', 'off', None, 17)
        with self.assertRaises(ValueError):
            validate_runtime_desktop_mode(True, True, 'authored.toml', 'off', 100, 17)

    def test_payload_diagnostics_preserve_every_existing_guest_field(self):
        expected=status();expected['host']['cd_unknown']=diagnostic()
        actual=copy.deepcopy(expected)
        compare_status(expected, actual, audio_mode='off', runtime_abi=17)
        for change in (lambda x: x['host']['cpu']['mpr'].pop(),
                       lambda x: x['host'].update(unexpected_generation=1),
                       lambda x: x['host'].update(boot={'mode':'system-card-reset'}),
                       lambda x: x['host']['cd_unknown']['origin'].update(ticks=99)):
            changed=copy.deepcopy(actual);change(changed)
            with self.subTest(changed=changed), self.assertRaises((RuntimeError, ValueError)):
                compare_status(expected, changed, audio_mode='off', runtime_abi=17)
        actual['host']['cd_unknown']['accepted_responses']=1
        with self.assertRaises(ValueError):
            compare_status(expected, actual, audio_mode='off', runtime_abi=17)

    def test_explicit_reviewed17_verifies_real_clean_checkout(self):
        tool=Path(__file__).resolve().parents[1]/'.deps/pcenginerecomp-abi17'
        if not tool.is_dir():self.skipTest('Reviewed ABI17 checkout required')
        checked=verify_tool_root(tool, ABI17_TOOL['revision'])
        self.assertEqual(checked, identity())


if __name__=='__main__':
    unittest.main()
