"""tool/ui/widgets/plots.py -- telemetry plots (tool/PLAN.md P4; ease-of-
use redesign, tool/SPEC_ui_retro.md follow-up): x progress, DNp01/Giant
Fiber, steering L/R, odour, jumps -- one pyqtgraph.PlotWidget per series,
laid out as a 2x3 grid (not a tall vertical stack) in the Run tab's
detail pane, from a telemetry DataFrame (live-run rows appended as they
arrive, or a full CSV loaded from run history). Ease-of-use redesign: a
shared vertical playhead line synced to the video player's current
frame, and clicking any plot seeks the player there.
"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QWidget

# (telemetry column, plot title) -- exactly 6, a 2-row x 3-column grid.
_SERIES = [
    ("mario_x", "x progress"),
    ("ttmn", "TTMn (Giant Fiber)"),
    ("r_team", "steering R"),
    ("dna01", "DNa01"),
    ("odor_l", "odour L"),
    ("odor_r", "odour R"),
]
_GRID_COLUMNS = 3


class TelemetryPlots(QWidget):
    seek_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)
        self._plots = {}
        self._curves = {}
        self._playheads = {}
        for index, (column, title) in enumerate(_SERIES):
            plot = pg.PlotWidget(title=title)
            plot.setMinimumHeight(120)
            curve = plot.plot([], [])
            playhead = pg.InfiniteLine(pos=0, angle=90, movable=False,
                                        pen=pg.mkPen((252, 252, 252), width=1))
            plot.addItem(playhead)
            plot.scene().sigMouseClicked.connect(
                lambda ev, p=plot: self._on_plot_clicked(ev, p))
            layout.addWidget(plot, index // _GRID_COLUMNS, index % _GRID_COLUMNS)
            self._plots[column] = plot
            self._curves[column] = curve
            self._playheads[column] = playhead

    def set_dataframe(self, tel) -> None:
        """Replaces every plot's data from a full telemetry DataFrame --
        loading a run from history."""
        if "frame" not in tel.columns:
            return
        x = tel["frame"].to_numpy()
        for column, curve in self._curves.items():
            if column in tel.columns:
                curve.setData(x, tel[column].to_numpy())

    def set_playhead(self, frame: int) -> None:
        for line in self._playheads.values():
            line.setPos(frame)

    def _on_plot_clicked(self, event, plot) -> None:
        view_box = plot.getPlotItem().getViewBox()
        point = view_box.mapSceneToView(event.scenePos())
        self.seek_requested.emit(max(0, round(point.x())))

    def clear(self) -> None:
        for curve in self._curves.values():
            curve.setData([], [])
        self.set_playhead(0)
