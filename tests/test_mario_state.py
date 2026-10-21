"""Save/load: loading a state and replaying the same buttons gives identical RAM on every frame."""
import numpy as np
import pytest

from fly_mario.mario import ram as R
from fly_mario.mario.env import MarioEnv, level_ids, env_id

SAVE_AT, PLAY = 150, 200


def buttons(i):
    return ("right", "A") if i % 30 < 16 else ("right",)


def play(env, start, n, sweep=True):
    rams = []
    for i in range(start, start + n):
        if sweep:                       # RAM pokes go through the state log too
            R.sweep_enemies(env, env.facts)
        rams.append(env.step(buttons(i)).ram)
    return rams


@pytest.mark.parametrize("level", ["1-1", "1-2"])
def test_load_replays_identically(level):
    env = MarioEnv()
    env.reset(level, noop=5)
    play(env, 0, SAVE_AT)
    blob = env.save_state()
    saved_ram = env.ram.copy()
    first = play(env, SAVE_AT, PLAY)

    out = env.load_state(blob)
    assert np.array_equal(out.ram, saved_ram)
    second = play(env, SAVE_AT, PLAY)
    assert len(first) == len(second) == PLAY
    for k, (a, b) in enumerate(zip(first, second)):
        assert np.array_equal(a, b), f"{level}: RAM differs {k} frames after the load"


def test_load_into_a_fresh_env():
    a = MarioEnv()
    a.reset("1-1")
    play(a, 0, 100, sweep=False)
    blob = a.save_state()
    want = play(a, 100, 50, sweep=False)
    b = MarioEnv()
    b.load_state(blob)
    got = play(b, 100, 50, sweep=False)
    assert all(np.array_equal(x, y) for x, y in zip(want, got))


def test_all_35_envs_are_selectable():
    ids = level_ids()
    assert len(ids) == 35
    env = MarioEnv()
    for level in ids:
        env.reset(level)
        env.step(("right",))
        assert env.ram.shape == (2048,), level
    assert env_id("4-3", "v2") == "SuperMarioBros-4-3-v2"
    env.close()
