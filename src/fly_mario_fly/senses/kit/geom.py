"""Geometry shared by the senses. Every number is in level pixels; y grows downward."""
from __future__ import annotations

import numpy as np

from fly_mario_fly.contracts import MarioState


def theta_of(d: float, h: float) -> float:
    """Visual angle (rad) of an object of height h at distance d, seen from Mario's eye: 2*atan(h / 2d).
    d is floored at 1 px, so an object that touches Mario saturates at a finite angle."""
    return float(2.0 * np.arctan(h / (2.0 * max(float(d), 1.0))))


def feet_of(mario: MarioState) -> float:
    """Mario's feet y (his box is stored by its top)."""
    return mario.y + mario.h


def gap(mario: MarioState, x: float, top: float, w: float, h: float, rear: bool = False) -> float:
    """2-D surface-to-surface gap between Mario's box and a box (0 on an axis where they overlap).
    rear=True: the box is behind him, so the x gap is measured from his left edge."""
    feet = feet_of(mario)
    gx = max(0.0, mario.x - (x + w)) if rear else max(0.0, x - (mario.x + mario.w))
    gy = max(0.0, top - feet, (feet - mario.h) - (top + h))      # entirely below his feet / entirely above his head
    return float(np.hypot(gx, gy))


def over(mario: MarioState, x0: float, x1: float) -> bool:
    """His body horizontally overlaps the columns [x0, x1)."""
    return mario.x < x1 and mario.x + mario.w > x0


def is_cleared(mario: MarioState, top: float, x0: float, x1: float) -> bool:
    """He has got past a box: his feet are at or above its top AND his body is over it."""
    return feet_of(mario) <= top and over(mario, x0, x1)


def is_behind(mario: MarioState, x: float, w: float) -> bool:
    """The box is fully behind his left edge."""
    return x + w <= mario.x


def eye_of(mario: MarioState, dy: float = 0.0) -> tuple:
    """The eye point: his top-front corner, lowered by dy px (0 = the corner)."""
    return mario.x + mario.w, feet_of(mario) - mario.h + dy


def identity(obj) -> tuple:
    """What stays the same about an object from frame to frame. Enemies live in numbered slots and a slot is
    the identity the game itself keeps, so use it when the finder reports one; else (type, id)."""
    slot = obj.state.get("slot")
    return ("slot", slot) if slot is not None else (obj.type, obj.id)
