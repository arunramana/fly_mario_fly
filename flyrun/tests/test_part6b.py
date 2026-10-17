"""Part 6b (audit 006): fair shuffle, honest episode counting, guard inside _one."""
import numpy as np
import pytest

from flyrun import fitness
from flyrun.brain import CACHE
from flyrun.episodes4 import aggregate
from flyrun.knobs import INVENTED, Knobs
from flyrun.shuffle import build_W, load_counts, renormalised_shuffle


def test_counts_rebuild_W_exactly():
    counts, signs, _ = load_counts()
    assert np.array_equal(build_W(counts, signs), np.load(CACHE / "W_steer.npy"))


@pytest.mark.parametrize("seed", range(5))
def test_rn_shuffle_is_fair(seed):
    W = np.load(CACHE / "W_steer.npy")
    S = np.load(CACHE / f"W_steer_shuf{seed}_rn.npy")
    assert np.allclose(np.abs(S).sum(1), np.abs(W).sum(1))                    # row sums: 1.0 or 0, as the real matrix
    assert ((W != 0).sum(0) == (S != 0).sum(0)).all()                          # out-degree
    assert ((W != 0).sum(1) == (S != 0).sum(1)).all()                          # in-degree
    assert ((W > 0).sum(0) == (S > 0).sum(0)).all() and ((W < 0).sum(0) == (S < 0).sum(0)).all()   # source signs
    assert not np.diag(S).any()
    assert (W != S).sum() > 0.5 * (W != 0).sum()


def test_rn_shuffle_reproducible():
    assert np.array_equal(renormalised_shuffle(2)[0], np.load(CACHE / "W_steer_shuf2_rn.npy"))


def test_aggregate_counts_distinct_trajectories():
    r = lambda mx, x: dict(max_x=mx, x_at_end=x, fitness=0, flag_get=False, a_frac=0, blind_presses=0, n_onsets=0,
                           end_reason="died", cause="c")
    a = aggregate([r(100, 90), r(100, 90), r(200, 190)])
    assert (a["n_episodes"], a["n_traj"]) == (3, 2)


def test_fitness_one_rejects_scripted_frames(brain):
    fitness._BRAIN = brain
    with pytest.raises(RuntimeError, match="scripted"):
        fitness._one((Knobs(), 0, None, dict(takeover_x=250, max_frames=60)))


def test_every_invented_knob_is_registered():
    from dataclasses import fields
    assert {f.name for f in fields(Knobs)} <= set(INVENTED)
