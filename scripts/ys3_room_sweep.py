"""Bounded assisted room transitions and cheap discovery measurements.

The caller authenticates package, source guards and room catalogue. No game
code is patched. Entry settlement is separate from native qualification.
"""
from __future__ import annotations

import random

RAM = 0x1F0000
BOUNDARY = 0x4A6A
SCHEDULER = 0x4809
SETTLED = 0x735F


def require(value, message):
    if not value:
        raise ValueError(message)


def cpu_seed(status):
    cpu = status['host']['cpu']
    return status['host']['pc'].to_bytes(2, 'little') + bytes(
        [cpu[k] for k in ('a', 'x', 'y', 'sp', 'p')] + cpu['mpr'])


def paused(status):
    require(status['paused'] and not any(status['host']['buttons']), 'Neutral paused guest required')


def fresh_origin(status):
    """Refuse inherited dialogue/resource state from earlier discovery cases."""
    paused(status)
    checkpoint = status['host'].get('checkpoint', {})
    require(checkpoint.get('resumed') is True, 'Fresh restored checkpoint process required')
    window = checkpoint.get('window', {})
    require(all(window.get(field) == 0 for field in ('ticks', 'native_steps', 'interpreter_steps')),
            'One room per fresh process; inherited execution is refused')
    origin = checkpoint.get('origin', {})
    require(status['frame'] == origin.get('frame') and status['ticks'] == origin.get('ticks') and
            all(status['host'][field] == origin.get(field) for field in ('native_steps', 'interpreter_steps')),
            'Restored origin counters differ from the current guest')


def room_state(ram):
    require(type(ram) is bytes and len(ram) == 8192, 'Exact WRAM required')
    return dict(area=ram[0x7C], entrance=ram[0x7D], file=ram[0xF9C],
                transitioning=bool(ram[0x25] & 8), hp=ram[0xD18], maximum_hp=ram[0xD1E])


def call_frame(status):
    """Use free stack below the existing main-loop frame; never discard it."""
    paused(status)
    cpu = status['host']['cpu']
    require(status['host']['pc'] == BOUNDARY and cpu['mpr'][1:3] == [0xF8, 0x80],
            'Original main-loop boundary/mapping required')
    require(16 <= cpu['sp'] <= 255, 'Insufficient verified stack headroom')
    require(not cpu['p'] & 8, 'Decimal mode must be clear at the main loop')
    old = cpu_seed(status)
    new = SCHEDULER.to_bytes(2, 'little') + old[2:5] + bytes([cpu['sp'] - 2]) + old[6:]
    return dict(address=RAM + 0x100 + cpu['sp'] - 1,
                data=(BOUNDARY - 1).to_bytes(2, 'little'), expected_cpu=old, data_cpu=new)


def check_data_write(address, data, protected):
    require(type(data) is bytes and data and RAM <= address and address + len(data) <= RAM + 8192,
            'Canonical WRAM write required')
    offsets = range(address - RAM, address - RAM + len(data))
    require(not any((bank << 13) + offset in protected for bank in range(0xF8, 0xFC) for offset in offsets),
            'Data assist aliases captured or compiled code')


def guarded_write(client, address, data, protected):
    check_data_write(address, data, protected)
    expected = client.read_memory(address, len(data))
    if data != expected:
        client.write_memory(address, data, expected)
        require(client.read_memory(address, len(data)) == data, 'Assist readback differs')
    return dict(address=address, expected=expected.hex(), data=data.hex())


def source_guard(client, guards):
    require(type(guards) is list and len(guards) >= 4, 'Authenticated transition source guards required')
    for row in guards:
        require(len(row['mpr']) == 8 and len(row['physical']) == len(row['data']) > 0,
                'Complete source identity required')
        for offset, (physical, value) in enumerate(zip(row['physical'], row['data'])):
            pc = (row['pc'] + offset) & 65535
            require(physical == (row['mpr'][pc >> 13] << 13) + (pc & 8191), 'Source mapping differs')
            require(client.read_memory(physical, 1) == bytes([value]), 'Original transition code changed')
    require({BOUNDARY, SCHEDULER, 0x5646, SETTLED} <= {row['pc'] for row in guards},
            'Main-loop, scheduler and settle source guards required')


def delta(before, after):
    result = {}
    for field in ('native_steps', 'interpreter_steps'):
        result[field] = after['host'][field] - before['host'][field]
        require(result[field] >= 0, 'Retirement counters moved backwards')
    return result


def warp(client, area, file_id, entrance, guards, protected, *, reference=False):
    require(type(area) is int and 0 <= area < 136, 'Decoded area selector required')
    require(type(file_id) is int and 0 <= file_id <= 255, 'Decoded file ID required')
    require(type(entrance) is int and 0 <= entrance < 128, 'Explicit nonnegative entrance required')
    start = client.call('status'); fresh_origin(start)
    mapping = start['host']['cpu']['mpr']
    boundary = client.run_until(BOUNDARY, mapping, instructions=5000000, ticks=100000000,
                                mpr_mask=4, reference=reference, timeout=60)
    paused(boundary)
    source_guard(client, guards)
    before_ram = client.read_memory_block(RAM, 8192)
    require(not room_state(before_ram)['transitioning'], 'An existing room transition is pending')
    frame = call_frame(boundary)
    check_data_write(RAM + 0x7C, bytes([area, entrance]), protected)
    check_data_write(frame['address'], frame['data'], protected)
    writes = [guarded_write(client, RAM + 0x7C, bytes([area, entrance]), protected),
              guarded_write(client, frame['address'], frame['data'], protected)]
    client.write_cpu(frame['expected_cpu'], frame['data_cpu'])
    queued = client.run_until(BOUNDARY, boundary['host']['cpu']['mpr'], instructions=100000,
                              ticks=10000000, mpr_mask=255, reference=reference, timeout=30)
    require(queued['host']['cpu']['sp'] == boundary['host']['cpu']['sp'], 'Scheduler return stack differs')
    require(room_state(client.read_memory_block(RAM, 8192))['transitioning'], 'Transition was not queued')
    target_mapping = queued['host']['cpu']['mpr'].copy(); target_mapping[3] = 0x81
    settled = client.run_until(SETTLED, target_mapping, instructions=30000000, ticks=500000000,
                               mpr_mask=12, reference=reference, timeout=120)
    ram = client.read_memory_block(RAM, 8192)
    state = room_state(ram)
    require(state['area'] == area and state['file'] == file_id and not state['transitioning'] and ram[0x9B] == 0,
            'Deferred original room initialization did not settle')
    return dict(area=area, file_id=file_id, entrance=entrance, entry_verified=True,
                native_qualified=False, before=start, boundary=boundary, queued=queued,
                settled=settled, room=state, writes=writes,
                cpu_assist=dict(expected=frame['expected_cpu'].hex(), data=frame['data_cpu'].hex()),
                retirements=delta(start, settled))


def input_plan(seed, frames):
    require(type(seed) is int and 0 <= seed < 2**32, '32-bit seed required')
    require(type(frames) is int and 1 <= frames <= 1800, 'Exercise bound is 1..1800 frames')
    rng = random.Random(seed)
    # PCE I/II and cardinal directions. Menu/Run is excluded from random holds:
    # it can strand a room in a paused menu and hide the gameplay handlers.
    masks = [0x20, 0x80, 0x21, 0x81, 0x22, 0x82, 0, 1, 2]
    result = []
    while frames:
        length = min(60, frames)
        mask = masks[len(result)] if len(result) < 6 else rng.choice(masks)
        result.append((mask, length)); frames -= length
    return result


def exercise(client, seed, frames, protected, *, reference=False):
    start = client.call('status'); paused(start)
    initial_area = room_state(client.read_memory_block(RAM, 8192))['area']
    steps = []; dead = False; left_area = False
    try:
        for mask, count in input_plan(seed, frames):
            state = room_state(client.read_memory_block(RAM, 8192))
            if state['hp'] == 0:
                dead = True; break
            writes = []
            if 0 < state['hp'] < 60 and state['maximum_hp'] >= 90:
                writes.append(guarded_write(client, RAM + 0xD18, bytes([90]), protected))
            client.call('set_input', port=0, mask=mask)
            status = client.advance(count, reference=reference)
            steps.append(dict(mask=mask, frames=count, writes=writes,
                              room=room_state(client.read_memory_block(RAM, 8192))))
            if steps[-1]['room']['hp'] == 0:
                dead = True; break
            if steps[-1]['room']['area'] != initial_area or steps[-1]['room']['transitioning']:
                left_area = True; break
    finally:
        client.call('set_input', port=0, mask=0)
    end = client.call('status'); paused(end)
    return dict(seed=seed, requested_frames=frames, completed_frames=sum(s['frames'] for s in steps),
                dead=dead, left_area=left_area, steps=steps, final=end, retirements=delta(start, end))
