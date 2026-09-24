"""tool/ui/tabs/objects.py -- tab 3: per-kind odour intensity for
POWERUP/QUESTION_BLOCK (C8a, tool/PLAN.md P6,
docs/SPEC_entity_perception.md). GROUND/USED_BLOCK/SOLID_OTHER/PIT are
shown greyed: PIT has no live call site in FullPolicy.act()'s decision
loop yet (bridge/profiles/default.json's own note), and the terrain
kinds have no odours and unread looming/danger fields (SPEC section 6) --
editing them would be a control that lies (ground rule 4). Shares the
same "Enable per-kind entity profiles" toggle as tab 2 (enemies.py);
flipping it in either tab reloads both so they never show mismatched
checkbox state.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget,
)

from mario.entities.kinds import EntityKind
from tool.core.entity_profiles_store import load_merged, set_kind_odour_intensity

LIVE_KINDS = [
    (EntityKind.POWERUP, "Power-up (mushroom/flower/star/1-up)"),
    (EntityKind.QUESTION_BLOCK, "`?` block"),
]

GREYED_KINDS = [
    (EntityKind.GROUND, "Ground -- no odours, looming/danger unread"),
    (EntityKind.USED_BLOCK, "Used block -- no odours, looming/danger unread"),
    (EntityKind.SOLID_OTHER, "Bricks/pipes/other solid -- no odours, looming/danger unread"),
    (EntityKind.PIT, "Pit -- not yet a call site in the decision loop"),
]


class ObjectsTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        layout = QVBoxLayout(self)

        settings = window.get_tool_settings()
        self.enable_checkbox = QCheckBox("Enable per-kind entity profiles (C8a)")
        self.enable_checkbox.setChecked(settings.entity_profile.enabled)
        self.enable_checkbox.setToolTip("Same setting as tab 2's checkbox -- one toggle for both tabs.")
        self.enable_checkbox.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self.enable_checkbox)

        profiles = load_merged(window.project.name)
        self._kind_boxes = []
        for kind, label in LIVE_KINDS:
            box = self._kind_box(kind, label, profiles)
            box.setEnabled(settings.entity_profile.enabled)
            self._kind_boxes.append(box)
            layout.addWidget(box)

        for kind, reason in GREYED_KINDS:
            box = QGroupBox(kind.name.replace("_", " ").title())
            box_layout = QVBoxLayout(box)
            note = QLabel(reason)
            note.setWordWrap(True)
            note.setEnabled(False)
            box_layout.addWidget(note)
            box.setEnabled(False)
            layout.addWidget(box)

        layout.addStretch(1)

    def _kind_box(self, kind: EntityKind, label: str, profiles) -> QGroupBox:
        profile = profiles.get(kind)
        box = QGroupBox(label)
        form = QFormLayout(box)
        intensity_spin = QDoubleSpinBox()
        intensity_spin.setRange(0.0, 10.0)
        intensity_spin.setSingleStep(0.1)
        intensity_spin.setValue(profile.odours[0].intensity)
        intensity_spin.valueChanged.connect(
            lambda value, k=kind: self._on_intensity_changed(k, value))
        form.addRow(f"Odour intensity ({profile.odours[0].channel})", intensity_spin)
        return box

    def _on_enable_toggled(self, checked: bool) -> None:
        settings = self._window.get_tool_settings()
        entity_profile = dataclasses.replace(settings.entity_profile, enabled=checked)
        self._window.set_tool_settings(dataclasses.replace(settings, entity_profile=entity_profile))
        for box in self._kind_boxes:
            box.setEnabled(checked)
        self._window.reload_tab("enemies")

    def _on_intensity_changed(self, kind: EntityKind, value: float) -> None:
        set_kind_odour_intensity(self._window.project.name, kind.name, 0, value)
