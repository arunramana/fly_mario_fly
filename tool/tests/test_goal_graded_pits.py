"""Goal tab's Graded pit response toggle (docs/SPEC_pits.md) round-trips
through config.scenario.graded_pit_response."""
from __future__ import annotations

import shutil

from config.output_routing import PROJECTS_ROOT

NAME = "_goal_graded_pits_test"


def test_toggle_writes_config_and_starts_from_it(qtbot):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    try:
        window = MainWindow(ToolProject.create(NAME))
        qtbot.addWidget(window)
        goal = window.tabs.widget(4)
        assert goal.graded_pits_checkbox.isChecked() is False
        goal.graded_pits_checkbox.setChecked(True)
        assert window.get_config().scenario.graded_pit_response is True
        window.save()
    finally:
        shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
