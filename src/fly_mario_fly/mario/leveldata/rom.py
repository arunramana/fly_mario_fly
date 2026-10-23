"""Locate and read SMB1's level tables in the iNES ROM the gym env loads (super-mario-bros.nes, NROM-256).

Source of the formats: the community disassembly of Super Mario Bros. (doppelganger's "smbdis.asm"; labels used here:
WorldAddrOffsets, AreaAddrOffsets, EnemyAddrHOffsets, EnemyDataAddrLow/High, AreaDataHOffsets, AreaDataAddrLow/High,
GetAreaDataAddrs, E_* enemy data, L_* area data). The tables are found by their bytes, not by fixed offsets, and the
asserts below fail loudly if the file is not SMB1.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

HEADER = 16                                  # iNES header; PRG ROM is mapped at CPU $8000
PRG_BASE = 0x8000

# WorldAddrOffsets: where each world's row starts inside AreaAddrOffsets (worlds have 5,5,4,5,4,4,5,4 area slots)
WORLD_OFFSETS = (0, 5, 10, 14, 19, 23, 27, 32)

AREA_TYPES = ("water", "overground", "underground", "castle")        # AreaType 0..3 (pointer bits 6-5)
TYPE_COUNTS = (3, 22, 3, 6)                                          # how many data blocks of each type exist
KEY_NAMES = ("water", "ground", "underground", "castle")             # the disassembly's L_WaterArea1, L_GroundArea1 ...


def rom_file() -> Path:
    from gym_super_mario_bros._roms import rom_path
    return Path(rom_path(False, "vanilla"))          # the ROM gym_super_mario_bros.make("SuperMarioBros-*-v0") loads


@lru_cache(maxsize=None)
def _load(path: str) -> "Rom":
    return Rom(Path(path).read_bytes())


def load(path: str | Path | None = None) -> "Rom":
    return _load(str(path or rom_file()))


class Rom:
    def __init__(self, data: bytes):
        assert data[:4] == b"NES\x1a", "not an iNES file"
        self.data = data
        anchor = bytes(WORLD_OFFSETS)
        assert data.count(anchor) == 1, "WorldAddrOffsets not found: not Super Mario Bros. 1?"
        wo = data.find(anchor)
        self.area_addr_offsets = list(data[wo + 8:wo + 44])               # AreaAddrOffsets: 36 area pointers
        eho = wo + 44
        assert list(data[eho:eho + 4]) == [0x1F, 0x06, 0x1C, 0x00], "EnemyAddrHOffsets mismatch"
        self.enemy_h = list(data[eho:eho + 4])
        n = sum(TYPE_COUNTS)
        el, eh = eho + 4, eho + 4 + n
        self.enemy_ptr = [data[el + i] | data[eh + i] << 8 for i in range(n)]            # EnemyDataAddrLow/High
        ado = eh + n
        assert list(data[ado:ado + 4]) == [0x00, 0x03, 0x19, 0x1C], "AreaDataHOffsets mismatch"
        self.area_h = list(data[ado:ado + 4])
        al, ah = ado + 4, ado + 4 + n
        self.area_ptr = [data[al + i] | data[ah + i] << 8 for i in range(n)]              # AreaDataAddrLow/High

    def byte(self, cpu: int) -> int:
        return self.data[cpu - PRG_BASE + HEADER]

    def area_pointer(self, world: int, slot: int) -> int:
        """FindAreaPointer: the area pointer byte for world 0-7 and an area slot within the world."""
        return self.area_addr_offsets[WORLD_OFFSETS[world] + slot]

    def locate(self, pointer: int) -> tuple:
        """GetAreaDataAddrs: (area type 0-3, index within type, enemy data CPU address, area data CPU address)."""
        typ, idx = (pointer & 0x60) >> 5, pointer & 0x1F
        return typ, idx, self.enemy_ptr[self.enemy_h[typ] + idx], self.area_ptr[self.area_h[typ] + idx]


def area_key(pointer: int) -> str:
    typ, idx = (pointer & 0x60) >> 5, pointer & 0x1F
    return f"{KEY_NAMES[typ]}{idx + 1}"
