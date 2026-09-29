"""tool/ui/widgets/collapsible_section.py -- a titled section whose body folds away
(header button with an arrow, e.g. "Control rules (0/11 on)"). The title carries
a count badge set by the caller through set_title()."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QToolButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    def __init__(self, title: str, parent=None, expanded: bool = True):
        super().__init__(parent)
        self._title = title
        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.toggle.setStyleSheet("QToolButton { border: none; font-weight: bold; text-align: left; }")
        self.toggle.toggled.connect(self._on_toggled)
        self.body = QFrame()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(16, 0, 0, 4)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(self.body)
        self._on_toggled(expanded)

    def set_title(self, title: str) -> None:
        self._title = title
        self.toggle.setText(("▼ " if self.toggle.isChecked() else "▶ ") + title)

    def add_widget(self, widget: QWidget) -> None:
        self.body_layout.addWidget(widget)

    def _on_toggled(self, expanded: bool) -> None:
        self.body.setVisible(expanded)
        self.set_title(self._title)
