"""The lite brain panel and the frame it is drawn in, from a synthetic panel file (no data, no emulator)."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from fly_mario_fly.lite import drawing
from fly_mario_fly.lite.panel import FLOOR, PANEL_W, Panel


def synthetic(tmp_path):
    h, w = 200, PANEL_W
    pts = np.array([[20, 20], [21, 20], [100, 60], [101, 60]], np.int16)
    rows = [["AA", "role a", ["ga"]], ["BB", "role b", ["gb"]]]
    f = tmp_path / "p.npz"
    np.savez_compressed(f, bg=np.full((h, w, 3), 10, np.uint8), pts=pts, grp=np.array([0, 0, 1, 1], np.int16),
                        groups=np.array(["ga", "gb"]), colours=np.array([[255, 0, 0], [0, 255, 0]], np.uint8), counts=np.array([2, 2]),
                        big=np.array([False, False]), other=np.zeros((0, 2), np.int16), other_col=np.array([110, 118, 130], np.uint8),
                        rows=np.array(json.dumps(rows)), n_neurons=np.array(907))
    return f


def test_the_panel_has_the_height_asked_and_its_own_width(tmp_path):
    img = Panel.load(synthetic(tmp_path)).draw({}, 480)
    assert img.shape == (480, PANEL_W, 3) and img.dtype == np.uint8


def test_an_active_group_glows_in_its_colour_and_a_silent_one_is_dim(tmp_path):
    p = Panel.load(synthetic(tmp_path))
    quiet = p.draw({"ga": 0.0, "gb": 0.0}, 300)
    loud = p.draw({"ga": 0.5, "gb": 0.0}, 300)
    assert loud[20, 20, 0] > quiet[20, 20, 0] + 100            # group a, red, at its soma
    assert loud[60, 100, 1] == quiet[60, 100, 1]               # group b stays as it was


def test_brightness_is_against_the_largest_rate_so_far(tmp_path):
    p = Panel.load(synthetic(tmp_path))
    assert p.levels({"ga": 0.4})[0] == 1.0                     # the largest so far is itself
    assert p.levels({"ga": 0.2})[0] == pytest.approx(0.5)      # half of it
    assert p.levels({"ga": 0.0})[0] == 0.0
    assert p.top[1] == pytest.approx(FLOOR)                                   # a group that never fires keeps the floor, so noise does not light it


def test_the_index_bar_follows_the_groups_level(tmp_path):
    p = Panel.load(synthetic(tmp_path))
    p.levels({"ga": 1.0})
    full = p.draw({"ga": 1.0}, 300)
    empty = p.draw({"ga": 0.0}, 300)
    assert (full != empty).any()
    assert full.shape == empty.shape


def test_a_frame_is_the_panel_the_game_and_the_strip(tmp_path):
    p = Panel.load(synthetic(tmp_path))
    rec = SimpleNamespace(screen=np.zeros((240, 256, 3), np.uint8), outputs={}, scroll_x_after=0, rates={"ga": 0.3}, buttons=frozenset({"right"}))
    with_panel = drawing.draw(rec, 2, p)
    assert with_panel.shape[1::-1] == drawing.frame_size(2, True) == (PANEL_W + 512, 480 + drawing.STRIP)
    alone = drawing.draw(rec, 2, None)
    assert alone.shape[1::-1] == drawing.frame_size(2, False) == (512, 480 + drawing.STRIP)
    assert with_panel.shape[1] % 2 == 0 and with_panel.shape[0] % 2 == 0     # yuv420p needs even sides
