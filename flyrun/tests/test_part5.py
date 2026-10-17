import numpy as np

from flyrun.brain import CACHE
from flyrun.shuffle import degree_shuffle


def test_shuffle_preserves_degrees_and_signs():
    W = np.load(CACHE / "W_steer.npy")
    S = np.load(CACHE / "W_steer_shuf0.npy")
    assert not np.array_equal(W, S)
    assert ((W != 0).sum(0) == (S != 0).sum(0)).all()     # out-degree per neuron
    assert ((W != 0).sum(1) == (S != 0).sum(1)).all()     # in-degree per neuron
    assert ((W > 0).sum(0) == (S > 0).sum(0)).all() and ((W < 0).sum(0) == (S < 0).sum(0)).all()
    for j in range(W.shape[0]):                           # each neuron's outgoing weights, as a multiset
        assert np.allclose(np.sort(W[:, j]), np.sort(S[:, j]))
    assert not np.diag(S).any()
    assert (W != S).sum() > 0.5 * (W != 0).sum()          # actually rewired, not a token swap


def test_shuffle_is_reproducible_from_seed():
    W = np.load(CACHE / "W_steer.npy")
    assert np.array_equal(degree_shuffle(W, seed=0)[0], np.load(CACHE / "W_steer_shuf0.npy"))
