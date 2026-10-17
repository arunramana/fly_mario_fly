"""Part 7d/7e search engine: CMA-ES over the config's knobs on TRAIN only, constraints enforced.
Called from part7.py (`--stage 7d|7e`); reads only the config. Per restart, under flyrun/<evo7d|evo7e>/<label>/:
gen.csv, all_evals.csv, best_genome.json, state.pkl (checkpoint/resume), stamp.json.

Fitness of a genome = mean over TRAIN episodes of max_x + flag_bonus*flag - blind_penalty*blind, and -inf if ANY TRAIN
episode fails a constraint (silence A_frac == 0, first A at a threat, blind presses <= max). The logged / selected value
is -inf. CMA-ES minimises, so it is told  -(-1e6 + mean_fitness)  for infeasible genomes: strictly worse than every feasible
genome (feasible fitness >= -450), and the infeasible still rank among themselves by their raw fitness. Ranking among feasible
genomes and feasible-vs-infeasible is identical to -inf; only the order *among* infeasible genomes is graded (an
implementation detail, not a scalar of the fly)."""
import json
import multiprocessing as mp
import os
import pickle
import shutil
import time
from dataclasses import replace
from pathlib import Path

import cma
import numpy as np
import pandas as pd

from . import part7 as P

ROOT = Path(__file__).resolve().parent
INFEASIBLE_BASE = -1.0e6
LF = P.LF


def stage_dir(stage):
    return ROOT / {"7d": "evo7d", "7e": "evo7e"}[stage]


def start_of(cfg, restart):
    if restart["kind"] == "warm":
        return np.array(restart["u"], dtype=float)
    lo, hi = restart["fresh_range"]
    return np.random.default_rng(restart["rng"]).uniform(lo, hi, len(cfg["knobs"]))


def eval_pop(pool, cfg, genomes, split="train"):
    """Evaluate a list of Knobs on a split (+ one silence run each); one flat pool.map for all of them.
    -> per genome: dict(fitness (-inf if infeasible), feasible, mean_fitness, mean_max_x, ..., episodes=[...], fail=[...])"""
    c = cfg["constraints"]
    fit = dict(cfg["fitness"], silence_max_frames=c["silence_max_frames"])
    eps = cfg["episodes"][split]
    per = len(eps) + 1
    res = pool.map(P._ep, [j for k in genomes for j in [(k, e, fit) for e in eps] + [(k, "silence", fit)]])
    out = []
    for g in range(len(genomes)):
        rows, sil = res[g * per:(g + 1) * per - 1], res[(g + 1) * per - 1]
        fail = []
        if sil["a_frac"] != c["silence_a_frac"]:
            fail.append("silence")
        for r in rows:
            if c["first_a_at_threat"] and not r["first_a_ok"]:
                fail.append("first_a")
            if r["blind"] > c["max_blind_presses"]:
                fail.append("blind")
        mf = float(np.mean([r["fitness"] for r in rows]))
        out.append(dict(episodes=rows, silence_a_frac=sil["a_frac"], mean_fitness=mf, feasible=not fail,
                        fail=sorted(set(fail)), fitness=mf if not fail else float("-inf"),
                        mean_max_x=float(np.mean([r["max_x"] for r in rows])), min_max_x=int(min(r["max_x"] for r in rows)),
                        flags=int(sum(r["flag"] for r in rows)), blind=float(np.mean([r["blind"] for r in rows]))))
    return out


def _append(path, rows, header_comment):
    new = not path.exists()
    with open(path, "a", encoding="utf-8", newline=LF) as f:
        if new:
            f.write(header_comment + "\n")
        pd.DataFrame(rows).to_csv(f, header=new, index=False, lineterminator=LF)


def _drop_from(path, restart_label, gen):
    """On resume: forget rows of generations that were logged but not checkpointed."""
    if not path.exists():
        return
    head = path.read_text(encoding="utf-8").split("\n", 1)[0]
    df = pd.read_csv(path, comment="#")
    keep = (df.restart != restart_label) | (df.gen < gen)
    with open(path, "w", encoding="utf-8", newline=LF) as f:
        f.write(head + "\n")
        df[keep].to_csv(f, index=False, lineterminator=LF)


def _save(path, st):
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(pickle.dumps(st))
    for _ in range(20):   # Windows can briefly lock the target
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.5)
    raise PermissionError(path)


def run_restart(pool, cfg, restart, d, gens, stamp, hdr, log=print, deadline=None):
    d.mkdir(parents=True, exist_ok=True)
    (d / "stamp.json").write_text(json.dumps(stamp, indent=1), encoding="utf-8", newline=LF)
    cm, label = cfg["cmaes"], restart["label"]
    state_p, gen_csv, eval_csv = d / "state.pkl", d / "gen.csv", d / "all_evals.csv"
    start = start_of(cfg, restart)
    st = pickle.loads(state_p.read_bytes()) if state_p.exists() else dict(
        gen=0, es=None, best=None, no_improve=0, done=False, secs=0.0)
    if st["done"]:
        log(label, "already finished")
        return st
    if st["es"] is None:
        st["es"] = cma.CMAEvolutionStrategy(start, cm["sigma0"], dict(
            popsize=cm["popsize"], bounds=cm["bounds"], seed=restart["cma_seed"], verbose=-9))
    es = st["es"]
    _drop_from(gen_csv, label, st["gen"])
    _drop_from(eval_csv, label, st["gen"])
    while st["gen"] < min(gens, cm["max_gens"]):
        if deadline and time.time() > deadline:
            log(f"[{label}] wall-clock cap reached at gen {st['gen']}; checkpoint kept, restart not marked done")
            return st
        t0, gen = time.time(), st["gen"]
        X = [np.clip(np.asarray(u), 0, 1) for u in es.ask()]
        if gen == 0:
            X[0] = np.clip(start, 0, 1).copy()    # the start genome itself is always evaluated
        dec = [P.decode(cfg, u) for u in X]
        ev = eval_pop(pool, cfg, [k for k, _ in dec])
        told = [-(e["fitness"] if e["feasible"] else INFEASIBLE_BASE + e["mean_fitness"]) for e in ev]
        es.tell([list(u) for u in X], told)
        feas = [i for i, e in enumerate(ev) if e["feasible"]]
        ib = max(feas, key=lambda i: ev[i]["fitness"]) if feas else int(np.argmax([e["mean_fitness"] for e in ev]))
        if feas and (st["best"] is None or ev[ib]["fitness"] > st["best"]["fitness"]):
            st["best"] = dict(fitness=ev[ib]["fitness"], u=list(map(float, X[ib])), genome=dec[ib][1], gen=gen,
                              train=ev[ib])
            st["no_improve"] = 0
            (d / "best_genome.json").write_text(json.dumps(dict(st["best"], restart=label, stamp=stamp), indent=1, default=str),
                                                encoding="utf-8", newline=LF)
        else:
            st["no_improve"] += 1
        _append(eval_csv, [dict(restart=label, gen=gen, idx=i, genome=json.dumps(dec[i][1]), u=json.dumps(list(map(float, X[i]))),
                                feasible=e["feasible"], fail="+".join(e["fail"]), fitness=e["fitness"], mean_fitness=e["mean_fitness"],
                                mean_max_x=e["mean_max_x"], min_max_x=e["min_max_x"], flags=e["flags"], blind=e["blind"],
                                silence_a_frac=e["silence_a_frac"], max_x=json.dumps([r["max_x"] for r in e["episodes"]]),
                                ends=json.dumps([r["cause"] if not r["flag"] else "flag" for r in e["episodes"]]))
                           for i, e in enumerate(ev)], hdr)
        b = st["best"]
        gb = ev[ib]
        _append(gen_csv, [dict(restart=label, gen=gen, n_feasible=len(feas), n_infeasible=len(ev) - len(feas),
                               best_fitness=b["fitness"] if b else float("-inf"), best_u=json.dumps(b["u"]) if b else "",
                               best_genome=json.dumps(b["genome"]) if b else "",
                               best_mean_max_x=b["train"]["mean_max_x"] if b else float("nan"),
                               best_flags=b["train"]["flags"] if b else 0,
                               gen_best_fitness=gb["fitness"], gen_best_u=json.dumps(list(map(float, X[ib]))),
                               gen_best_genome=json.dumps(dec[ib][1]), gen_best_mean_max_x=gb["mean_max_x"],
                               gen_best_max_x=json.dumps([r["max_x"] for r in gb["episodes"]]),
                               gen_best_ends=json.dumps([r["cause"] if not r["flag"] else "flag" for r in gb["episodes"]]),
                               gen_best_feasible=gb["feasible"], gen_best_fail="+".join(gb["fail"]),
                               secs=time.time() - t0)], hdr)
        st["gen"] += 1
        st["secs"] += time.time() - t0
        _save(state_p, st)
        log(f"[{label}] gen {gen:2d}  feasible {len(feas):2d}/{len(ev)}  best {b['fitness'] if b else float('-inf'):.0f}  "
            f"gen-best mean_max_x {gb['mean_max_x']:.0f} min {gb['min_max_x']} flags {gb['flags']}  "
            f"{'FEASIBLE' if gb['feasible'] else 'infeasible:' + '+'.join(gb['fail'])}  {time.time() - t0:.0f}s", flush=True)
        if st["no_improve"] >= cm["patience"]:
            log(f"[{label}] no improvement for {cm['patience']} generations: early stop")
            st["early_stop"] = True
            break
    st["done"] = True
    _save(state_p, st)
    return st


def _seed_continue(cfg, label, d, src):
    """7e R2: copy a finished 7d restart's files into this stage's dir and re-open its CMA state."""
    if (d / "state.pkl").exists():
        return
    d.mkdir(parents=True, exist_ok=True)
    for f in ("state.pkl", "gen.csv", "all_evals.csv", "best_genome.json"):
        shutil.copyfile(src / f, d / f)
    st = pickle.loads((d / "state.pkl").read_bytes())
    st.update(done=False, no_improve=0, early_stop=False, gen0=st["gen"], secs0=st["secs"])
    _save(d / "state.pkl", st)


def _state(d):
    p = d / "state.pkl"
    return pickle.loads(p.read_bytes()) if p.exists() else None


def run_stage(cfg, cfg_path, stage, workers, outdir=None, log=print):
    """7d / 7e. Refuses a dirty tree (done by the caller). -> {label: state}.
    7e: per-restart generation allotments (budgets.stage_7e.gens, counted from the restart's gen at 7e start), a stage-wide
    wall-clock cap, early stop per restart, and a second pass handing the generations early-stopped restarts did not use to
    freed_time_order (first restart that can still run)."""
    b = cfg["budgets"]["stage_" + stage]
    st = P.stamp(cfg_path, cfg)
    hdr = f"# stage {stage}  [{P.stamp_line(st)}]"
    base = outdir or stage_dir(stage)
    t0, out = time.time(), {}
    rs = {r["label"]: r for r in cfg["restarts"]}
    if stage == "7d":
        cap = b.get("wall_clock_cap_hours")
        with mp.get_context("spawn").Pool(workers, initializer=P._init) as pool:
            for label in b["restarts"]:
                out[label] = run_restart(pool, cfg, rs[label], base / label, b["gens_per_restart"], st, hdr, log,
                                         deadline=t0 + cap * 3600 if cap else None)
        return out
    for label, src in b.get("continue_from", {}).items():
        _seed_continue(cfg, label, base / label, ROOT / src / label)
    def spent():
        s = 0.0
        for label in b["restarts"]:
            x = _state(base / label)
            s += (x["secs"] - x.get("secs0", 0.0)) if x else 0.0
        return s
    deadline = t0 + b["wall_clock_cap_hours"] * 3600 - spent()
    log(f"7e: {spent() / 60:.0f} min already spent in earlier sessions; cap leaves {(deadline - t0) / 60:.0f} min")
    with mp.get_context("spawn").Pool(workers, initializer=P._init) as pool:
        def go(label, extra=0):
            x = _state(base / label)
            gen0 = x.get("gen0", 0) if x else 0
            if x and extra and x["done"] and x["gen"] < gen0 + b["gens"][label] + extra and not x.get("early_stop"):
                x["done"] = False                  # re-open a restart that finished its allotment, to spend freed generations
                _save(base / label / "state.pkl", x)
            out[label] = run_restart(pool, cfg, rs[label], base / label, gen0 + b["gens"][label] + extra, st, hdr, log,
                                     deadline=deadline)
        for label in b["restarts"]:
            go(label)
        unused = 0
        for label in b["restarts"]:
            x = _state(base / label)
            if x and x["done"] and x.get("early_stop"):
                unused += max(0, x.get("gen0", 0) + b["gens"][label] - x["gen"])
        log(f"7e: {unused} generations freed by early stops")
        for label in b.get("freed_time_order", []):
            if unused <= 0 or time.time() > deadline:
                break
            x = _state(base / label)
            if not x or x.get("early_stop"):
                continue
            go(label, unused)
            unused = 0
    return out


def montage(cfg, label, d, every=2, scale=2):
    """montage.mp4 for one restart: generation 0, then each generation where the run-best TRAIN mean max_x improved. Each
    stage replays the run-best genome of that generation on the first TRAIN episode, labelled
    'gen N | TRAIN mean max_x M | death cause'."""
    import cv2
    from .brain import load_brain
    from .diagnose7b import capture
    g = pd.read_csv(d / "gen.csv", comment="#")
    keep, prev = [], -1.0
    for r in g.sort_values("gen").itertuples():
        if not r.best_u or (isinstance(r.best_u, float) and np.isnan(r.best_u)):
            continue
        if not keep or r.best_mean_max_x > prev:
            keep.append(r)
        prev = max(prev, r.best_mean_max_x)
    if not keep:
        return None
    brain, ep = load_brain(), cfg["episodes"]["train"][0]
    out, writer = d / "montage.mp4", None
    for r in keep:
        kn, _ = P.decode(cfg, json.loads(r.best_u))
        s, df = capture(replace(kn, SENSOR_NOISE=float(ep["sigma"])), ep, brain, record=True)
        text = f"gen {int(r.gen)} | TRAIN mean max_x {r.best_mean_max_x:.0f} | ep0 {s['cause']} (x {s['max_x']})"
        print(text, flush=True)
        for fr in df.attrs["frames"][::every]:
            f = cv2.resize(np.ascontiguousarray(fr), None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
            cv2.rectangle(f, (0, 0), (f.shape[1], 22), (0, 0, 0), -1)
            cv2.putText(f, text, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            if writer is None:
                writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), 30, (f.shape[1], f.shape[0]))
            lab = cv2.cvtColor(f, cv2.COLOR_RGB2BGR)
            writer.write(lab)
        for _ in range(20):
            writer.write(lab)
    writer.release()
    return out
