"""Background evolution: CMA-ES over a fly's evolvable knobs, with elitism, resumable.

    $FLY_MARIO_FLY_DATA/runs/evo_<id>/
        config.json     what was asked (fly yaml path, level, seed, population, moments ...): enough to resume
        start.yaml      the fly we started from
        progress.json   one row per generation: best, mean, best-ever, rejected, best knob values, best run id
        state.pkl       the CMA state after each finished generation (resume reads it)
        dev.json        the final best (and the start) on the dev set, seen once at the end
        best.yaml       the best-ever fly, as a configs/flies/ yaml with provenance (evolved_from, generation, seed)

Elitism: the start genome is evaluated first and is the first best-ever. A later genome replaces the best-ever
only if it scores strictly higher, so the reported best is never worse than the start. The search itself is
standard CMA-ES (population 12, step 0.2 in the unit cube, as in the old E1s run).
"""
from __future__ import annotations

import json
import os
import pickle
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import yaml

from fly_mario_fly.runner import atomic
from fly_mario_fly.runner import config as C
from fly_mario_fly.runner import levels, record
from fly_mario_fly.evolve import devset
from fly_mario_fly.evolve import fitness as F
from fly_mario_fly.evolve import genome as G

POP, SIGMA0 = 12, 0.2           # settings of the old E1s run


def _jobs(fly, scenes, flag_x):
    """One job per training episode; a scene may be (scene, moment id)."""
    out = []
    for s in scenes:
        scene, moment = s if isinstance(s, tuple) else (s, None)
        out.append({"fly": fly, "scene": scene, "moment": moment, "flag_x": flag_x})
    return out


class Pool:
    """Episodes in parallel (spawned processes, each loads its brains from the cache); workers=0 runs in-process."""

    def __init__(self, workers: int):
        self.workers = workers
        self.ex = None
        if workers > 0:
            for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
                os.environ[v] = "1"           # inherited by the spawned workers before numpy loads there
            self.ex = ProcessPoolExecutor(workers, mp_context=get_context("spawn"), initializer=F.worker_init)

    def map(self, jobs: list, on_done=None) -> list:
        """Results in submission order (deterministic). on_done(i, n) fires as the i-th result is collected."""
        if self.ex is None:
            it = (F.play_episode(j) for j in jobs)
        else:
            it = self.ex.map(F.play_episode, jobs, chunksize=1)
        out = []
        for r in it:
            out.append(r)
            if on_done:
                on_done(len(out), len(jobs))
        return out

    def close(self) -> None:
        if self.ex is not None:
            self.ex.shutdown()


def resolve_flag_x(level: str, override: float | None) -> float:
    """The level's flag x: the scan's, else the given one. A level never scanned to its flag cannot normalise progress."""
    if override:
        return float(override)
    info = levels.level_info(level)
    if info.flag_x:
        return float(info.flag_x)
    if info.status.wins:                       # a scan that stopped short: the furthest x a winning run reached is the flag
        return float(info.status.best_x)
    raise SystemExit(f"level {level} has no known flag x (its scan did not reach the flag): pass --flag-x")


def evaluate(pool: Pool, fly, genes, us, scenes, flag_x) -> list:
    """Candidates (rows of unit vectors) -> [{fitness, values, eps}], all episodes in one parallel batch."""
    vals = [G.decode(genes, u) for u in us]
    jobs = [j for v in vals for j in _jobs(G.apply_knobs(fly, v), scenes, flag_x)]
    res = pool.map(jobs)
    n = len(scenes)
    out = []
    for i, v in enumerate(vals):
        eps = res[i * n:(i + 1) * n]
        out.append({"fitness": F.candidate_fitness(eps), "values": v, "eps": eps,
                    "rejected": any(e["violations"] > 0 for e in eps),
                    "flags": sum(e["outcome"] == "flag" for e in eps),
                    "mean_max_x": float(np.mean([e["max_x"] for e in eps]))})
    return out


def _atomic_write(path: Path, data: bytes) -> None:
    atomic.write_bytes(path, data)


def best_fly(fly, values: dict, cfg: dict, gen: int, fitness: float):
    prov = dict(fly.provenance)
    prov.update({"evolved_from": fly.name, "generation": gen, "seed": cfg["seed"], "level": cfg["level"],
                 "train_fitness": round(fitness, 4), "evolved": sorted(values),
                 "evolution": cfg["id"]})
    return replace(G.apply_knobs(fly, values), name=f"{fly.name}_evo_k{cfg['seed']}", provenance=prov)


def save_best_run(fly, scene, moment, flag_x, run_id: str) -> str:
    """Replay one episode of the best genome and keep it as a normal run (video, frames, summary)."""
    F.play_episode({"fly": fly, "scene": scene, "moment": moment, "flag_x": flag_x}, run_id=run_id, save=True)
    return run_id


def run(cfg: dict, pool: Pool | None = None, log=print) -> dict:
    """cfg: id, fly (yaml path or name), level, gens, seed, pop, train_n, flag_x, moments, workers."""
    import cma
    folder = Path(cfg["folder"]) if cfg.get("folder") else record.runs_dir() / cfg["id"]
    folder.mkdir(parents=True, exist_ok=True)
    atomic.write_json(folder / "config.json", cfg)
    fly0 = C.load_fly(cfg["fly"])
    (folder / "start.yaml").write_text(C.dump_fly(fly0), encoding="utf-8")
    genes = G.build_genome(fly0)
    if not genes:
        raise SystemExit(f"{fly0.name}: nothing evolvable is switched on")
    flag_x = resolve_flag_x(cfg["level"], cfg.get("flag_x"))
    scenes = (F.moment_scenes(cfg["level"], cfg["moments"]) if cfg.get("moments")
              else F.train_scenes(cfg["level"]))
    if cfg.get("train_n"):
        scenes = scenes[::max(1, len(scenes) // cfg["train_n"])][:cfg["train_n"]]
    own_pool = pool is None
    pool = pool or Pool(cfg.get("workers", 0))
    state_path, prog_path = folder / "state.pkl", folder / "progress.json"
    t_start = time.time()

    def progress(rows, best, phase, gen_done, extra=None):
        """progress.json: the rows per generation plus where the job is (phase, generation, ETA) for the job screen."""
        done = [r for r in rows if r["gen"] >= 0]
        secs = float(np.mean([r["secs"] for r in done])) if done else None
        left = max(0, cfg["gens"] - gen_done)
        _atomic_write(prog_path, json.dumps({
            "rows": rows, "best_ever": _slim(best), "phase": phase, "generation": gen_done, "gens": cfg["gens"],
            "best": best["fitness"], "mean": rows[-1]["mean"] if rows else None,
            "eta_s": None if secs is None else round(secs * left), "elapsed_s": round(time.time() - t_start),
            "updated": time.time(), **(extra or {})}, indent=1).encode())
    try:
        if state_path.exists():
            es, rows, best, gen0 = pickle.loads(state_path.read_bytes())
            log(f"resuming {cfg['id']} at generation {gen0}")
        else:
            x0 = G.encode(genes)
            start = evaluate(pool, fly0, genes, [x0], scenes, flag_x)[0]
            best = dict(start, gen=-1, run=None)
            best["run"] = _keep_run(fly0, start, scenes, flag_x, cfg, "start")
            log(f"start: fitness {start['fitness']:.4f} flags {start['flags']}/{len(scenes)} "
                f"rejected {start['rejected']} genes {len(genes)}")
            es = cma.CMAEvolutionStrategy(x0, SIGMA0, {"popsize": cfg["pop"], "bounds": [0, 1], "seed": cfg["seed"],
                                                       "verbose": -9})
            rows, gen0 = [], 0
            start_row = {"gen": -1, "best": start["fitness"], "mean": start["fitness"], "best_ever": start["fitness"],
                         "rejected": int(start["rejected"]), "best_values": start["values"], "best_run": best["run"]}
            rows.append(start_row)
            progress(rows, best, "training", 0)
        for gen in range(gen0, cfg["gens"]):
            t0 = time.time()
            us = es.ask()
            ev = evaluate(pool, fly0, genes, us, scenes, flag_x)
            es.tell(us, [-e["fitness"] for e in ev])
            gb = ev[int(np.argmax([e["fitness"] for e in ev]))]
            if gb["fitness"] > best["fitness"] + 1e-12:               # elitism: only a strict improvement replaces it
                best = dict(gb, gen=gen)
                best["run"] = _keep_run(G.apply_knobs(fly0, gb["values"]), gb, scenes, flag_x, cfg, f"g{gen:02d}")
            rows.append({"gen": gen, "best": gb["fitness"], "mean": float(np.mean([e["fitness"] for e in ev])),
                         "best_ever": best["fitness"], "best_ever_gen": best["gen"], "rejected": sum(e["rejected"] for e in ev),
                         "best_flags": gb["flags"], "best_values": gb["values"], "best_run": best["run"],
                         "secs": round(time.time() - t0, 1)})
            _atomic_write(state_path, pickle.dumps((es, rows, _slim(best), gen + 1)))
            progress(rows, best, "training", gen + 1)
            log(f"gen {gen:2d} best {gb['fitness']:.4f} mean {rows[-1]['mean']:.4f} best-ever {best['fitness']:.4f} "
                f"(gen {best['gen']}) rejected {rows[-1]['rejected']}/{cfg['pop']} {rows[-1]['secs']:.0f}s")
        progress(rows, best, "dev set", cfg["gens"])
        out = finish(cfg, fly0, genes, best, rows, flag_x, pool, folder, log)
        progress(rows, best, "done", cfg["gens"], {"dev": {k: v["summary"] for k, v in out["dev"].items()}})
        return out
    finally:
        if own_pool:
            pool.close()


def _slim(best: dict) -> dict:
    return {k: v for k, v in best.items() if k != "eps"} | {"eps": [{k: e[k] for k in ("max_x", "score", "outcome", "violations", "fitness")} for e in best["eps"]]}


def _keep_run(fly, cand: dict, scenes, flag_x, cfg: dict, tag: str) -> str:
    """Save the best episode of this candidate as a run folder; returns its run id."""
    i = int(np.argmax([e["fitness"] for e in cand["eps"]]))
    s = scenes[i]
    scene, moment = s if isinstance(s, tuple) else (s, None)
    return save_best_run(fly, scene, moment, flag_x, f"{cfg['id']}_{tag}")


def finish(cfg, fly0, genes, best, rows, flag_x, pool, folder: Path, log) -> dict:
    """Write the best fly, then run the level's dev set once on the final best (and on the start, for comparison)."""
    fly_best = best_fly(fly0, best["values"], cfg, best["gen"], best["fitness"])
    (folder / "best.yaml").write_text(C.dump_fly(fly_best), encoding="utf-8")
    out = {}
    for tag, fly in (("best", fly_best), ("start", fly0)):
        ev = devset.evaluate(fly, cfg["level"], "tuned", pool=pool, flag_x=flag_x)
        eps = ev["episodes"]
        out[tag] = {**ev["summary"], "summary": ev["summary"], "fitness": F.candidate_fitness(eps),
                    "violations": sum(e["violations"] for e in eps), "episodes": eps}
    atomic.write_json(folder / "dev.json", out)
    log(f"dev set: best {out['best']['flags']}/{out['best']['n']} flags, start {out['start']['flags']}/{out['start']['n']}")
    return {"folder": str(folder), "best": _slim(best), "rows": rows, "dev": out}
