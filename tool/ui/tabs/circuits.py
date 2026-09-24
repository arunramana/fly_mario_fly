"""tool/ui/tabs/circuits.py -- tab 4: a card per circuit (jump/steering/
speed/takeoff/MDN/mushroom body), each showing a real brain-map image
(render.brain_panel.highlight_populations) plus a one-line description;
clicking a card reveals just that circuit's own config/params.py group(s)
in the (single, eagerly-built) ParamForm below (tool/SPEC_ui_retro.md
sections 8/10). Noise sigma + seed, and the shuffled-connectome toggle
(C5) stay above the grid -- cross-cutting, not part of any one circuit.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from config.project_config import from_dict as config_from_dict
from tool.core.circuit_manifest import CIRCUIT_REGISTRY, OTHER_ENTRY
from tool.ui.widgets.circuit_card_image import circuit_card_pixmap
from tool.ui.widgets.param_form import ParamForm
from tool.ui.widgets.preset_bar import PresetBar

CARD_ICON_PX = 64


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

        # tool/SPEC_ui_retro.md section 3, "one home per setting": ONE
        # ParamForm, covering every group -- so _widget_by_path still has
        # every scalar (noise.sigma among them) no matter which card is
        # selected. The card grid below only toggles which group boxes
        # are VISIBLE (ParamForm.show_only_groups), it never builds a
        # second form -- there is still exactly one writable widget per
        # scalar.
        self.param_form = ParamForm(window.get_config())
        self.param_form.changed.connect(self._on_config_changed)

        card_row = QHBoxLayout()
        self._circuit_buttons: dict[str, QPushButton] = {}
        self._entries_by_id = {e.circuit_id: e for e in (*CIRCUIT_REGISTRY, OTHER_ENTRY)}
        for entry in self._entries_by_id.values():
            button = QPushButton(entry.display_name)
            button.setCheckable(True)
            button.setIcon(circuit_card_pixmap(entry))
            button.setIconSize(QSize(CARD_ICON_PX, CARD_ICON_PX))
            button.setToolTip(entry.description)
            button.clicked.connect(lambda _checked, cid=entry.circuit_id: self._select_circuit(cid))
            card_row.addWidget(button)
            self._circuit_buttons[entry.circuit_id] = button
        card_row.addStretch(1)
        layout.addLayout(card_row)

        self._description_label = QLabel()
        self._description_label.setWordWrap(True)
        layout.addWidget(self._description_label)

        layout.addWidget(self.param_form)
        self._select_circuit(CIRCUIT_REGISTRY[0].circuit_id)

    def _select_circuit(self, circuit_id: str) -> None:
        for cid, button in self._circuit_buttons.items():
            button.setChecked(cid == circuit_id)
        entry = self._entries_by_id[circuit_id]
        self._description_label.setText(
            f"{entry.description}"
            + (f"  See {entry.spec_path}." if entry.spec_path else "")
        )
        self.param_form.show_only_groups(set(entry.groups))

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
