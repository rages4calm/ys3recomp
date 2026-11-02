"""Read player data from an authenticated Ys III USA 8 KiB WRAM snapshot.

This is a read-only data view, not a checkpoint decoder or route qualifier.
HP uses its observed low byte; positions use separate low/high-byte arrays.
The context byte is deliberately not interpreted as a story or quest flag.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PlayerState:
    hp: int
    maximum_hp: int
    x: int
    y: int
    camera_x: int
    camera_y: int
    cached_x: int
    cached_y: int
    active_actor: int
    context_byte: int

    @property
    def world_x(self) -> int:
        return (self.x + self.camera_x) & 0xFFFF

    @property
    def world_y(self) -> int:
        return (self.y + self.camera_y) & 0xFFFF

    @property
    def cache_matches_player(self) -> bool | None:
        if self.active_actor != 0:
            return None
        return (self.cached_x, self.cached_y) == (self.x, self.y)


def read_player_state(ram: bytes) -> PlayerState:
    """Decode data only; callers authenticate the input and execution context."""
    if type(ram) is not bytes or len(ram) != 8192:
        raise ValueError("Expected an immutable 8 KiB WRAM snapshot")

    def word(low: int, high: int) -> int:
        return ram[low] | (ram[high] << 8)

    return PlayerState(
        hp=ram[0x0D18],
        maximum_hp=ram[0x0D1E],
        x=word(0x10DB, 0x111F),
        y=word(0x1163, 0x11A7),
        camera_x=word(0x0D0C, 0x0D0D),
        camera_y=word(0x0D0E, 0x0D0F),
        cached_x=word(0x008B, 0x008C),
        cached_y=word(0x008D, 0x008E),
        active_actor=ram[0x0085],
        context_byte=ram[0x0BE0],
    )


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("ram", type=Path, help="Private, authenticated WRAM file")
    args = parser.parse_args()
    state = read_player_state(args.ram.read_bytes())
    print(json.dumps({
        "analysis_only": True,
        "native_qualified": False,
        "player": asdict(state),
        "world_x": state.world_x,
        "world_y": state.world_y,
        "cache_matches_player": state.cache_matches_player,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
