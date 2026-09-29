"""tool/ui/widgets/reflow_grid.py -- a card grid whose column count follows its width.

QGridLayout fixes its columns at construction; on a laptop three 200px cards
plus an inspector don't fit, on a big monitor they leave dead space. This
re-places the same widgets into as many columns as currently fit, so the grid
reflows on every resize. (FlowLayout does the same for the character/entity
tabs; this keeps QGridLayout's equal-width columns, which the circuit cards
want.)
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QGridLayout, QLayout, QVBoxLayout, QWidget


class ReflowGrid(QWidget):
    def __init__(self, cell_width: int, spacing: int = 10, parent=None):
        super().__init__(parent)
        self._cell_width = cell_width
        self._spacing = spacing
        self._items: list[QWidget] = []
        self._columns = 0
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        # Without this the layout pins the widget's minimum to the *current* column count's width,
        # so the grid could never narrow enough to reflow to fewer columns.
        root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self._grid = QGridLayout()
        self._grid.setSpacing(spacing)
        root.addLayout(self._grid)
        root.addStretch(1)   # cards stay top-aligned however tall the tab is

    def add(self, widget: QWidget) -> None:
        self._items.append(widget)
        self._reflow(force=True)

    def columns_for(self, width: int) -> int:
        return max(1, (width + self._spacing) // (self._cell_width + self._spacing))

    @property
    def columns(self) -> int:
        return self._columns

    def minimumSizeHint(self) -> QSize:
        # One card, not the current column count's worth: otherwise the grid's own
        # minimum would stop the window ever getting narrow enough to reflow.
        hint = super().minimumSizeHint()
        return QSize(self._cell_width, hint.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow()

    def _reflow(self, force: bool = False) -> None:
        columns = self.columns_for(self.width())
        if columns == self._columns and not force:
            return
        self._columns = columns
        for widget in self._items:
            self._grid.removeWidget(widget)
        for i, widget in enumerate(self._items):
            self._grid.addWidget(widget, i // columns, i % columns)
