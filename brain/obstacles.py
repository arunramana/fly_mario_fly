# What this file does, in plain English:
# Works out how big the nearest wall, pipe, block or step in front of Mario looks
# to him, from the map of blocks drawn on screen (the game's tile memory). It is
# the obstacle twin of brain/perception.py's enemy size: the same formula for
# angular size (theta = 2 atan(w / 2d)) and the same weighting for objects above
# or below his eye level. It never presses anything and never touches the brain;
# its output is only a number the looming mechanism turns into sensory activity.
"""brain/obstacles.py -- docs/SPEC_e2a.md section 1 (encoding rule fixed before validation).

Mario's-eye-view assumption: a static obstacle expands on the retina because Mario walks toward it. Geometry only: the stimulus
is re-read from RAM every frame, so d (and with it theta and dtheta) changes only through Mario's own motion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from mario.ram import screen, tile_ram
from mario.ram.addresses import ADDR_MARIO_PAGE, ADDR_MARIO_SIZE, ADDR_MARIO_X

ADDR_PLAYER_HITBOX_BOTTOM = 0x04AF
BODY_SMALL_PX, BODY_BIG_PX = 12, 24   # Mario's hitbox heights (docs/SPEC_geometry_5c.md section 1; the game's own collision box)
TILE_PX = 16
TILE_TOP_Y = 32                 # screen y of metatile row 0 (measured: the floor row 11 starts at y 208 = 32 + 16 * 11)
FLOOR_ROW = tile_ram.GROUND_ROW  # rows >= FLOOR_ROW are the floor: never an obstacle
EMPTY = tile_ram.EMPTY_ID


@dataclass(frozen=True)
class Face:
    d_px: float          # face left edge minus Mario's left edge (same convention as enemies)
    w_px: float          # vertical extent of the contiguous solid run (picture plane, perpendicular to the approach)
    centre_y: float      # screen y of the run's centre
    top_y: float         # screen y of the run's top edge
    bottom_y: float      # screen y of the run's bottom edge (the face is an extended object, not its centre point)


def _runs(tiles: Sequence[int]) -> list[tuple[int, int]]:
    """Contiguous (first_row, last_row) runs of solid tiles in rows 0..FLOOR_ROW-1."""
    runs, start = [], None
    for r in range(FLOOR_ROW):
        if tiles[r] != EMPTY:
            start = r if start is None else start
        elif start is not None:
            runs.append((start, r - 1))
            start = None
    if start is not None:
        runs.append((start, FLOOR_ROW - 1))
    return runs


def nearest_face(columns: Iterable[tuple[int, Sequence[int]]], mario_x: float, feet_y: float, height_px: float) -> Face | None:
    """The nearest obstacle face. `columns` = (left x of the column in px, its 13 tile ids) for the visible columns only.
    A column is a face when it is ahead (d > 0) and a solid run overlaps Mario's body [feet - h, feet)."""
    top = feet_y - height_px
    best: Face | None = None
    for col_x, tiles in columns:
        d = col_x - mario_x
        if d <= 0 or (best is not None and d >= best.d_px):
            continue
        hit = [(a, b) for a, b in _runs(tiles)
               if TILE_TOP_Y + TILE_PX * a < feet_y and TILE_TOP_Y + TILE_PX * (b + 1) > top]
        if not hit:
            continue
        a, b = max(hit, key=lambda ab: ab[1] - ab[0])
        best = Face(float(d), float(TILE_PX * (b - a + 1)), TILE_TOP_Y + TILE_PX * (a + b + 1) / 2.0,
                    float(TILE_TOP_Y + TILE_PX * a), float(TILE_TOP_Y + TILE_PX * (b + 1)))
    return best


def visible_columns(ram) -> list[tuple[int, list[int]]]:
    """(left x px, 13 tile ids) of every metatile column drawn on screen. Read-only use of the legacy tile decoder."""
    buf1, buf2 = tile_ram._grids(ram)
    left = screen.screen_left(ram)
    out = []
    for col in range(left // TILE_PX, (left + screen.SCREEN_WIDTH_PX - 1) // TILE_PX + 1):
        if col * TILE_PX >= left + screen.SCREEN_WIDTH_PX:
            break
        out.append((col * TILE_PX, [tile_ram._tile_at_abs_col(buf1, buf2, col, r) or 0 for r in range(tile_ram.ROWS)]))
    return out


def elevation_deg(face: Face, body_top: float, body_bottom: float, d: float) -> float:
    """Elevation of the NEAREST POINT of the face to Mario's body: the vertical gap between the face extent and the body extent
    (0 when they overlap), seen from distance d. An extended object, not its centre point (docs/SPEC_geometry_5c.md step 3)."""
    gap = max(0.0, face.top_y - body_bottom, body_top - face.bottom_y)
    return math.degrees(math.atan2(gap, d))


def theta_of(face: Face | None, body_top: float, body_bottom: float, elevation_limit_deg: float) -> tuple[float, float | None]:
    """(theta rad, d px) for a face: 2 atan(w / 2d) x max(0, 1 - elev / limit); the enemies' weight function, nearest-point elevation."""
    if face is None:
        return 0.0, None
    d = max(face.d_px, 1.0)
    elev = elevation_deg(face, body_top, body_bottom, d)
    return 2.0 * math.atan(face.w_px / (2.0 * d)) * max(0.0, 1.0 - elev / elevation_limit_deg), face.d_px


def obstacle_thetas(ram, prev_theta, elevation_limit_deg: float):
    """Same contract as `brain.perception.enemy_thetas` (theta, dtheta, distance per hemisphere), for the nearest obstacle face."""
    mario_x = int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X])
    height = BODY_SMALL_PX if int(ram[ADDR_MARIO_SIZE]) == 0 else BODY_BIG_PX
    feet = int(ram[ADDR_PLAYER_HITBOX_BOTTOM])
    face = nearest_face(visible_columns(ram), mario_x, feet, height)
    th, d = theta_of(face, feet - height, feet, elevation_limit_deg)
    theta = {"L": th, "R": th}
    return theta, {s: theta[s] - prev_theta[s] for s in ("L", "R")}, {"L": d, "R": d}
