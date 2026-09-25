"""tool/ui/widgets/run_player.py -- ease-of-use redesign, Run tab player:
live mode vs seekable mode, auto-hiding transport bar, next/prev event,
LIVE badge. Exercises the mechanism directly with a synthetic telemetry
DataFrame, not through a full simulation run.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tool.core.frame_store import FrameStore
from tool.ui.widgets.run_player import RunPlayer, _event_markers


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
    player = RunPlayer()
    assert player._mode == "empty"
    assert not player.play_button.isEnabled()


def test_show_frame_enters_live_mode(qapp):
    player = RunPlayer()
    obs = np.zeros((240, 256, 3), dtype=np.uint8)
    player.show_frame(obs, {"frame": 3, "mario_x": 10})
    assert player._mode == "live"
    assert not player.canvas.pixmap().isNull()
    assert not player.play_button.isEnabled()


def test_set_live_shows_and_hides_badge(qapp):
    # isHidden(), not isVisible(): RunPlayer is never shown on screen in
    # this offscreen test, so isVisible() would read False for every
    # child regardless of setVisible() -- isHidden() reflects the
    # explicit setVisible() call directly.
    player = RunPlayer()
    assert player.live_badge.isHidden()
    player.set_live(True)
    assert not player.live_badge.isHidden()
    player.set_live(False)
    assert player.live_badge.isHidden()


def test_load_run_with_no_recording_shows_no_recording_state(qapp):
    player = RunPlayer()
    tel = _fake_telemetry()
    player.load_run(None, tel, {"died_or_flagged": False})
    assert player._mode == "empty"
    assert not player.play_button.isEnabled()


def test_load_run_with_a_real_recording_enables_transport(qapp, tmp_path):
    raw_path = _real_recording(tmp_path)
    player = RunPlayer()
    player.load_run(raw_path, _fake_telemetry(), {"died_or_flagged": False})
    assert player._mode == "seekable"
    assert player.play_button.isEnabled()
    assert player.timeline._n_frames == 30


def test_seek_frame_updates_timeline_and_emits_frame_changed(qapp, tmp_path):
    raw_path = _real_recording(tmp_path)
    player = RunPlayer()
    player.load_run(raw_path, _fake_telemetry(), {"died_or_flagged": False})
    seen = []
    player.frame_changed.connect(seen.append)
    player.seek_frame(10)
    assert player.timeline._position == 10
    assert 10 in seen


def test_step_frame_and_jump_seconds(qapp, tmp_path):
    raw_path = _real_recording(tmp_path)
    player = RunPlayer()
    player.load_run(raw_path, _fake_telemetry(), {"died_or_flagged": False})
    player.seek_frame(10)
    player.step_frame(1)
    assert player._current_frame_index == 11
    player.step_frame(-1)
    assert player._current_frame_index == 10


def test_next_event_jumps_to_the_nearest_marker_after_current(qapp, tmp_path):
    raw_path = _real_recording(tmp_path)
    player = RunPlayer()
    player.load_run(raw_path, _fake_telemetry(), {"died_or_flagged": True})  # markers: jump 5,20; climb 10; death 29
    player.seek_frame(0)
    player.next_event()
    assert player._current_frame_index == 5
    player.next_event()
    assert player._current_frame_index == 10
    player.next_event()
    assert player._current_frame_index == 20
    player.next_event()
    assert player._current_frame_index == 29


def test_prev_event_jumps_to_the_nearest_marker_before_current(qapp, tmp_path):
    raw_path = _real_recording(tmp_path)
    player = RunPlayer()
    player.load_run(raw_path, _fake_telemetry(), {"died_or_flagged": True})
    player.seek_frame(29)
    player.prev_event()
    assert player._current_frame_index == 20
    player.prev_event()
    assert player._current_frame_index == 10
    player.prev_event()
    assert player._current_frame_index == 5


def test_playback_advances_and_stops_at_the_end(qapp, tmp_path):
    raw_path = _real_recording(tmp_path, n_frames=5)
    player = RunPlayer()
    player.load_run(raw_path, _fake_telemetry(), {"died_or_flagged": False})
    player.toggle_playback()
    assert player._playing
    for _ in range(10):
        player._on_tick()
    assert player._current_frame_index == 4
    assert not player._playing


def test_auto_hide_bar_hides_while_playing_after_timeout_fires(qapp, tmp_path):
    raw_path = _real_recording(tmp_path)
    player = RunPlayer()
    player.load_run(raw_path, _fake_telemetry(), {"died_or_flagged": False})
    player.toggle_playback()
    assert not player.transport.isHidden()
    player._auto_hide()
    assert player.transport.isHidden()


def test_auto_hide_does_not_hide_while_paused(qapp, tmp_path):
    raw_path = _real_recording(tmp_path)
    player = RunPlayer()
    player.load_run(raw_path, _fake_telemetry(), {"died_or_flagged": False})
    player._auto_hide()
    assert not player.transport.isHidden(), "paused -- the bar should stay put, nothing to interact with mid-hide"


def test_recording_longer_than_telemetry_still_plays_with_frozen_tel_rows(qapp, tmp_path):
    raw_path = _real_recording(tmp_path, n_frames=40)
    player = RunPlayer()
    player.load_run(raw_path, _fake_telemetry(n=30), {"died_or_flagged": True})
    assert player._n_frames == 40
    player.seek_frame(35)
    assert not player.canvas.pixmap().isNull()
    row = player.current_row()
    assert row is not None and row["frame"] == 29


def test_event_markers_from_telemetry_and_summary():
    tel = _fake_telemetry()
    markers = _event_markers(tel, {"died_or_flagged": True})
    assert markers["jump"] == [5, 20]
    assert markers["climb"] == [10]
    assert markers["death_or_flag"] == [len(tel) - 1]


def test_event_markers_no_death_marker_when_survived():
    tel = _fake_telemetry()
    markers = _event_markers(tel, {"died_or_flagged": False})
    assert "death_or_flag" not in markers
