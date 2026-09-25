"""tool/ui/widgets/video_timeline.py -- ease-of-use redesign, Run tab
video player: a scrub bar with event markers (jumps, climbs, death/flag
-- ticks in per-type colours) and a playhead. Click or drag anywhere to
seek; TelemetryPlots reuses the same "click seeks" convention for its own
playhead sync.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

# (marker type, colour, display label) -- shown in this order so a
# death/flag tick (the rarest, most important) draws last, on top.
MARKER_STYLES = [
    ("climb", (222, 178, 60), "Climb"),
    ("stomp", (168, 121, 224), "Stomp"),
    ("jump", (217, 89, 38), "Jump"),
    ("death_or_flag", (216, 40, 0), "Death/flag"),
]


class VideoTimeline(QWidget):
    seek_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._n_frames = 0
        self._position = 0
        self._markers: dict[str, list[int]] = {}
        self.setMinimumHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

    def set_length(self, n_frames: int) -> None:
        self._n_frames = max(0, n_frames)
        self._position = min(self._position, max(0, self._n_frames - 1))
        self.update()

    def set_position(self, frame: int) -> None:
        self._position = max(0, min(frame, max(0, self._n_frames - 1)))
        self.update()

    def set_markers(self, markers: dict[str, list[int]]) -> None:
        """`markers`: {"jump": [12, 340, ...], "climb": [...], "stomp":
        [...], "death_or_flag": [...]} -- a marker type absent or empty
        just draws nothing, it's never a fabricated tick."""
        self._markers = markers
        self.update()

    def _frame_at_x(self, x: float) -> int:
        if self._n_frames <= 1 or self.width() <= 0:
            return 0
        frac = max(0.0, min(1.0, x / self.width()))
        return round(frac * (self._n_frames - 1))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.seek_requested.emit(self._frame_at_x(event.position().x()))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.seek_requested.emit(self._frame_at_x(event.position().x()))

    def _x_for_frame(self, frame: int) -> float:
        if self._n_frames <= 1:
            return 0.0
        return (frame / (self._n_frames - 1)) * self.width()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        h = self.height()
        track_y = h // 2
        painter.fillRect(self.rect(), self.palette().window())
        painter.setPen(QPen((self.palette().color(self.foregroundRole())), 2))
        painter.drawLine(0, track_y, self.width(), track_y)

        for marker_type, color, _label in MARKER_STYLES:
            frames = self._markers.get(marker_type) or []
            painter.setPen(QPen(_qcolor(color), 2))
            for frame in frames:
                x = self._x_for_frame(frame)
                painter.drawLine(QPointF(x, 2), QPointF(x, h - 2))

        if self._n_frames > 0:
            x = self._x_for_frame(self._position)
            painter.setPen(QPen(_qcolor((252, 252, 252)), 3))
            painter.drawLine(QPointF(x, 0), QPointF(x, h))


def _qcolor(rgb):
    from PySide6.QtGui import QColor
    return QColor(*rgb)
