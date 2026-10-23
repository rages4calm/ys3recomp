"""Synthetic before/after evidence; no game or BIOS content."""
import copy
import unittest

from scripts.qualify_coverage import qualify


def fixtures():
    before_run = {"native_steps": 10, "interpreter_steps": 90, "native_block_steps": 2,
                  "interpreter_block_steps": 3, "guard_misses": 7, "ticks": 1000,
                  "development": {"port": 1000}, "device": {"writes": 6},
                  "source": {"generations": [3, 4]}, "stop": "dev_quit"}
    after_run = copy.deepcopy(before_run)
    after_run.update(native_steps=80, interpreter_steps=20, native_block_steps=4,
                     interpreter_block_steps=1, guard_misses=12)
    after_run["development"]["port"] = 2000
    status = {"id": 1, "frame": 60, "ticks": 1000, "paused": True, "local_paused": False,
              "host": {"native_steps": 10, "interpreter_steps": 90,
                       "cpu": {"instruction_generations": [3, 4]}, "buttons": [0] * 5}}
    before = {"passed": True, "exit_code": 0, "source_route_sha256": "route-hash",
              "source_binary_sha256": "historical-hash", "initial_bram_sha256": "seed-hash",
              "images": [{"frame": 60, "png_sha256": "authored-image-hash"}],
              "memory_edits_replayed": 2, "final_status": status,
              "released_status": copy.deepcopy(status), "input_sha256": {"seed": "seed-hash"}}
    after = copy.deepcopy(before)
    for name in ("final_status", "released_status"):
        after[name]["host"].update(native_steps=80, interpreter_steps=20)
    return before, after, copy.deepcopy(before_run), before_run, after_run


def incremental_fixtures():
    before, after, reference, before_run, after_run = fixtures()
    before_run.update(native_steps=80, interpreter_steps=20, native_block_steps=4,
                      interpreter_block_steps=1, guard_misses=12)
    after_run.update(native_steps=95, interpreter_steps=5, native_block_steps=5,
                     interpreter_block_steps=0, guard_misses=15)
    for name in ("final_status", "released_status"):
        before[name]["host"].update(native_steps=80, interpreter_steps=20)
        after[name]["host"].update(native_steps=95, interpreter_steps=5)
    return before, after, reference, before_run, after_run


class CoverageQualificationTests(unittest.TestCase):
    def test_native_redistribution_with_conserved_totals_passes(self):
        result = qualify(*fixtures())
        self.assertTrue(result["passed"])
        self.assertEqual(result["native_steps_gained"], 70)
        self.assertEqual(result["candidate_native_fraction"], 0.8)
        self.assertTrue(result["baseline_matches_original_runner"])
        self.assertTrue(result["baseline_matches_original_runner_exact_tiers"])
        self.assertEqual(result["normalization"]["baseline_runner_tier_fields"], [])

    def test_shared_wrapper_preserves_full_runner_comparison(self):
        values = list(fixtures())
        values[1]["binary_sha256"] = "authored-candidate"
        values[4] = {"kind": "pce-consumer-execution", "qualified": True,
                     "binary_sha256": "authored-candidate", "result": values[4]}
        self.assertTrue(qualify(*values)["passed"])
        values[4]["result"]["device"]["writes"] += 1
        with self.assertRaisesRegex(ValueError, "candidate_runner.device.writes"):
            qualify(*values)

    def test_original_baseline_requires_exact_all_other_fields(self):
        values = fixtures()
        values[3]["device"]["writes"] = 7
        with self.assertRaisesRegex(ValueError, r"baseline_runner.device.writes"):
            qualify(*values)

    def test_total_instruction_and_block_changes_are_rejected(self):
        for key in ("interpreter_steps", "interpreter_block_steps"):
            values = fixtures()
            values[4][key] += 1
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "total_"):
                qualify(*values)

    def test_device_and_source_generations_are_exact(self):
        for group, key, value in (("device", "writes", 7), ("source", "generations", [3, 5])):
            values = fixtures()
            values[4][group][key] = value
            with self.subTest(group=group), self.assertRaisesRegex(ValueError, "candidate_runner"):
                qualify(*values)

    def test_image_mismatch_and_removed_checkpoint_are_rejected(self):
        for remove in (False, True):
            values = fixtures()
            if remove:
                values[1]["images"].clear()
            else:
                values[1]["images"][0]["png_sha256"] = "different"
            with self.assertRaisesRegex(ValueError, "replay.images"):
                qualify(*values)

    def test_insufficient_gain_and_fraction_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "native gain"):
            qualify(*fixtures(), min_native_gain=71)
        with self.assertRaisesRegex(ValueError, "native fraction"):
            qualify(*fixtures(), min_native_fraction=0.9)

    def test_status_source_generation_and_counter_sum_cannot_change(self):
        values = fixtures()
        values[1]["final_status"]["host"]["cpu"]["instruction_generations"] = [3, 5]
        with self.assertRaises(RuntimeError):
            qualify(*values)
        values = fixtures()
        values[1]["final_status"]["host"]["interpreter_steps"] += 1
        with self.assertRaisesRegex(ValueError, "retired count"):
            qualify(*values)

    def test_added_capture_diagnostic_is_recorded_but_existing_changes_fail(self):
        values = fixtures()
        values[4]["code_capture"] = {"enabled": False, "instructions": 0}
        result = qualify(*values)
        self.assertEqual(result["normalization"]["candidate_added_code_capture"],
                         {"candidate_runner.code_capture": {"enabled": False, "instructions": 0}})
        values[3]["code_capture"] = {"enabled": True}
        values[2]["code_capture"] = {"enabled": True}
        with self.assertRaisesRegex(ValueError, "code_capture"):
            qualify(*values)

    def test_failed_replay_edits_and_changed_protected_inputs_fail(self):
        for key, replacement in (("passed", False), ("memory_edits_replayed", 3),
                                 ("input_sha256", {"seed": "changed"})):
            values = fixtures()
            values[1][key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError):
                qualify(*values)

    def test_thresholds_are_finite_and_meaningful(self):
        for fraction in (float("nan"), float("inf"), -1, 1.1):
            with self.assertRaises(ValueError):
                qualify(*fixtures(), min_native_fraction=fraction)
        with self.assertRaises(ValueError):
            qualify(*fixtures(), min_native_gain=0)

    def test_incremental_baseline_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(ValueError, "baseline_runner"):
            qualify(*incremental_fixtures())
        result = qualify(*incremental_fixtures(), allow_baseline_tier_change=True)
        self.assertEqual(result["baseline_native_fraction"], 0.8)
        self.assertEqual(result["candidate_native_fraction"], 0.95)
        self.assertEqual(result["native_steps_gained"], 15)
        self.assertFalse(result["baseline_matches_original_runner"])
        self.assertTrue(result["baseline_matches_original_runner_semantics"])
        self.assertFalse(result["baseline_matches_original_runner_exact_tiers"])
        self.assertEqual(result["normalization"]["baseline_runner_tier_fields"],
                         ["native_steps", "interpreter_steps", "guard_misses",
                          "native_block_steps", "interpreter_block_steps"])

    def test_incremental_reference_instruction_and_block_totals_are_conserved(self):
        for key in ("interpreter_steps", "interpreter_block_steps"):
            values = incremental_fixtures()
            values[2][key] += 1
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "baseline_runner.total_"):
                qualify(*values, allow_baseline_tier_change=True)

    def test_incremental_reference_device_and_source_generations_remain_exact(self):
        for group, key, changed in (("device", "writes", 7), ("source", "generations", [3, 5])):
            values = incremental_fixtures()
            values[2][group][key] = changed
            with self.subTest(group=group), self.assertRaisesRegex(ValueError, "baseline_runner." + group):
                qualify(*values, allow_baseline_tier_change=True)

    def test_incremental_mode_still_checks_images_and_baseline_status_totals(self):
        values = incremental_fixtures()
        values[1]["images"][0]["png_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "replay.images"):
            qualify(*values, allow_baseline_tier_change=True)
        values = incremental_fixtures()
        values[0]["final_status"]["host"]["native_steps"] += 1
        with self.assertRaisesRegex(ValueError, "baseline.final_status: retired count"):
            qualify(*values, allow_baseline_tier_change=True)

    def test_incremental_tier_counts_cannot_be_invalid_types(self):
        values = incremental_fixtures()
        values[3]["guard_misses"] = True
        with self.assertRaisesRegex(ValueError, "baseline_runner.guard_misses"):
            qualify(*values, allow_baseline_tier_change=True)


if __name__ == "__main__":
    unittest.main()
