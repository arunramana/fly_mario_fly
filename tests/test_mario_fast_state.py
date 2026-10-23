"""The in-memory fast path of load_state gives the same game as the replay, and never breaks reset."""
import numpy as np

from fly_mario_fly.mario import ram as R
from fly_mario_fly.mario.env import MarioEnv


def play(env, start, n):
    rams = []
    for i in range(start, start + n):
        R.sweep_enemies(env, env.facts)
        rams.append(env.step(("right", "A") if i % 30 < 16 else ("right",)).ram)
    return rams


def same(a, b):
    return len(a) == len(b) and all(np.array_equal(x, y) for x, y in zip(a, b))


def test_fast_path_equals_replay():
    env = MarioEnv()
    env.reset("1-1")
    play(env, 0, 120)
    blob = env.save_state()
    want = play(env, 120, 80)
    env.load_state(blob)
    assert env._slot is not None                      # this load took the fast path
    assert same(want, play(env, 120, 80))


def test_older_blob_falls_back_to_replay():
    env = MarioEnv()
    env.reset("1-1")
    play(env, 0, 100)
    older = env.save_state()
    want = play(env, 100, 60)
    play(env, 160, 20)
    env.save_state()                                  # the slot now holds a newer moment
    env.load_state(older)                             # token mismatch: replay
    assert same(want, play(env, 100, 60))


def test_reset_after_save_gives_the_real_start():
    fresh = MarioEnv()
    fresh.reset("1-1")
    clean = fresh.step(("right",)).ram
    env = MarioEnv()
    env.reset("1-1")
    play(env, 0, 50)
    env.save_state()
    env.reset("1-1")
    assert np.array_equal(env.step(("right",)).ram, clean)
