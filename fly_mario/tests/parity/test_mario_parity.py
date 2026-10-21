"""Parity: on recorded frames the new object finders see what the old perception sees.

Only tests/parity may import old-repo code (the frozen `flyrun` package at the repo root). The old functions
are called on the RAM of OUR emulator wrapper, so this checks the finders, not the emulator.

Compared on every frame of a fixed button sequence:
  enemies   old senses_v2.enemy_boxes        vs  goomba/koopa/piranha finders (old kind "shell" = koopa with state shell)
  walls     old level.scan_visible walls     vs  pipe + step finders, compared per column height
  pits      old level.scan_visible pits      vs  pit finder
  ? blocks  old level.scan_blocks            vs  qblock finder
  mushroom  old senses_v2.mushroom           vs  mushroom finder
Intentional differences (no old counterpart, or a deliberate change) are listed in DIFFERENCES below.
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

pytestmark = pytest.mark.parity_old

DIFFERENCES = """
- brick, usedblock, step: new types. The old code only had walls (pipe + stair columns, one set) and tile ids for ceilings.
  Pipe and step are compared together, per column height, so the old merged wall set is reproduced.
- Koopa: the old "shell" kind is a koopa with state['shell']; piranha is unchanged.
- Enemy type bytes: the old code chose them per level (1-1: goomba 0x06, koopa 0x00; 1-2 adds red koopa 0x03 and
  piranha 0x0D). They are now game-wide facts. Same result on 1-1, which has no 0x03 / 0x0D.
- Faces: the old code reported a face's height relative to Mario's own column and merged across tile types;
  the finders report each type's raw stack from the ground.
- Pit: the new box also carries a height (the two ground rows) and an `open` flag when it runs off the screen.
"""


def old_modules(level):
    os.environ["FLYRUN_LEVEL"] = level
    from flyrun import env as OE, level as OL, senses_v2 as OS
    return OE, OL, OS


def old_view(ram, OE, OL, OS):
    enemies = [(s, int(ram[OE.ADDR_ENEMY_TYPE + s]), int(ram[OS.ADDR_ENEMY_STATE + s]),
                int(ram[OE.ADDR_ENEMY_PAGE + s]) * 256 + int(ram[OE.ADDR_ENEMY_X + s]), int(ram[OS.ADDR_ENEMY_Y + s]))
               for s in range(OE.N_ENEMY_SLOTS) if int(ram[OE.ADDR_ENEMY_ACTIVE + s])]
    walls, pits = OL.scan_visible(ram, rim=True)
    threats = OS.enemy_boxes(enemies, walls)
    return dict(
        enemies=sorted((t.kind, t.ident[1], t.x, t.top, t.w, t.h) for t in threats),
        walls=dict(walls),
        pits=sorted(pits),
        qblocks=sorted(OL.scan_blocks(ram)),
        mushroom=OS.mushroom(ram),
    )


def new_view(ram, facts, objs):
    enemies = []
    for name in ("goomba", "koopa", "piranha"):
        for o in objs[name].find(ram, facts):
            kind = "shell" if o.state["shell"] else name
            enemies.append((kind, o.id, int(o.box.x), int(o.box.y), int(o.box.w), int(o.box.h)))
    walls = {}
    for name in ("pipe", "step"):
        for o in objs[name].find(ram, facts):
            for x in range(int(o.box.x), int(o.box.x + o.box.w), facts["grid"]["tile"]):
                walls[x] = int(o.box.h)
    mush = objs["mushroom"].find(ram, facts)
    return dict(
        enemies=sorted(enemies),
        walls=walls,
        pits=sorted((int(o.box.x), int(o.box.w)) for o in objs["pit"].find(ram, facts)),
        qblocks=sorted((int(o.box.x), o.state["row"]) for o in objs["qblock"].find(ram, facts)),
        mushroom=(int(mush[0].box.x), int(mush[0].box.y)) if mush else None,
    )


def driver_sequence(level):
    """1-1: the old scripted driver plays (it reaches the flag); recorded here as plain buttons."""
    from flyrun import scripted
    drv, env = scripted.Driver(), MarioEnv()
    env.reset(level)
    seq = []
    for _ in range(2200):
        b = ("right", "A") if drv.act(env.ram) == 2 else ("right",)
        seq.append(b)
        if env.step(b).done:
            break
    return seq


def pulse_sequence(n=2500, period=30, hold=16):
    return [("right", "A") if i % period < hold else ("right",) for i in range(n)]


CASES = [("1-1", "driver"), ("1-2", "pulse"), ("1-1", "mushroom")]
SEEN: dict = {}


def run_case(level, seq_kind):
    OE, OL, OS = old_modules(level)
    objs = registry.list_plugins("objects")
    env = MarioEnv()
    env.reset(level)
    facts = env.facts
    if seq_kind == "driver":
        seq = driver_sequence(level)
    elif seq_kind == "pulse":
        seq = pulse_sequence()
    else:
        seq = None
    hit = None            # mushroom case: frames since the jump started
    frames, i = 0, 0
    while True:
        if seq is not None:
            if i >= len(seq):
                break
            b = seq[i]
        else:
            # walk to 18 px short of the ? block at x 336 (enemies off, as in the old O0 setup), hit it from
            # below with Right+A for 14 frames, then idle while the mushroom comes out
            R.sweep_enemies(env, facts)
            if hit is None and R.mario_x(env.ram, facts) >= 318:
                hit = 0
            b = ("right",) if hit is None else (("right", "A") if hit < 14 else ())
            if hit is not None:
                hit += 1
                if hit > 80:
                    break
        out = env.step(b)
        i += 1
        old, new = old_view(env.ram, OE, OL, OS), new_view(env.ram, facts, objs)
        assert new == old, f"{level} {seq_kind} frame {i}: {new} != {old}"
        for k, v in new.items():
            if v:
                SEEN.setdefault((level, seq_kind), set()).add(k)
        for e in new["enemies"]:
            SEEN[(level, seq_kind)].add(e[0])
        frames += 1
        if out.done:
            break
    return frames


@pytest.mark.parametrize("level,seq_kind", CASES)
def test_parity(level, seq_kind):
    frames = run_case(level, seq_kind)
    assert frames > 60
    # the sequence must actually exercise the finders: something other than flat ground was seen
    assert SEEN[(level, seq_kind)] & {"walls", "pits", "qblocks", "enemies", "mushroom"}


def test_coverage_across_cases():
    """Between them the cases see every old category (so equality is not vacuous)."""
    seen = set().union(*SEEN.values()) if SEEN else set()
    missing = {"enemies", "walls", "pits", "qblocks", "mushroom", "goomba"} - seen
    assert not missing, f"never exercised: {missing} (ran: {sorted(SEEN)})"
