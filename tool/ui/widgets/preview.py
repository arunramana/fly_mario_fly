"""tool/ui/widgets/preview.py -- live preview: the raw `obs` RGB frame
(through tool/core/palette.py if Luigi is selected) plus simple telemetry
bars, cheap to draw every frame (tool/PLAN.md P4). The full
`render.brain_panel` composition stays a post-run, offline step -- P0's
timing spike measured it at 14fps, unusable live.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from tool.core.palette import apply as apply_palette

# (telemetry key, display label, max value for the bar) -- a small, fixed
# set of per-population activations that already exist as row values,
# cheap because they're just floats the run already computed.
_BARS = [
    ("lc4", "LC4", 5.0),
    ("lplc2", "LPLC2", 5.0),
    ("ttmn", "TTMn", 5.0),
    ("dna01", "DNa01", 5.0),
    ("dna02", "DNa02", 5.0),
    ("dnp09", "DNp09", 5.0),
    ("mdn", "MDN", 5.0),
]


def frame_to_pixmap(frame: np.ndarray) -> QPixmap:
    frame = np.ascontiguousarray(frame)
    h, w, _ = frame.shape
    image = QImage(frame.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(image.copy())  # copy: `frame` may be freed/reused after this call


class PreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = "mario"

        layout = QVBoxLayout(self)
        self.frame_label = QLabel("(no run yet)")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_label.setMinimumSize(256, 240)
        layout.addWidget(self.frame_label)

        self.bars: dict[str, QProgressBar] = {}
        for key, label_text, _max in _BARS:
            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(label_text)
            bar = QProgressBar()
            bar.setRange(0, 100)
            row_layout.addWidget(label)
            row_layout.addWidget(bar)
            layout.addWidget(row)
            self.bars[key] = bar

    def set_player(self, player: str) -> None:
        self._player = player

    def show_frame(self, obs: np.ndarray, row: dict) -> None:
        displayed = apply_palette(obs, self._player)
        pixmap = frame_to_pixmap(displayed)
        self.frame_label.setPixmap(
            pixmap.scaled(512, 480, Qt.AspectRatioMode.KeepAspectRatio)
        )
        for key, _label, max_value in _BARS:
            value = row.get(key)
            bar = self.bars[key]
            if value is None:
                bar.setEnabled(False)
                continue
            bar.setEnabled(True)
            pct = int(max(0.0, min(1.0, float(value) / max_value)) * 100)
            bar.setValue(pct)

    def clear(self) -> None:
        self.frame_label.setText("(no run yet)")
        self.frame_label.setPixmap(QPixmap())
        for bar in self.bars.values():
            bar.setValue(0)
