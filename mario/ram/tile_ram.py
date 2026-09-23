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

**Tile IDs were NOT taken on faith from a web table — two disagreed with
each other during research for this module (one said question blocks are
0xC0/0xC1 with 0xC2/0xC3 as plain coin tiles, another claimed the reverse).
Resolved empirically, twice over**: (1) against SMBDIS.ASM's own
`Palette3_MTiles` graphics table, where a metatile ID's top two bits select
one of 4 palette tables and the low 6 bits index into it — "question block
(coin)" is entry 0 of palette 3 -> `0xC0`, "question block (power-up)" is
entry 1 -> `0xC1`; and (2) by dumping the live buffer during a run of SMB
1-1 and cross-checking against the captured screenshot at that exact frame:
the isolated "?" block hanging above-left of the very first obstacle
cluster showed up as `0xC0`, and the row of brick-?-brick-?-brick below it
showed brick=`0x51`, its two "?"s as `0xC1` (power-up, matching the
elevated lone block being the power-up spot in the real level) and `0xC0`
(coin) — matching the rendered sprites in the screenshot exactly. Ground
came back as `0x54` at row 11, matching SMBDIS.ASM's own
`lda #$54  ;old terrain type with ground level terrain type`. **0x00 =
empty (sky/pit)**, confirmed the same way at a 1-1 pit: ground present at
row 11 under Mario's feet, then 0x00 the instant a forward column crosses
the gap. Pipe metatiles (0x10-0x15) were independently spotted at the
correct buffer position ahead of Mario's advance, matching
`Palette0_MTiles`'s pipe entries exactly — an unplanned second confirmation
that the whole indexing scheme (both the tile IDs and the column math
below) is self-consistent.

**Column indexing.** Two 16-column buffers back to back form one
continuous strip of absolute metatile columns: columns `[0,16)` live in
`Block_Buffer_1`, `[16,32)` in `Block_Buffer_2`, `[32,48)` back in
`Block_Buffer_1`, and so on — `buffer = Buf1 if (abs_col // 16) % 2 == 0
else Buf2`, `column_in_buffer = abs_col % 16`. Verified against the running
game, not assumed: checked that this formula places a tile-buffer feature
(a pipe, a `?`-block cluster) at the SAME column parity and offset the
screenshot at that exact frame shows it, at both an early page-0 position
and again after Mario had crossed into page 1 (where the two buffers had
visibly swapped which one was "ahead" of him) — the naive alternative
(picking whichever buffer merely shows ground under Mario's own column)
looked right by coincidence on a flat stretch but is not reliable: flat
ground is pre-filled well ahead of the visible screen in *both* buffers, so
"ground present" cannot by itself tell you which one is currently on
screen. The abs_col formula does not depend on that coincidence.
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

# A `?` block that has already been hit becomes this metatile -- a plain,
# solid "used block" with no coin/power-up left inside, corroborated by two
# independent sources (the SMB RAM-map reference consulted during
# SPEC_terrain.md's own research, and a direct instruction from the project
# owner) but NOT independently re-confirmed with a live block-hit this
# sprint: several scripted attempts to land a jump on the confirmed 1-1
# block at abs_col=16 (row 7) -- both timing-swept and position-pinned via
# direct RAM writes -- never registered a hit, most likely because nes-py's
# controller-hold semantics and the game's own collision-height check don't
# line up the way a hand-timed script assumes. Recorded here rather than
# silently claimed as verified. `question_blocks_near` already excludes it
# by construction (it is deliberately absent from `QUESTION_IDS`, not
# filtered by a separate check), and it is intentionally solid for
# `solid_ahead` -- a used block is still a real physical obstacle.
USED_BLOCK_ID = 0xC4
assert USED_BLOCK_ID not in QUESTION_IDS and USED_BLOCK_ID not in (GROUND_ID, EMPTY_ID)

# Rows spanning Mario's body for the "wall ahead" check -- above the ground
# rows (11-12), covering both small (1 tile) and big (2 tile) Mario's head
# height. Purely decorative background metatiles (clouds, bushes, hills) in
# every 1-1 obstacle this module was checked against live higher up the
# screen (rows 0-6), so this window in practice only ever sees sky, ground,
# brick, block, or pipe metatiles.
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


def solid_ahead(ram) -> bool:
    """Is the column directly in front of Mario (offset 1) blocked at body
    height -- a wall/pipe to climb, as opposed to a pit (SPEC_terrain.md
    section 1: this is what lets the existing contact-based climb reflex in
    run_steering.py finally tell the two apart instead of stalling on
    either). Question blocks don't count as a climb target -- they float
    overhead, not underfoot."""
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
    column. A block that has already been hit reads back as
    `USED_BLOCK_ID` (0xC4), not a member of `QUESTION_IDS` -- it is
    excluded here by construction, not by a separate check, so it stops
    being an odour source (run_steering.py's `question_block_odor`) the
    instant it's used, matching a real emptied `?` block having nothing
    left to smell."""
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
