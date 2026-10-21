"""The dev set and `evaluate`: how a fly is judged. Training never sees these starts.

    evaluate(fly, level, dials, starts) -> {"episodes": [per start ...], "summary": {...}}

`starts` defaults to the level's dev set (configs/dev_sets.yaml, 10 starts). `dials` is "tuned" (the fly as it is) or
"original" (every knob back at its hand-set default). Episodes run in a process pool, one per start.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import yaml

from fly_mario.contracts import FlyConfig, Scene

DEV_SETS = Path(__file__).resolve().parents[3] / "configs" / "dev_sets.yaml"      # configs/dev_sets.yaml
MAX_FRAMES, STUCK_FRAMES = 3000, 150          # as in fitness.py (the old run's rules)


def dev_starts(level: str) -> list:
    """The level's dev set: [{noop, sigma, seed}, ...] (its own entry, else `default`)."""
    sets = yaml.safe_load(DEV_SETS.read_text(encoding="utf-8"))
    return [dict(s) for s in sets.get(level, sets["default"])]


def start_scene(level: str, start: dict) -> Scene:
    return Scene(level, noop=int(start["noop"]), sigma=float(start["sigma"]), seed=int(start["seed"]),
                 max_frames=MAX_FRAMES, stuck_frames=STUCK_FRAMES)


def with_dials(fly: FlyConfig, dials: str) -> FlyConfig:
    """"original": every knob at its KnobSpec default (the hand-set value before evolution); "tuned": as is."""
    if dials == "tuned":
        return fly
    return replace(fly, knobs={}, provenance={**fly.provenance, "dials": "original"})


def summarize(episodes: list) -> dict:
    """flags n/10, mean and min max_x, mean score."""
    n = len(episodes)
    xs = [e["max_x"] for e in episodes]
    return {"n": n, "flags": sum(e["outcome"] == "flag" for e in episodes),
            "mean_max_x": float(np.mean(xs)) if n else 0.0, "min_max_x": float(min(xs)) if n else 0.0,
            "mean_score": float(np.mean([e["score"] for e in episodes])) if n else 0.0}


def evaluate(fly: FlyConfig, level: str, dials: str = "tuned", starts: list | None = None, pool=None,
             workers: int = 0, flag_x: float = 1.0, on_done=None) -> dict:
    """Play `fly` from each start. Per start: outcome, max_x, score, counts (+ blocks, mushroom, violations).

    `pool` is an evolve.search.Pool to reuse (the caller closes it); else one is made with `workers` processes
    (0 = in this process). `on_done(i, n)` is called as each episode comes back."""
    from fly_mario.evolve import search           # (search imports this module for the final dev run)
    starts = dev_starts(level) if starts is None else starts
    fly = with_dials(fly, dials)
    jobs = [{"fly": fly, "scene": start_scene(level, s), "moment": None, "flag_x": flag_x} for s in starts]
    own = pool is None
    pool = pool or search.Pool(workers)
    try:
        res = pool.map(jobs, on_done=on_done) if on_done else pool.map(jobs)
    finally:
        if own:
            pool.close()
    keys = ("outcome", "max_x", "score", "counts", "blocks", "mushroom", "violations", "fitness", "death", "frames")
    episodes = [{"start": s, **{k: e.get(k) for k in keys}} for s, e in zip(starts, res)]
    return {"episodes": episodes, "summary": summarize(episodes)}
