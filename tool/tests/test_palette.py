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
