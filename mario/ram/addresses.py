# What this file does, in plain English:
# Lists the locations in the game's memory that this project reads: Mario's
# position and size, and the position, presence and type of the five enemy
# slots. It also holds the type code that marks a power-up, since power-ups
# share those slots with enemies.
"""mario/ram/addresses.py -- every SMB RAM address this project reads
(documented in docs/SPEC_jump.md section 2).
"""

from __future__ import annotations

ADDR_MARIO_X = 0x0086
ADDR_MARIO_PAGE = 0x006D
ADDR_MARIO_Y = 0x00B5
ADDR_MARIO_SIZE = 0x0756       # small=0, big/fiery>=1

ADDR_ENEMY_X = 0x0087
ADDR_ENEMY_Y = 0x00B6
ADDR_ENEMY_ACTIVE = 0x000F
ADDR_ENEMY_TYPE = 0x0016
N_ENEMY_SLOTS = 5

# Powerups (mushroom/flower/star/1-up) share the same 5 enemy-object slots
# as actual enemies (SPEC_odour.md section 1) -- they are approach targets,
# not threats. Classify through mario/entities/registry.py, not by comparing
# this byte directly.
POWERUP_ID = 0x2E
