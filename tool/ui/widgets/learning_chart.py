"""tool/ui/widgets/learning_chart.py -- the Run tab's "Learning" sub-tab:
max_x (or score, from the selector) per training episode, the real network against each shuffled control
(same colours as the Player dropdown's groups), a rolling mean per network,
and the untrained baseline as a horizontal line. Clicking a point emits its
run number so the window can load that episode in the Player. Fed from the
run store's index entries (`training` key), so it fills in as training
appends episodes and works on reopening a project. Below it, when the
training run had a held-out test set, the test win-rate (frozen weights, seeds
never trained on) against episode, from training_eval.json.
"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

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


def collect_scores(entries: list[dict]) -> dict[str, list[tuple[int, float, int]]]:
    """{network label: [(episode, score, run number), ...]}: the same episodes as
    collect_series but with the game score (entries recorded before scores were kept are
    skipped)."""
    out: dict[str, list] = {}
    for e in entries:
        t = e.get("training")
        if not t or t["network"] == "baseline" or t.get("score") is None:
            continue
        out.setdefault(t["network"], []).append((t["episode"], t["score"], e["number"]))
    for points in out.values():
        points.sort()
    return out


def collect_tests(evals: list[dict]) -> dict[str, list[tuple[int, float, float]]]:
    """{network label: [(episode, win rate 0-100, mean test max_x), ...]} from
    training_eval.json, for the most recent training session only (its `baseline` run
    number is the session id), so re-training does not overlay two curves."""
    if not evals:
        return {}
    session = max(e.get("baseline", 0) for e in evals)
    out: dict[str, list] = {}
    for e in evals:
        if e.get("baseline", 0) == session:
            out.setdefault(e["network"], []).append((e["episode"], 100.0 * e["win_rate"], e["mean_max_x"]))
    for points in out.values():
        points.sort()
    return out


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
        top = QHBoxLayout()
        self.hint = QLabel("Per training episode. Click a point to load that episode in the Player.")
        top.addWidget(self.hint, 1)
        self.metric_combo = QComboBox()
        self.metric_combo.addItem("max_x", "max_x")
        self.metric_combo.addItem("score", "score")
        self.metric_combo.currentIndexChanged.connect(lambda _i: self._redraw())
        top.addWidget(self.metric_combo)
        layout.addLayout(top)
        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", "episode")
        self.plot.setLabel("left", "max_x")
        self.plot.addLegend()
        layout.addWidget(self.plot, 2)
        self.test_label = QLabel("Test win-rate (frozen weights, held-out seeds): set 'Test every N episodes' in the Goal tab.")
        layout.addWidget(self.test_label)
        self.test_plot = pg.PlotWidget()
        self.test_plot.setLabel("bottom", "episode")
        self.test_plot.setLabel("left", "test win-rate %")
        self.test_plot.setYRange(0, 100)
        self.test_plot.addLegend()
        layout.addWidget(self.test_plot, 1)
        self._scores: dict[str, list] = {}
        self._tests: dict[str, list] = {}
        self._series: dict[str, list] = {}
        self._baseline: int | None = None
        self._scatters: list = []
        self._baseline_line = None

    # ---- data ---------------------------------------------------------

    def set_entries(self, entries: list[dict]) -> None:
        self._series, self._baseline = collect_series(entries)
        self._scores = collect_scores(entries)
        self._redraw()

    def set_tests(self, evals: list[dict]) -> None:
        self._tests = collect_tests(evals)
        self._redraw_tests()

    def tests(self) -> dict[str, list]:
        return self._tests

    def metric(self) -> str:
        return self.metric_combo.currentData()

    def series(self) -> dict[str, list]:
        return self._series

    def baseline(self) -> int | None:
        return self._baseline

    def _redraw(self) -> None:
        self.plot.clear()
        self.plot.plotItem.legend.clear()
        self._scatters = []
        score_mode = self.metric() == "score"
        self.plot.setLabel("left", self.metric())
        series = self._scores if score_mode else self._series
        if self._baseline is not None and not score_mode:
            self._baseline_line = pg.InfiniteLine(
                pos=self._baseline, angle=0, movable=False,
                pen=pg.mkPen((150, 150, 150), style=pg.QtCore.Qt.PenStyle.DashLine),
                label="baseline", labelOpts={"position": 0.95, "color": (150, 150, 150)})
            self.plot.addItem(self._baseline_line)
        for i, (label, points) in enumerate(sorted(series.items(), key=lambda kv: _order(kv[0]))):
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

    def _redraw_tests(self) -> None:
        self.test_plot.clear()
        self.test_plot.plotItem.legend.clear()
        latest = []
        for i, (label, points) in enumerate(sorted(self._tests.items(), key=lambda kv: _order(kv[0]))):
            color = _COLORS[i % len(_COLORS)]
            xs = [p[0] for p in points]
            self.test_plot.plot(xs, [p[1] for p in points], pen=pg.mkPen(color, width=2), symbol="o",
                                symbolBrush=color, symbolSize=6, name=label)
            latest.append(f"{label}: {points[-1][1]:.0f}% wins, mean test max_x {points[-1][2]:.0f}")
        self.test_label.setText("Test (frozen, held-out seeds), latest -- " + "; ".join(latest) if latest else
                                "Test win-rate (frozen weights, held-out seeds): set 'Test every N episodes' in the Goal tab.")

    def _on_clicked(self, _scatter, points, *_args) -> None:
        if len(points):
            self.point_selected.emit(int(points[0].data()))


def _order(label: str):
    if label == "real":
        return (0, 0)
    tail = label.rsplit(" ", 1)[-1]
    return (1, int(tail) if tail.isdigit() else 0)
