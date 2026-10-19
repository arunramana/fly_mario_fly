"""E1s: evolution Stage 1 WITH sour smell on 1-1 (pre-registered in runs/E1s_prereg.md): the same search as E1 (e1_evolve.py) with the 8-gene genome of e1s_genome.py on the 907-neuron sour brain, headroom looming ON. CMA-ES over the genome built from configs/drives.yaml; fitness = mean over the 12 training episodes of
max_x / 3161 + score / 10000; a candidate with ANY grounded A onset with nothing in view (no chosen loom threat and no hum) in any training episode is rejected (fitness -1).
python -m flyrun.e1s_evolve time                 time one episode, project the runtime
python -m flyrun.e1s_evolve run [tag] [wfile]    the search (tag "E1s" = the real brain; E1c0 / E1c1 = shuffled controls with W_steer_jo_orn_shuf{0,1}_rn.npy)
python -m flyrun.e1s_evolve holdout [tag] [wfile]   the best candidate on HOLDOUT, ONCE
python -m flyrun.e1s_evolve plot [tag]           runs/<tag>_genes.png"""
import json
import multiprocessing as mp
import os
import pickle
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from . import e1s_genome as G
from . import episodes4

ROOT = Path(__file__).resolve().parent
BODIES = G.BODIES
REAL = G.WFILE
WORST = -1.0
POP, GENS, PATIENCE, SEED, NPROC = 12, 30, 8, 1, 14
TRAIN12 = [dict(noop_start=n, seed=301 + i + 6 * j, sigma=sg) for j, sg in enumerate((0.0, 0.05)) for i, n in enumerate((0, 7, 15, 19, 29, 37))]
_B = {}


def brain(wfile):
    if wfile not in _B:
        os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = wfile, BODIES
        from .brain import load_brain
        _B[wfile] = load_brain()
    return _B[wfile]


def one_episode(job):
    """-> dict(max_x, score, flag, violations, frames, secs, x_end, cause). violations = grounded A onsets with no chosen loom threat and no hum."""
    wfile, values, ep = job
    from .run import run_episode
    t0 = time.time()
    k, enemy_input = G.knobs_for(values)
    k = replace(k, SENSOR_NOISE=ep["sigma"])
    s, df = run_episode(k, brain(wfile), noop_start=ep["noop_start"], episode_seed=ep["seed"], stuck_frames=150, enemy_input=enemy_input)
    hum = df["hum_level"].fillna(0).to_numpy() if "hum_level" in df else np.zeros(len(df))
    onset = (df.a.to_numpy() == 1) & (np.r_[0, df.a.to_numpy()[:-1]] == 0) & (df.air.to_numpy() == 0)
    viol = int((onset & (df.threat_kind.to_numpy() == "none") & (hum == 0)).sum())
    return dict(max_x=s["max_x"], score=s["score"], flag=bool(s["flag_get"]), violations=viol, frames=s["frames"], secs=time.time() - t0, x_end=s["x_at_end"], cause=s["cause"])


def ep_fitness(r):
    return r["max_x"] / 3161.0 + r["score"] / 10000.0


def candidate_fitness(rs):
    return WORST if any(r["violations"] > 0 for r in rs) else float(np.mean([ep_fitness(r) for r in rs]))


def evaluate(pool, wfile, genes, us):
    vals = [{g.name: g.value(u) for g, u in zip(genes, row)} for row in us]
    jobs = [(wfile, v, ep) for v in vals for ep in TRAIN12]
    res = pool.map(one_episode, jobs, chunksize=1)
    out = []
    for i in range(len(vals)):
        rs = res[i * len(TRAIN12):(i + 1) * len(TRAIN12)]
        out.append(dict(fitness=candidate_fitness(rs), values=vals[i], rejected=any(r["violations"] > 0 for r in rs), mean_max_x=float(np.mean([r["max_x"] for r in rs])),
                        flags=int(sum(r["flag"] for r in rs)), violations=int(sum(r["violations"] for r in rs))))
    return out


def log_best(values, name, wfile):
    from . import e1s_log
    return e1s_log.log_run(values, name, wfile=wfile, brain=brain(wfile), prefix="E1s")


def floors():
    return {k: v["floor"] for k, v in json.load(open(ROOT / "runs" / "E1s_floors.json")).items()}


def main_time():
    genes = G.build(floors())
    v = G.start_values()
    t0 = time.time()
    r = one_episode((REAL, v, dict(noop_start=0, seed=301, sigma=0.0)))
    dt = time.time() - t0
    ep = int(np.ceil(POP * len(TRAIN12) / NPROC))
    print("one episode (start genome, noop 0 sigma 0):", {k: r[k] for k in ("max_x", "score", "flag", "violations", "frames", "secs", "cause")}, "wall", round(dt, 1), "s")
    per_gen = POP * len(TRAIN12) * dt / NPROC
    print(f"projection: {POP * len(TRAIN12)} episodes per generation / {NPROC} workers x {dt:.1f} s = {per_gen / 60:.1f} min per generation (worst case, every episode as long as this one); {GENS} generations = {GENS * per_gen / 3600:.1f} h")


def main_run(tag, wfile):
    import cma
    genes = G.build(floors())
    x0 = [g.unit(g.start) for g in genes]
    prog_path = ROOT / "runs" / f"{tag}_progress.json"
    state_path = ROOT / "runs" / f"{tag}_cma_state.pkl"
    rows, best, stall, gen0 = [], dict(fitness=-9), 0, 0
    if state_path.exists():
        es, rows, best, stall, gen0 = pickle.load(open(state_path, "rb"))
        print("resuming at generation", gen0, flush=True)
    else:
        es = cma.CMAEvolutionStrategy(x0, 0.2, dict(popsize=POP, bounds=[0, 1], seed=SEED, verbose=-9))
    with mp.get_context("spawn").Pool(NPROC) as pool:
        if gen0 == 0:
            start = evaluate(pool, wfile, genes, [x0])[0]
            print("start genome:", {k: start[k] for k in ("fitness", "rejected", "mean_max_x", "flags", "violations")}, flush=True)
            json.dump(dict(start=start, genes=[dict(name=g.name, start=g.start, lo=g.lo, hi=g.hi, log=g.log) for g in genes]), open(ROOT / "runs" / f"{tag}_start.json", "w"), indent=1)
        for gen in range(gen0, GENS):
            t0 = time.time()
            us = es.ask()
            ev = evaluate(pool, wfile, genes, us)
            es.tell(us, [-e["fitness"] for e in ev])
            ib = int(np.argmax([e["fitness"] for e in ev]))
            gbest = ev[ib]
            improved = gbest["fitness"] > best["fitness"] + 1e-9
            if improved:
                best, stall = dict(gbest, gen=gen), 0
            else:
                stall += 1
            row = dict(gen=gen, best=gbest["fitness"], mean=float(np.mean([e["fitness"] for e in ev])), n_rejected=int(sum(e["rejected"] for e in ev)), best_values=gbest["values"], best_flags=gbest["flags"],
                       best_mean_max_x=gbest["mean_max_x"], best_ever=best["fitness"], stall=stall, secs=time.time() - t0, all_values=[e["values"] for e in ev], all_fitness=[e["fitness"] for e in ev])
            rows.append(row)
            log_best(gbest["values"], f"{tag}_gen{gen:02d}_best", wfile)
            json.dump(dict(rows=rows, best=best), open(prog_path, "w"), indent=1)
            pickle.dump((es, rows, best, stall, gen + 1), open(state_path, "wb"))
            print(f"gen {gen:2d} best {gbest['fitness']:.4f} mean {row['mean']:.4f} rejected {row['n_rejected']}/{POP} flags(best) {gbest['flags']}/12 best-ever {best['fitness']:.4f} stall {stall} {row['secs']:.0f}s", flush=True)
            if stall >= PATIENCE:
                print("stopping early: no improvement for", PATIENCE, "generations", flush=True)
                break
    json.dump(dict(rows=rows, best=best, finished=True), open(prog_path, "w"), indent=1)


def holdout_episodes(values, wfile, eps=None):
    """Per episode: flag, max_x, death, ? blocks hit, mushroom, score, back-up presses / frames, A with nothing in view (violations)."""
    from . import c1_run as C
    from .run import run_episode
    k0, enemy_input = G.knobs_for(values)
    rows = []
    for e in (eps or episodes4.HOLDOUT):
        ep = dict(noop_start=e["noop_start"], seed=e["seed"], sigma=e["sigma"])
        pr = C.Probe()
        s, df = run_episode(replace(k0, SENSOR_NOISE=ep["sigma"]), brain(wfile), noop_start=ep["noop_start"], episode_seed=ep["seed"], stuck_frames=150, probe=pr, enemy_input=enemy_input)
        df.attrs["hits"], df.attrs["toggles"] = pr.hits, C.toggle_set(k0, enemy_input)
        r = C.analyse(s, df, ep)
        hum = df["hum_level"].fillna(0).to_numpy() if "hum_level" in df else np.zeros(len(df))
        onset = (df.a.to_numpy() == 1) & (np.r_[0, df.a.to_numpy()[:-1]] == 0) & (df.air.to_numpy() == 0)
        r["violations"] = int((onset & (df.threat_kind.to_numpy() == "none") & (hum == 0)).sum())
        bk = df.backup.to_numpy() if "backup" in df else np.zeros(len(df))
        r["backup_frames"] = int(bk.sum())
        r["backup_presses"] = int(((bk == 1) & (np.r_[0, bk[:-1]] == 0)).sum())
        r["stall"] = bool(s["end_reason"] == "stuck")
        for key in ("onsets", "overlap_onsets", "blocks_hit_detail"):
            r.pop(key, None)
        rows.append(r)
        print(ep, r["flag"], r["max_x"], r["cause"], r["blocks_hit"], r["score"], "backups", r["backup_presses"], flush=True)
    return rows


def main_holdout(tag, wfile):
    """The best-ever candidate on HOLDOUT, ONCE."""
    prog = json.load(open(ROOT / "runs" / f"{tag}_progress.json"))
    values = prog["best"]["values"]
    if (ROOT / "runs" / f"{tag}_holdout.json").exists():
        sys.exit("HOLDOUT already run for " + tag + " (once only)")
    rows = holdout_episodes(values, wfile)
    json.dump(dict(values=values, episodes=rows), open(ROOT / "runs" / f"{tag}_holdout.json", "w"), indent=1, default=float)
    print("HOLDOUT flags", sum(r["flag"] for r in rows), "/ 10; mean max_x", np.mean([r["max_x"] for r in rows]), "backup presses", sum(r["backup_presses"] for r in rows))


def main_plot(tag):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    prog = json.load(open(ROOT / "runs" / f"{tag}_progress.json"))
    start = json.load(open(ROOT / "runs" / f"{tag}_start.json"))
    genes = start["genes"]
    rows = prog["rows"]
    fig, axs = plt.subplots(2, 3, figsize=(15, 7), sharex=True)
    for ax, g in zip(axs.flat, genes):
        gen = [r["gen"] for r in rows]
        for r in rows:
            ax.scatter([r["gen"]] * len(r["all_values"]), [v[g["name"]] for v in r["all_values"]], s=8, c="0.75")
        ax.plot(gen, [r["best_values"][g["name"]] for r in rows], "o-", c="tab:red", ms=3, label="generation best")
        ax.axhline(g["start"], c="k", ls="--", lw=0.8, label="start")
        ax.axhspan(g["lo"], g["hi"], color="tab:blue", alpha=0.05)
        ax.set_title(g["name"])
        if g["log"]:
            ax.set_yscale("log")
    axs.flat[0].legend(fontsize=8)
    for ax in axs[1]:
        ax.set_xlabel("generation")
    fig.suptitle(f"{tag}: each gene over the generations (grey = the population, red = the best of the generation, dashed = the start)")
    fig.tight_layout()
    fig.savefig(ROOT / "runs" / f"{tag}_genes.png", dpi=110)
    print("saved", f"{tag}_genes.png")


if __name__ == "__main__":
    cmd = sys.argv[1]
    tag = sys.argv[2] if len(sys.argv) > 2 else "E1s"
    wfile = sys.argv[3] if len(sys.argv) > 3 else REAL
    {"time": lambda: main_time(), "run": lambda: main_run(tag, wfile), "holdout": lambda: main_holdout(tag, wfile), "plot": lambda: main_plot(tag)}[cmd]()
