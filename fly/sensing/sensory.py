# What this file does, in plain English:
# Makes artificial "something is approaching" test signals: how large an
# object of a given width looks as it closes in at a steady speed, and a
# longer pattern of overlapping approaches from both sides. It also picks
# out the jump network's detector groups by side. Used only by diagnostic
# and tuning scripts, not by the live game.
"""
sensory.py — synthetic-looming stimulus + hemisphere routing helpers.

Shared by scripts/tune.py (offline diagnostics, needs matplotlib),
scripts/diag4.py and scripts/denormal_probe.py. This module must NOT pull in
matplotlib -- it drags contourpy, which forces numpy>=2 and breaks nes-py's
numpy<2 pin. See requirements.txt.
"""

from __future__ import annotations

import numpy as np

DRIVEN_SIDE = "R"
W_TILE = 16.0


def theta_ramp(d0: float = 300.0, v: float = 4.0, w: float = W_TILE,
               d_min: float = 10.0):
    """d(t), theta(t) for an object of width w approaching at constant v."""
    d = np.arange(d0, d_min, -v)
    theta = 2.0 * np.arctan(w / (2.0 * d))
    dtheta = np.diff(theta, prepend=theta[0])
    return d, theta, dtheta


def masks(bodies, side=DRIVEN_SIDE):
    m = lambda t, s: ((bodies["type"] == t) & (bodies["somaSide"] == s)).to_numpy()
    return {
        "LC4_drive": m("LC4", side),
        "LPLC2_drive": m("LPLC2", side),
        "LC4_all": (bodies["type"] == "LC4").to_numpy(),
        "LPLC2_all": (bodies["type"] == "LPLC2").to_numpy(),
        "DNp01_drive": m("DNp01", side),
        "TTMn_drive": m("TTMn", side),
    }


def sensory_trace(K: int, msk: dict, theta: np.ndarray, dtheta: np.ndarray):
    """(n_frames, K) input: LC4 gets |dtheta| (angular velocity), LPLC2 gets
    theta (expansion) -- spec section 2's split, no extra scaling constant."""
    I = np.zeros((len(theta), K))
    I[:, msk["LC4_drive"]] = np.abs(dtheta)[:, None]
    I[:, msk["LPLC2_drive"]] = theta[:, None]
    return I


def sustained_bilateral_trace(n_bursts: int = 4, burst_frames: int = 500,
                               quiet_frames: int = 250, seed: int = 0,
                               d0_range=(120.0, 320.0), v: float = 4.0,
                               w: float = W_TILE, overlap_range=(5, 40)):
    """Diagnostic 4's stimulus: bursts of overlapping approaches on BOTH
    hemispheres, each often starting before the last has decayed, separated
    by quiet stretches. Bilateral overlap is what matters: some of the
    expanded subgraph's neurons integrate drive from both sides, so a
    one-sided trace with clean gaps never tests whether the network resets.

    Returns theta_L, dtheta_L, theta_R, dtheta_R, approach (True during a
    burst, False during a quiet stretch).
    """
    rng = np.random.default_rng(seed)
    theta_L_parts, theta_R_parts, approach_parts = [], [], []
    for _ in range(n_bursts):
        L = np.zeros(burst_frames)
        R = np.zeros(burst_frames)
        f = 0
        while f < burst_frames:
            side = rng.choice(["L", "R"])
            d0 = rng.uniform(*d0_range)
            _, th, _ = theta_ramp(d0=d0, v=v, w=w)
            end = min(f + len(th), burst_frames)
            th = th[:end - f]
            target = L if side == "L" else R
            target[f:end] = np.maximum(target[f:end], th)
            f += max(len(th) - rng.integers(*overlap_range), 1)
        theta_L_parts.append(L)
        theta_R_parts.append(R)
        approach_parts.append(np.ones(burst_frames, dtype=bool))
        theta_L_parts.append(np.zeros(quiet_frames))
        theta_R_parts.append(np.zeros(quiet_frames))
        approach_parts.append(np.zeros(quiet_frames, dtype=bool))

    theta_L = np.concatenate(theta_L_parts)
    theta_R = np.concatenate(theta_R_parts)
    approach = np.concatenate(approach_parts)
    dtheta_L = np.diff(theta_L, prepend=theta_L[0])
    dtheta_R = np.diff(theta_R, prepend=theta_R[0])
    return theta_L, dtheta_L, theta_R, dtheta_R, approach
