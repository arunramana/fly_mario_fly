"""fly/plasticity/three_factor.py -- REFACTOR_PLAN.md phase 6 step 4: the
three-factor, depression-only KC->MBON rule (SPEC_mushroom_body.md section
4), extracted from bridge/full_policy.py's inline mushroom-body block into
two standalone functions -- the same "move, don't duplicate" discipline
phase 3 used for Network/Integrator, applied here so the sign test
(docs/RUNS.md's phase 6 note) exercises the REAL update rule directly,
rather than a hand-copied reimplementation of it that could silently drift
from what the live circuit actually does.
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

    Mutates `W` in place and returns it -- bridge/full_policy.py's own
    call site relies on `self.W_kc_mbon` staying the same object across an
    episode (main() aliases it once at setup, reading the final trained
    result back out at the end, not re-read every frame).

    Always depresses when `dopamine` and `elig` are both nonzero,
    REGARDLESS of which happened first -- there is no branch here that
    could ever produce potentiation. See docs/RUNS.md's phase 6 sign-test
    entry for what that means (and doesn't mean) about matching Handler et
    al. 2019's bidirectional, ISI-order-dependent finding.
    """
    W -= learning_rate * dopamine[:, None] * elig[None, :] * W
    return W
