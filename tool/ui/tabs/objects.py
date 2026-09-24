"""tool/ui/tabs/objects.py -- tab 3: picture cards for POWERUP/
QUESTION_BLOCK plus greyed GROUND/USED_BLOCK/SOLID_OTHER/PIT (C8a,
tool/PLAN.md P6, docs/SPEC_entity_perception.md; tool/SPEC_ui_retro.md
sections 7/10 -- card grid, entity registry). Greyed cards' detail panel
states WHY, not just that it's disabled (tool/core/entity_registry.py's
own reasons, derived alongside "live"). Shares the same "Enable per-kind
entity profiles" toggle as tab 2 (enemies.py); flipping it in either tab
reloads both so they never show mismatched checkbox state.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget

from mario.entities.kinds import EntityKind
from tool.core.entity_profiles_store import load_merged, set_kind_odour_intensity, set_kind_odour_sign
from tool.core.entity_registry import all_entity_entries
from tool.ui.widgets.entity_cards import EntityCardGrid

# Same small, stable tab-membership split as enemies.py's own
# ENEMIES_TAB_KINDS -- live/greyed status itself is derived, this list
# just says which kinds appear on THIS tab.
OBJECTS_TAB_KINDS = (
    EntityKind.POWERUP, EntityKind.QUESTION_BLOCK,
    EntityKind.GROUND, EntityKind.USED_BLOCK, EntityKind.SOLID_OTHER, EntityKind.PIT,
)


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
        entries_by_kind = {e.kind: e for e in all_entity_entries()}
        entries = [entries_by_kind[k] for k in OBJECTS_TAB_KINDS]

        # No on_field_changed handler needed: every kind on this tab is
        # is_food=True (or greyed), so EntityCardGrid never renders a
        # looming/danger control here at all (see its own is_food gate).
        self._grid = EntityCardGrid(
            entries, profiles, settings.entity_profile.enabled,
            self._on_intensity_changed, self._on_sign_changed, lambda *_: None,
        )
        layout.addWidget(self._grid)
        # Backward-compatible aliases (tool/tests/test_entity_profiles_tab.py):
        # LIVE detail pages only, matching the pre-card-grid shape (the
        # old GREYED_KINDS boxes were never in this list either).
        self._kind_boxes = [self._grid._kind_boxes[e.kind] for e in entries if e.live]
        self._valence_checks = self._grid._valence_checks

        layout.addStretch(1)

    def _on_enable_toggled(self, checked: bool) -> None:
        settings = self._window.get_tool_settings()
        entity_profile = dataclasses.replace(settings.entity_profile, enabled=checked)
        self._window.set_tool_settings(dataclasses.replace(settings, entity_profile=entity_profile))
        self._grid.set_enabled(checked)
        self._window.reload_tab("enemies")

    def _on_intensity_changed(self, kind: EntityKind, value: float) -> None:
        set_kind_odour_intensity(self._window.project.name, kind.name, 0, value)

    def _on_sign_changed(self, kind: EntityKind, checked: bool) -> None:
        set_kind_odour_sign(self._window.project.name, kind.name, 0, 1 if checked else -1)
