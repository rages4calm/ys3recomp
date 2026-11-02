"""Synthetic data-layout checks; no retail code, media or saves."""
import importlib.util
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / "scripts" / "ys3_state.py"
SPEC = importlib.util.spec_from_file_location("ys3_state_under_test", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PlayerDataTests(unittest.TestCase):
    def test_independent_split_axes_and_camera(self):
        ram = bytearray(8192)
        for offset, value in {
            0x10DB: 0x34, 0x111F: 0x12, 0x1163: 0x78, 0x11A7: 0x56,
            0x0D0C: 0x02, 0x0D0D: 0x01, 0x0D0E: 0x04, 0x0D0F: 0x03,
        }.items():
            ram[offset] = value
        state = MODULE.read_player_state(bytes(ram))
        self.assertEqual((state.x, state.y), (0x1234, 0x5678))
        self.assertEqual((state.world_x, state.world_y), (0x1336, 0x597C))

    def test_world_coordinates_wrap_as_unsigned_words(self):
        ram = bytearray(8192)
        ram[0x10DB] = 32
        ram[0x0D0C:0x0D0E] = b"\xf0\xff"
        state = MODULE.read_player_state(bytes(ram))
        self.assertEqual(state.world_x, 16)

    def test_health_does_not_invent_a_high_byte(self):
        ram = bytearray(8192)
        ram[0x0D18:0x0D1A] = b"\x14\xab"
        ram[0x0D1E:0x0D20] = b"\x1e\xcd"
        state = MODULE.read_player_state(bytes(ram))
        self.assertEqual((state.hp, state.maximum_hp), (20, 30))

    def test_cached_position_is_not_another_actor_player_position(self):
        ram = bytearray(8192)
        ram[0x0085] = 2
        self.assertIsNone(MODULE.read_player_state(bytes(ram)).cache_matches_player)

    def test_player_cache_mismatch_remains_visible(self):
        ram = bytearray(8192)
        ram[0x10DB] = 12
        ram[0x008B] = 13
        self.assertFalse(MODULE.read_player_state(bytes(ram)).cache_matches_player)
        ram[0x008B] = 12
        self.assertTrue(MODULE.read_player_state(bytes(ram)).cache_matches_player)

    def test_context_byte_has_no_story_interpretation(self):
        ram = bytearray(8192)
        ram[0x0BE0] = 96
        state = MODULE.read_player_state(bytes(ram))
        self.assertEqual(state.context_byte, 96)
        self.assertFalse(hasattr(state, "quest"))

    def test_rejects_truncated_and_mutable_snapshots(self):
        for invalid in (b"", bytes(8191), bytes(8193), bytearray(8192)):
            with self.subTest(kind=type(invalid), length=len(invalid)):
                with self.assertRaises(ValueError):
                    MODULE.read_player_state(invalid)


if __name__ == "__main__":
    unittest.main()
