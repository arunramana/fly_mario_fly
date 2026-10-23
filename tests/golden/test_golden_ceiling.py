"""Golden: the headroom (rise available above Mario) and the loom factor min(1, rise / (h + 2)) equal the old tile-id scan on every
frame of two recorded sequences (1-2 pulse up to x ~ 900 with the Koopa and the low ceiling; 1-1 driver up to x ~ 1700 past the
87 / 88 blocks). 8 probes per frame: feet 176 / actual x box 16 / 24 x span of his own columns / the 160 px ahead."""
import pytest

from fly_mario_fly import registry
from fly_mario_fly.mario import ram as R
from fly_mario_fly.mario.env import MarioEnv
from fly_mario_fly.senses.kit.headroom import rise_available
from golden_data import buttons_of, expand


@pytest.mark.parametrize("level", ["1-2", "1-1"])
def test_headroom_equals_the_frozen_old_headroom(golden, level):
    rec = golden("ceiling.json.gz")[level]
    buttons, rises = expand(rec["buttons"]), expand(rec["rises"])
    assert len(rises) == rec["n_checked"]
    plugins = registry.list_plugins("objects")
    env = MarioEnv()
    env.reset(level)
    f = env.facts
    squeezed = 0
    for i, b in enumerate(buttons):
        out = env.step(buttons_of(b))
        if i >= len(rises):
            assert out.done                                         # the old run stopped because the episode ended
            break
        mx = R.mario_x(env.ram, f)
        world = [o for p in plugins.values() if p.kind == "terrain" for o in p.find(env.ram, f)]
        left = int(env.ram[f["ram"]["screen_page"]]) * 256 + int(env.ram[f["ram"]["screen_x"]])
        right = left + f["grid"]["screen_w"]                        # the finders see the visible screen only
        feet_now = int(env.ram[f["ram"]["mario_feet_y"]])
        probes = [(feet, h, x0, x1) for feet in (176, feet_now) for h in (16, 24) for x0, x1 in ((mx, mx + 12), (mx, min(mx + 160, right)))]
        for (feet, h, x0, x1), old_rise in zip(probes, rises[i]):
            new_rise = rise_available(world, f, x0, x1, feet, h)
            assert new_rise == old_rise, f"{level} frame {i} feet {feet} h {h} span {x0}-{x1}: {new_rise} != {old_rise}"
            assert min(1.0, new_rise / (16 + 2.0)) == min(1.0, old_rise / (16 + 2.0))
            squeezed += new_rise < rec["max_jump_height"]
    assert mx >= rec["stop_x"] - 40, f"{level}: the sequence only reached x {mx}"
    assert squeezed, f"{level}: never saw a ceiling lower than a full jump, so equality is vacuous"
