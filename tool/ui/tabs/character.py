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
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QSplitter, QToolButton,
    QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from config.params import ArousalParams
from tool.core.tool_settings import CharacterSettings
from tool.ui.widgets.asset_image import load_asset
from tool.ui.widgets.card_button import make_card_button
from tool.ui.widgets.flow_layout import FlowLayout
from tool.ui.widgets.no_scroll_inputs import NoScrollSlider
from tool.ui.widgets.scroll_page import install_scroll_page

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
        install_scroll_page(self, outer)

        card_area = QWidget()
        # A FlowLayout's own sizeHint() collapses to one card's width (it
        # has no notion of "how many columns would look good"), which a
        # QSplitter reads literally and shrinks this pane to fit -- an
        # explicit minimum width is what actually gets the splitter to
        # give the grid room to wrap past a single column.
        card_area.setMinimumWidth(CARD_ICON_PX + 40)   # one card; the FlowLayout wraps the rest
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

        # docs/SPEC_arousal_pc1.md: a steady drive into the pC1 arousal neurons.
        # Above 0 it switches the Arousal module on (Circuits tab); it is also
        # sent live to a run in progress (MainWindow.set_arousal_live).
        self.arousal_slider = NoScrollSlider(Qt.Orientation.Horizontal)
        self.arousal_slider.setRange(0, 100)
        arousal = window.get_config().modules.arousal
        self.arousal_slider.setValue(int(round((arousal.arousal if arousal else 0.0) * 100)))
        self.arousal_slider.setToolTip(
            "Arousal (pC1), 0-100%. pC1 activity = arousal x arousal_max_h (Circuits tab, default 10), "
            "delivered to DNp09, DNa01/02, MDN, pIP1 ... through pC1's real synapses (share of the "
            "target's total input). 0 = off: the run is unchanged. Live: moving it during a run applies "
            "immediately. docs/SPEC_arousal_pc1.md")
        self.arousal_label = QLabel(f"{self.arousal_slider.value()}%")
        self.arousal_slider.valueChanged.connect(self._on_arousal_changed)
        window.config_changed.connect(self._sync_arousal)
        row = QHBoxLayout()
        row.addWidget(self.arousal_slider, 1)
        row.addWidget(self.arousal_label)
        state_form.addRow("Arousal (pC1)", row)
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

    def _on_arousal_changed(self, value: int) -> None:
        level = value / 100.0
        self.arousal_label.setText(f"{value}%")
        config = self._window.get_config()
        current = config.modules.arousal
        if current is None and level == 0.0:
            return
        params = dataclasses.replace(current or ArousalParams(), arousal=level)
        self._window.set_config(dataclasses.replace(
            config, modules=dataclasses.replace(config.modules, arousal=params)))
        self._window.set_arousal_live(level)

    def _sync_arousal(self, config) -> None:
        """Keep the slider in step with the config (Circuits edits, presets)."""
        arousal = config.modules.arousal
        value = int(round((arousal.arousal if arousal else 0.0) * 100))
        if value != self.arousal_slider.value():
            self.arousal_slider.blockSignals(True)
            self.arousal_slider.setValue(value)
            self.arousal_slider.blockSignals(False)
            self.arousal_label.setText(f"{value}%")

    def _on_powerup_changed(self, checked: bool) -> None:
        settings = self._window.get_tool_settings()
        character = dataclasses.replace(settings.character, starting_powerup=checked)
        self._window.set_tool_settings(dataclasses.replace(settings, character=character))
