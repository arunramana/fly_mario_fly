"""Part 7e: final-genome selection (rule d) and the single HOLDOUT evaluation.
python -m flyrun.part7 --config flyrun/configs/part7.yaml --stage 7e_select    (writes runs/008e_final_genome.json + reference)
python -m flyrun.part7 --config flyrun/configs/part7.yaml --stage 7e_holdout   (once; needs the final genome committed)"""
import json
import multiprocessing as mp
from pathlib import Path

import numpy as np
import pandas as pd

from . import part7 as P

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
FINAL, REF, RESULT, LOCK = (RUNS / n for n in ("008e_final_genome.json", "008e_reference_genome.json",
                                               "008e_holdout.json", "008e_holdout.lock"))


def _evals(cfg):
    dfs = []
    for label in cfg["budgets"]["stage_7e"]["restarts"]:
        p = ROOT / "evo7e" / label / "all_evals.csv"
        if p.exists():
            dfs.append(pd.read_csv(p, comment="#", keep_default_na=False, na_values=[""]))
    return pd.concat(dfs, ignore_index=True)


def _row(r, cfg, why, stamp):
    u = json.loads(r.u)
    knobs, genome = P.decode(cfg, u)
    assert genome == json.loads(r.genome), "u does not decode to the logged genome"
    return dict(role=why, restart=r.restart, gen=int(r.gen), idx=int(r.idx), genome=genome, u=u, feasible=bool(r.feasible),
                fail=r.fail if isinstance(r.fail, str) else "", train_fitness=float(r.mean_fitness),
                train_mean_max_x=float(r.mean_max_x), train_min_max_x=int(r.min_max_x), train_flags=int(r.flags),
                train_blind_mean=float(r.blind), train_max_x=json.loads(r.max_x), train_ends=json.loads(r.ends), stamp=stamp)


def select(cfg, cfg_path):
    P.require_clean(cfg_path)
    st = P.stamp(cfg_path, cfg)
    ev = _evals(cfg)
    feas = ev[ev.feasible.astype(str) == "True"].sort_values(["fitness", "blind"], ascending=[False, True])
    if feas.empty:
        raise SystemExit("no feasible genome in any 7e restart")
    fin = _row(next(feas.head(1).itertuples()), cfg, "final candidate (rule d: highest feasible TRAIN fitness, ties fewer blind)", st)
    inf = ev[ev.feasible.astype(str) != "True"].sort_values(["mean_max_x", "blind"], ascending=[False, True])
    ref = _row(next(inf.head(1).itertuples()), cfg, "reference only, NOT a candidate (best infeasible by TRAIN mean max_x)", st)
    for path, d in ((FINAL, fin), (REF, ref)):
        path.write_text(json.dumps(d, indent=1), encoding="utf-8", newline=P.LF)
    print(json.dumps({k: fin[k] for k in ("restart", "gen", "genome", "train_fitness", "train_mean_max_x", "train_flags")}, indent=1))
    print("reference:", {k: ref[k] for k in ("restart", "gen", "fail", "train_mean_max_x", "train_flags", "train_blind_mean")})
    return fin, ref


def holdout(cfg, cfg_path, workers):
    P.require_clean(cfg_path)
    rel = FINAL.relative_to(P.REPO).as_posix()
    if not P._git("ls-files", "--", rel).strip() or P._git("status", "--porcelain", "--", rel).strip():
        raise SystemExit("refusing HOLDOUT: runs/008e_final_genome.json is not committed (or was changed after committing)")
    if RESULT.exists() or LOCK.exists():
        raise SystemExit("refusing HOLDOUT: it was already run (008e_holdout.json / .lock exists). HOLDOUT is evaluated once.")
    st = P.stamp(cfg_path, cfg)
    LOCK.write_text("HOLDOUT started " + P.stamp_line(st) + "\n", encoding="utf-8", newline=P.LF)
    out = dict(stamp=st)
    with mp.get_context("spawn").Pool(workers, initializer=P._init) as pool:
        for name, path in (("final", FINAL), ("reference", REF)):
            g = json.loads(path.read_text(encoding="utf-8"))
            knobs, genome = P.decode(cfg, g["u"])
            assert genome == g["genome"]
            ev = P.evaluate(pool, cfg, knobs, "holdout")
            out[name] = dict(role=g["role"], restart=g["restart"], gen=g["gen"], genome=genome, u=g["u"], **ev)
            print(name, {k: ev[k] for k in ("mean_max_x", "flags", "all_constraints_ok")}, flush=True)
    c = cfg["success"]
    f = out["final"]
    out["win"] = bool(f["flags"] >= c["holdout_flags_min"] and f["all_constraints_ok"])
    RESULT.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8", newline=P.LF)
    print("WIN" if out["win"] else "NO WIN")
    return out
