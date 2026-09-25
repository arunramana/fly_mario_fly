"""tool/ui/widgets/preview.py -- live preview: the raw `obs` RGB frame
(through tool/core/palette.py if Luigi is selected), cheap to draw every
frame (tool/PLAN.md P4). The full `render.brain_panel` composition stays
a post-run, offline step -- P0's timing spike measured it at 14fps,
unusable live.

Ease-of-use redesign: this widget is now JUST the frame -- the neuron
activity bars moved to tool/ui/widgets/neuron_activity_strip.py, a
compact horizontal strip the Run tab places below this widget. `obs`
arrives at full resolution now (tool/core/runner.py no longer strides it
2x); this widget scales UP by a whole-number factor with nearest-
neighbour sampling so the preview can be the largest element on the tab
without turning pixel art to mush.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from tool.core.palette import apply as apply_palette

NES_W, NES_H = 256, 240


def frame_to_pixmap(frame: np.ndarray) -> QPixmap:
    frame = np.ascontiguousarray(frame)
    h, w, _ = frame.shape
    image = QImage(frame.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(image.copy())  # copy: `frame` may be freed/reused after this call


def integer_scale(pixmap: QPixmap, target: QSize) -> QPixmap:
    """Scales UP by the largest whole-number factor that still fits
    `target`, nearest-neighbour -- pixel art stays crisp instead of soft
    (a smooth filter) or needlessly tiny (no scale-up at all). Never
    scales down below 1x: a target smaller than the source just shows the
    source at native size, since shrinking pixel art is the one direction
    that never looks better."""
    if pixmap.isNull() or target.width() <= 0 or target.height() <= 0:
        return pixmap
    factor = max(1, min(target.width() // pixmap.width(), target.height() // pixmap.height()))
    return pixmap.scaled(pixmap.width() * factor, pixmap.height() * factor,
                          Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)


class PreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = "mario"
        self._last_pixmap = QPixmap()
        # Set by the owning tab (RunTab) so show_frame() can feed both
        # widgets from the one `row` dict main_window.py already has --
        # keeps `self.preview.show_frame(obs, row)` as the one call site
        # (tool/tests monkeypatch it directly), with the strip as a
        # silent passenger rather than a second call site to keep in sync.
        self.activity_strip = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.frame_label = QLabel("(no run yet)")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_label.setMinimumSize(NES_W, NES_H)
        self.frame_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.frame_label)

    def set_player(self, player: str) -> None:
        self._player = player

    def show_frame(self, obs: np.ndarray, row: dict) -> None:
        displayed = apply_palette(obs, self._player, mario_x=row.get("mario_x"))
        self._last_pixmap = frame_to_pixmap(displayed)
        self.frame_label.setPixmap(integer_scale(self._last_pixmap, self.frame_label.size()))
        if self.activity_strip is not None:
            self.activity_strip.update_from_row(row)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._last_pixmap.isNull():
            self.frame_label.setPixmap(integer_scale(self._last_pixmap, self.frame_label.size()))

    def clear(self) -> None:
        self._last_pixmap = QPixmap()
        self.frame_label.setText("(no run yet)")
        self.frame_label.setPixmap(QPixmap())
        if self.activity_strip is not None:
            self.activity_strip.clear()
