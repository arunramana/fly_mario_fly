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
