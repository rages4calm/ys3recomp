"""Strict frozen ABI16 selection and retained additive diagnostic checks."""
import copy
import unittest

from scripts.replay_route import (ABI16_TOOL, compare_status, runtime_audio_selection,
    runtime_audio_command, selected_audio, validate_runtime_desktop_mode, validate_runtime_diagnostics)
from tests.test_abi15_replay import audio, selection
from tests.test_compat16_contract import fixture as diagnostic
from tests.test_replay import route_fixture


def identity():
    return {'runtime_abi': 16, 'revision': ABI16_TOOL['revision'], 'tracked_source_clean': True,
            'shared_source_identity': {'revision': ABI16_TOOL['revision'], 'source_files': 54,
                                      'source_sha256': ABI16_TOOL['source_sha256']}}


def status():
    value = copy.deepcopy(route_fixture()['last_status'])
    value['ticks'] = 100
    value['host']['unknown_commands'] = 2
    return value


class Abi16ReplayTests(unittest.TestCase):
    def test_frozen_source_identity_and_default_audio(self):
        self.assertEqual(runtime_audio_selection(identity(), 'on', 'filtered', 48000), selection())
        self.assertIsNone(runtime_audio_selection(identity(), 'off'))
        for path, value in ((('revision',), '0' * 40), (('tracked_source_clean',), False),
                            (('runtime_abi',), 17), (('runtime_abi',), True),
                            (('shared_source_identity', 'source_files'), 53),
                            (('shared_source_identity', 'source_files'), 54.0),
                            (('shared_source_identity', 'source_sha256'), '0' * 64),
                            (('shared_source_identity', 'revision'), '0' * 40)):
            changed = identity()
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                runtime_audio_selection(changed, 'off')

    def test_current_audio_contract_remains_exact_in_both_modes(self):
        for timing in ('gear', 'legacy'):
            value = audio(timing)
            self.assertEqual(selected_audio(value, selection(timing), 100, runtime_abi=16), value)
            command = runtime_audio_command(['host'], 'on', 'output.wav', 100,
                'filtered', 48000, timing, runtime_abi=16)
            self.assertEqual(command[-2:], ['--audio-timing', timing])
        validate_runtime_desktop_mode(True, True, 'authored.toml', 'off', None, 16)
        with self.assertRaises(ValueError):
            validate_runtime_desktop_mode(True, True, 'authored.toml', 'off', 100, 16)

    def test_only_validated_added_diagnostic_is_separate_from_old_guest(self):
        expected = status()
        actual = copy.deepcopy(expected)
        actual['host']['cd_unknown'] = diagnostic()
        original = copy.deepcopy(actual)
        compare_status(expected, actual, audio_mode='off', runtime_abi=16)
        self.assertEqual(actual, original)
        for field in ('unreviewed_event', 'unexpected_generation'):
            changed = copy.deepcopy(actual)
            changed['host'][field] = 0
            with self.assertRaises(RuntimeError):
                compare_status(expected, changed, audio_mode='off', runtime_abi=16)
        changed = copy.deepcopy(actual)
        changed['host']['cpu']['mpr'][0] ^= 1
        with self.assertRaises(RuntimeError):
            compare_status(expected, changed, audio_mode='off', runtime_abi=16)

    def test_full_new_reference_keeps_exact_unknown_origin(self):
        expected = status()
        expected['host']['cd_unknown'] = diagnostic()
        actual = copy.deepcopy(expected)
        compare_status(expected, actual, audio_mode='off', runtime_abi=16)
        actual['host']['cd_unknown']['origin']['ticks'] -= 1
        with self.assertRaises(RuntimeError):
            compare_status(expected, actual, audio_mode='off', runtime_abi=16)

    def test_invalid_added_diagnostic_cannot_be_projected_away(self):
        expected = status()
        actual = copy.deepcopy(expected)
        actual['host']['cd_unknown'] = diagnostic()
        actual['host']['cd_unknown']['accepted_responses'] = 1
        with self.assertRaises(ValueError):
            compare_status(expected, actual, audio_mode='off', runtime_abi=16)
        actual['host']['cd_unknown'] = diagnostic()
        actual['host']['cd_unknown']['origin']['mpr'].pop()
        with self.assertRaises(ValueError):
            compare_status(expected, actual, audio_mode='off', runtime_abi=16)

    def test_host_and_runner_use_their_actual_existing_accepted_count(self):
        host = {'unknown_commands': 2, 'cd_unknown': diagnostic()}
        runner = {'scsi': {'unknown_commands': 2}, 'cd_unknown': diagnostic()}
        self.assertEqual(validate_runtime_diagnostics(host, 16, 100), diagnostic())
        self.assertEqual(validate_runtime_diagnostics(runner, 16, 100, runner=True), diagnostic())
        runner['scsi']['unknown_commands'] = 1
        with self.assertRaises(ValueError):
            validate_runtime_diagnostics(runner, 16, 100, runner=True)


if __name__ == '__main__':
    unittest.main()
