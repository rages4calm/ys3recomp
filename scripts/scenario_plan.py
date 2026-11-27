"""Build and validate private input scenarios without launching a game.

Every recorded control is retained. Explicit milestones select proof captures;
they do not establish gameplay, source coverage or native qualification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

MAX_STEP_FRAMES = 600
MAX_NEW_FRAMES = 20000
LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _pairs(items):
    result = {}
    for key, value in items:
        _require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def read_json(raw: bytes):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                      parse_constant=_constant)


def _step(action: dict) -> None:
    _require(set(action) == {"cmd", "mask", "frames"}, "Unexpected step fields")
    _require(type(action["mask"]) is int and 0 <= action["mask"] <= 255,
             "Controller mask must be an integer in 0..255")
    _require(type(action["frames"]) is int and 1 <= action["frames"] <= MAX_STEP_FRAMES,
             "TCP frame count must be an integer in 1..600")


def parse_manifest(raw: bytes) -> list[dict]:
    """Validate the runner's exact JSONL action contract, including sparse cuts."""
    _require(type(raw) is bytes and bool(raw) and raw.endswith(b"\n"),
             "Manifest requires complete newline-terminated records")
    lines = raw.splitlines(keepends=True)
    actions = []
    labels = set()
    steps = total = 0
    last_cut = -1
    for index, line in enumerate(lines):
        _require(len(line) <= 65536, "Oversized action record")
        action = read_json(line)
        _require(type(action) is dict and type(action.get("cmd")) is str,
                 "Action must be an object with a command")
        kind = action["cmd"]
        if kind == "step":
            _step(action)
            steps += 1
            total += action["frames"]
            _require(total <= MAX_NEW_FRAMES, "Scenario exceeds 20000 new frames")
        elif kind == "checkpoint":
            _require(set(action) == {"cmd", "label"}
                     and type(action["label"]) is str
                     and LABEL.fullmatch(action["label"]) is not None,
                     "Invalid checkpoint label")
            _require(action["label"] not in labels, "Duplicate checkpoint label")
            _require(steps - 1 > last_cut,
                     "Checkpoint control indices must strictly increase after a step")
            labels.add(action["label"])
            last_cut = steps - 1
        elif kind == "quit":
            _require(action == {"cmd": "quit"} and index == len(lines) - 1,
                     "Quit must be the final action")
            _require(steps > 0 and last_cut == steps - 1 and actions[-1]["cmd"] == "checkpoint",
                     "Final checkpoint must follow all steps immediately before quit")
        else:
            raise ValueError(f"Unsupported action: {kind}")
        actions.append(action)
    _require(actions[-1] == {"cmd": "quit"}, "Explicit final quit required")
    return actions


def build_manifest(receipt: dict, milestones: list[tuple[int, str]]) -> bytes:
    """Select proof boundaries from a closed unassisted receipt; retain all inputs."""
    _require(type(receipt) is dict, "Source receipt must be an object")
    _require(all(receipt.get(key) is True for key in ("passed", "natural_quit", "child_stopped"))
             and type(receipt.get("exit_code")) is int and receipt["exit_code"] == 0,
             "Source receipt must have passed and closed naturally")
    _require(type(receipt.get("writes", [])) is list and not receipt.get("writes", []),
             "Memory-write recipes are not supported")
    write_count = receipt.get("guest_memory_writes", 0)
    _require(type(write_count) is int and write_count == 0,
             "Memory-write recipes are not supported")
    controls = receipt.get("controls")
    _require(type(controls) is list and bool(controls), "Source receipt requires controls")
    selected = {}
    previous = -1
    for index, label in milestones:
        _require(type(index) is int and previous < index < len(controls),
                 "Milestone indices must be strictly increasing valid control indices")
        _require(type(label) is str and LABEL.fullmatch(label) is not None,
                 "Invalid checkpoint label")
        _require(label not in selected.values(), "Duplicate checkpoint label")
        selected[index] = label
        previous = index
    _require(previous == len(controls) - 1, "A milestone is required after the final control")
    actions = []
    for index, control in enumerate(controls):
        _require(type(control) is list and len(control) == 2,
                 "Each source control must contain exactly mask and frames")
        action = dict(cmd="step", mask=control[0], frames=control[1])
        _step(action)
        actions.append(action)
        if index in selected:
            actions.append(dict(cmd="checkpoint", label=selected[index]))
    actions.append(dict(cmd="quit"))
    raw = b"".join(json.dumps(action, separators=(",", ":"), ensure_ascii=True).encode("ascii")
                   + b"\n" for action in actions)
    parse_manifest(raw)
    return raw


def write_plan(receipt_path: Path, milestones: list[tuple[int, str]], output: Path) -> bytes:
    raw = build_manifest(read_json(receipt_path.read_bytes()), milestones)
    with output.open("xb") as stream:
        stream.write(raw)
    return raw


def _milestone(value: str) -> tuple[int, str]:
    try:
        index, label = value.split(":", 1)
        _require(index.isascii() and index.isdecimal(), "Use a zero-based decimal control index")
        _require(LABEL.fullmatch(label) is not None, "Invalid checkpoint label")
        return int(index), label
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"Expected INDEX:LABEL: {error}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Retain all controls and select explicit proof milestones")
    build.add_argument("receipt", type=Path)
    build.add_argument("--milestone", type=_milestone, action="append", required=True,
                       help="Zero-based control INDEX:LABEL; include the final control")
    build.add_argument("--out", type=Path, required=True, help="New private JSONL file; never overwritten")
    validate = commands.add_parser("validate", help="Validate an existing JSONL scenario without executing it")
    validate.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        raw = (write_plan(args.receipt, args.milestone, args.out) if args.command == "build"
               else args.manifest.read_bytes())
        actions = parse_manifest(raw)
    except (OSError, ValueError) as error:
        print(f"Scenario plan refused: {error}", file=sys.stderr)
        return 1
    steps = [action for action in actions if action["cmd"] == "step"]
    print(f"Validated {len(steps)} controls, {len(actions) - len(steps) - 1} milestones, "
          f"{sum(action['frames'] for action in steps)} new frames. No guest launched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
