# What this file does, in plain English:
# Gives a finished game a single score: a weighted sum of points, distance
# travelled and time. By default only distance counts, and a setting that
# gives distance zero or negative weight is refused, because an earlier run
# showed that scoring survival alone rewards getting stuck. Nothing that
# decides Mario's moves reads this score; only the tests use it so far.
"""sim/fitness.py -- scores an episode after the fact from points, distance
and time. Nothing that chooses an action reads it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FitnessWeights:
    """`distance` must be > 0: survival-only scoring is degenerate (run 025,
    see the error below). `points`/`time` default to 0.0 because neither
    has been validated against a real run."""

    points: float = 0.0
    distance: float = 1.0
    time: float = 0.0

    def __post_init__(self):
        if self.distance <= 0.0:
            raise ValueError(
                "FitnessWeights.distance must be > 0 -- 025 proved "
                "survival/points-only fitness is degenerate (an episode "
                "'survived' 800 frames oscillating at x=658 against a "
                "baseline that reached x=1432 and died); distance is not "
                "optional and cannot be configured away to zero."
            )


def compute_fitness(weights: FitnessWeights, *, distance: float, time: float = 0.0,
                     points: float = 0.0) -> float:
    """`distance` is `info["max_x_abs"]`, `time` is `info["n_frames"]`.
    Nothing tracks `points` yet."""
    return weights.points * points + weights.distance * distance + weights.time * time
