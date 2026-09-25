"""tool/ui/widgets/collapsible_drawer.py -- ease-of-use redesign: a
titled panel that collapses to just its header, used for the Run tab's
left (run browser) and right (Plots/Data/Config) drawers. Remembers
whether it's open and how wide through plain get/set methods -- the
owning tab persists those into ToolSettings (tool.core.tool_settings.
RunTabUIState) so they survive a restart.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QSizePolicy, QVBoxLayout, QWidget


class CollapsibleDrawer(QWidget):
    toggled = Signal(bool)

    def __init__(self, title: str, content: QWidget, parent=None,
                 open: bool = True, width: int = 260):
        super().__init__(parent)
        self._content = content
        self._width = width
        # Our own explicit flag, not content.isVisible() -- a widget
        # never shown on screen (e.g. under test, no qtbot .show()) always
        # reports isVisible() == False regardless of setVisible(), since
        # Qt visibility also depends on the whole ancestor chain being
        # shown, not just this widget's own state.
        self._open = open

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._toggle_button = QPushButton()
        self._toggle_button.setCheckable(True)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        layout.addWidget(self._toggle_button)
        layout.addWidget(content)

        self._title = title
        self.set_open(open)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setFixedWidth(self._width if open else self._toggle_button.sizeHint().width())

    def _on_toggle_clicked(self) -> None:
        self.set_open(not self.is_open())

    def is_open(self) -> bool:
        return self._open

    def set_open(self, open: bool) -> None:
        self._open = open
        self._content.setVisible(open)
        self._toggle_button.setChecked(open)
        self._toggle_button.setText(f"{'v' if open else '>'} {self._title}")
        self.setFixedWidth(self._width if open else self._toggle_button.sizeHint().width() + 8)
        self.toggled.emit(open)

    def width_when_open(self) -> int:
        return self._width

    def set_width_when_open(self, width: int) -> None:
        self._width = width
        if self.is_open():
            self.setFixedWidth(width)
