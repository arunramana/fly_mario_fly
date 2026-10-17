"""Replay a genome (episodes are deterministic at sigma 0, so the replay is exact) to an mp4.
CLI: python -m flyrun.render_stage --arm fly --gen N [--restart K]  (that generation's best genome)."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import fitness
from .baselines import CONTROLLERS
from .brain import load_brain
from .genome import CONTROLLER, decode
from .run import run_episode, save_video

EVO = Path(__file__).resolve().parent / "evo"


def replay(arm, u, record=True):
    """-> (summary, df) exactly as evaluate() ran it (same limits)."""
    brain = fitness._BRAIN if fitness._BRAIN is not None else load_brain()
    knobs, _ = decode(arm, u)
    ctl = CONTROLLERS[CONTROLLER[arm]] if CONTROLLER[arm] else None
    return run_episode(knobs, brain, controller=ctl, stuck_frames=150, record=record)


def render_genome(arm, u, path):
    """Worker-safe (module level): replay u and write the mp4; returns the summary."""
    s, df = replay(arm, u)
    save_video(df.attrs["frames"], path)
    return s


def best_restart(arm):
    p = EVO / arm / "best_genome.json"
    return json.loads(p.read_text())["restart"] if p.exists() else 1


def gen_best_u(arm, gen, restart=None):
    g = pd.read_csv(EVO / arm / "gen.csv")
    r = best_restart(arm) if restart is None else restart
    row = g[(g.restart == r) & (g.gen == gen)].iloc[0]
    return np.array(json.loads(row.gen_best_u)), r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["fly", "theta"])
    ap.add_argument("--gen", type=int, required=True)
    ap.add_argument("--restart", type=int, default=None)
    a = ap.parse_args()
    u, r = gen_best_u(a.arm, a.gen, a.restart)
    out = EVO / a.arm / f"stage_r{r}_gen{a.gen:02d}.mp4"
    print(render_genome(a.arm, u, out), "->", out)


if __name__ == "__main__":
    main()
