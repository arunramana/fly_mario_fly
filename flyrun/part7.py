"""Part 7 (assisted, disclosed): the 1-1 win search, pre-registered. Everything comes from configs/part7.yaml.
python -m flyrun.part7 --config flyrun/configs/part7.yaml --stage {check,7d,7e,replay}
7a implements `check` only; 7d / 7e / replay are stubs. Every output is stamped with the git commit, the config
sha256 and the W sha256."""
import argparse
import hashlib
import json
import multiprocessing as mp
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
RUNS = ROOT / "runs"
LF = chr(10)   # outputs are written with LF endings (flyrun/.gitattributes)
EP_REQ = {"noop_start", "seed", "sigma"}


class ConfigError(Exception):
    pass


# ---------------------------------------------------------------- config
def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_config(path):
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    errs = validate(cfg)
    if errs:
        raise ConfigError("; ".join(errs))
    return cfg


def validate(cfg):
    """-> list of problems (empty = valid). Pure: needs nothing but the dict."""
    e = []
    try:
        names = [k["name"] for k in cfg["knobs"]]
        if len(set(names)) != len(names):
            e.append("duplicate knob names")
        for k in cfg["knobs"]:
            if not k["lo"] < k["hi"]:
                e.append(f"knob {k['name']}: lo >= hi")
            if k["int"] and not (float(k["lo"]).is_integer() and float(k["hi"]).is_integer()):
                e.append(f"knob {k['name']}: int knob with non-integer range")
            if not str(k.get("tag", "")).startswith("INVENTED"):
                e.append(f"knob {k['name']}: not tagged INVENTED")
        rule = cfg["conditional_knob_rule"]
        if len(rule["with"]) > rule["max_new_knobs_ever"] or rule["max_new_knobs_ever"] > 2:
            e.append("conditional rule adds more than 2 knobs")
        for k in rule["with"]:
            if not k["lo"] < k["hi"]:
                e.append(f"conditional knob {k['name']}: lo >= hi")
        cm = cfg["cmaes"]
        for key in ("popsize", "max_gens", "patience"):
            if not isinstance(cm[key], int) or cm[key] <= 0:
                e.append(f"cmaes.{key} must be a positive int")
        if not cm["sigma0"] > 0:
            e.append("cmaes.sigma0 must be > 0")
        labels = [r["label"] for r in cfg["restarts"]]
        for r in cfg["restarts"]:
            if not isinstance(r.get("cma_seed"), int):
                e.append(f"restart {r['label']}: cma_seed missing")
            if r["kind"] == "warm":
                u = r.get("u", [])
                if len(u) != len(names) or not all(0.0 <= x <= 1.0 for x in u):
                    e.append(f"restart {r['label']}: u must be {len(names)} values in [0,1]")
            elif r["kind"] == "fresh":
                if not isinstance(r.get("rng"), int):
                    e.append(f"restart {r['label']}: rng seed missing")
            else:
                e.append(f"restart {r['label']}: unknown kind")
        if len({r.get("cma_seed") for r in cfg["restarts"]}) != len(cfg["restarts"]):
            e.append("cma_seed repeated across restarts")
        for b in ("stage_7d", "stage_7e"):
            for l in cfg["budgets"][b]["restarts"]:
                if l not in labels:
                    e.append(f"budgets.{b}: unknown restart {l}")
        for split in ("train", "holdout"):
            for ep in cfg["episodes"][split]:
                if not EP_REQ <= set(ep):
                    e.append(f"episodes.{split}: {ep} missing one of {sorted(EP_REQ)}")
        if {x["seed"] for x in cfg["episodes"]["train"]} & {x["seed"] for x in cfg["episodes"]["holdout"]}:
            e.append("a TRAIN seed also appears in HOLDOUT")
        if len(cfg["episodes"]["holdout"]) != cfg["success"]["holdout_episodes"]:
            e.append("success.holdout_episodes != len(holdout)")
        if cfg["constraints"]["silence_a_frac"] != 0.0:
            e.append("silence constraint must be A_frac == 0")
        _ = cfg["arm"]["w_sha256"], cfg["fitness"]["flag_bonus"], cfg["success"]["holdout_flags_min"]
    except (KeyError, TypeError) as ex:
        e.append(f"missing/invalid field: {ex!r}")
    return e


def decode(cfg, u):
    """Unit cube -> Knobs, with the ranges from the yaml (the rest of Knobs stays as knobs.py)."""
    from .knobs import Knobs
    u = np.clip(np.asarray(u, dtype=float), 0.0, 1.0)
    vals = {}
    for k, x in zip(cfg["knobs"], u):
        v = k["lo"] + x * (k["hi"] - k["lo"])
        vals[k["name"]] = int(round(v)) if k["int"] else float(v)
    return replace(Knobs(), SENSOR_NOISE=0.0, **vals), vals


# ---------------------------------------------------------------- stamping / git
def _git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


def git_status(paths):
    """-> porcelain lines for tracked changes under `paths`, plus untracked .py/.yaml files there
    (run outputs such as evo7/*.pkl are untracked and do not count)."""
    lines = _git("status", "--porcelain", "--", *map(str, paths)).splitlines()
    return [l for l in lines if not l.startswith("??") or l.endswith((".py", ".yaml"))]


def dirty_paths(config_path):
    return git_status([ROOT, Path(config_path).resolve()])


def w_path(cfg):
    from .brain import CACHE
    return CACHE / cfg["arm"]["w_file"]


def env_freeze():
    """-> (pip freeze text of the running interpreter, its sha256)."""
    txt = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, check=True).stdout
    return txt, hashlib.sha256(txt.encode()).hexdigest()


def stamp(cfg_path, cfg):
    """Provenance on every output: git commit (+dirty), config sha256, W sha256, interpreter version, pip-freeze hash.
    The full freeze goes to runs/008_env.txt."""
    freeze, fh = env_freeze()
    RUNS.mkdir(exist_ok=True)
    (RUNS / "008_env.txt").write_text(f"# {sys.version}\n# {sys.executable}\n{freeze}", encoding="utf-8", newline=LF)
    return dict(git_commit=_git("rev-parse", "HEAD").strip(), dirty=bool(dirty_paths(cfg_path)),
                config_sha256=sha256(cfg_path), w_sha256=sha256(w_path(cfg)),
                python=sys.version, pip_freeze_sha256=fh)


def stamp_line(st):
    return (f"commit {st['git_commit'][:10]}{' +DIRTY' if st['dirty'] else ''}, config {st['config_sha256'][:12]}, "
            f"W {st['w_sha256'][:12]}, python {st['python'].split()[0]}, pip-freeze {st['pip_freeze_sha256'][:12]}")


def require_clean(cfg_path):
    d = dirty_paths(cfg_path)
    if d:
        raise SystemExit("refusing to run: uncommitted changes to flyrun/ or the config:\n  " + "\n  ".join(d))


# ---------------------------------------------------------------- evaluation
_B = None


def _init():
    global _B
    from .brain import load_brain
    _B = load_brain()


def _ep(job):
    """One episode (or the silence control) -> summary + the constraint inputs. Mirrors fitness._one / fair_eval._ep."""
    from .run import run_episode
    knobs, ep, fit = job
    t0 = time.time()
    if ep == "silence":    # nothing in view: no enemies, no pipes, no pits
        k = replace(knobs, PIPE_SENSE=False, PIT_SENSE=False)
        _, df = run_episode(k, _B, enemy_input=False, max_frames=fit["silence_max_frames"], stuck_frames=10**6)
        return dict(kind="silence", a_frac=float(df.a.mean()), secs=time.time() - t0)
    k = replace(knobs, SENSOR_NOISE=ep["sigma"])
    s, df = run_episode(k, _B, noop_start=ep["noop_start"], episode_seed=ep["seed"], stuck_frames=150)
    if int((df["driver"] == "script").sum()):
        raise RuntimeError(f"scripted frames inside a Part 7 evaluation: seed {ep['seed']}")
    on = df[(df.a == 1) & (df.a.shift(1, fill_value=0) == 0)]
    d0 = float(on.iloc[0].stim_d) if not on.empty and on.iloc[0].stim_d is not None else float("nan")
    first_d = None if np.isnan(d0) else d0
    fitness = s["max_x"] + fit["flag_bonus"] * int(s["flag_get"]) - fit["blind_penalty"] * s["blind_presses"]
    return dict(kind="episode", noop_start=ep["noop_start"], seed=ep["seed"], sigma=ep["sigma"], max_x=s["max_x"],
                flag=bool(s["flag_get"]), blind=s["blind_presses"], n_onsets=s["n_onsets"], fitness=fitness,
                end=s["end_reason"], cause=s["cause"], first_a_stim_d=first_d, any_a=not on.empty,
                first_a_ok=first_d is not None and first_d <= fit["blind_px"], secs=time.time() - t0)


def evaluate(pool, cfg, knobs, split):
    """-> episodes with per-episode constraint flags, silence A_frac (one run per genome), mean_max_x, flags."""
    c = cfg["constraints"]
    fit = dict(cfg["fitness"], silence_max_frames=c["silence_max_frames"])
    res = pool.map(_ep, [(knobs, e, fit) for e in cfg["episodes"][split]] + [(knobs, "silence", fit)])
    rows, sil = res[:-1], res[-1]
    for r in rows:
        r["c_silence"] = sil["a_frac"] == c["silence_a_frac"]
        r["c_first_a"] = r["first_a_ok"] if c["first_a_at_threat"] else True
        r["c_blind"] = r["blind"] <= c["max_blind_presses"]
        r["constraints_ok"] = r["c_silence"] and r["c_first_a"] and r["c_blind"]
    return dict(episodes=rows, silence_a_frac=sil["a_frac"], silence_secs=sil["secs"],
                mean_max_x=float(np.mean([r["max_x"] for r in rows])), flags=int(sum(r["flag"] for r in rows)),
                mean_fitness=float(np.mean([r["fitness"] for r in rows])),
                all_constraints_ok=all(r["constraints_ok"] for r in rows))


# ---------------------------------------------------------------- stage: check
def table(header, rows):
    rows = [[str(x) for x in r] for r in rows]
    w = [max(len(x) for x in col) for col in zip(header, *rows)]
    f = lambda r: "| " + " | ".join(x.ljust(n) for x, n in zip(r, w)) + " |"
    return "\n".join([f(header), "|" + "|".join("-" * (n + 2) for n in w) + "|", *map(f, rows)])


def stage_check(cfg, cfg_path, workers):
    import pandas as pd
    from . import episodes4, genome, knobs as KN
    st = stamp(cfg_path, cfg)
    out, md = dict(stamp=st), []

    def P(s=""):
        print(s, flush=True)
        md.append(s)

    P(f"# Part 7 check  ({stamp_line(st)})\n")

    # 1. validation (validate() already ran in load_config)
    ho_ref = [dict(noop_start=e["noop_start"], seed=e["seed"], sigma=e["sigma"]) for e in episodes4.HOLDOUT]
    ho_cfg = [dict(noop_start=e["noop_start"], seed=e["seed"], sigma=float(e["sigma"])) for e in cfg["episodes"]["holdout"]]
    fly = [(n, float(lo), float(hi), bool(i)) for n, lo, hi, i in genome.FLY]
    v = [("yaml validates", True),
         ("W sha256 matches the file", st["w_sha256"] == cfg["arm"]["w_sha256"]),
         ("HOLDOUT == Part 6b (episodes4.HOLDOUT)", ho_cfg == ho_ref),
         ("knob ranges == Part 6b (genome.FLY)",
          [(k["name"], float(k["lo"]), float(k["hi"]), k["int"]) for k in cfg["knobs"]] == fly),
         ("fitness constants == knobs.py", (cfg["fitness"]["flag_bonus"], cfg["fitness"]["blind_penalty"],
                                            cfg["fitness"]["blind_px"]) == (KN.FLAG_BONUS, KN.BLIND_PENALTY, KN.BLIND_PX)),
         ("every restart has an explicit CMA seed", all(isinstance(r["cma_seed"], int) for r in cfg["restarts"]))]
    gen = pd.read_csv(ROOT / "evo6" / "real" / "gen.csv")
    for r in cfg["restarts"]:
        if r["kind"] == "warm":
            last = gen[gen.restart == r["source"]["restart"]].sort_values("gen").iloc[-1]
            v.append((f"{r['label']}: u == evo6/real gen.csv restart {r['source']['restart']}",
                      bool(np.allclose(r["u"], json.loads(last.best_u), rtol=0, atol=1e-15))))
            v.append((f"{r['label']}: yaml decode == genome.decode",
                      decode(cfg, r["u"])[0] == genome.decode("fly", np.array(r["u"]))[0]))
    P("## 1. Config validation\n")
    P(table(["check", "result"], [(a, "PASS" if b else "FAIL") for a, b in v]))
    P()

    # 2. + 3. re-evaluate r3, r2 on HOLDOUT; constraints per episode
    ref = json.loads((RUNS / "007_fair_eval.json").read_text())
    key = {"warm_r3": "real/r3_fresh98", "warm_r2": "real/r2_fresh99"}
    out["holdout"], rep = {}, []
    with mp.get_context("spawn").Pool(workers, initializer=_init) as pool:
        for r in [r for r in cfg["restarts"] if r["kind"] == "warm"]:
            kn, vals = decode(cfg, r["u"])
            ev = evaluate(pool, cfg, kn, "holdout")
            exp = cfg["reproduction"][r["label"]]
            same_list = [e["max_x"] for e in ev["episodes"]] == ref[key[r["label"]]]["max_x"]
            ok = round(ev["mean_max_x"], 1) == exp["mean_max_x"] and ev["flags"] == exp["flags"]
            rep.append((r["label"], f"{ev['mean_max_x']:.1f}", exp["mean_max_x"], ev["flags"], exp["flags"],
                        same_list, "PASS" if ok else "FAIL"))
            out["holdout"][r["label"]] = dict(genome=vals, **ev, reproduces=ok, max_x_list_identical=same_list)
        P("## 2. Part 6b HOLDOUT reproduction\n")
        P(table(["restart", "mean_max_x", "expected", "flags", "expected", "max_x list identical", "result"], rep))
        P()
        P("## 3. Constraints on HOLDOUT, per episode (silence is one run per genome)\n")
        for lab, d in out["holdout"].items():
            P(f"**{lab}**  genome {d['genome']}  silence A_frac = {d['silence_a_frac']:.3f}  "
              f"-> all constraints on every episode: {'PASS' if d['all_constraints_ok'] else 'FAIL'}\n")
            P(table(["noop", "seed", "sigma", "max_x", "end", "silence", "first A at threat", "blind<=8"],
                    [(e["noop_start"], e["seed"], e["sigma"], e["max_x"], "flag" if e["flag"] else e["cause"],
                      "ok" if e["c_silence"] else "FAIL",
                      ("ok" if e["c_first_a"] else "FAIL")
                      + (f" ({e['first_a_stim_d']:.0f}px)" if e["first_a_stim_d"] is not None else " (no stimulus/no A)"),
                      ("ok" if e["c_blind"] else "FAIL") + f" ({e['blind']})") for e in d["episodes"]]))
            P()

        # 4. timing: one TRAIN evaluation of r3 (6 episodes + the silence run), all jobs in parallel
        kn, _ = decode(cfg, [r for r in cfg["restarts"] if r["label"] == "warm_r3"][0]["u"])
        t0 = time.time()
        tr = evaluate(pool, cfg, kn, "train")
        wall = time.time() - t0
    secs = [e["secs"] for e in tr["episodes"]] + [tr["silence_secs"]]
    cm = cfg["cmaes"]
    per_gen_cpu = cm["popsize"] * float(np.sum(secs))                  # worker-seconds for one generation
    est = lambda gens, w: per_gen_cpu * gens / w
    b7d, b7e = cfg["budgets"]["stage_7d"], cfg["budgets"]["stage_7e"]
    g7d = len(b7d["restarts"]) * b7d["gens_per_restart"]
    g7e = len(b7e["restarts"]) * b7e["max_gens_per_restart"]
    P("## 4. TRAIN timing (r3 genome, 6 TRAIN episodes + 1 silence run)\n")
    P(f"wall for one evaluation on {workers} workers: {wall:.1f}s;  per-job seconds: " + ", ".join(f"{s:.1f}" for s in secs))
    P(f"TRAIN: mean_max_x {tr['mean_max_x']:.0f}, flags {tr['flags']}/6, all constraints ok: {tr['all_constraints_ok']}\n")
    P(f"One generation = {cm['popsize']} genomes x 7 jobs = {per_gen_cpu:.0f} worker-s (job speed measured with up to "
      f"{workers} concurrent workers). Estimates assume perfect packing:\n")
    P(table(["stage", "generations", "wall @12 workers", "wall @8 workers"],
            [("7d short", g7d, f"{est(g7d, 12) / 60:.0f} min", f"{est(g7d, 8) / 60:.0f} min"),
             ("7e full (upper bound, no early stop)", g7e, f"{est(g7e, 12) / 3600:.1f} h", f"{est(g7e, 8) / 3600:.1f} h")]))
    P(f"\n7e cap {b7e['wall_clock_cap_hours']} h: " + ("binds" if est(g7e, 12) / 3600 > b7e["wall_clock_cap_hours"] else "does not bind"))
    out["timing"] = dict(train_eval=tr, wall=wall, per_gen_cpu_s=per_gen_cpu, est_7d_min_12w=est(g7d, 12) / 60,
                         est_7e_h_12w=est(g7e, 12) / 3600, workers=workers)
    out["checks"] = dict(v)
    out["ok"] = all(b for _, b in v) and all(d["reproduces"] for d in out["holdout"].values())
    P(f"\n**check: {'PASS' if out['ok'] else 'FAIL'}** (constraint failures on r3/r2 are information, not check failures)")
    RUNS.mkdir(exist_ok=True)
    (RUNS / "008_check.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8", newline=LF)
    (RUNS / "008_check.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline=LF)
    return out


# ---------------------------------------------------------------- stages not in 7a
def stage_stub(name):
    raise NotImplementedError(f"stage {name} is not implemented in 7a")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--stage", required=True, choices=["check", "7d", "7e", "replay"])
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    if a.stage in ("7d", "7e"):
        require_clean(a.config)
    if a.stage == "check":
        return stage_check(cfg, a.config, a.workers)
    if a.stage == "replay":
        from .diagnose7b import dump_holdout   # 7b: per-frame replay of warm r3 on HOLDOUT
        return dump_holdout(cfg, stamp(a.config, cfg))
    stage_stub(a.stage)


if __name__ == "__main__":
    main()
