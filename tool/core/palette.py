"""tool/core/palette.py -- Mario<->Luigi sprite colour swap, applied to a
DISPLAYED RGB frame only (tool/PLAN.md's Luigi note under section 4's
table: the RAM poke this used to mean, C6, froze movement outright and
was dropped entirely). Never touches RAM, the circuit's decisions, or the
recorded telemetry -- a pure rendering filter, applied by the live
preview (P4) and, if requested, when compositing an exported video.

Found in manual testing: the original `to_luigi` swapped red-dominant
pixels across the WHOLE frame, recolouring bricks, `?`-blocks, and other
red-ish scenery, not just Mario. Restricted below to a window around
Mario's own position.

`ADDR_MARIO_Y` (checked directly, not assumed) is unusable for this: it
reads a constant `1` for every frame of a full 689-frame run, including
9 escape jumps -- it does not track vertical screen position in this
build, for whatever it actually is. `mario_x` (`row["mario_x"]`, already
in the telemetry row `on_frame` receives) DOES vary correctly and is used
here; the vertical window is a fixed, empirically observed band (ground
level through a generous jump apex -- checked against the same 689-frame
run, near-Mario red pixels stayed within roughly rows 190-239 in the
common case) rather than a second RAM value. This narrows the swap to
Mario's own screen position; it is not a claim of pixel-exact isolation
(a rare on-screen red element at the same x AND in this y band would
still be swapped) -- see this module's own test for what it does and
doesn't guarantee.
"""

from __future__ import annotations

import numpy as np

from config.params import EntityParams
from tool.core.display_params import PaletteDisplayParams

# All four in the NES's own 256x240 coordinate space (matching mario_x,
# a raw RAM value) -- scaled to whatever `frame`'s actual resolution is
# in to_luigi() below, since the live preview queues a 2x-shrunk frame
# (tool/core/runner.py's run_one_streaming) but mario_x is never shrunk.
NES_WIDTH_PX, NES_HEIGHT_PX = 256, 240
MARIO_WIDTH_PX = EntityParams().entity_width_px  # same 16px every enemy-slot entity assumes
MARIO_X_MARGIN_PX = PaletteDisplayParams().mario_x_margin_px
MARIO_Y_MIN = PaletteDisplayParams().mario_y_min_px
MARIO_Y_MAX = NES_HEIGHT_PX  # the bottom of the screen -- a hardware fact, not a hand-set choice


def to_luigi(frame: np.ndarray, mario_x: int | None = None) -> np.ndarray:
    """Swaps the R and G channels wherever a pixel is red-dominant (SMB1's
    Mario sprite: cap, shirt, overalls trim) -- turns that hue green,
    Luigi's own colour, without needing the exact NES palette index.
    Leaves browns/skin/sky/ground/blacks alone (none of those read as
    red-dominant under this test).

    `mario_x=None` (no position known) swaps the whole frame -- the
    original, unrestricted behaviour, kept for callers that genuinely
    don't have a position (e.g. a bare frame with no telemetry row).
    Any real caller with a `row["mario_x"]` should pass it."""
    r = frame[..., 0].astype(np.int16)
    g = frame[..., 1].astype(np.int16)
    b = frame[..., 2].astype(np.int16)
    red_dominant = (r > 150) & (r > g + 60) & (r > b + 40)

    if mario_x is not None:
        h, w = frame.shape[:2]
        x_scale, y_scale = w / NES_WIDTH_PX, h / NES_HEIGHT_PX
        mask = np.zeros(red_dominant.shape, dtype=bool)
        lo = max(0, round((mario_x - MARIO_X_MARGIN_PX) * x_scale))
        hi = min(w, round((mario_x + MARIO_WIDTH_PX + MARIO_X_MARGIN_PX) * x_scale))
        y_lo = max(0, round(MARIO_Y_MIN * y_scale))
        y_hi = min(h, round(MARIO_Y_MAX * y_scale))
        mask[y_lo:y_hi, lo:hi] = True
        red_dominant = red_dominant & mask

    out = frame.copy()
    out[..., 0] = np.where(red_dominant, frame[..., 1], frame[..., 0])
    out[..., 1] = np.where(red_dominant, frame[..., 0], frame[..., 1])
    return out


def apply(frame: np.ndarray, player: str, mario_x: int | None = None) -> np.ndarray:
    """`player`: "mario" (identity) or "luigi" (recoloured, restricted to
    Mario's own on-screen position when `mario_x` is given). Anything
    else is a bug in the caller, not a silent fallback -- raises."""
    if player == "mario":
        return frame
    if player == "luigi":
        return to_luigi(frame, mario_x=mario_x)
    raise ValueError(f"player must be 'mario' or 'luigi', got {player!r}")
