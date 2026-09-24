"""tool/ui/tabs/enemies.py -- tab 2: per-kind odour intensity, looming
salience, and danger weight for GOOMBA/KOOPA/ENEMY (C8a, tool/PLAN.md P6,
docs/SPEC_entity_perception.md). Reads/writes
projects/<name>/entity_profiles.json through tool/core/
entity_profiles_store.py; only takes effect on a run when the "Enable
per-kind entity profiles" checkbox is on (EntityProfileSettings.enabled --
ground rule 4, the file existing is not itself what turns this on).
"""

from __future__ import annotations

import dataclasses

from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QVBoxLayout, QWidget,
)

from mario.entities.kinds import EntityKind
from tool.core.entity_profiles_store import (
    load_merged, set_kind_field, set_kind_odour_intensity, set_kind_odour_sign,
)

# (EntityKind, display name) -- the kinds this tab edits; a live channel
# in bridge/perception.py's profiled_odor/profiled_enemy_thetas (SPEC
# section 6). QUESTION_BLOCK/POWERUP are tab 3's (objects.py); ENEMY is
# the generic non-Goomba/Koopa fallback, still live-editable.
LIVE_KINDS = [
    (EntityKind.GOOMBA, "Goomba"),
    (EntityKind.KOOPA, "Koopa"),
    (EntityKind.ENEMY, "Enemy (generic fallback)"),
]


class EnemiesTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        layout = QVBoxLayout(self)

        settings = window.get_tool_settings()
        self.enable_checkbox = QCheckBox("Enable per-kind entity profiles (C8a)")
        self.enable_checkbox.setChecked(settings.entity_profile.enabled)
        self.enable_checkbox.setToolTip(
            "Off (default): FullPolicy gets entity_profiles=None, byte-"
            "identical to before C8a existed. On: values below (and "
            "tab 3's) are read from projects/<name>/entity_profiles.json."
        )
        self.enable_checkbox.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self.enable_checkbox)

        profiles = load_merged(window.project.name)
        self._kind_boxes = []
        self._valence_checks: dict[EntityKind, QCheckBox] = {}
        for kind, label in LIVE_KINDS:
            box = self._kind_box(kind, label, profiles)
            box.setEnabled(settings.entity_profile.enabled)
            self._kind_boxes.append(box)
            layout.addWidget(box)

        layout.addStretch(1)

    def _kind_box(self, kind: EntityKind, label: str, profiles) -> QGroupBox:
        profile = profiles.get(kind)
        box = QGroupBox(label)
        form = QFormLayout(box)

        if profile.odours:
            intensity_spin = QDoubleSpinBox()
            intensity_spin.setRange(0.0, 10.0)
            intensity_spin.setSingleStep(0.1)
            intensity_spin.setValue(profile.odours[0].intensity)
            intensity_spin.valueChanged.connect(
                lambda value, k=kind: self._on_intensity_changed(k, value))
            form.addRow(f"Odour intensity ({profile.odours[0].channel})", intensity_spin)

            # tool/SPEC_ui_retro.md section 4: valence flip. Checked =
            # sign > 0 (attractive, routes into profiled_odor's food sum);
            # unchecked = sign < 0 (aversive, threat sum). A flipped kind's
            # danger_weight control above then does nothing for it (SPEC
            # section 1 only applies danger_weight to threat-signed
            # channels) -- said in the tooltip so it doesn't look like a bug.
            valence_check = QCheckBox("Smells good (attractive)")
            valence_check.setChecked(profile.odours[0].sign > 0)
            valence_check.setToolTip(
                "Off: smells bad -- routes into the threat sum, scaled by "
                "danger weight below. On: smells good -- routes into the "
                "food sum instead, and danger weight then does nothing "
                "for this kind. This is a science change when actually "
                "used (CLAUDE.md rule 3) -- give it its own recorded run."
            )
            valence_check.toggled.connect(
                lambda checked, k=kind: self._on_sign_changed(k, checked))
            form.addRow("Valence", valence_check)
            self._valence_checks[kind] = valence_check

        looming_spin = QDoubleSpinBox()
        looming_spin.setRange(0.0, 10.0)
        looming_spin.setSingleStep(0.1)
        looming_spin.setValue(profile.looming_salience)
        looming_spin.valueChanged.connect(
            lambda value, k=kind: self._on_field_changed(k, "looming_salience", value))
        form.addRow("Looming salience", looming_spin)

        danger_spin = QDoubleSpinBox()
        danger_spin.setRange(0.0, 10.0)
        danger_spin.setSingleStep(0.1)
        danger_spin.setValue(profile.danger_weight)
        danger_spin.setToolTip("Master knob: also scales looming salience above (SPEC section 1).")
        danger_spin.valueChanged.connect(
            lambda value, k=kind: self._on_field_changed(k, "danger_weight", value))
        form.addRow("Danger weight (master)", danger_spin)

        return box

    def _on_enable_toggled(self, checked: bool) -> None:
        settings = self._window.get_tool_settings()
        entity_profile = dataclasses.replace(settings.entity_profile, enabled=checked)
        self._window.set_tool_settings(dataclasses.replace(settings, entity_profile=entity_profile))
        for box in self._kind_boxes:
            box.setEnabled(checked)
        self._window.reload_tab("objects")

    def _on_field_changed(self, kind: EntityKind, field_name: str, value: float) -> None:
        # entity_profiles.json is written immediately, not staged behind
        # the header's Save button -- it's its own file, not part of
        # config.json/tool.json, so it doesn't participate in the
        # project's dirty/unsaved-changes tracking (same reason run
        # history/telemetry don't either).
        set_kind_field(self._window.project.name, kind.name, field_name, value)

    def _on_intensity_changed(self, kind: EntityKind, value: float) -> None:
        set_kind_odour_intensity(self._window.project.name, kind.name, 0, value)

    def _on_sign_changed(self, kind: EntityKind, checked: bool) -> None:
        set_kind_odour_sign(self._window.project.name, kind.name, 0, 1 if checked else -1)
