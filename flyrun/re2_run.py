"""Part RE2 runner: the E1s champion (runs/E1s_progress.json best, frozen) with the rear toggles.
ARM = A..F (REAR_EYE, REAR_SOUR): A off/off, B on/off, C off/honest, D off/gated, E on/honest, F on/gated.
python -m flyrun.re2_run scene ARM      -> runs/RE2_scene_<ARM>.json + _trace.csv   (1-2, L2 button replay to x 780, then the fly; noop 0, sigma 0)
python -m flyrun.re2_run holdout ARM    -> runs/RE2_holdout_<ARM>.json              (1-1, the 10 dev-set (old HOLDOUT) episodes)
python -m flyrun.re2_run level12 ARM    -> runs/RE2_12_<ARM>.json + _trace.csv      (1-2 from the start, noop 0, sigma 0; information only)"""
import json
import multiprocessing as mp
import os
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
ARMS = {"A": (False, "off"), "B": (True, "off"), "C": (False, "honest"), "D": (False, "gated"), "E": (True, "honest"), "F": (True, "gated")}


def champion():
    return json.load(open(ROOT / "runs" / "E1s_progress.json"))["best"]["values"]


def knobs_for(arm, sigma=0.0, values=None):
    from . import e1s_genome as G
    k, enemy_input = G.knobs_for(values or champion())
    eye, sour = ARMS[arm]
    return replace(k, SENSOR_NOISE=sigma, REAR_EYE=eye, REAR_SOUR=sour != "off", REAR_SOUR_MODE="honest" if sour == "off" else sour), enemy_input


def episode(arm, ep, record=False, takeover_x=None, max_frames=3000):
    from . import av1_run as A
    from . import c1_run as C
    from . import e1s_genome as G
    from .run import run_episode
    k, enemy_input = knobs_for(arm, ep["sigma"])
    pr = C.Probe() if os.environ.get("FLYRUN_LEVEL", "1-1") == "1-1" else A.Probe12()
    s, df = run_episode(k, A.brain(G.WFILE), noop_start=ep["noop_start"], episode_seed=ep["seed"], stuck_frames=150, probe=pr, enemy_input=enemy_input, record=record, max_frames=max_frames, takeover_x=takeover_x)
    df.attrs["hits"], df.attrs["toggles"] = pr.hits, C.toggle_set(k, enemy_input)
    return s, df, k


def trace(df):
    from . import av1_run as A
    out = A.trace(df)
    for c in ("threat_rear", "sour_rear"):
        if c in df:
            out[c] = df[c].fillna(0).astype(int)
    return out


def rear_stats(df):
    """Rear-loom bookkeeping from a trace: frames with a rear threat chosen, A onsets (a new press while grounded) made while the chosen threat was a rear one, Left+A frames, rear-sour frames."""
    tr = df.threat_rear.fillna(0).astype(int) if "threat_rear" in df else df.a * 0
    onset = (df.a == 1) & (df.a.shift(1, fill_value=0) == 0) & (df.air == 0)
    return dict(rear_loom_frames=int(tr.sum()), rear_jump_onsets=int((onset & (tr == 1)).sum()), a_onsets=int(onset.sum()), left_a_frames=int(((df.left == 1) & (df.a == 1)).sum()),
                sour_rear_frames=int(df.sour_rear.fillna(0).sum()) if "sour_rear" in df else 0)


def _job(job):
    arm, ep = job
    from . import av1_run as A
    s, df, _ = episode(arm, ep)
    r = A.summarise(s, df, ep)
    r.update(rear_stats(df))
    return r


def main():
    cmd, arm = sys.argv[1], sys.argv[2]
    if cmd == "holdout":
        from . import episodes4
        eps = [dict(noop_start=e["noop_start"], seed=e["seed"], sigma=e["sigma"]) for e in episodes4.HOLDOUT]
        with mp.get_context("spawn").Pool(6) as pool:
            res = pool.map(_job, [(arm, e) for e in eps])
        json.dump(dict(arm=arm, episodes=res), open(ROOT / "runs" / f"RE2_holdout_{arm}.json", "w"), indent=1, default=float)
        for r in res:
            print(r["noop_start"], r["sigma"], "flag" if r["flag"] else "DIED", r["max_x"], r["cause"], "backups", r["backup_presses"], "rear-loom frames", r["rear_loom_frames"], "traj", r["traj"], flush=True)
        print(arm, "flags", sum(r["flag"] for r in res), "/ 10; mean max_x", np.mean([r["max_x"] for r in res]), "backup presses", sum(r["backup_presses"] for r in res), "rear-caused A onsets", sum(r["rear_jump_onsets"] for r in res), "Left+A frames", sum(r["left_a_frames"] for r in res))
        return
    os.environ["FLYRUN_LEVEL"] = "1-2"
    from . import av1_run as A
    tk = None
    if cmd == "scene":
        from . import scripted
        scripted.Driver = A.ReplayDriver
        tk = 780
    ep = dict(noop_start=0, seed=0, sigma=0.0)
    s, df, k = episode(arm, ep, takeover_x=tk)
    r = A.summarise(s, df, ep)
    r["arm"], r["takeover_x"] = arm, tk
    r.update(rear_stats(df))
    stem = f"RE2_{'scene' if cmd == 'scene' else '12'}_{arm}"
    trace(df).to_csv(ROOT / "runs" / f"{stem}_trace.csv", index=False, lineterminator="\n")
    json.dump(r, open(ROOT / "runs" / f"{stem}.json", "w"), indent=1, default=float)
    print(arm, "max_x", r["max_x"], "flag", r["flag"], "end", r["end"], "cause", r["cause"], "frames", r["frames"], "backup frames", r["backup_frames"], "presses", r["backup_presses"], "rear loom", r["rear_loom_frames"], "sour rear", r["sour_rear_frames"])


if __name__ == "__main__":
    main()
