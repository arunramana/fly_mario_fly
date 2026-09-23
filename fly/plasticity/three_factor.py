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
