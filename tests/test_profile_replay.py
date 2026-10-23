"""Synthetic profile forwarding and exact guest-state projection checks."""
import copy
import unittest

from scripts.replay_route import compare_status, validate_descriptor_selection, validate_route
from tests.test_audio_qualification import pcm
from tests.test_replay import route_fixture


def filtered_audio():
    value = pcm()
    value.update(sample_rate=48000, frames=160, mixed_nonzero=155, peak=2000,
                 pcm_hash=4321, psg_nonzero=20, adpcm_nonzero=30, cdda_nonzero=40,
                 wav_frames=0, wav_truncated=False)
    value["processing"] = {"profile": "filtered-v1", "source_rate": 44100,
        "source_frames": 147, "raw_pcm_hash": 1234, "raw_peak": 3000,
        "raw_mixed_nonzero": 140, "resampler": "sinc64-q30-v1",
        "latency_source_frames": 31, "tail_flushed": False}
    return value


class ProfileReplayTests(unittest.TestCase):
    def test_frozen_route_cannot_smuggle_profile_or_rate_overrides(self):
        for flag in ("--audio-profile", "--audio-rate"):
            route = route_fixture()
            route["initial_command"] += [flag, "filtered"]
            with self.assertRaises(ValueError):
                validate_route(route)
            route["initial_command"][-2:] = [flag + "=filtered"]
            with self.assertRaises(ValueError):
                validate_route(route)

    def test_legacy_descriptor_omission_and_explicit_raw_default(self):
        validate_descriptor_selection({"runtime": {"audio": "off"}}, None)
        validate_descriptor_selection({"runtime": {"audio": "on"}},
                                      {"profile": "raw", "sample_rate": 44100})

    def test_declared_profile_requires_explicit_execution_selection(self):
        for runtime in ({"audio": "on", "audio_profile": "filtered"},
                        {"audio": "on", "audio_profile": "raw"},
                        {"audio": "on", "audio_rate": 44100}):
            with self.subTest(runtime=runtime), self.assertRaises(ValueError):
                validate_descriptor_selection({"runtime": runtime}, None)

    def test_descriptor_profile_rate_and_audio_mode_must_agree(self):
        selected = {"profile": "filtered", "sample_rate": 48000}
        validate_descriptor_selection({"runtime": {"audio": "on", "audio_profile": "filtered",
                                                    "audio_rate": 48000}}, selected)
        for runtime in ({"audio": "off", "audio_profile": "filtered", "audio_rate": 48000},
                        {"audio": "on", "audio_profile": "filtered"},
                        {"audio": "on"},
                        {"audio": "on", "audio_profile": "raw", "audio_rate": 48000}):
            with self.subTest(runtime=runtime), self.assertRaises(ValueError):
                validate_descriptor_selection({"runtime": runtime}, selected)

    def test_processed_audio_is_validated_before_guest_projection(self):
        expected = route_fixture()["last_status"]
        actual = copy.deepcopy(expected)
        actual["host"]["audio_output"] = filtered_audio()
        selected = {"profile": "filtered", "sample_rate": 48000}
        compare_status(expected, actual, audio_mode="on", audio_selection=selected)
        with self.assertRaises(ValueError):
            compare_status(expected, actual, audio_mode="on")
        actual["host"]["audio_output"]["processing"]["latency_source_frames"] = 0
        with self.assertRaises(ValueError):
            compare_status(expected, actual, audio_mode="on", audio_selection=selected)

    def test_processed_projection_retains_all_original_guest_diagnostics(self):
        expected = route_fixture()["last_status"]
        for edit in (lambda value: value["host"].update(native_steps=3),
                     lambda value: value["host"].update(unexpected_guest=0),
                     lambda value: value["host"]["cpu"].update(mpr=[1] * 8)):
            actual = copy.deepcopy(expected)
            actual["host"]["audio_output"] = filtered_audio()
            edit(actual)
            with self.assertRaises(RuntimeError):
                compare_status(expected, actual, audio_mode="on",
                               audio_selection={"profile": "filtered", "sample_rate": 48000})

    def test_selected_audio_cannot_be_projected_under_off_or_implicit_mode(self):
        expected = route_fixture()["last_status"]
        actual = copy.deepcopy(expected)
        actual["host"]["audio_output"] = filtered_audio()
        for mode in (None, "off"):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                compare_status(expected, actual, audio_mode=mode,
                               audio_selection={"profile": "filtered", "sample_rate": 48000})


if __name__ == "__main__":
    unittest.main()
