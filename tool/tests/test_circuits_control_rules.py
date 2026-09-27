"""Circuits tab: one checkbox per control rule (docs/CONTROL_AUDIT.md) writing
config.rules, a read-only mirror of the forced graded-pit switch, and the wall
perception module's toggle and editors."""
from __future__ import annotations

import shutil

from config.output_routing import PROJECTS_ROOT
from config.params import CONTROL_RULE_LABELS, ControlRules

NAME = "_circuits_rules_test"


def _window(qtbot):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    window = MainWindow(ToolProject.create(NAME))
    qtbot.addWidget(window)
    return window, window.tabs.widget(3)


def test_every_rule_is_shown_and_toggles_the_config(qtbot):
    try:
        window, circuits = _window(qtbot)
        assert set(circuits.rule_checkboxes) == set(CONTROL_RULE_LABELS)
        assert all(cb.isChecked() for cb in circuits.rule_checkboxes.values()), "defaults: every rule on"
        for rule, cb in circuits.rule_checkboxes.items():
            cb.setChecked(False)
            assert getattr(window.get_config().rules, rule) is False
        assert window.get_config().rules == ControlRules(**{r: False for r in CONTROL_RULE_LABELS})
        cb = circuits.rule_checkboxes["refusal"]
        cb.setChecked(True)
        assert window.get_config().rules.refusal is True
        window.save()
    finally:
        shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def test_rule_checkboxes_follow_config_changes_made_elsewhere(qtbot):
    import dataclasses
    try:
        window, circuits = _window(qtbot)
        cfg = window.get_config()
        window.set_config(dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, jump_hold=False)))
        assert circuits.rule_checkboxes["jump_hold"].isChecked() is False
        window.save()
    finally:
        shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def test_graded_pit_is_mirrored_read_only(qtbot):
    try:
        window, circuits = _window(qtbot)
        assert not circuits.graded_pit_mirror.isEnabled() and not circuits.graded_pit_mirror.isChecked()
        window.tabs.widget(4).graded_pits_checkbox.setChecked(True)
        assert circuits.graded_pit_mirror.isChecked()
        window.save()
    finally:
        shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def test_wall_module_toggle_and_editors(qtbot):
    try:
        window, circuits = _window(qtbot)
        assert window.get_config().modules.wall_ahead is None                 # off by default
        assert not circuits.module_editor_boxes["wall_ahead"].isVisibleTo(circuits)
        circuits.module_checkboxes["wall_ahead"].setChecked(True)
        assert window.get_config().modules.wall_ahead is not None
        assert circuits.module_editor_boxes["wall_ahead"].isVisibleTo(circuits)
        circuits.module_editors[("wall_ahead", "takeoff_gain")].setValue(0.5)
        assert window.get_config().modules.wall_ahead.takeoff_gain == 0.5
        window.save()
    finally:
        shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
