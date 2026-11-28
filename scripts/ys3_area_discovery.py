"""Analyze private loader evidence without running or declaring game code.

Capture rows remain historical observations. Snapshot matches require the full
MPR mapping and every decoded source byte; conflicting epochs are never joined
into a synthetic memory image. Reports contain original bytes and stay private.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT))
from scripts.merge_observations import load_capture_api
from scripts.verify_tool import verify

PHYSICAL_BYTES = 1 << 21
# Only directly stored regions supported by this snapshot format. In particular,
# F9..FB WRAM mirrors and device registers need a separate canonical bus reader.
SOURCE_STORAGE_RANGES = ((0, 0x40000), (0x100000, 0x10000), (0x1F0000, 0x2000))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, maximum, label):
    require(type(value) is int and 0 <= value <= maximum, label + ' is out of range')
    return value


def mapping(values):
    require(isinstance(values, (list, tuple)) and len(values) == 8, 'Eight MPR bytes required')
    return tuple(integer(v, 255, 'MPR') for v in values)


def normalize_known_ranges(ranges):
    require(isinstance(ranges, (list, tuple)) and 1 <= len(ranges) <= 64,
            'Supply 1..64 explicit known physical ranges')
    intervals = []
    for item in ranges:
        require(isinstance(item, (list, tuple)) and len(item) == 2, 'Known range requires base and length')
        start, length = item
        integer(start, PHYSICAL_BYTES - 1, 'Known physical base')
        integer(length, PHYSICAL_BYTES, 'Known physical length')
        require(length > 0 and start + length <= PHYSICAL_BYTES, 'Known physical range exceeds snapshot')
        require(any(base <= start and start + length <= base + size for base, size in SOURCE_STORAGE_RANGES),
                'Known source range must be canonical BIOS, CD RAM or F8 WRAM; mirrors/device holes are unsupported')
        intervals.append((start, start + length))
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return [(start, end - start) for start, end in merged]


def address_known(address, ranges):
    return any(start <= address < start + length for start, length in ranges)


def identity(row):
    return row['pc'], tuple(row['mpr']), tuple(row['physical']), tuple(row['data'])


def source_fields(row):
    return dict(pc=row['pc'], mpr=list(row['mpr']), physical=list(row['physical']), data=list(row['data']))


def historical_hits(row, capture_index):
    native = integer(row['native_hits'], (1 << 64) - 1, 'Native historical hits')
    interpreted = integer(row['interpreted_hits'], (1 << 64) - 1, 'Interpreted historical hits')
    require(0 < native + interpreted < 1 << 64, 'Bounded positive historical hits required')
    return dict(capture_index=capture_index, native_hits=native, interpreted_hits=interpreted)


def decoded_row(row, isa):
    """Decode one intact capture row, never bytes borrowed from another row."""
    pc = integer(row['pc'], 65535, 'PC'); mpr = mapping(row['mpr'])
    data = tuple(integer(v, 255, 'Source byte') for v in row['data'])
    addresses = tuple(integer(v, PHYSICAL_BYTES - 1, 'Physical source') for v in row['physical'])
    require(1 <= len(data) <= 7 and len(addresses) == len(data), 'Invalid source extent')
    def read(at):
        offset = (at - pc) & 65535
        require(offset < len(data), 'Truncated captured instruction')
        return data[offset]
    ins = isa.decode(read, pc, mpr)
    require(ins.data == data and ins.physical == addresses, 'Source mapping or decoder length differs')
    return ins


def select_snapshot_identities(captures, memory, mpr, isa, *, known_ranges):
    """Select full identities matching ONE explicitly supplied physical epoch.

    Counts remain per capture, since inputs may overlap. No historical retirement
    is attributed to a new guest or to execution at the supplied snapshot.
    """
    require(type(memory) is bytes and len(memory) == PHYSICAL_BYTES, 'Exact 2 MiB physical snapshot required')
    mpr = mapping(mpr); known_ranges = normalize_known_ranges(known_ranges)
    selected = {}; unresolved = {}; other_mpr = set()
    for number, capture in enumerate(captures):
        for row in capture['observations']:
            ins = decoded_row(row, isa); key = identity(row)
            if tuple(row['mpr']) != mpr:
                other_mpr.add(key)
                continue
            hits = historical_hits(row, number)
            unavailable = [at for at in ins.physical if not address_known(at, known_ranges)]
            matching = not unavailable and all(memory[at] == value for at, value in zip(ins.physical, ins.data))
            destination = selected if matching else unresolved
            if key not in destination:
                destination[key] = source_fields(row) | dict(capture_hits=[])
                if not matching:
                    destination[key]['reason'] = ('Instruction bytes outside known physical storage ranges'
                                                  if unavailable else 'Source bytes differ from the supplied physical epoch')
                    if unavailable:
                        destination[key]['unavailable_physical'] = unavailable
            destination[key]['capture_hits'].append(hits)
    order = lambda item: (item['pc'], item['mpr'], item['physical'], item['data'])
    return dict(snapshot_consistent=sorted(selected.values(), key=order),
                unresolved_variants=sorted(unresolved.values(), key=order),
                other_mpr_identities=len(other_mpr), historical_counts_are_per_capture=True)


def group_service_callers(captures, isa, targets=None):
    """Group direct JSR/JMP callers by target and complete original identity."""
    if targets is not None:
        targets = frozenset(integer(t, 65535, 'Service target') for t in targets)
    groups = {}; indirect = {}
    for number, capture in enumerate(captures):
        for row in capture['observations']:
            ins = decoded_row(row, isa)
            if ins.mnemonic not in ('JSR', 'JMP'):
                continue
            hits = historical_hits(row, number)
            if ins.target is None:
                key = identity(row)
                if key not in indirect:
                    indirect[key] = source_fields(row) | dict(mnemonic=ins.mnemonic, mode=ins.mode,
                        reason='Indirect transfer target requires actual runtime evidence', capture_hits=[])
                indirect[key]['capture_hits'].append(hits)
                continue
            if targets is not None and ins.target not in targets:
                continue
            key = (ins.target, *identity(row))
            if key not in groups:
                groups[key] = source_fields(row) | dict(target=ins.target, mnemonic=ins.mnemonic, capture_hits=[])
            groups[key]['capture_hits'].append(hits)
    return dict(direct_callers=sorted(groups.values(), key=lambda r: (r['target'], r['pc'], r['mpr'], r['data'])),
                unresolved_indirect_transfers=sorted(indirect.values(), key=lambda r: (r['pc'], r['mpr'], r['data'])))


def disassemble_snapshot(memory, mpr, requests, isa, *, known_ranges):
    """Bounded linear listings at explicit logical PCs, not code discovery."""
    require(type(memory) is bytes and len(memory) == PHYSICAL_BYTES, 'Exact 2 MiB physical snapshot required')
    mpr = mapping(mpr); known_ranges = normalize_known_ranges(known_ranges)
    require(len(requests) <= 16, 'At most sixteen explicit disassembly ranges')
    result = []
    for pc, count in requests:
        integer(pc, 65535, 'Disassembly PC')
        require(type(count) is int and 1 <= count <= 256, 'Disassembly count must be 1..256')
        rows = []
        def read(at):
            physical = isa.physical(at, mpr)
            require(address_known(physical, known_ranges), 'Disassembly fetch crosses an unknown physical range')
            return memory[physical]
        for _ in range(count):
            ins = isa.decode(read, pc, mpr)
            rows.append(ins.report() | dict(mpr=list(mpr), listing=isa.listing(ins)))
            pc = ins.next_pc
        result.append(dict(instructions=rows, scope='Explicit linear disassembly; not an entry/root declaration'))
    return result


AREA_LAYOUT_FIELDS = frozenset(('format', 'file_table_physical', 'file_count',
    'area_file_table_physical', 'area_room_table_physical', 'area_count',
    'track_base_physical', 'sector_stride', 'sector_bias', 'code_destination', 'transfer_mpr'))


def decode_area_catalogue(memory, known_ranges, layout):
    """Decode an explicit table layout, without claiming a playable entry.

    Transfer MPRs describe the caller-supplied load recipe. They do not establish
    execution mappings, code roots or the initialized state of an area.
    """
    require(type(memory) is bytes and len(memory) == PHYSICAL_BYTES, 'Exact 2 MiB physical snapshot required')
    ranges = normalize_known_ranges(known_ranges)
    require(type(layout) is dict and set(layout) == AREA_LAYOUT_FIELDS, 'Exact ys3-area-layout-1 fields required')
    require(layout['format'] == 'ys3-area-layout-1', 'Unsupported area-layout format')
    file_count = integer(layout['file_count'], 256, 'File count')
    area_count = integer(layout['area_count'], 256, 'Area count')
    require(file_count > 0 and area_count > 0, 'File/area counts must be 1..256')
    stride = integer(layout['sector_stride'], 65535, 'Sector stride')
    require(stride > 0, 'Positive sector stride required')
    bias = integer(layout['sector_bias'], 0xFFFFFF, 'Sector bias')
    destination = integer(layout['code_destination'], PHYSICAL_BYTES - 1, 'Code destination')
    require(address_known(destination, ranges), 'Code destination must start in known canonical storage')
    transfer = mapping(layout['transfer_mpr'])
    spans = [('file_table_physical', file_count), ('area_file_table_physical', area_count),
             ('area_room_table_physical', area_count), ('track_base_physical', 3)]
    occupied = []
    for field, size in spans:
        start = integer(layout[field], PHYSICAL_BYTES - 1, field)
        require(start + size <= PHYSICAL_BYTES and all(address_known(at, ranges) for at in range(start, start + size)),
                field + ' crosses unknown physical storage')
        require(not any(start < end and previous < start + size for previous, end in occupied),
                'Area/file/base table spans must not overlap')
        occupied.append((start, start + size))
    at = layout['track_base_physical']
    base = int.from_bytes(memory[at:at+3], 'big')
    files = []
    for file_id in range(file_count):
        count = memory[layout['file_table_physical'] + file_id]
        require(count <= 32 and count <= stride, 'Sector count must be zero or 1..32 and fit its file slot')
        lba = base + stride * file_id + bias
        require(lba <= 0xFFFFFF and lba + max(count - 1, 0) <= 0xFFFFFF, 'File sector extent exceeds 24-bit LBA')
        files.append(dict(file_id=file_id, lba=lba, sectors=count, hole=count == 0,
                          status='decoded-only', observed=False))
    areas = []
    for area_id in range(area_count):
        file_id = memory[layout['area_file_table_physical'] + area_id]
        require(file_id + 1 < file_count, 'Area code file or companion neighbor is outside file table')
        code, companion = files[file_id], files[file_id + 1]
        require(code['sectors'] > 0 and companion['sectors'] > 0, 'Area code/companion file points to a zero-length hole')
        areas.append(dict(area_id=area_id, descriptor_index=memory[layout['area_room_table_physical'] + area_id],
            code_file_id=file_id, code_lba=code['lba'], code_sectors=code['sectors'],
            companion_file_id=file_id + 1, companion_lba=companion['lba'], companion_sectors=companion['sectors'],
            companion_role='uninterpreted',
            code_destination=destination, transfer_mpr=list(transfer), execution_mpr=None,
            entry_roots=[], status='decoded-only', entry_verified=False, observed=False, native_qualified=False))
    return dict(format='ys3-area-catalogue-analysis-1', analysis_only=True, native_qualified=False,
        new_guest_retirements=0, declared_identities=0, track_base_lba=base,
        file_count=file_count, area_count=area_count, files=files, areas=areas,
        scope='Caller-described tables decoded from known snapshot bytes; companion file purpose and descriptor semantics are uninterpreted. Observed loads, transfer extent, execution roots and playable entry remain separate verification')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def private_path(path, *, existing=False):
    path = Path(path).absolute()
    require(path.resolve().is_relative_to((ROOT / '.local').resolve()), 'Original source reports and snapshots must stay under project .local/')
    for item in (path, *path.parents):
        require(not item.is_symlink() and not item.is_junction(), 'Linked private path refused')
        if item == ROOT:
            break
    return path.resolve(strict=existing)


def auto_int(value):
    try:
        return int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError('Use an explicit decimal or 0x-prefixed integer') from error


def mpr_arg(value):
    try:
        return mapping([auto_int(token) for token in value.split(',')])
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def range_arg(value):
    try:
        pc, count = value.split(':')
        pc, count = auto_int(pc), auto_int(count)
        integer(pc, 65535, 'Disassembly PC')
        require(1 <= count <= 256, 'Disassembly count must be 1..256')
        return pc, count
    except ValueError as error:
        raise argparse.ArgumentTypeError('Use PC:instruction-count, bounded to 1..256 instructions') from error


def physical_range_arg(value):
    try:
        base, length = value.split(':')
        return tuple(normalize_known_ranges([(auto_int(base), auto_int(length))])[0])
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool-root', type=Path, required=True)
    parser.add_argument('--capture', type=Path, action='append', required=True)
    parser.add_argument('--physical-memory', type=Path, required=True)
    parser.add_argument('--physical-memory-sha256', required=True)
    parser.add_argument('--physical-range', type=physical_range_arg, action='append', required=True,
                        help='Known canonical physical BASE:LENGTH; repeat for BIOS, CD RAM and F8 WRAM')
    parser.add_argument('--mpr', type=mpr_arg, required=True)
    parser.add_argument('--service', type=auto_int, action='append')
    parser.add_argument('--disassemble', type=range_arg, action='append', default=[])
    parser.add_argument('--area-layout', type=Path, help='Private numeric ys3-area-layout-1 table description')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        producer_files = [Path(__file__).resolve(), Path(__file__).with_name('merge_observations.py'),
                          Path(__file__).with_name('verify_tool.py'), ROOT / 'toolchain.json']
        producer_bindings = {str(path.resolve()): sha(path) for path in producer_files}
        require(1 <= len(args.capture) <= 64, 'Supply 1..64 explicit closed captures')
        require(re.fullmatch('[0-9a-f]{64}', args.physical_memory_sha256) is not None, 'Explicit full physical-memory SHA256 required')
        memory_path = private_path(args.physical_memory, existing=True)
        out = private_path(args.out); require(not out.exists(), 'Create-new output required')
        area_layout = None; layout_input = None
        if args.area_layout is not None:
            layout_path = private_path(args.area_layout, existing=True)
            require(layout_path.is_file() and layout_path.stat().st_size <= 16384, 'Bounded numeric area-layout file required')
            def unique_fields(pairs):
                result = {}
                for key, value in pairs:
                    require(key not in result, 'Duplicate area-layout field')
                    result[key] = value
                return result
            raw_layout = layout_path.read_bytes()
            area_layout = json.loads(raw_layout, object_pairs_hook=unique_fields,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite area-layout number')))
            layout_input = dict(path=str(layout_path), sha256=hashlib.sha256(raw_layout).hexdigest())
        require(memory_path.is_file() and memory_path.stat().st_size == PHYSICAL_BYTES, 'Exact 2 MiB physical snapshot required')
        require(sha(memory_path) == args.physical_memory_sha256, 'Physical snapshot hash differs')
        paths = [private_path(path, existing=True) for path in args.capture]
        require(len(set(paths)) == len(paths), 'Duplicate capture input')
        tool = args.tool_root.resolve(strict=True)
        pin = json.loads((ROOT / 'toolchain.json').read_bytes())['tool']
        verified = verify(tool, pin['revision'], pin['runtime_abi'])
        api = load_capture_api(tool)
        isa = importlib.import_module(api.__package__ + '.isa')
        project = importlib.import_module(api.__package__ + '.project')
        source = project.source_identity(tool)
        expected = {k: pin[k] for k in ('revision', 'source_sha256', 'source_files')}
        require(source == expected, 'Frozen SDK production source differs')
        captures = []; inputs = []
        for path in paths:
            cap, digest = api.load_capture(path)
            require(cap['complete'] and not cap['dropped_instructions'] and not cap['unreadable_instructions'], 'Complete lossless captures required')
            captures.append(cap)
            inputs.append(dict(path=str(path), sha256=digest, runtime_abi=cap['runtime_abi'],
                historical_retirements=cap['retired_instructions'],
                historical_native=sum(r['native_hits'] for r in cap['observations']),
                historical_interpreted=sum(r['interpreted_hits'] for r in cap['observations'])))
        memory = memory_path.read_bytes()
        require(hashlib.sha256(memory).hexdigest() == args.physical_memory_sha256, 'Snapshot changed while reading')
        known_ranges = normalize_known_ranges(args.physical_range)
        selection = select_snapshot_identities(captures, memory, args.mpr, isa, known_ranges=known_ranges)
        report = dict(schema='ys3-area-discovery-analysis-1', analysis_only=True, native_qualified=False,
            new_guest_retirements=0, declared_identities=0, tool=verified | dict(shared_source_identity=source),
            producer_input_sha256=producer_bindings,
            physical_epoch=dict(path=str(memory_path), sha256=args.physical_memory_sha256, mpr=list(args.mpr),
                known_ranges=[dict(base=start, length=length) for start, length in known_ranges],
                provenance_scope='Caller-authenticated snapshot bytes/MPR; checkpoint-to-snapshot extraction must be verified separately'),
            captures=inputs, **selection,
            historical_service_calls=group_service_callers(captures, isa, args.service),
            disassembly=disassemble_snapshot(memory, args.mpr, args.disassemble, isa, known_ranges=known_ranges))
        # Snapshot rows retain per-capture counts, rather than synthesizing totals.
        selected_keys = {identity(row) for row in selection['snapshot_consistent']}
        selected_captures = [dict(observations=[r for r in cap['observations'] if identity(r) in selected_keys]) for cap in captures]
        report['snapshot_service_calls'] = group_service_callers(selected_captures, isa, args.service)
        if area_layout is not None:
            report['area_layout_input'] = layout_input
            report['area_catalogue'] = decode_area_catalogue(memory, known_ranges, area_layout)
            require(sha(layout_input['path']) == layout_input['sha256'], 'Area layout changed during analysis')
        require(all(sha(row['path']) == row['sha256'] for row in inputs) and sha(memory_path) == args.physical_memory_sha256, 'Analysis input changed')
        require(project.source_identity(tool) == source and verify(tool, pin['revision'], pin['runtime_abi']) == verified, 'SDK changed during analysis')
        require(all(sha(path) == digest for path, digest in producer_bindings.items()), 'Consumer producer or selected pin changed during analysis')
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')
        print(json.dumps(dict(passed=True, analysis_only=True, snapshot_consistent=len(selection['snapshot_consistent']),
            unresolved_variants=len(selection['unresolved_variants']), new_guest_retirements=0)))
        return 0
    except (OSError, ValueError, ImportError, subprocess.SubprocessError) as error:
        print('Area discovery analysis rejected: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
