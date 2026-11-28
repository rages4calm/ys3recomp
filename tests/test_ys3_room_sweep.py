"""Synthetic CPU, RAM and deferred-task fixtures; no retail game bytes."""
import copy
import unittest

from scripts import ys3_room_sweep as sweep


def status(pc=sweep.BOUNDARY, sp=0xEF, p=0x45):
    return dict(paused=True, frame=10, ticks=500, host=dict(pc=pc, buttons=[0] * 5,
        native_steps=100, interpreter_steps=20,
        checkpoint=dict(resumed=True, origin=dict(frame=10, ticks=500, native_steps=100, interpreter_steps=20),
                        window=dict(ticks=0, native_steps=0, interpreter_steps=0)),
        cpu=dict(a=0x13, x=0x27, y=0x39, sp=sp, p=p,
                 mpr=[0xFF, 0xF8, 0x80, 0x85, 0x83, 0x84, 0x87, 0])))


def guards():
    result = []
    for n, pc in enumerate((sweep.BOUNDARY, sweep.SCHEDULER, 0x5646, sweep.SETTLED)):
        mpr = status()['host']['cpu']['mpr'].copy()
        if pc == sweep.SETTLED:
            mpr[3] = 0x81
        result.append(dict(pc=pc, mpr=mpr,
            physical=[(mpr[pc >> 13] << 13) + (pc & 8191)], data=[0x10 + n]))
    return result


class FakeClient:
    """Models a scheduler that returns before its deferred room task runs."""
    def __init__(self, failure=None):
        self.status = status(pc=0x5000)
        self.ram = bytearray(8192)
        self.ram[0x7C] = 42
        self.ram[0xF9C] = 28
        self.ram[0xD18] = 82
        self.ram[0xD1E] = 100
        self.source = {r['physical'][0]: r['data'][0] for r in guards()}
        self.failure = failure
        self.windows = []
        self.writes = []
        self.cpu_writes = []
        self.frames = []

    def call(self, command, **kwargs):
        if command == 'status':
            return copy.deepcopy(self.status)
        if command == 'set_input':
            self.status['host']['buttons'][kwargs['port']] = kwargs['mask']
            return dict(ok=True)
        raise AssertionError(command)

    def read_memory(self, address, length):
        if sweep.RAM <= address and address + length <= sweep.RAM + 8192:
            return bytes(self.ram[address - sweep.RAM:address - sweep.RAM + length])
        return bytes(self.source[address + i] for i in range(length))

    def read_memory_block(self, address, length):
        return self.read_memory(address, length)

    def write_memory(self, address, data, expected):
        assert self.read_memory(address, len(data)) == expected
        self.writes.append((address, data, expected))
        self.ram[address - sweep.RAM:address - sweep.RAM + len(data)] = data

    def write_cpu(self, expected, data):
        assert sweep.cpu_seed(self.status) == expected
        self.cpu_writes.append((expected, data))
        self.status['host']['pc'] = int.from_bytes(data[:2], 'little')
        cpu = self.status['host']['cpu']
        for index, field in enumerate(('a', 'x', 'y', 'sp', 'p'), 2):
            cpu[field] = data[index]
        cpu['mpr'] = list(data[7:])

    def run_until(self, pc, mpr, **kwargs):
        self.windows.append((pc, list(mpr), kwargs))
        self.status['host']['native_steps'] += 10
        if len(self.windows) == 1:
            self.status['host']['pc'] = sweep.BOUNDARY
        elif len(self.windows) == 2:
            assert self.status['host']['pc'] == sweep.SCHEDULER
            self.status['host']['pc'] = sweep.BOUNDARY
            self.status['host']['cpu']['sp'] += 2
            if self.failure == 'stack':
                self.status['host']['cpu']['sp'] -= 1
            if self.failure != 'queue':
                self.ram[0x25] |= 8
        elif len(self.windows) == 3:
            assert self.ram[0x25] & 8
            self.status['host']['pc'] = sweep.SETTLED
            self.status['host']['cpu']['mpr'][3] = 0x81
            self.ram[0xF9C] = 24
            self.ram[0x25] &= ~8
            self.ram[0x9B] = 0
            if self.failure == 'file':
                self.ram[0xF9C] = 25
            if self.failure == 'flag':
                self.ram[0x25] |= 8
            if self.failure == 'area':
                self.ram[0x7C] = 22
            if self.failure == 'busy':
                self.ram[0x9B] = 1
        else:
            raise AssertionError('Unexpected extra execution window')
        return self.call('status')

    def advance(self, frames, **kwargs):
        self.frames.append((frames, kwargs))
        self.status['host']['native_steps'] += frames * 3
        if self.failure == 'death':
            self.ram[0xD18] = 0
        if self.failure == 'leave':
            self.ram[0x7C] += 1
        if self.failure == 'transition':
            self.ram[0x25] |= 8
        if self.failure == 'advance':
            raise RuntimeError('Synthetic execution failure')
        return self.call('status')


class RoomSweepTests(unittest.TestCase):
    def test_fresh_origin_refuses_reused_or_rebound_guest_before_any_controls(self):
        variants = []
        cold = status(); cold['host']['checkpoint']['resumed'] = False; variants.append(cold)
        for field in ('ticks', 'native_steps', 'interpreter_steps'):
            used = status(); used['host']['checkpoint']['window'][field] = 1; variants.append(used)
        wrong_frame = status(); wrong_frame['frame'] += 1; variants.append(wrong_frame)
        wrong_clock = status(); wrong_clock['ticks'] += 1; variants.append(wrong_clock)
        wrong_count = status(); wrong_count['host']['native_steps'] += 1; variants.append(wrong_count)
        for bad in variants:
            with self.subTest(bad=bad):
                client = FakeClient(); client.status = bad
                with self.assertRaises(ValueError):
                    sweep.warp(client, 21, 24, 0, guards(), set())
                self.assertEqual(client.windows, [])
                self.assertEqual(client.writes, [])
                self.assertEqual(client.cpu_writes, [])

    def test_call_frame_preserves_live_context_and_uses_only_free_stack(self):
        before = status(sp=0xC3, p=0xC5)
        unchanged = copy.deepcopy(before)
        frame = sweep.call_frame(before)
        self.assertEqual(before, unchanged)
        self.assertEqual(frame['address'], sweep.RAM + 0x1C2)
        self.assertEqual(int.from_bytes(frame['data'], 'little') + 1, sweep.BOUNDARY)
        self.assertEqual(frame['expected_cpu'], sweep.cpu_seed(before))
        seeded = frame['data_cpu']
        self.assertEqual(int.from_bytes(seeded[:2], 'little'), sweep.SCHEDULER)
        self.assertEqual(seeded[2:5], bytes([0x13, 0x27, 0x39]))
        self.assertEqual(seeded[5], 0xC1)
        self.assertEqual(seeded[6:], frame['expected_cpu'][6:])

    def test_call_frame_refuses_unsafe_or_unsettled_context(self):
        variants = [status(sp=15), status(p=8), status(pc=0x4A67)]
        wrong_bank = status(); wrong_bank['host']['cpu']['mpr'][2] = 0x81
        variants.append(wrong_bank)
        held = status(); held['host']['buttons'][0] = 1; variants.append(held)
        running = status(); running['paused'] = False; variants.append(running)
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                sweep.call_frame(bad)

    def test_data_assist_refuses_every_work_ram_alias_and_noncanonical_range(self):
        for bank in range(0xF8, 0xFC):
            with self.subTest(bank=bank), self.assertRaises(ValueError):
                sweep.check_data_write(sweep.RAM + 0x7C, b'\x01\x02', {(bank << 13) + 0x7D})
        for address, data in ((sweep.RAM - 1, b'\0'), (sweep.RAM + 8191, b'\0\0'),
                              (sweep.RAM, b''), (sweep.RAM, bytearray(b'\0'))):
            with self.subTest(address=address), self.assertRaises(ValueError):
                sweep.check_data_write(address, data, set())
        sweep.check_data_write(sweep.RAM + 0x7C, b'\x01\x02', {sweep.RAM + 0x7B})

    def test_guarded_write_uses_expected_bytes_and_omits_noop(self):
        client = FakeClient()
        receipt = sweep.guarded_write(client, sweep.RAM + 0x7C, b'\x15\0', set())
        self.assertEqual(receipt, dict(address=sweep.RAM + 0x7C, expected='2a00', data='1500'))
        self.assertEqual(len(client.writes), 1)
        sweep.guarded_write(client, sweep.RAM + 0x7C, b'\x15\0', set())
        self.assertEqual(len(client.writes), 1)

    def test_source_guard_requires_all_sites_exact_bytes_and_logical_mapping(self):
        sweep.source_guard(FakeClient(), guards())
        variants = [guards()[:-1]]
        wrong_mapping = guards(); wrong_mapping[0]['physical'][0] += 1; variants.append(wrong_mapping)
        wrong_bytes = guards(); wrong_bytes[0]['data'][0] ^= 1; variants.append(wrong_bytes)
        missing = guards(); missing[0] = copy.deepcopy(missing[1]); variants.append(missing)
        truncated = guards(); truncated[0]['mpr'].pop(); variants.append(truncated)
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                sweep.source_guard(FakeClient(), bad)

    def test_warp_distinguishes_queue_return_from_deferred_settlement(self):
        client = FakeClient()
        result = sweep.warp(client, 21, 24, 0, guards(), set(), reference=True)
        self.assertTrue(result['entry_verified'])
        self.assertFalse(result['native_qualified'])
        self.assertEqual(result['room']['area'], 21)
        self.assertEqual(result['room']['file'], 24)
        self.assertEqual(result['retirements'], dict(native_steps=30, interpreter_steps=0))
        self.assertEqual([r[0] for r in client.windows], [sweep.BOUNDARY, sweep.BOUNDARY, sweep.SETTLED])
        self.assertEqual(client.windows[1][2]['mpr_mask'], 255)
        self.assertEqual(client.windows[2][1][3], 0x81)
        self.assertTrue(all(r[2]['reference'] for r in client.windows))
        self.assertEqual(len(client.cpu_writes), 1)

    def test_warp_refuses_queue_failure_bad_stack_and_incomplete_room(self):
        for failure in ('stack', 'queue', 'file', 'flag', 'area', 'busy'):
            client = FakeClient(failure)
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                sweep.warp(client, 21, 24, 0, guards(), set())
            self.assertLessEqual(len(client.windows), 3)

    def test_warp_refuses_pending_transition_before_editing(self):
        client = FakeClient(); client.ram[0x25] = 8
        with self.assertRaises(ValueError):
            sweep.warp(client, 21, 24, 0, guards(), set())
        self.assertEqual(client.writes, [])
        self.assertEqual(client.cpu_writes, [])

    def test_protected_stack_preflight_prevents_partial_selector_edits(self):
        client = FakeClient()
        original_selectors = bytes(client.ram[0x7C:0x7E])
        # Protect the second return-frame byte through a noncanonical mirror.
        protected = {(0xFA << 13) + 0x100 + client.status['host']['cpu']['sp']}
        with self.assertRaisesRegex(ValueError, 'aliases'):
            sweep.warp(client, 21, 24, 0, guards(), protected)
        self.assertEqual(bytes(client.ram[0x7C:0x7E]), original_selectors)
        self.assertEqual(client.writes, [])
        self.assertEqual(client.cpu_writes, [])
        self.assertEqual(len(client.windows), 1)

    def test_warp_validates_selectors_before_any_execution(self):
        for area, file_id, entrance in ((136, 24, 0), (-1, 24, 0), (True, 24, 0),
                                       (21, 256, 0), (21, 24, -1), (21, 24, 128)):
            client = FakeClient()
            with self.subTest(case=(area, file_id, entrance)), self.assertRaises(ValueError):
                sweep.warp(client, area, file_id, entrance, guards(), set())
            self.assertEqual(client.windows, [])

    def test_seeded_input_is_repeatable_finite_and_excludes_pause_buttons(self):
        first = sweep.input_plan(1234, 1800)
        self.assertEqual(first, sweep.input_plan(1234, 1800))
        self.assertNotEqual(first, sweep.input_plan(1235, 1800))
        self.assertEqual(sum(count for _, count in first), 1800)
        self.assertTrue(all(1 <= count <= 60 and not mask & 0xC for mask, count in first))
        self.assertEqual(sum(count for _, count in sweep.input_plan(0, 61)), 61)
        for seed, frames in ((0, 0), (0, 1801), (-1, 60), (2**32, 60), (True, 60)):
            with self.assertRaises(ValueError):
                sweep.input_plan(seed, frames)

    def test_delta_retains_each_tier_and_refuses_counter_rewind(self):
        before = status(); after = copy.deepcopy(before)
        after['host']['native_steps'] += 15
        after['host']['interpreter_steps'] += 3
        self.assertEqual(sweep.delta(before, after), dict(native_steps=15, interpreter_steps=3))
        after['host']['interpreter_steps'] = 19
        with self.assertRaises(ValueError):
            sweep.delta(before, after)

    def test_exercise_refills_only_living_hp_and_clears_input(self):
        client = FakeClient(); client.ram[0xD18] = 40
        result = sweep.exercise(client, 1, 121, set())
        self.assertEqual(result['completed_frames'], 121)
        self.assertFalse(result['dead'])
        self.assertEqual(client.ram[0xD18], 90)
        self.assertEqual(client.status['host']['buttons'], [0] * 5)
        self.assertEqual(len(client.writes), 1)
        self.assertEqual(result['retirements']['native_steps'], 363)

    def test_exercise_reports_death_and_never_revives_dead_player(self):
        client = FakeClient('death')
        result = sweep.exercise(client, 1, 1800, set())
        self.assertTrue(result['dead'])
        self.assertEqual(result['completed_frames'], 60)
        self.assertEqual(client.writes, [])
        self.assertEqual(client.status['host']['buttons'], [0] * 5)
        client = FakeClient(); client.ram[0xD18] = 0
        result = sweep.exercise(client, 1, 60, set())
        self.assertTrue(result['dead'])
        self.assertEqual(result['completed_frames'], 0)
        self.assertEqual(client.frames, [])

    def test_exercise_stops_after_room_exit_or_deferred_transition_without_death(self):
        for failure in ('leave', 'transition'):
            client = FakeClient(failure)
            with self.subTest(failure=failure):
                result = sweep.exercise(client, 1, 1800, set())
                self.assertTrue(result['left_area'])
                self.assertFalse(result['dead'])
                self.assertEqual(result['completed_frames'], 60)
                self.assertEqual(len(client.frames), 1)
                self.assertEqual(len(result['steps']), 1)
                self.assertEqual(client.status['host']['buttons'], [0] * 5)
                if failure == 'leave':
                    self.assertEqual(result['steps'][0]['room']['area'], 43)
                    self.assertFalse(result['steps'][0]['room']['transitioning'])
                else:
                    self.assertEqual(result['steps'][0]['room']['area'], 42)
                    self.assertTrue(result['steps'][0]['room']['transitioning'])

    def test_exercise_releases_held_controls_after_execution_failure(self):
        client = FakeClient('advance')
        with self.assertRaisesRegex(RuntimeError, 'Synthetic execution failure'):
            sweep.exercise(client, 1, 60, set())
        self.assertEqual(client.status['host']['buttons'], [0] * 5)


if __name__ == '__main__':
    unittest.main()
