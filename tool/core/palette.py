"""tool/core/palette.py -- Mario<->Luigi sprite colour swap, applied to a
DISPLAYED RGB frame only (tool/PLAN.md's Luigi note under section 4's
table: the RAM poke this used to mean, C6, froze movement outright and
was dropped entirely). Never touches RAM, the circuit's decisions, or the
recorded telemetry -- a pure rendering filter, applied by the live
preview (P4) and, if requested, when compositing an exported video.
"""

from __future__ import annotations

import numpy as np


def to_luigi(frame: np.ndarray) -> np.ndarray:
    """Swaps the R and G channels wherever a pixel is red-dominant (SMB1's
    Mario sprite: cap, shirt, overalls trim) -- turns that hue green,
    Luigi's own colour, without needing the exact NES palette index.
    Leaves browns/skin/sky/ground/blacks alone (none of those read as
    red-dominant under this test)."""
    r = frame[..., 0].astype(np.int16)
    g = frame[..., 1].astype(np.int16)
    b = frame[..., 2].astype(np.int16)
    red_dominant = (r > 150) & (r > g + 60) & (r > b + 40)

    out = frame.copy()
    out[..., 0] = np.where(red_dominant, frame[..., 1], frame[..., 0])
    out[..., 1] = np.where(red_dominant, frame[..., 0], frame[..., 1])
    return out


def apply(frame: np.ndarray, player: str) -> np.ndarray:
    """`player`: "mario" (identity) or "luigi" (recoloured). Anything else
    is a bug in the caller, not a silent fallback -- raises."""
    if player == "mario":
        return frame
    if player == "luigi":
        return to_luigi(frame)
    raise ValueError(f"player must be 'mario' or 'luigi', got {player!r}")
