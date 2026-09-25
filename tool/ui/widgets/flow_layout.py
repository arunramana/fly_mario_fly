"""tool/ui/widgets/flow_layout.py -- a responsive, wrapping grid: lays
widgets left-to-right, wrapping to a new row when the current one runs
out of horizontal space, and re-wrapping live as the window resizes.
Qt has no built-in equivalent (QGridLayout's column count is fixed at
construction) -- this is the standard "Flow Layout" pattern from Qt's own
C++ examples, ported to PySide6. Used by the card grids (character,
entity, circuit tabs) so they stay a real responsive grid rather than a
fixed-column layout that wastes space or clips at some window sizes.
"""

from __future__ import annotations

from PySide6.QtCore import QMargins, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin: int = 0, spacing: int = 8):
        super().__init__(parent)
        if margin >= 0:
            self.setContentsMargins(QMargins(margin, margin, margin, margin))
        self.setSpacing(spacing)
        self._items: list = []

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(left, top, -right, -bottom)
        x, y = effective_rect.x(), effective_rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._items:
            widget = item.widget()
            style = widget.style() if widget else None
            space_x = spacing
            space_y = spacing
            if style is not None:
                space_x += style.layoutSpacing(
                    QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton,
                    Qt.Orientation.Horizontal)
                space_y += style.layoutSpacing(
                    QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton,
                    Qt.Orientation.Vertical)
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()
