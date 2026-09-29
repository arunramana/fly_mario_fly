"""tool/core/fitness.py -- thin wrapper over sim.fitness for a finished
run's summary info dict (tool/PLAN.md section 3).
"""

from __future__ import annotations

from sim.fitness import FitnessWeights, compute_fitness
from tool.core.tool_settings import FitnessSettings


def fitness_of(settings: FitnessSettings, info: dict) -> float:
    """`info` is run_steering.main()'s own returned summary dict --
    max_x_abs (distance) and n_frames (time) have always been there;
    score (points) is tool/PLAN.md's C4."""
    weights = FitnessWeights(points=settings.points, distance=settings.distance, time=settings.time,
                              powerup=settings.powerup)
    return compute_fitness(weights, distance=info["max_x_abs"], time=info["n_frames"],
                            points=info.get("score") or 0, powerups=info.get("n_powerups") or 0)
