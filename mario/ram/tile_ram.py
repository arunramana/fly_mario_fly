# What this file does, in plain English:
# Reads the part of the game's memory that holds the map of blocks around
# Mario (ground, bricks, pipes, "?" blocks, empty sky). From it, it answers
# three questions: is there ground ahead or a pit, and how many blocks wide
# is the pit; is there a wall or pipe directly in front of Mario; and where
# are the nearby "?" blocks.
"""
tile_ram.py — SPEC_terrain.md section 1: decode the SMB collision tile
buffer at 0x0500-0x069F.

Two 13-row x 16-column metatile buffers, `Block_Buffer_1` (0x0500) and
`Block_Buffer_2` (0x05D0) — confirmed against the actual disassembly
(gist.github.com/1wErt3r/4048722, doppelganger's SMBDIS.ASM): row-major,
13 rows of 16 bytes, `0x0500 + 0xD0 = 0x05D0`, `0x05D0 + 0xD0 = 0x06A0`.
Each buffer is one full NES nametable's worth of metatile columns (16
metatile-columns = 32 hardware tile-columns = exactly one 256px screen);
SMB's engine double-buffers them the way the PPU double-buffers horizontal
scrolling, so which one holds the *next* upcoming screen alternates as
Mario crosses each 256px boundary.

**Tile IDs are verified, not taken from a web table** (published tables
disagree on 0xC0-0xC3). Checked two ways: against SMBDIS.ASM's
`Palette3_MTiles` (top two bits pick the palette, low six the entry:
"question block (coin)" = 0xC0, "(power-up)" = 0xC1), and by dumping the
live buffer on 1-1 against a screenshot of the same frame (lone "?" =
0xC0; brick-?-brick-?-brick = 0x51, 0xC1, 0xC0). Ground is 0x54 at row 11
(SMBDIS.ASM: `lda #$54`); empty (sky/pit) is 0x00, seen at a 1-1 pit.
Pipe metatiles 0x10-0x15 appeared where `Palette0_MTiles` predicts,
confirming the IDs and the column math together.

**Column indexing.** Two 16-column buffers back to back form one
continuous strip of absolute metatile columns: columns `[0,16)` live in
`Block_Buffer_1`, `[16,32)` in `Block_Buffer_2`, `[32,48)` back in
`Block_Buffer_1`, and so on — `buffer = Buf1 if (abs_col // 16) % 2 == 0
else Buf2`, `column_in_buffer = abs_col % 16`. Checked against screenshots
on page 0 and again on page 1, after the buffers swap. Do not instead pick
whichever buffer shows ground under Mario: flat ground is pre-filled ahead
in both buffers, so that only looks right on flat stretches.
"""

from __future__ import annotations

import numpy as np

BUF1_ADDR = 0x0500
BUF2_ADDR = 0x05D0
BUF_END = 0x06A0
ROWS, COLS = 13, 16

ADDR_MARIO_X = 0x0086
ADDR_MARIO_PAGE = 0x006D

GROUND_ROW = 11          # empirically confirmed: flat ground sits at row 11 (and 12)
GROUND_ID = 0x54
QUESTION_COIN_ID = 0xC0
QUESTION_POWERUP_ID = 0xC1
QUESTION_IDS = (QUESTION_COIN_ID, QUESTION_POWERUP_ID)
EMPTY_ID = 0x00

# A `?` block that has been hit becomes this solid "used block". From the
# SMB RAM map, NOT confirmed with a live hit: scripted jumps at the 1-1
# block (abs_col=16, row 7) never registered one. Absent from QUESTION_IDS
# so it stops being an odour source, and solid for `solid_ahead`.
USED_BLOCK_ID = 0xC4
assert USED_BLOCK_ID not in QUESTION_IDS and USED_BLOCK_ID not in (GROUND_ID, EMPTY_ID)

# Rows spanning Mario's body for the "wall ahead" check: above the ground
# rows (11-12), up to big Mario's head. Decorative metatiles (clouds,
# bushes, hills) sit in rows 0-6 on 1-1, so this window sees only sky,
# ground, brick, block or pipe.
BODY_ROWS = (8, 9, 10)


def _grids(ram) -> tuple[np.ndarray, np.ndarray]:
    """Both buffers as (13, 16) row-major grids."""
    buf1 = np.asarray(ram[BUF1_ADDR:BUF2_ADDR]).reshape(ROWS, COLS)
    buf2 = np.asarray(ram[BUF2_ADDR:BUF_END]).reshape(ROWS, COLS)
    return buf1, buf2


def _mario_abs_col(ram) -> int:
    abs_x = int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X])
    return abs_x // 16


def _tile_at_abs_col(buf1, buf2, abs_col: int, row: int):
    if abs_col < 0:
        return None  # behind the start of the level -- not meaningful
    buf = buf1 if (abs_col // 16) % 2 == 0 else buf2
    return int(buf[row, abs_col % 16])


def ground_ahead(ram, n_tiles: int) -> list[bool]:
    """For offsets 1..n_tiles ahead of Mario's own column: is there ground
    (GROUND_ID) at the ground row? A run of False starting at offset 1 is a
    pit -- its length is the gap width SPEC_terrain.md section 2 wants."""
    buf1, buf2 = _grids(ram)
    col0 = _mario_abs_col(ram)
    return [_tile_at_abs_col(buf1, buf2, col0 + k, GROUND_ROW) == GROUND_ID
            for k in range(1, n_tiles + 1)]


def gap_width(ram, max_tiles: int = 8) -> int:
    """Consecutive non-ground tiles immediately ahead of Mario (offset 1),
    stopping at the first tile that IS ground."""
    width = 0
    for grounded in ground_ahead(ram, max_tiles):
        if grounded:
            break
        width += 1
    return width


def distance_to_gap(ram, max_tiles: int = 8) -> int | None:
    """Tile-offset (1-indexed, matching ground_ahead's own convention) of
    the NEAREST non-ground tile ahead of Mario -- how many tiles until a
    pit starts, not how wide it is. gap_width() only ever reads offset 1
    (it's 0 for every tile Mario hasn't reached the edge of yet); this
    reuses the same ground_ahead() scan to answer "is one coming up" while
    Mario is still several tiles of solid ground away from it
    (docs/SPEC_pits.md: distance-triggered long jump). None if every tile
    in the lookahead window is ground -- no gap within range."""
    for offset, grounded in enumerate(ground_ahead(ram, max_tiles), start=1):
        if not grounded:
            return offset
    return None


def solid_ahead(ram) -> bool:
    """Is the column directly in front of Mario (offset 1) blocked at body
    height -- a wall or pipe to climb rather than a pit (SPEC_terrain.md
    section 1). Question blocks don't count: they float overhead."""
    buf1, buf2 = _grids(ram)
    col0 = _mario_abs_col(ram)
    for row in BODY_ROWS:
        t = _tile_at_abs_col(buf1, buf2, col0 + 1, row)
        if t is not None and t != EMPTY_ID and t not in QUESTION_IDS:
            return True
    return False


def question_blocks_near(ram, n_tiles: int = 16) -> list[int]:
    """Screen-relative column offsets (can be negative -- behind Mario) of
    every `?` block (coin or power-up) within +-n_tiles of Mario's own
    column. A hit block reads as USED_BLOCK_ID and is not listed, so an
    emptied block stops smelling (bridge.perception.question_block_odor)."""
    buf1, buf2 = _grids(ram)
    col0 = _mario_abs_col(ram)
    offsets = []
    for k in range(-n_tiles, n_tiles + 1):
        for row in range(ROWS):
            t = _tile_at_abs_col(buf1, buf2, col0 + k, row)
            if t in QUESTION_IDS:
                offsets.append(k)
                break
    return offsets


def upcoming_gap_width(ram, max_tiles: int = 8) -> int:
    """Width (tiles) of the first pit within the lookahead window, wherever
    it starts; 0 if there is none. gap_width() only counts a pit that begins
    right at offset 1."""
    width = 0
    for grounded in ground_ahead(ram, max_tiles):
        if not grounded:
            width += 1
        elif width:
            break
    return width


# Highest row an obstacle's height is counted up to (row 10 is the first row
# above the ground; 8 tiles is the tallest stair in the game).
OBSTACLE_TOP_ROW = 3


def obstacle_height(ram, abs_col: int) -> int:
    """Height in tiles of the solid stack standing on the ground in one
    absolute column: consecutive solid tiles counted upward from row 10. A
    floating block (not touching the ground stack) does not count -- Mario
    walks under it. 0 = the column is open at walking height."""
    buf1, buf2 = _grids(ram)
    height = 0
    for row in range(GROUND_ROW - 1, OBSTACLE_TOP_ROW - 1, -1):
        t = _tile_at_abs_col(buf1, buf2, abs_col, row)
        if t is None or t == EMPTY_ID or t in QUESTION_IDS:
            break
        height += 1
    return height


def obstacle_ahead(ram, max_tiles: int = 6) -> tuple[int, int] | None:
    """The nearest solid obstacle ahead within `max_tiles` columns of Mario's
    own, as (distance_tiles, height_tiles) -- distance 1-indexed like
    ground_ahead. None if the way is open. A pipe, a stair step or a block
    stack all read the same: a wall of some height."""
    col0 = _mario_abs_col(ram)
    for k in range(1, max_tiles + 1):
        h = obstacle_height(ram, col0 + k)
        if h:
            return k, h
    return None
