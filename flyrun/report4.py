"""Part 4b report: holdout evaluation of each arm's best genome, videos, curves.
python -m flyrun.report4  -> runs/004_report_numbers.json, runs/004_curve_<arm>.png,
evo4/<arm>/best.mp4 (holdout noop_start 3, sigma 0), evo4/<arm>/montage.mp4"""
import json
from dataclasses import replace
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .baselines import CONTROLLERS
from .brain import load_brain
from .episodes4 import HOLDOUT, TRAIN, aggregate, jobs
from .evolve4 import EVO4, PART4
from .fitness import WorkerPool, _one
from .genome import BASE, CONTROLLER, decode
from .montage import label
from .run import run_episode, save_video

RUNS = EVO4.parent / "runs"
DISPLAY = dict(noop_start=3, sigma=0.0, seed=101)   # best.mp4 / montage episode (a HOLDOUT episode)


def replay(arm_or_ctl, knobs, ctl_name, record=True, ep=DISPLAY, brain=None):
    brain = brain or load_brain()
    ctl = CONTROLLERS[ctl_name] if ctl_name else None
    return run_episode(replace(knobs, SENSOR_NOISE=ep["sigma"]), brain, noop_start=ep["noop_start"],
                       episode_seed=ep["seed"], controller=ctl, record=record, stuck_frames=150)


def obstacle_table(max_x):
    lm = pd.read_csv(RUNS / "001_level_map.csv")
    return [dict(kind=o["kind"], x=int(o["x"]), size=int(o["size"]),
                 cleared=bool(max_x > o["x"] + (16 if o["kind"] == "wall" else o["size"])))
            for _, o in lm.iterrows()]


def evaluate_on(pool, knobs, ctl, episodes):
    return aggregate(pool.pool.map(_one, jobs(knobs, ctl, episodes)))


def montage(arm, brain):
    g = pd.read_csv(EVO4 / arm / "gen.csv")
    r = json.loads((EVO4 / arm / "best_genome.json").read_text())["restart"]
    g = g[g.restart == r].sort_values("gen")
    keep, prev = [], -1.0
    for _, row in g.iterrows():
        if row.gen == 0 or row.best_mean_max_x > prev:
            keep.append(row)
        prev = max(prev, row.best_mean_max_x)
    writer, out = None, EVO4 / arm / "montage.mp4"
    for row in keep:
        knobs, _ = decode(arm, np.array(json.loads(row.gen_best_u)))
        s, df = replay(arm, knobs, CONTROLLER[arm], brain=brain)
        text = f"gen {int(row.gen)} | max_x {s['max_x']} | {s['cause']}"
        for fr in df.attrs["frames"]:
            lab = label(fr, text)
            if writer is None:
                h, w = lab.shape[:2]
                writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), 30, (w, h))
            writer.write(cv2.cvtColor(lab, cv2.COLOR_RGB2BGR))
        for _ in range(20):
            writer.write(cv2.cvtColor(lab, cv2.COLOR_RGB2BGR))
    writer.release()
    return [(int(r_.gen), r_.best_mean_max_x) for r_ in keep]


def main():
    brain = load_brain()
    out = {}
    refs = {}   # (name, knobs, controller)
    with WorkerPool(12) as pool:
        # reference rows on the same HOLDOUT set
        p4fly = json.loads((PART4 / "fly" / "best_genome.json").read_text())
        refs["fly_part4_hopper"] = (decode("fly", np.array(p4fly["u"]))[0], None)
        p4th = json.loads((PART4 / "theta" / "best_genome.json").read_text())
        refs["theta_part4"] = (decode("theta", np.array(p4th["u"]))[0], "theta_rule")
        refs["spam_fixed_18_3"] = (BASE, "spam_fixed")
        out["reference_holdout"] = {k: evaluate_on(pool, kn, c, HOLDOUT) for k, (kn, c) in refs.items()}
        out["reference_train"] = {k: evaluate_on(pool, kn, c, TRAIN) for k, (kn, c) in refs.items()}
        for arm in ("fly", "theta", "spam"):
            best = json.loads((EVO4 / arm / "best_genome.json").read_text())
            u = np.array(best["u"])
            knobs, vals = decode(arm, u)
            ctl = CONTROLLER[arm]
            a = dict(best=best, genome=vals)
            a["train"] = evaluate_on(pool, knobs, ctl, TRAIN)
            a["holdout"] = evaluate_on(pool, knobs, ctl, HOLDOUT)
            h0 = evaluate_on(pool, knobs, ctl, [e for e in HOLDOUT if e["sigma"] == 0.0])
            h5 = evaluate_on(pool, knobs, ctl, [e for e in HOLDOUT if e["sigma"] == 0.05])
            a["holdout_sigma0"], a["holdout_sigma005"] = h0, h5
            a["start_label"] = best["start"]
            g = pd.read_csv(EVO4 / arm / "gen.csv")
            a["restarts"] = {int(r): dict(start=d.start.iloc[0], gens=int(d.gen.max()) + 1,
                                          best_fit=float(d.best_fit.iloc[-1]),
                                          train_mean_max_x=float(d.best_mean_max_x.iloc[-1]),
                                          train_flag=float(d.best_flag_rate.iloc[-1]),
                                          blind=float(d.best_blind.iloc[-1]),
                                          genome=d.best_genome.iloc[-1]) for r, d in g.groupby("restart")}
            # display episode: death map and behaviour
            s, df = replay(arm, knobs, ctl, brain=brain)
            a["display"] = s
            a["obstacles"] = obstacle_table(s["max_x"])
            ev = df[(df.a == 1) & (df.a.shift(1, fill_value=0) == 0)]
            iv = np.diff(ev.frame.values)
            a["behaviour"] = dict(A_frac=float(df.a.mean()), n_onsets=int(len(ev)),
                                  median_interval=float(np.median(iv)) if len(iv) else None)
            if arm == "fly":
                k0 = replace(knobs, PIPE_SENSE=False, PIT_SENSE=False)
                s0, d0 = run_episode(k0, brain, enemy_input=False, max_frames=600, stuck_frames=10**6)
                a["behaviour"]["silence_600f"] = dict(A_frac=float(d0.a.mean()), ttmn_max=float(d0.ttmn.max()))
            save_video(df.attrs["frames"], EVO4 / arm / "best.mp4")
            a["montage_stages"] = montage(arm, brain)
            fig, ax = plt.subplots(figsize=(7, 3.8))
            for r, d in g.groupby("restart"):
                ax.plot(d.gen, d.best_fit, "-o", ms=3, label=f"best (r{r}, {d.start.iloc[0]})")
                ax.plot(d.gen, d.mean_fit, "--", alpha=0.6, label=f"pop. mean (r{r})")
            ax.set_xlabel("generation")
            ax.set_ylabel("TRAIN fitness (mean of 3 episodes)")
            ax.set_title(f"{arm} arm, Part 4b")
            ax.legend(fontsize=6)
            fig.tight_layout()
            fig.savefig(RUNS / f"004_curve_{arm}.png", dpi=130)
            plt.close(fig)
            out[arm] = a
            hd = a["holdout"]
            print(arm, vals, "train", round(a["train"]["fitness"]), "holdout flag", hd["flag_rate"],
                  "mean/min", round(hd["mean_max_x"]), hd["min_max_x"], "A_frac", round(hd["a_frac"], 2),
                  "blind", hd["blind_presses"], flush=True)
    out["timing_s"] = json.loads((EVO4 / "timing.json").read_text())
    (RUNS / "004_report_numbers.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
