"""tool/ui/tabs/character.py -- tab 1: Mario/Luigi picture cards
(tool/SPEC_ui_retro.md section 6; display-only recolour,
tool/core/palette.py), hunger override and starting power-up (live,
C7 -- tool/CODEBASE_CHANGES.md), arousal pC1 (not wired, C9, no SPEC yet)
in an inspector panel to the right of the cards (ease-of-use redesign --
was full-width rows below them). Presets for this tab live in the
header's Presets menu (main_window.py), not a per-tab bar.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QSplitter, QToolButton,
    QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from tool.core.tool_settings import CharacterSettings
from tool.ui.widgets.asset_image import load_asset
from tool.ui.widgets.card_button import make_card_button
from tool.ui.widgets.flow_layout import FlowLayout
from tool.ui.widgets.no_scroll_inputs import NoScrollSlider

CARD_ICON_PX = 96
# Short button text (fits the card); the fuller description is the
# tooltip -- "Luigi (display-only colour swap)" as a button LABEL
# doesn't fit a card this width and was clipping (ease-of-use redesign).
PLAYERS = [("mario", "Mario", "mario_card", "Mario"),
           ("luigi", "Luigi", "luigi_card", "Luigi (display-only colour swap)")]


class CharacterTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        settings = window.get_tool_settings()

        outer = QSplitter(Qt.Orientation.Horizontal, self)
        QVBoxLayout(self).addWidget(outer)

        card_area = QWidget()
        # A FlowLayout's own sizeHint() collapses to one card's width (it
        # has no notion of "how many columns would look good"), which a
        # QSplitter reads literally and shrinks this pane to fit -- an
        # explicit minimum width is what actually gets the splitter to
        # give the grid room to wrap past a single column.
        card_area.setMinimumWidth(3 * (CARD_ICON_PX + 40))
        card_flow = FlowLayout(card_area, spacing=10)
        self._player_buttons: dict[str, QToolButton] = {}
        for player_id, label, asset_id, tooltip in PLAYERS:
            button = make_card_button(label, load_asset(asset_id), CARD_ICON_PX, tooltip)
            button.setAutoExclusive(True)
            button.setChecked(settings.character.player == player_id)
            button.clicked.connect(lambda _checked, p=player_id: self._on_player_changed(p))
            card_flow.addWidget(button)
            self._player_buttons[player_id] = button
        outer.addWidget(card_area)

        # The inspector panel (tool/SPEC_ui_retro.md section 6, ease-of-
        # use redesign): one shared control set, not duplicated per
        # player -- both cards read/write the same settings.character
        # fields regardless of which one is currently selected.
        inspector = QWidget()
        state_form = QFormLayout(inspector)
        self.hunger_combo = QComboBox()
        self.hunger_combo.addItems(["Read from Mario's size (default)", "Force hungry", "Force sated"])
        self.hunger_combo.setCurrentIndex(self._hunger_index(settings.character.hunger_override))
        self.hunger_combo.currentIndexChanged.connect(self._on_hunger_changed)
        state_form.addRow("Hunger", self.hunger_combo)

        self.powerup_checkbox = QCheckBox("Start big (force_mario_size=1 from frame 0)")
        self.powerup_checkbox.setChecked(settings.character.starting_powerup)
        self.powerup_checkbox.toggled.connect(self._on_powerup_changed)
        state_form.addRow("Starting power-up", self.powerup_checkbox)

        arousal_slider = NoScrollSlider(Qt.Orientation.Horizontal)
        arousal_slider.setEnabled(False)
        arousal_slider.setToolTip("not wired yet (C9)")
        state_form.addRow("Arousal pC1 (not wired -- C9, no SPEC yet)", arousal_slider)
        outer.addWidget(inspector)
        outer.setStretchFactor(0, 3)
        outer.setStretchFactor(1, 2)
        # QSplitter's stretch factor only governs how EXTRA space is
        # divided on resize, not the initial split -- without this, Qt's
        # default initial sizing left the card side too narrow for the
        # FlowLayout to ever show more than one card per row.
        outer.setSizes([700, 400])

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
