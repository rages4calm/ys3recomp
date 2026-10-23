"""Strict ABI 13 headless PCM diagnostics; no host playback claim."""
from __future__ import annotations

import copy

PCM_FIELDS = {"enabled", "sample_rate", "channels", "frames", "psg_nonzero",
              "adpcm_nonzero", "cdda_nonzero", "mixed_nonzero", "peak", "pcm_hash",
              "discarded_frames", "wav_frames", "wav_truncated"}
PCM_INITIAL_HASH = 14695981039346656037
MAX_WAV_FRAMES = 5292000


def validate_audio(value, mode, wav_limit=None, drained_frames=None):
    """Reject missing/unknown fields and loss, including future schema drift."""
    if mode not in ("on", "off"):
        raise ValueError("audio mode must be on or off")
    if mode == "off":
        if value is not None or wav_limit is not None or drained_frames is not None:
            raise ValueError("audio_output must be absent when audio is off")
        return None
    if not isinstance(value, dict) or set(value) != PCM_FIELDS:
        raise ValueError("audio_output: exact ABI 13 headless PCM fields required")
    if type(value["enabled"]) is not bool or value["enabled"] != (mode == "on"):
        raise ValueError("audio_output.enabled disagrees with selected mode")
    if type(value["wav_truncated"]) is not bool:
        raise ValueError("audio_output.wav_truncated requires a boolean")
    for key in PCM_FIELDS - {"enabled", "wav_truncated"}:
        if type(value[key]) is not int or value[key] < 0:
            raise ValueError("audio_output." + key + ": requires a nonnegative integer")
    if value["sample_rate"] != 44100 or value["channels"] != 2:
        raise ValueError("audio_output: expected 44100 Hz stereo")
    if value["pcm_hash"] >= 1 << 64 or value["peak"] > 32768:
        raise ValueError("audio_output: invalid PCM hash or peak")
    if value["discarded_frames"] != 0:
        raise ValueError("audio_output: runtime PCM queue lost frames")
    for key in ("psg_nonzero", "adpcm_nonzero", "cdda_nonzero", "mixed_nonzero"):
        if value[key] > value["frames"]:
            raise ValueError("audio_output." + key + " exceeds PCM frames")
    if wav_limit is not None and (type(wav_limit) is not int or not 1 <= wav_limit <= MAX_WAV_FRAMES or mode != "on"):
        raise ValueError("WAV limit requires audio on and 1..5292000 frames")
    if drained_frames is not None and (type(drained_frames) is not int or not 0 <= drained_frames <= value["frames"]):
        raise ValueError("explicit drained PCM count must be an integer in 0..generated frames")
    # The default is a fully drained endpoint. A validated desktop pre-drain
    # checkpoint may instead supply the actual SDL submitted count: the same
    # drain writes WAV before it submits samples to SDL, without yielding.
    written_source_frames = value["frames"] if drained_frames is None else drained_frames
    expected_wav = min(written_source_frames, wav_limit) if wav_limit is not None else 0
    expected_truncated = wav_limit is not None and written_source_frames > wav_limit
    if value["wav_frames"] != expected_wav or value["wav_truncated"] != expected_truncated:
        raise ValueError("audio_output: WAV counters disagree with explicit output bound")
    return copy.deepcopy(value)


def extract_audio(container, mode, wav_limit=None):
    """The pinned runner omits this diagnostic entirely with audio off."""
    if mode == "off" and "audio_output" in container:
        raise ValueError("audio_output must be absent when audio is off")
    if mode == "on" and "audio_output" not in container:
        raise ValueError("audio_output is required when audio is on")
    return validate_audio(container.pop("audio_output", None), mode, wav_limit)


def without_audio(status, mode, wav_limit=None):
    result = copy.deepcopy(status)
    extract_audio(result["host"], mode, wav_limit)
    return result


def audio_command(command, mode, output, wav_limit=None):
    """Append only explicit audio overrides, preserving the frozen command."""
    result = command.copy()
    if any(flag in result for flag in ("--audio-output", "--audio-out", "--audio-frames")):
        raise ValueError("frozen source command already specifies audio options")
    if mode is None:
        if wav_limit is not None:
            raise ValueError("WAV capture requires explicit audio on")
        return result
    if mode not in ("off", "on"):
        raise ValueError("audio mode must be on or off")
    result += ["--audio-output", mode]
    if wav_limit is not None:
        if mode != "on" or type(wav_limit) is not int or not 1 <= wav_limit <= MAX_WAV_FRAMES:
            raise ValueError("WAV capture requires audio on and 1..5292000 frames")
        result += ["--audio-out", str(output), "--audio-frames", str(wav_limit)]
    return result
