"""Part 4b: re-evolve for robustness and selectivity.
python -m flyrun.evolve4 --arm spam|theta|fly|all [--workers 12]

Each evaluation = TRAIN episodes (noop_start {0,7,17} x sigma 0.05, seeds 1,2,3), fitness = mean of
max_x + 10000*flag - 50*blind_presses. HOLDOUT (episodes4.py) is never touched here.
Fly restarts: 1 = Part 4 default genome, 2 = Part 4 restart-3 (flag) genome, 3 = fresh random start.
Outputs under flyrun/evo4/<arm>/: gen.csv, all_evals.csv, best_genome.json, state.pkl (resume)."""
import argparse
import json
import pickle
import time
from pathlib import Path

import cma
import numpy as np

from .episodes4 import TRAIN, aggregate, jobs
from .evolve import MAX_GENS, PATIENCE, POPSIZE, RESTARTS, SIGMA0, _append, _drop_from, _save
from .fitness import WorkerPool, _one
from .genome import CONTROLLER, SPECS, decode, x0

EVO4 = Path(__file__).resolve().parent / "evo4"
PART4 = Path(__file__).resolve().parent / "evo"


def starts(arm):
    """-> list of (label, u0) for restarts 1..3."""
    d = x0(arm)
    if arm == "fly":
        p4 = np.array(json.loads((PART4 / "fly" / "best_genome.json").read_text())["u"])
        fresh = np.random.default_rng(99).uniform(0.05, 0.95, len(SPECS["fly"]))
        return [("part4_default", d), ("part4_restart3", p4), ("fresh", fresh)]
    return [("default", d)] * 3


def eval_pop(pool, arm, decoded):
    ctl = CONTROLLER[arm]
    alljobs = [j for k, _ in decoded for j in jobs(k, ctl, TRAIN)]
    res = pool.pool.map(_one, alljobs)
    n = len(TRAIN)
    out = [aggregate(res[i * n:(i + 1) * n]) for i in range(len(decoded))]
    for o, i in zip(out, range(len(decoded))):
        o["flag_all"] = bool(all(r["flag_get"] for r in res[i * n:(i + 1) * n]))
    return out


def run_arm(arm, pool, restarts=RESTARTS, max_gens=MAX_GENS, popsize=POPSIZE, d=None, sts=None):
    """d / sts override the output dir and the restart starts (Part 5 evolves on the shuffled matrix)."""
    d = d or EVO4 / arm
    d.mkdir(parents=True, exist_ok=True)
    state_p, gen_csv, eval_csv = d / "state.pkl", d / "gen.csv", d / "all_evals.csv"
    sts = sts or starts(arm)
    st = pickle.loads(state_p.read_bytes()) if state_p.exists() else dict(
        restart=1, gen=0, es=None, run_best=None, no_improve=0, arm_best=None, done=False)
    if st["done"]:
        print(arm, "already finished")
        return
    while st["restart"] <= restarts:
        r = st["restart"]
        label, start = sts[r - 1]
        if st["es"] is None:
            st["es"] = cma.CMAEvolutionStrategy(start, SIGMA0, dict(
                popsize=popsize, bounds=[0, 1], seed=r, verbose=-9))
            st.update(gen=0, run_best=None, no_improve=0)
        es = st["es"]
        _drop_from(gen_csv, r, st["gen"])
        _drop_from(eval_csv, r, st["gen"])
        while st["gen"] < max_gens:
            gen = st["gen"]
            X = [np.clip(np.asarray(u), 0, 1) for u in es.ask()]
            if gen == 0:
                X[0] = np.clip(start, 0, 1).copy()   # the start genome itself is always evaluated
            decoded = [decode(arm, u) for u in X]
            ag = eval_pop(pool, arm, decoded)
            fits = [a["fitness"] for a in ag]
            es.tell([list(u) for u in X], [-f for f in fits])
            ib = int(np.argmax(fits))
            if st["run_best"] is None or fits[ib] > st["run_best"]["fitness"]:
                st["run_best"] = dict(fitness=fits[ib], u=list(map(float, X[ib])), genome=decoded[ib][1],
                                      gen=gen, train=ag[ib])
                st["no_improve"] = 0
            else:
                st["no_improve"] += 1
            rb = st["run_best"]
            _append(eval_csv, [dict(restart=r, gen=gen, idx=i, genome=json.dumps(decoded[i][1]),
                                    u=json.dumps(list(map(float, X[i]))), fitness=fits[i],
                                    mean_max_x=ag[i]["mean_max_x"], min_max_x=ag[i]["min_max_x"],
                                    flag_rate=ag[i]["flag_rate"], a_frac=ag[i]["a_frac"],
                                    blind_presses=ag[i]["blind_presses"], max_x=json.dumps(ag[i]["max_x"]),
                                    ends=json.dumps(ag[i]["ends"])) for i in range(len(X))])
            _append(gen_csv, [dict(restart=r, start=label, gen=gen, best_fit=rb["fitness"],
                                   mean_fit=float(np.mean(fits)), best_genome=json.dumps(rb["genome"]),
                                   best_u=json.dumps(rb["u"]), best_mean_max_x=rb["train"]["mean_max_x"],
                                   best_flag_rate=rb["train"]["flag_rate"], best_blind=rb["train"]["blind_presses"],
                                   best_a_frac=rb["train"]["a_frac"], gen_best_fit=fits[ib],
                                   gen_best_genome=json.dumps(decoded[ib][1]),
                                   gen_best_u=json.dumps(list(map(float, X[ib]))),
                                   gen_best_mean_max_x=ag[ib]["mean_max_x"])])
            ab = st["arm_best"]
            if ab is None or rb["fitness"] > ab["fitness"]:
                st["arm_best"] = dict(rb, restart=r, arm=arm, start=label)
                (d / "best_genome.json").write_text(json.dumps(st["arm_best"], indent=2))
            st["gen"] += 1
            _save(state_p, st)
            print(f"[{arm}] r{r}({label}) gen {gen:2d} best {rb['fitness']:.0f} (gen {fits[ib]:.0f}, mean "
                  f"{np.mean(fits):.0f}) maxx {rb['train']['mean_max_x']:.0f} blind {rb['train']['blind_presses']:.1f} "
                  f"flag {rb['train']['flag_rate']:.2f}", flush=True)
            if any(a["flag_all"] for a in ag):
                print(f"[{arm}] r{r} flag on every train episode at gen {gen}", flush=True)
                break
            if st["no_improve"] >= PATIENCE:
                print(f"[{arm}] r{r} no improvement for {PATIENCE} generations", flush=True)
                break
        st.update(restart=r + 1, es=None)
        _save(state_p, st)
    st["done"] = True
    _save(state_p, st)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="all", choices=["spam", "theta", "fly", "all"])
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    arms = ["spam", "theta", "fly"] if a.arm == "all" else [a.arm]
    EVO4.mkdir(exist_ok=True)
    timing_p = EVO4 / "timing.json"
    timing = json.loads(timing_p.read_text()) if timing_p.exists() else {}
    with WorkerPool(a.workers) as pool:
        for arm in arms:
            t0 = time.time()
            run_arm(arm, pool)
            timing[arm] = timing.get(arm, 0.0) + time.time() - t0
            timing_p.write_text(json.dumps(timing, indent=2))
            print(f"[{arm}] done in {timing[arm]:.0f}s", flush=True)


if __name__ == "__main__":
    main()
