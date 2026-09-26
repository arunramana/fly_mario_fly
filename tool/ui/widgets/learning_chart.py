"""tool/ui/widgets/learning_chart.py -- the Run tab's "Learning" sub-tab:
max_x per training episode, the real network against each shuffled control
(same colours as the Player dropdown's groups), a rolling mean per network,
and the untrained baseline as a horizontal line. Clicking a point emits its
run number so the window can load that episode in the Player. Fed from the
run store's index entries (`training` key), so it fills in as training
appends episodes and works on reopening a project.
"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

ROLLING_WINDOW = 10
_COLORS = [(230, 90, 60), (70, 130, 220), (60, 170, 110), (170, 100, 200), (200, 160, 40)]


def collect_series(entries: list[dict]) -> tuple[dict[str, list[tuple[int, int, int]]], int | None]:
    """({network label: [(episode, max_x, run number), ...] sorted by episode},
    baseline max_x or None) from run-store index entries."""
    series: dict[str, list] = {}
    baseline = None
    for e in entries:
        t = e.get("training")
        if not t:
            continue
        if t["network"] == "baseline":
            baseline = t["max_x"]
            continue
        series.setdefault(t["network"], []).append((t["episode"], t["max_x"], e["number"]))
    for points in series.values():
        points.sort()
    return series, baseline


def rolling_mean(values: list[float], window: int = ROLLING_WINDOW) -> list[float]:
    out = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1): i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


class LearningChart(QWidget):
    point_selected = Signal(int)  # run number of the clicked episode

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.hint = QLabel("max_x per training episode. Click a point to load that episode in the Player.")
        layout.addWidget(self.hint)
        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", "episode")
        self.plot.setLabel("left", "max_x")
        self.plot.addLegend()
        layout.addWidget(self.plot, 1)
        self._series: dict[str, list] = {}
        self._baseline: int | None = None
        self._scatters: list = []
        self._baseline_line = None

    # ---- data ---------------------------------------------------------

    def set_entries(self, entries: list[dict]) -> None:
        self._series, self._baseline = collect_series(entries)
        self._redraw()

    def series(self) -> dict[str, list]:
        return self._series

    def baseline(self) -> int | None:
        return self._baseline

    def _redraw(self) -> None:
        self.plot.clear()
        self.plot.plotItem.legend.clear()
        self._scatters = []
        if self._baseline is not None:
            self._baseline_line = pg.InfiniteLine(
                pos=self._baseline, angle=0, movable=False,
                pen=pg.mkPen((150, 150, 150), style=pg.QtCore.Qt.PenStyle.DashLine),
                label="baseline", labelOpts={"position": 0.95, "color": (150, 150, 150)})
            self.plot.addItem(self._baseline_line)
        for i, (label, points) in enumerate(sorted(self._series.items(), key=lambda kv: _order(kv[0]))):
            color = _COLORS[i % len(_COLORS)]
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            scatter = pg.ScatterPlotItem(
                x=xs, y=ys, data=[p[2] for p in points], size=7,
                brush=pg.mkBrush(*color, 110), pen=pg.mkPen(None), name=label)
            scatter.sigClicked.connect(self._on_clicked)
            self.plot.addItem(scatter)
            self.plot.plot(xs, rolling_mean(ys), pen=pg.mkPen(color, width=2),
                           name=f"{label} (mean of {ROLLING_WINDOW})")
            self._scatters.append(scatter)

    def _on_clicked(self, _scatter, points, *_args) -> None:
        if len(points):
            self.point_selected.emit(int(points[0].data()))


def _order(label: str):
    if label == "real":
        return (0, 0)
    tail = label.rsplit(" ", 1)[-1]
    return (1, int(tail) if tail.isdigit() else 0)
