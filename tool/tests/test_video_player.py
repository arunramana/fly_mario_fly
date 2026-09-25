"""tool/ui/widgets/video_player.py -- ease-of-use redesign, Run tab video
player: live mode (during a Play) vs seekable mode (a finished run's
raw-frame recording). Exercises the mechanism directly with a synthetic
telemetry DataFrame, not through a full simulation run.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from tool.core.raw_frame_recorder import RawFrameRecorder
from tool.ui.widgets.video_player import VideoPlayer, _event_markers


def _fake_telemetry(n=30) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    spike = np.zeros(n, dtype=bool)
    spike[[5, 20]] = True
    climb = np.zeros(n, dtype=bool)
    climb[10] = True
    return pd.DataFrame({
        "lc4": rng.random(n), "lplc2": rng.random(n), "mem": rng.random(n) * 0.5,
        "spike": spike, "ttmn": rng.random(n) * 10, "dna01": rng.random(n) * 10,
        "dna02": rng.random(n) * 10, "direction": ["R"] * n, "climb": climb,
        "conflict": [False] * n, "odor_l": rng.random(n), "odor_r": rng.random(n),
        "hungry": [True] * n, "dnp09": rng.random(n), "dlmn": rng.random(n),
        "frame": np.arange(n),
    })


def _real_recording(tmp_path, n_frames=30):
    obs = np.random.default_rng(0).integers(0, 255, (240, 256, 3), dtype=np.uint8)
    out_path = tmp_path / "test_raw.mp4"
    recorder = RawFrameRecorder(out_path)
    for _ in range(n_frames):
        recorder.write_frame(obs)
    recorder.close()
    # close() no longer waits for ffmpeg (tool/core/raw_frame_recorder.py's
    # own docstring) -- wait for the file size to settle (unchanged across
    # two checks), not just ">0", since a still-growing/still-flushing
    # file can otherwise look "ready" mid-write.
    deadline = time.time() + 15
    last_size = -1
    stable_checks = 0
    while time.time() < deadline:
        size = out_path.stat().st_size if out_path.exists() else 0
        if size > 0 and size == last_size:
            stable_checks += 1
            if stable_checks >= 3:
                break
        else:
            stable_checks = 0
        last_size = size
        time.sleep(0.2)
    return out_path


def test_starts_in_empty_mode(qapp):
    player = VideoPlayer()
    assert player._mode == "empty"
    assert not player.play_button.isEnabled()


def test_show_frame_enters_live_mode(qapp):
    player = VideoPlayer()
    obs = np.zeros((240, 256, 3), dtype=np.uint8)
    player.show_frame(obs, {"frame": 3, "mario_x": 10})
    assert player._mode == "live"
    assert not player.frame_label.pixmap().isNull()
    assert not player.play_button.isEnabled(), "no seeking mid-run -- nothing recorded to scrub yet"


def test_load_run_with_no_recording_shows_no_recording_state(qapp):
    player = VideoPlayer()
    tel = _fake_telemetry()
    player.load_run(None, tel, {"died_or_flagged": False})
    assert player._mode == "empty"
    assert not player.play_button.isEnabled()


def test_load_run_after_live_preserves_the_last_live_frame(qapp):
    """Found live: loading "no recording" after a run that WAS shown live
    used to wipe the last frame the user was just watching."""
    player = VideoPlayer()
    obs = np.full((240, 256, 3), 200, dtype=np.uint8)
    player.show_frame(obs, {"frame": 3, "mario_x": 10})
    assert not player.frame_label.pixmap().isNull()

    player.load_run(None, _fake_telemetry(), {"died_or_flagged": False})
    assert not player.frame_label.pixmap().isNull(), "the last live frame must survive a load_run(None, ...)"


def test_load_run_with_a_real_recording_enables_transport(qapp, tmp_path):
    raw_path = _real_recording(tmp_path)
    player = VideoPlayer()
    player.load_run(raw_path, _fake_telemetry(), {"died_or_flagged": False})
    assert player._mode == "seekable"
    assert player.play_button.isEnabled()
    assert player.timeline._n_frames == 30


def test_seek_frame_updates_timeline_and_emits_frame_changed(qapp, tmp_path):
    raw_path = _real_recording(tmp_path)
    player = VideoPlayer()
    player.load_run(raw_path, _fake_telemetry(), {"died_or_flagged": False})

    seen = []
    player.frame_changed.connect(seen.append)
    player.seek_frame(10)
    assert player.timeline._position == 10
    assert 10 in seen


def test_step_frame_and_jump_seconds(qapp, tmp_path):
    raw_path = _real_recording(tmp_path)
    player = VideoPlayer()
    player.load_run(raw_path, _fake_telemetry(), {"died_or_flagged": False})
    player.seek_frame(10)
    player.step_frame(1)
    assert player._current_frame_index == 11
    player.step_frame(-1)
    assert player._current_frame_index == 10


def test_event_markers_from_telemetry_and_summary():
    tel = _fake_telemetry()
    markers = _event_markers(tel, {"died_or_flagged": True})
    assert markers["jump"] == [5, 20]
    assert markers["climb"] == [10]
    assert markers["death_or_flag"] == [len(tel) - 1]
    assert "stomp" not in markers, "no per-frame stomp column exists yet -- must not fabricate ticks"


def test_event_markers_no_death_marker_when_survived():
    tel = _fake_telemetry()
    markers = _event_markers(tel, {"died_or_flagged": False})
    assert "death_or_flag" not in markers
