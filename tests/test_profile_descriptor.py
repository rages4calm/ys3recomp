"""Media-free descriptor selection and early CLI rejection checks."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tomllib
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('prepare_descriptor', ROOT/'scripts/prepare_descriptor.py')
DESCRIPTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DESCRIPTOR)


class ProfileDescriptorTests(unittest.TestCase):
    def test_omitted_selection_preserves_original_shape(self):
        self.assertEqual(DESCRIPTOR.runtime_audio_lines(None), [])
        self.assertEqual(DESCRIPTOR.runtime_audio_lines('on'), ['audio = "on"'])
        self.assertEqual(DESCRIPTOR.runtime_audio_lines('off'), ['audio = "off"'])

    def test_explicit_selections_emit_only_selected_fields(self):
        selections = [
            (None, 44100, {'audio': 'on', 'audio_rate': 44100}),
            ('raw', None, {'audio': 'on', 'audio_profile': 'raw'}),
            ('raw', 44100, {'audio': 'on', 'audio_profile': 'raw', 'audio_rate': 44100}),
            ('filtered', None, {'audio': 'on', 'audio_profile': 'filtered'}),
            ('filtered', 44100, {'audio': 'on', 'audio_profile': 'filtered', 'audio_rate': 44100}),
            ('filtered', 48000, {'audio': 'on', 'audio_profile': 'filtered', 'audio_rate': 48000}),
        ]
        for profile, rate, expected in selections:
            with self.subTest(profile=profile, rate=rate):
                lines = DESCRIPTOR.runtime_audio_lines('on', profile, rate)
                self.assertEqual(tomllib.loads('[runtime]\n'+'\n'.join(lines)), {'runtime': expected})

    def test_selection_requires_explicit_audio_on(self):
        for audio in (None, 'off'):
            for profile, rate in (('raw', None), ('filtered', None), (None, 44100), ('filtered', 48000)):
                with self.subTest(audio=audio, profile=profile, rate=rate):
                    with self.assertRaisesRegex(ValueError, 'require audio on'):
                        DESCRIPTOR.runtime_audio_lines(audio, profile, rate)

    def test_raw_48000_is_rejected(self):
        for profile in (None, 'raw'):
            with self.subTest(profile=profile):
                with self.assertRaisesRegex(ValueError, 'raw audio requires'):
                    DESCRIPTOR.runtime_audio_lines('on', profile, 48000)

    def test_helper_rejects_invalid_values_and_types(self):
        for audio in (True, 1, '', 'ON', [], {}):
            with self.subTest(audio=audio):
                with self.assertRaisesRegex(ValueError, 'audio must'):
                    DESCRIPTOR.runtime_audio_lines(audio)
        for profile in (True, 1, '', 'filtered-v1', [], {}):
            with self.subTest(profile=profile):
                with self.assertRaisesRegex(ValueError, 'audio profile must'):
                    DESCRIPTOR.runtime_audio_lines('on', profile)
        for rate in (True, False, 44100.0, '44100', 0, 96000, [], {}):
            with self.subTest(rate=rate):
                with self.assertRaisesRegex(ValueError, 'audio rate must'):
                    DESCRIPTOR.runtime_audio_lines('on', 'filtered', rate)

    def cli_arguments(self, *extra):
        return ['--tool-root', 'missing-tool', '--inputs', 'missing-inputs',
                '--module', 'missing-module', '--out', 'missing-output', *extra]

    def test_parser_retains_none_defaults_and_typed_explicit_values(self):
        parser = DESCRIPTOR.build_parser()
        args = parser.parse_args(self.cli_arguments())
        self.assertEqual((args.audio, args.audio_profile, args.audio_rate), (None, None, None))
        args = parser.parse_args(self.cli_arguments('--audio', 'on', '--audio-profile', 'filtered',
                                                     '--audio-rate', '48000'))
        self.assertEqual((args.audio, args.audio_profile, args.audio_rate), ('on', 'filtered', 48000))
        self.assertIs(type(args.audio_rate), int)

    def test_cli_rejects_bad_selections_before_verification_or_io(self):
        cases = [
            ('--audio-profile', 'filtered'),
            ('--audio', 'off', '--audio-rate', '44100'),
            ('--audio', 'on', '--audio-rate', '48000'),
            ('--audio', 'on', '--audio-profile', 'raw', '--audio-rate', '48000'),
            ('--audio', 'on', '--audio-profile', 'unknown'),
            ('--audio', 'on', '--audio-rate', '96000'),
            ('--audio', 'on', '--audio-rate', 'True'),
        ]
        for flags in cases:
            with self.subTest(flags=flags):
                with mock.patch.object(DESCRIPTOR.sys, 'argv', ['prepare_descriptor.py', *self.cli_arguments(*flags)]), \
                     mock.patch.object(DESCRIPTOR.subprocess, 'check_output') as verify, \
                     mock.patch.object(Path, 'resolve', side_effect=AssertionError('unexpected file resolution')), \
                     mock.patch.object(Path, 'open', side_effect=AssertionError('unexpected file open')), \
                     contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        DESCRIPTOR.main()
                    self.assertEqual(error.exception.code, 2)
                    verify.assert_not_called()


if __name__ == '__main__':
    unittest.main()
