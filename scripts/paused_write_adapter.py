"""Single-attempt WRAM data assists with separately verified caller authority.

The caller owns exact build/topology, title policy, complete original/prefix
source bindings and fresh live footprint. No automatic assists or retries.
"""
import copy

BASE, SIZE, U64 = 0x1F0000, 8192, (1 << 64) - 1


def require(ok, message):
    if not ok:
        raise ValueError(message)


def integer(value, low, high):
    require(type(value) is int and low <= value <= high, 'Exact bounded integer required')
    return value


def same(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(same(left[k], right[k]) for k in left)
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(same(x, y) for x, y in zip(left, right))
    return type(left) in (int, bool, str, type(None)) and left == right


class PausedWRAMAssist:
    """One capability, poisoned on any failure, including uncertain delivery.

    ``authorize`` must revalidate bound evidence and return a private policy
    receipt for the exact fresh status/RAM/literal. ``source_snapshot`` must
    return (complete original+live physical footprint, immutable epoch receipt).
    It must preserve checkpoint origins; this class grants no prefix authority.
    ``persist`` must durably retain each record or raise before proceeding.
    A single client owner is mandatory; its pinned next-ID contract is used to
    record the exact request before sending. SDK wire journaling is mandatory.
    """
    def __init__(self, client, *, observation, writes, persist, authorize, source_snapshot):
        require(all(callable(f) for f in (persist, authorize, source_snapshot)),
                'Authority, source and durable evidence callbacks required')
        self.client, self.observation, self.writes = client, observation, writes
        self.persist, self.authorize, self.source_snapshot = persist, authorize, source_snapshot
        self.used = False

    def ram(self):
        chunks = [self.client.read_memory(BASE + i, 256) for i in range(0, SIZE, 256)]
        require(all(type(x) is bytes and len(x) == 256 for x in chunks), 'Complete WRAM read required')
        return b''.join(chunks)

    def apply(self, *, address, expected, data):
        require(not self.used, 'Assist capability already consumed or failed')
        self.used = True  # Also poison preflight/persistence failures; never reuse.
        journal = getattr(self.client, '_journal', None)
        require(journal is not None and getattr(journal, '_stream', None) is not None
                and not journal._stream.closed and getattr(journal, '_failed', True) is False,
                'Live durable SDK wire journal required')
        integer(address, BASE, BASE + SIZE - 1)
        require(type(expected) is bytes and type(data) is bytes and
                1 <= len(data) == len(expected) <= 256 and data != expected and
                address + len(data) <= BASE + SIZE, 'Exact bounded nonredundant literal required')
        a = self.client.call('status')
        memory = self.ram()
        footprint, epoch = self.source_snapshot()
        require(type(epoch) is dict and bool(epoch), 'Explicit bound source epoch receipt required')
        require(type(footprint) in (set, frozenset) and 0 < len(footprint) <= 0x200000,
                'Complete bound original and live footprint required')
        footprint = frozenset(footprint)
        for physical in footprint:
            integer(physical, 0, 0x1FFFFF)
        b = self.client.call('status')
        self.persist('preflight-raw', dict(before=a, after=b, ram=memory.hex(),
                     source=copy.deepcopy(epoch), footprint=sorted(footprint)))
        self.observation.validate_paused_observation(a, b)
        require(b['paused'] is True and b['local_paused'] is False, 'Network paused boundary required')
        window = epoch.get('live', {}).get('window', {})
        for key, value in (('current_frame', b['frame']), ('current_ticks', b['ticks']),
                           ('current_native_steps', b['host']['native_steps']),
                           ('current_interpreter_steps', b['host']['interpreter_steps'])):
            require(same(window.get(key), value), 'Live source epoch differs from paused BEFORE status')
        cpu, debug = b['host']['cpu'], b['host']['debug_memory']
        require(debug['write_enabled'] is True, 'Explicit RAM write opt-in required')
        pc = integer(b['host']['pc'], 0, 65535)
        mpr = cpu['mpr']
        require(type(mpr) is list and len(mpr) == 8, 'All eight MPRs required')
        for value in mpr:
            integer(value, 0, 255)
        physical = [(mpr[((pc + i) & 65535) >> 13] << 13) | ((pc + i) & 8191) for i in range(7)]
        require(type(cpu['instruction_physical']) is list and len(cpu['instruction_physical']) == 7,
                'Seven physical fetch bytes required')
        for value in cpu['instruction_physical']:
            integer(value, 0, 0x1FFFFF)
        integer(cpu['physical_pc'], 0, 0x1FFFFF)
        require(cpu['instruction_physical'] == physical and cpu['physical_pc'] == physical[0],
                'Logical PC/MPR source mapping differs')
        raw, generations = cpu['instruction_bytes'], cpu['instruction_generations']
        require(type(raw) is list and type(generations) is list and len(raw) == len(generations) == 7,
                'Seven fetched bytes and generations required')
        for p, byte in zip(physical, raw):
            integer(byte, 0, 255)
            if 0xF8 <= p >> 13 <= 0xFB:
                require(memory[p & 8191] == byte, 'Fetched byte differs from complete backing')
        protected = footprint | frozenset(physical)
        for p in range(address, address + len(data)):
            require(not any(((bank << 13) | (p & 8191)) in protected for bank in range(0xF8, 0xFC)),
                    'Submitted byte aliases original/live/current code')
        offset = address - BASE
        require(memory[offset:offset + len(expected)] == expected, 'Fresh expected literal differs')
        changed = sum(x != y for x, y in zip(expected, data))
        integer(debug['write_requests'], 0, U64 - 1)
        integer(debug['bytes_changed'], 0, U64 - changed)
        bank_generations = {}
        for p, generation in zip(physical, generations):
            integer(generation, 0, U64 - changed if 0xF8 <= p >> 13 <= 0xFB else U64)
            require(p >> 13 not in bank_generations or bank_generations[p >> 13] == generation,
                    'Same fetched bank reports inconsistent generations')
            bank_generations[p >> 13] = generation
        policy = self.authorize(address, expected, data, copy.deepcopy(b), memory, footprint)
        require(type(policy) is dict and bool(policy), 'Fresh verified title authority receipt required')
        identity = integer(self.client._next_id, 1, (1 << 53) - 1)
        require(identity > b['id'], 'Next request must follow paused status')
        request = dict(id=identity, cmd='write_memory', address=address, expected=expected.hex(), data=data.hex())
        self.persist('intent', dict(request=request, policy=copy.deepcopy(policy), source=copy.deepcopy(epoch)))
        ack = self.client.write_memory(address, data, expected)  # Exactly once; no exception retry.
        self.persist('ack', copy.deepcopy(ack))
        after_memory = self.ram()
        footprint_after, epoch_after = self.source_snapshot()
        c = self.client.call('status')
        self.persist('after-raw', dict(after=c, ram=after_memory.hex(), source=copy.deepcopy(epoch_after)))
        require(type(footprint_after) in (set, frozenset), 'Complete postwrite source footprint required')
        for value in footprint_after:
            integer(value, 0, 0x1FFFFF)
        require(same(epoch_after, epoch) and frozenset(footprint_after) == footprint,
                'Paused source epoch changed')
        proof = self.writes.validate_paused_write(b, c, request=request, acknowledgement=ack,
                    memory_before=memory, memory_after=after_memory,
                    profile=self.writes.WORK_RAM_MIRRORS, code_footprint=footprint)
        self.persist('proof', proof)
        return proof
