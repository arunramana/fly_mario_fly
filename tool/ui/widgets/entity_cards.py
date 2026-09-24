"""tool/ui/widgets/entity_cards.py -- tool/SPEC_ui_retro.md sections 7/10:
one picture-card grid + detail panel widget, generic over any list of
tool.core.entity_registry.EntityKindEntry -- enemies.py and objects.py
both build one of these rather than each hand-rolling their own per-kind
layout. Proven generic by tool/tests/test_entity_registry.py's own
dummy-entry test, which passes an entry neither tab file has ever
mentioned by name.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from tool.core.entity_registry import EntityKindEntry
from tool.ui.widgets.asset_image import load_asset

CARD_ICON_PX = 64


class EntityCardGrid(QWidget):
    """`on_intensity_changed(kind, value)`, `on_sign_changed(kind, checked)`,
    `on_field_changed(kind, field_name, value)` -- called only for LIVE
    entries (greyed ones have no editable field at all, ground rule 4:
    a control that can't do anything must not exist, not just be
    disabled)."""

    def __init__(self, entries: list[EntityKindEntry], profiles, enabled: bool,
                 on_intensity_changed, on_sign_changed, on_field_changed, parent=None):
        super().__init__(parent)
        self._on_intensity_changed = on_intensity_changed
        self._on_sign_changed = on_sign_changed
        self._on_field_changed = on_field_changed

        self._kind_boxes: dict = {}       # kind -> detail page QWidget (enabled/disabled as a whole)
        self._valence_checks: dict = {}   # kind -> QCheckBox, live entries only
        self._card_buttons: dict = {}

        layout = QVBoxLayout(self)
        card_row = QHBoxLayout()
        self._stack = QStackedWidget()

        for index, entry in enumerate(entries):
            button = QPushButton()
            button.setCheckable(True)
            button.setIcon(load_asset(entry.asset_id))
            button.setIconSize(QSize(CARD_ICON_PX, CARD_ICON_PX))
            button.setText(entry.display_name)
            button.setToolTip(entry.display_name if entry.live else f"{entry.display_name} (greyed): {entry.greyed_reason}")
            button.clicked.connect(lambda _checked, i=index: self._stack.setCurrentIndex(i))
            card_row.addWidget(button)
            self._card_buttons[entry.kind] = button

            page = self._build_page(entry, profiles, enabled)
            self._stack.addWidget(page)
            self._kind_boxes[entry.kind] = page

        card_row.addStretch(1)
        layout.addLayout(card_row)
        layout.addWidget(self._stack)

        if entries:
            self._card_buttons[entries[0].kind].setChecked(True)

    def _build_page(self, entry: EntityKindEntry, profiles, enabled: bool) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        kind = entry.kind

        if not entry.live:
            note = QLabel(entry.greyed_reason)
            note.setWordWrap(True)
            form.addRow(note)
            page.setEnabled(False)
            return page

        profile = profiles.get(kind)

        intensity_spin = QDoubleSpinBox()
        intensity_spin.setRange(0.0, 10.0)
        intensity_spin.setSingleStep(0.1)
        intensity_spin.setValue(profile.odours[0].intensity)
        intensity_spin.valueChanged.connect(lambda v, k=kind: self._on_intensity_changed(k, v))
        form.addRow(f"Odour intensity ({profile.odours[0].channel})", intensity_spin)

        valence_check = QCheckBox("Smells good (attractive)")
        valence_check.setChecked(profile.odours[0].sign > 0)
        valence_check.setToolTip(
            "Off: smells bad -- routes into the threat sum, scaled by "
            "danger weight below. On: smells good -- routes into the food "
            "sum instead, and danger weight then does nothing for this "
            "kind. This is a science change when actually used (CLAUDE.md "
            "rule 3) -- give it its own recorded run."
        )
        valence_check.toggled.connect(lambda v, k=kind: self._on_sign_changed(k, v))
        form.addRow("Valence", valence_check)
        self._valence_checks[kind] = valence_check

        # looming_salience/danger_weight are inert for a food-signed kind
        # (bridge/perception.py: profiled_enemy_thetas skips POWERUP
        # outright and QUESTION_BLOCK is tile-sourced, never in that same
        # loop; profiled_odor only ever applies danger_weight to a
        # THREAT-signed (sign<0) entry) -- a control for either would be a
        # control that lies (ground rule 4), so is_food gates them out,
        # not a hand-listed kind exception.
        if not profile.is_food:
            looming_spin = QDoubleSpinBox()
            looming_spin.setRange(0.0, 10.0)
            looming_spin.setSingleStep(0.1)
            looming_spin.setValue(profile.looming_salience)
            looming_spin.valueChanged.connect(lambda v, k=kind: self._on_field_changed(k, "looming_salience", v))
            form.addRow("Looming salience", looming_spin)

            danger_spin = QDoubleSpinBox()
            danger_spin.setRange(0.0, 10.0)
            danger_spin.setSingleStep(0.1)
            danger_spin.setValue(profile.danger_weight)
            danger_spin.setToolTip("Master knob: also scales looming salience above (SPEC section 1).")
            danger_spin.valueChanged.connect(lambda v, k=kind: self._on_field_changed(k, "danger_weight", v))
            form.addRow("Danger weight (master)", danger_spin)

        page.setEnabled(enabled)
        return page

    def set_enabled(self, enabled: bool) -> None:
        for kind, page in self._kind_boxes.items():
            if kind in self._valence_checks:  # a live page -- greyed pages stay disabled always
                page.setEnabled(enabled)
