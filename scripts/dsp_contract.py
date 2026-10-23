"""Reviewed opt-in ABI13 DSP telemetry; legacy raw paths remain delegated.

Reviewed against shared revision 72bd5a2d4616d50d8b19f0d78c5af6ddfbd1c777:
headless.cpp's shared TCP/final writer, pcm.hpp/cpp, audio_dsp.hpp/cpp,
audio_host.hpp/cpp and wav.hpp, with the qualified Windows x64 SDL3 SDK.
No filtering, resampling or audio-quality decision happens in this module.
"""
from __future__ import annotations

import copy

if __package__:
    from . import audio_contract as legacy
    from . import desktop_contract as desktop
else:
    import audio_contract as legacy
    import desktop_contract as desktop


PROCESSING_FIELDS = {'profile', 'source_rate', 'source_frames', 'raw_pcm_hash',
                     'raw_peak', 'raw_mixed_nonzero', 'resampler',
                     'latency_source_frames', 'tail_flushed'}
FILTERED_FIELDS = legacy.PCM_FIELDS | {'processing'}
DEVICE_FORMAT_FIELDS = {'input_rate', 'device_rate', 'device_channels', 'device_format'}
AUDIO_FLAGS = {'--audio-output', '--audio-out', '--audio-frames',
               '--audio-profile', '--audio-rate'}
UINT64_MAX = (1 << 64) - 1
UINT32_MAX = (1 << 32) - 1
INT32_MAX = (1 << 31) - 1


def _wav_limit(value, rate):
    if value is not None and (type(value) is not int or not 1 <= value <= 120 * rate):
        raise ValueError('WAV frame cap must be an integer from 1 to 120 * output rate')


def selection(mode, profile=None, rate=None, wav_limit=None):
    """Normalize explicit opt-in flags; None leaves the legacy API in control."""
    if profile is None and rate is None:
        return None
    if mode != 'on':
        raise ValueError('explicit DSP selection requires audio on')
    if profile is not None and profile not in ('raw', 'filtered'):
        raise ValueError('audio profile must be raw or filtered')
    if rate is not None and (type(rate) is not int or rate not in (44100, 48000)):
        raise ValueError('audio output rate must be integer 44100 or 48000')
    profile = 'raw' if profile is None else profile
    rate = 44100 if rate is None else rate
    if profile == 'raw' and rate != 44100:
        raise ValueError('raw audio requires 44100 Hz')
    _wav_limit(wav_limit, rate)
    return {'profile': profile, 'sample_rate': rate}


def _selected(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {'profile', 'sample_rate'}:
        raise ValueError('exact normalized DSP selection required')
    result = selection('on', value['profile'], value['sample_rate'])
    if result != value:
        raise ValueError('normalized DSP selection required')
    return result


def audio_command(command, mode, output, wav_limit=None, profile=None, rate=None):
    """Preserve omitted legacy behavior exactly; append only explicit DSP flags."""
    selected = selection(mode, profile, rate, wav_limit)
    if selected is None:
        return legacy.audio_command(command, mode, output, wav_limit)
    if any(str(argument).split('=', 1)[0] in AUDIO_FLAGS for argument in command):
        raise ValueError('frozen source command already specifies audio options')
    result = command.copy() + ['--audio-output', 'on']
    if profile is not None:
        result += ['--audio-profile', profile]
    if rate is not None:
        result += ['--audio-rate', str(rate)]
    if wav_limit is not None:
        result += ['--audio-out', str(output), '--audio-frames', str(wav_limit)]
    return result


def _nonnegative(value, field, maximum=UINT64_MAX):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(field + ': integer within declared unsigned storage required')


def _filtered_core(value, selected):
    if not isinstance(value, dict) or set(value) != FILTERED_FIELDS:
        raise ValueError('filtered audio_output requires exact PCM and processing fields')
    if value['enabled'] is not True or type(value['wav_truncated']) is not bool:
        raise ValueError('filtered audio requires enabled true and boolean WAV truncation')
    for key in legacy.PCM_FIELDS - {'enabled', 'wav_truncated'}:
        _nonnegative(value[key], 'audio_output.' + key)
    if value['sample_rate'] != selected['sample_rate'] or value['channels'] != 2:
        raise ValueError('filtered PCM geometry disagrees with selection')
    if value['peak'] > 32768 or value['pcm_hash'] >= 1 << 64 or value['discarded_frames'] != 0:
        raise ValueError('invalid filtered PCM peak/hash or runtime queue loss')
    processing = value['processing']
    if not isinstance(processing, dict) or set(processing) != PROCESSING_FIELDS:
        raise ValueError('exact filtered processing fields required')
    for key in ('source_rate', 'source_frames', 'raw_pcm_hash', 'raw_peak',
                'raw_mixed_nonzero', 'latency_source_frames'):
        _nonnegative(processing[key], 'audio_output.processing.' + key)
    if (processing['profile'] != 'filtered-v1' or processing['source_rate'] != 44100
            or processing['tail_flushed'] is not False):
        raise ValueError('filtered processing profile/source clock/unflushed tail required')
    rate = selected['sample_rate']
    resampler, latency = ('identity', 0) if rate == 44100 else ('sinc64-q30-v1', 31)
    if (processing['resampler'] != resampler or processing['latency_source_frames'] != latency):
        raise ValueError('resampler or latency disagrees with output rate')
    source_frames = processing['source_frames']
    expected_frames = source_frames if rate == 44100 else source_frames * 160 // 147
    if value['frames'] != expected_frames:
        raise ValueError('output frame count disagrees with exact source/output ratio')
    if (processing['raw_pcm_hash'] >= 1 << 64 or processing['raw_peak'] > 32768
            or processing['raw_mixed_nonzero'] > source_frames):
        raise ValueError('raw source PCM hash/peak/activity exceeds source bounds')
    for key in ('psg_nonzero', 'adpcm_nonzero', 'cdda_nonzero'):
        if value[key] > source_frames:
            raise ValueError(key + ' exceeds source-domain frames')
    if value['mixed_nonzero'] > value['frames']:
        raise ValueError('mixed activity exceeds output-domain frames')
    if source_frames == 0 and (
            processing['raw_pcm_hash'] != legacy.PCM_INITIAL_HASH
            or processing['raw_peak'] != 0 or value['pcm_hash'] != legacy.PCM_INITIAL_HASH
            or value['peak'] != 0):
        raise ValueError('zero-source PCM must retain initial hashes and zero peaks')
    return copy.deepcopy(value)


def validate_audio(value, selected, wav_limit=None, drained_frames=None):
    """Validate enabled PCM; raw/omitted selection delegates the frozen ABI13 core."""
    selected = _selected(selected)
    if selected is None or selected['profile'] == 'raw':
        return legacy.validate_audio(value, 'on', wav_limit, drained_frames)
    core = _filtered_core(value, selected)
    _wav_limit(wav_limit, selected['sample_rate'])
    if drained_frames is not None and (
            type(drained_frames) is not int or not 0 <= drained_frames <= core['frames']):
        raise ValueError('drained PCM count must be within generated output frames')
    written = core['frames'] if drained_frames is None else drained_frames
    expected = min(written, wav_limit) if wav_limit is not None else 0
    truncated = wav_limit is not None and written > wav_limit
    if core['wav_frames'] != expected or core['wav_truncated'] != truncated:
        raise ValueError('WAV counters disagree with output-domain drain and frame cap')
    return core


def raw_projection(value):
    """Project a validated filtered core onto raw ABI13 fields, excluding WAV.

    Source counts are reported by the runtime; never derive them from ticks.
    The caller must first validate the WAV/drain contract for its checkpoint.
    """
    if not isinstance(value, dict):
        raise ValueError('validated filtered core required')
    selected = _selected({'profile': 'filtered', 'sample_rate': value.get('sample_rate')})
    core = _filtered_core(value, selected)
    processing = core['processing']
    return {'enabled': True, 'sample_rate': 44100, 'channels': 2,
            'frames': processing['source_frames'],
            'psg_nonzero': core['psg_nonzero'], 'adpcm_nonzero': core['adpcm_nonzero'],
            'cdda_nonzero': core['cdda_nonzero'],
            'mixed_nonzero': processing['raw_mixed_nonzero'],
            'peak': processing['raw_peak'], 'pcm_hash': processing['raw_pcm_hash'],
            'discarded_frames': 0}


def headless_audio(value, selected, wav_limit=None, allow_pending=False):
    """Validate reference PCM without inventing an unreported drain count.

    Unsaturated WAV counters identify the output drain exactly. A saturated,
    truncated capture identifies only an interval. With no WAV capture, the
    headless diagnostics do not expose pending output at all.
    """
    selected = _selected(selected)
    if type(allow_pending) is not bool:
        raise ValueError('allow_pending must be a boolean')
    if not allow_pending or wav_limit is None:
        return validate_audio(value, selected, wav_limit)
    rate = 44100 if selected is None else selected['sample_rate']
    _wav_limit(wav_limit, rate)
    if not isinstance(value, dict):
        raise ValueError('headless PCM object required')
    # Validate the complete core before interpreting checkpoint WAV counters.
    core = copy.deepcopy(value)
    written, truncated = core.get('wav_frames'), core.get('wav_truncated')
    _nonnegative(written, 'audio_output.wav_frames')
    if type(truncated) is not bool:
        raise ValueError('audio_output.wav_truncated must be a boolean')
    core.update(wav_frames=0, wav_truncated=False)
    validate_audio(core, selected)
    frames = core['frames']
    if written < wav_limit or not truncated:
        if not 0 <= frames - written <= desktop.PCM_PENDING_CAPACITY:
            raise ValueError('headless checkpoint pending PCM exceeds output queue capacity')
        return validate_audio(value, selected, wav_limit, drained_frames=written)
    # A possible drain belongs to both cap+1..generated and
    # generated-capacity..generated. Do not persist any guessed drain value.
    if max(wav_limit + 1, frames - desktop.PCM_PENDING_CAPACITY) > frames:
        raise ValueError('headless truncated WAV has no possible bounded drain interval')
    return validate_audio(value, selected, wav_limit, drained_frames=frames)


def desktop_audio(value, selected, wav_limit, allow_pending=False):
    """Return the validated filtered core of a muted unthrottled desktop host."""
    selected = _selected(selected)
    if selected is None or selected['profile'] == 'raw':
        return desktop.desktop_audio(value, wav_limit, allow_pending)
    if type(allow_pending) is not bool:
        raise ValueError('allow_pending must be a boolean')
    if (not isinstance(value, dict)
            or set(value) != FILTERED_FIELDS | {'device_open', 'fast_forward_muted', 'host'}):
        raise ValueError('exact filtered desktop PCM/processing/host fields required')
    if value['device_open'] is not True or value['fast_forward_muted'] is not True:
        raise ValueError('filtered desktop requires an open device and fast-forward mute')
    host = value['host']
    if not isinstance(host, dict) or set(host) != desktop.AUDIO_HOST_FIELDS | DEVICE_FORMAT_FIELDS:
        raise ValueError('exact filtered SDL host counters and format fields required')
    for key in desktop.AUDIO_HOST_FIELDS:
        _nonnegative(host[key], 'audio_output.host.' + key)
    # AudioHostStats stores these in unsigned (32 bits on qualified Windows
    # x64). SDL_AudioSpec rate/channels are positive signed int before casting.
    # device_format remains a queried numeric enum, without an invented set.
    for key in DEVICE_FORMAT_FIELDS:
        _nonnegative(host[key], 'audio_output.host.' + key,
                     INT32_MAX if key in ('device_rate', 'device_channels') else UINT32_MAX)
    if host['input_rate'] != selected['sample_rate'] or any(
            host[key] <= 0 for key in ('device_rate', 'device_channels', 'device_format')):
        raise ValueError('SDL input rate must match selection; queried device format must be positive')
    core = {key: copy.deepcopy(value[key]) for key in FILTERED_FIELDS}
    validate_audio(core, selected, wav_limit,
                   host['submitted_frames'] if allow_pending else None)
    pending = core['frames'] - host['submitted_frames']
    if (not 0 <= pending <= (desktop.PCM_PENDING_CAPACITY if allow_pending else 0)
            or host['dropped_frames'] != host['submitted_frames']
            or host['queued_frames'] != 0 or host['peak_queue_frames'] != 0):
        raise ValueError('muted SDL presentation requires bounded output pending, equal drops and zero queues')
    if host['clears'] < 1 or host['pauses'] < 1:
        raise ValueError('muted SDL stream must be paused and cleared')
    return core
