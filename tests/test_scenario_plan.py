"""Authored scenario validation only; no game inputs, SDK or guest process."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts" / "scenario_plan.py"
SPEC = importlib.util.spec_from_file_location("scenario_plan_under_test", PATH)
PLAN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLAN)


def receipt(controls=None):
    return dict(passed=True, natural_quit=True, child_stopped=True, exit_code=0,
                controls=controls if controls is not None else [[2, 8], [0, 4], [128, 600]], writes=[])


def raw(actions):
    return b"".join(json.dumps(action).encode() + b"\n" for action in actions)


def one_step(mask=0, frames=1):
    return [dict(cmd="step", mask=mask, frames=frames),
            dict(cmd="checkpoint", label="end"), dict(cmd="quit")]


class ScenarioPlanTests(unittest.TestCase):
    def test_sparse_milestones_retain_every_control(self):
        source = receipt()
        actions = PLAN.parse_manifest(PLAN.build_manifest(source, [(0, "menu"), (2, "exit")]))
        self.assertEqual([[item["mask"], item["frames"]] for item in actions if item["cmd"] == "step"],
                         source["controls"])
        self.assertEqual([item["label"] for item in actions if item["cmd"] == "checkpoint"],
                         ["menu", "exit"])
        self.assertEqual(actions[-1], {"cmd": "quit"})

    def test_exact_server_frame_limit(self):
        for frames in (1, 600):
            with self.subTest(frames=frames):
                PLAN.parse_manifest(raw(one_step(frames=frames)))
        for frames in (0, -1, 601, 900, True, 1.0):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                PLAN.parse_manifest(raw(one_step(frames=frames)))

    def test_controller_mask_types_and_range(self):
        for mask in (0, 255):
            PLAN.parse_manifest(raw(one_step(mask=mask)))
        for mask in (-1, 256, True, False, 0.0, "0"):
            with self.subTest(mask=mask), self.assertRaises(ValueError):
                PLAN.parse_manifest(raw(one_step(mask=mask)))

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            PLAN.parse_manifest(b'{"cmd":"step","mask":0,"mask":1,"frames":1}\n')

    def test_duplicate_receipt_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            PLAN.read_json(b'{"passed":true,"passed":false}')

    def test_nonfinite_json_is_rejected(self):
        for number in (b"NaN", b"Infinity", b"-Infinity"):
            with self.subTest(number=number), self.assertRaises(ValueError):
                PLAN.parse_manifest(b'{"cmd":"step","mask":0,"frames":' + number + b'}\n')

    def test_duplicate_labels_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            PLAN.build_manifest(receipt(), [(0, "room"), (2, "room")])

    def test_milestone_indices_must_increase(self):
        for milestones in ([(2, "end"), (0, "room")], [(0, "one"), (0, "two"), (2, "end")],
                           [(-1, "end")], [(3, "end")], [(True, "room"), (2, "end")]):
            with self.subTest(milestones=milestones), self.assertRaises(ValueError):
                PLAN.build_manifest(receipt(), milestones)

    def test_final_milestone_is_required(self):
        for milestones in ([], [(0, "menu")]):
            with self.subTest(milestones=milestones), self.assertRaises(ValueError):
                PLAN.build_manifest(receipt(), milestones)

    def test_invalid_labels_are_rejected(self):
        for label in ("", "../room", "room space", "a" * 49, "\u00e9", True):
            with self.subTest(label=label), self.assertRaises(ValueError):
                PLAN.build_manifest(receipt(), [(2, label)])

    def test_failed_or_unclosed_receipt_is_rejected(self):
        for key, value in (("passed", False), ("natural_quit", False), ("child_stopped", False),
                           ("exit_code", 1), ("exit_code", False), ("passed", 1)):
            source = receipt()
            source[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                PLAN.build_manifest(source, [(2, "end")])

    def test_memory_write_receipts_are_rejected(self):
        for edits in ({"writes": ["edit.json"]}, {"guest_memory_writes": 1},
                      {"writes": ""}, {"guest_memory_writes": False}):
            source = receipt()
            source.update(edits)
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                PLAN.build_manifest(source, [(2, "end")])

    def test_malformed_or_empty_controls_are_rejected(self):
        for controls in ([], [[1]], [[1, 2, 3]], ["1:2"], [[0, 900]], [[False, 1]]):
            with self.subTest(controls=controls), self.assertRaises(ValueError):
                PLAN.build_manifest(receipt(controls), [(0, "end")])

    def test_total_frame_bound(self):
        controls = [[0, 500] for _ in range(40)]
        PLAN.build_manifest(receipt(controls), [(39, "end")])
        controls.append([0, 1])
        with self.assertRaisesRegex(ValueError, "20000"):
            PLAN.build_manifest(receipt(controls), [(40, "end")])

    def test_checkpoint_requires_a_new_step(self):
        for actions in ([dict(cmd="checkpoint", label="start"), dict(cmd="quit")],
                        [*one_step()[:-1], dict(cmd="checkpoint", label="again"), dict(cmd="quit")]):
            with self.subTest(actions=actions), self.assertRaises(ValueError):
                PLAN.parse_manifest(raw(actions))

    def test_quit_must_be_final_after_last_checkpoint(self):
        for actions in (one_step()[:-1], one_step() + [dict(cmd="step", mask=0, frames=1)],
                        [dict(cmd="step", mask=0, frames=1), dict(cmd="quit")],
                        [dict(cmd="quit")]):
            with self.subTest(actions=actions), self.assertRaises(ValueError):
                PLAN.parse_manifest(raw(actions))

    def test_extra_fields_and_unknown_commands_are_rejected(self):
        for action in (dict(cmd="step", mask=0, frames=1, capture=False), dict(cmd="resume"),
                       dict(cmd="checkpoint", label="end", extra=1), dict(cmd="quit", extra=1)):
            with self.subTest(action=action), self.assertRaises(ValueError):
                PLAN.parse_manifest(raw([action]))

    def test_incomplete_or_oversized_records_are_rejected(self):
        for value in (b"", raw(one_step()).rstrip(b"\n"), b"\n", b" " * 65536 + b"\n"):
            with self.subTest(length=len(value)), self.assertRaises(ValueError):
                PLAN.parse_manifest(value)

    def test_write_is_exclusive_and_source_stays_unchanged(self):
        with tempfile.TemporaryDirectory(prefix="scenario-synthetic-") as directory:
            source = Path(directory) / "receipt.json"
            output = Path(directory) / "plan.jsonl"
            original = json.dumps(receipt()).encode()
            source.write_bytes(original)
            result = PLAN.write_plan(source, [(2, "end")], output)
            self.assertEqual(output.read_bytes(), result)
            with self.assertRaises(FileExistsError):
                PLAN.write_plan(source, [(2, "another_end")], output)
            self.assertEqual(output.read_bytes(), result)
            self.assertEqual(source.read_bytes(), original)

    def test_cli_build_and_validate(self):
        with tempfile.TemporaryDirectory(prefix="scenario-cli-synthetic-") as directory:
            source = Path(directory) / "receipt.json"
            output = Path(directory) / "plan.jsonl"
            source.write_text(json.dumps(receipt()), encoding="utf-8")
            for arguments in (["build", str(source), "--milestone", "0:menu", "--milestone", "2:end",
                               "--out", str(output)], ["validate", str(output)]):
                result = subprocess.run([sys.executable, "-B", str(PATH), *arguments],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("3 controls, 2 milestones, 612 new frames", result.stdout)


if __name__ == "__main__":
    unittest.main()
