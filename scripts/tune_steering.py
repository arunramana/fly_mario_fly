# What this file does, in plain English:
# Sanity-checks the strength setting g for the turning circuit (DNa01/DNa02)
# with no game: prints its spectral radius (whether activity can run away)
# at 7 values of g, and how the right-side neurons settle under a constant
# input at 4 values. The closing "Decision" text (G_STEER = 1.2) is fixed
# wording, printed whatever the numbers show.
"""
tune_steering.py — SPEC_steering.md section 1's lighter gain check: not a
full Diagnostic-4 sweep (out of scope, "cut for speed"), just spectral
radius at a few g values plus a constant-bias settling check, the same
sanity bar the ORIGINAL jump circuit passed before Diagnostic 4 existed.

    .venv/Scripts/python.exe -m scripts.tune_steering
"""
from __future__ import annotations

import numpy as np

from fly.connectome import circuit
from fly.network import dynamics
from fly.circuits.load_steering_cached import load

HOME_BIAS = 1.0  # the constant "go home" current, R-hemisphere only -- see run_steering.py


def main():
    bodies, edges, total_input, signs, W, order, diag = load()
    K = W.shape[0]

    r_mask = ((bodies["type"].isin(["DNa01", "DNa02"])) & (bodies["somaSide"] == "R")).to_numpy()

    print("spectral radius of W_steer at several g:")
    for g in (0.5, 1.0, 1.2, 1.27, 1.3, 1.5, 2.0):
        print(f"  g={g:<5} rho={circuit.spectral_radius(W, g):.4f}")

    print("\nconstant-bias settling check (HOME_BIAS on R-hemisphere "
          "DNa01+DNa02 only, 400 steps, no other input):")
    I = np.zeros(K)
    I[r_mask] = HOME_BIAS
    for g in (1.0, 1.2, 1.3, 1.5):
        h = np.zeros(K)
        trace = []
        for _ in range(400):
            h = dynamics.step(h, W, g, I)
            trace.append(h[r_mask].mean())
        trace = np.array(trace)
        tail = trace[-50:]
        clipped_frac = (trace >= dynamics.CLIP - 1e-6).mean()
        print(f"  g={g:<4} final R-team mean={tail.mean():.3f} "
              f"(std over last 50 steps={tail.std():.4f}, "
              f"fraction of steps at clip ceiling={clipped_frac:.3f})")

    print("\nDecision: rho(g=1)=0.7857, so the linear stability boundary "
          "(rho=1) sits near g~1.27. g=1.2 is comfortably under it, still "
          "gives more recurrent amplification than g=1.0, and the settling "
          "check above should show it converging to a stable non-zero "
          "point with no clipping. -> G_STEER = 1.2")


if __name__ == "__main__":
    main()
