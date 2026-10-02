# What this file does, in plain English:
# Works out how big the nearest visible enemy looks to Mario, and in which
# direction, from the game's memory. It fixes one defect of the older version:
# the game stores Mario's height and an enemy's height on different baselines
# (a Goomba on the same ground reads 8 pixels lower than Mario), so an enemy at
# Mario's own level used to look like it was above or below him. Here both are
# compared by where their feet and centres really are.
"""brain/perception.py -- docs/SPEC_brain_core.md section 6 (elevation encoding, defect D1).

`bridge.perception.bio_enemy_thetas` (frozen) compares the raw Player_Y_Position byte with the raw Enemy_Y_Position
byte. The engine stores them on different baselines: for small Mario on flat ground in 1-1 the player byte is 176 and a
Goomba's is 184, though both stand on the same floor (feet at screen y 208). That 8 px offset made a same-level enemy
read as ~30 deg elevation at close range and down-weighted theta to nothing.

Here the vertical centre of each object is taken from where its sprite really is:
  Mario: feet = bottom of his hitbox (RAM 0x04AF, screen y, any size), height 16 px small / 32 px big (RAM 0x0756)
  enemy: sprite top = Enemy_Y_Position + 8, height 16 px (the registry models every enemy as 16 px), feet = byte + 24
Measured offsets (small Mario, 1-1): Mario byte 176, hitbox bottom 208; Goomba byte 184, feet 208 (same floor).
Validated only on a synthetic ground-level object (tests/test_brain_core.py), never on game outcomes.
"""

from __future__ import annotations

import math

from bridge.perception import _dx
from mario.entities.kinds import EntityKind
from mario.ram import screen
from mario.ram.addresses import ADDR_ENEMY_Y, ADDR_MARIO_SIZE, ADDR_MARIO_X

ADDR_PLAYER_HITBOX_BOTTOM = 0x04AF   # screen y of the bottom edge of Mario's collision box (feet)
ENEMY_Y_BYTE_TO_TOP_PX = 8           # Enemy_Y_Position is 8 px above the sprite top
SPRITE_PX = 16                       # every enemy is modelled 16 px (mario/entities/registry.py)
MARIO_SMALL_PX, MARIO_BIG_PX = 16, 32


def mario_centre_y(ram) -> float:
    height = MARIO_SMALL_PX if int(ram[ADDR_MARIO_SIZE]) == 0 else MARIO_BIG_PX
    return int(ram[ADDR_PLAYER_HITBOX_BOTTOM]) - height / 2.0


def enemy_centre_y(ram, slot: int) -> float:
    return int(ram[ADDR_ENEMY_Y + slot]) + ENEMY_Y_BYTE_TO_TOP_PX + SPRITE_PX / 2.0


def enemy_thetas(ram, prev_theta, registry, elevation_limit_deg: float):
    """Same contract as bridge.perception.bio_enemy_thetas (theta, dtheta, distance per hemisphere), visible enemies
    ahead of Mario only, theta = 2 atan(w / 2d) weighted by max(0, 1 - elev / limit); only elev changes: it is the angle
    between Mario's and the enemy's vertical centres over the horizontal distance."""
    mario_x, mario_cy = int(ram[ADDR_MARIO_X]), mario_centre_y(ram)
    best, best_d = 0.0, None
    for slot, rec in enumerate(registry.enemy_records(ram)):
        if not rec.active or rec.kind == EntityKind.POWERUP or not screen.enemy_on_screen(ram, slot, rec.width):
            continue
        d = _dx(ram, slot, rec, mario_x, True)
        if d < 0:
            continue
        elev = math.degrees(math.atan2(abs(enemy_centre_y(ram, slot) - mario_cy), max(d, 1)))
        w = max(0.0, 1.0 - elev / elevation_limit_deg)
        th = 2.0 * math.atan(rec.width / (2.0 * max(d, 1))) * w
        if th > best:
            best, best_d = th, d
    theta = {"L": best, "R": best}
    return theta, {s: theta[s] - prev_theta[s] for s in ("L", "R")}, {"L": best_d, "R": best_d}
