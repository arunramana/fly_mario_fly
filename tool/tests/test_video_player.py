"""tool/ui/widgets/video_player.py -- ease-of-use redesign, Run tab video
player: live mode (during a Play) vs seekable mode (a finished run's
frame recording). Exercises the mechanism directly with a synthetic
telemetry DataFrame, not through a full simulation run.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tool.core.frame_store import FrameStore
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
    out_path = tmp_path / "test_raw.npz"
    store = FrameStore()
    for _ in range(n_frames):
        store.write_frame(obs)
    return store.close(out_path)


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


def test_recording_longer_than_telemetry_still_plays_with_frozen_tel_rows(qapp, tmp_path):
    """death_animation_frames: the recording can outlast the telemetry
    (tel has 30 rows, the recording has 40 frames -- 10 display-only death
    -animation frames). Seeking past row 29 must still show a real
    recorded frame and must not crash reading telemetry -- it freezes on
    the last real row instead."""
    raw_path = _real_recording(tmp_path, n_frames=40)
    player = VideoPlayer()
    player.load_run(raw_path, _fake_telemetry(n=30), {"died_or_flagged": True})
    assert player._n_frames == 40, "the recording's own length wins, not len(tel)"

    player.seek_frame(35)
    assert player._current_frame_index == 35
    assert not player.frame_label.pixmap().isNull()
    row = player.current_row()
    assert row is not None and row["frame"] == 29, "frozen on the last real telemetry row"


def test_playback_timer_advances_frames_at_1x(qapp, tmp_path):
    raw_path = _real_recording(tmp_path, n_frames=30)
    player = VideoPlayer()
    player.load_run(raw_path, _fake_telemetry(), {"died_or_flagged": False})
    player.toggle_playback()
    assert player._playing
    for _ in range(5):
        player._on_tick()
    assert player._current_frame_index == 5, "1x speed should advance exactly one frame per tick"
    player.toggle_playback()
    assert not player._playing


def test_playback_stops_at_the_last_frame(qapp, tmp_path):
    raw_path = _real_recording(tmp_path, n_frames=5)
    player = VideoPlayer()
    player.load_run(raw_path, _fake_telemetry(), {"died_or_flagged": False})
    player.toggle_playback()
    for _ in range(10):
        player._on_tick()
    assert player._current_frame_index == 4
    assert not player._playing, "playback must stop itself at the last frame, not loop or error"


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
