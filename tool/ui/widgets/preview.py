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

from config.params import JumpParams
from tool.core.display_params import PreviewBarParams
from tool.core.palette import apply as apply_palette

# (telemetry key, display label, max value for the bar) -- a small, fixed
# set of per-population activations that already exist as row values,
# cheap because they're just floats the run already computed.
#
# Max values are per-population, not a uniform guess (tool/core/
# display_params.py's own PreviewBarParams, tool/SCALARS_UI.md) -- found
# in manual testing that a uniform 5.0 pinned TTMn at 100% the instant it
# fired, since a jump's TTMn value is exactly SPIKE_AMP, "a spike is a
# full-scale event", 10x the old assumed ceiling. dna01/dna02 (observed
# max ~10.4) were also clipped, just less severely. TTMn's own max reads
# config.jump.spike_amp directly rather than a duplicate display scalar.
_bars = PreviewBarParams()
_BARS = [
    ("lc4", "LC4", _bars.bar_max_lc4),
    ("lplc2", "LPLC2", _bars.bar_max_lplc2),
    ("ttmn", "TTMn", JumpParams().spike_amp),
    ("dna01", "DNa01", _bars.bar_max_dna01),
    ("dna02", "DNa02", _bars.bar_max_dna02),
    ("dnp09", "DNp09", _bars.bar_max_dnp09),
    ("mdn", "MDN", _bars.bar_max_mdn),
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
        displayed = apply_palette(obs, self._player, mario_x=row.get("mario_x"))
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
