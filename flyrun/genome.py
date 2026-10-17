"""Genomes for the evolved knobs. CMA-ES searches the unit cube; decode() maps to ranges.
Only the knobs listed here are searched; everything else in Knobs stays fixed."""
from dataclasses import replace

import numpy as np

from .knobs import Knobs

# (knob, lo, hi, is_int)
FLY = [("G", 0.2, 1.5, False), ("TTMN_THRESH", 0.02, 0.4, False), ("A_HOLD", 4, 32, True),
       ("COOLDOWN", 0, 30, True), ("HOME_R", 0.1, 2.0, False), ("PIT_GAIN", 0.0, 5.0, False)]
THETA = [("THETA_RULE_DEG", 20.0, 70.0, False), ("A_HOLD", 4, 32, True), ("COOLDOWN", 0, 30, True)]
SPAM = [("A_HOLD", 4, 32, True), ("COOLDOWN", 0, 30, True)]
SPECS = {"fly": FLY, "theta": THETA, "spam": SPAM}
CONTROLLER = {"fly": None, "theta": "theta_rule", "spam": "spam"}   # fitness.CONTROLLERS key; None = the circuit
# Evolution runs deterministic episodes: no sensor noise (noise is for the robustness check only).
BASE = replace(Knobs(), SENSOR_NOISE=0.0)


def decode(arm, u):
    u = np.clip(np.asarray(u, dtype=float), 0.0, 1.0)
    vals = {}
    for (name, lo, hi, is_int), x in zip(SPECS[arm], u):
        v = lo + x * (hi - lo)
        vals[name] = int(round(v)) if is_int else float(v)
    return replace(BASE, **vals), vals


def encode(arm, knobs):
    return np.array([(getattr(knobs, n) - lo) / (hi - lo) for n, lo, hi, _ in SPECS[arm]])


def x0(arm):
    """Start point: the current defaults (fly) / 43.6 deg, hold 12, cooldown 10 (theta rule)."""
    return encode(arm, BASE)
