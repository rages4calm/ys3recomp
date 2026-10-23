"""Qualify a packaged desktop route against a retained headless audio route."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

if __package__:
    from .audio_contract import validate_audio
    from .desktop_contract import (PCM_PENDING_CAPACITY, desktop_audio, headless_status,
                                   validate_desktop, validate_package_proof)
    from .qualify_coverage import assert_exact, qualify, read_json
    from .replay_route import compare_status, project_status, sha256, unwrap_execution
else:
    from audio_contract import validate_audio
    from desktop_contract import (PCM_PENDING_CAPACITY, desktop_audio, headless_status,
                                  validate_desktop, validate_package_proof)
    from qualify_coverage import assert_exact, qualify, read_json
    from replay_route import compare_status, project_status, sha256, unwrap_execution


def qualify_desktop(baseline, candidate, baseline_run, candidate_run):
    receipt = copy.deepcopy(candidate)
    run = copy.deepcopy(unwrap_execution(candidate_run, candidate.get("binary_sha256")))
    old_run = unwrap_execution(baseline_run, baseline.get("binary_sha256"))
    desktop = receipt["desktop_contract"]
    for key in ("packaged", "hidden", "unthrottled", "working_directory_initially_empty", "working_directory_finally_empty"):
        if desktop.get(key) is not True:
            raise ValueError("packaged desktop contract requires " + key)
    if receipt.get("shared_project_run_used") is not False or receipt.get("project_execution_mode") != "shared-verify-then-consumer-route":
        raise ValueError("packaged desktop requires explicit shared verify/consumer supervision")
    assert_exact(desktop["package_before"], desktop["package_after"], "package_after")
    validate_package_proof(desktop, receipt["binary_sha256"])
    for name in ("package_before", "environment", "loaded_sdl_before", "loaded_sdl_final"):
        if not isinstance(desktop.get(name), dict) or not desktop[name]:
            raise ValueError("missing package proof: " + name)
    audio_contract = receipt["audio_contract"]
    if audio_contract.get("mode") != "on" or audio_contract.get("runtime_abi") != 13 or audio_contract.get("headless_pcm_only") is not False:
        raise ValueError("desktop PCM contract mismatch")
    limit = audio_contract["wav_frame_limit"]
    if limit != baseline["audio_contract"]["wav_frame_limit"] or limit is None:
        raise ValueError("desktop WAV bound differs from retained headless route")
    original_audio = copy.deepcopy(run["audio_output"])
    core = desktop_audio(original_audio, limit)
    assert_exact(core, validate_audio(old_run["audio_output"], "on", limit), "headless_reference_pcm")
    assert_exact(core, audio_contract["validated_output"], "audio_contract.validated_output")
    assert_exact(original_audio, desktop["audio_output"], "desktop_contract.audio_output")
    run["audio_output"] = core
    presentation = validate_desktop(run.pop("desktop"), receipt["final_status"]["frame"])
    assert_exact(presentation, desktop["presentation"], "desktop_contract.presentation")
    for key in ("wav_sha256", "wav_bytes"):
        assert_exact(baseline["audio_contract"][key], audio_contract[key], "headless_reference." + key)
    for name in ("before_final_release", "final_status", "released_status"):
        receipt[name] = headless_status(receipt[name], limit)
        compare_status(baseline[name], receipt[name])
        assert_exact(project_status(baseline[name]), project_status(receipt[name]), name)
        assert_exact(core, receipt[name]["host"]["audio_output"], name + ".audio_output")
    before_checks = baseline["checkpoint_status"]
    after_checks = receipt["checkpoint_status"]
    if len(before_checks) != len(after_checks) or len(after_checks) != len(receipt["images"]):
        raise ValueError("desktop checkpoint/image status count differs")
    pending_checks = []
    for index, (before, after) in enumerate(zip(before_checks, after_checks)):
        raw_audio = after["host"]["audio_output"]
        # TCP snapshots are serialized by pump before its audio drain. With
        # zero runtime discard, this difference is the bounded source queue,
        # not SDL presentation loss. Endpoint/runner validation stays strict.
        pending_checks.append({"index": index, "frame": after["frame"],
                               "pending_frames": raw_audio["frames"] - raw_audio["host"]["submitted_frames"]})
        after_checks[index] = headless_status(after, limit, allow_pending=True)
        compare_status(before, after_checks[index])
        assert_exact(project_status(before), project_status(after_checks[index]), f"checkpoint_status[{index}]")
    result = qualify(baseline, receipt, old_run, old_run, run, min_native_fraction=0.999999,
                     min_native_gain=0, require_unchanged_tiers=True)
    result.update(packaged_desktop_qualified=True, unchanged_tier_counts=True,
                  checkpoint_status_checks=len(after_checks), audio_output=original_audio,
                  checkpoint_pending_pcm=pending_checks,
                  checkpoint_pending_pcm_limit=PCM_PENDING_CAPACITY,
                  presentation=presentation, desktop_contract=candidate["desktop_contract"],
                  audio_contract=candidate["audio_contract"],
                  wav_matches_headless=True,
                  scope="Same-route packaged SDL loading, digital PCM and muted fast-forward presentation. Paced device playback is separate; no listening or independent analog/hardware parity claim.")
    return result


def verify_wav(receipt, path):
    expected = (path.parent / "audio.wav").resolve(strict=True)
    contract = receipt["audio_contract"]
    actual = Path(contract["wav_path"]).resolve(strict=True)
    if actual != expected or sha256(actual) != contract["wav_sha256"] or actual.stat().st_size != contract["wav_bytes"]:
        raise ValueError("bounded WAV identity differs from replay receipt")
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline-receipt", "candidate-receipt", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("qualification output must be new")
    paths = [args.baseline_receipt, args.candidate_receipt,
             args.baseline_receipt.parent / "run.stdout", args.candidate_receipt.parent / "run.stdout"]
    result, failure = {"passed": False}, None
    try:
        values = [read_json(path) for path in paths]
        wavs = [verify_wav(receipt, path) for receipt, path in zip(values[:2], paths[:2])]
        result = qualify_desktop(*values)
        result["evidence_sha256"] = {str(path.resolve()): sha256(path) for path in paths + wavs}
    except (OSError, KeyError, ValueError, RuntimeError) as error:
        result.update(passed=False, error=repr(error))
        failure = error
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as output:
        output.write(json.dumps(result, indent=2) + "\n")
    if failure is not None:
        raise failure
    print("PASS: packaged desktop; exact headless route/PCM/WAV; " + str(args.out))


if __name__ == "__main__":
    main()
