"""tool/ui/widgets/entity_cards.py -- tool/SPEC_ui_retro.md sections 7/10,
ease-of-use redesign: one picture-card grid + inspector-panel widget,
generic over any list of tool.core.entity_registry.EntityKindEntry --
enemies.py and objects.py both build one of these rather than each
hand-rolling their own per-kind layout. Cards sit in a responsive
FlowLayout (wraps to fit the window, not a fixed column count) on the
left; the selected card's own settings show in an inspector panel to the
RIGHT (a QSplitter), not as full-width rows stacked below the cards.
Proven generic by tool/tests/test_entity_registry.py's own dummy-entry
test, which passes an entry neither tab file has ever mentioned by name.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QLabel, QScrollArea,
    QSplitter, QStackedWidget, QWidget,
)

from mario.entities.kinds import EntityKind
from tool.core.entity_registry import EntityKindEntry
from tool.ui.widgets.asset_image import load_asset
from tool.ui.widgets.card_button import make_card_button
from tool.ui.widgets.flow_layout import FlowLayout
from tool.ui.widgets.no_scroll_inputs import NoScrollDoubleSpinBox

CARD_ICON_PX = 96  # bigger cards -- ease-of-use redesign


class EntityCardGrid(QSplitter):
    """`on_intensity_changed(kind, value)`, `on_sign_changed(kind, checked)`,
    `on_field_changed(kind, field_name, value)` -- called only for LIVE
    entries (greyed ones have no editable field at all, ground rule 4:
    a control that can't do anything must not exist, not just be
    disabled)."""

    def __init__(self, entries: list[EntityKindEntry], profiles, enabled: bool,
                 on_intensity_changed, on_sign_changed, on_field_changed, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._on_intensity_changed = on_intensity_changed
        self._on_sign_changed = on_sign_changed
        self._on_field_changed = on_field_changed

        self._kind_boxes: dict = {}       # kind -> detail page QWidget (enabled/disabled as a whole)
        self._valence_checks: dict = {}   # kind -> QCheckBox, live entries only
        self._card_buttons: dict = {}

        card_scroll = QScrollArea()
        card_scroll.setWidgetResizable(True)
        # A FlowLayout's own sizeHint() collapses to one card's width (it
        # has no notion of "how many columns would look good"), which a
        # QSplitter reads literally and shrinks this pane to fit -- an
        # explicit minimum width is what actually gets the splitter to
        # give the grid room to wrap past a single column.
        card_scroll.setMinimumWidth(CARD_ICON_PX + 40)   # one card; the FlowLayout wraps the rest
        card_area = QWidget()
        card_flow = FlowLayout(card_area, spacing=10)
        self._stack = QStackedWidget()

        for index, entry in enumerate(entries):
            tooltip = entry.display_name if entry.live else f"{entry.display_name} (greyed): {entry.greyed_reason}"
            button = make_card_button(entry.display_name, load_asset(entry.asset_id), CARD_ICON_PX, tooltip)
            button.clicked.connect(lambda _checked, i=index: self._select(i))
            card_flow.addWidget(button)
            self._card_buttons[entry.kind] = button

            page = self._build_page(entry, profiles, enabled)
            self._stack.addWidget(page)
            self._kind_boxes[entry.kind] = page

        card_scroll.setWidget(card_area)
        self.addWidget(card_scroll)
        self.addWidget(self._stack)
        self.setStretchFactor(0, 3)
        self.setStretchFactor(1, 2)
        # QSplitter's stretch factor only governs EXTRA space on resize,
        # not the initial split -- without this, the card side started
        # too narrow for FlowLayout to ever wrap to more than one column.
        self.setSizes([700, 400])

        if entries:
            self._select(0)

    def _select(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        for i, button in enumerate(self._card_buttons.values()):
            button.setChecked(i == index)

    def _build_page(self, entry: EntityKindEntry, profiles, enabled: bool) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        kind = entry.kind

        title = QLabel(entry.display_name)
        title.setStyleSheet("font-weight: bold;")
        form.addRow(title)

        if not entry.live:
            note = QLabel(entry.greyed_reason)
            note.setWordWrap(True)
            form.addRow(note)
            page.setEnabled(False)
            return page

        profile = profiles.get(kind)

        intensity_spin = NoScrollDoubleSpinBox()
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
            looming_spin = NoScrollDoubleSpinBox()
            looming_spin.setRange(0.0, 10.0)
            looming_spin.setSingleStep(0.1)
            looming_spin.setValue(profile.looming_salience)
            looming_spin.valueChanged.connect(lambda v, k=kind: self._on_field_changed(k, "looming_salience", v))
            form.addRow("Looming salience", looming_spin)

            danger_spin = NoScrollDoubleSpinBox()
            danger_spin.setRange(0.0, 10.0)
            danger_spin.setSingleStep(0.1)
            danger_spin.setValue(profile.danger_weight)
            danger_spin.setToolTip("Master knob: also scales looming salience above (SPEC section 1).")
            danger_spin.valueChanged.connect(lambda v, k=kind: self._on_field_changed(k, "danger_weight", v))
            form.addRow("Danger weight (master)", danger_spin)

        # QUESTION_BLOCK only: the profile for Circuits' "? block ahead" perception module
        # (docs/SPEC_learning_v2.md section 5). Scales its Kenyon-cell inputs and weak looming cue.
        if kind == EntityKind.QUESTION_BLOCK:
            cue_spin = NoScrollDoubleSpinBox()
            cue_spin.setRange(0.0, 10.0)
            cue_spin.setSingleStep(0.1)
            cue_spin.setValue(profile.cue_weight)
            cue_spin.setToolTip("Scale on the '? block ahead' perception module's cue (its two Kenyon-cell "
                                "inputs and its looming route). Only used while that module is on "
                                "(Circuits > Mushroom body) and profiles are enabled. 1 = unscaled.")
            cue_spin.valueChanged.connect(lambda v, k=kind: self._on_field_changed(k, "cue_weight", v))
            form.addRow("Cue weight (? block ahead)", cue_spin)

        page.setEnabled(enabled)
        return page

    def set_enabled(self, enabled: bool) -> None:
        for kind, page in self._kind_boxes.items():
            if kind in self._valence_checks:  # a live page -- greyed pages stay disabled always
                page.setEnabled(enabled)
