"""Part S3 sections 1-2: the Part 6b HOLDOUT list (10 episodes) for the real fly, 5 row-renormalised shuffles, the theta-rule and the blind timer.
All arms: senses v2 (rim + pit hole), MOTOR v2 where a brain exists, default knobs (no tuning). Writes runs/S3_holdout.json.
python -m flyrun.s3_eval"""
import hashlib
import json
import multiprocessing as mp
import os
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from . import episodes4
from .knobs import Knobs

ROOT = Path(__file__).resolve().parent
KN = replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2")
ARMS = ["real"] + [f"shuf{i}" for i in range(5)] + ["theta_rule", "blind_timer"]
_B = {}


def _brain(arm):
    from .brain import load_brain
    wfile = "W_steer.npy" if not arm.startswith("shuf") else f"W_steer_{arm}_rn.npy"
    if wfile not in _B:
        os.environ["FLYRUN_WFILE"] = wfile
        _B[wfile] = load_brain()
    return _B[wfile]


def _ep(job):
    from .run import run_episode
    from . import s3_controls as C
    arm, ep, trig = job
    t0 = time.time()
    brain = _brain("real" if arm in ("theta_rule", "blind_timer") else arm)
    ctrl = {"theta_rule": lambda: C.theta_rule(trig), "blind_timer": lambda: C.BlindTimer}.get(arm, lambda: None)()
    if ep == "silence":    # nothing in view: no enemies, no pipes, no pits
        k = replace(KN, PIPE_SENSE=False, PIT_SENSE=False)
        _, df = run_episode(k, brain, enemy_input=False, max_frames=600, stuck_frames=10**6, controller=ctrl)
        return dict(arm=arm, kind="silence", a_frac=float(df.a.mean()))
    k = replace(KN, SENSOR_NOISE=ep["sigma"], MOTOR_VERSION="v2")
    s, df = run_episode(k, brain, noop_start=ep["noop_start"], episode_seed=ep["seed"], stuck_frames=150, controller=ctrl)
    on = df[(df.a == 1) & (df.a.shift(1, fill_value=0) == 0) & (df.air == 0)]
    onsets = [(float(np.degrees(r.theta)), str(r.threat_kind), None if r.stim_d is None or r.stim_d != r.stim_d else float(r.stim_d), int(r.x))
              for r in on.itertuples()]
    h = hashlib.md5((",".join(map(str, df.x)) + "|" + ",".join(map(str, df.a))).encode()).hexdigest()[:10]
    return dict(arm=arm, kind="episode", noop_start=ep["noop_start"], seed=ep["seed"], sigma=ep["sigma"], max_x=s["max_x"], flag=bool(s["flag_get"]),
                end=s["end_reason"], x_end=s["x_at_end"], cause=s["cause"], blind=s["blind_presses"], left_presses=s.get("left_presses", 0),
                a_frac=s["a_frac"], onsets=onsets, traj=h, frames=s["frames"], secs=time.time() - t0)


def measure_trigger(rows):
    """Median theta (deg) at the fly's grounded A onsets on enemies / faces, excluding re-presses touching the threat (stim_d < 5) and pits."""
    th = [o[0] for r in rows for o in r["onsets"] if o[1] in ("goomba", "koopa", "face") and o[2] is not None and o[2] >= 5]
    return float(np.median(th)), len(th), float(np.min(th)), float(np.max(th))


def main():
    eps = [dict(noop_start=e["noop_start"], seed=e["seed"], sigma=e["sigma"]) for e in episodes4.HOLDOUT]
    out = {}
    with mp.get_context("spawn").Pool(6) as pool:
        real = pool.map(_ep, [("real", e, None) for e in eps] + [("real", "silence", None)])
        trig, n, lo, hi = measure_trigger([r for r in real if r["kind"] == "episode"])
        print("trigger angle", trig, n, lo, hi, flush=True)
        out["trigger"] = dict(median_deg=trig, n_onsets=n, min_deg=lo, max_deg=hi)
        out["real"] = real
        rest = [a for a in ARMS if a != "real"]
        res = pool.map(_ep, [(a, e, trig) for a in rest for e in eps + ["silence"]])
        for a in rest:
            out[a] = [r for r in res if r["arm"] == a]
    (ROOT / "runs" / "S3_holdout.json").write_text(json.dumps(out, indent=1))
    for a in ARMS:
        ep = [r for r in out[a] if r["kind"] == "episode"]
        print(a, "flags", sum(r["flag"] for r in ep), "max_x", [r["max_x"] for r in ep], "traj", len({r["traj"] for r in ep}),
              "silence", [r["a_frac"] for r in out[a] if r["kind"] == "silence"], flush=True)


if __name__ == "__main__":
    main()
