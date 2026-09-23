"""sim/fitness.py -- REFACTOR_PLAN.md section 6: "Fitness -- weights on
points, distance and time. 025 proved survival-only is degenerate (an
episode survived 800 frames oscillating at x=658 against a baseline 1432),
so distance is not optional and the GUI must make a survival-only setting
visibly degenerate."

Computed and recorded, nothing more -- per this phase's own instruction,
NOT wired into any decision. Nothing in run_steering.py's actual choice of
action reads a `FitnessWeights` or a `compute_fitness()` result; this
module exists so an episode's outcome CAN be scored after the fact (by a
future GUI, a future training loop, or a report), not so it changes what
happens during one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FitnessWeights:
    """`distance` has no zero default and rejects zero -- 025's own
    finding, made structural rather than just documented: a "points and/or
    time only" configuration is exactly the shape that let an episode
    "survive" 800 frames oscillating at x=658 (a stuck loop, not real
    escape) score AS WELL AS a baseline that actually reached x=1432 and
    then died. `points`/`time` default to 0.0 -- neither has ever been
    validated against a real training run in this project (no episode has
    ever been scored by anything but eyeballing survival/max_x), so 0.0 is
    the honest "not used yet" default, not a considered weighting."""

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
    """Pure function of an episode's own summary numbers -- `distance`
    is `info["max_x_abs"]`, `time` is `info["n_frames"]`, `points` is
    whatever score signal a caller has (none is currently tracked
    anywhere in this project; 0.0 by default is honest about that, not a
    placeholder pretending score exists)."""
    return weights.points * points + weights.distance * distance + weights.time * time
