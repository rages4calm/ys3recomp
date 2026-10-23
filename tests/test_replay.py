"""Authored route-validation and diagnostic-comparison fixtures only."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.replay_route import compare_status, source_binary_anchor, unwrap_execution, validate_route


def route_fixture():
    return {
        "initial_command": ["runner", "payload", "0", "0", "0", "100", "100", "hybrid",
                            "--dev-port", "0", "--dev-start-paused", "on", "--bram", "seed",
                            "--dev-memory-write", "on"],
        "steps": [{"frames": 2, "mask": 0, "target_frame": 3}],
        "checkpoints": [],
        "last_status": {"id": 4, "ok": True, "frame": 3, "ticks": 9,
                        "paused": True, "local_paused": False,
                        "host": {"native_steps": 2, "interpreter_steps": 6,
                                 "cpu": {"instruction_generations": [7], "mpr": [0] * 8},
                                 "cd_control": {"bram_seeded": True}, "buttons": [0] * 5}},
    }


class ReplayValidationTests(unittest.TestCase):
    def test_recorded_block_overshoot_is_allowed(self):
        self.assertEqual(validate_route(route_fixture()), {0, 3})

    def test_step_bounds_and_booleans_rejected(self):
        for field, value in (("frames", 0), ("frames", 601), ("frames", True),
                             ("mask", -1), ("mask", 4096), ("mask", False),
                             ("target_frame", 1)):
            with self.subTest(field=field, value=value):
                route = route_fixture()
                route["steps"][0][field] = value
                with self.assertRaises(ValueError):
                    validate_route(route)

    def test_checkpoint_requires_paused_boundary(self):
        route = route_fixture()
        route["checkpoints"] = [{"frame": 2, "file": "authored.png", "png_sha256": "0" * 64}]
        with self.assertRaises(ValueError):
            validate_route(route)

    def test_memory_expected_bytes_and_range(self):
        edit = {"memory_write": {"address": 12, "data": "a0", "expected": "00"}, "frame": 3}
        route = route_fixture()
        route["steps"].append(edit)
        validate_route(route)
        for invalid in ("", "0", "AA", "a ", "gg", "00" * 257, False):
            changed = copy.deepcopy(route)
            changed["steps"][-1]["memory_write"]["expected"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_route(changed)
        for address in (-1, 0x200000, True):
            changed = copy.deepcopy(route)
            changed["steps"][-1]["memory_write"]["address"] = address
            with self.assertRaises(ValueError):
                validate_route(changed)
        edit["memory_write"].update(address=0x1FFFFF, data="0000", expected="0000")
        with self.assertRaises(ValueError):
            validate_route(route)

    def test_memory_edit_requires_opt_in_and_current_frame(self):
        route = route_fixture()
        route["steps"].append({"memory_write": {"address": 12, "data": "a0", "expected": "00"}, "frame": 2})
        with self.assertRaises(ValueError):
            validate_route(route)
        route["steps"][-1]["frame"] = 3
        route["initial_command"][-1] = "off"
        with self.assertRaises(ValueError):
            validate_route(route)

    def test_child_file_output_is_rejected(self):
        for flag in ("--frame-out", "--window-capture", "--wall-seconds"):
            route = route_fixture()
            route["initial_command"] += [flag, "output"]
            with self.assertRaises(ValueError):
                validate_route(route)


class StatusComparisonTests(unittest.TestCase):
    def test_request_metadata_does_not_affect_guest_state(self):
        expected = route_fixture()["last_status"]
        actual = copy.deepcopy(expected)
        actual["id"] = 987
        compare_status(expected, actual)

    def test_only_named_execution_counters_can_be_projected(self):
        expected = route_fixture()["last_status"]
        actual = copy.deepcopy(expected)
        actual["host"].update(native_steps=7, interpreter_steps=1)
        with self.assertRaises(RuntimeError):
            compare_status(expected, actual)
        compare_status(expected, actual, True)
        self.assertEqual(expected["host"]["native_steps"], 2)

    def test_source_generation_and_all_guest_fields_remain_exact(self):
        expected = route_fixture()["last_status"]
        for mutate in (
                lambda value: value["host"]["cpu"]["instruction_generations"].append(8),
                lambda value: value["host"]["cpu"]["mpr"].__setitem__(0, 1),
                lambda value: value["host"]["cd_control"].update(bram_seeded=False),
                lambda value: value.update(ticks=10),
                lambda value: value.update(local_paused=True),
                lambda value: value["host"].update(new_diagnostic=1)):
            actual = copy.deepcopy(expected)
            mutate(actual)
            with self.assertRaises(RuntimeError):
                compare_status(expected, actual, True)


class HistoricalBinaryAnchorTests(unittest.TestCase):
    def test_explicit_historical_anchor_accepts_exact_hash_without_route_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "historical-runner"
            old.write_bytes(b"authored synthetic historical executable fixture")
            command = ["active-build-may-no-longer-exist", "payload"]
            original = command.copy()
            expected = hashlib.sha256(old.read_bytes()).hexdigest()
            self.assertEqual(source_binary_anchor(command, root, expected, old.name), old.resolve())
            self.assertEqual(command, original)

    def test_wrong_historical_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "historical-runner"
            old.write_bytes(b"different authored fixture")
            with self.assertRaises(ValueError):
                source_binary_anchor(["runner"], root, "0" * 64, old)

    def test_default_mode_still_requires_original_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                source_binary_anchor(["missing-runner"], Path(directory), "0" * 64)


class SharedExecutionEnvelopeTests(unittest.TestCase):
    def test_qualified_contract_unwraps_same_runner_without_projection(self):
        runner = {"native_steps": 4, "interpreter_steps": 6, "device": {"writes": 3}}
        wrapper = {"kind": "pce-consumer-execution", "qualified": True,
                   "binary_sha256": "authored-hash", "result": runner}
        self.assertIs(unwrap_execution(wrapper, "authored-hash", require_contract=True), runner)
        self.assertIs(unwrap_execution(runner), runner)

    def test_wrong_binary_unqualified_or_missing_result_are_rejected(self):
        wrapper = {"kind": "pce-consumer-execution", "qualified": True,
                   "binary_sha256": "authored-hash", "result": {"ticks": 1}}
        for key, value in (("kind", "unrelated"), ("qualified", False),
                           ("qualified", 1), ("binary_sha256", "changed"), ("result", None)):
            candidate = dict(wrapper, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                unwrap_execution(candidate, "authored-hash", require_contract=True)
        with self.assertRaises(ValueError):
            unwrap_execution({"ticks": 1}, require_contract=True)


if __name__ == "__main__":
    unittest.main()
