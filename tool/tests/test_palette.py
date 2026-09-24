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


def test_luigi_with_mario_x_ignores_red_pixels_above_the_ground_band():
    """ADDR_MARIO_Y is unusable (constant across a full run, see this
    module's own docstring) -- the vertical restriction is a fixed band,
    not a real position, so it must not swap something red at mario_x's
    column but far above where mario could ever actually be (HUD text)."""
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
