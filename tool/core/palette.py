"""tool/core/palette.py -- Mario<->Luigi sprite colour swap, applied to a
DISPLAYED RGB frame only (tool/PLAN.md's Luigi note under section 4's
table: the RAM poke this used to mean, C6, froze movement outright and
was dropped entirely). Never touches RAM, the circuit's decisions, or the
recorded telemetry -- a pure rendering filter, applied by the live
preview (P4) and, if requested, when compositing an exported video.

Found in manual testing: the original `to_luigi` swapped red-dominant
pixels across the WHOLE frame, recolouring bricks, `?`-blocks, and other
red-ish scenery, not just Mario. Restricted below to a window around
Mario's own position -- `mario_x` for the column band, `ram[0x03B8]` (now
that ADDR_MARIO_Y is fixed to that address, not the old 0x00B5 viewport
flag that stayed constant at 1 -- codebase: fix ADDR_MARIO_Y to 0x03B8)
for the row band, so the box follows Mario through a jump instead of
sitting still in a generous fixed band.

Checked directly, not assumed: a probe script (held right+A through a
full jump arc on a real 1-1 env, compared `ram[0x03B8]` each frame
against the topmost red-dominant screen row within Mario's own x-column)
found `screen_row ~= ram[0x03B8] + offset`, offset ranging 17-22px across
the jump's animation frames -- NOT `255 - ram[0x03B8]` (`info["y_pos"]`'s
own formula, tests/test_addr_mario_y.py): that quantity is a height-
above-ground metric for game logic, not a screen row, and moves the
OPPOSITE direction from ram[0x03B8] does on screen. See
tool/core/display_params.py's own provenance strings for the exact
measured numbers. This is still not a claim of pixel-exact isolation (a
rare on-screen red element inside the box would still be swapped, and the
box is generous by design, per mario_height_px's own margin) -- see this
module's own test for what it does and doesn't guarantee.
"""

from __future__ import annotations

import numpy as np

from config.params import EntityParams
from tool.core.display_params import PaletteDisplayParams

# All in the NES's own 256x240 coordinate space (matching mario_x/mario_y,
# raw RAM values) -- scaled to whatever `frame`'s actual resolution is in
# to_luigi() below, since the live preview queues a 2x-shrunk frame
# (tool/core/runner.py's run_one_streaming) but mario_x/mario_y are never
# shrunk.
NES_WIDTH_PX, NES_HEIGHT_PX = 256, 240
MARIO_WIDTH_PX = EntityParams().entity_width_px  # same 16px every enemy-slot entity assumes
MARIO_X_MARGIN_PX = PaletteDisplayParams().mario_x_margin_px
MARIO_Y_OFFSET_PX = PaletteDisplayParams().mario_y_offset_px
MARIO_HEIGHT_PX = PaletteDisplayParams().mario_height_px


def to_luigi(frame: np.ndarray, mario_x: int | None = None, mario_y: int | None = None) -> np.ndarray:
    """Swaps the R and G channels wherever a pixel is red-dominant (SMB1's
    Mario sprite: cap, shirt, overalls trim) -- turns that hue green,
    Luigi's own colour, without needing the exact NES palette index.
    Leaves browns/skin/sky/ground/blacks alone (none of those read as
    red-dominant under this test).

    `mario_x=None` (no position known) swaps the whole frame -- the
    original, unrestricted behaviour, kept for callers that genuinely
    don't have a position (e.g. a bare frame with no telemetry row). Any
    real caller with a `row["mario_x"]`/`row["mario_y"]` should pass both;
    `mario_x` given without `mario_y` falls back to a box anchored at the
    bottom of the screen (the old fixed band's own worst case), rather
    than silently ignoring the restriction."""
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
        row_top = (mario_y + MARIO_Y_OFFSET_PX) if mario_y is not None else (NES_HEIGHT_PX - MARIO_HEIGHT_PX)
        y_lo = max(0, round(row_top * y_scale))
        y_hi = min(h, round((row_top + MARIO_HEIGHT_PX) * y_scale))
        mask[y_lo:y_hi, lo:hi] = True
        red_dominant = red_dominant & mask

    out = frame.copy()
    out[..., 0] = np.where(red_dominant, frame[..., 1], frame[..., 0])
    out[..., 1] = np.where(red_dominant, frame[..., 0], frame[..., 1])
    return out


def apply(frame: np.ndarray, player: str, mario_x: int | None = None, mario_y: int | None = None) -> np.ndarray:
    """`player`: "mario" (identity) or "luigi" (recoloured, restricted to
    Mario's own real on-screen box when `mario_x`/`mario_y` are given).
    Anything else is a bug in the caller, not a silent fallback --
    raises."""
    if player == "mario":
        return frame
    if player == "luigi":
        return to_luigi(frame, mario_x=mario_x, mario_y=mario_y)
    raise ValueError(f"player must be 'mario' or 'luigi', got {player!r}")
