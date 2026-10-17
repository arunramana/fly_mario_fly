"""Part 6b: HOLDOUT evaluation of the equal-budget evolved genomes (flyrun/evo6), real vs shuffles, plus the
original 4b fly, the evolved timer and the theta rule. Per episode we keep the first A's stimulus source, because
"escape at Goomba #1" means the first A fired with a Goomba in view AND Mario got past x 320 (Goomba #1 kills at ~298).
python -m flyrun.fair_eval -> runs/007_fair_eval.json"""
import json
import multiprocessing as mp
import os
from dataclasses import replace

import numpy as np

from .episodes4 import HOLDOUT, aggregate
from .evolve4 import EVO4
from .evolve6 import EVO6, WFILE
from .controls import RUNS
from .genome import CONTROLLER, decode
from .knobs import BLIND_PENALTY
from .fitness import fitness_of

import pandas as pd

CLEARED_X = 320
_B = None


def _init():
    global _B
    from .brain import load_brain
    _B = load_brain()


def _ep(job):
    from .baselines import CONTROLLERS
    from .run import run_episode
    knobs, ctl, ep = job
    k = replace(knobs, SENSOR_NOISE=ep["sigma"])
    s, df = run_episode(k, _B, noop_start=ep["noop_start"], episode_seed=ep["seed"], stuck_frames=150,
                        controller=CONTROLLERS[ctl] if ctl else None)
    a = df[df.a == 1]
    s = dict(s, fitness=fitness_of(s, BLIND_PENALTY), first_a_src=None if a.empty else str(a.iloc[0].stim_src),
             first_a_x=None if a.empty else int(a.iloc[0].x), first_a_theta=None if a.empty else float(np.degrees(a.iloc[0].theta)))
    return s


def evaluate(pool, knobs, ctl=None):
    res = pool.map(_ep, [(knobs, ctl, e) for e in HOLDOUT])
    ag = aggregate(res)
    ag["escapes_looming"] = int(sum(r["max_x"] > CLEARED_X and r["first_a_src"] == "goomba" for r in res))
    ag["passes_goomba1"] = int(sum(r["max_x"] > CLEARED_X for r in res))
    ag["first_a_src"] = sorted({str(r["first_a_src"]) for r in res})
    ag["end_causes"] = {}
    for _, _, c in ag["ends"]:
        ag["end_causes"][c] = ag["end_causes"].get(c, 0) + 1
    return ag


def restart_genomes(d):
    g = pd.read_csv(d / "gen.csv")
    out = {}
    for r, grp in g.groupby("restart"):
        last = grp.sort_values("gen").iloc[-1]
        out[f"r{int(r)}_{last.start}"] = decode("fly", np.array(json.loads(last.best_u)))[0]
    return out


def main():
    out = {}
    jobs = [("real", [("real/evolved_best", decode("fly", np.array(json.loads((EVO6 / "real" / "best_genome.json").read_text())["u"]))[0], None)]
             + [(f"real/{k}", v, None) for k, v in restart_genomes(EVO6 / "real").items()]
             + [("real/4b_original", decode("fly", np.array(json.loads((EVO4 / "fly" / "best_genome.json").read_text())["u"]))[0], None)])]
    for i in range(3):
        a = f"shuf{i}_rn"
        jobs.append((a, [(f"{a}/evolved_best", decode("fly", np.array(json.loads((EVO6 / a / "best_genome.json").read_text())["u"]))[0], None)]
                     + [(f"{a}/{k}", v, None) for k, v in restart_genomes(EVO6 / a).items()]))
    for arm, entries in jobs:
        if WFILE[arm]:
            os.environ["FLYRUN_WFILE"] = WFILE[arm]
        else:
            os.environ.pop("FLYRUN_WFILE", None)
        with mp.get_context("spawn").Pool(10, initializer=_init) as pool:
            for name, knobs, ctl in entries:
                out[name] = evaluate(pool, knobs, ctl)
                o = out[name]
                print(name, "mean_max_x", round(o["mean_max_x"]), "traj", o["n_traj"], "blind", o["blind_presses"], "esc", o["escapes_looming"], flush=True)
    os.environ.pop("FLYRUN_WFILE", None)
    with mp.get_context("spawn").Pool(10, initializer=_init) as pool:   # no-brain baselines, real matrix irrelevant
        for name, arm in (("timer_evolved", "spam"), ("theta_rule_evolved", "theta")):
            kn = decode(arm, np.array(json.loads((EVO4 / arm / "best_genome.json").read_text())["u"]))[0]
            out[name] = evaluate(pool, kn, CONTROLLER[arm])
            print(name, round(out[name]["mean_max_x"]), out[name]["n_traj"], flush=True)
    (RUNS / "007_fair_eval.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
