"""tool/ui/tabs/character.py -- tab 1: Mario/Luigi (live, tool/core/
palette.py, display-only), hunger override and starting power-up (live,
C7 -- tool/CODEBASE_CHANGES.md), arousal pC1 (not wired, C9, no SPEC yet).
"""

from __future__ import annotations

import dataclasses

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel, QRadioButton,
    QSlider, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from tool.core.tool_settings import CharacterSettings
from tool.ui.widgets.preset_bar import PresetBar


class CharacterTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        layout = QVBoxLayout(self)

        layout.addWidget(PresetBar("character", self._preset_data, self._apply_preset))

        player_box = QGroupBox("Character")
        player_form = QFormLayout(player_box)
        self.mario_radio = QRadioButton("Mario")
        self.luigi_radio = QRadioButton("Luigi (display-only colour swap)")
        settings = window.get_tool_settings()
        (self.mario_radio if settings.character.player == "mario" else self.luigi_radio).setChecked(True)
        self.mario_radio.toggled.connect(self._on_player_changed)
        player_form.addRow(self.mario_radio)
        player_form.addRow(self.luigi_radio)
        layout.addWidget(player_box)

        state_box = QGroupBox("Internal state (C7 -- a science change when used)")
        state_form = QFormLayout(state_box)
        self.hunger_combo = QComboBox()
        self.hunger_combo.addItems(["Read from Mario's size (default)", "Force hungry", "Force sated"])
        self.hunger_combo.setCurrentIndex(self._hunger_index(settings.character.hunger_override))
        self.hunger_combo.currentIndexChanged.connect(self._on_hunger_changed)
        state_form.addRow("Hunger", self.hunger_combo)

        self.powerup_checkbox = QCheckBox("Start big (force_mario_size=1 from frame 0)")
        self.powerup_checkbox.setChecked(settings.character.starting_powerup)
        self.powerup_checkbox.toggled.connect(self._on_powerup_changed)
        state_form.addRow("Starting power-up", self.powerup_checkbox)
        layout.addWidget(state_box)

        arousal_box = QGroupBox("Arousal (not wired -- C9, no SPEC yet)")
        arousal_form = QFormLayout(arousal_box)
        arousal_slider = QSlider(Qt.Orientation.Horizontal)
        arousal_slider.setEnabled(False)
        arousal_slider.setToolTip("not wired yet (C9)")
        arousal_form.addRow("pC1", arousal_slider)
        layout.addWidget(arousal_box)

        layout.addStretch(1)

    def _preset_data(self) -> dict:
        return dataclasses.asdict(self._window.get_tool_settings().character)

    def _apply_preset(self, data: dict) -> None:
        settings = self._window.get_tool_settings()
        self._window.set_tool_settings(
            dataclasses.replace(settings, character=CharacterSettings(**data))
        )
        self._window.reload_tab("character")

    @staticmethod
    def _hunger_index(value: bool | None) -> int:
        if value is None:
            return 0
        return 1 if value else 2

    def _on_player_changed(self) -> None:
        player = "mario" if self.mario_radio.isChecked() else "luigi"
        settings = self._window.get_tool_settings()
        character = dataclasses.replace(settings.character, player=player)
        self._window.set_tool_settings(dataclasses.replace(settings, character=character))
        self._window.on_player_changed(player)

    def _on_hunger_changed(self, index: int) -> None:
        override = {0: None, 1: True, 2: False}[index]
        settings = self._window.get_tool_settings()
        character = dataclasses.replace(settings.character, hunger_override=override)
        self._window.set_tool_settings(dataclasses.replace(settings, character=character))

    def _on_powerup_changed(self, checked: bool) -> None:
        settings = self._window.get_tool_settings()
        character = dataclasses.replace(settings.character, starting_powerup=checked)
        self._window.set_tool_settings(dataclasses.replace(settings, character=character))
