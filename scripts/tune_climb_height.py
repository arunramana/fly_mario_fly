"""
tune_climb_height.py -- SPEC_habituation.md follow-up: calibrate
CLIMB_JUMP_FRAMES against real wall height, the way 007 calibrated GAP_GAIN
against pit width. Scripted, not emergent -- run right+B for a fixed
approach, stop the instant tile_ram.solid_ahead(ram) is true (a real
ground-connected wall, not floating decoration -- solid_ahead's BODY_ROWS
already excludes those), measure its height, then re-run the SAME
deterministic approach with a jump of hold=H triggered at that exact frame,
sweeping H, and check whether Mario ends up past the wall's far column.

    .venv/Scripts/python.exe -m scripts.tune_climb_height
"""
from __future__ import annotations

import sys
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")

import setuptools  # noqa: F401
import gym_super_mario_bros
from nes_py.wrappers import JoypadSpace

from mario.ram import tile_ram

MOVES = [["right", "B"], ["right", "A", "B"]]
RUN, JUMP = 0, 1

CLEAR_MARGIN_TILES = 2   # how far past the wall's far edge counts as "cleared"
POST_JUMP_WINDOW = 90    # frames to watch after the jump for clearance/failure


def contiguous_height(buf1, buf2, col):
    h = 0
    for row in range(tile_ram.GROUND_ROW - 1, -1, -1):
        t = tile_ram._tile_at_abs_col(buf1, buf2, col, row)
        if t not in (0, None):
            h += 1
        else:
            break
    return h


def find_first_wall(level="1-1", max_frames=800):
    """Run right+B until tile_ram.solid_ahead first fires. Returns the
    frame it happened at and the wall's height/far column.

    A dumb proximity-triggered hop (any active enemy within 24px ahead,
    ANY type -- this is a scratch survival heuristic for the calibration
    script only, not the real escape circuit) keeps Mario alive long
    enough to actually reach a wall; without it he walks straight into the
    first Goomba, which tells us nothing about wall height."""
    from run_mario import ADDR_ENEMY_X, ADDR_ENEMY_ACTIVE, N_ENEMY_SLOTS, ADDR_MARIO_X

    env = gym_super_mario_bros.make(f"SuperMarioBros-{level}-v0")
    env = JoypadSpace(env, MOVES)
    obs = env.reset()
    ram = env.unwrapped.ram
    hop = 0
    for frame in range(max_frames):
        if tile_ram.solid_ahead(ram):
            col0 = tile_ram._mario_abs_col(ram)
            buf1, buf2 = tile_ram._grids(ram)
            height = contiguous_height(buf1, buf2, col0 + 1)
            far_col = col0 + 1
            while contiguous_height(buf1, buf2, far_col) > 0:
                far_col += 1
            env.close()
            return frame, col0, height, far_col
        mario_x = int(ram[ADDR_MARIO_X])
        if hop == 0:
            for i in range(N_ENEMY_SLOTS):
                if ram[ADDR_ENEMY_ACTIVE + i] and 0 < int(ram[ADDR_ENEMY_X + i]) - mario_x < 24:
                    hop = 20
                    break
        action = JUMP if hop > 0 else RUN
        if hop > 0:
            hop -= 1
        obs, r, done, info = env.step(action)
        if done:
            env.close()
            return None, None, None, None
    env.close()
    return None, None, None, None


def test_hold(level, wall_frame, hold, max_frames):
    """Replay the identical deterministic approach (same survival hop
    heuristic as find_first_wall, so the pre-wall trajectory matches
    exactly), jump for `hold` frames starting at wall_frame, then watch
    whether Mario clears it."""
    from run_mario import ADDR_ENEMY_X, ADDR_ENEMY_ACTIVE, N_ENEMY_SLOTS, ADDR_MARIO_X

    env = gym_super_mario_bros.make(f"SuperMarioBros-{level}-v0")
    env = JoypadSpace(env, MOVES)
    obs = env.reset()
    ram = env.unwrapped.ram
    hop = 0
    for frame in range(max_frames):
        if frame < wall_frame:
            mario_x = int(ram[ADDR_MARIO_X])
            if hop == 0:
                for i in range(N_ENEMY_SLOTS):
                    if ram[ADDR_ENEMY_ACTIVE + i] and 0 < int(ram[ADDR_ENEMY_X + i]) - mario_x < 24:
                        hop = 20
                        break
            action = JUMP if hop > 0 else RUN
            if hop > 0:
                hop -= 1
        elif frame < wall_frame + hold:
            action = JUMP
        else:
            action = RUN
        obs, r, done, info = env.step(action)
        if done:
            env.close()
            return "died", frame
    mario_x_abs = int(ram[0x006D]) * 256 + int(ram[0x0086])
    env.close()
    return "survived", mario_x_abs


def main():
    print("Finding the first real (ground-connected) wall on a plain right+B run...")
    frame, col0, height, far_col = find_first_wall()
    if frame is None:
        sys.exit("No wall found / died before finding one -- widen max_frames.")
    print(f"  found at frame {frame}, mario col={col0}, wall height={height} tiles, "
          f"spans to col={far_col - 1}\n")

    clear_col = far_col + CLEAR_MARGIN_TILES
    print(f"Sweeping jump hold duration (trigger frame fixed at {frame}), "
          f"'cleared' = abs_col >= {clear_col} within {POST_JUMP_WINDOW} frames after triggering...\n")
    for hold in (8, 10, 12, 14, 16, 18, 20, 22, 25, 30, 35, 40):
        status, result = test_hold("1-1", frame, hold, frame + hold + POST_JUMP_WINDOW)
        if status == "died":
            print(f"  hold={hold:3d}: DIED at frame {result}")
        else:
            cleared = result // 16 >= clear_col
            print(f"  hold={hold:3d}: survived, abs_x={result} (col={result // 16}) "
                  f"-> {'CLEARED' if cleared else 'blocked'}")


if __name__ == "__main__":
    main()
