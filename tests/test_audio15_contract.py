"""Authored ABI15 timing-wrapper fixtures; no retail or runtime DSP execution."""
import contextlib
import copy
import io
import unittest

from scripts import audio_contract as legacy
from scripts import dsp_contract as dsp
from scripts.audio15_contract import (audio_command, canonical, raw_projection,
                                      selection, validate_desktop, validate_headless)
from scripts.prepare_descriptor import build_parser, runtime_audio_lines
from tests.test_dsp_contract import filtered, hosted, raw


def timed(value, timing='gear'):
    result = copy.deepcopy(value)
    if timing == 'gear':
        result['timing'] = 'gear-v1'
    return result


class Audio15SelectionTests(unittest.TestCase):
    def test_enabled_defaults_are_explicit_gear_raw_44100(self):
        self.assertEqual(selection('on'), {'profile': 'raw', 'sample_rate': 44100, 'timing': 'gear'})
        self.assertEqual(selection('on', 'filtered', 48000, 'legacy'),
                         {'profile': 'filtered', 'sample_rate': 48000, 'timing': 'legacy'})
        self.assertIsNone(selection(None))
        self.assertIsNone(selection('off'))

    def test_explicit_selections_require_on_and_strict_types(self):
        for mode in (None, 'off'):
            for options in ({'timing': 'gear'}, {'profile': 'raw'}, {'rate': 44100}, {'wav_limit': 1}):
                with self.subTest(mode=mode, options=options), self.assertRaises(ValueError):
                    selection(mode, **options)
        for options in ({'timing': True}, {'timing': 'gear-v1'}, {'timing': 'Gear'},
                        {'profile': True}, {'profile': 'future'}, {'rate': True},
                        {'rate': 44100.0}, {'rate': 48000}, {'wav_limit': True}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                selection('on', **options)
        with self.assertRaises(ValueError):
            selection(True)

    def test_raw_and_filtered_timing_are_independent_choices(self):
        for profile, rate in (('raw', 44100), ('filtered', 44100), ('filtered', 48000)):
            for timing in ('gear', 'legacy'):
                with self.subTest(profile=profile, rate=rate, timing=timing):
                    self.assertEqual(selection('on', profile, rate, timing),
                                     {'profile': profile, 'sample_rate': rate, 'timing': timing})

    def test_argv_omission_preserves_existing_flags_and_explicit_timing_appends(self):
        command = ['runner', 'authored']
        self.assertEqual(audio_command(command, None, 'new.wav'), command)
        for mode in ('on', 'off'):
            self.assertEqual(audio_command(command, mode, 'new.wav'),
                             legacy.audio_command(command, mode, 'new.wav'))
        result = audio_command(command, 'on', 'new.wav', 1440000, 'filtered', 48000, 'legacy')
        self.assertEqual(result, dsp.audio_command(command, 'on', 'new.wav', 1440000, 'filtered', 48000)
                         + ['--audio-timing', 'legacy'])
        self.assertEqual(command, ['runner', 'authored'])

    def test_frozen_timing_rejected_even_when_audio_omitted_or_off(self):
        for mode in (None, 'off', 'on'):
            for argument in ('--audio-timing', '--audio-timing=gear', '--audio-timing=legacy'):
                with self.subTest(mode=mode, argument=argument), self.assertRaises(ValueError):
                    audio_command(['runner', argument, 'gear'], mode, 'new.wav')
        with self.assertRaises(ValueError):
            audio_command(['runner'], 'off', 'new.wav', timing='legacy')


class Audio15TelemetryTests(unittest.TestCase):
    def test_raw_gear_adds_only_timing_and_legacy_retains_old_core(self):
        original = raw()
        for timing in ('gear', 'legacy'):
            chosen = selection('on', timing=timing)
            value = timed(original, timing)
            self.assertEqual(validate_headless(value, chosen), value)
            self.assertEqual(canonical(value, chosen), original)
        self.assertEqual(set(timed(original)) - set(original), {'timing'})
        self.assertNotIn('timing', original)

    def test_gear_field_is_required_exact_and_forbidden_on_legacy(self):
        chosen = selection('on')
        with self.assertRaises(ValueError):
            validate_headless(raw(), chosen)
        for invalid in (None, True, 'gear', 'legacy', 1, 'gear-v2'):
            value = timed(raw())
            value['timing'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_headless(value, chosen)
        with self.assertRaises(ValueError):
            validate_headless(timed(raw()), selection('on', timing='legacy'))
        with self.assertRaises(ValueError):
            validate_headless(dict(raw(), timing=None), selection('on', timing='legacy'))

    def test_filtered_contract_delegation_and_copy_isolation(self):
        for rate in (44100, 48000):
            chosen = selection('on', 'filtered', rate)
            core = filtered(rate=rate)
            value = timed(core)
            result = validate_headless(value, chosen)
            self.assertEqual(canonical(result, chosen), dsp.validate_audio(core, dsp.selection('on', 'filtered', rate)))
            result['processing']['raw_peak'] = 1
            self.assertEqual(value['processing']['raw_peak'], 90)

    def test_processing_unknown_fields_loss_geometry_and_hash_checks_are_retained(self):
        chosen = selection('on', 'filtered', 48000)
        for key, invalid in (('future', 0), ('discarded_frames', 1), ('pcm_hash', 1 << 64),
                             ('frames', 159), ('sample_rate', 44100), ('peak', 32769)):
            value = timed(filtered())
            value[key] = invalid
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_headless(value, chosen)
        value = timed(filtered())
        value['processing']['future'] = 0
        with self.assertRaises(ValueError):
            validate_headless(value, chosen)
        for selected in (dict(chosen, future=0), {'profile': 'filtered', 'sample_rate': 48000},
                         dict(chosen, timing=True), dict(chosen, sample_rate=True)):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                validate_headless(timed(filtered()), selected)

    def test_wav_output_rate_cap_and_predrain_checkpoint_geometry_retained(self):
        chosen = selection('on', 'filtered', 48000)
        pending = timed(filtered(14700, wav_limit=20000, drained=7808))
        self.assertEqual(validate_headless(pending, chosen, 20000, True), pending)
        with self.assertRaises(ValueError):
            validate_headless(pending, chosen, 20000)
        pending['wav_frames'] -= 1
        with self.assertRaises(ValueError):
            validate_headless(pending, chosen, 20000, True)
        value = timed(filtered(wav_limit=5760000))
        validate_headless(value, chosen, 5760000)
        with self.assertRaises(ValueError):
            validate_headless(value, chosen, 5760001)

    def test_absent_pcm_off_handling_never_admits_disabled_object(self):
        self.assertIsNone(validate_headless(None, selection('off')))
        self.assertIsNone(canonical(None, None))
        for value, cap in ((raw(), None), (None, 1)):
            with self.subTest(value=value, cap=cap), self.assertRaises(ValueError):
                validate_headless(value, None, cap)
        with self.assertRaises(ValueError):
            validate_desktop(None, None, None)

    def test_desktop_gear_timing_validated_separately_then_host_removed(self):
        for timing in ('gear', 'legacy'):
            chosen = selection('on', 'filtered', 48000, timing)
            core = filtered(wav_limit=200)
            value = timed(hosted(core), timing)
            self.assertEqual(validate_desktop(value, chosen, 200), timed(core, timing))
            value['host']['device_format'] = True
            with self.assertRaises(ValueError):
                validate_desktop(value, chosen, 200)
        value = timed(hosted(raw()))
        self.assertEqual(validate_desktop(value, selection('on'), None), timed(raw()))
        value['host']['input_rate'] = 44100  # raw keeps its old six-field SDL shape
        with self.assertRaises(ValueError):
            validate_desktop(value, selection('on'), None)

    def test_desktop_predrain_pending_and_timing_mismatch_rejected(self):
        chosen = selection('on', 'filtered', 48000)
        core = filtered(14700, wav_limit=20000, drained=7808)
        value = timed(hosted(core, pending=8192))
        self.assertEqual(validate_desktop(value, chosen, 20000, True), timed(core))
        with self.assertRaises(ValueError):
            validate_desktop(value, chosen, 20000)
        value['timing'] = 'legacy'
        with self.assertRaises(ValueError):
            validate_desktop(value, chosen, 20000, True)

    def test_projection_retains_selected_timing_and_excludes_wav(self):
        for timing in ('gear', 'legacy'):
            chosen = selection('on', 'filtered', 48000, timing)
            projected = raw_projection(validate_headless(timed(filtered(), timing), chosen), chosen)
            self.assertEqual(projected['frames'], 147)
            self.assertEqual(projected['pcm_hash'], 123)
            self.assertNotIn('wav_frames', projected)
            self.assertNotIn('processing', projected)
            self.assertEqual(projected.get('timing'), 'gear-v1' if timing == 'gear' else None)
        with self.assertRaises(ValueError):
            canonical(dict(timed(raw()), host={}), selection('on'))

    def test_pending_permission_requires_exact_boolean_in_raw_and_filtered_paths(self):
        for core, chosen in ((raw(), selection('on')),
                             (filtered(), selection('on', 'filtered', 48000))):
            for invalid in (1, 0, None, 'true'):
                with self.subTest(chosen=chosen, invalid=invalid), self.assertRaises(ValueError):
                    validate_headless(timed(core), chosen, allow_pending=invalid)
                with self.assertRaises(ValueError):
                    validate_desktop(timed(hosted(core)), chosen, None, allow_pending=invalid)


class DescriptorAudio15Tests(unittest.TestCase):
    def test_omitted_timing_has_identical_descriptor_lines(self):
        self.assertEqual(runtime_audio_lines(None), [])
        self.assertEqual(runtime_audio_lines('off'), ['audio = "off"'])
        self.assertEqual(runtime_audio_lines('on'), ['audio = "on"'])
        self.assertEqual(runtime_audio_lines('on', 'filtered', 48000),
                         ['audio = "on"', 'audio_profile = "filtered"', 'audio_rate = 48000'])

    def test_explicit_timing_is_exact_optional_runtime_field(self):
        for timing in ('gear', 'legacy'):
            self.assertEqual(runtime_audio_lines('on', 'filtered', 48000, timing),
                             ['audio = "on"', 'audio_profile = "filtered"', 'audio_rate = 48000',
                              f'audio_timing = "{timing}"'])
        for audio, timing in ((None, 'gear'), ('off', 'legacy'), ('on', True),
                              ('on', 'gear-v1'), ('on', 'future')):
            with self.subTest(audio=audio, timing=timing), self.assertRaises(ValueError):
                runtime_audio_lines(audio, timing=timing)

    def test_timing_cli_choices_and_duplicate_refusal(self):
        required = ['--tool-root', 'authored-tool', '--inputs', 'authored-inputs',
                    '--module', 'authored-module', '--out', 'authored-output']
        parser = build_parser()
        for timing in ('gear', 'legacy'):
            self.assertEqual(parser.parse_args(required + ['--audio', 'on', '--audio-timing', timing]).audio_timing, timing)
        for options in (['--audio-timing', 'gear', '--audio-timing', 'legacy'],
                        ['--audio-timing', 'future']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                parser.parse_args(required + options)
            self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
