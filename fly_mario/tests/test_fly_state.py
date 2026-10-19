"""Saved moments: brain state keyed by MaleCNS body id round-trips, and loads into a bigger brain."""
import os

import numpy as np
import pytest

from fly_mario.fly.brain import Brain
from fly_mario.fly.spec import BrainSpec


def _toy(ids, seed=0):
    rng = np.random.default_rng(seed)
    n = len(ids)
    return Brain(BrainSpec(), rng.normal(size=(n, n)) / n, ids, ["LC4"] * n, ["L"] * n, np.ones(n))


def test_round_trip():
    b = _toy([11, 22, 33, 44])
    h = np.array([0.5, 0.0, 2.0, 7.25])
    assert np.array_equal(b.set_state(b.get_state(h)), h)


def test_state_is_keyed_by_body_id_not_row():
    b = _toy([11, 22, 33])
    assert b.get_state(np.array([1.0, 2.0, 3.0])) == {11: 1.0, 22: 2.0, 33: 3.0}
    reordered = _toy([33, 11, 22])
    assert reordered.set_state({11: 1.0, 22: 2.0, 33: 3.0}).tolist() == [3.0, 1.0, 2.0]


def test_smaller_into_bigger_leaves_new_neurons_at_rest():
    small, big = _toy([1, 2, 3]), _toy([1, 2, 3, 4, 5])
    h = big.set_state(small.get_state(np.array([1.0, 2.0, 3.0])))
    assert h.tolist() == [1.0, 2.0, 3.0, 0.0, 0.0]


def test_bigger_into_smaller_drops_unknown_ids():
    small, big = _toy([1, 2, 3]), _toy([1, 2, 3, 4, 5])
    assert small.set_state(big.get_state(np.arange(1.0, 6.0))).tolist() == [1.0, 2.0, 3.0]


def test_set_state_accepts_json_string_keys():
    b = _toy([7, 8])
    assert b.set_state({"7": 1.5, "8": 2.5}).tolist() == [1.5, 2.5]


@pytest.mark.skipif(not os.environ.get("FLY_MARIO_DATA"), reason="FLY_MARIO_DATA not set")
def test_real_636_into_907_and_continue_running():
    from fly_mario.fly.brain import build_brain
    small, big = build_brain(BrainSpec()), build_brain(BrainSpec(mechanisms=("hearing", "attraction", "aversion")))
    h = small.advance(small.new_state(), small.drive({"LPLC2_R": 0.4, "LC4_R": 0.2}))
    assert h.max() > 0
    h_big = big.set_state(small.get_state(h))
    assert np.array_equal(h_big[:small.n], h)                  # base rows keep their rates
    assert not h_big[small.n:].any()                           # everything new is at rest
    assert big.get_state(h_big).keys() >= small.get_state(h).keys()
    big.advance(h_big, big.drive({"LPLC2_R": 0.4}))             # and the bigger brain runs on from it
