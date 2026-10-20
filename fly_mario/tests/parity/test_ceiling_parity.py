"""Parity: the new headroom (terrain boxes of the frame) equals the old level.headroom (tile-id scan) frame by frame.

Driven by the fixed pulse sequence (right held, A for 16 of every 30 frames) on 1-2 up to x ~ 900 (the Koopa and the
low ceiling around it) and the old scripted driver on 1-1 up to x ~ 1700 (87 / 88 blocks). Per frame, for a small and a big Mario, standing
and at his actual feet, over his own columns and over the 160 px ahead (clipped to the visible screen), the rise and the loom factor
min(1, rise / (h + 2)) must match.
"""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]          # worktree root, where the old `flyrun` package lives
sys.path.insert(0, str(REPO_ROOT))

from fly_mario import registry                           # noqa: E402
from fly_mario.mario import ram as R                      # noqa: E402
from fly_mario.mario.env import MarioEnv                  # noqa: E402
from fly_mario.senses.kit.headroom import rise_available  # noqa: E402


def pulse(i, period=30, hold=16):
    return ("right", "A") if i % period < hold else ("right",)


def driver(env):
    """1-1: the old scripted driver plays (the pulse dies at x 702); it reaches the 87 / 88 blocks past x 1500."""
    from flyrun import scripted
    drv = scripted.Driver()
    return lambda i: ("right", "A") if drv.act(env.ram) == 2 else ("right",)


def world_of(ram, facts, plugins):
    return [o for p in plugins.values() if p.kind == "terrain" for o in p.find(ram, facts)]


@pytest.mark.parametrize("level,stop_x", [("1-2", 900), ("1-1", 1700)])
def test_headroom_matches_old(level, stop_x):
    os.environ["FLYRUN_LEVEL"] = level
    from flyrun import level as OL
    from flyrun.knobs import MAX_JUMP_HEIGHT
    plugins = registry.list_plugins("objects")
    env = MarioEnv()
    env.reset(level)
    f = env.facts
    pick = driver(env) if level == "1-1" else pulse
    squeezed = 0
    for i in range(4000):
        out = env.step(pick(i))
        if out.done:
            break
        mx = R.mario_x(env.ram, f)
        world = world_of(env.ram, f, plugins)
        left = int(env.ram[f["ram"]["screen_page"]]) * 256 + int(env.ram[f["ram"]["screen_x"]])
        right = left + f["grid"]["screen_w"]       # the finders see the visible screen only; a creature is always on it
        feet_now = int(env.ram[f["ram"]["mario_feet_y"]])
        for feet in (176, feet_now):
            for box_h in (16, 24):
                for x0, x1 in ((mx, mx + 12), (mx, min(mx + 160, right))):
                    _, old_rise = OL.headroom(env.ram, x0, x1, feet, box_h)
                    new_rise = rise_available(world, f, x0, x1, feet, box_h)
                    assert new_rise == old_rise, f"{level} frame {i} feet {feet} h {box_h} span {x0}-{x1}: {new_rise} != {old_rise}"
                    old_f = min(1.0, old_rise / (16 + 2.0))
                    assert min(1.0, new_rise / (16 + 2.0)) == old_f
                    squeezed += new_rise < MAX_JUMP_HEIGHT
        if mx >= stop_x:
            break
    assert mx >= stop_x - 40, f"{level}: the sequence only reached x {mx}"
    assert squeezed, f"{level}: never saw a ceiling lower than a full jump, so equality is vacuous"
