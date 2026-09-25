"""tool/core/frame_store.py -- palette-indexed frame recording, no
subprocess. Replaces tool/tests/test_raw_frame_recorder.py (ffmpeg,
removed).
"""
from __future__ import annotations

import numpy as np

from tool.core.frame_store import FrameStore, frames_to_rgb, load_frames


def _frame(color, h=240, w=256):
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:] = color
    return frame


def test_write_then_close_round_trips_exact_pixels(tmp_path):
    store = FrameStore()
    store.write_frame(_frame((255, 0, 0)))
    store.write_frame(_frame((0, 255, 0)))
    out = store.close(tmp_path / "run_raw.npz")
    assert out is not None and out.exists()

    frames, palette = load_frames(out)
    assert frames.shape == (2, 240, 256)
    assert frames.dtype == np.uint8
    rgb = frames_to_rgb(frames, palette)
    assert np.array_equal(rgb[0], _frame((255, 0, 0)))
    assert np.array_equal(rgb[1], _frame((0, 255, 0)))


def test_palette_reuses_indices_for_repeated_colors(tmp_path):
    store = FrameStore()
    for _ in range(5):
        store.write_frame(_frame((10, 20, 30)))
    out = store.close(tmp_path / "run_raw.npz")
    _frames, palette = load_frames(out)
    assert len(palette) == 1, "one distinct colour across every frame must be one palette entry"


def test_close_with_no_frames_returns_none(tmp_path):
    store = FrameStore()
    assert store.close(tmp_path / "run_raw.npz") is None
    assert not (tmp_path / "run_raw.npz").exists()


def test_load_frames_missing_file_returns_none(tmp_path):
    assert load_frames(tmp_path / "nope.npz") is None


def test_a_real_multicolor_frame_round_trips():
    frame = np.zeros((240, 256, 3), dtype=np.uint8)
    frame[0:100] = (92, 148, 252)   # NES sky blue
    frame[100:200] = (0, 168, 0)    # ground green
    frame[200:, 100:120] = (136, 20, 0)  # Mario red patch
    store = FrameStore()
    store.write_frame(frame)
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        out = store.close(Path(d) / "run_raw.npz")
        frames, palette = load_frames(out)
        rgb = frames_to_rgb(frames, palette)
        assert np.array_equal(rgb[0], frame)
        assert len(palette) == 4, "black background + sky + ground + Mario patch"
