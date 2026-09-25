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
# Was 0x00B5 -- checked directly against gym_super_mario_bros.smb_env's own
# source and cross-verified bit-exact against info['y_pos'] over a real
# 106-frame episode (0 mismatches): 0x00B5 is "_y_viewport", a coarse 0-5
# viewport-REGION flag (1 = normal, >1 = falling into a hole), not a pixel
# position -- confirmed empirically too: constant at 1 across a full
# 689-frame run including 9 escape jumps. 0x03B8 ("_y_pixel" in that same
# source) is the real vertical pixel position; info['y_pos'] itself is
# `255 - ram[0x03B8]` in the normal (non-hole) case. The only live
# consumer (run_steering.inject_mushroom's synthetic-mushroom placement,
# opt-in via inject_frame=, exercised by no golden) is otherwise
# unaffected.
ADDR_MARIO_Y = 0x03B8
ADDR_PLAYER_STATE = 0x001D     # 0 == on the ground (1 jumping, 2 falling, 3 climbing)
ADDR_MARIO_SIZE = 0x0756       # small=0, big/fiery>=1

ADDR_ENEMY_X = 0x0087
ADDR_ENEMY_Y = 0x00CF
ADDR_ENEMY_PAGE = 0x006E       # Enemy_PageLoc + slot: which 256px page the enemy's x byte is on
ADDR_ENEMY_ACTIVE = 0x000F
ADDR_ENEMY_TYPE = 0x0016
N_ENEMY_SLOTS = 5

# Powerups (mushroom/flower/star/1-up) share the same 5 enemy-object slots
# as actual enemies (SPEC_odour.md section 1) -- they are approach targets,
# not threats. Classify through mario/entities/registry.py, not by comparing
# this byte directly.
POWERUP_ID = 0x2E
