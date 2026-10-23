"""Qualify an ABI 13 PCM route upgrade with unchanged guest/native work."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

if __package__:
    from .audio_contract import PCM_FIELDS, extract_audio
    from .qualify_coverage import assert_exact, qualify, read_json
    from .replay_route import compare_status, sha256, unwrap_execution
else:
    from audio_contract import PCM_FIELDS, extract_audio
    from qualify_coverage import assert_exact, qualify, read_json
    from replay_route import compare_status, sha256, unwrap_execution


def qualify_audio(baseline, candidate, reference_run, baseline_run, candidate_run,
                  audio_reference_run, mode):
    """Only separately validated audio_output may extend historical diagnostics."""
    receipt = copy.deepcopy(candidate)
    run = copy.deepcopy(unwrap_execution(candidate_run, candidate.get("binary_sha256")))
    contract = receipt.get("audio_contract", {})
    if contract.get("runtime_abi") != 13 or contract.get("headless_pcm_only") is not True or contract.get("mode") != mode:
        raise ValueError("candidate requires the explicit ABI 13 headless audio contract")
    limit = contract.get("wav_frame_limit")
    audio = extract_audio(run, mode, limit)
    assert_exact(audio, contract["validated_output"], "audio_contract.validated_output")
    if mode == "off" or "audio_output_absent" in contract:
        assert_exact(mode == "off", contract["audio_output_absent"], "audio_contract.audio_output_absent")
    if mode == "on":
        # Shared upstream SDL evidence supplies deterministic PCM expectations.
        # Playback/WAV host fields are explicitly outside this headless comparison.
        source = audio_reference_run["audio_output"]
        expected = {key: source[key] for key in PCM_FIELDS - {"wav_frames", "wav_truncated"}}
        measured = {key: audio[key] for key in expected}
        assert_exact(expected, measured, "audio_reference_pcm")
        for key in ("frames", "psg_nonzero", "adpcm_nonzero", "cdda_nonzero", "mixed_nonzero", "peak"):
            if audio[key] == 0:
                raise ValueError("audio route lacks nonzero " + key)
    for field in ("before_final_release", "final_status", "released_status"):
        value = extract_audio(receipt[field]["host"], mode, limit)
        assert_exact(audio, value, field + ".audio_output")
    compare_status(baseline["before_final_release"], receipt["before_final_release"])
    left_checks = baseline.get("checkpoint_status", [])
    right_checks = receipt.get("checkpoint_status", [])
    if len(left_checks) != len(right_checks):
        raise ValueError("checkpoint status count differs")
    for index, (left, right) in enumerate(zip(left_checks, right_checks)):
        extract_audio(right["host"], mode, limit)
        compare_status(left, right)
    result = qualify(baseline, receipt, reference_run, baseline_run, run,
                     min_native_fraction=0.999999, min_native_gain=0,
                     allow_baseline_tier_change=True, require_unchanged_tiers=True)
    # Exact whole-run retired/guard/block counts are required above; state this
    # explicitly because coverage expansion normally permits tier redistribution.
    result.update(audio_qualified=True, audio_mode=mode, audio_output=audio,
                  audio_output_absent=mode == "off",
                  audio_output_presence_evidence=("Explicit absent flag and absence validated in runner/statuses."
                      if mode == "off" else "Presence derived from strictly validated PCM object in runner/statuses; receipt not rewritten."),
                  unchanged_tier_counts=True, checkpoint_status_checks=len(left_checks),
                  audio_contract=candidate["audio_contract"],
                  scope="Same-route headless PCM reproducibility, not physical playback or independent mixed-audio parity.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline-receipt", "candidate-receipt", "reference-run", "audio-reference-run", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--audio-output", required=True, choices=("off", "on"))
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("qualification output must be new")
    paths = [args.baseline_receipt, args.candidate_receipt, args.reference_run,
             args.baseline_receipt.parent / "run.stdout", args.candidate_receipt.parent / "run.stdout",
             args.audio_reference_run]
    result = {"passed": False}
    failure = None
    try:
        result = qualify_audio(*(read_json(path) for path in paths), args.audio_output)
        result["evidence_sha256"] = {str(path.resolve()): sha256(path) for path in paths}
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        result.update(passed=False, error=repr(error))
        failure = error
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as output:
        output.write(json.dumps(result, indent=2) + "\n")
    if failure is not None:
        raise failure
    print(f"PASS: ABI 13 audio {args.audio_output}; unchanged native tiers; {args.out}")


if __name__ == "__main__":
    main()
