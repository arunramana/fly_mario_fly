"""Part 6b: default knobs on HOLDOUT for the real matrix and the 5 row-renormalised shuffles.
Escape at Goomba #1 = the episode got past x 320 (the Goomba kills Mario at x ~298 otherwise).
python -m flyrun.fair_default -> runs/007_default_knobs.json"""
import json
import os

from .brain import load_brain
from .controls import RUNS, holdout, looming_check
from .fitness import WorkerPool
from .genome import BASE

GOOMBA1_CLEARED_X = 320


def main():
    out = {}
    for tag, wf in [("real", None)] + [(f"shuf{i}_rn", f"W_steer_shuf{i}_rn.npy") for i in range(5)]:
        if wf:
            os.environ["FLYRUN_WFILE"] = wf
        else:
            os.environ.pop("FLYRUN_WFILE", None)
        lc = looming_check(load_brain())
        with WorkerPool(10) as pool:
            h = holdout(pool, BASE)
        out[tag] = dict(theta_deg_at_first_a=lc["theta_deg_at_first_a"], first_a_x=lc["first_a_x"], src_at_first_a=lc["src_at_first_a"],
                        ttmn_peak=lc["ttmn_peak_whole_run"], lc4_lplc2_ttmn_peak_x_lt_400=lc["peak_popmean_x_lt_400"],
                        holdout_mean_max_x=h["mean_max_x"], max_x=h["max_x"], n_traj=h["n_traj"], n_episodes=h["n_episodes"],
                        blind_presses=h["blind_presses"], n_onsets=h["n_onsets"], a_frac=h["a_frac"],
                        escapes=int(sum(m > GOOMBA1_CLEARED_X for m in h["max_x"])), end_causes=h["end_causes"])
        print(tag, json.dumps({k: out[tag][k] for k in ("theta_deg_at_first_a", "ttmn_peak", "holdout_mean_max_x", "n_traj", "escapes", "blind_presses")}), flush=True)
    os.environ.pop("FLYRUN_WFILE", None)
    (RUNS / "007_default_knobs.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
