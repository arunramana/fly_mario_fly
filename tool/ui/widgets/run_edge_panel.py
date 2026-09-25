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


class EdgePanel(QWidget):
    toggled = Signal(bool)

    def __init__(self, key: str, title: str, content: QWidget, size: QSize,
                 parent=None, settings: QSettings | None = None):
        super().__init__(parent)
        self.setObjectName("edgePanel")
        self._key = key
        self._settings = settings if settings is not None else _SETTINGS
        self._open = self._settings.value(f"{key}/open", True, type=bool)

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
