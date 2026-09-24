"""tool/ui/widgets/plots.py -- telemetry plots (tool/PLAN.md P4): x
progress, DNp01/Giant Fiber, steering L/R, odour, jumps -- one
pyqtgraph.PlotWidget per series, from a telemetry DataFrame (live-run rows
appended as they arrive, or a full CSV loaded from run history).
"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget

# (telemetry column, plot title)
_SERIES = [
    ("mario_x", "x progress"),
    ("ttmn", "TTMn (Giant Fiber)"),
    ("r_team", "steering R"),
    ("dna01", "DNa01"),
    ("odor_l", "odour L"),
    ("odor_r", "odour R"),
]


class TelemetryPlots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._plots = {}
        self._curves = {}
        for column, title in _SERIES:
            plot = pg.PlotWidget(title=title)
            plot.setMinimumHeight(80)
            curve = plot.plot([], [])
            layout.addWidget(plot)
            self._plots[column] = plot
            self._curves[column] = curve

    def set_dataframe(self, tel) -> None:
        """Replaces every plot's data from a full telemetry DataFrame --
        loading a run from history."""
        if "frame" not in tel.columns:
            return
        x = tel["frame"].to_numpy()
        for column, curve in self._curves.items():
            if column in tel.columns:
                curve.setData(x, tel[column].to_numpy())

    def clear(self) -> None:
        for curve in self._curves.values():
            curve.setData([], [])
