# What this file does, in plain English:
# Pins the three hitbox numbers the distance calculation relies on (Goomba box 10 px wide starting 3 px right
# of its drawn x; Mario's front edge 13 px small / 14 px big) against the game's own collision-box bytes in RAM,
# read from a real 1-1 emulator state. If the engine bytes ever disagree, these constants are wrong.
"""Phase 5c step 4 hitbox constants vs RAM box bytes (Mario box 0x04AC-0x04AF, enemy box 0x04B0 + 4 * slot)."""
from __future__ import annotations

from brain.perception import ENEMY_BOX_LEFT_PX, ENEMY_HITBOX_W_PX, front_edge_offset_px
from mario.actions.actions import action_from_buttons
from mario.emulator.env import make_env

MARIO_BOX, ENEMY_BOX, MARIO_DRAWN_X, ENEMY_DRAWN_X, ENEMY_TYPE, ENEMY_ACTIVE, SIZE, GOOMBA = 0x04AC, 0x04B0, 0x03AD, 0x03AE, 0x16, 0x0F, 0x0756, 6


def _btn(right):
    return action_from_buttons(right=right, left=False, down=False, up=False, a=False, b=False)


def test_hitbox_constants_match_the_ram_boxes():
    env = make_env("1-1")
    env.reset()
    ram = env.unwrapped.ram
    for i in range(600):
        env.step(_btn(i < 90))
        box = [int(ram[ENEMY_BOX + k]) for k in range(4)]
        if ram[ENEMY_TYPE] == GOOMBA and ram[ENEMY_ACTIVE] and 0 < ram[ENEMY_DRAWN_X] < 200 and 0 < box[0] < box[2] < 255:
            break
    else:
        raise AssertionError("no on-screen Goomba found")
    assert box[0] - int(ram[ENEMY_DRAWN_X]) == ENEMY_BOX_LEFT_PX == 3
    assert box[2] - box[0] == ENEMY_HITBOX_W_PX == 10
    mario_x = int(ram[MARIO_DRAWN_X])
    assert int(ram[MARIO_BOX + 2]) - mario_x == front_edge_offset_px(0) == 13        # small Mario
    ram[0x0754] = 0                                                                  # big Mario (0x0754 = 0, size byte 1)
    ram[SIZE] = 1
    env.step(_btn(False))
    assert int(ram[MARIO_BOX + 2]) - int(ram[MARIO_DRAWN_X]) == front_edge_offset_px(1) == 14
    env.close()
