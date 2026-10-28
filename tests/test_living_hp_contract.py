"""Authored synthetic RAM and source-footprint cases; no game inputs or I/O."""
import copy
import unittest

from scripts import living_hp_contract as c


class LivingHpTests(unittest.TestCase):
    def inputs(self, hp=9, maximum=60):
        ram = bytearray(64)
        ram[8] = hp
        ram[20] = maximum
        policy = {"current_address": 4104, "maximum_address": 4116,
                  "readonly_maximum": 60, "aliases": [4104, 8200],
                  "max_successful_edits": 6}
        snapshot = {"base": 4096, "ram": bytes(ram), "executed_physical": [32768, 32769]}
        authority = {"verified": True, "sha256": "a" * 64, "scope": "living-current-hp-only"}
        return policy, snapshot, authority

    def planned(self, hp=9):
        return c.plan_edit(*self.inputs(hp))

    def result(self, plan):
        ram = bytearray(plan["snapshot"]["ram"])
        ram[8] = 60
        paused = {"cpu": {"mpr": [0, 1, 2, 3, 4, 5, 6, 7], "generation": [4, 4]},
                  "ticks": 123, "pcm": {"hash": 456, "frames": 78}}
        return {"request_attempts": 1, "ack": {"ok": True, "address": 4104, "length": 1},
                "readback": b"\x3c", "ram_after": bytes(ram),
                "write_requests_before": 3, "write_requests_after": 4,
                "bytes_changed_before": 7, "bytes_changed_after": 8,
                "paused_before": paused, "paused_after": copy.deepcopy(paused)}

    def test_living_range_and_inputs_preserved(self):
        for hp in (1, 5, 9, 37, 59):
            inputs = self.inputs(hp)
            before = copy.deepcopy(inputs)
            plan = c.plan_edit(*inputs)
            self.assertEqual(plan["request"], {"address": 4104, "expected": bytes([hp]), "data": b"\x3c"})
            self.assertEqual(inputs, before)

    def test_dead_redundant_overfilled_or_wrong_maximum(self):
        for hp, maximum in ((0, 60), (60, 60), (61, 60), (5, 50)):
            with self.assertRaises(ValueError):
                c.plan_edit(*self.inputs(hp, maximum))

    def test_high_bytes_and_incomplete_ram(self):
        for offset in (9, 21):
            policy, snapshot, authority = self.inputs()
            ram = bytearray(snapshot["ram"])
            ram[offset] = 1
            snapshot["ram"] = bytes(ram)
            with self.assertRaises(ValueError):
                c.plan_edit(policy, snapshot, authority)
        for ram in (b"", b"\x00" * 10, bytearray(64)):
            policy, snapshot, authority = self.inputs()
            snapshot["ram"] = ram
            with self.assertRaises(ValueError):
                c.plan_edit(policy, snapshot, authority)

    def test_all_declared_aliases_and_missing_source_proof(self):
        for address in (4104, 8200):
            policy, snapshot, authority = self.inputs()
            snapshot["executed_physical"].append(address)
            with self.assertRaises(ValueError):
                c.plan_edit(policy, snapshot, authority)
        for footprint in ([], [True], [1.5], [-1]):
            policy, snapshot, authority = self.inputs()
            snapshot["executed_physical"] = footprint
            with self.assertRaises(ValueError):
                c.plan_edit(policy, snapshot, authority)

    def test_address_alias_and_policy_types(self):
        for key, value in (("current_address", True), ("maximum_address", 4105),
                           ("readonly_maximum", True), ("readonly_maximum", 256),
                           ("max_successful_edits", True), ("aliases", [8200]),
                           ("aliases", [4104, 4104]), ("aliases", [4104, 4116]),
                           ("aliases", [4104, True])):
            policy, snapshot, authority = self.inputs()
            policy[key] = value
            with self.assertRaises(ValueError):
                c.plan_edit(policy, snapshot, authority)

    def test_verified_binding_and_scope_required(self):
        for key, value in (("verified", False), ("verified", 1), ("sha256", "A" * 64),
                           ("sha256", "a" * 63), ("scope", "revive")):
            policy, snapshot, authority = self.inputs()
            authority[key] = value
            with self.assertRaises(ValueError):
                c.plan_edit(policy, snapshot, authority)

    def test_success_cap_and_boolean_counter(self):
        for count in (-1, True, 6):
            with self.assertRaises(ValueError):
                c.plan_edit(*self.inputs(), successful_edits=count)
        plan = c.plan_edit(*self.inputs(), successful_edits=5)
        self.assertEqual(c.validate_result(plan, self.result(plan))["successful_edits"], 6)

    def test_exact_committed_single_byte_result(self):
        plan = self.planned()
        result = self.result(plan)
        before = copy.deepcopy((plan, result))
        self.assertEqual(c.validate_result(plan, result), {
            "committed": True, "write_requests_delta": 1, "bytes_changed_delta": 1,
            "successful_edits": 1, "authority_sha256": "a" * 64})
        self.assertEqual((plan, result), before)

    def test_other_byte_maximum_or_high_changes_rejected(self):
        for offset in (0, 9, 20, 21):
            plan = self.planned()
            result = self.result(plan)
            ram = bytearray(result["ram_after"])
            ram[offset] ^= 1
            result["ram_after"] = bytes(ram)
            with self.assertRaises(ValueError):
                c.validate_result(plan, result)

    def test_retry_uncertainty_ack_and_readback_rejected(self):
        for key, value in (("request_attempts", 0), ("request_attempts", 2),
                           ("request_attempts", True), ("readback", b"\x3b"),
                           ("readback", b"\x3c\x00"), ("ack", None)):
            plan = self.planned()
            result = self.result(plan)
            result[key] = value
            with self.assertRaises(ValueError):
                c.validate_result(plan, result)
        for key, value in (("ok", False), ("ok", 1), ("address", 4116),
                           ("address", True), ("length", 2), ("length", True)):
            plan = self.planned()
            result = self.result(plan)
            result["ack"][key] = value
            with self.assertRaises(ValueError):
                c.validate_result(plan, result)

    def test_accounting_exactly_one_not_boolean_or_hidden(self):
        for key, value in (("write_requests_before", True), ("write_requests_after", 3),
                           ("write_requests_after", 5), ("bytes_changed_before", True),
                           ("bytes_changed_after", 7), ("bytes_changed_after", 9)):
            plan = self.planned()
            result = self.result(plan)
            result[key] = value
            with self.assertRaises(ValueError):
                c.validate_result(plan, result)

    def test_paused_views_keep_all_source_and_clock_types(self):
        for mutate in ("ticks", "mpr", "generation", "pcm", "bool"):
            plan = self.planned()
            result = self.result(plan)
            view = result["paused_after"]
            if mutate == "ticks":
                view["ticks"] += 1
            elif mutate == "mpr":
                view["cpu"]["mpr"][0] = 8
            elif mutate == "generation":
                view["cpu"]["generation"][0] += 1
            elif mutate == "pcm":
                view["pcm"]["hash"] += 1
            else:
                view["cpu"]["mpr"][1] = True
            with self.assertRaises(ValueError):
                c.validate_result(plan, result)

    def test_unknown_fields_and_plan_tampering_rejected(self):
        for part in ("policy", "snapshot", "authority"):
            inputs = list(self.inputs())
            inputs[("policy", "snapshot", "authority").index(part)]["unknown"] = 1
            with self.assertRaises(ValueError):
                c.plan_edit(*inputs)
        plan = self.planned()
        plan["request"]["data"] = b"\x63"
        with self.assertRaises(ValueError):
            c.validate_result(plan, self.result(plan))
        plan = self.planned()
        result = self.result(plan)
        result["unknown"] = True
        with self.assertRaises(ValueError):
            c.validate_result(plan, result)


if __name__ == "__main__":
    unittest.main()
