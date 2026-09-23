# What this file does, in plain English:
# Checks settings for the MDN circuit (the neurons that make a fly walk
# backwards) by simulating it with no game. Prints its spectral radius (a
# number saying whether activity can run away), then average MDN activity
# after 300 steps with zero input at 4 strengths, and at 5 input levels at
# strength 1.2, noting whether each hits the maximum.
"""
tune_mdn.py -- pick G_MDN, MDN_DRIVE, MDN_THRESHOLD by directly simulating
the real MDN circuit (same lighter-touch approach as tune_steering.py /
tune_terrain.py -- SPEC_habituation.md section 2 explicitly doesn't call
for a full Diagnostic-4 sweep here).

    .venv/Scripts/python.exe -m scripts.tune_mdn
"""
from __future__ import annotations

import numpy as np

from fly.network import dynamics
from fly.circuits.load_mdn_cached import load

SUBSTEPS_TO_SETTLE = 300


def settle(W, mdn_mask, g, drive, steps=SUBSTEPS_TO_SETTLE):
    K = W.shape[0]
    h = np.zeros(K)
    I = np.zeros(K)
    I[mdn_mask] = drive
    trace = []
    for _ in range(steps):
        h = dynamics.step(h, W, g, I)
        trace.append(h[mdn_mask].mean())
    return np.array(trace)


def main():
    print("Loading MDN circuit (cached)...")
    bodies, edges, total_input, signs, W, order, diag = load()
    mdn_mask = (bodies["type"] == "MDN").to_numpy()
    rho1 = dynamics.np.linalg.eigvals(W).__abs__().max()
    print(f"spectral radius (g=1): {rho1:.4f}  ->  linear boundary near g~{1/rho1:.2f}\n")

    print("--- zero drive: must decay to zero (no runaway with no input) ---")
    for g in (0.8, 1.0, 1.2, 1.4):
        tr = settle(W, mdn_mask, g, drive=0.0)
        print(f"  g={g:<4} settled MDN_mean={tr[-1]:.4f}")

    print("\n--- sweep drive at a candidate g, looking for a clean settled ---"
          " non-zero, non-clipped response ---")
    G_MDN = 1.2
    for drive in (0.5, 1.0, 1.5, 2.0, 3.0):
        tr = settle(W, mdn_mask, G_MDN, drive=drive)
        print(f"  g={G_MDN} drive={drive:<4} -> settled MDN_mean={tr[-1]:.4f} "
              f"(clipped={tr[-1] >= dynamics.CLIP - 1e-6})")


if __name__ == "__main__":
    main()
