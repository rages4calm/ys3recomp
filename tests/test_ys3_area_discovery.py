"""Authored synthetic loader observations; no retail instruction fixtures."""
import contextlib
import copy
import hashlib
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import ys3_area_discovery as discovery

ROOT = Path(__file__).resolve().parents[1]
PIN = json.loads((ROOT/'toolchain.json').read_bytes())['tool']
TOOL = ROOT/PIN['checkout']


class AreaDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capture_api = discovery.load_capture_api(TOOL)
        cls.isa = importlib.import_module(cls.capture_api.__package__+'.isa')

    def setUp(self):
        self.mpr = [1, 2, 3, 4, 5, 6, 7, 8]
        self.memory = bytearray(discovery.PHYSICAL_BYTES)
        self.known_ranges = [(0, 0x40000)]

    def row(self, pc=0x4000, data=(0x20, 0x34, 0x12), mpr=None, native=3, interpreted=4):
        mpr = self.mpr.copy() if mpr is None else mpr.copy()
        return dict(pc=pc, mpr=mpr, data=list(data),
                    physical=[self.isa.physical(pc+i, mpr) for i in range(len(data))],
                    native_hits=native, interpreted_hits=interpreted)

    def capture(self, rows):
        return dict(schema=1, runtime_abi=29, capacity=65536, complete=True,
                    dropped_instructions=0, unreadable_instructions=0,
                    retired_instructions=sum(r['native_hits']+r['interpreted_hits'] for r in rows),
                    observations=copy.deepcopy(rows))

    def put(self, row):
        for at, value in zip(row['physical'], row['data']):
            self.memory[at] = value

    def select(self, captures):
        for cap in captures:
            self.capture_api.validate_capture(cap)
        return discovery.select_snapshot_identities(captures, bytes(self.memory), self.mpr, self.isa,
                                                    known_ranges=self.known_ranges)

    def test_full_mapping_and_source_preserved_with_per_capture_counts(self):
        first = self.row(); self.put(first)
        other_mpr = self.mpr.copy(); other_mpr[-1] = 99
        other = self.row(mpr=other_mpr)
        captures = [self.capture([first, other]), self.capture([self.row(native=8, interpreted=9)])]
        before = copy.deepcopy(captures)
        report = self.select(captures)
        self.assertEqual(captures, before)
        self.assertEqual(report['other_mpr_identities'], 1)
        self.assertEqual(len(report['snapshot_consistent']), 1)
        selected = report['snapshot_consistent'][0]
        self.assertEqual(selected['mpr'], first['mpr'])
        self.assertEqual(selected['physical'], first['physical'])
        self.assertEqual(selected['data'], first['data'])
        self.assertEqual(selected['capture_hits'], [dict(capture_index=0, native_hits=3, interpreted_hits=4),
                                                   dict(capture_index=1, native_hits=8, interpreted_hits=9)])

    def test_conflicting_epochs_remain_unresolved_never_stitched(self):
        first = self.row(); conflict = self.row(data=(0x4C, 0x78, 0x56))
        self.put(first)
        report = self.select([self.capture([first, conflict])])
        self.assertEqual(len(report['snapshot_consistent']), 1)
        self.assertEqual(report['unresolved_variants'][0]['data'], conflict['data'])
        # Snapshot combines bytes from both historic rows: neither identity fits.
        self.memory[first['physical'][1]] = conflict['data'][1]
        report = self.select([self.capture([first, conflict])])
        self.assertFalse(report['snapshot_consistent'])
        self.assertEqual(len(report['unresolved_variants']), 2)

    def test_instruction_extent_covers_bank_and_logical_wrap(self):
        for pc in (0x1FFF, 0xFFFF):
            row = self.row(pc=pc); self.put(row)
            self.assertEqual(len(self.select([self.capture([row])])['snapshot_consistent']), 1)
        broken = self.row(); broken['data'] = [0x20]; broken['physical'] = broken['physical'][:1]
        with self.assertRaises(ValueError):
            discovery.decoded_row(broken, self.isa)

    def test_direct_callers_keep_target_full_mapping_bytes_and_per_capture_hits(self):
        mapping = self.mpr.copy(); mapping[-1] = 99
        a = self.row(); b = self.row(mpr=mapping)
        jump = self.row(pc=0x4020, data=(0x4C, 0x34, 0x12))
        caps = [self.capture([a, b, jump]), self.capture([a])]
        report = discovery.group_service_callers(caps, self.isa, [0x1234])
        self.assertEqual(len(report['direct_callers']), 3)
        first = report['direct_callers'][0]
        self.assertEqual(first['target'], 0x1234)
        self.assertEqual(len(first['capture_hits']), 2)
        self.assertEqual(discovery.group_service_callers(caps, self.isa, [0x9999])['direct_callers'], [])

    def test_indirect_target_is_not_guessed_from_snapshot_or_another_row(self):
        rows = [self.row(data=(0x6C, 0x00, 0x50)), self.row(pc=0x4030, data=(0x7C, 0x00, 0x50))]
        result = discovery.group_service_callers([self.capture(rows)], self.isa, [0x1234])
        self.assertFalse(result['direct_callers'])
        self.assertEqual(len(result['unresolved_indirect_transfers']), 2)
        self.assertTrue(all('target' not in r for r in result['unresolved_indirect_transfers']))

    def test_linear_disassembly_is_bounded_uses_official_isa_and_keeps_mpr(self):
        first = self.row(); self.put(first)
        rows = discovery.disassemble_snapshot(bytes(self.memory), self.mpr, [(0x4000, 1)], self.isa,
                                              known_ranges=self.known_ranges)
        self.assertEqual(rows[0]['instructions'][0]['mnemonic'], 'JSR')
        self.assertEqual(rows[0]['instructions'][0]['target'], 0x1234)
        self.assertEqual(rows[0]['instructions'][0]['mpr'], self.mpr)
        for request in ([(0, 257)], [(0, 1)]*17):
            with self.assertRaises(ValueError):
                discovery.disassemble_snapshot(bytes(self.memory), self.mpr, request, self.isa,
                                                known_ranges=self.known_ranges)
        with self.assertRaises(ValueError):
            discovery.select_snapshot_identities([], b'', self.mpr, self.isa, known_ranges=self.known_ranges)

    def test_matching_bytes_in_unknown_storage_are_never_authenticated(self):
        row = self.row(); self.put(row)
        self.known_ranges = [(0x7000, 1)]
        report = self.select([self.capture([row])])
        self.assertFalse(report['snapshot_consistent'])
        unresolved = report['unresolved_variants'][0]
        self.assertEqual(unresolved['data'], row['data'])
        self.assertEqual(unresolved['mpr'], self.mpr)
        self.assertEqual(unresolved['unavailable_physical'], row['physical'])

    def test_instruction_crossing_unknown_byte_is_rejected_even_when_all_bytes_match(self):
        row = self.row(pc=0x1FFF); self.put(row)
        self.known_ranges = [(row['physical'][0], 1), (row['physical'][2], 1)]
        report = self.select([self.capture([row])])
        self.assertFalse(report['snapshot_consistent'])
        self.assertEqual(report['unresolved_variants'][0]['unavailable_physical'], [row['physical'][1]])
        with self.assertRaisesRegex(ValueError, 'unknown physical range'):
            discovery.disassemble_snapshot(bytes(self.memory), self.mpr, [(0x1FFF, 1)], self.isa,
                                            known_ranges=self.known_ranges)
        # Adjacent declared ranges have no hole and preserve the original mapping.
        self.known_ranges = [(row['physical'][0], 1), (row['physical'][1], 2)]
        self.assertEqual(self.select([self.capture([row])])['snapshot_consistent'][0]['physical'], row['physical'])

    def test_known_ranges_refuse_device_holes_mirrors_and_invalid_extents(self):
        for ranges in ([], [(0x1FE000, 1)], [(0x1F2000, 1)], [(0x3FFFF, 2)],
                       [(0, 0)], [(0, True)], [(discovery.PHYSICAL_BYTES, 1)]):
            with self.subTest(ranges=ranges), self.assertRaises(ValueError):
                discovery.normalize_known_ranges(ranges)
        self.assertEqual(discovery.normalize_known_ranges([(0, 16), (8, 16), (24, 1)]), [(0, 25)])

    def test_mirror_and_device_instruction_identity_is_not_silently_canonicalized(self):
        for bank in (0xF9, 0xFA, 0xFB, 0xFF):
            with self.subTest(bank=bank):
                self.mpr[2] = bank
                row = self.row(); self.put(row)
                self.known_ranges = [(0x1F0000, 0x2000)]
                report = self.select([self.capture([row])])
                self.assertFalse(report['snapshot_consistent'])
                self.assertEqual(report['unresolved_variants'][0]['physical'], row['physical'])
                self.assertEqual(report['unresolved_variants'][0]['mpr'], self.mpr)

    def cli_fixture(self, directory):
        root = Path(directory); private = root/'.local'; private.mkdir()
        (root/'toolchain.json').write_text(json.dumps(dict(tool=PIN)))
        row = self.row(); self.put(row)
        memory = private/'physical.bin'; memory.write_bytes(self.memory)
        capture = private/'capture.json'; capture.write_text(json.dumps(self.capture([row])))
        output = private/'report.json'
        args = ['--tool-root', str(TOOL), '--capture', str(capture), '--physical-memory', str(memory),
                '--physical-memory-sha256', hashlib.sha256(memory.read_bytes()).hexdigest(),
                '--physical-range', '0:0x40000',
                '--mpr', ','.join(map(str,self.mpr)), '--service', '0x1234', '--disassemble', '0x4000:1', '--out', str(output)]
        return root, output, args

    def area_fixture(self):
        layout = dict(format='ys3-area-layout-1', file_table_physical=0x200, file_count=5,
            area_file_table_physical=0x205, area_room_table_physical=0x207, area_count=2,
            track_base_physical=0x209, sector_stride=32, sector_bias=2,
            code_destination=0x100000, transfer_mpr=list(reversed(self.mpr)))
        self.memory[0x200:0x205] = bytes((2, 3, 0, 4, 5))
        self.memory[0x205:0x207] = bytes((0, 3))
        self.memory[0x207:0x209] = bytes((7, 11))
        self.memory[0x209:0x20C] = bytes((0x12, 0x34, 0x56))
        ranges = [(0, 0x40000), (0x100000, 0x10000)]
        return layout, ranges

    def test_area_catalogue_decodes_big_endian_base_adjacent_tables_and_keeps_holes(self):
        layout, ranges = self.area_fixture()
        original = copy.deepcopy(layout)
        report = discovery.decode_area_catalogue(bytes(self.memory), ranges, layout)
        self.assertEqual(layout, original)
        self.assertEqual(report['track_base_lba'], 0x123456)
        self.assertEqual(report['files'][2]['sectors'], 0)
        self.assertTrue(report['files'][2]['hole'])
        self.assertEqual(report['areas'][1]['code_lba'], 0x123456 + 32*3 + 2)
        self.assertEqual(report['areas'][1]['companion_lba'], 0x123456 + 32*4 + 2)
        self.assertEqual(report['areas'][1]['descriptor_index'], 11)

    def test_catalogue_transfer_metadata_never_becomes_execution_roots_or_qualification(self):
        layout, ranges = self.area_fixture()
        report = discovery.decode_area_catalogue(bytes(self.memory), ranges, layout)
        self.assertEqual(report['new_guest_retirements'], 0)
        self.assertEqual(report['declared_identities'], 0)
        self.assertFalse(report['native_qualified'])
        for area in report['areas']:
            self.assertEqual(area['transfer_mpr'], layout['transfer_mpr'])
            self.assertNotEqual(area['transfer_mpr'], self.mpr)
            self.assertIsNone(area['execution_mpr'])
            self.assertEqual(area['entry_roots'], [])
            self.assertEqual(area['status'], 'decoded-only')
            self.assertFalse(area['entry_verified'])
            self.assertFalse(area['observed'])
            self.assertEqual(area['companion_role'], 'uninterpreted')
            self.assertNotIn('room_index', area)
            self.assertFalse(any(key.startswith('graphics_') for key in area))

    def test_area_catalogue_rejects_missing_unknown_overlapping_or_unavailable_layout(self):
        layout, ranges = self.area_fixture()
        for change in (dict(extra=1), dict(file_count=True), dict(area_count=257),
                       dict(area_room_table_physical=0x204), dict(track_base_physical=0x1FE000),
                       dict(code_destination=0x1F2000), dict(transfer_mpr=[0]*7)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                discovery.decode_area_catalogue(bytes(self.memory), ranges, dict(layout, **change))
        missing = dict(layout); missing.pop('sector_bias')
        with self.assertRaises(ValueError):
            discovery.decode_area_catalogue(bytes(self.memory), ranges, missing)
        with self.assertRaisesRegex(ValueError, 'unknown physical storage'):
            discovery.decode_area_catalogue(bytes(self.memory), [(0x200, 11), (0x100000, 1)], layout)

    def test_area_catalogue_rejects_bad_file_neighbors_zero_references_and_sector_overflow(self):
        layout, ranges = self.area_fixture()
        original = self.memory[:]
        for file_id in (1, 2, 4, 255):
            self.memory[:] = original; self.memory[0x205] = file_id
            with self.subTest(file_id=file_id), self.assertRaises(ValueError):
                discovery.decode_area_catalogue(bytes(self.memory), ranges, layout)
        self.memory[:] = original; self.memory[0x200] = 33
        with self.assertRaises(ValueError):
            discovery.decode_area_catalogue(bytes(self.memory), ranges, layout)
        self.memory[:] = original; self.memory[0x209:0x20C] = b'\xff\xff\xff'
        with self.assertRaisesRegex(ValueError, '24-bit LBA'):
            discovery.decode_area_catalogue(bytes(self.memory), ranges, layout)

    def test_cli_binds_area_layout_hash_and_emits_decoded_only_catalogue(self):
        with tempfile.TemporaryDirectory() as folder:
            root, output, args = self.cli_fixture(folder)
            layout, _ = self.area_fixture()
            memory = Path(args[args.index('--physical-memory')+1]); memory.write_bytes(self.memory)
            args[args.index('--physical-memory-sha256')+1] = hashlib.sha256(memory.read_bytes()).hexdigest()
            layout_path = root/'.local/layout.json'; layout_path.write_text(json.dumps(layout))
            args.extend(['--physical-range', '0x100000:0x10000', '--area-layout', str(layout_path)])
            with patch.object(discovery, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(discovery.main(args), 0)
            report = json.loads(output.read_bytes())
            self.assertEqual(report['area_layout_input']['sha256'], hashlib.sha256(layout_path.read_bytes()).hexdigest())
            self.assertEqual(report['area_catalogue']['area_count'], 2)
            self.assertTrue(report['area_catalogue']['analysis_only'])
            self.assertFalse(report['area_catalogue']['areas'][0]['entry_verified'])

    def test_cli_binds_authentic_inputs_and_labels_no_new_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            root, output, args = self.cli_fixture(folder)
            with patch.object(discovery, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(discovery.main(args), 0)
            report = json.loads(output.read_bytes())
            self.assertTrue(report['analysis_only'])
            self.assertFalse(report['native_qualified'])
            self.assertEqual(report['new_guest_retirements'], 0)
            self.assertEqual(report['declared_identities'], 0)
            self.assertEqual(report['physical_epoch']['known_ranges'], [dict(base=0, length=0x40000)])
            self.assertEqual(report['captures'][0]['historical_retirements'], 7)
            self.assertEqual(len(report['snapshot_service_calls']['direct_callers']), 1)
            # Create-new rule protects already emitted evidence.
            original = output.read_bytes()
            with patch.object(discovery, 'ROOT', root), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(discovery.main(args), 1)
            self.assertEqual(output.read_bytes(), original)

    def test_cli_rejects_wrong_digest_and_public_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root, output, args = self.cli_fixture(folder)
            args[args.index('--physical-memory-sha256')+1] = '0'*64
            with patch.object(discovery, 'ROOT', root), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(discovery.main(args), 1)
            self.assertFalse(output.exists())
            args[args.index('--out')+1] = str(root/'public.json')
            with patch.object(discovery, 'ROOT', root), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(discovery.main(args), 1)
            self.assertFalse((root/'public.json').exists())

    def test_cli_requires_explicit_known_ranges(self):
        with tempfile.TemporaryDirectory() as folder:
            root, output, args = self.cli_fixture(folder)
            at = args.index('--physical-range'); del args[at:at+2]
            with patch.object(discovery, 'ROOT', root), contextlib.redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit) as raised:
                discovery.main(args)
            self.assertEqual(raised.exception.code, 2)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
