"""CMA-ES over the global knobs. python -m flyrun.evolve --arm fly|theta|both [--workers 12]

Fitness = max_x + 10000*flag_get from deterministic (sigma 0) fly-only episodes, so one episode per
evaluation. Search is in the unit cube (genome.py maps to ranges). Resumable: state.pkl is written
after every generation. Outputs per arm under flyrun/evo/<arm>/: gen.csv, all_evals.csv,
best_genome.json, state.pkl, r<k>_gen_NN.mp4 (that generation's best, every 5 generations)."""
import argparse
import json
import os
import pickle
import time

import cma
import numpy as np
import pandas as pd

from .fitness import WorkerPool
from .genome import CONTROLLER, decode, x0
from .render_stage import EVO, render_genome

POPSIZE, SIGMA0, MAX_GENS, RESTARTS, PATIENCE, RENDER_EVERY = 12, 0.25, 40, 3, 10, 5


def _append(path, rows):
    pd.DataFrame(rows).to_csv(path, mode="a", header=not path.exists(), index=False)


def _drop_from(path, restart, gen):
    """On resume: forget rows of generations that were logged but not checkpointed."""
    if not path.exists():
        return
    df = pd.read_csv(path)
    keep = (df.restart < restart) | ((df.restart == restart) & (df.gen < gen))
    df[keep].to_csv(path, index=False)


def _eval_one(job):
    """Worker: one deterministic episode (module level so spawn can pickle it)."""
    from .fitness import _one
    knobs, ctl = job
    return _one((knobs, 0, ctl, {}))


def _save(path, st):
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(pickle.dumps(st))
    for attempt in range(20):   # Windows can briefly lock the target (indexer / antivirus)
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.5)
    os.replace(tmp, path)


def run_arm(arm, pool, restarts=RESTARTS, max_gens=MAX_GENS, popsize=POPSIZE):
    d = EVO / arm
    d.mkdir(parents=True, exist_ok=True)
    state_p, gen_csv, eval_csv = d / "state.pkl", d / "gen.csv", d / "all_evals.csv"
    ctl = CONTROLLER[arm]
    start = x0(arm)
    st = pickle.loads(state_p.read_bytes()) if state_p.exists() else dict(
        restart=1, gen=0, es=None, run_best=None, no_improve=0, arm_best=None, done=False)
    if st["done"]:
        print(arm, "already finished")
        return
    renders = []
    while st["restart"] <= restarts:
        r = st["restart"]
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
                X[0] = start.copy()   # the defaults themselves are always evaluated in generation 0
            decoded = [decode(arm, u) for u in X]
            out = pool.pool.map(_eval_one, [(k, ctl) for k, _ in decoded])
            fits = [o["fitness"] for o in out]
            es.tell([list(u) for u in X], [-f for f in fits])
            ib = int(np.argmax(fits))
            if st["run_best"] is None or fits[ib] > st["run_best"]["fitness"]:
                st["run_best"] = dict(fitness=fits[ib], u=list(map(float, X[ib])), genome=decoded[ib][1],
                                      max_x=out[ib]["max_x"], end_reason=out[ib]["end_reason"],
                                      death_x=out[ib]["x_at_end"], cause=out[ib]["cause"], gen=gen)
                st["no_improve"] = 0
            else:
                st["no_improve"] += 1
            rb = st["run_best"]
            _append(eval_csv, [dict(restart=r, gen=gen, idx=i, genome=json.dumps(decoded[i][1]),
                                    u=json.dumps(list(map(float, X[i]))), fitness=fits[i],
                                    max_x=out[i]["max_x"], end_reason=out[i]["end_reason"],
                                    death_x=out[i]["x_at_end"], cause=out[i]["cause"])
                                for i in range(len(X))])
            _append(gen_csv, [dict(restart=r, gen=gen, best_fit=rb["fitness"], mean_fit=float(np.mean(fits)),
                                   best_genome=json.dumps(rb["genome"]), best_u=json.dumps(rb["u"]),
                                   best_max_x=rb["max_x"], best_end_reason=rb["end_reason"],
                                   best_death_x=rb["death_x"], best_cause=rb["cause"],
                                   gen_best_fit=fits[ib], gen_best_genome=json.dumps(decoded[ib][1]),
                                   gen_best_u=json.dumps(list(map(float, X[ib]))),
                                   gen_best_max_x=out[ib]["max_x"], gen_best_end=out[ib]["end_reason"],
                                   gen_best_cause=out[ib]["cause"])])
            if gen % RENDER_EVERY == 0:
                renders.append(pool.pool.apply_async(
                    render_genome, (arm, X[ib], str(d / f"r{r}_gen_{gen:02d}.mp4"))))
            ab = st["arm_best"]
            if ab is None or rb["fitness"] > ab["fitness"]:
                st["arm_best"] = dict(rb, restart=r, arm=arm)
                (d / "best_genome.json").write_text(json.dumps(st["arm_best"], indent=2))
            st["gen"] += 1
            _save(state_p, st)
            print(f"[{arm}] r{r} gen {gen:2d} best {rb['fitness']:.0f} (gen {fits[ib]:.0f}, mean "
                  f"{np.mean(fits):.0f}) {rb['end_reason']}@{rb['death_x']}", flush=True)
            if any(o["flag_get"] for o in out):
                print(f"[{arm}] r{r} reached the flag at gen {gen}", flush=True)
                break
            if st["no_improve"] >= PATIENCE:
                print(f"[{arm}] r{r} no improvement for {PATIENCE} generations", flush=True)
                break
        st.update(restart=r + 1, es=None)
        _save(state_p, st)
    st["done"] = True
    _save(state_p, st)
    for rr in renders:
        rr.get()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="both", choices=["fly", "theta", "both"])
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--restarts", type=int, default=RESTARTS)
    ap.add_argument("--max-gens", type=int, default=MAX_GENS)
    a = ap.parse_args()
    arms = ["fly", "theta"] if a.arm == "both" else [a.arm]
    EVO.mkdir(exist_ok=True)
    timing_p = EVO / "timing.json"
    timing = json.loads(timing_p.read_text()) if timing_p.exists() else {}
    with WorkerPool(a.workers) as pool:
        for arm in arms:
            t0 = time.time()
            run_arm(arm, pool, a.restarts, a.max_gens)
            timing[arm] = timing.get(arm, 0.0) + time.time() - t0
            timing_p.write_text(json.dumps(timing, indent=2))
            print(f"[{arm}] done in {timing[arm]:.0f}s", flush=True)


if __name__ == "__main__":
    main()
