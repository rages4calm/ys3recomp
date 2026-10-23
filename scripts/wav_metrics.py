"""Read-only integer PCM16 stereo measurements, without signal processing.

These metrics describe samples, not sound quality, profile correctness or
alignment. Comparisons require identical declared geometry and frame counts.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import struct


DEFAULT_CHUNK_FRAMES = 16384
SCOPE = ('Exact PCM sample measurements only; no quality threshold, profile '
         'qualification, normalization, resampling or alignment inference.')


def _sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _read_exact(stream, size):
    data = stream.read(size)
    if len(data) != size:
        raise ValueError('truncated WAV data')
    return data


def _geometry(stream):
    """Validate all RIFF chunk bounds, including chunks after the PCM payload."""
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    header = _read_exact(stream, 12)
    if header[:4] != b'RIFF' or header[8:] != b'WAVE':
        raise ValueError('expected a RIFF WAVE file')
    if struct.unpack('<I', header[4:8])[0] + 8 != size:
        raise ValueError('RIFF size differs from actual file length')
    fmt = None
    payload = None
    while stream.tell() < size:
        kind, length = struct.unpack('<4sI', _read_exact(stream, 8))
        start = stream.tell()
        end = start + length + (length & 1)
        if end > size:
            raise ValueError('truncated WAV chunk')
        if kind == b'fmt ':
            if fmt is not None or payload is not None or length not in (16, 18):
                raise ValueError('unsupported or duplicate WAV format chunk')
            raw = _read_exact(stream, length)
            tag, channels, rate, byte_rate, block, bits = struct.unpack('<HHIIHH', raw[:16])
            if (tag, channels, block, bits) != (1, 2, 4, 16):
                raise ValueError('only uncompressed PCM16 stereo WAV is supported')
            if rate <= 0 or byte_rate != rate * 4 or (length == 18 and raw[16:] != b'\0\0'):
                raise ValueError('invalid PCM rate or format extension')
            fmt = {'encoding': 'PCM', 'sample_rate': rate, 'channels': 2,
                   'sample_width_bytes': 2, 'block_align': 4}
        elif kind == b'data':
            if fmt is None or payload is not None or length % 4:
                raise ValueError('missing format, duplicate data or partial stereo frame')
            payload = (start, length)
        stream.seek(end)
    if fmt is None or payload is None:
        raise ValueError('WAV needs one format and one data chunk')
    fmt['frames'] = payload[1] // 4
    stream.seek(payload[0])
    return fmt


class _Source:
    def __init__(self, path, stack):
        self.path = Path(path).resolve(strict=True)
        if not self.path.is_file():
            raise ValueError('WAV input must be a regular file')
        self.before = _sha256(self.path)
        self.stream = stack.enter_context(self.path.open('rb'))
        self.geometry = _geometry(self.stream)

    def finish(self):
        after = _sha256(self.path)
        if self.before != after:
            raise ValueError('WAV input changed during measurement')
        return {'path': str(self.path), 'sha256_before': self.before,
                'sha256_after': after, 'unchanged': True}


def _chunk_size(value):
    if type(value) is not int or not 1 <= value <= 1048576:
        raise ValueError('chunk_frames must be an integer from 1 to 1048576')
    return value


def _chunks(source, chunk_frames):
    remaining = source.geometry['frames']
    while remaining:
        count = min(remaining, chunk_frames)
        yield struct.iter_unpack('<hh', _read_exact(source.stream, count * 4))
        remaining -= count


def analyze(path, *, chunk_frames=DEFAULT_CHUNK_FRAMES):
    """Return exact per-channel integers; signed negative_peak is <= zero.

    Positive/negative peaks include zero as the empty/opposite-sign baseline.
    endpoint_extreme_count counts literal -32768 and +32767 occurrences; it
    does not infer clipping. dc_numerator is the signed sum of samples.
    """
    chunk_frames = _chunk_size(chunk_frames)
    channels = [dict(sample_count=0, nonzero_count=0, positive_peak=0,
                     negative_peak=0, absolute_peak=0, endpoint_extreme_count=0,
                     dc_numerator=0, energy_sum=0) for _ in range(2)]
    with ExitStack() as stack:
        source = _Source(path, stack)
        for chunk in _chunks(source, chunk_frames):
            for frame in chunk:
                for value, metrics in zip(frame, channels):
                    metrics['sample_count'] += 1
                    metrics['nonzero_count'] += value != 0
                    metrics['positive_peak'] = max(metrics['positive_peak'], value)
                    metrics['negative_peak'] = min(metrics['negative_peak'], value)
                    metrics['absolute_peak'] = max(metrics['absolute_peak'], abs(value))
                    metrics['endpoint_extreme_count'] += value in (-32768, 32767)
                    metrics['dc_numerator'] += value
                    metrics['energy_sum'] += value * value
        identity = source.finish()
        return {'schema': 1, 'kind': 'pcm16-stereo-analysis', 'scope': SCOPE,
                'input': identity, 'geometry': source.geometry, 'channels': channels,
                'channel_order': ['left', 'right']}


def compare(left, right, *, chunk_frames=DEFAULT_CHUNK_FRAMES):
    """Compare corresponding frames exactly; reject any geometry mismatch."""
    chunk_frames = _chunk_size(chunk_frames)
    channels = [dict(sample_count=0, mismatch_count=0, sum_absolute_difference=0,
                     maximum_absolute_difference=0, squared_error_sum=0)
                for _ in range(2)]
    with ExitStack() as stack:
        lhs, rhs = _Source(left, stack), _Source(right, stack)
        if lhs.geometry != rhs.geometry:
            raise ValueError('WAV comparison requires identical geometry and frame count')
        for left_chunk, right_chunk in zip(_chunks(lhs, chunk_frames), _chunks(rhs, chunk_frames)):
            for a, b in zip(left_chunk, right_chunk):
                for x, y, metrics in zip(a, b, channels):
                    difference = abs(x - y)
                    metrics['sample_count'] += 1
                    metrics['mismatch_count'] += x != y
                    metrics['sum_absolute_difference'] += difference
                    metrics['maximum_absolute_difference'] = max(metrics['maximum_absolute_difference'], difference)
                    metrics['squared_error_sum'] += difference * difference
        return {'schema': 1, 'kind': 'pcm16-stereo-comparison', 'scope': SCOPE,
                'left': lhs.finish(), 'right': rhs.finish(), 'geometry': lhs.geometry,
                'channels': channels, 'channel_order': ['left', 'right']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('analyze', 'compare'):
        command = commands.add_parser(name)
        command.add_argument('inputs', nargs=1 if name == 'analyze' else 2, type=Path)
        command.add_argument('--out', required=True, type=Path)
        command.add_argument('--chunk-frames', type=int, default=DEFAULT_CHUNK_FRAMES)
    args = parser.parse_args(argv)
    try:
        destination = args.out.resolve()
        if destination.exists() or any(destination == item.resolve() for item in args.inputs):
            raise ValueError('output must be a new file distinct from every input')
        result = (analyze(*args.inputs, chunk_frames=args.chunk_frames)
                  if args.command == 'analyze'
                  else compare(*args.inputs, chunk_frames=args.chunk_frames))
        # Exclusive creation also closes the preflight-to-write overwrite race.
        with destination.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
    except (OSError, ValueError, struct.error) as exc:
        parser.exit(2, f'WAV measurement failed: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
