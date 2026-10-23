"""Synthetic restored-boundary and managed upstream-capture supervision checks."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.replay_route import (capture_start_proof, finish_managed_capture,
    managed_capture_command, managed_capture_selection, sha256, validate_capture_summary,
    validate_route, verify_tool_root)

ROOT = Path(__file__).resolve().parents[1]


def route():
    patches = [{"frame": 1, "physical": 4096, "expected": "eaea", "data": "8080"},
               {"frame": 2, "physical": 4096, "expected": "8080", "data": "eaea"}]
    steps = []
    for frame in range(1, 5):
        steps.append({"frames": 1, "mask": 0, "target_frame": frame})
        if frame <= 2:
            p = patches[frame - 1]
            steps.append({"frame": frame, "memory_write": {
                "address": p["physical"], "expected": p["expected"], "data": p["data"]}})
    return {"initial_command": ["runner", "payload", "0", "0", "0", "100", "100", "hybrid",
              "--dev-port", "0", "--dev-start-paused", "on", "--bram", "seed",
              "--dev-memory-write", "on", "--video-output", "continuous"],
            "steps": steps, "checkpoints": [{"frame": 3, "file": "authored.png", "png_sha256": "0" * 64}],
            "last_status": {"frame": 4, "paused": True, "host": {"cd_control": {"bram_seeded": True}}},
            "assistance": {"jump_patch_active": False, "code_patches": patches}}


def status():
    return {"frame": 3, "ticks": 90, "paused": True, "local_paused": False,
            "host": {"pc": 8191, "native_steps": 10, "interpreter_steps": 20,
                     "cpu": {"mpr": [1, 3, 0, 0, 0, 0, 0, 0], "physical_pc": 16383,
                             "instruction_bytes": [234] * 7,
                             "instruction_physical": [16383] + list(range(24576, 24582)),
                             "instruction_generations": [2] * 7}}}


class Client:
    def __init__(self):
        self.before, self.after = status(), status()
        self.calls, self.reads = [], []
        self.data = b"\xea\xea"

    def call(self, name):
        self.calls.append(name)
        return copy.deepcopy(self.before if len(self.calls) == 1 else self.after)

    def read_memory(self, address, length):
        self.reads.append((address, length))
        return self.data


def completion():
    selected = managed_capture_selection(route(), 3)
    proof = capture_start_proof(Client(), selected)
    capture = {"schema": 1, "runtime_abi": 13, "capacity": 65536, "dropped_instructions": 0,
               "unreadable_instructions": 0, "retired_instructions": 9, "complete": True}
    runner = {"native_steps": 19, "interpreter_steps": 20,
              "code_capture_window": {"requested_start_frame": 3, "started": True,
                  "actual_start_frame": 3, "actual_start_ticks": 90,
                  "native_steps_before": 10, "interpreter_steps_before": 20}}
    return selected, proof, capture, runner


class ManagedCaptureTests(unittest.TestCase):
    def test_omitted_capture_preserves_command_without_receipt_selection(self):
        command = route()["initial_command"]
        self.assertIsNone(managed_capture_selection(route()))
        self.assertEqual(managed_capture_command(command, "unused.json", None), command)
        with self.assertRaises(ValueError):
            managed_capture_selection(route(), limit=10)

    def test_requires_paused_checkpoint_after_restoration_and_before_endpoint(self):
        self.assertEqual(managed_capture_selection(route(), 3)["canonical_bytes"], {4096: 234, 4097: 234})
        for start in (-1, 0, 1, 2, 4, True, 2.5):
            with self.subTest(start=start), self.assertRaises(ValueError):
                managed_capture_selection(route(), start)
        changed = route()
        changed["checkpoints"] = []
        with self.assertRaises(ValueError):
            managed_capture_selection(changed, 3)

    def test_rejects_unrestored_unjournaled_or_stale_expected_patch(self):
        for mutation in (lambda r: r["assistance"].update(jump_patch_active=True),
                         lambda r: r["assistance"]["code_patches"].pop(),
                         lambda r: r["assistance"]["code_patches"][1].update(expected="8181"),
                         lambda r: r.pop("assistance")):
            changed = route()
            mutation(changed)
            with self.assertRaises((ValueError, KeyError)):
                managed_capture_selection(changed, 3)

    def test_capacity_and_continuous_video_are_explicit(self):
        for limit in (0, 65537, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                managed_capture_selection(route(), 3, limit)
        changed = route()
        changed["initial_command"][-1] = "snapshot"
        with self.assertRaises(ValueError):
            managed_capture_selection(changed, 3)

    def test_capture_source_collisions_include_equals_form(self):
        for flag in ("--code-capture", "--capture-limit", "--code-capture-start-frame"):
            for tail in ([flag, "3"], [flag + "=3"]):
                changed = route()
                changed["initial_command"] += tail
                with self.subTest(tail=tail), self.assertRaises(ValueError):
                    validate_route(changed)
                with self.assertRaises(ValueError):
                    managed_capture_command(changed["initial_command"], "new.json", completion()[0])

    def test_fixed_new_output_and_managed_start_flag(self):
        selected = managed_capture_selection(route(), 3, 512)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "observed-code.json"
            command = managed_capture_command(route()["initial_command"], output, selected)
            self.assertEqual(command[-6:], ["--code-capture", str(output), "--capture-limit", "512",
                                           "--code-capture-start-frame", "3"])
            output.write_text("immutable")
            with self.assertRaises(ValueError):
                managed_capture_command(route()["initial_command"], output, selected)

    def test_fresh_readback_preserves_cross_mpr_source_and_retirement(self):
        client = Client()
        proof = capture_start_proof(client, managed_capture_selection(route(), 3))
        self.assertEqual(client.calls, ["status", "status"])
        self.assertEqual(client.reads, [(4096, 2)])
        self.assertEqual(proof["retired_instructions"], 30)
        self.assertEqual(proof["status"]["host"]["cpu"]["instruction_physical"][1], 24576)
        self.assertEqual(proof["canonical_readback"], [{"address": 4096, "expected": "eaea", "observed": "eaea"}])

    def test_readback_wrong_pause_and_source_identity_fail(self):
        for mutation in (lambda c: setattr(c, "data", b"\x80\x80"),
                         lambda c: c.before.update(paused=False),
                         lambda c: c.before.update(frame=2),
                         lambda c: c.before["host"]["cpu"]["mpr"].pop(),
                         lambda c: c.before["host"]["cpu"]["instruction_bytes"].__setitem__(0, None),
                         lambda c: c.before["host"]["cpu"]["instruction_physical"].__setitem__(0, 5)):
            client = Client()
            mutation(client)
            with self.assertRaises(ValueError):
                capture_start_proof(client, managed_capture_selection(route(), 3))

    def test_no_guest_execution_during_restoration_proof(self):
        for mutation in (lambda c: c.after.update(ticks=91),
                         lambda c: c.after["host"].update(native_steps=11),
                         lambda c: c.after["host"]["cpu"]["instruction_generations"].__setitem__(0, 3)):
            client = Client()
            mutation(client)
            with self.assertRaises(ValueError):
                capture_start_proof(client, managed_capture_selection(route(), 3))

    def test_window_and_retirement_delta_are_exact(self):
        selected, proof, capture, runner = completion()
        self.assertEqual(validate_capture_summary(capture, selected, proof, runner), 9)
        for key, value in (("retired_instructions", 8), ("complete", False), ("runtime_abi", 12),
                           ("capacity", 65535), ("dropped_instructions", 1), ("unreadable_instructions", 1)):
            changed = dict(capture, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_capture_summary(changed, selected, proof, runner)
        for key, value in (("actual_start_frame", 4), ("actual_start_ticks", 91), ("native_steps_before", 11),
                           ("started", 1), ("unknown", 0)):
            changed = copy.deepcopy(runner)
            changed["code_capture_window"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_capture_summary(capture, selected, proof, changed)

    def test_shared_loader_is_isolated_and_original_capture_hash_retained(self):
        selected, proof, capture, runner = completion()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "observed-code.json"
            output.write_text("authored capture fixture")
            digest = sha256(output)
            summary = {"capture": capture, "observations": 2, "sha256": digest}
            response = subprocess.CompletedProcess([], 0, json.dumps(summary), "")
            with patch("scripts.replay_route.subprocess.run", return_value=response) as run:
                result = finish_managed_capture(output, root, selected, proof, runner)
            self.assertEqual(result["sha256"], digest)
            self.assertEqual(result["window"], runner["code_capture_window"])
            self.assertEqual(run.call_args.kwargs["env"]["PYTHONPATH"], str(root))
            self.assertEqual(run.call_args.kwargs["env"]["PYTHONSAFEPATH"], "1")
            self.assertIn("pcerecomp.capture import load_capture", run.call_args.args[0][2])

    def test_shared_loader_rejection_and_capture_mutation_cannot_pass(self):
        selected, proof, capture, runner = completion()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "observed-code.json"
            output.write_text("authored")
            with patch("scripts.replay_route.subprocess.run", side_effect=subprocess.CalledProcessError(1, ["shared-loader"])):
                with self.assertRaises(subprocess.CalledProcessError):
                    finish_managed_capture(output, Path(temp), selected, proof, runner)
            digest = sha256(output)
            def mutate(*args, **kwargs):
                output.write_text("changed")
                return subprocess.CompletedProcess([], 0, json.dumps({"capture": capture, "observations": 2, "sha256": digest}), "")
            with patch("scripts.replay_route.subprocess.run", side_effect=mutate):
                with self.assertRaises(ValueError):
                    finish_managed_capture(output, Path(temp), selected, proof, runner)


class ActualSharedLoaderTests(unittest.TestCase):
    """Authored instructions only; no game image, process or build is involved."""
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((ROOT / "toolchain.json").read_text(encoding="utf-8"))
        cls.tool = (Path(os.environ["YS3_CAPTURE_TEST_TOOL"])
                    if "YS3_CAPTURE_TEST_TOOL" in os.environ
                    else ROOT / manifest["tool"]["checkout"])
        cls.tool = cls.tool.resolve()
        if not (cls.tool / "pcerecomp/capture.py").is_file():
            raise unittest.SkipTest("The pinned upstream checkout is required for shared capture-loader tests")
        # The normal verifier checks the manifest's exact revision, ABI and full
        # source digest. Existing but dirty/wrong dependencies must fail loudly.
        verify_tool_root(cls.tool)

    def fixture(self):
        selected, proof, capture, runner = completion()
        capture["observations"] = [{"pc": 0, "mpr": [0] * 8, "physical": [0], "data": [234],
                                    "native_hits": 9, "interpreted_hits": 0}]
        return selected, proof, capture, runner

    def test_actual_shared_loader_checks_synthetic_capture(self):
        selected, proof, capture, runner = self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "observed-code.json"
            output.write_text(json.dumps(capture))
            result = finish_managed_capture(output, self.tool,
                                           selected, proof, runner)
            self.assertEqual(result["observations"], 1)
            self.assertEqual(result["capture"]["retired_instructions"], 9)

    def test_actual_shared_loader_rejects_malformed_mapping_and_hit_total(self):
        selected, proof, capture, runner = self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "observed-code.json"
            for mutation in (lambda c: c["observations"][0].update(physical=[1]),
                             lambda c: c["observations"][0].update(native_hits=8),
                             lambda c: c["observations"].append(copy.deepcopy(c["observations"][0]))):
                changed = copy.deepcopy(capture)
                mutation(changed)
                output.write_text(json.dumps(changed))
                with self.assertRaises(subprocess.CalledProcessError):
                    finish_managed_capture(output, self.tool,
                                           selected, proof, runner)


if __name__ == "__main__":
    unittest.main()
