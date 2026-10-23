"""Authored route-validation and diagnostic-comparison fixtures only."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.replay_route import (compare_status, source_binary_anchor, unwrap_execution,
                                 validate_project_binding, validate_project_mode,
                                 validate_project_outputs, validate_route)


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
        for flag in ("--frame-out", "--window-capture", "--wall-seconds", "--audio-out",
                     "--audio-frames", "--audio-output"):
            route = route_fixture()
            route["initial_command"] += [flag, "output"]
            with self.assertRaises(ValueError):
                validate_route(route)


class StatusComparisonTests(unittest.TestCase):
    def test_packaged_desktop_projection_requires_explicit_validated_host_mode(self):
        from tests.test_desktop_qualification import desktop_fixture
        baseline, candidate, _, _ = desktop_fixture()
        expected = copy.deepcopy(baseline["final_status"])
        expected["host"].pop("audio_output")
        actual = candidate["final_status"]
        with self.assertRaises(ValueError):
            compare_status(expected, actual, audio_mode="on", wav_limit=20)
        compare_status(expected, actual, audio_mode="on", wav_limit=20, desktop_packaged=True)
        actual["host"]["unexpected_guest_field"] = 0
        with self.assertRaisesRegex(RuntimeError, "unexpected_guest_field"):
            compare_status(expected, actual, audio_mode="on", wav_limit=20, desktop_packaged=True)

    def test_audio_extension_requires_explicit_mode_and_validation(self):
        from tests.test_audio_qualification import pcm
        expected = route_fixture()["last_status"]
        actual = copy.deepcopy(expected)
        actual["host"]["audio_output"] = pcm()
        with self.assertRaises(RuntimeError):
            compare_status(expected, actual)
        compare_status(expected, actual, audio_mode="on")
        actual["host"]["audio_output"]["discarded_frames"] = 1
        with self.assertRaises(ValueError):
            compare_status(expected, actual, audio_mode="on")

    def test_audio_projection_preserves_all_other_guest_fields(self):
        from tests.test_audio_qualification import pcm
        expected = route_fixture()["last_status"]
        actual = copy.deepcopy(expected)
        actual["host"].update(audio_output=pcm(), unknown_diagnostic=1)
        with self.assertRaisesRegex(RuntimeError, "unknown_diagnostic"):
            compare_status(expected, actual, audio_mode="on")

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


class SharedVerifyOnlyTests(unittest.TestCase):
    def binding_fixture(self):
        binding = {"descriptor_sha256": "authored-descriptor", "tool": {"source_sha256": "authored-source"},
                   "files": {"module_source": "authored-module", "bios": "authored-input"},
                   "revision_override": False}
        built = {"schema": 1, "kind": "pce-consumer-build", "binding": binding}
        verification = {"schema": 1, "verified": True, **copy.deepcopy(binding)}
        return built, verification

    def test_official_verified_binding_must_match_every_build_identity(self):
        built, verification = self.binding_fixture()
        self.assertEqual(validate_project_binding(built, verification), built["binding"])
        for change in (
                lambda value: value["tool"].update(source_sha256="changed"),
                lambda value: value["files"].update(module_source="changed"),
                lambda value: value["files"].update(bios="changed"),
                lambda value: value.update(descriptor_sha256="changed"),
                lambda value: value.update(revision_override=0),
                lambda value: value.update(verified=False),
                lambda value: value.update(unexpected_identity="extra")):
            changed = copy.deepcopy(verification)
            change(changed)
            with self.assertRaises(ValueError):
                validate_project_binding(built, changed)

    def test_exact_output_set_rejects_dependency_hash_change_addition_and_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "authored-runner"
            dependency = root / "authored-library"
            binary.write_bytes(b"synthetic executable fixture")
            dependency.write_bytes(b"synthetic dependency fixture")
            hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in root.iterdir()}
            built = {"binary": str(binary), "binary_sha256": hashes[binary.name], "output_files": hashes}
            self.assertEqual(validate_project_outputs(built, binary), hashes)
            dependency.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "output/dependency"):
                validate_project_outputs(built, binary)
            dependency.write_bytes(b"synthetic dependency fixture")
            added = root / "unexpected-library"
            added.write_bytes(b"unexpected")
            with self.assertRaisesRegex(ValueError, "output/dependency"):
                validate_project_outputs(built, binary)
            added.unlink()
            dependency.unlink()
            with self.assertRaisesRegex(ValueError, "output/dependency"):
                validate_project_outputs(built, binary)

    def test_selected_binary_must_match_recorded_path_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "runner"
            binary.write_bytes(b"synthetic executable")
            built = {"binary": str(binary), "binary_sha256": "0" * 64, "output_files": {}}
            with self.assertRaisesRegex(ValueError, "selected target"):
                validate_project_outputs(built, binary)

    def test_verify_only_requires_descriptor_and_build_pair(self):
        for descriptor, build, verify_only in ((None, None, True), ("descriptor", None, True),
                                                (None, "build", True), ("descriptor", None, False)):
            with self.subTest(descriptor=descriptor, build=build, verify_only=verify_only), self.assertRaises(ValueError):
                validate_project_mode(descriptor, build, verify_only)
        validate_project_mode(None, None, False)
        validate_project_mode("descriptor", "build", False)
        validate_project_mode("descriptor", "build", True)


if __name__ == "__main__":
    unittest.main()
