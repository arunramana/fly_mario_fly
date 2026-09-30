# What this file does, in plain English:
# The learning rule for the fly's learning centre (the mushroom body). It
# keeps a fading memory of which sensory-coding cells were recently active;
# when a reward or punishment signal arrives it weakens their links to the
# output cells, in proportion to each link's current strength. Links only
# ever weaken, never strengthen -- unless recovery is switched on: then a
# reward or punishment signal also lets links of cells that were NOT recently
# active creep back toward their original strength (never above it). Used by
# the game controller and tests.
"""fly/plasticity/three_factor.py -- the three-factor, depression-only
KC->MBON rule (SPEC_mushroom_body.md section 4). The live circuit and the
sign test (tests/test_mb_sign_test.py) both call these functions, so the
test exercises the real rule.
"""

from __future__ import annotations

import numpy as np


def update_eligibility(elig: np.ndarray, kc_active: np.ndarray, tau: float) -> np.ndarray:
    """`elig(t+1) = (1 - 1/tau)*elig(t) + (1/tau)*kc_active(t)` -- SPEC_
    mushroom_body.md section 4. Per-KC, not per-synapse: the sparse KC
    code IS the identity-carrying signal, matching the standard real-MB
    coincidence-detection model (Aso/Rubin-style)."""
    return (1.0 - 1.0 / tau) * elig + (1.0 / tau) * kc_active


def recover(W: np.ndarray, W0: np.ndarray, dopamine: np.ndarray, elig: np.ndarray,
            recovery_rate: float) -> np.ndarray:
    """Recovery (docs/SPEC_learning_v3.md A1): dopamine WITHOUT KC coincidence lets a depressed
    synapse recover toward its untrained weight `W0`, as in real flies:
    `W[i,j] += min(1, recovery_rate * dopamine[j] * (1 - elig[i])) * (W0[i,j] - W[i,j])`.
    Toward `W0` only and only from below (a synapse at or above `W0` is left alone), so it can
    never potentiate beyond baseline. Mutates and returns `W`. rate 0 = no-op."""
    if recovery_rate <= 0.0:
        return W
    step = np.minimum(1.0, recovery_rate * dopamine[:, None] * (1.0 - elig)[None, :])
    W += step * np.maximum(W0 - W, 0.0)
    return W


def depress(W: np.ndarray, dopamine: np.ndarray, elig: np.ndarray, learning_rate: float) -> np.ndarray:
    """`W[i,j] -= learning_rate * dopamine[j] * elig[i] * W[i,j]` -- SPEC_
    mushroom_body.md section 4: multiplicative (proportional to the
    synapse's own current weight, so it decays toward but never past
    zero), depression only, applied to whichever MBON `dopamine` targets
    (already routed to PAM or PPL1/PPM by fly.plasticity.dopamine.
    event_dopamine before this is ever called).

    Mutates `W` in place and returns it: run_steering.main() holds the
    same object from setup and returns it as the trained matrix.

    Depresses whenever dopamine and eligibility overlap, whichever came
    first; it can never potentiate, unlike Handler et al. 2019's
    order-dependent result (docs/RUNS.md 027).
    """
    W -= learning_rate * dopamine[:, None] * elig[None, :] * W
    return W
