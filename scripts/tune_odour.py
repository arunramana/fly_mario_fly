"""
tune_odour.py -- SPEC_odour.md section 0: pick ODOUR_GAIN and the hunger
multiplier(s) by actually simulating the real steering circuit (DNa01/DNa02,
W_s, G_STEER=1.2), not by comparing raw injected currents in isolation. The
recurrent network's own gain/leak can amplify or damp a raw current
differently than 1:1, so "effective(d=16px) ~= HOME_BIAS" has to be checked
against the settled L/R team output, the same quantity run_steering.py's WTA
actually compares.

    .venv/Scripts/python.exe -m scripts.tune_odour
"""
from __future__ import annotations

import numpy as np

from fly.network import dynamics
from fly.circuits.load_steering_cached import load as load_steering

HOME_BIAS = 1.0
G_STEER = 1.2
SUBSTEPS_TO_SETTLE = 300  # generous; run_steering.py itself only gives 10/frame,
                          # but the WTA reads a running h that accumulates frame
                          # over frame, so the steady-state comparison here is
                          # the right question to ask, not a one-frame answer.


def make_masks(bodies):
    dna = bodies["type"].isin(["DNa01", "DNa02"]).to_numpy()
    r = dna & (bodies["somaSide"] == "R").to_numpy()
    l = dna & (bodies["somaSide"] == "L").to_numpy()
    return r, l


def settle(W, r_mask, l_mask, home_bias, odor_l=0.0, odor_r=0.0, steps=SUBSTEPS_TO_SETTLE):
    K = W.shape[0]
    h = np.zeros(K)
    I = np.zeros(K)
    I[r_mask] = home_bias + odor_r
    I[l_mask] = odor_l
    trace_r, trace_l = [], []
    for _ in range(steps):
        h = dynamics.step(h, W, G_STEER, I)
        trace_r.append(h[r_mask].mean())
        trace_l.append(h[l_mask].mean())
    return np.array(trace_r), np.array(trace_l)


def main():
    print("Loading steering circuit (cached)...")
    bodies, edges, total_input, signs, W, order, diag = load_steering()
    r_mask, l_mask = make_masks(bodies)

    print("\n--- baseline: HOME_BIAS only, no odour ---")
    tr, tl = settle(W, r_mask, l_mask, HOME_BIAS)
    r_ss, l_ss = tr[-20:].mean(), tl[-20:].mean()
    print(f"  settled R_team={r_ss:.4f}  L_team={l_ss:.4f}  "
          f"(any L>0 here is cross-hemisphere leakage through real "
          f"recurrent partners, not odour -- worth knowing before judging "
          f"any 'flip')")

    print("\n--- run 006's original bug, for reference: raw concentration, "
          "no gain, mushroom 40px behind Mario ---")
    conc_40 = 1.0 / 40
    tr, tl = settle(W, r_mask, l_mask, HOME_BIAS, odor_l=conc_40)
    print(f"  raw conc={conc_40:.4f} (no ODOUR_GAIN) -> R={tr[-20:].mean():.4f} "
          f"L={tl[-20:].mean():.4f}  flip={tl[-20:].mean() > tr[-20:].mean()}")

    print("\n--- sweep ODOUR_GAIN at several distances, no hunger boost yet ---")
    for gain in (4, 8, 12, 16, 20, 24, 32):
        row = []
        for d in (8, 16, 24, 40):
            conc = gain / d
            tr, tl = settle(W, r_mask, l_mask, HOME_BIAS, odor_l=conc)
            flip = tl[-20:].mean() > tr[-20:].mean()
            row.append(f"d={d:2d}:{'FLIP' if flip else 'no  '}({tl[-20:].mean():.3f}/{tr[-20:].mean():.3f})")
        print(f"  ODOUR_GAIN={gain:3d}  " + "  ".join(row))

    print("\n--- with hunger: does a HUNGRY multiplier flip at realistic "
          "range (16-40px) while a SATED multiplier does not, at a fixed "
          "ODOUR_GAIN? ---")
    ODOUR_GAIN = 16
    for hunger_mult in (1.0, 1.5, 2.0, 3.0, 4.0):
        row = []
        for d in (16, 24, 40):
            conc = ODOUR_GAIN * hunger_mult / d
            tr, tl = settle(W, r_mask, l_mask, HOME_BIAS, odor_l=conc)
            flip = tl[-20:].mean() > tr[-20:].mean()
            row.append(f"d={d:2d}:{'FLIP' if flip else 'no'}")
        print(f"  ODOUR_GAIN={ODOUR_GAIN} hunger_mult={hunger_mult:<4} " + "  ".join(row))


if __name__ == "__main__":
    main()
