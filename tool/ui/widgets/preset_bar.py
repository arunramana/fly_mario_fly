"""tool/ui/widgets/preset_bar.py -- one save/load row, reused by every tab
that wants presets (tool/PLAN.md P7). A tab hands it `get_data`/`set_data`
closures over its own slice of project state; this widget never looks
inside that dict, so it works the same for CharacterSettings, a whole
ProjectConfig, or a mix of both.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QWidget,
)

from tool.core.presets import list_presets, load_preset, save_preset


class PresetBar(QWidget):
    def __init__(self, tab_key: str, get_data, set_data, parent=None):
        """get_data() -> dict: this tab's own current, JSON-safe state.
        set_data(dict) -> None: applies a loaded preset back (and refreshes
        whatever UI needs to reflect it -- the tab's own job, not this
        widget's)."""
        super().__init__(parent)
        self._tab_key = tab_key
        self._get_data = get_data
        self._set_data = set_data

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.combo = QComboBox()
        self.combo.setEditable(False)
        self._refresh_combo()
        layout.addWidget(self.combo, 1)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("preset name")
        layout.addWidget(self.name_edit, 1)

        save_button = QPushButton("Save preset")
        save_button.clicked.connect(self._on_save)
        layout.addWidget(save_button)

        load_button = QPushButton("Load preset")
        load_button.clicked.connect(self._on_load)
        layout.addWidget(load_button)

    def _refresh_combo(self) -> None:
        current = self.combo.currentText()
        self.combo.clear()
        self.combo.addItems(list_presets(self._tab_key))
        index = self.combo.findText(current)
        if index >= 0:
            self.combo.setCurrentIndex(index)

    def _on_save(self) -> None:
        name = self.name_edit.text().strip() or self.combo.currentText().strip()
        if not name:
            QMessageBox.warning(self, "No name", "Type a name to save this preset as.")
            return
        save_preset(self._tab_key, name, self._get_data())
        self.name_edit.clear()
        self._refresh_combo()
        index = self.combo.findText(name)
        if index >= 0:
            self.combo.setCurrentIndex(index)

    def _on_load(self) -> None:
        name = self.combo.currentText()
        if not name:
            return
        self._set_data(load_preset(self._tab_key, name))
