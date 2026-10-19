"""E1 section 1: the gain floors, measured on the current 881-neuron brain (nothing is changed; each is a bisection in log space of a yes / no scene).
 HUM_GAIN: the smallest gain at which hum alone (looming off) still hits block 256 in the Q2 scene.
 SMELL_GAIN: the smallest gain at which smell alone (home off) still turns him (a sustained Left, >= 5 frames) in the M2b scene A.
 HOME_R: the smallest value at which he still walks right on his own (nothing in view: Right pressed in >= 95% of frames 30-300).
python -m flyrun.e1_floors -> runs/E1_floors.json"""
import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
WF, BODIES = "W_steer_jo_orn.npy", "steer_jo_orn_bodies.parquet"


def bisect(lo, hi, ok, iters=14):
    """ok(hi) must be True and ok(lo) False; returns the smallest passing value to a relative resolution of (hi/lo)^(1/2^iters), by log bisection."""
    assert ok(hi), "the start value fails its own test"
    if ok(lo):
        return lo, "the lower end already passes"
    for _ in range(iters):
        mid = float(np.sqrt(lo * hi))
        if ok(mid):
            hi = mid
        else:
            lo = mid
    return hi, "bisection"


def hum_hits_256(g):
    from . import q2_run as Q2
    s, df = Q2.run_arm(WF, True, bodies=BODIES, gain=g)
    return any(b["block_x"] == 256 and b["hit"] for b in Q2.blocks(df))


def smell_turns(g):
    from . import m2_run as M, m2b_run as B
    s, df = M.run_fly(WF, True, sigma=0.0, mushroom=True, record=False, gain=g, home=False, setup_fn=M.setup)
    return B.summarise(df, 560)["turned_back"]


def home_walks(h):
    from . import run as R
    from .brain import load_brain
    from .knobs import Knobs
    os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = WF, BODIES
    try:
        k = replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2", SENSOR_NOISE=0.0, PIPE_SENSE=False, PIT_SENSE=False, HOME_R=h)
        s, df = R.run_episode(k, load_brain(), enemy_input=False, max_frames=300, stuck_frames=10 ** 6)
    finally:
        del os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"]
    return float(df.right.iloc[30:300].mean()) >= 0.95


def main():
    out = {}
    for name, start, lo, fn in (("HUM_GAIN", 14.5342, 0.5, hum_hits_256), ("SMELL_GAIN", 213.9495, 2.0, smell_turns), ("HOME_R", 0.5, 0.005, home_walks)):
        v, how = bisect(lo, start, fn)
        out[name] = dict(start=start, floor=v, floor_over_start=v / start, how=how, search_lo=lo)
        print(name, out[name], flush=True)
    json.dump(out, open(ROOT / "runs" / "E1_floors.json", "w"), indent=1)


if __name__ == "__main__":
    main()
