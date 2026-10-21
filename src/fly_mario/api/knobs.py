"""Knob values <-> slider positions. The API never shows a raw knob value, only where it sits between lo and hi.

A "log" knob is positioned on a log axis (a width scale of 0.25..4 has its default in the middle).
"""
from __future__ import annotations

import math

from fly_mario import registry


def to_position(spec, value: float) -> float:
    """Raw value -> 0..1 along the knob's own axis (clipped)."""
    lo, hi = float(spec.lo), float(spec.hi)
    if hi == lo:
        return 0.0
    if spec.scale == "log" and lo > 0 and value > 0:
        p = math.log(value / lo) / math.log(hi / lo)
    else:
        p = (value - lo) / (hi - lo)
    return min(1.0, max(0.0, p))


def from_position(spec, position: float) -> float:
    """0..1 -> raw value inside [lo, hi]."""
    lo, hi = float(spec.lo), float(spec.hi)
    p = min(1.0, max(0.0, float(position)))
    v = lo * (hi / lo) ** p if spec.scale == "log" and lo > 0 else lo + p * (hi - lo)
    return min(hi, max(lo, v))


def specs_by_key() -> dict:
    """Every knob any installed sense, action or loom shape declares, by key."""
    out: dict = {}
    for kind in ("senses", "actions", "shapes"):
        for plugin in registry.list_plugins(kind).values():
            for k in getattr(plugin, "knobs", ()):
                out[k.key] = k
    return out
