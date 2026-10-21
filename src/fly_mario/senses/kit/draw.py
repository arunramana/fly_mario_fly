"""One visual language for every sense, so a user can read the screen without a legend.

  red     looming (what the fly thinks is coming at it); dashed = suppressed (no headroom, or already cleared)
  green   hum (a ? block) and sweet smell (a mushroom)
  yellow  sour smell (dotted)
  white   the home dot (the pull to keep walking right)

Overlay geometry is in level pixels:  box (x, y, w, h)   line (x0, y0, x1, y1)   dot (x, y, radius)
wedge (eye_x, eye_y, x, y, w, h): the cone from Mario's eye to the box it measures.
"""
from __future__ import annotations

from fly_mario.contracts import CalcStep, OverlayItem

RED, GREEN, YELLOW, WHITE = "#e53935", "#43a047", "#fdd835", "#ffffff"


def box(x, y, w, h, colour, line="solid") -> OverlayItem:
    return OverlayItem("box", (float(x), float(y), float(w), float(h)), colour, line)


def wedge(eye, x, y, w, h, colour, line="solid") -> OverlayItem:
    return OverlayItem("wedge", (float(eye[0]), float(eye[1]), float(x), float(y), float(w), float(h)), colour, line)


def line_(x0, y0, x1, y1, colour, style="solid") -> OverlayItem:
    return OverlayItem("line", (float(x0), float(y0), float(x1), float(y1)), colour, style)


def dot(x, y, r, colour) -> OverlayItem:
    return OverlayItem("dot", (float(x), float(y), float(r)), colour, "solid")


def step(label, formula, value, norm=None, group=None) -> CalcStep:
    """One line of the worked calculation. norm is the value scaled to 0..1 for a bar; None = the value, clipped."""
    v = float(value)
    n = min(max(v, 0.0), 1.0) if norm is None else min(max(float(norm), 0.0), 1.0)
    return CalcStep(label, formula, v, n, group)
