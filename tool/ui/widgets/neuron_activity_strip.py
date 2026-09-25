"""tool/ui/widgets/neuron_activity_strip.py -- ease-of-use redesign: the
Run tab's per-population activation bars as one compact horizontal strip
under the preview, not a tall stack of labelled bars beside it. Split out
of tool/ui/widgets/preview.py, which now only draws the game frame.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from config.params import JumpParams
from tool.core.display_params import PreviewBarParams

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
BARS = [
    ("lc4", "LC4", _bars.bar_max_lc4),
    ("lplc2", "LPLC2", _bars.bar_max_lplc2),
    ("ttmn", "TTMn", JumpParams().spike_amp),
    ("dna01", "DNa01", _bars.bar_max_dna01),
    ("dna02", "DNa02", _bars.bar_max_dna02),
    ("dnp09", "DNp09", _bars.bar_max_dnp09),
    ("mdn", "MDN", _bars.bar_max_mdn),
]


class NeuronActivityStrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(14)

        self.bars: dict[str, QProgressBar] = {}
        for key, label_text, _max in BARS:
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(1)
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setMinimumWidth(60)
            cell_layout.addWidget(label)
            cell_layout.addWidget(bar)
            layout.addWidget(cell)
            self.bars[key] = bar
        layout.addStretch(1)

    def update_from_row(self, row: dict) -> None:
        for key, _label, max_value in BARS:
            value = row.get(key)
            bar = self.bars[key]
            if value is None:
                bar.setEnabled(False)
                continue
            bar.setEnabled(True)
            pct = int(max(0.0, min(1.0, float(value) / max_value)) * 100)
            bar.setValue(pct)

    def clear(self) -> None:
        for bar in self.bars.values():
            bar.setValue(0)
