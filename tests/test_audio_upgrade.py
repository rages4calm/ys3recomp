"""Authored audio-upgrade evidence graphs and negative qualification checks."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import wave

from scripts.qualify_audio_upgrade import load_expectation, qualify_audio_upgrade
from tests.test_desktop_qualification import desktop_fixture


def digest(value):
    return hashlib.sha256(value).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return digest(path.read_bytes())


class EvidenceFixture:
    def __init__(self, root, changed=False, declare=True):
        self.root = root
        _, base, _, run = desktop_fixture()
        self.baseline, self.old_run = copy.deepcopy(base), copy.deepcopy(run)
        tool = {"revision": "a" * 40, "source_sha256": "b" * 64, "runtime_abi": 13}
        self.tool = tool
        for key in ("source_route_sha256", "source_binary_sha256", "initial_bram_sha256"):
            self.baseline[key] = digest(key.encode())
        self.baseline["source_command"] = ["authored-frozen-runner", "authored-frozen-image", "0", "0", "mpr", "100", "100", "hybrid"]
        self.baseline["command"] = self.baseline["source_command"] + ["--hidden", "on", "--unthrottled", "on", "--audio-output", "on"]
        self.baseline["command"][0] = self.baseline["desktop_contract"]["package_before"]["binary"]
        self.baseline["project_verification_before"] = {"schema": 1, "verified": True,
                                                        "tool": {key: tool[key] for key in ("revision", "source_sha256")}}
        self.baseline["project_verification_after"] = copy.deepcopy(self.baseline["project_verification_before"])
        outputs = self.baseline["desktop_contract"]["package_before"]["output_files"]
        self.baseline["project_output_files_before"] = outputs.copy()
        self.baseline["project_output_files_after"] = outputs.copy()
        self.candidate, self.new_run = copy.deepcopy(self.baseline), copy.deepcopy(self.old_run)
        identity = {"revision": tool["revision"], "runtime_abi": 13,
                    "shared_source_identity": {"revision": tool["revision"], "source_sha256": tool["source_sha256"]}}
        self.candidate["tool_identity"] = identity
        self.candidate["tool_identity_after"] = copy.deepcopy(identity)
        if changed:
            for value in self.candidate_audio_objects():
                value.update(psg_nonzero=11, mixed_nonzero=41, peak=1001, pcm_hash=654321)
            self.new_run["audio_output"].update(psg_nonzero=11, mixed_nonzero=41, peak=1001, pcm_hash=654321)
        self.reference, self.reference_run = copy.deepcopy(self.candidate), copy.deepcopy(self.new_run)
        self.reference["command"] = self.reference["source_command"] + ["--audio-output", "on"]
        self.reference.pop("desktop_contract")
        self.reference["audio_contract"]["headless_pcm_only"] = True
        self.reference_run.pop("desktop")
        for obj in [self.reference_run["audio_output"], *self.reference_audio_objects()]:
            for key in ("device_open", "fast_forward_muted", "host"):
                obj.pop(key, None)
        self.gear = {"passed": True, "source_sha256": tool["source_sha256"], "runtime_abi": 13,
                     "scope": "Authored independent synthetic PSG probe"}
        self.paths = {role: root / (role + (".wav" if role == "wav" else ".json")) for role in
                      ("run", "receipt", "wav", "upstream_qualification", "independent_gear")}
        self.wav(self.paths["wav"], changed)
        wave_hash = digest(self.paths["wav"].read_bytes())
        for receipt in (self.candidate, self.reference):
            receipt["audio_contract"].update(wav_sha256=wave_hash, wav_bytes=124)
        oldwav = root / "old.wav"
        self.wav(oldwav, False)
        self.baseline["audio_contract"].update(wav_sha256=digest(oldwav.read_bytes()), wav_bytes=124)
        self.expectation = {"schema": 1, "kind": "ys3-reviewed-audio-upgrade", "tool": tool,
            "route": {key: self.candidate[key] for key in ("source_route_sha256", "source_binary_sha256", "initial_bram_sha256")},
            "files": {}, "qualification_success": True, "gear_success": True,
            "qualification_pointers": {key: "/" + key for key in
                ("result", "tool_revision", "source_sha256", "runtime_abi", "route_sha256", "run_sha256", "receipt_sha256", "wav_sha256", "independent_gear_sha256")},
            "gear_pointers": {"result": "/passed", "source_sha256": "/source_sha256", "runtime_abi": "/runtime_abi"},
            "reviewed_binding": {"qualified": True, "tool": copy.deepcopy(tool),
                "route": {key: self.candidate[key] for key in ("source_route_sha256", "source_binary_sha256", "initial_bram_sha256")},
                "execution": {"tier": "hybrid", "audio": "on", "candidate_desktop_packaged": True, "reference_host": "headless"},
                "evidence_sha256": {}, "independent_scope": "Authored independent synthetic PSG probe"}}
        if declare:
            self.expectation["allowed_pcm_changes"] = ["psg_nonzero", "mixed_nonzero", "peak", "pcm_hash"] if changed else []
        self.expectation_path = root / "expectation.json"
        self.write()

    @staticmethod
    def wav(path, changed):
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(2)
            stream.setsampwidth(2)
            stream.setframerate(44100)
            stream.writeframes((b"\1\0\1\0" if changed else b"\0\0\0\0") * 20)

    def candidate_audio_objects(self):
        return [self.candidate["audio_contract"]["validated_output"], self.candidate["desktop_contract"]["audio_output"],
                *(self.candidate[name]["host"]["audio_output"] for name in ("before_final_release", "final_status", "released_status")),
                *(state["host"]["audio_output"] for state in self.candidate["checkpoint_status"])]

    def reference_audio_objects(self):
        return [self.reference["audio_contract"]["validated_output"],
                *(self.reference[name]["host"]["audio_output"] for name in ("before_final_release", "final_status", "released_status")),
                *(state["host"]["audio_output"] for state in self.reference["checkpoint_status"])]

    def write(self):
        hashes = {"run": dump(self.paths["run"], self.reference_run),
                  "receipt": dump(self.paths["receipt"], self.reference),
                  "wav": digest(self.paths["wav"].read_bytes()),
                  "independent_gear": dump(self.paths["independent_gear"], self.gear)}
        self.qualification = {"result": True, "tool_revision": self.tool["revision"],
            "source_sha256": self.tool["source_sha256"], "runtime_abi": 13,
            "route_sha256": self.candidate["source_route_sha256"],
            **{role + "_sha256": value for role, value in hashes.items()}}
        hashes["upstream_qualification"] = dump(self.paths["upstream_qualification"], self.qualification)
        self.expectation["files"] = {role: {"path": path.name, "sha256": hashes[role]} for role, path in self.paths.items()}
        self.expectation["reviewed_binding"]["evidence_sha256"] = hashes
        dump(self.expectation_path, self.expectation)

    def qualify(self):
        return qualify_audio_upgrade(self.baseline, self.candidate, self.old_run, self.new_run, self.expectation_path)


class AudioUpgradeTests(unittest.TestCase):
    def test_default_no_pcm_change_and_declared_new_reference_change_pass(self):
        for changed, declare in ((False, False), (True, True)):
            with tempfile.TemporaryDirectory() as folder:
                fixture = EvidenceFixture(Path(folder), changed, declare)
                result = fixture.qualify()
                self.assertTrue(result["audio_upgrade_qualified"])
                self.assertEqual(result["old_audio"]["pcm"]["pcm_hash"], 123456)
                self.assertEqual(result["new_audio"]["pcm"]["pcm_hash"], 654321 if changed else 123456)

    def test_changes_without_declaration_or_pinned_reference_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = EvidenceFixture(Path(folder), changed=True, declare=False)
            with self.assertRaisesRegex(ValueError, "unchanged"):
                fixture.qualify()
            fixture.expectation["allowed_pcm_changes"] = ["pcm_hash", "psg_nonzero", "mixed_nonzero", "peak"]
            dump(fixture.expectation_path, fixture.expectation)
            fixture.paths["run"].write_text("{}")
            with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
                fixture.qualify()

    def test_guest_counter_source_image_and_schema_changes_fail(self):
        changes = (lambda f: f.new_run["device"].update(writes=9),
                   lambda f: f.new_run.update(native_steps=99, interpreter_steps=1),
                   lambda f: f.new_run["source"].update(generations=[3, 5]),
                   lambda f: f.candidate["images"][0].update(png_sha256="changed"),
                   lambda f: f.candidate["final_status"]["host"].update(unknown_guest=1),
                   lambda f: f.candidate["checkpoint_status"][0].update(new_status_diagnostic=1),
                   lambda f: f.new_run["audio_output"].update(unknown_pcm=1))
        for change in changes:
            with tempfile.TemporaryDirectory() as folder:
                fixture = EvidenceFixture(Path(folder), changed=True)
                change(fixture)
                with self.assertRaises((ValueError, RuntimeError)):
                    fixture.qualify()

    def test_tool_route_reference_status_and_unknown_expectation_fail(self):
        changes = (lambda f: f.candidate["tool_identity"].update(revision="e" * 40),
                   lambda f: f.candidate["project_verification_before"]["tool"].update(source_sha256="e" * 64),
                   lambda f: f.reference.update(source_route_sha256="e" * 64),
                   lambda f: f.reference.update(passed=False),
                   lambda f: f.reference.update(exit_code=1),
                   lambda f: f.reference["command"].__setitem__(7, "native"),
                   lambda f: f.reference["tool_identity"]["shared_source_identity"].update(source_sha256="e" * 64))
        for change in changes:
            with tempfile.TemporaryDirectory() as folder:
                fixture = EvidenceFixture(Path(folder), changed=True)
                change(fixture)
                fixture.write()
                with self.assertRaises(ValueError):
                    fixture.qualify()
        with tempfile.TemporaryDirectory() as folder:
            fixture = EvidenceFixture(Path(folder))
            fixture.expectation["unexpected"] = True
            dump(fixture.expectation_path, fixture.expectation)
            with self.assertRaisesRegex(ValueError, "schema"):
                fixture.qualify()

    def test_upstream_qualification_must_link_every_exact_reference(self):
        for key, changed in (("result", False), ("tool_revision", "e" * 40),
                             ("source_sha256", "e" * 64), ("runtime_abi", 14),
                             ("route_sha256", "e" * 64), ("run_sha256", "e" * 64),
                             ("receipt_sha256", "e" * 64), ("wav_sha256", "e" * 64),
                             ("independent_gear_sha256", "e" * 64)):
            with tempfile.TemporaryDirectory() as folder:
                fixture = EvidenceFixture(Path(folder), changed=True)
                fixture.qualification[key] = changed
                new_hash = dump(fixture.paths["upstream_qualification"], fixture.qualification)
                fixture.expectation["files"]["upstream_qualification"]["sha256"] = new_hash
                fixture.expectation["reviewed_binding"]["evidence_sha256"]["upstream_qualification"] = new_hash
                dump(fixture.expectation_path, fixture.expectation)
                with self.subTest(key=key), self.assertRaises(ValueError):
                    fixture.qualify()

    def test_independent_gear_must_pass_exact_new_source_and_abi(self):
        for key, changed in (("passed", False), ("source_sha256", "e" * 64), ("runtime_abi", 14)):
            with tempfile.TemporaryDirectory() as folder:
                fixture = EvidenceFixture(Path(folder), changed=True)
                fixture.gear[key] = changed
                fixture.write()
                with self.assertRaises(ValueError):
                    fixture.qualify()

    def test_only_reviewed_psg_synthesis_fields_can_be_declared(self):
        for field in ("frames", "sample_rate", "channels", "enabled", "discarded_frames",
                      "wav_frames", "wav_truncated", "adpcm_nonzero", "cdda_nonzero"):
            with tempfile.TemporaryDirectory() as folder:
                fixture = EvidenceFixture(Path(folder))
                fixture.expectation["allowed_pcm_changes"] = [field]
                dump(fixture.expectation_path, fixture.expectation)
                with self.subTest(field=field), self.assertRaises(ValueError):
                    fixture.qualify()

    def test_checkpoint_pcm_matches_new_reference_not_old(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = EvidenceFixture(Path(folder), changed=True)
            fixture.reference["checkpoint_status"][0]["host"]["audio_output"]["pcm_hash"] = 123456
            fixture.write()
            with self.assertRaisesRegex(ValueError, "new_reference"):
                fixture.qualify()

    def test_validated_checkpoint_drain_counters_are_separate_from_pcm_comparison(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = EvidenceFixture(Path(folder), changed=True)
            # Same generated PCM, different pre-drain phase. Quota is saturated.
            fixture.candidate["checkpoint_status"][0]["host"]["audio_output"]["host"].update(submitted_frames=71, dropped_frames=71)
            self.assertTrue(fixture.qualify()["passed"])
            fixture.candidate["checkpoint_status"][0]["host"]["audio_output"]["discarded_frames"] = 1
            with self.assertRaises(ValueError):
                fixture.qualify()

    def test_unsaturated_checkpoint_wav_phase_is_validated_not_compared_as_pcm(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = EvidenceFixture(Path(folder), changed=True)
            for receipt, new in ((fixture.baseline, False), (fixture.candidate, True), (fixture.reference, True)):
                audio = receipt["checkpoint_status"][0]["host"]["audio_output"]
                audio.update(frames=25, psg_nonzero=6 if new else 5, adpcm_nonzero=4,
                             cdda_nonzero=3, mixed_nonzero=16 if new else 15)
                if "host" in audio:
                    audio["host"].update(submitted_frames=25, dropped_frames=25)
            candidate_audio = fixture.candidate["checkpoint_status"][0]["host"]["audio_output"]
            candidate_audio.update(wav_frames=15, wav_truncated=False)
            candidate_audio["host"].update(submitted_frames=15, dropped_frames=15)
            fixture.write()
            result = fixture.qualify()
            self.assertEqual(result["checkpoint_audio"][0]["new_pcm"]["wav_frames"], 15)
            self.assertEqual(result["checkpoint_audio"][0]["reference_pcm"]["wav_frames"], 20)
            candidate_audio["wav_frames"] = 16
            with self.assertRaises(ValueError):
                fixture.qualify()

    def test_new_wav_must_match_new_reference_and_have_valid_geometry(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = EvidenceFixture(Path(folder), changed=True)
            fixture.candidate["audio_contract"]["wav_sha256"] = fixture.baseline["audio_contract"]["wav_sha256"]
            with self.assertRaisesRegex(ValueError, "candidate.wav_sha256"):
                fixture.qualify()
            fixture.paths["wav"].write_bytes(b"not a wave")
            with self.assertRaises(ValueError):
                fixture.qualify()

    def test_unknown_abi_and_reference_envelope_require_followup_review(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = EvidenceFixture(Path(folder))
            fixture.expectation["tool"]["runtime_abi"] = 14
            dump(fixture.expectation_path, fixture.expectation)
            with self.assertRaisesRegex(ValueError, "ABI 13"):
                load_expectation(fixture.expectation_path)


if __name__ == "__main__":
    unittest.main()
