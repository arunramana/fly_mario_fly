"""tool/ui/tabs/enemies.py -- tab 2: picture cards for GOOMBA/KOOPA/ENEMY
(C8a, tool/PLAN.md P6, docs/SPEC_entity_perception.md;
tool/SPEC_ui_retro.md sections 7/10 -- card grid, entity registry).
Reads/writes projects/<name>/entity_profiles.json through tool/core/
entity_profiles_store.py; only takes effect on a run when the "Enable
per-kind entity profiles" checkbox is on (EntityProfileSettings.enabled --
ground rule 4, the file existing is not itself what turns this on).
"""

from __future__ import annotations

import dataclasses

from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget

from mario.entities.kinds import EntityKind
from tool.ui.widgets.scroll_page import install_scroll_page
from tool.core.entity_profiles_store import (
    load_merged, set_kind_field, set_kind_odour_intensity, set_kind_odour_sign,
)
from tool.core.entity_registry import all_entity_entries
from tool.ui.widgets.entity_cards import EntityCardGrid

# Which EntityKinds this tab covers, in card order -- a small, stable
# tab-membership split (this rarely changes), NOT the live/greyed
# classification itself, which tool/core/entity_registry.py derives from
# bridge/profiles/default.json (tool/SPEC_ui_retro.md section 10).
# QUESTION_BLOCK/POWERUP are tab 3's (objects.py).
ENEMIES_TAB_KINDS = (EntityKind.GOOMBA, EntityKind.KOOPA, EntityKind.ENEMY)


class EnemiesTab(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        content = QWidget()
        layout = QVBoxLayout(content)
        install_scroll_page(self, content)

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
        entries_by_kind = {e.kind: e for e in all_entity_entries()}
        entries = [entries_by_kind[k] for k in ENEMIES_TAB_KINDS]

        self._grid = EntityCardGrid(
            entries, profiles, settings.entity_profile.enabled,
            self._on_intensity_changed, self._on_sign_changed, self._on_field_changed,
        )
        layout.addWidget(self._grid)
        # Backward-compatible aliases (tool/tests/test_entity_profiles_tab.py,
        # test_one_home_per_setting.py): a list of the LIVE detail pages
        # only, matching the pre-card-grid shape exactly.
        self._kind_boxes = [self._grid._kind_boxes[e.kind] for e in entries if e.live]
        self._valence_checks = self._grid._valence_checks

        layout.addStretch(1)

    def _on_enable_toggled(self, checked: bool) -> None:
        settings = self._window.get_tool_settings()
        entity_profile = dataclasses.replace(settings.entity_profile, enabled=checked)
        self._window.set_tool_settings(dataclasses.replace(settings, entity_profile=entity_profile))
        self._grid.set_enabled(checked)
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
