# What this file does, in plain English:
# Checks the after-the-fact game score in sim/fitness.py: by default only
# distance counts, a zero or negative distance weight is refused, a game
# that went farther and died outscores one that stayed alive but got stuck
# (numbers from an earlier run), and the score is a plain weighted sum.
"""
Fitness is computed and recorded, never wired into a decision, so these
tests check the object itself.
"""
from __future__ import annotations

import pytest

from sim.fitness import FitnessWeights, compute_fitness


def test_default_weights_are_distance_only():
    w = FitnessWeights()
    assert w.distance == 1.0 and w.points == 0.0 and w.time == 0.0


def test_zero_distance_is_rejected():
    """025's finding, made structural: survival/points-only cannot be
    configured by accident."""
    with pytest.raises(ValueError, match="distance must be > 0"):
        FitnessWeights(distance=0.0)


def test_negative_distance_is_also_rejected():
    with pytest.raises(ValueError, match="distance must be > 0"):
        FitnessWeights(distance=-1.0)


def test_compute_fitness_matches_the_actual_025_degenerate_case():
    """025's own numbers: an episode that 'survived' 800 frames
    oscillating at x=658 versus a baseline that reached x=1432 and died.
    Distance-weighted fitness must NOT rank the stuck episode higher."""
    w = FitnessWeights()  # distance=1.0, points=0.0, time=0.0
    stuck = compute_fitness(w, distance=658, time=800)
    baseline = compute_fitness(w, distance=1432, time=689)
    assert baseline > stuck


def test_compute_fitness_is_a_pure_weighted_sum():
    w = FitnessWeights(points=2.0, distance=1.0, time=0.5)
    assert compute_fitness(w, distance=100, time=50, points=10) == 2.0 * 10 + 1.0 * 100 + 0.5 * 50
