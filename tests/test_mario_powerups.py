"""The four power-ups are four object types: block contents from the level database (1-1) decide which one appears."""
import os

import pytest

from fly_mario import registry
from fly_mario.mario import ram as R
from fly_mario.mario import walker
from fly_mario.mario.env import MarioEnv

NAMES = ["mushroom", "fire_flower", "star", "one_up"]


def still_dir():
    d = os.environ.get("POWERUP_STILLS")
    if d:
        os.makedirs(d, exist_ok=True)
    return d


def save_still(env, box, path):
    from PIL import Image, ImageDraw
    f, r = env.facts, env.facts["ram"]
    left = int(env.ram[r["screen_page"]]) * 256 + int(env.ram[r["screen_x"]])
    img = Image.fromarray(env.step(()).frame).convert("RGB") if False else Image.fromarray(env._gym.unwrapped.screen.copy())
    d = ImageDraw.Draw(img)
    x0, y0 = box.x - left, box.y + 32
    d.rectangle([x0, y0, x0 + box.w - 1, y0 + box.h - 1], outline=(255, 0, 0))
    img.resize((img.width * 3, img.height * 3), Image.NEAREST).save(path)


def hit_block(env, bx, tries=12):
    """Walk to just left of the block at world x `bx`, then jump under it until a power-up appears in slot 5."""
    facts = env.facts
    r, slot = facts["ram"], facts["grid"]["powerup_slot"]
    walker.walk_to(env, bx - 14)
    still = 0
    for _ in range(600):                  # nudge him under the block (its width plus his 12 px), then wait until he is still
        R.sweep_enemies(env, facts)
        x = R.mario_x(env.ram, facts)
        env.step(("right",) if x < bx - 4 else ("left",) if x > bx + 4 else ())
        still = still + 1 if R.mario_x(env.ram, facts) == x and bx - 4 <= x <= bx + 4 else 0
        if still >= 10:
            break
    for _ in range(tries):
        for i in range(40):
            R.sweep_enemies(env, facts)
            env.step(("A",))
            if int(env.ram[r["enemy_active"] + slot]):
                return True
        for _ in range(20):
            R.sweep_enemies(env, facts)
            env.step(())
    return False


def found(env):
    objs = registry.list_plugins("objects")
    return {n: objs[n].find(env.ram, env.facts) for n in NAMES}


def check(env, want, tag):
    hits = found(env)
    assert [n for n in NAMES if hits[n]] == [want], hits
    box = hits[want][0].box
    assert (box.w, box.h) == (16, 16)
    d = still_dir()
    if d:
        save_still(env, box, os.path.join(d, f"{tag}.png"))
    return box


def test_registered_as_pickups():
    objs = registry.list_plugins("objects")
    for n in NAMES:
        assert objs[n].kind == "pickup" and objs[n].default_loom_shape == "own_box"


@pytest.mark.parametrize("level_x,want,big,tag", [
    (336, "mushroom", False, "mushroom"),
    (1248, "fire_flower", True, "fire_flower"),
    (1616, "star", False, "star"),
    (1024, "one_up", False, "one_up"),
])
def test_block_gives_the_right_powerup(level_x, want, big, tag):
    env = MarioEnv()
    env.reset("1-1")
    f = env.facts
    if big:
        env.poke(0x0754, 0)               # PlayerSize: 0 = big
        env.poke(f["ram"]["power"], 1)
    assert hit_block(env, level_x), "no power-up appeared"
    for _ in range(60):                   # let it finish rising out of the block
        R.sweep_enemies(env, f)
        env.step(())
    check(env, want, tag)
    env.close()
