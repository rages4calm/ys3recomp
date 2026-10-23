"""Authored ABI 13 audio contracts and upgrade drift fixtures."""
import copy
import unittest

from scripts.audio_contract import PCM_INITIAL_HASH, audio_command, extract_audio, validate_audio
from scripts.qualify_audio import qualify_audio
from tests.test_coverage import fixtures


def pcm(mode="on", frames=100):
    return {"enabled": mode == "on", "sample_rate": 44100, "channels": 2,
            "frames": frames if mode == "on" else 0,
            "psg_nonzero": 10 if mode == "on" else 0,
            "adpcm_nonzero": 20 if mode == "on" else 0,
            "cdda_nonzero": 30 if mode == "on" else 0,
            "mixed_nonzero": 40 if mode == "on" else 0,
            "peak": 1000 if mode == "on" else 0,
            "pcm_hash": 123456 if mode == "on" else PCM_INITIAL_HASH,
            "discarded_frames": 0, "wav_frames": 0, "wav_truncated": False}


def upgrade(mode="on"):
    before, after, reference, oldrun, newrun = fixtures()
    for run in (reference, oldrun, newrun):
        run.update(native_steps=100, interpreter_steps=0, native_block_steps=5,
                   interpreter_block_steps=0, guard_misses=0)
    for receipt in (before, after):
        for field in ("final_status", "released_status"):
            receipt[field]["host"].update(native_steps=100, interpreter_steps=0)
        receipt["before_final_release"] = copy.deepcopy(receipt["final_status"])
        receipt["checkpoint_status"] = [copy.deepcopy(receipt["final_status"])]
    output = pcm(mode)
    if mode == "on":
        for field in ("before_final_release", "final_status", "released_status"):
            after[field]["host"]["audio_output"] = copy.deepcopy(output)
        after["checkpoint_status"][0]["host"]["audio_output"] = copy.deepcopy(output)
    after["audio_contract"] = {"runtime_abi": 13, "mode": mode,
                               "wav_frame_limit": None, "headless_pcm_only": True,
                               "validated_output": copy.deepcopy(output) if mode == "on" else None,
                               "audio_output_absent": mode == "off"}
    if mode == "on":
        newrun["audio_output"] = copy.deepcopy(output)
    audio_reference = {"audio_output": pcm("on")}
    return before, after, reference, oldrun, newrun, audio_reference, mode


class AudioContractTests(unittest.TestCase):
    def test_explicit_drained_pcm_validates_actual_unsaturated_wave_counters(self):
        value = pcm()
        value.update(wav_frames=71, wav_truncated=False)
        validate_audio(value, "on", 200, drained_frames=71)
        with self.assertRaises(ValueError):
            validate_audio(value, "on", 200)
        for drained in (True, -1, 101, 71.0):
            with self.subTest(drained=drained), self.assertRaises(ValueError):
                validate_audio(value, "on", 200, drained_frames=drained)
        value.update(wav_frames=70, wav_truncated=False)
        validate_audio(value, "on", 70, drained_frames=70)
        value["wav_truncated"] = True
        validate_audio(value, "on", 70, drained_frames=71)
        with self.assertRaises(ValueError):
            validate_audio(value, "on", 70, drained_frames=70)

    def test_explicit_modes_preserve_original_arguments(self):
        command = ["runner", "authored"]
        self.assertEqual(audio_command(command, "off", "wave"), command + ["--audio-output", "off"])
        self.assertEqual(audio_command(command, "on", "wave", 12),
                         command + ["--audio-output", "on", "--audio-out", "wave", "--audio-frames", "12"])
        self.assertEqual(command, ["runner", "authored"])

    def test_output_requires_explicit_on_and_bounded_frames(self):
        for mode, limit in ((None, 1), ("off", 1), ("on", True), ("on", 0), ("on", 5292001)):
            with self.subTest(mode=mode, limit=limit), self.assertRaises(ValueError):
                audio_command(["runner"], mode, "wave", limit)
        with self.assertRaises(ValueError):
            audio_command(["runner", "--audio-output", "off"], "on", "wave")

    def test_exact_schema_rejects_missing_unknown_or_desktop_fields(self):
        for change in (lambda v: v.pop("frames"), lambda v: v.update(unknown=0),
                       lambda v: v.update(device_open=True)):
            value = pcm()
            change(value)
            with self.assertRaisesRegex(ValueError, "exact ABI 13"):
                validate_audio(value, "on")

    def test_numeric_types_loss_and_format_are_not_normalized(self):
        for key, changed in (("frames", True), ("discarded_frames", 1), ("sample_rate", 48000),
                             ("channels", 1), ("peak", 32769), ("pcm_hash", 1 << 64),
                             ("psg_nonzero", 101), ("enabled", 1), ("wav_truncated", 0)):
            value = pcm()
            value[key] = changed
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_audio(value, "on")

    def test_off_bridge_requires_absence_without_inventing_zero_telemetry(self):
        self.assertIsNone(extract_audio({}, "off"))
        for value in (None, pcm("off"), pcm("on"), {}, False):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "must be absent"):
                extract_audio({"audio_output": value}, "off")
        with self.assertRaises(ValueError):
            extract_audio({}, "on")

    def test_wav_counter_bound_is_exact(self):
        value = pcm()
        value.update(wav_frames=20, wav_truncated=True)
        validate_audio(value, "on", 20)
        for key, changed in (("wav_frames", 21), ("wav_truncated", False)):
            altered = dict(value, **{key: changed})
            with self.assertRaises(ValueError):
                validate_audio(altered, "on", 20)


class AudioUpgradeQualificationTests(unittest.TestCase):
    def test_off_rejects_any_exposed_pcm_object_in_runner_or_status(self):
        for field in ("runner", "before_final_release", "final_status", "released_status", "checkpoint_status"):
            values = upgrade("off")
            if field == "runner":
                values[4]["audio_output"] = pcm("off")
            elif field == "checkpoint_status":
                values[1][field][0]["host"]["audio_output"] = None
            else:
                values[1][field]["host"]["audio_output"] = pcm("off")
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "must be absent"):
                qualify_audio(*values)

    def test_on_presence_proves_nonabsence_in_preexisting_contract_receipt(self):
        values = upgrade("on")
        values[1]["audio_contract"].pop("audio_output_absent")
        result = qualify_audio(*values)
        self.assertFalse(result["audio_output_absent"])
        values[1]["audio_contract"]["audio_output_absent"] = True
        with self.assertRaisesRegex(ValueError, "audio_output_absent"):
            qualify_audio(*values)

    def test_on_and_off_require_unchanged_tiers_and_guest_state(self):
        for mode in ("on", "off"):
            result = qualify_audio(*upgrade(mode))
            self.assertTrue(result["audio_qualified"])
            self.assertTrue(result["unchanged_tier_counts"])
            self.assertEqual(result["native_steps_gained"], 0)
            self.assertEqual(result["checkpoint_status_checks"], 1)

    def test_same_total_different_native_distribution_is_rejected(self):
        values = upgrade()
        values[4].update(native_steps=99, interpreter_steps=1)
        with self.assertRaisesRegex(ValueError, "unchanged_tiers"):
            qualify_audio(*values)

    def test_pcm_reference_hash_and_source_counts_are_exact(self):
        for key in ("pcm_hash", "psg_nonzero", "adpcm_nonzero", "cdda_nonzero", "frames"):
            values = upgrade()
            values[5]["audio_output"][key] += 1
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "audio_reference_pcm"):
                qualify_audio(*values)

    def test_pcm_status_drift_and_unknown_guest_diagnostic_fail(self):
        values = upgrade()
        values[1]["released_status"]["host"]["audio_output"]["pcm_hash"] += 1
        with self.assertRaisesRegex(ValueError, "released_status.audio_output"):
            qualify_audio(*values)
        values = upgrade()
        values[1]["final_status"]["host"]["unknown"] = 0
        with self.assertRaises(RuntimeError):
            qualify_audio(*values)

    def test_checkpoint_guest_drift_and_audio_loss_fail(self):
        for change in (lambda v: v["host"]["cpu"]["instruction_generations"].append(9),
                       lambda v: v["host"]["audio_output"].update(discarded_frames=1)):
            values = upgrade()
            change(values[1]["checkpoint_status"][0])
            with self.assertRaises((ValueError, RuntimeError)):
                qualify_audio(*values)

    def test_missing_explicit_contract_fails(self):
        values = upgrade()
        values[1].pop("audio_contract")
        with self.assertRaisesRegex(ValueError, "explicit ABI 13"):
            qualify_audio(*values)


if __name__ == "__main__":
    unittest.main()
