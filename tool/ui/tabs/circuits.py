"""tool/ui/tabs/circuits.py -- tab 4: every scalar in config/params.py
(ParamForm, from schema.py), noise sigma + seed, and the shuffled-
connectome toggle (C5).
"""

from __future__ import annotations

import dataclasses

from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QGroupBox, QSpinBox, QVBoxLayout, QWidget,
)

from config.project_config import from_dict as config_from_dict
from tool.ui.widgets.param_form import ParamForm
from tool.ui.widgets.preset_bar import PresetBar


class CircuitsTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        layout = QVBoxLayout(self)

        layout.addWidget(PresetBar("circuits", self._preset_data, self._apply_preset))

        shuffle_box = QGroupBox("Shuffled connectome (CLAUDE.md invariant 6)")
        shuffle_form = QFormLayout(shuffle_box)
        settings = window.get_tool_settings()
        current_seed = settings.circuits.shuffle_seed
        self.shuffle_checkbox = QCheckBox("Shuffle edges (same neurons, same degree, random wiring)")
        self.shuffle_checkbox.setChecked(current_seed is not None)
        self.shuffle_checkbox.toggled.connect(self._on_shuffle_toggled)
        shuffle_form.addRow(self.shuffle_checkbox)
        self.shuffle_seed_spin = QSpinBox()
        self.shuffle_seed_spin.setRange(0, 2_000_000_000)
        self.shuffle_seed_spin.setValue(current_seed or 0)
        self.shuffle_seed_spin.setEnabled(current_seed is not None)
        self.shuffle_seed_spin.valueChanged.connect(self._on_shuffle_seed_changed)
        shuffle_form.addRow("Shuffle seed", self.shuffle_seed_spin)
        layout.addWidget(shuffle_box)

        self.param_form = ParamForm(window.get_config())
        self.param_form.changed.connect(self._on_config_changed)
        layout.addWidget(self.param_form)

    def _on_shuffle_toggled(self, checked: bool) -> None:
        self.shuffle_seed_spin.setEnabled(checked)
        seed = self.shuffle_seed_spin.value() if checked else None
        settings = self._window.get_tool_settings()
        circuits = dataclasses.replace(settings.circuits, shuffle_seed=seed)
        self._window.set_tool_settings(dataclasses.replace(settings, circuits=circuits))

    def _on_shuffle_seed_changed(self, value: int) -> None:
        if not self.shuffle_checkbox.isChecked():
            return
        settings = self._window.get_tool_settings()
        circuits = dataclasses.replace(settings.circuits, shuffle_seed=value)
        self._window.set_tool_settings(dataclasses.replace(settings, circuits=circuits))

    def _on_config_changed(self, config) -> None:
        self._window.set_config(config)

    def _preset_data(self) -> dict:
        return {
            "config": self._window.get_config().to_dict(),
            "shuffle_seed": self._window.get_tool_settings().circuits.shuffle_seed,
        }

    def _apply_preset(self, data: dict) -> None:
        self._window.set_config(config_from_dict(data["config"]))
        settings = self._window.get_tool_settings()
        circuits = dataclasses.replace(settings.circuits, shuffle_seed=data["shuffle_seed"])
        self._window.set_tool_settings(dataclasses.replace(settings, circuits=circuits))
        self._window.reload_tab("circuits")
