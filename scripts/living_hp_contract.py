"""Pure planning and commit checks for independently verified living-HP assists.

This module performs no I/O and grants no game-write authority. Callers verify
and freeze the supplied authority binding, game-specific addresses, read-only
maximum and complete backing-alias footprint. They retain raw native ACKs and
validate their protocol before supplying the small acknowledgement view below.
Original-source footprint completeness and paused-view construction likewise
belong to the caller; this module never removes fields or normalizes guest state.
"""
import copy
import re

U64 = (1 << 64) - 1


def _require(value, message):
    if not value:
        raise ValueError(message)


def _integer(value, low, high, name):
    _require(type(value) is int and low <= value <= high, name + " outside bounds")
    return value


def _fields(value, fields, name):
    _require(type(value) is dict and set(value) == set(fields), name + " fields differ")


def _same(left, right, depth=0):
    """Type-strict equality: booleans cannot stand in for counters or bytes."""
    if depth > 32 or type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(
            _same(left[key], right[key], depth + 1) for key in left
        )
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(
            _same(a, b, depth + 1) for a, b in zip(left, right)
        )
    return type(left) in (str, bytes, int, bool, type(None)) and left == right


def plan_edit(policy, snapshot, authority, *, successful_edits=0):
    """Plan one current-HP low-byte CAS; never lower max, revive or overfill.

    ``snapshot.ram`` is a complete caller-selected RAM window containing both
    two-byte HP fields. ``executed_physical`` contains physical fetch addresses
    from complete original-source evidence. ``authority.verified`` asserts that
    the caller verified the actual bound evidence, rather than trusting a name.
    A returned plan is data only and does not authorize issuing its request.
    """
    _fields(policy, {"current_address", "maximum_address", "readonly_maximum",
                     "aliases", "max_successful_edits"}, "policy")
    current = _integer(policy["current_address"], 0, U64 - 1, "current address")
    maximum = _integer(policy["maximum_address"], 0, U64 - 1, "maximum address")
    _require(abs(current - maximum) >= 2, "HP fields overlap")
    target = _integer(policy["readonly_maximum"], 2, 255, "read-only maximum")
    cap = _integer(policy["max_successful_edits"], 1, 1000, "successful edit cap")
    _integer(successful_edits, 0, cap - 1, "successful edits")
    aliases = policy["aliases"]
    _require(type(aliases) is list and 1 <= len(aliases) <= 256, "alias footprint required")
    for address in aliases:
        _integer(address, 0, U64, "backing alias")
    _require(len(set(aliases)) == len(aliases) and current in aliases,
             "distinct aliases must include current HP")
    _require(not {current + 1, maximum, maximum + 1}.intersection(aliases),
             "low-byte aliases overlap high or maximum fields")

    _fields(authority, {"verified", "sha256", "scope"}, "authority binding")
    _require(authority["verified"] is True and type(authority["verified"]) is bool,
             "independently verified authority required")
    _require(type(authority["sha256"]) is str and
             re.fullmatch(r"[0-9a-f]{64}", authority["sha256"]) is not None,
             "full lowercase authority SHA256 required")
    _require(authority["scope"] == "living-current-hp-only", "authority scope differs")

    _fields(snapshot, {"base", "ram", "executed_physical"}, "RAM/source snapshot")
    base = _integer(snapshot["base"], 0, U64, "RAM base")
    ram = snapshot["ram"]
    _require(type(ram) is bytes and 4 <= len(ram) <= 1024 * 1024 and
             base + len(ram) - 1 <= U64, "bounded complete RAM bytes required")
    _require(base <= current < current + 1 < base + len(ram) and
             base <= maximum < maximum + 1 < base + len(ram), "both HP fields must be captured")
    fetched = snapshot["executed_physical"]
    _require(type(fetched) is list and 1 <= len(fetched) <= 1024 * 1024,
             "complete original-source physical footprint required")
    for address in fetched:
        _integer(address, 0, U64, "executed physical address")
    _require(not set(aliases).intersection(fetched), "HP backing alias was fetched as source")
    hp = ram[current - base:current - base + 2]
    limit = ram[maximum - base:maximum - base + 2]
    _require(hp[1] == limit[1] == 0 and limit[0] == target,
             "fresh read-only maximum and zero high bytes required")
    _require(1 <= hp[0] < target, "living below-maximum HP required; no revive or redundant edit")
    return {
        "schema": 1,
        "policy": copy.deepcopy(policy),
        "snapshot": copy.deepcopy(snapshot),
        "authority": copy.deepcopy(authority),
        "successful_edits": successful_edits,
        "request": {"address": current, "expected": hp[:1], "data": limit[:1]},
    }


def validate_result(plan, result):
    """Validate a committed single-attempt CAS against full RAM and paused views.

    Failed, unacknowledged or uncertain attempts cannot pass this function.
    Native I/O, durable intent, failure capture and the prohibition on retries
    remain the caller's responsibility. No rollback is inferred or requested.
    """
    _fields(plan, {"schema", "policy", "snapshot", "authority", "successful_edits", "request"}, "plan")
    _require(type(plan["schema"]) is int and plan["schema"] == 1, "plan schema differs")
    rebuilt = plan_edit(plan["policy"], plan["snapshot"], plan["authority"],
                        successful_edits=plan["successful_edits"])
    _require(_same(plan, rebuilt), "plan no longer matches its verified inputs")
    _fields(result, {"request_attempts", "ack", "readback", "ram_after",
                     "write_requests_before", "write_requests_after",
                     "bytes_changed_before", "bytes_changed_after",
                     "paused_before", "paused_after"}, "CAS result")
    _integer(result["request_attempts"], 1, 1, "one request attempt")
    ack = result["ack"]
    _fields(ack, {"ok", "address", "length"}, "acknowledgement view")
    _require(ack["ok"] is True and type(ack["ok"]) is bool, "positive acknowledgement required")
    _integer(ack["address"], plan["request"]["address"], plan["request"]["address"], "ACK address")
    _integer(ack["length"], 1, 1, "ACK length")
    _require(type(result["readback"]) is bytes and result["readback"] == plan["request"]["data"],
             "exact one-byte readback required")
    before, after = plan["snapshot"]["ram"], result["ram_after"]
    _require(type(after) is bytes and len(after) == len(before), "complete unchanged RAM extent required")
    offset = plan["request"]["address"] - plan["snapshot"]["base"]
    _require([i for i, (a, b) in enumerate(zip(before, after)) if a != b] == [offset],
             "only the current HP low byte may change")
    _require(after[offset:offset + 1] == plan["request"]["data"], "RAM result differs from requested byte")
    for prefix in ("write_requests", "bytes_changed"):
        a = _integer(result[prefix + "_before"], 0, U64 - 1, prefix + " before")
        b = _integer(result[prefix + "_after"], 0, U64, prefix + " after")
        _require(b == a + 1, "one actual " + prefix + " increment required")
    _require(type(result["paused_before"]) is dict and bool(result["paused_before"]) and
             _same(result["paused_before"], result["paused_after"]),
             "paused source/CPU/device/clock views must remain exactly equal")
    return {"committed": True, "write_requests_delta": 1, "bytes_changed_delta": 1,
            "successful_edits": plan["successful_edits"] + 1,
            "authority_sha256": plan["authority"]["sha256"]}
