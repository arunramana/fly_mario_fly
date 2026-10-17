"""Part 5 numbers: real vs shuffled matrix on HOLDOUT, the looming-escape check, the pit-cue ablation.
python -m flyrun.controls  -> runs/005_controls.json  (clips are rendered by make_clips.py)"""
import json
import os
from dataclasses import replace

import numpy as np

from .episodes4 import HOLDOUT, aggregate, jobs
from .evolve4 import EVO4, PART4
from .evolve5 import EVO5
from .fitness import WorkerPool, _one
from .genome import BASE, decode
from .run import run_episode

RUNS = EVO4.parent / "runs"
PIT3_CLEAR_X = 2480        # pit 3 is at x 2448, width 32 (runs/001_level_map.csv)


def genomes():
    g4 = json.loads((PART4 / "fly" / "best_genome.json").read_text())
    g4b = json.loads((EVO4 / "fly" / "best_genome.json").read_text())
    out = {"default_knobs": BASE,
           "part4_hopper": decode("fly", np.array(g4["u"]))[0],
           "part4b_fly": decode("fly", np.array(g4b["u"]))[0]}
    p = EVO5 / "fly_shuf" / "best_genome.json"
    if p.exists():
        out["shuf_evolved"] = decode("fly", np.array(json.loads(p.read_text())["u"]))[0]
    return out


def holdout(pool, knobs):
    res = pool.pool.map(_one, jobs(knobs, None, HOLDOUT))
    a = aggregate(res)
    a["pit3_crossed"] = int(sum(m > PIT3_CLEAR_X for m in a["max_x"]))
    a["end_causes"] = {}
    for _, _, c in a["ends"]:
        a["end_causes"][c] = a["end_causes"].get(c, 0) + 1
    return a


def looming_check(brain):
    """Default knobs, sigma 0, no noop delay: first A press, the theta at it, and population peaks
    before the first pipe (x < 400, i.e. around Goomba #1)."""
    s, df = run_episode(BASE, brain, record=True, record_h=True, stuck_frames=150, max_frames=900)
    H, m = df.attrs["H"], brain.masks
    a = df[df.a == 1]
    first = None if a.empty else a.iloc[0]
    early = (df.x < 400).to_numpy()
    pk = {k: float(H[early][:, m[k]].mean(1).max()) for k in ("LC4_R", "LPLC2_R", "TTMn", "DNp01", "DNp09")}
    return dict(summary=s, first_a_frame=None if first is None else int(first.frame),
                first_a_x=None if first is None else int(first.x),
                theta_deg_at_first_a=None if first is None else float(np.degrees(first.theta)),
                d_px_at_first_a=None if first is None or first.stim_d is None else float(first.stim_d),
                src_at_first_a=None if first is None else str(first.stim_src),
                n_a_frames_x_lt_400=int(df[early].a.sum()), peak_popmean_x_lt_400=pk,
                ttmn_peak_whole_run=float(H[:, m["TTMn"]].mean(1).max()))


def main():
    from .brain import load_brain
    out = {}
    gs = genomes()
    rows = {}
    for tag, wfile in (("real", None), ("shuf", "W_steer_shuf0.npy")):
        if wfile:
            os.environ["FLYRUN_WFILE"] = wfile
        else:
            os.environ.pop("FLYRUN_WFILE", None)
        with WorkerPool(12) as pool:
            for name, kn in gs.items():
                if name == "shuf_evolved" and tag == "real":
                    pass   # evolved on the shuffle; also run on the real matrix as a cross-check
                rows[f"{tag}/{name}"] = holdout(pool, kn)
                a = rows[f"{tag}/{name}"]
                print(tag, name, "flag", a["flag_rate"], "mean/min", round(a["mean_max_x"]), a["min_max_x"],
                      "A", round(a["a_frac"], 2), "blind", a["blind_presses"], "pit3", a["pit3_crossed"], flush=True)
            if tag == "real":
                ab = replace(gs["part4b_fly"], PIT_GAIN=0.0)
                rows["real/part4b_fly_PIT_GAIN0"] = holdout(pool, ab)
                a = rows["real/part4b_fly_PIT_GAIN0"]
                print("ablation", "mean/min", round(a["mean_max_x"]), a["min_max_x"], "pit3", a["pit3_crossed"], a["max_x"], flush=True)
        out["holdout"] = rows
        out["looming"] = out.get("looming", {})
        out["looming"][tag] = looming_check(load_brain())
    os.environ.pop("FLYRUN_WFILE", None)
    out["timing_s"] = json.loads((EVO5 / "timing.json").read_text())
    (RUNS / "005_controls.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
