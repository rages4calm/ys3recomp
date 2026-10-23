"""Narrow packaged desktop diagnostics for an unthrottled TCP replay."""
from __future__ import annotations

import copy
import os
from pathlib import Path

if __package__:
    from .audio_contract import PCM_FIELDS, validate_audio
else:
    from audio_contract import PCM_FIELDS, validate_audio

AUDIO_HOST_FIELDS = {"submitted_frames", "dropped_frames", "clears", "pauses",
                     "queued_frames", "peak_queue_frames"}
DESKTOP_FIELDS = {"presented", "polls", "focus_losses", "gamepad_connections", "resize_events",
                  "pacing_resets", "keyboard_events", "gamepad_events", "input_pulses",
                  "unmapped_key_down", "last_unmapped_scancode"}
ASSET_FLAGS = ("--bios", "--toc", "--disc", "--libchdr", "--input-script", "--bram")
PCM_PENDING_CAPACITY = 8192  # Pinned AudioOutput::capacity; discarded_frames must stay zero.


def desktop_command(command, evidence):
    """Resolve existing asset arguments for a new, empty working directory."""
    result = command.copy()
    if any(flag in result for flag in ("--hidden", "--unthrottled")):
        raise ValueError("frozen route already specifies desktop presentation overrides")
    indexes = [1]
    for flag in ASSET_FLAGS:
        if flag in result:
            if result.count(flag) != 1 or result.index(flag) + 1 >= len(result):
                raise ValueError("invalid asset option: " + flag)
            indexes.append(result.index(flag) + 1)
    for index in indexes:
        path = Path(result[index])
        result[index] = str((path if path.is_absolute() else evidence / path).resolve(strict=True))
    return result + ["--hidden", "on", "--unthrottled", "on"]


def validate_desktop_mode(enabled, verify_only, descriptor, audio_mode, wav_limit):
    if enabled and (not verify_only or not descriptor or audio_mode != "on" or wav_limit is None):
        raise ValueError("packaged desktop requires project verify-only, audio on and bounded WAV capture")


def desktop_audio(value, wav_limit, allow_pending=False):
    """Validate desktop-only fields before returning the exact headless core."""
    if not isinstance(value, dict) or set(value) != PCM_FIELDS | {"device_open", "fast_forward_muted", "host"}:
        raise ValueError("audio_output: exact packaged desktop fields required")
    core = {key: copy.deepcopy(value[key]) for key in PCM_FIELDS}
    if value["device_open"] is not True or value["fast_forward_muted"] is not True:
        raise ValueError("desktop audio requires an open device and explicit fast-forward mute")
    host = value["host"]
    if not isinstance(host, dict) or set(host) != AUDIO_HOST_FIELDS:
        raise ValueError("audio_output.host: exact SDL host fields required")
    for key in AUDIO_HOST_FIELDS:
        if type(host[key]) is not int or host[key] < 0:
            raise ValueError("audio_output.host." + key + ": nonnegative integer required")
    validate_audio(core, "on", wav_limit,
                   drained_frames=host["submitted_frames"] if allow_pending else None)
    pending = core["frames"] - host["submitted_frames"]
    maximum_pending = PCM_PENDING_CAPACITY if allow_pending else 0
    if (not 0 <= pending <= maximum_pending or host["dropped_frames"] != host["submitted_frames"]
            or host["queued_frames"] != 0 or host["peak_queue_frames"] != 0):
        raise ValueError("fast-forward muted presentation requires equal submitted/dropped, zero host queue and bounded pending PCM")
    if host["clears"] < 1 or host["pauses"] < 1:
        raise ValueError("fast-forward mute must pause and clear the SDL stream")
    return core


def headless_status(status, wav_limit, allow_pending=False):
    result = copy.deepcopy(status)
    result["host"]["audio_output"] = desktop_audio(result["host"]["audio_output"], wav_limit, allow_pending)
    return result


def validate_desktop(value, frames):
    if not isinstance(value, dict) or set(value) != DESKTOP_FIELDS:
        raise ValueError("desktop: exact presentation diagnostic fields required")
    for key in DESKTOP_FIELDS:
        if type(value[key]) is not int or value[key] < 0:
            raise ValueError("desktop." + key + ": nonnegative integer required")
    if value["presented"] != frames or value["polls"] < frames:
        raise ValueError("desktop presentation/poll count disagrees with complete guest frames")
    for key in ("focus_losses", "pacing_resets", "keyboard_events", "gamepad_events", "input_pulses",
                "unmapped_key_down", "last_unmapped_scancode"):
        if value[key] != 0:
            raise ValueError("unrecorded desktop host input/event: " + key)
    return copy.deepcopy(value)


def validate_package_proof(value, binary_sha256):
    package = value["package_before"]
    fields = {"binary", "binary_sha256", "dll", "dll_sha256", "output_files", "official_desktop_build"}
    if not isinstance(package, dict) or set(package) != fields or package["official_desktop_build"] is not True:
        raise ValueError("exact official desktop package proof required")
    if package["binary_sha256"] != binary_sha256:
        raise ValueError("package proof binary hash differs from replay")
    if (package["output_files"].get(Path(package["binary"]).name) != binary_sha256
            or package["output_files"].get("SDL3.dll") != package["dll_sha256"]
            or Path(package["dll"]) != Path(package["binary"]).with_name("SDL3.dll")):
        raise ValueError("package proof lacks the pinned adjacent SDL DLL")
    env = value["environment"]
    if (not isinstance(env, dict) or set(env) != {"original_path", "child_path", "removed_entries",
            "removed_sdl_driver_overrides", "no_sdk_or_packaged_bin_path", "scope"}
            or env["no_sdk_or_packaged_bin_path"] is not True or not env["child_path"]):
        raise ValueError("exact sanitized package environment proof required")
    for entry in env["child_path"].split(os.pathsep):
        path = Path(entry.strip().strip('"'))
        if not path.is_absolute() or path == Path(package["binary"]).parent or (path / "SDL3.dll").exists():
            raise ValueError("child PATH retains a relative, SDK or packaged DLL search directory")
    before_pid = None
    for name in ("loaded_sdl_before", "loaded_sdl_final"):
        loaded = value[name]
        if (not isinstance(loaded, dict) or set(loaded) != {"pid", "executable", "binary_sha256",
                "loaded_sdl", "dll_sha256", "adjacent_package_loaded", "inspection"}
                or loaded["adjacent_package_loaded"] is not True):
            raise ValueError("exact live loaded SDL proof required")
        if type(loaded["pid"]) is not int or loaded["pid"] <= 0 or (before_pid is not None and loaded["pid"] != before_pid):
            raise ValueError("live DLL proofs must identify the same owned process")
        before_pid = loaded["pid"]
        for key, target in (("executable", "binary"), ("binary_sha256", "binary_sha256"),
                            ("loaded_sdl", "dll"), ("dll_sha256", "dll_sha256")):
            if loaded[key] != package[target]:
                raise ValueError("live loaded module differs from package: " + key)
