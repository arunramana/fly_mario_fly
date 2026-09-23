"""mario/ram/addresses.py -- every SMB RAM address this project reads, in
one place. docs/SPEC_jump.md section 2's own table documents these; the
code itself had them scattered (ADDR_MARIO_X/PAGE/ENEMY_* in run_mario.py,
ADDR_MARIO_SIZE in run_steering.py, Mario-y and Enemy-y as bare literals
0x00B5/0x00B6 in run_steering.py, never named at all) -- see
docs/REFACTOR_PLAN.md phase 2's report for the full duplication writeup.
Consolidated here, values unchanged.
"""

from __future__ import annotations

ADDR_MARIO_X = 0x0086
ADDR_MARIO_PAGE = 0x006D
ADDR_MARIO_Y = 0x00B5          # was a bare literal in run_steering.py
ADDR_MARIO_SIZE = 0x0756       # small=0, big/fiery>=1

ADDR_ENEMY_X = 0x0087
ADDR_ENEMY_Y = 0x00B6          # was a bare literal in run_steering.py's inject_mushroom
ADDR_ENEMY_ACTIVE = 0x000F
ADDR_ENEMY_TYPE = 0x0016
N_ENEMY_SLOTS = 5

# Powerups (mushroom/flower/star/1-up) share the same 5 enemy-object slots
# as actual enemies (SPEC_odour.md section 1) -- they are approach targets,
# not threats. This one byte value is the ROM fact mario/entities/registry.py
# centralises: before phase 2 it was checked independently, with the same
# literal comparison, in three separate places (run_mario.py's enemy_thetas,
# run_steering.py's mushroom_odor and goomba_odor).
POWERUP_ID = 0x2E
