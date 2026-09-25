"""tool/ui/widgets/video_canvas.py -- Run tab / player redesign: the video
area itself. A plain QLabel+setPixmap can't letterbox on a dark background
(its own background shows through the unfilled margin, sky-blue like the
rest of the theme) -- this widget paints the frame itself so the margin
around a whole-number-scaled NES frame is always dark, video-player style,
regardless of the surrounding theme.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

LETTERBOX_COLOR = QColor(10, 10, 10)


class VideoCanvas(QWidget):
    """set_pixmap(pixmap) once per displayed frame; paintEvent does the
    whole-number nearest-neighbour scale-up and centers the result on a
    dark background. `pixmap()`/`frame_label` compatibility: kept as a
    plain accessor so code written against the old QLabel-based player
    (`frame_label.pixmap().isNull()`) still works unchanged."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._placeholder = "(no run loaded)"
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(256, 240)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def pixmap(self) -> QPixmap:
        """QLabel-compatible accessor -- see this class's own docstring."""
        return self._pixmap

    def setText(self, text: str) -> None:
        """QLabel-compatible: the placeholder shown when there's no frame."""
        self._placeholder = text
        self.update()

    def target_rect(self) -> QRect:
        """Where the frame is actually drawn -- overlays anchor to this,
        not to the widget's own full rect, so they land on the video
        itself rather than in the letterboxed margin."""
        if self._pixmap.isNull():
            return self.rect()
        w, h = self._pixmap.width(), self._pixmap.height()
        factor = max(1, min(self.width() // w, self.height() // h))
        draw_w, draw_h = w * factor, h * factor
        x = (self.width() - draw_w) // 2
        y = (self.height() - draw_h) // 2
        return QRect(x, y, draw_w, draw_h)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), LETTERBOX_COLOR)
        if self._pixmap.isNull():
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._placeholder)
            return
        rect = self.target_rect()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(rect, self._pixmap, self._pixmap.rect())
