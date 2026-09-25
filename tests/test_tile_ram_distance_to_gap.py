"""mario/ram/tile_ram.py's distance_to_gap -- docs/SPEC_pits.md section 2.
Synthetic RAM (not a real emulator): only the handful of addresses
tile_ram.py itself reads matter for this module's own logic.
"""
from __future__ import annotations

import numpy as np

from mario.ram import tile_ram


def _make_ram(mario_page=0, mario_x=0, ground_cols: set[int] | None = None) -> np.ndarray:
    """A minimal synthetic RAM array: only ADDR_MARIO_X/PAGE and the two
    tile buffers are populated. `ground_cols`: absolute metatile columns
    that should read as GROUND_ID at the ground row; every other column
    (within the two buffers' own 32-column range) is EMPTY_ID."""
    ram = np.zeros(tile_ram.BUF_END, dtype=np.uint8)
    ram[tile_ram.ADDR_MARIO_X] = mario_x
    ram[tile_ram.ADDR_MARIO_PAGE] = mario_page
    for col in (ground_cols or set()):
        buf_addr = tile_ram.BUF1_ADDR if (col // 16) % 2 == 0 else tile_ram.BUF2_ADDR
        ram[buf_addr + tile_ram.GROUND_ROW * 16 + (col % 16)] = tile_ram.GROUND_ID
    return ram


def test_no_gap_within_lookahead_returns_none():
    # Mario at absolute col 0; columns 1-8 all ground.
    ram = _make_ram(mario_x=0, ground_cols=set(range(0, 9)))
    assert tile_ram.distance_to_gap(ram, max_tiles=8) is None


def test_gap_starting_immediately_ahead_returns_one():
    # Column 1 (offset 1) is empty -- no ground_cols include it.
    ram = _make_ram(mario_x=0, ground_cols={0})
    assert tile_ram.distance_to_gap(ram, max_tiles=8) == 1


def test_gap_several_tiles_ahead_returns_its_own_distance():
    # Ground through offset 3 (cols 1-3), gap starts at offset 4 (col 4).
    ram = _make_ram(mario_x=0, ground_cols={0, 1, 2, 3})
    assert tile_ram.distance_to_gap(ram, max_tiles=8) == 4


def test_matches_gap_width_at_the_edge():
    """Once distance_to_gap == 1 (Mario standing right at the edge),
    gap_width's own measurement should describe the same pit."""
    # Ground everywhere except a 3-tile gap starting at offset 1 (cols 1-3),
    # ground resumes at offset 4 (col 4).
    ram = _make_ram(mario_x=0, ground_cols={0, 4, 5, 6, 7, 8})
    assert tile_ram.distance_to_gap(ram, max_tiles=8) == 1
    assert tile_ram.gap_width(ram, max_tiles=8) == 3


def test_respects_max_tiles_lookahead_window():
    # Gap starts at offset 10, outside an 8-tile lookahead.
    ram = _make_ram(mario_x=0, ground_cols=set(range(0, 9)))
    assert tile_ram.distance_to_gap(ram, max_tiles=8) is None
