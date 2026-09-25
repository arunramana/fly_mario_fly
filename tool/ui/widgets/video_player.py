"""tool/ui/widgets/video_player.py -- ease-of-use redesign: the Run tab's
video player. Two backing modes:

- "live": during an active Play, shows whatever frame the existing
  preview mechanism (tool/core/runner.py's throttled queue) delivers --
  no seeking, no timeline scrubbing (there's nothing recorded yet to
  scrub through).
- "seekable": once a run's frame recording exists (tool/core/
  frame_store.py -- during a run for a live one, or immediately for a
  completed one loaded from history), backed by the whole (N, H, W)
  palette-index array loaded into memory: play/pause, frame-step, speed,
  and a scrubbable timeline all work off a plain integer frame index, no
  media player, no codec, no async position to chase.

A recording may hold more frames than the telemetry DataFrame has rows --
run_steering.py's death_animation_frames extends the recording past the
real end of the episode for display only. Telemetry-derived displays
(activity strip, brain map, the Data drawer) freeze on the last real row
once playback runs past `len(tel)`; the game view keeps playing the
actual recorded animation frames.

The "Brain map" toggle renders on demand from the CURRENT frame's
telemetry row (render.brain_panel.panel_for_row) -- a live per-frame
render, not a second video.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from tool.core.frame_store import frames_to_rgb, load_frames
from tool.core.palette import apply as apply_palette
from tool.ui.widgets.neuron_activity_strip import NeuronActivityStrip
from tool.ui.widgets.preview import frame_to_pixmap, integer_scale
from tool.ui.widgets.video_timeline import VideoTimeline

FPS = 60  # the emulator's own fixed frame rate (tool/core/runner.py)
SPEEDS = [0.25, 0.5, 1.0, 1.5, 2.0, 4.0]


class VideoPlayer(QWidget):
    # Emitted whenever the displayed frame index changes, seekable mode
    # only -- the Plots/Data drawers stay in sync with this.
    frame_changed = Signal(int)
    brain_map_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = "mario"
        self._mode = "empty"  # "empty" | "live" | "seekable"
        self._tel = None
        self._panel_ctx = None
        self._n_frames = 0
        self._frames_idx = None   # (N, H, W) uint8 palette indices
        self._palette = None      # (K, 3) uint8 RGB
        self._current_frame_index = 0
        self._last_pixmap = QPixmap()
        self._brain_map_on = False
        self._speed = 1.0
        self._playing = False
        self._play_accum = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        views = QHBoxLayout()
        self.frame_label = QLabel("(no run loaded)")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_label.setMinimumSize(256, 240)
        self.frame_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        views.addWidget(self.frame_label, 1)

        self.brain_label = QLabel()
        self.brain_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brain_label.setVisible(False)
        self.brain_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        views.addWidget(self.brain_label, 1)

        layout.addLayout(views, 1)

        # A fixed-rate (~60Hz) ticker, not a per-speed interval: 0.25x-4x
        # is handled by a fractional accumulator (_on_tick) so the timer
        # itself never has to run faster than the emulator's own frame
        # rate, whatever the selected speed.
        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(round(1000 / FPS))
        self._playback_timer.timeout.connect(self._on_tick)

        # Lives inside the brain-map view, not as a permanent fixture --
        # it duplicates the per-neuron numbers panel_for_row already
        # draws into brain_label, so it only earns its space when that
        # view is on.
        self.activity_strip = NeuronActivityStrip()
        self.activity_strip.setVisible(False)
        layout.addWidget(self.activity_strip)

        transport = QHBoxLayout()
        self.brain_map_button = QPushButton("Brain map")
        self.brain_map_button.setCheckable(True)
        self.brain_map_button.toggled.connect(self._on_brain_map_toggled)
        transport.addWidget(self.brain_map_button)

        self.play_button = QPushButton("Play")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.toggle_playback)
        transport.addWidget(self.play_button)

        self.step_back_button = QPushButton("<")
        self.step_back_button.setToolTip("Step back one frame (←)")
        self.step_back_button.clicked.connect(lambda: self.step_frame(-1))
        transport.addWidget(self.step_back_button)

        self.step_forward_button = QPushButton(">")
        self.step_forward_button.setToolTip("Step forward one frame (→)")
        self.step_forward_button.clicked.connect(lambda: self.step_frame(1))
        transport.addWidget(self.step_forward_button)

        self.back_1s_button = QPushButton("-1s")
        self.back_1s_button.clicked.connect(lambda: self.jump_seconds(-1))
        transport.addWidget(self.back_1s_button)

        self.forward_1s_button = QPushButton("+1s")
        self.forward_1s_button.clicked.connect(lambda: self.jump_seconds(1))
        transport.addWidget(self.forward_1s_button)

        self.speed_combo = QComboBox()
        for speed in SPEEDS:
            self.speed_combo.addItem(f"{speed:g}x", speed)
        self.speed_combo.setCurrentIndex(SPEEDS.index(1.0))
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        transport.addWidget(self.speed_combo)

        self.readout_label = QLabel("--:-- / --:--  (frame -/-)")
        transport.addWidget(self.readout_label)
        transport.addStretch(1)
        layout.addLayout(transport)

        self.timeline = VideoTimeline()
        self.timeline.seek_requested.connect(self.seek_frame)
        layout.addWidget(self.timeline)

        for button in (self.play_button, self.step_back_button, self.step_forward_button,
                       self.back_1s_button, self.forward_1s_button, self.speed_combo):
            button.setEnabled(False)

    # ---- mode: live (during a run) --------------------------------------

    def set_player(self, player: str) -> None:
        self._player = player

    def show_frame(self, obs, row: dict) -> None:
        """Called on every throttled frame while a run is actively
        playing (main_window.py's poll loop) -- no seeking possible yet,
        there's nothing finished to scrub through."""
        if self._mode != "live":
            self._enter_live_mode()
        displayed = apply_palette(obs, self._player, mario_x=row.get("mario_x"), mario_y=row.get("mario_y"))
        self._last_pixmap = frame_to_pixmap(displayed)
        self.frame_label.setPixmap(integer_scale(self._last_pixmap, self.frame_label.size()))
        self.activity_strip.update_from_row(row)
        frame = row.get("frame")
        if frame is not None:
            self.readout_label.setText(f"frame {frame} (live)")

    def _enter_live_mode(self) -> None:
        self._mode = "live"
        self._stop_playback()
        self._tel = None
        self._panel_ctx = None
        self._frames_idx = None
        self._palette = None
        self.brain_label.setVisible(False)
        self.timeline.set_length(0)
        for button in (self.play_button, self.step_back_button, self.step_forward_button,
                       self.back_1s_button, self.forward_1s_button, self.speed_combo):
            button.setEnabled(False)

    # ---- mode: seekable (a finished run's frame recording) ---------------

    def load_run(self, raw_frames_path, tel, info: dict | None = None) -> None:
        """`raw_frames_path=None`: "no recording" -- an older run, or one
        played with raw_frames off. The plots/data drawers still work off
        `tel` either way; only the video half of the tab is unavailable."""
        self._stop_playback()
        self._tel = tel
        self._info = info or {}
        if tel is not None and len(tel):
            from render.brain_panel import _panel_context
            self._panel_ctx = _panel_context(tel.fillna(0).reset_index(drop=True))
        else:
            self._panel_ctx = None

        loaded = load_frames(raw_frames_path) if raw_frames_path is not None else None
        if loaded is None:
            self._mode = "empty"
            self._frames_idx = None
            self._palette = None
            self._n_frames = len(tel) if tel is not None else 0
            # Found live: a run that WAS just watched live (this._last_
            # pixmap already holds its final frame) must not have that
            # wiped just because there's nothing to SCRUB through --
            # "no recording" means no seeking, not "forget what was just
            # on screen." Only the placeholder text applies when there
            # was never a live frame either (an older history entry from
            # a session that never showed it live).
            if self._last_pixmap.isNull():
                self.frame_label.setText("(no recording for this run)")
            self.brain_label.setVisible(False)
            self.timeline.set_length(0)
            for button in (self.play_button, self.step_back_button, self.step_forward_button,
                           self.back_1s_button, self.forward_1s_button, self.speed_combo):
                button.setEnabled(False)
            self.readout_label.setText("(no recording for this run)")
            return

        self._frames_idx, self._palette = loaded
        # The recording may run past the telemetry (death_animation_frames)
        # -- the actual frame count is the timeline's own length, not
        # len(tel).
        self._n_frames = len(self._frames_idx)
        self._mode = "seekable"
        self.timeline.set_length(self._n_frames)
        self.timeline.set_markers(_event_markers(tel, self._info))
        for button in (self.play_button, self.step_back_button, self.step_forward_button,
                       self.back_1s_button, self.forward_1s_button, self.speed_combo):
            button.setEnabled(True)
        self.play_button.setText("Play")
        self._refresh_frame_display(0)

    # ---- transport --------------------------------------------------

    def toggle_playback(self) -> None:
        if self._mode != "seekable":
            return
        if self._playing:
            self._stop_playback()
        else:
            self._start_playback()

    def _start_playback(self) -> None:
        if self._n_frames == 0:
            return
        if self._current_frame_index >= self._n_frames - 1:
            self.seek_frame(0)
        self._playing = True
        self._play_accum = 0.0
        self.play_button.setText("Pause")
        self._playback_timer.start()

    def _stop_playback(self) -> None:
        self._playing = False
        self._playback_timer.stop()
        self.play_button.setText("Play")

    def _on_tick(self) -> None:
        self._play_accum += self._speed
        step = int(self._play_accum)
        if step <= 0:
            return
        self._play_accum -= step
        new_frame = self._current_frame_index + step
        if new_frame >= self._n_frames - 1:
            self.seek_frame(self._n_frames - 1)
            self._stop_playback()
        else:
            self.seek_frame(new_frame)

    def step_frame(self, delta: int) -> None:
        if self._mode != "seekable":
            return
        self.seek_frame(self._current_frame_index + delta)

    def jump_seconds(self, delta: float) -> None:
        if self._mode != "seekable":
            return
        self.seek_frame(self._current_frame_index + round(delta * FPS))

    def go_start(self) -> None:
        if self._mode == "seekable":
            self.seek_frame(0)

    def go_end(self) -> None:
        if self._mode == "seekable":
            self.seek_frame(self._n_frames - 1)

    def seek_frame(self, frame: int) -> None:
        if self._mode != "seekable" or self._n_frames == 0:
            return
        self._refresh_frame_display(frame)

    def _on_speed_changed(self, index: int) -> None:
        self._speed = SPEEDS[index]
        self._play_accum = 0.0

    def _on_brain_map_toggled(self, checked: bool) -> None:
        self._brain_map_on = checked
        self.brain_label.setVisible(checked and self._mode != "empty")
        self.activity_strip.setVisible(checked and self._mode != "empty")
        self.brain_map_toggled.emit(checked)
        if self._mode == "seekable":
            self._refresh_frame_display(self._current_frame_index)

    # ---- shared display refresh --------------------------------------

    def _tel_row(self, frame: int) -> dict:
        """The telemetry row for `frame`, clamped to the last real row
        once `frame` runs past a death-animation extension -- there's no
        new circuit data past the real end of the episode, so every
        telemetry-derived display just freezes there."""
        if self._tel is None or not len(self._tel):
            return {}
        tel_frame = min(frame, len(self._tel) - 1)
        return self._tel.iloc[tel_frame].to_dict()

    def _refresh_frame_display(self, frame: int) -> None:
        frame = max(0, min(frame, max(0, self._n_frames - 1)))
        self._current_frame_index = frame
        self.timeline.set_position(frame)
        total_s = self._n_frames / FPS
        cur_s = frame / FPS
        self.readout_label.setText(
            f"{_fmt_time(cur_s)} / {_fmt_time(total_s)}  (frame {frame}/{max(0, self._n_frames - 1)})"
        )
        row = self._tel_row(frame)
        if self._frames_idx is not None and frame < len(self._frames_idx):
            rgb = frames_to_rgb(self._frames_idx[frame], self._palette)
            displayed = apply_palette(rgb, self._player, mario_x=row.get("mario_x"), mario_y=row.get("mario_y"))
            self._last_pixmap = frame_to_pixmap(displayed)
            self.frame_label.setPixmap(integer_scale(self._last_pixmap, self.frame_label.size()))
        if row:
            self.activity_strip.update_from_row(row)
        if self._brain_map_on and self._panel_ctx is not None and self._tel is not None and len(self._tel):
            from render.brain_panel import panel_for_row
            tel_frame = min(frame, len(self._tel) - 1)
            image = panel_for_row(self._tel, tel_frame, self._panel_ctx)
            self.brain_label.setPixmap(_pil_to_pixmap(image).scaled(
                self.brain_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        self.frame_changed.emit(frame)

    def current_row(self):
        if self._tel is None or not len(self._tel) or self._mode != "seekable":
            return None
        tel_frame = min(self._current_frame_index, len(self._tel) - 1)
        return self._tel.iloc[tel_frame]

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._last_pixmap.isNull() and self._mode in ("live", "seekable"):
            self.frame_label.setPixmap(integer_scale(self._last_pixmap, self.frame_label.size()))


def _fmt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"


def _pil_to_pixmap(image) -> QPixmap:
    import numpy as np
    arr = np.array(image.convert("RGB"))
    h, w, _ = arr.shape
    qimage = QImage(arr.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimage)


def _event_markers(tel, info: dict) -> dict[str, list[int]]:
    """Event ticks for the timeline: jump (telemetry's own "spike"
    column), climb ("climb"), death/flag (a single marker at the run's
    last frame, from its own summary info -- not a per-frame column).
    "stomp" isn't in per-frame telemetry today (only a run-total count,
    FullPolicy.n_stomps) -- appears automatically the moment it is,
    without a control that lies about ticks that were never computed."""
    markers: dict[str, list[int]] = {}
    if tel is None:
        return markers
    if "spike" in tel.columns:
        markers["jump"] = [int(i) for i in tel.index[tel["spike"].astype(bool)]]
    if "climb" in tel.columns:
        markers["climb"] = [int(i) for i in tel.index[tel["climb"].astype(bool)]]
    if "stomp" in tel.columns:
        markers["stomp"] = [int(i) for i in tel.index[tel["stomp"].astype(bool)]]
    if info.get("died_or_flagged") and len(tel):
        markers["death_or_flag"] = [len(tel) - 1]
    return markers
