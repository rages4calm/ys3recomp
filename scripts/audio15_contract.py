"""ABI15 timing wrapper over the frozen ABI13 PCM/DSP contracts.

Reviewed against e0f67bf64fe670723acd4443b0da76f3bfe8276f: the shared
headless/TCP PCM writer adds only timing='gear-v1' for Gear timing. Explicit
legacy timing omits that field. Processing, host and WAV schemas are retained.
This module does not project away any guest CDDA/PSG state.
"""
from __future__ import annotations

import copy

if __package__:
    from . import audio_contract as legacy
    from . import dsp_contract as dsp
else:
    import audio_contract as legacy
    import dsp_contract as dsp


SELECTION_FIELDS = {'profile', 'sample_rate', 'timing'}


def selection(mode, profile=None, rate=None, timing=None, wav_limit=None):
    """Normalize enabled ABI15 audio, including the actual default Gear timing."""
    if mode is not None and (type(mode) is not str or mode not in ('on', 'off')):
        raise ValueError('audio mode must be on or off')
    if mode != 'on':
        if any(value is not None for value in (profile, rate, timing, wav_limit)):
            raise ValueError('audio profile/rate/timing/WAV selections require explicit audio on')
        return None
    if timing is not None and (type(timing) is not str or timing not in ('gear', 'legacy')):
        raise ValueError('audio timing must be gear or legacy')
    if profile is not None and type(profile) is not str:
        raise ValueError('audio profile must be raw or filtered')
    chosen = dsp.selection('on', profile, rate, wav_limit)
    if chosen is None:
        # Supplying the normalized defaults also validates the raw WAV cap.
        chosen = dsp.selection('on', 'raw', 44100, wav_limit)
    return dict(chosen, timing='gear' if timing is None else timing)


def _selection(value):
    if not isinstance(value, dict) or set(value) != SELECTION_FIELDS:
        raise ValueError('exact normalized ABI15 audio selection required')
    chosen = selection('on', value['profile'], value['sample_rate'], value['timing'])
    if chosen != value:
        raise ValueError('normalized ABI15 audio selection required')
    return chosen


def _dsp_selection(selected):
    return {'profile': selected['profile'], 'sample_rate': selected['sample_rate']}


def audio_command(command, mode, output, wav_limit=None, profile=None, rate=None, timing=None):
    """Refuse hidden timing overrides even on omitted/off paths.

    Other legacy argv behavior remains delegated. Only an explicitly supplied
    timing adds a flag; default Gear is recorded in normalized selection.
    """
    if any(str(argument).split('=', 1)[0] == '--audio-timing' for argument in command):
        raise ValueError('frozen source command already specifies audio timing')
    selection(mode, profile, rate, timing, wav_limit)
    result = dsp.audio_command(command, mode, output, wav_limit, profile, rate)
    if timing is not None:
        result += ['--audio-timing', timing]
    return result


def _strip_timing(value, selected):
    selected = _selection(selected)
    if not isinstance(value, dict):
        raise ValueError('ABI15 audio_output object required')
    result = copy.deepcopy(value)
    if selected['timing'] == 'gear':
        if type(result.get('timing')) is not str or result['timing'] != 'gear-v1':
            raise ValueError('Gear audio requires exact timing=gear-v1 telemetry')
        result.pop('timing')
    elif 'timing' in result:
        raise ValueError('legacy audio must retain the schema without timing telemetry')
    return result, selected


def _restore_timing(core, selected):
    result = copy.deepcopy(core)
    if selected['timing'] == 'gear':
        result['timing'] = 'gear-v1'
    return result


def validate_headless(value, selected, wav_limit=None, allow_pending=False):
    """Return validated complete ABI15 headless PCM, preserving Gear timing."""
    if type(allow_pending) is not bool:
        raise ValueError('allow_pending must be a boolean')
    if selected is None:
        if value is not None or wav_limit is not None:
            raise ValueError('disabled/omitted audio requires absent PCM and no WAV capture')
        return None
    core, selected = _strip_timing(value, selected)
    validated = dsp.headless_audio(core, _dsp_selection(selected), wav_limit, allow_pending)
    return _restore_timing(validated, selected)


def validate_desktop(value, selected, wav_limit, allow_pending=False):
    """Validate muted packaged desktop output and return its full ABI15 core."""
    if type(allow_pending) is not bool:
        raise ValueError('allow_pending must be a boolean')
    core, selected = _strip_timing(value, selected)
    validated = dsp.desktop_audio(core, _dsp_selection(selected), wav_limit, allow_pending)
    return _restore_timing(validated, selected)


def canonical(value, selected):
    """Remove only validated timing metadata for a deliberate epoch comparison.

    Call a full validator first for the observation's actual WAV/drain context.
    This does not assert equivalence between Gear and legacy sample values.
    """
    if selected is None:
        if value is not None:
            raise ValueError('absent audio selection requires absent PCM')
        return None
    core, selected = _strip_timing(value, selected)
    expected = dsp.FILTERED_FIELDS if selected['profile'] == 'filtered' else legacy.PCM_FIELDS
    if set(core) != expected:
        raise ValueError('canonical audio requires the exact validated PCM core')
    return core


def raw_projection(value, selected):
    """Retain the selected timing when projecting processed PCM to its source."""
    chosen = _selection(selected)
    core = canonical(value, chosen)
    if chosen['profile'] == 'filtered':
        projected = dsp.raw_projection(core)
    else:
        projected = {key: copy.deepcopy(item) for key, item in core.items()
                     if key not in ('wav_frames', 'wav_truncated')}
    return _restore_timing(projected, chosen)
