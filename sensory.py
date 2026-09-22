"""
sensory.py — synthetic-looming stimulus + hemisphere routing helpers.

Shared by tune.py (offline diagnostics, needs matplotlib) and run_mario.py
(live emulator run, must NOT pull in matplotlib -- it drags contourpy,
which forces numpy>=2 and breaks nes-py's numpy<2 pin. See requirements.txt).
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


def theta_multi_approach(n_approaches: int = 10, d0: float = 300.0, v: float = 4.0,
                          w: float = W_TILE, d_min: float = 10.0,
                          gap_frames: int = 150):
    """Several single-hemisphere approaches back-to-back with clean gaps
    (enemy off-screen, theta=0) in between, each ramp allowed to fully clear
    before the next starts. The gentlest version of a "sustained" trace --
    good for a first check, but see `sustained_bilateral_trace` below: this
    one turns out NOT to reproduce the saturation seen in the real run,
    because the real game drives both hemispheres with overlapping enemies,
    never letting either side fully rest.

    Returns theta, dtheta (n_frames,) and `approach` -- a bool mask, True
    during a ramp, False during a gap.
    """
    theta_parts, approach_parts = [], []
    for _ in range(n_approaches):
        _, theta_i, _ = theta_ramp(d0, v, w, d_min)
        theta_parts.append(theta_i)
        approach_parts.append(np.ones(len(theta_i), dtype=bool))
        theta_parts.append(np.zeros(gap_frames))
        approach_parts.append(np.zeros(gap_frames, dtype=bool))
    theta = np.concatenate(theta_parts)
    approach = np.concatenate(approach_parts)
    dtheta = np.diff(theta, prepend=theta[0])
    return theta, dtheta, approach


def sustained_bilateral_trace(n_bursts: int = 4, burst_frames: int = 500,
                               quiet_frames: int = 250, seed: int = 0,
                               d0_range=(120.0, 320.0), v: float = 4.0,
                               w: float = W_TILE, overlap_range=(5, 40)):
    """The realistic version of Diagnostic 4's stimulus: what SMB 1-1 actually
    delivers over a level -- clusters of enemies on BOTH hemispheres, each new
    approach often starting before the last one has fully decayed (Mario
    keeps running; Goombas don't queue up and wait), separated by genuine
    quiet stretches where nothing is on screen.

    A single-hemisphere trace with clean gaps (`theta_multi_approach`) does
    NOT reproduce the saturation the real run showed -- confirmed by running
    it through diag4.py, everything decays cleanly between ramps. Overlap
    across BOTH hemispheres is the missing ingredient: the expanded (section
    1b) subgraph's threshold-added neurons were selected by synapse count
    onto {LC4, LPLC2, DNp01}, not filtered for single-hemisphere projection,
    so some of them integrate drive from both sides at once and never see a
    clean reset.

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
