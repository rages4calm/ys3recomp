"""Authored packaged-desktop diagnostic and provenance drift checks."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.desktop_contract import (DESKTOP_FIELDS, desktop_audio, desktop_command,
                                      validate_desktop, validate_desktop_mode, validate_package_proof)
from scripts.qualify_desktop import qualify_desktop, verify_wav
from tests.test_audio_qualification import upgrade


def desktop_fixture():
    _, baseline, _, _, baseline_run, _, _ = upgrade("on")
    core = baseline_run["audio_output"]
    core.update(wav_frames=20, wav_truncated=True)
    baseline["binary_sha256"] = "authored-headless-binary"
    baseline["audio_contract"].update(wav_frame_limit=20, wav_sha256="authored-wave-hash", wav_bytes=124,
                                      validated_output=copy.deepcopy(core))
    for field in ("before_final_release", "final_status", "released_status"):
        baseline[field]["host"]["audio_output"] = copy.deepcopy(core)
    baseline["checkpoint_status"][0]["host"]["audio_output"] = copy.deepcopy(core)
    candidate, run = copy.deepcopy(baseline), copy.deepcopy(baseline_run)
    candidate.update(binary_sha256="authored-desktop-binary", shared_project_run_used=False,
                     project_execution_mode="shared-verify-then-consumer-route")
    candidate["audio_contract"]["headless_pcm_only"] = False
    full = dict(copy.deepcopy(core), device_open=True, fast_forward_muted=True,
                host={"submitted_frames": 100, "dropped_frames": 100, "queued_frames": 0,
                      "peak_queue_frames": 0, "clears": 1, "pauses": 1})
    for field in ("before_final_release", "final_status", "released_status"):
        candidate[field]["host"]["audio_output"] = copy.deepcopy(full)
    candidate["checkpoint_status"][0]["host"]["audio_output"] = copy.deepcopy(full)
    presentation = {key: 0 for key in DESKTOP_FIELDS}
    presentation.update(presented=60, polls=60, gamepad_connections=1, resize_events=1)
    run.update(audio_output=copy.deepcopy(full), desktop=copy.deepcopy(presentation))
    binary = str(Path.cwd() / "authored-package" / "pce-consumer.exe")
    dll = str(Path(binary).with_name("SDL3.dll"))
    package = {"binary": binary, "binary_sha256": candidate["binary_sha256"], "dll": dll,
               "dll_sha256": "authored-dll-hash", "official_desktop_build": True,
               "output_files": {"pce-consumer.exe": candidate["binary_sha256"], "SDL3.dll": "authored-dll-hash"}}
    loaded = {"pid": 1234, "executable": binary, "binary_sha256": candidate["binary_sha256"],
              "loaded_sdl": dll, "dll_sha256": "authored-dll-hash", "adjacent_package_loaded": True,
              "inspection": "authored live-module fixture"}
    candidate["desktop_contract"] = {
        "packaged": True, "hidden": True, "unthrottled": True,
        "working_directory_initially_empty": True, "working_directory_finally_empty": True,
        "package_before": package, "package_after": copy.deepcopy(package),
        "environment": {"original_path": str(Path.cwd() / "authored-system"),
                        "child_path": str(Path.cwd() / "authored-system"), "removed_entries": [],
                        "removed_sdl_driver_overrides": {}, "no_sdk_or_packaged_bin_path": True,
                        "scope": "authored PATH fixture"},
        "loaded_sdl_before": loaded, "loaded_sdl_final": copy.deepcopy(loaded),
        "audio_output": copy.deepcopy(full), "presentation": copy.deepcopy(presentation)}
    return baseline, candidate, baseline_run, run


class DesktopContractTests(unittest.TestCase):
    def test_checkpoint_wave_counters_follow_actual_drain_through_quota(self):
        full = desktop_fixture()[3]["audio_output"]
        full["host"].update(submitted_frames=71, dropped_frames=71)
        full.update(wav_frames=71, wav_truncated=False)
        desktop_audio(full, 200, allow_pending=True)
        with self.assertRaises(ValueError):
            desktop_audio(full, 200)
        full["frames"] = 129
        full["host"].update(submitted_frames=100, dropped_frames=100)
        full.update(wav_frames=100, wav_truncated=False)
        desktop_audio(full, 100, allow_pending=True)  # Exactly quota, not truncated yet.
        full["frames"] = 130
        full["host"].update(submitted_frames=101, dropped_frames=101)
        full["wav_truncated"] = True
        desktop_audio(full, 100, allow_pending=True)
        full["wav_truncated"] = False
        with self.assertRaises(ValueError):
            desktop_audio(full, 100, allow_pending=True)

    def test_only_checkpoint_mode_permits_bounded_pending_source_pcm(self):
        full = desktop_fixture()[3]["audio_output"]
        desktop_audio(full, 20, allow_pending=True)
        full["host"].update(submitted_frames=71, dropped_frames=71)
        desktop_audio(full, 20, allow_pending=True)
        with self.assertRaises(ValueError):
            desktop_audio(full, 20)
        full["frames"] = 10000
        full["host"].update(submitted_frames=1808, dropped_frames=1808)
        desktop_audio(full, 20, allow_pending=True)  # Exact 8192-frame capacity.
        for submitted, dropped in ((1807, 1807), (10001, 10001), (1808, 1807), (-1, -1)):
            altered = copy.deepcopy(full)
            altered["host"].update(submitted_frames=submitted, dropped_frames=dropped)
            with self.subTest(submitted=submitted, dropped=dropped), self.assertRaises(ValueError):
                desktop_audio(altered, 20, allow_pending=True)
        for key in ("queued_frames", "peak_queue_frames"):
            altered = copy.deepcopy(full)
            altered["host"][key] = 1
            with self.assertRaises(ValueError):
                desktop_audio(altered, 20, allow_pending=True)
        full["discarded_frames"] = 1
        with self.assertRaises(ValueError):
            desktop_audio(full, 20, allow_pending=True)

    def test_packaged_mode_requires_explicit_supervision_and_audio_capture(self):
        validate_desktop_mode(True, True, "descriptor", "on", 20)
        for values in ((True, False, "desc", "on", 20), (True, True, None, "on", 20),
                       (True, True, "desc", "off", 20), (True, True, "desc", "on", None)):
            with self.assertRaises(ValueError):
                validate_desktop_mode(*values)

    def test_asset_canonicalization_preserves_frozen_values_and_adds_only_host_flags(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ("payload", "bios", "disc", "library", "toc", "seed", "script"):
                (root / name).write_bytes(b"authored fixture")
            command = ["runner", "payload", "0", "0", "mpr", "100", "100", "hybrid",
                       "--bios", "bios", "--disc", "disc", "--libchdr", "library", "--toc", "toc",
                       "--bram", "seed", "--input-script", "script", "--dev-port", "0"]
            frozen = command.copy()
            result = desktop_command(command, root)
            self.assertEqual(command, frozen)
            self.assertEqual(result[2:8], command[2:8])
            self.assertEqual(result[-4:], ["--hidden", "on", "--unthrottled", "on"])
            self.assertEqual(result[1], str((root / "payload").resolve()))
            self.assertEqual(result[result.index("--bram") + 1], str((root / "seed").resolve()))
            with self.assertRaises(ValueError):
                desktop_command(command + ["--hidden", "on"], root)

    def test_desktop_pcm_rejects_unknown_fields_and_every_queue_drift(self):
        full = desktop_fixture()[3]["audio_output"]
        self.assertEqual(desktop_audio(full, 20)["frames"], 100)
        for change in (lambda v: v.update(unknown=0), lambda v: v.update(device_open=False),
                       lambda v: v.update(fast_forward_muted=False), lambda v: v["host"].update(unknown=0),
                       lambda v: v["host"].update(submitted_frames=99), lambda v: v["host"].update(dropped_frames=99),
                       lambda v: v["host"].update(queued_frames=1), lambda v: v["host"].update(peak_queue_frames=1),
                       lambda v: v["host"].update(pauses=0), lambda v: v["host"].update(clears=True)):
            altered = copy.deepcopy(full)
            change(altered)
            with self.assertRaises(ValueError):
                desktop_audio(altered, 20)

    def test_presentation_requires_exact_schema_frames_and_no_unrecorded_input(self):
        value = desktop_fixture()[3]["desktop"]
        validate_desktop(value, 60)
        for key, changed in (("presented", 59), ("polls", 59), ("keyboard_events", 1),
                             ("input_pulses", 1), ("unmapped_key_down", 1), ("unknown", 0)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_desktop(dict(value, **{key: changed}), 60)


class DesktopQualificationTests(unittest.TestCase):
    def test_checkpoint_pending_pcm_is_recorded_without_relaxing_endpoint(self):
        values = desktop_fixture()
        values[1]["checkpoint_status"][0]["host"]["audio_output"]["host"].update(submitted_frames=71, dropped_frames=71)
        result = qualify_desktop(*values)
        self.assertEqual(result["checkpoint_pending_pcm"], [{"index": 0, "frame": 60, "pending_frames": 29}])
        self.assertEqual(result["checkpoint_pending_pcm_limit"], 8192)
        values[1]["final_status"]["host"]["audio_output"]["host"].update(submitted_frames=71, dropped_frames=71)
        with self.assertRaises(ValueError):
            qualify_desktop(*values)

    def test_packaged_desktop_matches_headless_guest_pcm_and_wav(self):
        result = qualify_desktop(*desktop_fixture())
        self.assertTrue(result["packaged_desktop_qualified"])
        self.assertTrue(result["unchanged_tier_counts"])
        self.assertTrue(result["wav_matches_headless"])
        self.assertEqual(result["checkpoint_status_checks"], 1)

    def test_original_guest_diagnostic_and_checkpoint_drift_remain_errors(self):
        for change in (lambda v: v[1]["checkpoint_status"][0]["host"]["cpu"].update(unexpected=0),
                       lambda v: v[3]["device"].update(writes=7),
                       lambda v: v[3].update(native_steps=99, interpreter_steps=1)):
            values = desktop_fixture()
            change(values)
            with self.assertRaises((ValueError, RuntimeError)):
                qualify_desktop(*values)

    def test_pcm_and_wav_reference_drift_are_rejected(self):
        for change in (lambda v: v[3]["audio_output"].update(pcm_hash=42),
                       lambda v: v[1]["audio_contract"].update(wav_sha256="changed"),
                       lambda v: v[1]["audio_contract"].update(wav_frame_limit=21)):
            values = desktop_fixture()
            change(values)
            with self.assertRaises(ValueError):
                qualify_desktop(*values)

    def test_live_dll_binary_hash_path_pid_and_environment_are_bound(self):
        for change in (lambda v: v["loaded_sdl_final"].update(pid=5678),
                       lambda v: v["loaded_sdl_before"].update(loaded_sdl="sdk/SDL3.dll"),
                       lambda v: v["loaded_sdl_final"].update(dll_sha256="changed"),
                       lambda v: v["loaded_sdl_final"].update(binary_sha256="changed"),
                       lambda v: v["environment"].update(child_path="."),
                       lambda v: v["environment"].update(no_sdk_or_packaged_bin_path=False),
                       lambda v: v["package_before"].update(official_desktop_build=False)):
            values = desktop_fixture()
            change(values[1]["desktop_contract"])
            with self.assertRaises(ValueError):
                validate_package_proof(values[1]["desktop_contract"], values[1]["binary_sha256"])

    def test_wav_file_identity_is_checked_beyond_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            wav = root / "audio.wav"
            wav.write_bytes(b"authored synthetic wave fixture")
            receipt = {"audio_contract": {"wav_path": str(wav), "wav_sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
                                          "wav_bytes": wav.stat().st_size}}
            self.assertEqual(verify_wav(receipt, root / "receipt.json"), wav.resolve())
            wav.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                verify_wav(receipt, root / "receipt.json")


if __name__ == "__main__":
    unittest.main()
