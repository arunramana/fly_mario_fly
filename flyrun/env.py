"""Mario 1-1 emulator and RAM readers (nb 05, 06, 09)."""
import setuptools  # noqa: F401  -- must precede gym on Python 3.12 (distutils shim)

import gym
import numpy
import gym_super_mario_bros
from nes_py.wrappers import JoypadSpace

assert numpy.__version__.startswith("1.26"), numpy.__version__
assert gym.__version__.startswith("0.23"), gym.__version__

# Our own short button list (the tutorials used SIMPLE_MOVEMENT).
COMBOS = [["NOOP"], ["right"], ["right", "A"], ["left"], ["left", "A"]]
NOOP, RIGHT, RIGHT_A, LEFT, LEFT_A = range(5)
NAMES = ["NOOP", "R", "R+A", "L", "L+A"]

ADDR_MARIO_PAGE, ADDR_MARIO_X = 0x006D, 0x0086
ADDR_ENEMY_ACTIVE, ADDR_ENEMY_TYPE = 0x000F, 0x0016
ADDR_ENEMY_PAGE, ADDR_ENEMY_X = 0x006E, 0x0087
N_ENEMY_SLOTS, POWERUP_ID = 5, 0x2E


def make_env():
    # FLYRUN_LEVEL (a harness switch, default "1-1"): L2 runs the same fly on "1-2"
    import os
    env = gym_super_mario_bros.make(f"SuperMarioBros-{os.environ.get('FLYRUN_LEVEL', '1-1')}-v0")
    return JoypadSpace(env, COMBOS)


def mario_x(ram):
    return int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X])


def nearest_threat_d(ram):
    """(mario_x, px distance to the nearest active non-powerup enemy ahead, or None)."""
    mx = mario_x(ram)
    best = None
    for slot in range(N_ENEMY_SLOTS):
        if not int(ram[ADDR_ENEMY_ACTIVE + slot]):
            continue
        if int(ram[ADDR_ENEMY_TYPE + slot]) == POWERUP_ID:
            continue
        ex = int(ram[ADDR_ENEMY_PAGE + slot]) * 256 + int(ram[ADDR_ENEMY_X + slot])
        d = ex - mx
        if d < 0:
            continue
        if best is None or d < best:
            best = d
    return mx, best


def threats_ahead(ram):
    """[(slot, d)] for every active non-powerup enemy at or ahead of Mario (for the sum combine)."""
    mx = mario_x(ram)
    out = []
    for slot in range(N_ENEMY_SLOTS):
        if not int(ram[ADDR_ENEMY_ACTIVE + slot]) or int(ram[ADDR_ENEMY_TYPE + slot]) == POWERUP_ID:
            continue
        d = int(ram[ADDR_ENEMY_PAGE + slot]) * 256 + int(ram[ADDR_ENEMY_X + slot]) - mx
        if d >= 0:
            out.append((slot, d))
    return out
