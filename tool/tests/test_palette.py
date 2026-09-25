"""tool/core/palette.py: the Luigi colour swap never touches RAM/circuit/
telemetry -- this only tests the pixel filter itself.
"""
from __future__ import annotations

import numpy as np
import pytest

from tool.core.palette import apply, to_luigi


def test_mario_is_identity():
    frame = np.random.randint(0, 255, (10, 10, 3), dtype=np.uint8)
    assert np.array_equal(apply(frame, "mario"), frame)


def test_luigi_recolors_red_pixels_only():
    frame = np.zeros((2, 3, 3), dtype=np.uint8)
    frame[0, 0] = [200, 20, 20]    # red-dominant -> should change
    frame[0, 1] = [139, 69, 19]    # brown (skin/overalls) -> should NOT change
    frame[0, 2] = [0, 0, 0]        # black outline -> should NOT change
    frame[1, 0] = [255, 255, 255]  # white -> should NOT change
    frame[1, 1] = [92, 148, 252]   # NES sky blue -> should NOT change
    frame[1, 2] = [0, 168, 0]      # green ground -> should NOT change

    recolored = to_luigi(frame)
    assert not np.array_equal(recolored[0, 0], frame[0, 0]), "red pixel should have changed"
    assert recolored[0, 0, 1] == frame[0, 0, 0], "red channel should have moved to green"
    for coord in [(0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]:
        assert np.array_equal(recolored[coord], frame[coord]), f"{coord} should be unchanged"


def test_apply_rejects_unknown_player():
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply(frame, "peach")


def test_luigi_with_mario_x_restricts_to_a_window_near_mario():
    """Found in manual testing: without mario_x, to_luigi recolours red
    pixels ANYWHERE in the frame -- bricks, `?`-blocks, other scenery.
    Given mario_x, only a window around Mario's own position changes."""
    frame = np.zeros((240, 256, 3), dtype=np.uint8)
    frame[200, 5] = [200, 20, 20]    # far from mario_x=100 -- a "brick" elsewhere
    frame[200, 105] = [200, 20, 20]  # at mario's own position, ground level

    recolored = to_luigi(frame, mario_x=100)
    assert np.array_equal(recolored[200, 5], frame[200, 5]), \
        "a red pixel far from mario_x must be left alone"
    assert not np.array_equal(recolored[200, 105], frame[200, 105]), \
        "a red pixel at mario's own position must still be swapped"


def test_luigi_with_mario_x_and_y_ignores_red_pixels_outside_the_real_box():
    """Now that ADDR_MARIO_Y tracks Mario's real vertical position
    (codebase: fix ADDR_MARIO_Y to 0x03B8), the box follows him -- a red
    pixel at mario_x's column but far above his real y (HUD text, a red
    cloud) must not be swapped even when it WOULD have fallen inside the
    old fixed ground-level band."""
    frame = np.zeros((240, 256, 3), dtype=np.uint8)
    frame[10, 100] = [200, 20, 20]
    recolored = to_luigi(frame, mario_x=100, mario_y=176)  # mario_y=176 -> ground level, row ~195
    assert np.array_equal(recolored[10, 100], frame[10, 100])


def test_luigi_box_follows_mario_y_through_a_jump():
    """The whole point of using ram[0x03B8]: the box moves. A red pixel at
    the row a ground-level mario_y would cover must stop being swapped
    once mario_y says Mario has jumped well clear of it, and a red pixel
    at the JUMPED-TO row must start being swapped."""
    ground_row, ground_frame = 210, np.zeros((240, 256, 3), dtype=np.uint8)
    ground_frame[ground_row, 100] = [200, 20, 20]
    apex_row, apex_frame = 145, np.zeros((240, 256, 3), dtype=np.uint8)
    apex_frame[apex_row, 100] = [200, 20, 20]

    # Ground level (mario_y=176, matching this module's own probe).
    assert not np.array_equal(to_luigi(ground_frame, mario_x=100, mario_y=176)[ground_row, 100],
                               ground_frame[ground_row, 100]), "swapped at Mario's own ground-level row"
    assert np.array_equal(to_luigi(apex_frame, mario_x=100, mario_y=176)[apex_row, 100],
                           apex_frame[apex_row, 100]), "left alone far above Mario while he's on the ground"

    # Jump apex (mario_y=112, matching this module's own probe).
    assert not np.array_equal(to_luigi(apex_frame, mario_x=100, mario_y=112)[apex_row, 100],
                               apex_frame[apex_row, 100]), "swapped at Mario's own apex row"
    assert np.array_equal(to_luigi(ground_frame, mario_x=100, mario_y=112)[ground_row, 100],
                           ground_frame[ground_row, 100]), "left alone at ground level while he's at the apex"


def test_luigi_with_mario_x_but_no_mario_y_falls_back_to_a_ground_box():
    """A caller with a position but no y (shouldn't happen after this
    session's row["mario_y"] wiring, but must not crash) still restricts
    to SOME box rather than silently reverting to a whole-frame swap."""
    frame = np.zeros((240, 256, 3), dtype=np.uint8)
    frame[10, 100] = [200, 20, 20]
    recolored = to_luigi(frame, mario_x=100)
    assert np.array_equal(recolored[10, 100], frame[10, 100])


def test_luigi_window_scales_with_a_shrunk_frame():
    """The live preview queues a 2x-shrunk frame (tool/core/runner.py's
    run_one_streaming) -- mario_x is always the full-resolution RAM
    value, so the window must scale down with the frame, not stay in
    full-resolution pixel units (which would land on the wrong pixels
    entirely for a shrunk frame)."""
    small_frame = np.zeros((120, 128, 3), dtype=np.uint8)
    small_frame[100, 52] = [200, 20, 20]  # inside the scaled-down window for mario_x=100
    recolored = to_luigi(small_frame, mario_x=100)
    assert not np.array_equal(recolored[100, 52], small_frame[100, 52])


def test_luigi_recolor_on_a_real_emulator_frame_changes_some_pixels():
    import setuptools  # noqa: F401
    from mario.emulator.env import make_env

    env = make_env("1-1")
    obs = env.reset()
    env.close()

    recolored = to_luigi(obs)
    changed = (recolored != obs).any(axis=-1)
    assert changed.any(), "expected at least some red-dominant pixels (Mario's sprite) on the title frame"
    assert changed.sum() < obs.size // 3, "recoloring more than a third of the frame looks like a bug, not a sprite swap"
