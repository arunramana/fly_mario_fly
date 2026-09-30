"""tool/ui/duplicate_dialog.py -- "Duplicate project...": pick any existing
project (the read-only reference ones included, default the one given or the
most recently changed) and a new name. Shared by the project gate and the main
window's header menu; the caller does the actual ToolProject.duplicate.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
)

from tool.core.project import ToolProject


class DuplicateProjectDialog(QDialog):
    def __init__(self, parent=None, default_source: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Duplicate project")
        names = ToolProject.list_by_recency()   # most recently changed first
        self.source_combo = QComboBox()
        for name in names:
            suffix = "  (read-only reference)" if name in _read_only() else ""
            self.source_combo.addItem(name + suffix, name)
        if default_source in names:
            self.source_combo.setCurrentIndex(names.index(default_source))
        self.name_edit = QLineEdit()
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Duplicate", self.source_combo)
        form.addRow("New name", self.name_edit)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(self.buttons)
        self.name_edit.textChanged.connect(self._validate)
        self._validate()

    def _validate(self) -> None:
        text = self.name_edit.text().strip()
        error = ToolProject.name_error(text) if text else "Enter a name for the copy."
        self.error_label.setText(error or "")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(error is None and self.source_combo.count() > 0)

    def source(self) -> str:
        return self.source_combo.currentData()

    def new_name(self) -> str:
        return self.name_edit.text().strip()


def _read_only():
    from tool.core.project import READ_ONLY_PROJECT_NAMES
    return READ_ONLY_PROJECT_NAMES
