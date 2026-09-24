"""tool/ui/tabs/character.py -- tab 1: Mario/Luigi picture cards
(tool/SPEC_ui_retro.md section 6; display-only recolour,
tool/core/palette.py), hunger override and starting power-up (live,
C7 -- tool/CODEBASE_CHANGES.md), arousal pC1 (not wired, C9, no SPEC yet)
in the selected card's own panel below.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)
from PySide6.QtCore import QSize, Qt

from tool.core.tool_settings import CharacterSettings
from tool.ui.widgets.asset_image import load_asset
from tool.ui.widgets.preset_bar import PresetBar

CARD_ICON_PX = 96
PLAYERS = [("mario", "Mario", "mario_card"), ("luigi", "Luigi (display-only colour swap)", "luigi_card")]


class CharacterTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        layout = QVBoxLayout(self)

        layout.addWidget(PresetBar("character", self._preset_data, self._apply_preset))

        settings = window.get_tool_settings()

        player_box = QGroupBox("Character")
        card_row = QHBoxLayout()
        self._player_buttons: dict[str, QPushButton] = {}
        for player_id, label, asset_id in PLAYERS:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setIcon(load_asset(asset_id))
            button.setIconSize(QSize(CARD_ICON_PX, CARD_ICON_PX))
            button.setChecked(settings.character.player == player_id)
            button.clicked.connect(lambda _checked, p=player_id: self._on_player_changed(p))
            card_row.addWidget(button)
            self._player_buttons[player_id] = button
        card_row.addStretch(1)
        player_box.setLayout(card_row)
        layout.addWidget(player_box)

        # The selected card's own panel (tool/SPEC_ui_retro.md section 6):
        # one shared control set, not duplicated per player -- both cards
        # read/write the same settings.character fields regardless of
        # which one is currently selected.
        state_box = QGroupBox("Selected character's internal state (C7 -- a science change when used)")
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

        arousal_slider = QSlider(Qt.Orientation.Horizontal)
        arousal_slider.setEnabled(False)
        arousal_slider.setToolTip("not wired yet (C9)")
        state_form.addRow("Arousal pC1 (not wired -- C9, no SPEC yet)", arousal_slider)
        layout.addWidget(state_box)

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

    def _on_player_changed(self, player: str) -> None:
        for player_id, button in self._player_buttons.items():
            button.setChecked(player_id == player)
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
