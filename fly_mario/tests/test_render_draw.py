"""Renderer checks on synthetic data: no emulator, no connectome."""
import cv2
import numpy as np

from fly_mario.contracts import OverlayItem
from fly_mario.render import H, W, BrainData, FrameData, Renderer
from fly_mario.render.draw import GAME_H, GAME_W, GAME_X, GAME_Y, LEFT_W, game_panel


def _game(seed=0):
    return np.random.default_rng(seed).integers(0, 256, (240, 256, 3), dtype=np.uint8)


def _brain():
    rng = np.random.default_rng(1)
    brain = np.c_[rng.uniform(20000, 100000, 400), rng.uniform(0, 1, 400), rng.uniform(0, 50000, 400)]
    cord = np.c_[rng.uniform(40000, 60000, 100), rng.uniform(0, 1, 100), rng.uniform(53000, 80000, 100)]
    allx = np.vstack([brain, cord]).astype(np.float32)
    return BrainData(
        all_xyz=allx, xyz={"LC4_R": brain[:20], "DNp01": brain[20:22], "TTMn": cord[:2]},
        colours={"LC4_R": (57, 135, 229), "DNp01": (217, 89, 38), "TTMn": (230, 103, 103)},
        other_xyz=brain[30:40], index=[("LC4", "looming", ["LC4_R"]), ("DNp01", "Giant Fiber", ["DNp01"]),
                                      ("TTMn", "jump muscle", ["TTMn"])],
        rate_max={"LC4_R": 1.0, "DNp01": 0.5, "TTMn": 0.5}, counts={"LC4_R": 20, "DNp01": 2, "TTMn": 2},
        n_neurons=len(allx))


OVERLAY = [OverlayItem("box", (100.0, 100.0, 16.0, 16.0), "#e53935"),
           OverlayItem("wedge", (80.0, 120.0, 100.0, 100.0, 16.0, 16.0), "#e53935", "dashed"),
           OverlayItem("line", (90.0, 90.0, 140.0, 90.0), "#43a047", "dotted"),
           OverlayItem("dot", (120.0, 130.0, 2.0), "#ffffff")]


def _fd(overlay=OVERLAY, rates=None):
    return FrameData(game=_game(), overlay=list(overlay), rates=rates or {"LC4_R": 0.8, "DNp01": 0.1, "TTMn": 0.0},
                     scroll_x=10.0, frame=5)


def test_full_frame_size():
    img = Renderer(_brain()).frame(_fd())
    assert img.shape == (H, W, 3) and img.dtype == np.uint8 and (W, H) == (1920, 1080)


def test_game_panel_size_is_nes_x4():
    assert game_panel(_game(), OVERLAY, 0.0).shape == (240 * 4, 256 * 4, 3) == (GAME_H, GAME_W, 3)


def test_no_senses_leaves_game_pixels_untouched():
    fd = _fd()
    plain = cv2.resize(fd.game, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
    off = Renderer(_brain(), show_senses=False).frame(fd)
    assert np.array_equal(off[GAME_Y:GAME_Y + GAME_H, GAME_X:GAME_X + GAME_W], plain)
    on = Renderer(_brain(), show_senses=True).frame(fd)
    assert not np.array_equal(on[GAME_Y:GAME_Y + GAME_H, GAME_X:GAME_X + GAME_W], plain)


def test_senses_toggle_does_not_touch_the_brain_panel():
    fd = _fd()
    a, b = Renderer(_brain(), show_senses=True).frame(fd), Renderer(_brain(), show_senses=False).frame(fd)
    assert np.array_equal(a[:, :LEFT_W], b[:, :LEFT_W])


def test_no_brain_centres_the_game_and_leaves_the_sides_black():
    fd = _fd()
    img = Renderer(_brain(), show_brain=False).frame(fd)
    gx = (W - GAME_W) // 2
    assert img.shape == (H, W, 3)
    assert np.array_equal(img[GAME_Y:GAME_Y + GAME_H, gx:gx + GAME_W], game_panel(fd.game, fd.overlay, fd.scroll_x))
    assert (img[:, :gx] == img[0, 0]).all() and (img[:, gx + GAME_W:] == img[0, 0]).all()


def test_no_brain_without_brain_data():
    assert Renderer(None).frame(_fd()).shape == (H, W, 3)


def test_brain_glows_with_activity():
    quiet = Renderer(_brain()).frame(_fd(rates={"LC4_R": 0.0, "DNp01": 0.0, "TTMn": 0.0}))[:, :LEFT_W].astype(int)
    lit = Renderer(_brain()).frame(_fd(rates={"LC4_R": 1.0, "DNp01": 0.5, "TTMn": 0.5}))[:, :LEFT_W].astype(int)
    assert lit.sum() > quiet.sum()


def test_overlay_moves_with_scroll():
    a = game_panel(_game(), OVERLAY, 0.0)
    b = game_panel(_game(), OVERLAY, 32.0)
    assert not np.array_equal(a, b)
