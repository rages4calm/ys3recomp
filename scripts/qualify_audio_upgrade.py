"""Qualify declared PCM accuracy changes against a pinned, reviewed new route.

The expectation is private evidence, not a blanket permission to ignore audio.
Known ABI 13 diagnostics are required; new ABIs/schemas need deliberate review.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import re

if __package__:
    from .audio_contract import validate_audio
    from .desktop_contract import PCM_PENDING_CAPACITY, desktop_audio, validate_desktop, validate_package_proof
    from .qualify_coverage import assert_exact, read_json
    from .qualify_desktop import verify_wav
    from .replay_route import project_status, sha256, unwrap_execution
else:
    from audio_contract import validate_audio
    from desktop_contract import PCM_PENDING_CAPACITY, desktop_audio, validate_desktop, validate_package_proof
    from qualify_coverage import assert_exact, read_json
    from qualify_desktop import verify_wav
    from replay_route import project_status, sha256, unwrap_execution

ALLOWED_PCM_FIELDS = {"psg_nonzero", "mixed_nonzero", "peak", "pcm_hash"}
ROUTE_FIELDS = {"source_route_sha256", "source_binary_sha256", "initial_bram_sha256"}
FILE_ROLES = {"run", "receipt", "wav", "upstream_qualification", "independent_gear"}
QUALIFICATION_ROLES = {"result", "tool_revision", "source_sha256", "runtime_abi", "route_sha256",
                       "run_sha256", "receipt_sha256", "wav_sha256", "independent_gear_sha256"}
GEAR_ROLES = {"result", "source_sha256", "runtime_abi"}


def exact_keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(label + ": missing or unknown schema field")


def pointer(value, path):
    """Read only explicit RFC 6901 object/list locations in pinned JSON."""
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("evidence binding requires an explicit JSON pointer")
    for token in path[1:].split("/"):
        if re.search(r"~(?![01])", token):
            raise ValueError("invalid JSON pointer escape")
        key = token.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) and key.isdigit() else value[key]
    return value


def validate_expectation(value):
    required = {"schema", "kind", "tool", "route", "files", "reviewed_binding",
                "qualification_pointers", "qualification_success", "gear_pointers", "gear_success"}
    exact_keys(value, required | ({"allowed_pcm_changes"} if "allowed_pcm_changes" in value else set()), "audio expectation")
    if type(value["schema"]) is not int or value["schema"] != 1 or value["kind"] != "ys3-reviewed-audio-upgrade":
        raise ValueError("unsupported audio expectation schema/kind")
    tool = value["tool"]
    exact_keys(tool, {"revision", "source_sha256", "runtime_abi"}, "tool")
    if (not isinstance(tool["revision"], str) or not re.fullmatch(r"[0-9a-f]{40}", tool["revision"])
            or type(tool["runtime_abi"]) is not int or tool["runtime_abi"] != 13):
        raise ValueError("only the reviewed ABI 13 diagnostic contract is supported")
    exact_keys(value["route"], ROUTE_FIELDS, "route")
    for field in (tool["source_sha256"], *value["route"].values()):
        if not isinstance(field, str) or not re.fullmatch(r"[0-9a-f]{64}", field):
            raise ValueError("tool/route SHA256 must be exact lowercase hexadecimal")
    changes = value.get("allowed_pcm_changes", [])
    if not isinstance(changes, list) or any(type(key) is not str for key in changes) or len(changes) != len(set(changes)) or not set(changes) <= ALLOWED_PCM_FIELDS:
        raise ValueError("only explicitly declared known PCM synthesis scalars may change")
    roles = set(value["files"]) if isinstance(value["files"], dict) else set()
    if not FILE_ROLES <= roles or not roles <= FILE_ROLES | {"raw_upstream_qualification"}:
        raise ValueError("reference files: missing or unknown evidence role")
    for binding in value["files"].values():
        exact_keys(binding, {"path", "sha256"}, "reference artifact")
        if not isinstance(binding["path"], str) or not binding["path"] or not re.fullmatch(r"[0-9a-f]{64}", binding["sha256"]):
            raise ValueError("reference artifact requires a path and exact SHA256")
    reviewed = value["reviewed_binding"]
    exact_keys(reviewed, {"qualified", "tool", "route", "execution", "evidence_sha256", "independent_scope"}, "reviewed binding")
    if reviewed["qualified"] is not True or not isinstance(reviewed["independent_scope"], str) or not reviewed["independent_scope"].strip():
        raise ValueError("reviewed upstream/independent qualification and scope required")
    assert_exact(tool, reviewed["tool"], "reviewed.tool")
    assert_exact(value["route"], reviewed["route"], "reviewed.route")
    assert_exact({"tier": "hybrid", "audio": "on", "candidate_desktop_packaged": True,
                  "reference_host": "headless"}, reviewed["execution"], "reviewed.execution")
    assert_exact({key: binding["sha256"] for key, binding in value["files"].items()}, reviewed["evidence_sha256"], "reviewed.evidence_sha256")
    exact_keys(value["qualification_pointers"], QUALIFICATION_ROLES, "qualification pointers")
    exact_keys(value["gear_pointers"], GEAR_ROLES, "Gear pointers")
    for key in ("qualification_success", "gear_success"):
        if value[key] is not True and value[key] not in ("passed", "qualified"):
            raise ValueError("qualification success must be explicit true, passed or qualified")
    return set(changes)


def load_expectation(path):
    value = read_json(path)
    validate_expectation(value)
    files, hashes = {}, {str(path.resolve()): sha256(path)}
    for role, binding in value["files"].items():
        target = Path(binding["path"])
        target = (target if target.is_absolute() else path.parent / target).resolve(strict=True)
        if not target.is_file() or sha256(target) != binding["sha256"]:
            raise ValueError("new reference artifact hash mismatch: " + role)
        hashes[str(target)] = binding["sha256"]
        files[role] = target if role == "wav" else read_json(target)
    expected = {"result": value["qualification_success"], "tool_revision": value["tool"]["revision"],
                "source_sha256": value["tool"]["source_sha256"], "runtime_abi": value["tool"]["runtime_abi"],
                "route_sha256": value["route"]["source_route_sha256"]}
    expected.update({role + "_sha256": value["files"][role]["sha256"] for role in ("run", "receipt", "wav", "independent_gear")})
    for role, location in value["qualification_pointers"].items():
        assert_exact(expected[role], pointer(files["upstream_qualification"], location), "upstream_qualification." + role)
    gear_expected = {"result": value["gear_success"], "source_sha256": value["tool"]["source_sha256"], "runtime_abi": value["tool"]["runtime_abi"]}
    for role, location in value["gear_pointers"].items():
        assert_exact(gear_expected[role], pointer(files["independent_gear"], location), "independent_gear." + role)
    return value, files, hashes


def check_tool(receipt, tool, label):
    identity = receipt["tool_identity"]
    assert_exact(tool["revision"], identity["revision"], label + ".tool.revision")
    assert_exact(tool["runtime_abi"], identity["runtime_abi"], label + ".tool.runtime_abi")
    assert_exact(tool["revision"], identity["shared_source_identity"]["revision"], label + ".tool.shared_revision")
    assert_exact(tool["source_sha256"], identity["shared_source_identity"]["source_sha256"], label + ".tool.source_sha256")
    assert_exact(identity, receipt["tool_identity_after"], label + ".tool_identity_after")
    if label == "candidate":
        verified_tool = receipt["project_verification_before"]["tool"]
        for key in ("revision", "source_sha256"):
            assert_exact(tool[key], verified_tool[key], label + ".verified_tool." + key)


def check_receipt(receipt, label):
    if receipt.get("passed") is not True or type(receipt.get("exit_code")) is not int or receipt["exit_code"] != 0:
        raise ValueError(label + ": passed clean-exit route evidence required")
    desktop = receipt["desktop_contract"]
    for key in ("packaged", "hidden", "unthrottled", "working_directory_initially_empty", "working_directory_finally_empty"):
        if desktop.get(key) is not True:
            raise ValueError(label + ": packaged desktop proof required: " + key)
    assert_exact(desktop["package_before"], desktop["package_after"], label + ".package_after")
    validate_package_proof(desktop, receipt["binary_sha256"])
    assert_exact(desktop["package_before"]["binary"], receipt["command"][0], label + ".packaged_command_binary")
    if receipt.get("shared_project_run_used") is not False or receipt.get("project_execution_mode") != "shared-verify-then-consumer-route":
        raise ValueError(label + ": consumer/shared verification supervision required")
    assert_exact(receipt["project_verification_before"], receipt["project_verification_after"], label + ".project_verification_after")
    if receipt["project_verification_before"].get("verified") is not True:
        raise ValueError(label + ": official project verification required")
    assert_exact(receipt["project_output_files_before"], receipt["project_output_files_after"], label + ".project_output_files_after")
    assert_exact(desktop["package_before"]["output_files"], receipt["project_output_files_before"], label + ".packaged_output_files")
    audio = receipt["audio_contract"]
    if audio.get("runtime_abi") != 13 or audio.get("mode") != "on" or audio.get("headless_pcm_only") is not False:
        raise ValueError(label + ": known ABI 13 desktop audio contract required")


def check_execution_command(receipt, packaged, label):
    command = receipt["command"]
    if (not isinstance(command, list) or len(command) < 8 or not all(isinstance(value, str) for value in command)
            or command[7] != "hybrid"):
        raise ValueError(label + ": explicit hybrid execution command required")
    options = {"--audio-output": "on"}
    if packaged:
        options.update({"--hidden": "on", "--unthrottled": "on"})
    elif any(flag in command for flag in ("--hidden", "--unthrottled")):
        raise ValueError(label + ": headless reference cannot contain desktop overrides")
    for flag, expected in options.items():
        if command.count(flag) != 1 or command.index(flag) + 1 >= len(command) or command[command.index(flag) + 1] != expected:
            raise ValueError(label + ": execution option mismatch: " + flag)


def reference_audio(value, wav_limit, checkpoint=False):
    """Headless snapshots expose generation and WAV counters, without SDL stats."""
    if not checkpoint:
        return validate_audio(value, "on", wav_limit)
    # Before saturation, WAV frames identify the exact source drain count.
    # At saturation, truncation identifies whether that count exceeded quota;
    # its exact value is absent in headless diagnostics and is not invented.
    frames, written, truncated = value["frames"], value["wav_frames"], value["wav_truncated"]
    if type(frames) is not int or type(written) is not int or type(truncated) is not bool:
        raise ValueError("headless checkpoint PCM/WAV counter types invalid")
    if written < wav_limit or not truncated:
        if not 0 <= frames - written <= PCM_PENDING_CAPACITY:
            raise ValueError("headless checkpoint pending PCM exceeds source queue capacity")
        return validate_audio(value, "on", wav_limit, drained_frames=written)
    # Saturated/truncated metadata has the same truth value for every possible
    # drain count in quota+1..generated. Validate that interval via its upper
    # bound; retain the actual original counters unchanged.
    return validate_audio(value, "on", wav_limit, drained_frames=frames)


def pcm_compare(old, new, reference, allowed, label, checkpoint=False):
    if checkpoint:
        old, new, reference = [dict(value) for value in (old, new, reference)]
        for value in (old, new, reference):
            value.pop("wav_frames")
            value.pop("wav_truncated")
    assert_exact(reference, new, label + ".new_reference")
    for key in set(old) | set(new):
        if key not in allowed:
            assert_exact(old.get(key), new.get(key), label + ".unchanged." + key)


def _qualify_bound_audio_upgrade(baseline, candidate, baseline_run, candidate_run, expectation, reference_run, reference):
    allowed = validate_expectation(expectation)
    for label, receipt in (("baseline", baseline), ("candidate", candidate), ("reference", reference)):
        if label != "reference":
            check_receipt(receipt, label)
        elif (receipt.get("passed") is not True or type(receipt.get("exit_code")) is not int
              or receipt["exit_code"] != 0 or receipt["audio_contract"].get("headless_pcm_only") is not True
              or receipt["audio_contract"].get("runtime_abi") != 13 or receipt["audio_contract"].get("mode") != "on"):
            raise ValueError("reference: passed clean-exit ABI 13 headless audio route required")
        check_execution_command(receipt, packaged=label != "reference", label=label)
        for key in ROUTE_FIELDS:
            assert_exact(expectation["route"][key], receipt[key], label + "." + key)
    check_tool(candidate, expectation["tool"], "candidate")
    if "tool_identity" in reference or "tool_identity_after" in reference:
        check_tool(reference, expectation["tool"], "reference")
    for receipt in (candidate, reference):
        assert_exact(baseline["images"], receipt["images"], "route.images")
        assert_exact(baseline["memory_edits_replayed"], receipt["memory_edits_replayed"], "route.memory_edits_replayed")
        assert_exact(baseline["source_command"], receipt["source_command"], "route.source_command")
    def protected(receipt):
        values = receipt["input_sha256"].copy()
        values.pop(receipt["command"][0], None)
        return values
    assert_exact(protected(baseline), protected(candidate), "protected_inputs")
    assert_exact(protected(baseline), protected(reference), "reference_protected_inputs")
    limit = baseline["audio_contract"]["wav_frame_limit"]
    if limit is None:
        raise ValueError("retained bounded WAV required")
    for receipt in (candidate, reference):
        assert_exact(limit, receipt["audio_contract"]["wav_frame_limit"], "wav_frame_limit")
    audios, runs = [], []
    for label, receipt, run in (("baseline", baseline, baseline_run), ("candidate", candidate, candidate_run), ("reference", reference, reference_run)):
        run = copy.deepcopy(unwrap_execution(run, receipt["binary_sha256"]))
        raw_audio = run.pop("audio_output")
        audio = reference_audio(raw_audio, limit) if label == "reference" else desktop_audio(raw_audio, limit)
        assert_exact(audio, receipt["audio_contract"]["validated_output"], label + ".validated_output")
        if label != "reference":
            assert_exact(raw_audio, receipt["desktop_contract"]["audio_output"], label + ".desktop_audio_output")
            presentation = validate_desktop(run.pop("desktop"), receipt["final_status"]["frame"])
            assert_exact(presentation, receipt["desktop_contract"]["presentation"], label + ".presentation")
        run["development"].pop("port", None)
        audios.append(audio)
        runs.append(run)
    assert_exact(runs[0], runs[1], "candidate_guest_runner")
    assert_exact(runs[0], runs[2], "reference_guest_runner")
    pcm_compare(*audios, allowed, "final_pcm")
    checkpoints = []
    for field in ("before_final_release", "final_status", "released_status", "checkpoint_status"):
        groups = [receipt[field] if field == "checkpoint_status" else [receipt[field]] for receipt in (baseline, candidate, reference)]
        assert_exact(len(groups[0]), len(groups[1]), field + ".candidate_count")
        assert_exact(len(groups[0]), len(groups[2]), field + ".reference_count")
        if field == "checkpoint_status" and len(groups[0]) != len(baseline["images"]):
            raise ValueError("checkpoint/image counts disagree")
        for index, states in enumerate(zip(*groups)):
            guests, outputs = [], []
            for position, state in enumerate(states):
                known_status = {"frame", "ticks", "paused", "local_paused", "host", "id", "ok"}
                if not set(state) <= known_status or set(state) != set(states[0]):
                    raise ValueError(field + ": missing or unknown status schema field")
                guest = project_status(state)
                raw_audio = guest["host"].pop("audio_output")
                outputs.append(reference_audio(raw_audio, limit, checkpoint=field == "checkpoint_status")
                               if position == 2 else desktop_audio(raw_audio, limit, allow_pending=field == "checkpoint_status"))
                guests.append(guest)
            assert_exact(guests[0], guests[1], field + ".candidate_guest")
            assert_exact(guests[0], guests[2], field + ".reference_guest")
            pcm_compare(*outputs, allowed, field + ".pcm", checkpoint=field == "checkpoint_status")
            if field == "checkpoint_status":
                checkpoints.append({"frame": states[0]["frame"], "old_pcm": outputs[0], "new_pcm": outputs[1],
                                    "reference_pcm": outputs[2]})
    reference_wav = expectation["files"]["wav"]["sha256"]
    assert_exact(reference_wav, reference["audio_contract"]["wav_sha256"], "reference.wav_sha256")
    assert_exact(reference_wav, candidate["audio_contract"]["wav_sha256"], "candidate.wav_sha256")
    assert_exact(reference["audio_contract"]["wav_bytes"], candidate["audio_contract"]["wav_bytes"], "candidate.wav_bytes")
    if "pcm_hash" not in allowed:
        assert_exact(baseline["audio_contract"]["wav_sha256"], reference_wav, "undeclared_wav_change")
    return {"passed": True, "audio_upgrade_qualified": True, "allowed_pcm_changes": sorted(allowed),
            "new_tool": expectation["tool"], "source_route_sha256": candidate["source_route_sha256"],
            "old_audio": {"pcm": audios[0], "wav_sha256": baseline["audio_contract"]["wav_sha256"], "full": baseline["desktop_contract"]["audio_output"]},
            "new_audio": {"pcm": audios[1], "wav_sha256": reference_wav, "full": candidate["desktop_contract"]["audio_output"]},
            "checkpoint_audio": checkpoints, "image_checkpoints": len(candidate["images"]),
            "memory_edits_replayed": candidate["memory_edits_replayed"],
            "native_steps": runs[1]["native_steps"], "interpreter_steps": runs[1]["interpreter_steps"],
            "native_block_steps": runs[1]["native_block_steps"], "interpreter_block_steps": runs[1]["interpreter_block_steps"],
            "guard_misses": runs[1]["guard_misses"], "unchanged_guest_and_tier_counts": True,
            "reviewed_binding": expectation["reviewed_binding"],
            "scope": "Declared digital PCM changes reproduce a reviewed new upstream route; independent evidence retains its stated scope. No generic audio normalization, listening or hardware parity claim."}


def qualify_audio_upgrade(baseline, candidate, baseline_run, candidate_run, expectation_path):
    """Public API always verifies the expectation and all linked file bytes."""
    import wave
    expectation, files, hashes = load_expectation(Path(expectation_path))
    reference_audio_contract = files["receipt"]["audio_contract"]
    with wave.open(str(files["wav"]), "rb") as stream:
        geometry = (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes())
    frames = reference_audio_contract["validated_output"]["wav_frames"]
    assert_exact((2, 2, 44100, frames), geometry, "reference.wav_format")
    assert_exact(44 + 4 * frames, files["wav"].stat().st_size, "reference.wav_bytes")
    assert_exact(files["wav"].stat().st_size, reference_audio_contract["wav_bytes"], "reference.wav_receipt_bytes")
    result = _qualify_bound_audio_upgrade(baseline, candidate, baseline_run, candidate_run,
                                         expectation, files["run"], files["receipt"])
    for path, expected in hashes.items():
        if sha256(path) != expected:
            raise ValueError("new reference changed during qualification: " + path)
    result["evidence_sha256"] = hashes
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline-receipt", "candidate-receipt", "audio-expectation", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("qualification output must be new")
    result, failure = {"passed": False}, None
    try:
        paths = [args.baseline_receipt, args.candidate_receipt, args.baseline_receipt.parent / "run.stdout", args.candidate_receipt.parent / "run.stdout"]
        values = [read_json(path) for path in paths]
        wavs = [verify_wav(receipt, path) for receipt, path in zip(values[:2], paths[:2])]
        hashes = {str(path.resolve()): sha256(path) for path in paths + wavs}
        result = qualify_audio_upgrade(*values, args.audio_expectation)
        for path, expected in hashes.items():
            if sha256(path) != expected:
                raise ValueError("qualification evidence changed while checking: " + path)
        result["evidence_sha256"].update(hashes)
    except (OSError, KeyError, IndexError, TypeError, ValueError, RuntimeError) as error:
        result.update(passed=False, error=repr(error))
        failure = error
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as output:
        output.write(json.dumps(result, indent=2) + "\n")
    if failure is not None:
        raise failure
    print("PASS: pinned audio accuracy upgrade; original guest work exact; " + str(args.out))


if __name__ == "__main__":
    main()
