"""Obstacles read from the NES metatile buffer in RAM (no hard-coded positions).

Layout found empirically (flyrun/tests + runs/001_level_map.csv): 0x0500 + 208*page + 16*row + col,
2 pages x 13 rows x 16 cols, world page P is stored in buffer page P % 2. Tile 0 = empty sky,
84 = ground, 18..21 = pipe (top-left, top-right, body-left, body-right), 81/192/193 = brick/?-block.
Ground fills rows 11-12; a pit is a column where both are empty. Row r is y = 16*r px from the
top of the playfield.

The buffer only holds what has been scrolled in, so lookahead is limited to the visible screen
(ScreenLeft + 256): the fly sees what Mario could see, not the whole level.
"""
from dataclasses import dataclass

TILE = 16
BUF = 0x0500
PAGE_BYTES = 13 * 16
ROW_GROUND = 11           # INVENTED (fixed), hand-identified on 1-1: first ground row; rows 11 and 12 are ground
ROW_STAND = 10            # row directly above the ground: where a wall's base sits
ADDR_MARIO_PAGE, ADDR_MARIO_X = 0x006D, 0x0086
ADDR_SCREEN_PAGE, ADDR_SCREEN_X = 0x071A, 0x071C   # world x of the screen's left edge

SOLID_WALL = {18, 19, 20, 21, 97}   # INVENTED (fixed), hand-identified on 1-1: pipe pieces + hard (stair) block; run 001 notes
RIM_TILES = {16, 17}   # INVENTED (fixed), S3 0a: the rim of 1-1 pipe 4 (ids 16/17; pipes 1-3 use 18/19). Only read when scan_visible(rim=True) (senses v2); v1 keeps SOLID_WALL as it was
QBLOCK_TILES = {192, 193}   # INVENTED (fixed), hand-identified (O0): '?' blocks (192 coin, 193 mushroom); 35 = bump animation, 196 = used
EMPTY = 0


@dataclass
class Face:
    x: int      # world x of the left edge of the face
    h: int      # height in px


@dataclass
class Pit:
    x: int      # world x of the near edge
    w: int      # width in px


def tile(ram, wx, row):
    page, col = (wx // 256), (wx % 256) // TILE
    return int(ram[BUF + PAGE_BYTES * (page % 2) + 16 * row + col])


def _visible_range(ram):
    left = int(ram[ADDR_SCREEN_PAGE]) * 256 + int(ram[ADDR_SCREEN_X])
    return left, left + 256


def _mx(ram):
    return int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X])


def scan_visible(ram, rim=False):
    """-> (walls, pits) over the visible screen: walls [(x, H)] per column, pits [(x, w)]. rim=True (senses v2) also counts the RIM_TILES as wall."""
    solid = SOLID_WALL | RIM_TILES if rim else SOLID_WALL
    left, right = _visible_range(ram)
    walls, pits, cur = [], [], None
    for wx in range((left // TILE) * TILE, right, TILE):
        if tile(ram, wx, ROW_STAND) in solid:
            r = ROW_STAND
            while r >= 0 and tile(ram, wx, r) in solid:
                r -= 1
            walls.append((wx, (ROW_STAND - r) * TILE))
        no_ground = tile(ram, wx, ROW_GROUND) == EMPTY and tile(ram, wx, ROW_GROUND + 1) == EMPTY
        if no_ground:
            if cur is None:
                cur = [wx, TILE]
            else:
                cur[1] += TILE
        elif cur is not None:
            pits.append(tuple(cur))
            cur = None
    if cur is not None:
        pits.append(tuple(cur))   # runs off the right edge of the screen; width is a lower bound
    return walls, pits


def scan_blocks(ram):
    """Part Q1: the UNUSED "?" blocks on the visible screen -> [(x, row)] (tiles 192 / 193; a hit block is 35 then 196)."""
    left, right = _visible_range(ram)
    return [(wx, r) for wx in range((left // TILE) * TILE, right, TILE) for r in range(0, ROW_GROUND) if tile(ram, wx, r) in QBLOCK_TILES]


def obstacles_ahead(ram):
    """-> (Face, Pit), either may be None.

    Face = the nearest wall column AHEAD of the column Mario stands on whose top is higher than
    that column's top; H is the height difference. So pipe 1 is a 32 px face from the ground, and
    each stair step is its own 16 px face as Mario climbs. Pit = the nearest pit not yet crossed."""
    mx = _mx(ram)
    walls, pits = scan_visible(ram)
    height = dict(walls)
    here = (mx // TILE) * TILE            # the column under Mario's left edge
    base = height.get(here, 0)
    face = next((Face(wx, h - base) for wx, h in walls if wx > here and h > base), None)
    pit = next((Pit(x, w) for x, w in pits if x + w > mx and x >= mx - 4), None)
    return face, pit
