# What this file does, in plain English:
# The standard "is it any good?" test. It runs the project's fly on a fixed set of
# held-out seeds (default 20 seeds, 1000-1019) twice -- once with the real connectome,
# once with its wiring shuffled (same neurons, same in/out counts) -- and reports, for
# each, how often it reaches the flag and how far it gets, with 95% confidence
# intervals. Results are saved in the project (eval.json) for the Learning tab.
"""tool/core/evaluation.py -- docs/SPEC_bio_strict.md phase 1, item 4. Win = reaching the flag. Each run is a
frozen RunSpec (same snapshot as Play); the shuffled arm uses a different degree-preserving shuffle per seed."""

from __future__ import annotations

import dataclasses
import json
import math
import multiprocessing as mp
import os
from datetime import datetime, timezone

import numpy as np

from config.output_routing import PROJECTS_ROOT
from tool.core.run_spec import RunSpec, freeze

DEFAULT_N = 20
DEFAULT_SEED0 = 1000


def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a win rate (sound at small n and at 0 or n wins)."""
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_ci(values, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% percentile-bootstrap interval of the mean (fixed rng: same numbers every time)."""
    v = np.asarray(values, dtype=float)
    if len(v) == 0:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    means = rng.choice(v, size=(n_boot, len(v)), replace=True).mean(axis=1)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def summarize(max_x: list[float], wins: list[bool]) -> dict:
    n = len(max_x)
    k = int(sum(wins))
    lo, hi = wilson_ci(k, n)
    mlo, mhi = bootstrap_ci(max_x)
    return {"n": n, "wins": k, "win_rate": k / n if n else 0.0, "win_rate_ci": [lo, hi],
            "mean_max_x": float(np.mean(max_x)) if n else 0.0, "mean_max_x_ci": [mlo, mhi],
            "median_max_x": float(np.median(max_x)) if n else 0.0, "max_x": [int(x) for x in max_x]}


def _run(spec: RunSpec) -> dict:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    from tool.core.runner import run_one
    _tel, info = run_one(spec)
    return {"max_x": int(info["max_x_abs"]), "flag": bool(info.get("flag_get"))}


def run_eval(project, n: int = DEFAULT_N, seed0: int = DEFAULT_SEED0, workers: int = 1, shuffled: bool = True,
             max_frames: int | None = None, save: bool = True) -> dict:
    """Real connectome vs degree-preserving shuffle on seeds seed0..seed0+n-1. Returns (and saves) the result."""
    cfg = project.config
    if max_frames is not None:
        cfg = dataclasses.replace(cfg, scenario=dataclasses.replace(cfg.scenario, max_frames=max_frames))
    base_ts = dataclasses.replace(project.tool_settings, render=dataclasses.replace(
        project.tool_settings.render, raw_frames=False, record_video=False, death_animation_frames=0))
    arms = {"real": base_ts}
    if shuffled:
        arms["shuffled"] = None
    specs = {}
    for arm in arms:
        for i in range(n):
            ts = base_ts if arm == "real" else dataclasses.replace(
                base_ts, circuits=dataclasses.replace(base_ts.circuits, shuffle_seed=1 + i))
            specs[(arm, i)] = freeze(RunSpec(project_name=project.name, config=cfg, tool_settings=ts,
                                             seed=seed0 + i, out_filename=f"eval_{arm}_{i}.mp4"))
    keys = list(specs)
    if workers > 1:
        with mp.get_context("spawn").Pool(workers) as pool:
            results = pool.map(_run, [specs[k] for k in keys])
    else:
        results = [_run(specs[k]) for k in keys]
    out = {"time": datetime.now(timezone.utc).isoformat(), "seeds": [seed0, seed0 + n - 1], "project": project.name,
           "bio_strict": bool(getattr(project.config, "bio_strict", False))}
    for arm in arms:
        rs = [r for k, r in zip(keys, results) if k[0] == arm]
        out[arm] = summarize([r["max_x"] for r in rs], [r["flag"] for r in rs])
    if save:
        path = eval_path(project.name)
        path.write_text(json.dumps(load_eval_history(project.name) + [out], indent=1), encoding="utf-8")
    return out


def run_eval_streaming(project, queue, workers: int = 4) -> None:
    """Child-process entry point for the Learning tab's button (non-daemon, so it may start its own pool)."""
    try:
        queue.put(("done", run_eval(project, workers=workers)))
    except Exception as exc:  # the parent must learn it failed, not hang
        import traceback
        queue.put(("error", f"{exc}\n{traceback.format_exc()}"))


def eval_path(project_name: str):
    return PROJECTS_ROOT / project_name / "eval.json"


def load_eval_history(project_name: str) -> list[dict]:
    p = eval_path(project_name)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def format_eval(result: dict) -> str:
    """One line per arm: 'real: 3/20 wins (15%, 95% CI 5-36%), max_x mean 1520 (1310-1770), median 1409'."""
    lines = []
    for arm in ("real", "shuffled"):
        if arm in result:
            r = result[arm]
            lines.append(f"{arm}: {r['wins']}/{r['n']} wins ({100 * r['win_rate']:.0f}%, 95% CI "
                         f"{100 * r['win_rate_ci'][0]:.0f}-{100 * r['win_rate_ci'][1]:.0f}%), max_x mean "
                         f"{r['mean_max_x']:.0f} ({r['mean_max_x_ci'][0]:.0f}-{r['mean_max_x_ci'][1]:.0f}), "
                         f"median {r['median_max_x']:.0f}")
    return "  |  ".join(lines)
