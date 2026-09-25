"""tool/ui/widgets/video_player.py -- ease-of-use redesign: the Run tab's
video player. Two backing modes:

- "live": during an active Play, shows whatever frame the existing
  preview mechanism (tool/core/runner.py's throttled queue) delivers --
  no seeking, no timeline scrubbing (there's nothing recorded yet to
  scrub through).
- "seekable": once a run's raw-frame recording exists (tool/core/
  raw_frame_recorder.py -- during a run for a live one, or immediately
  for a completed one loaded from history), backed by a real
  QMediaPlayer against that file: play/pause, frame-step, speed, and a
  scrubbable timeline with event markers all work.

The "Brain map" toggle renders on demand from the CURRENT frame's
telemetry row (render.brain_panel.panel_for_row) -- a live per-frame
render, not a second video.
"""

from __future__ import annotations

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

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
        self._current_frame_index = 0
        self._last_pixmap = QPixmap()
        self._brain_map_on = False
        self._was_playing_before_scrub = False

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

        # QVideoSink, not QVideoWidget: delivers decoded QVideoFrames
        # straight to us (videoFrameChanged) instead of painting them
        # itself -- QVideoWidget's own smooth-scaled paint would defeat
        # the whole-number nearest-neighbour scale-up every OTHER frame
        # source in this app already uses (tool/ui/widgets/preview.py).
        # game_label (defined above) is the ONE place any frame -- live
        # or seekable -- actually gets painted.
        self._video_sink = QVideoSink()
        self._video_sink.videoFrameChanged.connect(self._on_video_frame)
        self._media_player = QMediaPlayer()
        self._media_player.setVideoOutput(self._video_sink)
        self._media_player.positionChanged.connect(self._on_position_changed)
        self._media_player.playbackStateChanged.connect(self._on_playback_state_changed)

        layout.addLayout(views, 1)

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
        displayed = apply_palette(obs, self._player, mario_x=row.get("mario_x"))
        self._last_pixmap = frame_to_pixmap(displayed)
        self.frame_label.setPixmap(integer_scale(self._last_pixmap, self.frame_label.size()))
        self.activity_strip.update_from_row(row)
        frame = row.get("frame")
        if frame is not None:
            self.readout_label.setText(f"frame {frame} (live)")

    def _enter_live_mode(self) -> None:
        self._mode = "live"
        self._tel = None
        self._panel_ctx = None
        self.brain_label.setVisible(False)
        self.timeline.set_length(0)
        for button in (self.play_button, self.step_back_button, self.step_forward_button,
                       self.back_1s_button, self.forward_1s_button, self.speed_combo):
            button.setEnabled(False)

    # ---- mode: seekable (a finished run's raw-frame recording) ----------

    def load_run(self, raw_frames_path, tel, info: dict | None = None) -> None:
        """`raw_frames_path=None`: "no recording" -- an older run, or one
        played with raw_frames off. The plots/data drawers still work off
        `tel` either way; only the video half of the tab is unavailable."""
        self._tel = tel
        self._info = info or {}
        if tel is not None and len(tel):
            from render.brain_panel import _panel_context
            self._panel_ctx = _panel_context(tel.fillna(0).reset_index(drop=True))
            self._n_frames = len(tel)
        else:
            self._panel_ctx = None
            self._n_frames = 0

        if raw_frames_path is None:
            self._mode = "empty"
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

        self._mode = "seekable"
        self._media_player.setSource(QUrl.fromLocalFile(str(raw_frames_path)))
        self._media_player.pause()
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
        if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._media_player.pause()
        else:
            self._media_player.play()

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
        frame = max(0, min(frame, self._n_frames - 1))
        self._media_player.setPosition(round(frame / FPS * 1000))
        self._refresh_frame_display(frame)

    def _current_frame(self) -> int:
        """The media player's OWN reported position -- authoritative
        during actual continuous playback (its position advances on Qt's
        own clock, not ours), but `setPosition()` is asynchronous: right
        after a manual seek/step, this can still read the PREVIOUS
        position for a beat. step_frame/jump_seconds chain off
        `self._current_frame_index` instead (our own last-requested
        frame) specifically to avoid that lag on rapid sequential
        stepping -- found live, `step_frame` immediately after `seek_frame`
        read position() as still 0."""
        return round(self._media_player.position() / 1000 * FPS)

    def _on_speed_changed(self, index: int) -> None:
        self._media_player.setPlaybackRate(SPEEDS[index])

    def _on_playback_state_changed(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setText("Pause" if playing else "Play")

    def _on_position_changed(self, _position_ms: int) -> None:
        if self._mode == "seekable":
            self._refresh_frame_display(self._current_frame())

    def _on_video_frame(self, frame) -> None:
        """QVideoSink's own decoded frame -- painted here, not by
        QVideoWidget, so the scale-up stays whole-number nearest-
        neighbour like every other frame source in this app."""
        if self._mode != "seekable" or not frame.isValid():
            return
        image = frame.toImage()
        self._last_pixmap = QPixmap.fromImage(image)
        self.frame_label.setPixmap(integer_scale(self._last_pixmap, self.frame_label.size()))

    def _on_brain_map_toggled(self, checked: bool) -> None:
        self._brain_map_on = checked
        self.brain_label.setVisible(checked and self._mode != "empty")
        self.activity_strip.setVisible(checked and self._mode != "empty")
        self.brain_map_toggled.emit(checked)
        if self._mode == "seekable":
            self._refresh_frame_display(self._current_frame())

    # ---- shared display refresh --------------------------------------

    def _refresh_frame_display(self, frame: int) -> None:
        frame = max(0, min(frame, max(0, self._n_frames - 1)))
        self._current_frame_index = frame
        self.timeline.set_position(frame)
        total_s = self._n_frames / FPS
        cur_s = frame / FPS
        self.readout_label.setText(
            f"{_fmt_time(cur_s)} / {_fmt_time(total_s)}  (frame {frame}/{max(0, self._n_frames - 1)})"
        )
        if self._tel is not None and frame < len(self._tel):
            row = self._tel.iloc[frame].to_dict()
            self.activity_strip.update_from_row(row)
        if self._brain_map_on and self._panel_ctx is not None:
            from render.brain_panel import panel_for_row
            image = panel_for_row(self._tel, frame, self._panel_ctx)
            self.brain_label.setPixmap(_pil_to_pixmap(image).scaled(
                self.brain_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        self.frame_changed.emit(frame)

    def current_row(self):
        if self._tel is None:
            return None
        frame = self._current_frame() if self._mode == "seekable" else None
        if frame is None or frame >= len(self._tel):
            return None
        return self._tel.iloc[frame]

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
