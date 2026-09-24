"""tool/ui/gate.py -- the project gate: new / duplicate / open / recent.
Cannot be skipped (tool/PLAN.md section 1) -- app.py always shows this
before the main window.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox,
    QPushButton, QVBoxLayout,
)

from tool.core.project import ToolProject


class ProjectGateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("fly_mario -- open a project")
        self.resize(420, 360)
        self.selected_project: ToolProject | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Recent projects:"))
        self.recent_list = QListWidget()
        self.recent_list.addItems(ToolProject.list_recent())
        self.recent_list.itemDoubleClicked.connect(self._open_selected)
        layout.addWidget(self.recent_list)

        buttons = QHBoxLayout()
        new_btn = QPushButton("New project")
        new_btn.clicked.connect(self._new_project)
        dup_btn = QPushButton("Duplicate legacy")
        dup_btn.clicked.connect(self._duplicate_legacy)
        open_btn = QPushButton("Open selected")
        open_btn.clicked.connect(self._open_selected)
        buttons.addWidget(new_btn)
        buttons.addWidget(dup_btn)
        buttons.addWidget(open_btn)
        layout.addLayout(buttons)

    def _refresh(self) -> None:
        self.recent_list.clear()
        self.recent_list.addItems(ToolProject.list_recent())

    def _new_project(self) -> None:
        name, ok = QInputDialog.getText(self, "New project", "Project name:")
        if not ok or not name:
            return
        try:
            self.selected_project = ToolProject.create(name)
        except FileExistsError as exc:
            QMessageBox.warning(self, "Project exists", str(exc))
            return
        self.accept()

    def _duplicate_legacy(self) -> None:
        name, ok = QInputDialog.getText(self, "Duplicate legacy", "New project name:")
        if not ok or not name:
            return
        try:
            legacy = ToolProject.open("legacy")
            self.selected_project = legacy.duplicate(name)
        except Exception as exc:
            QMessageBox.warning(self, "Could not duplicate", str(exc))
            return
        self.accept()

    def _open_selected(self) -> None:
        item = self.recent_list.currentItem()
        if item is None:
            QMessageBox.information(self, "No selection", "Select a project first.")
            return
        try:
            self.selected_project = ToolProject.open(item.text())
        except Exception as exc:
            QMessageBox.warning(self, "Could not open", str(exc))
            return
        self.accept()
