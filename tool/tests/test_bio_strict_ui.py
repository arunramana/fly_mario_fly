"""Goal tab's strict-fly switch writes config.bio_strict; bio params sit in Circuits > Other parameters."""
from __future__ import annotations

import shutil

import pytest

from config.output_routing import PROJECTS_ROOT
from tool.core.project import ToolProject
from tool.ui.main_window import MainWindow

NAME = "_bio_ui_test"


@pytest.fixture()
def window(qtbot):
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    w = MainWindow(ToolProject.open("win_attempt").duplicate(NAME))
    qtbot.addWidget(w)
    w._closing_confirmed = True
    yield w
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def test_goal_tab_toggles_bio_strict_and_params_are_editable(window):
    assert window.get_config().bio_strict is False
    window.goal_tab.bio_strict_checkbox.setChecked(True)
    assert window.get_config().bio_strict is True
    circuits = window.tabs.widget(3)
    assert "bio.elevation_limit_deg" in circuits.param_form._widget_by_path
    assert "bio.walk_threshold" in circuits.param_form._widget_by_path
