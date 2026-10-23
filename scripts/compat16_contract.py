"""Authored checks for the declared ABI16 unknown-CD diagnostics.

This validates retained observations only. It does not select a toolkit pin,
enable ABI16 execution or remove new diagnostics from guest comparisons.
Origin describes the last CPU $1801 latch write supplying the initial CDB
byte before its ACK, not an ACK or retirement trace.
"""
from __future__ import annotations

import copy

U64 = (1 << 64) - 1
KNOWN_CD_COMMANDS = {0, 3, 8, 0xD8, 0xD9, 0xDA, 0xDD, 0xDE}


def _integer(value, maximum, label, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(label + ' is not a bounded integer')
    return value


def _keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(label + ' fields differ from the declared contract')


def validate_cd_unknown(value, accepted_count, *, observed_ticks=None):
    """Retain exact fields, checking counts and mapped CPU-origin identity.

    Attempts include strict faults; accepted_count is the existing host/runner
    unknown_commands counter. Nullable fetch bytes remain nullable. Repeated
    latch writes retain the one supplying the initial accepted CDB byte. The last
    unknown command is independent of SCSI's later last-command diagnostic.
    """
    _integer(accepted_count, U64, 'existing accepted-response count')
    if observed_ticks is not None:
        _integer(observed_ticks, U64, 'observation ticks')
    _keys(value, {'accepted_responses', 'opcodes', 'last_command', 'origin'}, 'cd_unknown')
    accepted = _integer(value['accepted_responses'], U64, 'accepted responses')
    if accepted != accepted_count:
        raise ValueError('accepted responses disagree with existing unknown_commands')
    opcodes = value['opcodes']
    if not isinstance(opcodes, list) or len(opcodes) > 256:
        raise ValueError('unknown opcode histogram exceeds its bound')
    previous, attempts, counted = -1, 0, set()
    for item in opcodes:
        _keys(item, {'opcode', 'attempts'}, 'unknown opcode')
        opcode = _integer(item['opcode'], 255, 'unknown opcode')
        if opcode <= previous or opcode in KNOWN_CD_COMMANDS:
            raise ValueError('unknown histogram requires sorted unique unsupported-length opcodes')
        attempts += _integer(item['attempts'], U64, 'unknown attempts', 1)
        previous = opcode
        counted.add(opcode)
    if accepted > attempts:
        raise ValueError('accepted responses exceed unknown attempts')
    command = value['last_command']
    if not isinstance(command, list) or len(command) > 16:
        raise ValueError('last unknown command exceeds its bounded CDB')
    for byte in command:
        _integer(byte, 255, 'last unknown command byte')
    if bool(command) != bool(opcodes) or (command and command[0] not in counted):
        raise ValueError('last unknown command disagrees with opcode histogram')
    origin = value['origin']
    if origin is not None:
        if not opcodes:
            raise ValueError('unknown origin exists without an unknown attempt')
        _keys(origin, {'pc', 'ticks', 'mpr', 'physical_pc', 'fetch'}, 'unknown CPU origin')
        pc = _integer(origin['pc'], 65535, 'unknown origin PC')
        ticks = _integer(origin['ticks'], U64, 'unknown origin ticks')
        if observed_ticks is not None and ticks > observed_ticks:
            raise ValueError('unknown origin is later than its observation')
        mpr = origin['mpr']
        if not isinstance(mpr, list) or len(mpr) != 8:
            raise ValueError('unknown origin requires all eight MPRs')
        for bank in mpr:
            _integer(bank, 255, 'unknown origin MPR')
        physical = _integer(origin['physical_pc'], 0x1FFFFF, 'unknown origin physical PC')
        if physical != (mpr[pc >> 13] << 13) | (pc & 8191):
            raise ValueError('unknown origin physical PC disagrees with mapped PC/MPR')
        fetch = origin['fetch']
        if not isinstance(fetch, list) or len(fetch) != 7:
            raise ValueError('unknown origin requires seven nullable pure-fetch bytes')
        for byte in fetch:
            if byte is not None:
                _integer(byte, 255, 'unknown origin fetch byte')
    return copy.deepcopy(value)
