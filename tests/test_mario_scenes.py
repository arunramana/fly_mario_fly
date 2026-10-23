"""Scene modifiers: enemies stay gone, pickups go, terrain stays, start_at_x lands where asked."""
from fly_mario_fly import registry
from fly_mario_fly.mario import ram as R
from fly_mario_fly.mario.env import MarioEnv
from fly_mario_fly.mario.walker import Walker


def alive_enemies(env):
    f = env.facts
    return [s for s in range(f["grid"]["enemy_slots"]) if int(env.ram[f["ram"]["enemy_active"] + s])]


def run(level, modifier, params, frames, buttons=None):
    """Play `frames` frames with the scene applied; the default player is the scripted walker."""
    walker = Walker()
    buttons = buttons or (lambda i: walker.act(env))
    env = MarioEnv()
    env.reset(level)
    mod = registry.list_plugins("scenes")[modifier]
    mod.on_reset(env, params)
    seen_alive, seen_pits, last = 0, 0, None
    pits = registry.list_plugins("objects")["pit"]
    for i in range(frames):
        mod.on_frame(env, params)
        seen_alive += len(alive_enemies(env))                   # what the senses would see this frame
        seen_pits += bool(pits.find(env.ram, env.facts))
        last = env.step(buttons(i))
        if last.done:
            break
    return env, i + 1, seen_alive, seen_pits


def test_scene_plugins_registered():
    assert {"whole_level", "no_enemies", "keep_only", "start_at_x"} <= set(registry.list_plugins("scenes"))


def test_keep_only_pit_leaves_no_enemies_for_600_frames():
    env, frames, alive, seen_pits = run("1-1", "keep_only", {"types": ["pit"]}, 600)
    assert frames == 600, "Mario died with every enemy off"
    assert alive == 0
    assert R.mario_x(env.ram, env.facts) > 900           # he went on past the first Goombas and pipes


def test_whole_level_keeps_enemies():
    _, _, alive, _ = run("1-1", "whole_level", {}, 300, lambda i: ("right",))
    assert alive > 0


def test_no_enemies_matches_keep_only_nothing():
    _, _, a1, _ = run("1-1", "no_enemies", {}, 400)
    _, _, a2, _ = run("1-1", "keep_only", {"types": []}, 400)
    assert a1 == a2 == 0


def test_keep_only_goomba_keeps_goombas_but_not_koopas():
    env = MarioEnv()
    env.reset("1-1")
    mod = registry.list_plugins("scenes")["keep_only"]
    p = {"types": ["goomba"]}
    kinds, walker = set(), Walker()
    for i in range(1400):
        mod.on_frame(env, p)
        for s in alive_enemies(env):
            kinds.add(int(env.ram[env.facts["ram"]["enemy_type"] + s]))
        if env.step(walker.act(env)).done:
            break
    assert kinds == {0x06}


def test_start_at_x():
    env = MarioEnv()
    env.reset("1-1")
    registry.list_plugins("scenes")["start_at_x"].on_reset(env, {"x": 1500})
    f = env.facts
    assert R.mario_x(env.ram, f) >= 1500 and int(env.ram[f["ram"]["player_state"]]) == 0


def test_keep_only_leaves_terrain_alone():
    env = MarioEnv()
    env.reset("1-1")
    starts, keep = registry.list_plugins("scenes")["start_at_x"], registry.list_plugins("scenes")["keep_only"]
    starts.on_reset(env, {"x": 1300})
    keep.on_reset(env, {"types": ["pit"]})
    objs = registry.list_plugins("objects")
    assert objs["pit"].find(env.ram, env.facts), "the pit ahead of x 1300 should still be there"
    assert not alive_enemies(env)
