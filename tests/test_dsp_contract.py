"""Authored finite DSP telemetry fixtures; no runtime DSP or retail samples."""
import copy
import unittest

from scripts import audio_contract as legacy
from scripts import desktop_contract as legacy_desktop
from scripts.dsp_contract import (audio_command, desktop_audio, headless_audio,
                                  raw_projection, selection, validate_audio)


def raw():
    return {'enabled': True, 'sample_rate': 44100, 'channels': 2, 'frames': 100,
            'psg_nonzero': 10, 'adpcm_nonzero': 20, 'cdda_nonzero': 30,
            'mixed_nonzero': 40, 'peak': 90, 'pcm_hash': 123,
            'discarded_frames': 0, 'wav_frames': 0, 'wav_truncated': False}


def filtered(source_frames=147, rate=48000, wav_limit=None, drained=None):
    frames = source_frames if rate == 44100 else source_frames * 160 // 147
    written = frames if drained is None else drained
    return {'enabled': True, 'sample_rate': rate, 'channels': 2, 'frames': frames,
            'psg_nonzero': min(source_frames, 120),
            'adpcm_nonzero': min(source_frames, 100),
            'cdda_nonzero': min(source_frames, 110),
            'mixed_nonzero': min(frames, 150), 'peak': 100 if frames else 0,
            'pcm_hash': 456 if frames else legacy.PCM_INITIAL_HASH,
            'discarded_frames': 0,
            'wav_frames': min(written, wav_limit) if wav_limit is not None else 0,
            'wav_truncated': wav_limit is not None and written > wav_limit,
            'processing': {
                'profile': 'filtered-v1', 'source_rate': 44100,
                'source_frames': source_frames,
                'raw_pcm_hash': 123 if source_frames else legacy.PCM_INITIAL_HASH,
                'raw_peak': 90 if source_frames else 0,
                'raw_mixed_nonzero': min(source_frames, 130),
                'resampler': 'identity' if rate == 44100 else 'sinc64-q30-v1',
                'latency_source_frames': 0 if rate == 44100 else 31,
                'tail_flushed': False}}


def hosted(core, pending=0):
    value = copy.deepcopy(core)
    submitted = core['frames'] - pending
    value.update(device_open=True, fast_forward_muted=True, host={
        'submitted_frames': submitted, 'dropped_frames': submitted,
        'clears': 1, 'pauses': 1, 'queued_frames': 0, 'peak_queue_frames': 0})
    if 'processing' in core:
        value['host'].update(input_rate=core['sample_rate'], device_rate=48000,
                             device_channels=2, device_format=32784)
    return value


class SelectionTests(unittest.TestCase):
    def test_omission_keeps_legacy_in_control(self):
        for mode in (None, 'on', 'off'):
            self.assertIsNone(selection(mode))
            for cap in (None, 100):
                arguments = (['runner', 'authored'], mode, 'new.wav', cap)
                if mode != 'on' and cap is not None:
                    with self.assertRaises(ValueError):
                        audio_command(*arguments)
                else:
                    self.assertEqual(audio_command(*arguments), legacy.audio_command(*arguments))

    def test_raw_and_filtered_default_or_explicit_rates(self):
        self.assertEqual(selection('on', 'raw'), {'profile': 'raw', 'sample_rate': 44100})
        self.assertEqual(selection('on', rate=44100), {'profile': 'raw', 'sample_rate': 44100})
        self.assertEqual(selection('on', 'filtered'), {'profile': 'filtered', 'sample_rate': 44100})
        self.assertEqual(selection('on', 'filtered', 48000), {'profile': 'filtered', 'sample_rate': 48000})

    def test_selection_rejects_implicit_filtered_and_invalid_types(self):
        for mode, profile, rate in (('off', 'raw', None), (None, 'filtered', 44100),
                                    ('on', 'raw', 48000), ('on', None, 48000),
                                    ('on', 'filtered-v1', None), ('on', True, None),
                                    ('on', 'filtered', True), ('on', 'filtered', 44100.0),
                                    ('on', 'filtered', '48000'), ('on', 'filtered', 32000)):
            with self.subTest(mode=mode, profile=profile, rate=rate), self.assertRaises(ValueError):
                selection(mode, profile, rate)

    def test_dynamic_wav_cap_uses_output_rate(self):
        self.assertEqual(selection('on', 'filtered', 48000, 5760000)['sample_rate'], 48000)
        for rate, cap in ((48000, 5760001), (44100, 5292001), (48000, 0),
                          (48000, True), (48000, 1.5)):
            with self.subTest(rate=rate, cap=cap), self.assertRaises(ValueError):
                selection('on', 'filtered', rate, cap)

    def test_selected_argv_preserves_only_explicit_flags(self):
        command = ['runner', 'authored']
        self.assertEqual(audio_command(command, 'on', 'new.wav', 5760000, 'filtered', 48000),
                         command + ['--audio-output', 'on', '--audio-profile', 'filtered',
                                    '--audio-rate', '48000', '--audio-out', 'new.wav',
                                    '--audio-frames', '5760000'])
        self.assertEqual(audio_command(command, 'on', 'new.wav', profile='filtered'),
                         command + ['--audio-output', 'on', '--audio-profile', 'filtered'])
        self.assertEqual(audio_command(command, 'on', 'new.wav', rate=44100),
                         command + ['--audio-output', 'on', '--audio-rate', '44100'])
        self.assertEqual(command, ['runner', 'authored'])

    def test_selected_argv_rejects_every_existing_audio_flag(self):
        for flag in ('--audio-output', '--audio-out', '--audio-frames', '--audio-profile', '--audio-rate'):
            for option in (flag, flag + '=authored'):
                with self.subTest(option=option), self.assertRaises(ValueError):
                    audio_command(['runner', option], 'on', 'new.wav', profile='filtered')


class FilteredCoreTests(unittest.TestCase):
    def test_raw_none_and_explicit_raw_delegate_frozen_shape(self):
        for chosen in (None, selection('on', 'raw'), selection('on', rate=44100)):
            self.assertEqual(validate_audio(raw(), chosen), legacy.validate_audio(raw(), 'on'))
            desktop = hosted(raw())
            self.assertEqual(desktop_audio(desktop, chosen, None),
                             legacy_desktop.desktop_audio(desktop, None))
            desktop['host']['input_rate'] = 44100
            with self.assertRaises(ValueError):
                desktop_audio(desktop, chosen, None)

    def test_filtered_identity_and_sinc_geometry_without_latency_subtraction(self):
        for rate in (44100, 48000):
            chosen = selection('on', 'filtered', rate)
            value = filtered(rate=rate)
            self.assertEqual(validate_audio(value, chosen), value)
            self.assertEqual(value['frames'], 147 if rate == 44100 else 160)
            self.assertEqual(value['processing']['latency_source_frames'], 0 if rate == 44100 else 31)

    def test_literal_160_over_147_floor_boundaries(self):
        chosen = selection('on', 'filtered', 48000)
        for source, expected in ((0, 0), (1, 1), (146, 158), (147, 160), (148, 161), (294, 320)):
            value = filtered(source)
            self.assertEqual(value['frames'], expected)
            self.assertEqual(validate_audio(value, chosen)['frames'], expected)
            value['frames'] += 1
            with self.subTest(source=source), self.assertRaises(ValueError):
                validate_audio(value, chosen)

    def test_unknown_or_missing_core_processing_and_selection_fields_fail(self):
        chosen = selection('on', 'filtered', 48000)
        for target in ('core', 'processing', 'selection'):
            for operation in ('unknown', 'missing'):
                value, selected = filtered(), copy.deepcopy(chosen)
                obj = value if target == 'core' else value['processing'] if target == 'processing' else selected
                if operation == 'unknown':
                    obj['future'] = 0
                else:
                    obj.pop(next(iter(obj)))
                with self.subTest(target=target, operation=operation), self.assertRaises(ValueError):
                    validate_audio(value, selected)

    def test_profile_rate_resampler_latency_tail_and_boolean_types_are_strict(self):
        chosen = selection('on', 'filtered', 48000)
        cases = [('enabled', 1), ('sample_rate', 44100), ('channels', 1),
                 ('frames', True), ('wav_truncated', 0),
                 ('processing.profile', 'raw'), ('processing.source_rate', 48000),
                 ('processing.source_frames', 147.0), ('processing.resampler', 'identity'),
                 ('processing.latency_source_frames', 30), ('processing.tail_flushed', 0),
                 ('processing.tail_flushed', True)]
        for key, invalid in cases:
            value = filtered()
            if '.' in key:
                value['processing'][key.split('.')[1]] = invalid
            else:
                value[key] = invalid
            with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                validate_audio(value, chosen)
        with self.assertRaises(ValueError):
            validate_audio(filtered(), selection('on', 'raw'))
        with self.assertRaises(ValueError):
            validate_audio(raw(), chosen)

    def test_source_activity_and_output_activity_have_distinct_bounds(self):
        chosen = selection('on', 'filtered', 48000)
        value = filtered()
        value['mixed_nonzero'] = 160  # More output samples than the 147 source samples is valid.
        validate_audio(value, chosen)
        for field in ('psg_nonzero', 'adpcm_nonzero', 'cdda_nonzero',
                      'mixed_nonzero', 'processing.raw_mixed_nonzero'):
            invalid = copy.deepcopy(value)
            if field.startswith('processing.'):
                invalid['processing']['raw_mixed_nonzero'] = 148
            else:
                invalid[field] = 161 if field == 'mixed_nonzero' else 148
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_audio(invalid, chosen)

    def test_hash_peak_loss_and_initial_zero_source_constraints(self):
        chosen = selection('on', 'filtered', 48000)
        for field, invalid in (('pcm_hash', 1 << 64), ('peak', 32769), ('discarded_frames', 1),
                               ('processing.raw_pcm_hash', -1), ('processing.raw_pcm_hash', 1 << 64),
                               ('processing.raw_peak', 32769), ('processing.raw_peak', False)):
            value = filtered()
            if '.' in field:
                value['processing'][field.split('.')[1]] = invalid
            else:
                value[field] = invalid
            with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                validate_audio(value, chosen)
        validate_audio(filtered(0), chosen)
        for field in ('pcm_hash', 'peak', 'processing.raw_pcm_hash', 'processing.raw_peak'):
            value = filtered(0)
            if '.' in field:
                value['processing'][field.split('.')[1]] = 1
            else:
                value[field] = 1
            with self.subTest(initial_field=field), self.assertRaises(ValueError):
                validate_audio(value, chosen)

    def test_reviewed_uint64_counters_and_zero_source_activity(self):
        chosen = selection('on', 'filtered', 44100)
        # Storage bounds, without inferring any route duration or quality gate.
        validate_audio(filtered((1 << 64) - 1, rate=44100), chosen)
        with self.assertRaises(ValueError):
            validate_audio(filtered(1 << 64, rate=44100), chosen)
        for field in ('psg_nonzero', 'adpcm_nonzero', 'cdda_nonzero', 'mixed_nonzero'):
            value = filtered(0, rate=44100)
            value[field] = 1
            with self.subTest(initial_activity=field), self.assertRaises(ValueError):
                validate_audio(value, chosen)
        value = filtered(0, rate=44100)
        value['processing']['raw_mixed_nonzero'] = 1
        with self.assertRaises(ValueError):
            validate_audio(value, chosen)

    def test_projection_is_raw_source_evidence_without_wav_or_processing(self):
        chosen = selection('on', 'filtered', 48000)
        value = validate_audio(filtered(), chosen)
        self.assertEqual(raw_projection(value), {
            'enabled': True, 'sample_rate': 44100, 'channels': 2, 'frames': 147,
            'psg_nonzero': 120, 'adpcm_nonzero': 100, 'cdda_nonzero': 110,
            'mixed_nonzero': 130, 'peak': 90, 'pcm_hash': 123, 'discarded_frames': 0})
        with self.assertRaises(ValueError):
            raw_projection(raw())
        returned = validate_audio(value, chosen)
        returned['processing']['raw_peak'] = 1
        self.assertEqual(value['processing']['raw_peak'], 90)

    def test_wav_uses_output_domain_and_exact_drain(self):
        chosen = selection('on', 'filtered', 48000)
        value = filtered(wav_limit=200, drained=155)
        self.assertEqual(validate_audio(value, chosen, 200, 155), value)
        with self.assertRaises(ValueError):
            validate_audio(value, chosen, 200)  # terminal requires all160 output frames
        for drained in (True, -1, 161, 155.0):
            with self.subTest(drained=drained), self.assertRaises(ValueError):
                validate_audio(value, chosen, 200, drained)
        saturated = filtered(wav_limit=70)
        validate_audio(saturated, chosen, 70)
        saturated['wav_truncated'] = False
        with self.assertRaises(ValueError):
            validate_audio(saturated, chosen, 70)

    def test_selected_validation_enforces_dynamic_capture_limit(self):
        value = filtered(wav_limit=5760000)
        validate_audio(value, selection('on', 'filtered', 48000), 5760000)
        for cap in (5760001, True, 0):
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                validate_audio(value, selection('on', 'filtered', 48000), cap)


class HeadlessCheckpointTests(unittest.TestCase):
    def test_unsaturated_pending_and_terminal_are_distinct(self):
        chosen = selection('on', 'filtered', 48000)
        value = filtered(wav_limit=200, drained=80)
        self.assertEqual(headless_audio(value, chosen, 200, True), value)
        with self.assertRaises(ValueError):
            headless_audio(value, chosen, 200)

    def test_pending_bound_is_8192_output_frames(self):
        chosen = selection('on', 'filtered', 48000)
        value = filtered(14700, wav_limit=20000, drained=7808)  # output16000 minus8192
        headless_audio(value, chosen, 20000, True)
        value['wav_frames'] = 7807
        with self.assertRaises(ValueError):
            headless_audio(value, chosen, 20000, True)

    def test_saturated_truncated_checkpoint_retains_actual_data_without_guessed_drain(self):
        chosen = selection('on', 'filtered', 48000)
        value = filtered(14700, wav_limit=70, drained=8000)
        self.assertEqual(headless_audio(value, chosen, 70, True), value)
        self.assertNotIn('drained_frames', headless_audio(value, chosen, 70, True))
        value['frames'] = 16000
        value['wav_frames'] = 71
        with self.assertRaises(ValueError):
            headless_audio(value, chosen, 70, True)

    def test_no_capture_does_not_infer_a_pending_count(self):
        value = filtered(14700)
        self.assertEqual(headless_audio(value, selection('on', 'filtered', 48000), allow_pending=True), value)
        self.assertEqual(headless_audio(raw(), None, allow_pending=True), raw())
        value['wav_frames'] = 1
        with self.assertRaises(ValueError):
            headless_audio(value, selection('on', 'filtered', 48000), allow_pending=True)

    def test_raw_checkpoint_keeps_same_frozen_core(self):
        value = raw()
        value.update(wav_frames=71)
        self.assertEqual(headless_audio(value, None, 200, True),
                         legacy.validate_audio(value, 'on', 200, 71))
        for bad in (True, -1, 1.5):
            changed = copy.deepcopy(value)
            changed['wav_frames'] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                headless_audio(changed, None, 200, True)

    def test_untruncated_saturated_wav_and_impossible_truncation_interval(self):
        chosen = selection('on', 'filtered', 48000)
        value = filtered(wav_limit=70, drained=70)
        self.assertFalse(value['wav_truncated'])
        self.assertEqual(headless_audio(value, chosen, 70, True), value)
        impossible = filtered(wav_limit=160)
        impossible['wav_truncated'] = True
        with self.assertRaises(ValueError):
            headless_audio(impossible, chosen, 160, True)

    def test_pending_option_requires_boolean(self):
        for flag in (0, 1, None, 'true'):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                headless_audio(filtered(), selection('on', 'filtered', 48000), allow_pending=flag)


class DesktopDSPTests(unittest.TestCase):
    def test_filtered_host_exact_format_metadata_and_muted_terminal(self):
        chosen = selection('on', 'filtered', 48000)
        core = filtered(wav_limit=200)
        value = hosted(core)
        self.assertEqual(desktop_audio(value, chosen, 200), core)
        self.assertEqual(value['host']['device_format'], 32784)
        # A reported actual device format is not guessed from the requested stream.
        value['host'].update(device_rate=96000, device_channels=6, device_format=33056)
        desktop_audio(value, chosen, 200)

    def test_host_pending_is_in_output_domain(self):
        chosen = selection('on', 'filtered', 48000)
        core = filtered(14700, wav_limit=20000, drained=7808)
        value = hosted(core, pending=8192)
        self.assertEqual(desktop_audio(value, chosen, 20000, True), core)
        with self.assertRaises(ValueError):
            desktop_audio(value, chosen, 20000)
        value['host']['submitted_frames'] -= 1
        value['host']['dropped_frames'] -= 1
        value['wav_frames'] -= 1
        with self.assertRaises(ValueError):
            desktop_audio(value, chosen, 20000, True)

    def test_unknown_missing_or_invalid_host_and_device_fields_fail(self):
        chosen = selection('on', 'filtered', 48000)
        for key in ('submitted_frames', 'dropped_frames', 'clears', 'pauses',
                    'queued_frames', 'peak_queue_frames', 'input_rate',
                    'device_rate', 'device_channels', 'device_format'):
            for invalid in (True, -1, 1.5):
                value = hosted(filtered())
                value['host'][key] = invalid
                with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                    desktop_audio(value, chosen, None)
        for target, key in (('outer', 'unknown'), ('host', 'unknown')):
            value = hosted(filtered())
            (value if target == 'outer' else value['host'])[key] = 0
            with self.assertRaises(ValueError):
                desktop_audio(value, chosen, None)
        value = hosted(filtered())
        value['host'].pop('device_format')
        with self.assertRaises(ValueError):
            desktop_audio(value, chosen, None)

    def test_device_rates_flags_queues_drops_and_pause_are_not_optional(self):
        chosen = selection('on', 'filtered', 48000)
        for key, invalid in (('device_open', False), ('fast_forward_muted', False),
                             ('host.input_rate', 44100), ('host.device_rate', 0),
                             ('host.device_channels', 0), ('host.device_format', 0),
                             ('host.dropped_frames', 159), ('host.queued_frames', 1),
                             ('host.peak_queue_frames', 1), ('host.clears', 0), ('host.pauses', 0)):
            value = hosted(filtered())
            if '.' in key:
                value['host'][key.split('.')[1]] = invalid
            else:
                value[key] = invalid
            with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                desktop_audio(value, chosen, None)

    def test_reviewed_host_integer_storage_bounds_without_enum_guesses(self):
        chosen = selection('on', 'filtered', 48000)
        for key, limit in (('device_rate', (1 << 31) - 1),
                            ('device_channels', (1 << 31) - 1),
                            ('device_format', (1 << 32) - 1),
                            ('clears', (1 << 64) - 1), ('pauses', (1 << 64) - 1)):
            value = hosted(filtered())
            value['host'][key] = limit
            desktop_audio(value, chosen, None)
            value['host'][key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                desktop_audio(value, chosen, None)
        with self.assertRaises(ValueError):
            desktop_audio(hosted(filtered()), chosen, None, allow_pending=1)


if __name__ == '__main__':
    unittest.main()
