"""Authored replay timing selection and exposed-guest conservation checks."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
from itertools import product
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from scripts.replay_route import (ABI15_TOOL, compare_status, replay,
    runtime_audio_command, runtime_audio_selection, selected_audio,
    validate_descriptor_selection15, validate_route, validate_runtime_desktop_mode,
    argument_parser, main)
from tests.test_capture_replay import route as capture_route
from tests.test_dsp_contract import filtered, hosted
from tests.test_replay import route_fixture


def identity(abi=15):
    if abi != 15:
        return {"runtime_abi": abi}
    return {"runtime_abi": 15, "revision": ABI15_TOOL["revision"], "tracked_source_clean": True,
            "shared_source_identity": {"revision": ABI15_TOOL["revision"],
                                       "source_sha256": ABI15_TOOL["source_sha256"]}}


def selection(timing="gear"):
    return {"profile": "filtered", "sample_rate": 48000, "timing": timing}


def audio(timing="gear", desktop=False, pending=0):
    value = filtered(wav_limit=100, drained=160-pending)
    if timing == "gear":
        value["timing"] = "gear-v1"
    return hosted(value, pending) if desktop else value


class Abi15ReplayTests(unittest.TestCase):
    def parser_arguments(self):
        return ["--tool-root", "authored-tool", "--evidence-root", "authored-evidence",
                "--route", "authored-route.json", "--binary", "authored-runner",
                "--out", "authored-output"]

    def test_actual_cli_parser_preserves_zero_or_one_timing_option(self):
        self.assertIsNone(argument_parser().parse_args(self.parser_arguments()).audio_timing)
        for timing in ("gear", "legacy"):
            for option in (["--audio-timing", timing], ["--audio-timing=" + timing]):
                parsed = argument_parser().parse_args(self.parser_arguments() + option)
                self.assertEqual(parsed.audio_timing, timing)

    def test_actual_cli_parser_rejects_two_separated_equals_or_mixed_options(self):
        for first, second in product(("gear", "legacy"), repeat=2):
            for first_equals, second_equals in product((False, True), repeat=2):
                one = ["--audio-timing=" + first] if first_equals else ["--audio-timing", first]
                two = ["--audio-timing=" + second] if second_equals else ["--audio-timing", second]
                with self.subTest(first=one, second=two), redirect_stderr(io.StringIO()) as errors:
                    with self.assertRaises(SystemExit) as rejected:
                        argument_parser().parse_args(self.parser_arguments() + one + two)
                    self.assertEqual(rejected.exception.code, 2)
                    self.assertIn("must appear only once", errors.getvalue())

    def test_actual_main_rejects_duplicate_timing_before_replay(self):
        argv = ["replay_route.py"] + self.parser_arguments() + ["--audio-timing=legacy", "--audio-timing", "gear"]
        with patch.object(sys, "argv", argv), patch("scripts.replay_route.replay") as run:
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as rejected:
                    main()
            self.assertEqual(rejected.exception.code, 2)
            run.assert_not_called()

    def test_default_gear_explicit_legacy_and_old_omission_remain_distinct(self):
        self.assertEqual(runtime_audio_selection(identity(), "on"),
                         {"profile": "raw", "sample_rate": 44100, "timing": "gear"})
        self.assertEqual(runtime_audio_selection(identity(), "on", "filtered", 48000, "legacy", 100),
                         selection("legacy"))
        self.assertIsNone(runtime_audio_selection(identity(13), "on"))
        self.assertEqual(runtime_audio_selection(identity(13), "on", "filtered", 48000),
                         {"profile": "filtered", "sample_rate": 48000})
        for mode in (None, "off"):
            self.assertIsNone(runtime_audio_selection(identity(), mode))
            with self.assertRaises(ValueError):
                runtime_audio_selection(identity(), mode, timing="gear")

    def test_unreviewed_abi_or_source_cannot_enable_timing(self):
        for abi in (12, 14, 16, True, 15.0, "15"):
            with self.subTest(abi=abi), self.assertRaises(ValueError):
                runtime_audio_selection({"runtime_abi": abi}, "on")
        for mutation in (lambda x: x.update(revision="f"*40),
                         lambda x: x.update(tracked_source_clean=False),
                         lambda x: x.pop("shared_source_identity"),
                         lambda x: x["shared_source_identity"].update(source_sha256="f"*64)):
            changed = identity()
            mutation(changed)
            with self.assertRaises(ValueError):
                runtime_audio_selection(changed, "on")
        with self.assertRaises(ValueError):
            runtime_audio_selection(identity(13), "on", timing="legacy")

    def test_timing_flags_are_managed_and_never_duplicated(self):
        original = ["authored-runner", "authored-payload"]
        command = runtime_audio_command(original, "on", "authored.wav", 100,
                                        "filtered", 48000, "legacy", 15)
        self.assertEqual(command[-2:], ["--audio-timing", "legacy"])
        self.assertEqual(command.count("--audio-timing"), 1)
        self.assertEqual(original, ["authored-runner", "authored-payload"])
        self.assertNotIn("--audio-timing", runtime_audio_command(original, "on", "new.wav", runtime_abi=15))
        self.assertEqual(runtime_audio_command(original, None, "unused.wav"), original)
        for abi in (13, 15):
            for mode in (None, "off", "on"):
                for tail in (["--audio-timing", "gear"], ["--audio-timing=legacy"]):
                    with self.subTest(abi=abi, mode=mode, tail=tail), self.assertRaises(ValueError):
                        runtime_audio_command(original+tail, mode, "new.wav", runtime_abi=abi)
        with self.assertRaises(ValueError):
            runtime_audio_command(original, "on", "new.wav", timing="gear", runtime_abi=13)

    def test_frozen_route_rejects_timing_in_both_flag_forms(self):
        for tail in (["--audio-timing", "gear"], ["--audio-timing=legacy"]):
            value = route_fixture()
            value["initial_command"] += tail
            with self.assertRaises(ValueError):
                validate_route(value)

    def test_descriptor_default_gear_and_explicit_timing_bind_exactly(self):
        config = {"runtime": {"audio": "on", "audio_profile": "filtered", "audio_rate": 48000}}
        validate_descriptor_selection15(config, selection())
        with self.assertRaises(ValueError):
            validate_descriptor_selection15(config, selection("legacy"))
        config["runtime"]["audio_timing"] = "legacy"
        validate_descriptor_selection15(config, selection("legacy"))
        with self.assertRaises(ValueError):
            validate_descriptor_selection15(config, None)
        validate_descriptor_selection15({"runtime": {"audio": "off"}}, None)
        with self.assertRaises(ValueError):
            validate_descriptor_selection15({"runtime": {"audio": "off", "audio_timing": "gear"}}, None)

    def test_audio_off_packaged_proof_requires_explicit_verified_abi15_without_wav(self):
        validate_runtime_desktop_mode(True, True, "authored.toml", "off", None, 15)
        for abi, verify, descriptor, cap in ((13, True, "authored.toml", None),
                                            (15, False, "authored.toml", None),
                                            (15, True, None, None), (15, True, "authored.toml", 100)):
            with self.subTest(abi=abi, verify=verify, descriptor=descriptor, cap=cap), self.assertRaises(ValueError):
                validate_runtime_desktop_mode(True, verify, descriptor, "off", cap, abi)
        expected = route_fixture()["last_status"]
        compare_status(expected, copy.deepcopy(expected), audio_mode="off",
                       desktop_packaged=True, runtime_abi=15)
        for disabled_value in (None, {"enabled": False}, audio()):
            actual = copy.deepcopy(expected)
            actual["host"]["audio_output"] = disabled_value
            with self.assertRaises(ValueError):
                compare_status(expected, actual, audio_mode="off", desktop_packaged=True, runtime_abi=15)

    def test_actual_timing_markers_and_full_core_are_validated(self):
        for timing in ("gear", "legacy"):
            value = audio(timing)
            self.assertEqual(selected_audio(value, selection(timing), 100, runtime_abi=15), value)
            host = audio(timing, desktop=True)
            self.assertEqual(selected_audio(host, selection(timing), 100, desktop=True, runtime_abi=15), value)
            changed = copy.deepcopy(value)
            if timing == "gear":
                changed.pop("timing")
            else:
                changed["timing"] = "gear-v1"
            with self.assertRaises(ValueError):
                selected_audio(changed, selection(timing), 100, runtime_abi=15)
        with self.assertRaises(ValueError):
            selected_audio(audio(), selection(), 100, runtime_abi=14)
        with self.assertRaises(ValueError):
            selected_audio(audio(), selection(), 100, runtime_abi=13)

    def test_checkpoint_pending_is_bounded_and_terminal_output_fully_drained(self):
        value = audio(desktop=True, pending=7)
        selected_audio(value, selection(), 100, desktop=True, allow_pending=True, runtime_abi=15)
        with self.assertRaises(ValueError):
            selected_audio(value, selection(), 100, desktop=True, runtime_abi=15)

    def test_historical_guest_comparison_validates_audio_without_removing_guest_fields(self):
        expected = route_fixture()["last_status"]
        for timing in ("legacy", "gear"):
            actual = copy.deepcopy(expected)
            actual["host"]["audio_output"] = audio(timing)
            compare_status(expected, actual, audio_mode="on", wav_limit=100,
                           audio_selection=selection(timing), runtime_abi=15)
            actual["host"]["cpu"]["mpr"][7] = 1
            with self.assertRaises(RuntimeError):
                compare_status(expected, actual, audio_mode="on", wav_limit=100,
                               audio_selection=selection(timing), runtime_abi=15)
        actual = copy.deepcopy(expected)
        actual["host"].update(audio_output=audio(), unreviewed_held_clock_field=0)
        with self.assertRaises(RuntimeError):
            compare_status(expected, actual, audio_mode="on", wav_limit=100,
                           audio_selection=selection(), runtime_abi=15)
        compare_status(expected, copy.deepcopy(expected), audio_mode="off", runtime_abi=15)
        actual["host"].pop("unreviewed_held_clock_field")
        with self.assertRaises(ValueError):
            compare_status(expected, actual, audio_mode="off", runtime_abi=15)

    def test_abi15_replay_cannot_relabel_the_reviewed_abi13_capture_window(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence, tool = root/"evidence", root/"tool"
            evidence.mkdir();tool.mkdir()
            path = root/"route.json"
            path.write_text(json.dumps(capture_route()), encoding="utf-8")
            args = SimpleNamespace(out=str(root/"output"), evidence_root=str(evidence), tool_root=str(tool),
                project_descriptor=None, project_build=None, project_verify_only=False,
                audio_output="off", audio_frames=None, expected_revision=None, route=str(path),
                ignore_tier_counters=False, capture_start_frame=3, capture_limit=None)
            with patch("scripts.replay_route.upstream_client", return_value=(None, identity())):
                with self.assertRaisesRegex(ValueError, "managed capture requires reviewed runtime ABI 13"):
                    replay(args)
            receipt = json.loads((root/"output/receipt.json").read_text())
            self.assertFalse(receipt["passed"])
            self.assertNotIn("capture_contract", receipt)


if __name__ == "__main__":
    unittest.main()
