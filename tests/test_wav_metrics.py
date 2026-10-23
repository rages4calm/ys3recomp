"""Independent tiny literal WAV vectors for read-only integer measurements."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from scripts import wav_metrics as metrics


def wav_bytes(frames, *, rate=44100, channels=2, bits=16, tag=1):
    width = bits // 8
    block = channels * width
    fmt = struct.pack('<HHIIHH', tag, channels, rate, rate * block, block, bits)
    data = b''.join(struct.pack('<hh', *frame) for frame in frames)
    body = b'WAVEfmt ' + struct.pack('<I', len(fmt)) + fmt
    body += b'data' + struct.pack('<I', len(data)) + data
    return b'RIFF' + struct.pack('<I', len(body)) + body


class WavMetricsTests(unittest.TestCase):
    def setUp(self):
        scratch = Path('.local/batch-006/temp')
        scratch.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.left = self.make('left.wav', [(32767, -3), (-32768, -3), (0, 0), (2, -3)])

    def make(self, name, frames, **kwargs):
        path = self.root / name
        path.write_bytes(wav_bytes(frames, **kwargs))
        return path

    def test_literal_signed_peaks_endpoints_dc_and_energy(self):
        raw = self.left.read_bytes()
        result = metrics.analyze(self.left)
        self.assertEqual(result['channels'], [
            {'sample_count': 4, 'nonzero_count': 3, 'positive_peak': 32767,
             'negative_peak': -32768, 'absolute_peak': 32768,
             'endpoint_extreme_count': 2, 'dc_numerator': 1, 'energy_sum': 2147418117},
            {'sample_count': 4, 'nonzero_count': 3, 'positive_peak': 0,
             'negative_peak': -3, 'absolute_peak': 3,
             'endpoint_extreme_count': 0, 'dc_numerator': -9, 'energy_sum': 27}])
        expected_hash = hashlib.sha256(raw).hexdigest()
        self.assertEqual(result['input']['sha256_before'], expected_hash)
        self.assertEqual(result['input']['sha256_after'], expected_hash)
        self.assertEqual(self.left.read_bytes(), raw)
        self.assertEqual(result['geometry']['frames'], 4)
        self.assertNotIn('passed', result)

    def test_positive_dc_and_silence(self):
        result = metrics.analyze(self.make('dc.wav', [(5, 0)] * 3))
        self.assertEqual(result['channels'][0], {
            'sample_count': 3, 'nonzero_count': 3, 'positive_peak': 5,
            'negative_peak': 0, 'absolute_peak': 5, 'endpoint_extreme_count': 0,
            'dc_numerator': 15, 'energy_sum': 75})
        self.assertEqual(result['channels'][1], {
            'sample_count': 3, 'nonzero_count': 0, 'positive_peak': 0,
            'negative_peak': 0, 'absolute_peak': 0, 'endpoint_extreme_count': 0,
            'dc_numerator': 0, 'energy_sum': 0})

    def test_empty_data_is_an_exact_zero_sample_measurement(self):
        path = self.make('empty.wav', [])
        result = metrics.analyze(path)
        self.assertEqual(result['geometry']['frames'], 0)
        self.assertTrue(all(value == 0 for channel in result['channels'] for value in channel.values()))
        self.assertTrue(all(value == 0 for channel in metrics.compare(path, path)['channels']
                            for value in channel.values()))

    def test_declared_positive_sample_rates_are_not_profile_claims(self):
        for rate in (1, 32000, 48000, 96000):
            with self.subTest(rate=rate):
                result = metrics.analyze(self.make(f'rate-{rate}.wav', [(1, -1)], rate=rate))
                self.assertEqual(result['geometry']['sample_rate'], rate)
                self.assertNotIn('profile', result)

    def test_one_channel_change_has_independent_literal_error_sums(self):
        other = self.make('changed.wav', [(32767, -3), (-32768, 4), (0, 0), (2, -3)])
        result = metrics.compare(self.left, other)
        self.assertEqual(result['channels'], [
            {'sample_count': 4, 'mismatch_count': 0, 'sum_absolute_difference': 0,
             'maximum_absolute_difference': 0, 'squared_error_sum': 0},
            {'sample_count': 4, 'mismatch_count': 1, 'sum_absolute_difference': 7,
             'maximum_absolute_difference': 7, 'squared_error_sum': 49}])

    def test_full_signed_range_difference_does_not_overflow(self):
        left = self.make('minimum.wav', [(-32768, 32767)])
        right = self.make('maximum.wav', [(32767, -32768)])
        expected = {'sample_count': 1, 'mismatch_count': 1,
                    'sum_absolute_difference': 65535,
                    'maximum_absolute_difference': 65535, 'squared_error_sum': 4294836225}
        self.assertEqual(metrics.compare(left, right)['channels'], [expected, expected])

    def test_chunk_partition_does_not_change_any_measurements(self):
        other = self.make('partition.wav', [(32767, 0), (1, -3), (0, 0), (2, -3)])
        analysis = metrics.analyze(self.left)
        comparison = metrics.compare(self.left, other)
        for chunk in (1, 2, 3, 5, 100):
            with self.subTest(chunk=chunk):
                self.assertEqual(metrics.analyze(self.left, chunk_frames=chunk), analysis)
                self.assertEqual(metrics.compare(self.left, other, chunk_frames=chunk), comparison)

    def test_invalid_chunk_sizes_fail(self):
        for size in (0, -1, True, 1.5, 1048577):
            with self.subTest(size=size), self.assertRaises(ValueError):
                metrics.analyze(self.left, chunk_frames=size)
            with self.assertRaises(ValueError):
                metrics.compare(self.left, self.left, chunk_frames=size)

    def test_different_rates_or_frame_counts_are_rejected_without_alignment(self):
        for other in (self.make('rate.wav', [(1, 2)] * 4, rate=48000),
                      self.make('short.wav', [(1, 2)] * 3)):
            with self.subTest(other=other.name), self.assertRaisesRegex(ValueError, 'identical geometry'):
                metrics.compare(self.left, other)

    def test_unsupported_width_channels_compression_and_zero_rate_fail(self):
        for options in ({'bits': 8}, {'bits': 24}, {'channels': 1},
                        {'tag': 3}, {'tag': 65534}, {'rate': 0}):
            path = self.make('unsupported.wav', [(0, 0)], **options)
            with self.subTest(options=options), self.assertRaises(ValueError):
                metrics.analyze(path)

    def test_missing_malformed_truncated_and_partial_frames_fail(self):
        with self.assertRaises(FileNotFoundError):
            metrics.analyze(self.root / 'missing.wav')
        raw = self.left.read_bytes()
        malformed = [b'', b'not a WAV file', raw[:11], raw[:-1], raw + b'extra',
                     b'RIFX' + raw[4:], raw[:20] + b'\0' * 16 + raw[36:]]
        # Declare an incomplete stereo frame, but otherwise retain valid RIFF bounds.
        body = raw[8:40] + struct.pack('<I', 2) + b'\0\0'
        malformed.append(b'RIFF' + struct.pack('<I', len(body)) + body)
        for index, data in enumerate(malformed):
            path = self.root / f'malformed-{index}.wav'
            path.write_bytes(data)
            with self.subTest(index=index), self.assertRaises(ValueError):
                metrics.analyze(path)

    def test_unknown_chunks_are_bounded_and_do_not_enter_sample_metrics(self):
        raw = self.left.read_bytes()
        extra = b'JUNK' + struct.pack('<I', 3) + b'abc\0'
        body = raw[8:] + extra
        path = self.root / 'junk.wav'
        path.write_bytes(b'RIFF' + struct.pack('<I', len(body)) + body)
        self.assertEqual(metrics.analyze(path)['channels'], metrics.analyze(self.left)['channels'])
        truncated = path.read_bytes()[:-1]
        path.write_bytes(truncated[:4] + struct.pack('<I', len(truncated) - 8) + truncated[8:])
        with self.assertRaises(ValueError):
            metrics.analyze(path)

    def test_mutation_during_sample_measurement_is_detected(self):
        original_chunks = metrics._chunks

        def mutate(source, chunk_frames):
            yield from original_chunks(source, chunk_frames)
            raw = source.path.read_bytes()
            source.path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))

        with patch.object(metrics, '_chunks', mutate), self.assertRaisesRegex(ValueError, 'changed'):
            metrics.analyze(self.left)

    def test_comparison_also_detects_mutation_in_an_input(self):
        other = self.make('mutation.wav', [(32767, -3), (-32768, -3), (0, 0), (2, -3)])
        original_hash = metrics._sha256
        calls = 0

        def modified_hash(path):
            nonlocal calls
            calls += 1
            if calls == 4:
                raw = path.read_bytes()
                path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
            return original_hash(path)

        with patch.object(metrics, '_sha256', modified_hash), self.assertRaisesRegex(ValueError, 'changed'):
            metrics.compare(self.left, other)

    def test_cli_creates_only_new_output_and_preserves_inputs(self):
        raw = self.left.read_bytes()
        destination = self.root / 'analysis.json'
        self.assertEqual(metrics.main(['analyze', str(self.left), '--out', str(destination)]), 0)
        original = destination.read_bytes()
        self.assertEqual(json.loads(original)['input']['sha256_before'], hashlib.sha256(raw).hexdigest())
        for output in (destination, self.left):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                metrics.main(['analyze', str(self.left), '--out', str(output)])
            self.assertEqual(error.exception.code, 2)
        self.assertEqual(destination.read_bytes(), original)
        self.assertEqual(self.left.read_bytes(), raw)
        comparison = self.root / 'comparison.json'
        self.assertEqual(metrics.main(['compare', str(self.left), str(self.left), '--out', str(comparison)]), 0)
        self.assertEqual(json.loads(comparison.read_text())['channels'][0]['mismatch_count'], 0)

    def test_cli_does_not_emit_a_result_for_invalid_input(self):
        destination = self.root / 'refused.json'
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            metrics.main(['analyze', str(self.root / 'missing.wav'), '--out', str(destination)])
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
