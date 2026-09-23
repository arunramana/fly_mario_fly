"""
tune_orn_adapt.py -- does ORN adaptation alone break Mario out of a spot
he'd otherwise sit in forever?

Constructs the "stuck" case directly: a constant raw odour concentration
held fixed on one side (as if Mario were parked at a fixed distance from a
source, unable to close in -- e.g. wedged against an obstacle on the far
side of it), fed through OlfactoryAdaptation and then the REAL DNa01/DNa02
recurrent circuit (W_s, G_STEER), exactly the path run_steering.py's main
loop uses. Checks two things: (1) without adaptation, the WTA stays flipped
to the odour side forever; (2) with it, the WTA flips back to home (R)
after adaptation drags the effective odour down far enough, and reports the
exact frame that happens.

    .venv/Scripts/python.exe tune_orn_adapt.py
"""
from __future__ import annotations

import numpy as np

from fly.network import dynamics
from fly.circuits.load_steering_cached import load as load_steering
from fly.sensing.olfactory_adaptation import OlfactoryAdaptation, ALPHA_ADAPT
from run_steering import ODOUR_GAIN, HOME_BIAS, G_STEER

N_FRAMES = 600
STUCK_RAW_CONC = 1.0 / 24.0  # "parked" 24px from a source -- realistic close range


def make_masks(bodies):
    dna = bodies["type"].isin(["DNa01", "DNa02"]).to_numpy()
    r = dna & (bodies["somaSide"] == "R").to_numpy()
    l = dna & (bodies["somaSide"] == "L").to_numpy()
    return r, l


def run(use_adaptation: bool, hunger_mult: float):
    bodies, edges, total_input, signs, W, order, diag = load_steering()
    r_mask, l_mask = make_masks(bodies)
    K = W.shape[0]
    h = np.zeros(K)
    adapt = OlfactoryAdaptation()

    flip_frame = None
    r_trace, l_trace, eff_trace = [], [], []
    for frame in range(N_FRAMES):
        # match run_steering.py's actual order: gain/hunger scale first,
        # THEN adapt -- adaptation has to act in HOME_BIAS's own units to
        # mean anything (see ALPHA_ADAPT's comment in run_steering.py).
        prod = {"L": ODOUR_GAIN * hunger_mult * STUCK_RAW_CONC, "R": 0.0}
        if use_adaptation:
            eff = adapt.apply(prod)
        else:
            eff = prod
        odor_l_eff = eff["L"]
        odor_r_eff = eff["R"]

        I = np.zeros(K)
        I[r_mask] = HOME_BIAS + odor_r_eff
        I[l_mask] = odor_l_eff
        for _ in range(dynamics.SUBSTEPS):
            h = dynamics.step(h, W, G_STEER, I)
        r_team, l_team = h[r_mask].mean(), h[l_mask].mean()
        r_trace.append(r_team); l_trace.append(l_team); eff_trace.append(odor_l_eff)

        if flip_frame is None and l_team <= r_team and frame > 10:
            # only report a flip BACK to home after having been flipped to
            # odour at least once -- otherwise "never flipped away" would
            # trivially satisfy this check on frame 0
            pass
    return np.array(r_trace), np.array(l_trace), np.array(eff_trace)


def find_home_return(r_trace, l_trace):
    """First frame the WTA is back on R after having been on L -- None if
    it never leaves L (the stuck case with no adaptation)."""
    was_stuck = False
    for i in range(len(r_trace)):
        if l_trace[i] > r_trace[i]:
            was_stuck = True
        elif was_stuck and r_trace[i] >= l_trace[i]:
            return i
    return None


def main():
    print(f"STUCK_RAW_CONC={STUCK_RAW_CONC:.4f} (Mario parked ~24px from a source), "
          f"held constant for {N_FRAMES} frames -- the 'wedged next to a mushroom/"
          f"block and can't close the distance' case.\n")

    for hunger_label, hunger_mult in (("SATED", 1.0), ("HUNGRY", 3.0)):
        print(f"--- {hunger_label} (hunger_mult={hunger_mult}) ---")
        r_no, l_no, _ = run(use_adaptation=False, hunger_mult=hunger_mult)
        home_no = find_home_return(r_no, l_no)
        print(f"  WITHOUT adaptation: stuck on L from the start={l_no[20] > r_no[20]}, "
              f"returns home at frame={home_no}")

        r_yes, l_yes, eff_yes = run(use_adaptation=True, hunger_mult=hunger_mult)
        home_yes = find_home_return(r_yes, l_yes)
        print(f"  WITH adaptation:    stuck on L from the start={l_yes[20] > r_yes[20]}, "
              f"returns home at frame={home_yes}")
        if home_yes is not None:
            i = home_yes
            print(f"    -> at frame {i}: R_team={r_yes[i]:.4f} L_team={l_yes[i]:.4f} "
                  f"(effective odour decayed from {eff_yes[20]:.4f} at frame 20 "
                  f"to {eff_yes[i]:.4f})")
        print()


if __name__ == "__main__":
    main()
