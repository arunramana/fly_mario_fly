"""Episodes and fitness. One episode = one Run of a fly on a scene; a candidate = the mean over its episodes.

    episode fitness = max_x / flag_x(level) + score / 10000
    safety rule     = a grounded A press while no per-object sense has anything in view rejects the candidate
                      (fitness -1), as in the old run: a fly may not learn to hammer A blindly.

"In view" is generic: some per_object sense (whatever the fly has attached) drives some neuron group this frame.
Whole-fly senses (home, headroom ...) drive all the time and do not count.
"""
from __future__ import annotations

import os
from dataclasses import replace

import numpy as np

from fly_mario.contracts import FlyConfig, Scene
from fly_mario.runner import Run

WORST = -1.0
# The old E1s training set: idle frames 0,7,15,19,29,37 at sensor noise 0 and 0.05 (seeds 301..312).
TRAIN_NOOPS = (0, 7, 15, 19, 29, 37)
TRAIN_SIGMAS = (0.0, 0.05)
# The old holdout set, kept as the dev set: seen only by the final best genome.
DEV_NOOPS = (3, 11, 25, 33, 41)
STUCK_FRAMES = 150          # the old run's stuck rule length (now counted only after Mario's first move)
MAX_FRAMES = 3000


def train_scenes(level: str) -> list:
    return [Scene(level, noop=n, sigma=sg, seed=301 + i + 6 * j, max_frames=MAX_FRAMES, stuck_frames=STUCK_FRAMES)
            for j, sg in enumerate(TRAIN_SIGMAS) for i, n in enumerate(TRAIN_NOOPS)]


def dev_scenes(level: str) -> list:
    return [Scene(level, noop=n, sigma=sg, seed=101 + i, max_frames=MAX_FRAMES, stuck_frames=STUCK_FRAMES)
            for sg in TRAIN_SIGMAS for i, n in enumerate(DEV_NOOPS)]


def moment_scenes(level: str, moment_ids: list) -> list:
    """(scene, moment id) pairs: each saved moment at both noise levels. The moment fixes the start point."""
    base = Scene(level, max_frames=MAX_FRAMES, stuck_frames=STUCK_FRAMES)
    return [(replace(base, sigma=sg, seed=301 + i + 6 * j), m)
            for j, sg in enumerate(TRAIN_SIGMAS) for i, m in enumerate(moment_ids)]


def episode_fitness(max_x: float, score: float, flag_x: float) -> float:
    return max_x / flag_x + score / 10000.0


class BlindA:
    """Counts grounded A onsets with nothing in view."""

    def __init__(self, run: Run):
        self.per_object = {s.name for s in run.senses if s.scope == "per_object"}
        self.prev_a = False
        self.violations = 0

    def __call__(self, rec) -> None:
        a = "A" in rec.buttons
        in_view = any(any(v for v in out.inputs.values()) for n, out in rec.outputs.items() if n in self.per_object)
        self.violations += int(a and not self.prev_a and not rec.airborne and not in_view)
        self.prev_a = a


def play_episode(job: dict, run_id: str = "", save: bool = False) -> dict:
    """job: {fly: FlyConfig, scene: Scene, moment: id or None, flag_x: float}. Returns a plain dict (it crosses processes)."""
    fly: FlyConfig = job["fly"]
    run = Run(fly, job["scene"], from_moment=job.get("moment"), run_id=run_id)
    blind = BlindA(run)
    result = run.play(blind)
    if save:
        from fly_mario.runner import save_run
        save_run(run, result)
    return {"max_x": result.max_x, "score": result.score, "outcome": result.outcome, "violations": blind.violations,
            "frames": result.counts["frames"], "fitness": episode_fitness(result.max_x, result.score, job["flag_x"]),
            "hash": result.hash}


def candidate_fitness(eps: list) -> float:
    if any(e["violations"] > 0 for e in eps):
        return WORST
    return float(np.mean([e["fitness"] for e in eps]))


def worker_init() -> None:
    """Pool workers: one BLAS thread each (the sparse matvec is small); brains come from the on-disk cache."""
    for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[v] = "1"
