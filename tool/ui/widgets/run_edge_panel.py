"""tool/ui/widgets/run_edge_panel.py -- the Player tab's Brain map / Data /
Config panels. Children of the video canvas, positioned by absolute
geometry (never in a layout), so opening or closing one can't move or
resize the video. Each collapses to a thin labelled tab on its edge and
expands when clicked; open/closed is remembered through QSettings (a
local per-machine preference, injectable for tests).
"""

from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

_SETTINGS = QSettings("fly_mario", "run_tab_edge_panels")

DEFAULT_WIDTH_FRACTION = 0.15   # of the video canvas's width
WIDTH_FRACTION_RANGE = (0.10, 0.45)
MIN_WIDTH_EM = 10               # never narrower than this many line heights of the current font


class EdgePanel(QWidget):
    toggled = Signal(bool)

    def __init__(self, key: str, title: str, content: QWidget, size: QSize,
                 parent=None, settings: QSettings | None = None):
        super().__init__(parent)
        self.setObjectName("edgePanel")
        self._key = key
        self._settings = settings if settings is not None else _SETTINGS
        self._open = self._settings.value(f"{key}/open", True, type=bool)
        # Width is remembered as a share of the canvas, so the same preference is right on a
        # 1280px laptop window and a 1920px monitor (a saved pixel width would not be).
        self._width_fraction = self._clamp_fraction(
            self._settings.value(f"{key}/width_fraction", DEFAULT_WIDTH_FRACTION, type=float))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.tab = QPushButton(title)
        self.tab.setObjectName("edgePanelTab")
        self.tab.clicked.connect(self.toggle)
        layout.addWidget(self.tab)
        self.content = content
        content.setFixedSize(size)
        layout.addWidget(content)
        content.setVisible(self._open)
        self.adjustSize()

    @staticmethod
    def _clamp_fraction(fraction: float) -> float:
        lo, hi = WIDTH_FRACTION_RANGE
        return min(hi, max(lo, fraction))

    def width_fraction(self) -> float:
        return self._width_fraction

    def set_width_fraction(self, fraction: float) -> None:
        self._width_fraction = self._clamp_fraction(fraction)
        self._settings.setValue(f"{self._key}/width_fraction", self._width_fraction)

    def min_width_for(self, canvas_width: int) -> int:
        return max(int(canvas_width * self._width_fraction), MIN_WIDTH_EM * self.fontMetrics().height())

    def is_open(self) -> bool:
        return self._open

    def toggle(self) -> None:
        self.set_open(not self._open)

    def set_open(self, open_: bool) -> None:
        self._open = open_
        self._settings.setValue(f"{self._key}/open", open_)
        self.content.setVisible(open_)
        self.adjustSize()
        self.toggled.emit(open_)
