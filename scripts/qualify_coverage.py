"""Qualify measured native coverage against frozen private replay evidence.

This proves reproducibility within exposed diagnostics and checkpoint images.
It does not establish independent hardware accuracy or campaign completion.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

if __package__:
    from .replay_route import MAX_ROUTE_BYTES, compare_status, project_status, sha256, unwrap_execution
else:
    from replay_route import MAX_ROUTE_BYTES, compare_status, project_status, sha256, unwrap_execution

TIER_FIELDS = ("native_steps", "interpreter_steps", "guard_misses",
               "native_block_steps", "interpreter_block_steps")


def assert_exact(expected, actual, path="root"):
    """Report the first precise field difference without flooding diagnostics."""
    if type(expected) is not type(actual):
        raise ValueError(f"{path}: type differs")
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected or key not in actual:
                raise ValueError(f"{path}.{key}: missing or unexpected field")
            assert_exact(expected[key], actual[key], f"{path}.{key}")
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            raise ValueError(f"{path}: list length differs")
        for index, (left, right) in enumerate(zip(expected, actual)):
            assert_exact(left, right, f"{path}[{index}]")
    elif expected != actual:
        raise ValueError(f"{path}: {actual!r} != expected {expected!r}")


def runner_projection(value, tier=False):
    result = copy.deepcopy(value)
    if isinstance(result.get("development"), dict):
        result["development"].pop("port", None)
    if tier:
        for field in TIER_FIELDS:
            result.pop(field, None)
    return result


def count(value, key, label):
    result = value[key]
    if type(result) is not int or result < 0:
        raise ValueError(f"{label}.{key}: requires a nonnegative integer")
    return result


def retired(value, label):
    return count(value, "native_steps", label) + count(value, "interpreter_steps", label)


def block_retired(value, label):
    return count(value, "native_block_steps", label) + count(value, "interpreter_block_steps", label)


def permit_capture_addition(baseline, candidate, path, additions):
    """Only a newly exposed capture diagnostic may be added to comparison."""
    if "code_capture" not in baseline and "code_capture" in candidate:
        additions[path + ".code_capture"] = candidate.pop("code_capture")


def qualify(baseline, candidate, reference_run, baseline_run, candidate_run,
            min_native_fraction=0.5, min_native_gain=1, allow_baseline_tier_change=False,
            require_unchanged_tiers=False):
    baseline_run = unwrap_execution(baseline_run, baseline.get("binary_sha256"))
    candidate_run = unwrap_execution(candidate_run, candidate.get("binary_sha256"))
    if not math.isfinite(min_native_fraction) or not 0 <= min_native_fraction <= 1:
        raise ValueError("minimum native fraction must be finite and in 0..1")
    if type(min_native_gain) is not int or min_native_gain < (0 if require_unchanged_tiers else 1):
        raise ValueError("minimum native gain must be a positive integer")
    if require_unchanged_tiers:
        for field in TIER_FIELDS:
            count(baseline_run, field, "baseline_runner")
            count(candidate_run, field, "candidate_runner")
            assert_exact(baseline_run[field], candidate_run[field], "unchanged_tiers." + field)
    for label, receipt in (("baseline", baseline), ("candidate", candidate)):
        if receipt.get("passed") is not True or type(receipt.get("exit_code")) is not int or receipt["exit_code"] != 0:
            raise ValueError(f"{label}: requires a passed, clean-exit replay receipt")
    if allow_baseline_tier_change:
        for label, run in (("reference_runner", reference_run), ("baseline_runner", baseline_run)):
            for field in TIER_FIELDS:
                count(run, field, label)
        if retired(reference_run, "reference_runner") != retired(baseline_run, "baseline_runner"):
            raise ValueError("baseline_runner.total_retired: differs from original reference")
        if block_retired(reference_run, "reference_runner") != block_retired(baseline_run, "baseline_runner"):
            raise ValueError("baseline_runner.total_block_retired: differs from original reference")
    assert_exact(runner_projection(reference_run, allow_baseline_tier_change),
                 runner_projection(baseline_run, allow_baseline_tier_change), "baseline_runner")
    baseline_exact_tiers = all(type(reference_run[field]) is type(baseline_run[field])
                               and reference_run[field] == baseline_run[field]
                               for field in TIER_FIELDS)
    for key in ("source_route_sha256", "source_binary_sha256", "initial_bram_sha256"):
        assert_exact(baseline[key], candidate[key], "replay." + key)
    left_images = [{"frame": image["frame"], "png_sha256": image["png_sha256"]}
                   for image in baseline["images"]]
    right_images = [{"frame": image["frame"], "png_sha256": image["png_sha256"]}
                    for image in candidate["images"]]
    if not left_images:
        raise ValueError("replay.images: requires retained image checkpoints")
    assert_exact(left_images, right_images, "replay.images")
    assert_exact(baseline["memory_edits_replayed"], candidate["memory_edits_replayed"], "replay.memory_edits_replayed")

    baseline_total = retired(baseline_run, "baseline_runner")
    candidate_total = retired(candidate_run, "candidate_runner")
    if baseline_total != candidate_total or baseline_total == 0:
        raise ValueError("runner.total_retired: changed or empty instruction total")
    baseline_blocks = block_retired(baseline_run, "baseline_runner")
    candidate_blocks = block_retired(candidate_run, "candidate_runner")
    if baseline_blocks != candidate_blocks:
        raise ValueError("runner.total_block_retired: changed instruction total")
    additions = {}
    left_run = runner_projection(baseline_run, True)
    right_run = runner_projection(candidate_run, True)
    permit_capture_addition(left_run, right_run, "candidate_runner", additions)
    assert_exact(left_run, right_run, "candidate_runner")

    for field in ("final_status", "released_status"):
        left_status = copy.deepcopy(baseline[field])
        right_status = copy.deepcopy(candidate[field])
        permit_capture_addition(left_status["host"], right_status["host"], field + ".host", additions)
        if retired(left_status["host"], "baseline." + field) != baseline_total:
            raise ValueError("baseline." + field + ": retired count disagrees with runner")
        if retired(right_status["host"], "candidate." + field) != candidate_total:
            raise ValueError("candidate." + field + ": retired count disagrees with runner")
        compare_status(left_status, right_status, ignore_tier_counters=True)
        assert_exact(project_status(left_status, True), project_status(right_status, True), field)
        assert_exact(baseline_run["ticks"], left_status["ticks"], "baseline." + field + ".ticks")
        assert_exact(candidate_run["ticks"], right_status["ticks"], "candidate." + field + ".ticks")

    # Every shared input remains pinned. The freshly linked target executable
    # legitimately differs; historical source anchors remain protected inputs.
    def protected_inputs(receipt):
        result = receipt.get("input_sha256", {}).copy()
        if receipt.get("command"):
            result.pop(receipt["command"][0], None)
        return result
    assert_exact(protected_inputs(baseline), protected_inputs(candidate), "protected_inputs")
    old_native = count(baseline_run, "native_steps", "baseline_runner")
    new_native = count(candidate_run, "native_steps", "candidate_runner")
    gain = new_native - old_native
    fraction = new_native / candidate_total
    if gain < min_native_gain:
        raise ValueError(f"native gain {gain} is below required {min_native_gain}")
    if fraction < min_native_fraction:
        raise ValueError(f"native fraction {fraction} is below required {min_native_fraction}")
    provenance_keys = ("binary_sha256", "source_binary_sha256", "source_route_sha256",
                       "initial_bram_sha256", "tool_identity", "source_binary_anchor",
                       "source_binary_override", "input_sha256", "command", "module_sha256",
                       "module_manifest_sha256", "contract_path", "contract_sha256", "contract_binding",
                       "project_descriptor_sha256", "project_build_receipt_sha256",
                       "project_execution_mode", "shared_project_run_used", "project_binding",
                       "project_verification_before", "project_verification_after",
                       "project_output_files_before", "project_output_files_after", "host_bound_override")
    return {
        "passed": True,
        "baseline_native_steps": old_native, "candidate_native_steps": new_native,
        "baseline_interpreter_steps": count(baseline_run, "interpreter_steps", "baseline_runner"),
        "candidate_interpreter_steps": count(candidate_run, "interpreter_steps", "candidate_runner"),
        "baseline_native_block_steps": count(baseline_run, "native_block_steps", "baseline_runner"),
        "candidate_native_block_steps": count(candidate_run, "native_block_steps", "candidate_runner"),
        "candidate_interpreter_block_steps": count(candidate_run, "interpreter_block_steps", "candidate_runner"),
        "native_steps_gained": gain, "total_retired": candidate_total,
        "baseline_native_fraction": old_native / baseline_total,
        "candidate_native_fraction": fraction, "total_block_retired": candidate_blocks,
        "minimum_native_fraction": min_native_fraction, "minimum_native_gain": min_native_gain,
        "matched_image_checkpoints": len(left_images),
        "memory_edits_replayed": candidate["memory_edits_replayed"],
        "baseline_matches_original_runner": baseline_exact_tiers,
        "baseline_matches_original_runner_semantics": True,
        "baseline_matches_original_runner_exact_tiers": baseline_exact_tiers,
        "normalization": {"all_runner_comparisons": ["development.port"],
                          "baseline_runner_tier_fields": list(TIER_FIELDS) if allow_baseline_tier_change else [],
                          "candidate_runner_tier_fields": list(TIER_FIELDS),
                          "replay_status_tier_fields": ["host.native_steps", "host.interpreter_steps"],
                          "candidate_added_code_capture": additions},
        "baseline_provenance": {key: baseline[key] for key in provenance_keys if key in baseline},
        "candidate_provenance": {key: candidate[key] for key in provenance_keys if key in candidate},
        "limits": ["Internal reproduction of exposed diagnostics and checkpoint images; not independent hardware accuracy.",
                   "Native ratio covers the bounded recorded route; unseen overlays and the complete campaign remain unqualified.",
                   "Recorded assists and the explicit unknown-CD-response profile retain their original limits.",
                   "Guest saves remain volatile; this does not qualify cross-process persistence."]}


def read_json(path):
    if path.stat().st_size > MAX_ROUTE_BYTES:
        raise ValueError("JSON evidence exceeds four-MiB bound")
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("baseline-receipt", "candidate-receipt", "reference-run", "out"):
        parser.add_argument("--" + argument, required=True, type=Path)
    parser.add_argument("--min-native-fraction", type=float, default=0.5)
    parser.add_argument("--min-native-gain", type=int, default=1)
    parser.add_argument("--allow-baseline-tier-change", action="store_true",
                        help="allow only conserved execution-tier redistribution between baseline and original reference")
    args = parser.parse_args()
    output = args.out.resolve()
    if output.exists():
        raise ValueError("qualification output must be a new JSON file")
    result = {"passed": False}
    failure = None
    try:
        baseline_path = args.baseline_receipt.resolve(strict=True)
        candidate_path = args.candidate_receipt.resolve(strict=True)
        reference_path = args.reference_run.resolve(strict=True)
        baseline_stdout = baseline_path.parent / "run.stdout"
        candidate_stdout = candidate_path.parent / "run.stdout"
        result = qualify(read_json(baseline_path), read_json(candidate_path), read_json(reference_path),
                         read_json(baseline_stdout), read_json(candidate_stdout),
                         args.min_native_fraction, args.min_native_gain, args.allow_baseline_tier_change)
        result["evidence_sha256"] = {str(path): sha256(path) for path in
                                     (baseline_path, candidate_path, reference_path, baseline_stdout, candidate_stdout)}
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        result.update(passed=False, error=repr(error))
        failure = error
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(result, indent=2) + "\n"
    if len(raw.encode("utf-8")) > MAX_ROUTE_BYTES:
        raise ValueError("qualification receipt exceeds four-MiB bound")
    with output.open("x", encoding="utf-8") as stream:
        stream.write(raw)
    if failure is not None:
        raise failure
    print(f"PASS: {result['candidate_native_fraction']:.8%} native; "
          f"{result['candidate_interpreter_steps']} interpreted; "
          f"gained {result['native_steps_gained']} native instructions; {output}")


if __name__ == "__main__":
    main()
