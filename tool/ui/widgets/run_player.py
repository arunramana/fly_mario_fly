"""tool/ui/widgets/run_player.py -- Run tab / player redesign: the video
area plus its auto-hiding transport bar. Two backing modes, same as the
player this replaces (tool/ui/widgets/video_player.py, removed):

- "live": during an active Play, shows whatever frame the throttled
  preview queue delivers -- no seeking, nothing recorded yet to scrub.
- "seekable": a finished run's frame recording (tool/core/frame_store.py),
  the whole (N, H, W) palette-index array loaded into memory -- seeking/
  stepping/speed are plain integer-index math, no media player, no async
  position to chase.

A recording may hold more frames than the telemetry DataFrame has rows
(run_steering.py's death_animation_frames extends it for display only,
past the real end of the episode) -- telemetry-derived state (current_row,
event markers) freezes on the last real row once playback runs past
len(tel); the game view keeps playing the actual recorded frames.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from tool.core.frame_store import frames_to_rgb, load_frames
from tool.core.palette import apply as apply_palette
from tool.ui.widgets.preview import frame_to_pixmap
from tool.ui.widgets.video_canvas import VideoCanvas
from tool.ui.widgets.video_timeline import VideoTimeline

try:
    import qtawesome as qta
except ImportError:  # pragma: no cover -- qtawesome is a hard requirement
    qta = None        # (tool/requirements.txt); this guard just keeps a
                       # missing/broken install from crashing the whole tab.

FPS = 60
SPEEDS = [0.25, 0.5, 1.0, 1.5, 2.0, 4.0]
AUTO_HIDE_MS = 2500
ALL_EVENT_KINDS = ("jump", "climb", "stomp", "death_or_flag")


def _icon(name: str):
    return qta.icon(name, color="white") if qta is not None else None


class RunPlayer(QWidget):
    frame_changed = Signal(int)
    fullscreen_toggled = Signal(bool)
    live_row = Signal(dict)  # emitted from show_frame -- lets overlays track a live run too

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = "mario"
        self._mode = "empty"  # "empty" | "live" | "seekable"
        self._tel = None
        self._info: dict = {}
        self._n_frames = 0
        self._frames_idx = None
        self._palette = None
        self._current_frame_index = 0
        self._speed = 1.0
        self._playing = False
        self._play_accum = 0.0
        self._live = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.canvas = VideoCanvas()
        self.canvas.setMouseTracking(True)
        self.canvas.installEventFilter(self)
        layout.addWidget(self.canvas, 1)
        # QLabel-compatible alias -- tool/tests monkeypatches/reads
        # `window.run_tab.preview.frame_label`/`.show_frame` directly,
        # unaffected by this widget's own internal reshuffle.
        self.frame_label = self.canvas

        # LIVE badge -- a child of the canvas so it floats over the video
        # (top-left corner) rather than taking its own layout row.
        self.live_badge = QLabel("LIVE", self.canvas)
        self.live_badge.setObjectName("liveBadge")
        self.live_badge.move(10, 10)
        self.live_badge.adjustSize()
        self.live_badge.setVisible(False)

        # Auto-hiding transport bar: a child of the canvas, positioned at
        # its bottom edge in resizeEvent, so the video itself gets ~all of
        # the widget's height when the bar is hidden.
        self.transport = QWidget(self.canvas)
        self.transport.setObjectName("transportBar")
        self.transport.setMouseTracking(True)
        transport_row = QHBoxLayout(self.transport)
        transport_row.setContentsMargins(8, 4, 8, 4)

        self.play_button = QPushButton()
        self.play_button.setIcon(_icon("fa5s.play")) if qta else self.play_button.setText("Play")
        self.play_button.clicked.connect(self.toggle_playback)
        transport_row.addWidget(self.play_button)

        self.step_back_button = QPushButton()
        self.step_back_button.setIcon(_icon("fa5s.step-backward")) if qta else self.step_back_button.setText("<")
        self.step_back_button.setToolTip("Step back one frame (←)")
        self.step_back_button.clicked.connect(lambda: self.step_frame(-1))
        transport_row.addWidget(self.step_back_button)

        self.step_forward_button = QPushButton()
        self.step_forward_button.setIcon(_icon("fa5s.step-forward")) if qta else self.step_forward_button.setText(">")
        self.step_forward_button.setToolTip("Step forward one frame (→)")
        self.step_forward_button.clicked.connect(lambda: self.step_frame(1))
        transport_row.addWidget(self.step_forward_button)

        self.timeline = VideoTimeline()
        self.timeline.seek_requested.connect(self.seek_frame)
        transport_row.addWidget(self.timeline, 1)

        self.readout_label = QLabel("--:-- / --:--  (frame -/-)")
        transport_row.addWidget(self.readout_label)

        self.speed_combo = QComboBox()
        for speed in SPEEDS:
            self.speed_combo.addItem(f"{speed:g}x", speed)
        self.speed_combo.setCurrentIndex(SPEEDS.index(1.0))
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        transport_row.addWidget(self.speed_combo)

        self.fullscreen_button = QPushButton()
        self.fullscreen_button.setIcon(_icon("fa5s.expand")) if qta else self.fullscreen_button.setText("[ ]")
        self.fullscreen_button.setToolTip("Fullscreen (F)")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        transport_row.addWidget(self.fullscreen_button)

        for button in (self.play_button, self.step_back_button, self.step_forward_button, self.speed_combo):
            button.setEnabled(False)

        self._hide_timer = QTimer(self)
        self._hide_timer.setInterval(AUTO_HIDE_MS)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._auto_hide)

        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(round(1000 / FPS))
        self._playback_timer.timeout.connect(self._on_tick)

    # ---- auto-hide bar ----------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        if obj is self.canvas:
            if event.type() == QEvent.Type.Resize:
                self._reposition_children()
            elif event.type() in (QEvent.Type.MouseMove, QEvent.Type.Enter):
                self._show_bar_briefly()
        return super().eventFilter(obj, event)

    def _reposition_children(self) -> None:
        bar_h = self.transport.sizeHint().height()
        self.transport.setGeometry(0, self.canvas.height() - bar_h, self.canvas.width(), bar_h)

    def _show_bar_briefly(self) -> None:
        self.transport.setVisible(True)
        if self._playing:
            self._hide_timer.start()
        else:
            self._hide_timer.stop()

    def _auto_hide(self) -> None:
        if self._playing:
            self.transport.setVisible(False)

    # ---- mode: live -------------------------------------------------------

    def set_player(self, player: str) -> None:
        self._player = player

    def set_live(self, live: bool) -> None:
        self._live = live
        self.live_badge.setVisible(live)

    def show_frame(self, obs, row: dict) -> None:
        if self._mode != "live":
            self._enter_live_mode()
        displayed = apply_palette(obs, self._player, mario_x=row.get("mario_x"), mario_y=row.get("mario_y"))
        self.canvas.set_pixmap(frame_to_pixmap(displayed))
        frame = row.get("frame")
        if frame is not None:
            self.readout_label.setText(f"frame {frame} (live)")
        self.live_row.emit(row)

    def _enter_live_mode(self) -> None:
        self._mode = "live"
        self._stop_playback()
        self._tel = None
        self._frames_idx = None
        self._palette = None
        self.timeline.set_length(0)
        for button in (self.play_button, self.step_back_button, self.step_forward_button, self.speed_combo):
            button.setEnabled(False)

    # ---- mode: seekable -----------------------------------------------------

    def load_run(self, raw_frames_path, tel, info: dict | None = None) -> None:
        self._stop_playback()
        self.set_live(False)
        self._tel = tel
        self._info = info or {}

        loaded = load_frames(raw_frames_path) if raw_frames_path is not None else None
        if loaded is None:
            self._mode = "empty"
            self._frames_idx = None
            self._palette = None
            self._n_frames = len(tel) if tel is not None else 0
            if self.canvas.pixmap().isNull():
                self.canvas.setText("(no recording for this run)")
            self.timeline.set_length(0)
            for button in (self.play_button, self.step_back_button, self.step_forward_button, self.speed_combo):
                button.setEnabled(False)
            self.readout_label.setText("(no recording for this run)")
            return

        self._frames_idx, self._palette = loaded
        self._n_frames = len(self._frames_idx)
        self._mode = "seekable"
        self.timeline.set_length(self._n_frames)
        self.timeline.set_markers(_event_markers(tel, self._info))
        for button in (self.play_button, self.step_back_button, self.step_forward_button, self.speed_combo):
            button.setEnabled(True)
        self._set_play_icon(False)
        self._refresh_frame_display(0)

    # ---- transport ----------------------------------------------------------

    def toggle_playback(self) -> None:
        if self._mode != "seekable":
            return
        self._stop_playback() if self._playing else self._start_playback()

    def _start_playback(self) -> None:
        if self._n_frames == 0:
            return
        if self._current_frame_index >= self._n_frames - 1:
            self.seek_frame(0)
        self._playing = True
        self._play_accum = 0.0
        self._set_play_icon(True)
        self._playback_timer.start()
        self._hide_timer.start()

    def _stop_playback(self) -> None:
        self._playing = False
        self._playback_timer.stop()
        self._hide_timer.stop()
        self.transport.setVisible(True)
        self._set_play_icon(False)

    def _set_play_icon(self, playing: bool) -> None:
        if qta is not None:
            self.play_button.setIcon(_icon("fa5s.pause" if playing else "fa5s.play"))
        else:
            self.play_button.setText("Pause" if playing else "Play")

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
        if self._mode == "seekable":
            self.seek_frame(self._current_frame_index + delta)

    def jump_seconds(self, delta: float) -> None:
        if self._mode == "seekable":
            self.seek_frame(self._current_frame_index + round(delta * FPS))

    def go_start(self) -> None:
        if self._mode == "seekable":
            self.seek_frame(0)

    def go_end(self) -> None:
        if self._mode == "seekable":
            self.seek_frame(self._n_frames - 1)

    def seek_frame(self, frame: int) -> None:
        if self._mode == "seekable" and self._n_frames:
            self._refresh_frame_display(frame)

    def next_event(self) -> None:
        self._jump_to_event(1)

    def prev_event(self) -> None:
        self._jump_to_event(-1)

    def _jump_to_event(self, direction: int) -> None:
        if self._mode != "seekable":
            return
        frames = sorted({f for kind in ALL_EVENT_KINDS for f in self.timeline._markers.get(kind, [])})
        if not frames:
            return
        current = self._current_frame_index
        candidates = [f for f in frames if f > current] if direction > 0 else [f for f in frames if f < current]
        target = min(candidates) if direction > 0 else max(candidates, default=None)
        if target is not None:
            self.seek_frame(target)

    def _on_speed_changed(self, index: int) -> None:
        self._speed = SPEEDS[index]
        self._play_accum = 0.0

    def toggle_fullscreen(self) -> None:
        window = self.window()
        going_fullscreen = not window.isFullScreen()
        window.showNormal() if not going_fullscreen else window.showFullScreen()
        self.fullscreen_toggled.emit(going_fullscreen)

    # ---- shared display refresh --------------------------------------------

    def _tel_row(self, frame: int) -> dict:
        if self._tel is None or not len(self._tel):
            return {}
        return self._tel.iloc[min(frame, len(self._tel) - 1)].to_dict()

    def _refresh_frame_display(self, frame: int) -> None:
        frame = max(0, min(frame, max(0, self._n_frames - 1)))
        self._current_frame_index = frame
        self.timeline.set_position(frame)
        total_s, cur_s = self._n_frames / FPS, frame / FPS
        self.readout_label.setText(
            f"{_fmt_time(cur_s)} / {_fmt_time(total_s)}  (frame {frame}/{max(0, self._n_frames - 1)})")
        if self._frames_idx is not None and frame < len(self._frames_idx):
            row = self._tel_row(frame)
            rgb = frames_to_rgb(self._frames_idx[frame], self._palette)
            displayed = apply_palette(rgb, self._player, mario_x=row.get("mario_x"), mario_y=row.get("mario_y"))
            self.canvas.set_pixmap(frame_to_pixmap(displayed))
        self.frame_changed.emit(frame)

    def current_row(self):
        if self._tel is None or not len(self._tel) or self._mode != "seekable":
            return None
        return self._tel.iloc[min(self._current_frame_index, len(self._tel) - 1)]

    def event_markers(self) -> dict:
        return dict(self.timeline._markers)


def _fmt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"


def _event_markers(tel, info: dict) -> dict[str, list[int]]:
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
