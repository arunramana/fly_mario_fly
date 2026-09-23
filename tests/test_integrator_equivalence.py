# What this file does, in plain English:
# Checks that the shared neuron-update code (Integrator) gives exactly the
# same numbers, bit for bit, as the two update routines in
# fly/network/dynamics.py, with and without random noise and with and
# without "spiking" neurons that fire in pulses. It uses small random test
# networks, so a mismatch shows up here before the slower full-game tests.
"""
fly.network.integrator.Integrator is bit-exact against
fly.network.dynamics.step() (no spike index) and dynamics.HybridState
(with one). A drift shows up here, localised, before the slower goldens.
"""
from __future__ import annotations

import numpy as np

from fly.network import dynamics
from fly.network.integrator import Integrator


def test_plain_step_matches_dynamics_step_bit_exact():
    rng = np.random.default_rng(0)
    K = 40
    W = rng.normal(size=(K, K)) * 0.1
    h = np.zeros(K)
    h_ref = np.zeros(K)
    integrator = Integrator()  # no spike_idx -- the four non-spiking circuits' shape
    noise = dynamics.NoiseConfig(0.04, np.random.default_rng(1))
    noise_ref = dynamics.NoiseConfig(0.04, np.random.default_rng(1))

    for _ in range(500):
        I = rng.normal(size=K)
        h = integrator.step(h, W, 1.3, I, noise=noise)
        h_ref = dynamics.step(h_ref, W, 1.3, I, noise=noise_ref)
        assert np.array_equal(h, h_ref)


def test_plain_step_matches_dynamics_step_no_noise():
    """sigma=0.0 is the path every golden run at sigma=0 actually takes --
    worth its own explicit check since NoiseConfig.sample returns a bare
    0.0 (not an array) in that case, a different code path than sigma>0."""
    rng = np.random.default_rng(2)
    K = 40
    W = rng.normal(size=(K, K)) * 0.1
    h = np.zeros(K)
    h_ref = np.zeros(K)
    integrator = Integrator()

    for _ in range(500):
        I = rng.normal(size=K)
        h = integrator.step(h, W, 0.9, I, noise=None)
        h_ref = dynamics.step(h_ref, W, 0.9, I, noise=None)
        assert np.array_equal(h, h_ref)


def test_spiking_step_matches_hybridstate_bit_exact():
    rng = np.random.default_rng(3)
    K = 40
    spike_idx = np.array([5, 17])
    W = rng.normal(size=(K, K)) * 0.1

    hybrid = dynamics.HybridState(K, spike_idx, spike_threshold=0.5, spike_amp=50.0)
    integrator = Integrator(spike_idx=spike_idx, spike_threshold=0.5, spike_amp=50.0)
    h = np.zeros(K)
    noise = dynamics.NoiseConfig(0.04, np.random.default_rng(4))
    noise_ref = dynamics.NoiseConfig(0.04, np.random.default_rng(4))

    for _ in range(500):
        I = rng.normal(size=K) * 2.0  # wider range so the spike threshold actually gets crossed
        h = integrator.step(h, W, 1.5, I, noise=noise)
        h_ref = hybrid.step(W, 1.5, I, noise=noise_ref)
        assert np.array_equal(h, h_ref)
        assert np.array_equal(integrator.mem, hybrid.mem)
        assert np.array_equal(integrator.just_spiked, hybrid.just_spiked)
    assert hybrid.just_spiked.any(), "test is vacuous if the spike threshold was never crossed"


def test_empty_spike_idx_is_indistinguishable_from_no_spike_idx():
    """The unification's central claim: HybridState with an empty spike
    index reduces exactly to plain dynamics.step. Checked directly, not
    just argued in a docstring."""
    rng = np.random.default_rng(5)
    K = 20
    W = rng.normal(size=(K, K)) * 0.1
    h0 = rng.normal(size=K) * 0.01

    plain = Integrator()
    spiking_but_empty = Integrator(spike_idx=np.array([], dtype=int),
                                    spike_threshold=0.5, spike_amp=50.0)
    h_plain, h_empty = h0.copy(), h0.copy()
    for _ in range(200):
        I = rng.normal(size=K)
        h_plain = plain.step(h_plain, W, 1.1, I)
        h_empty = spiking_but_empty.step(h_empty, W, 1.1, I)
        assert np.array_equal(h_plain, h_empty)
