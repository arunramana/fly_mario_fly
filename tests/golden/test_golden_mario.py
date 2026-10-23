"""Golden: on three recorded button sequences, every frame's finders (enemies, walls, ? blocks, pits, mushroom) equal
what the old perception saw (frozen by tools/freeze_golden.py). Same intentional differences as the removed parity test (git tag `pre-cleanup`, tests/parity/test_mario_parity.py):
brick/usedblock/step are new types, the old "shell" kind is a koopa in its shell, pipe + step are compared per column height."""
import pytest

from fly_mario_fly import registry
from fly_mario_fly.mario import ram as R
from fly_mario_fly.mario.env import MarioEnv
from golden_data import buttons_of, expand

CASES = ["1-1/driver", "1-2/pulse", "1-1/mushroom"]
SEEN: dict = {}


def new_view(ram, facts, objs) -> dict:
    enemies = []
    for name in ("goomba", "koopa", "piranha"):
        for o in objs[name].find(ram, facts):
            kind = "shell" if o.state["shell"] else name
            enemies.append([kind, o.id, int(o.box.x), int(o.box.y), int(o.box.w), int(o.box.h)])
    walls = {}
    for name in ("pipe", "step"):
        for o in objs[name].find(ram, facts):
            for x in range(int(o.box.x), int(o.box.x + o.box.w), facts["grid"]["tile"]):
                walls[x] = int(o.box.h)
    mush = objs["mushroom"].find(ram, facts)
    return dict(
        enemies=sorted(enemies),
        walls=sorted([x, h] for x, h in walls.items()),
        pits=sorted([int(o.box.x), int(o.box.w)] for o in objs["pit"].find(ram, facts)),
        qblocks=sorted([int(o.box.x), o.state["row"]] for o in objs["qblock"].find(ram, facts)),
        mushroom=[int(mush[0].box.x), int(mush[0].box.y)] if mush else None,
    )


@pytest.mark.parametrize("case", CASES)
def test_finders_equal_the_frozen_old_view(golden, case):
    rec = golden("mario.json.gz")[case]
    buttons, views = expand(rec["buttons"]), expand(rec["views"])
    assert len(buttons) == len(views) == rec["frames"] > 60
    objs = registry.list_plugins("objects")
    env = MarioEnv()
    env.reset(rec["level"])
    facts = env.facts
    for i, (b, old) in enumerate(zip(buttons, views), 1):
        if rec["sweep"]:
            R.sweep_enemies(env, facts)                             # the mushroom case plays with enemies off
        out = env.step(buttons_of(b))
        new = new_view(env.ram, facts, objs)
        assert new == old, f"{case} frame {i}: {new} != {old}"
        for k, v in new.items():
            if v:
                SEEN.setdefault(case, set()).add(k)
        for e in new["enemies"]:
            SEEN[case].add(e[0])
        assert not out.done or i == len(buttons), f"{case}: the episode ended early at frame {i}"


def test_coverage_across_cases():
    """Between them the cases see every category (so equality is not vacuous). Runs after the cases above."""
    seen = set().union(*SEEN.values()) if SEEN else set()
    missing = {"enemies", "walls", "pits", "qblocks", "mushroom", "goomba"} - seen
    assert not missing, f"never exercised: {missing} (ran: {sorted(SEEN)})"
