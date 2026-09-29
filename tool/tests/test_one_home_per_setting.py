"""noise.sigma has two editors (Goal tab and Circuits > Other parameters) but ONE
value: each writes config.noise.sigma through window.set_config and re-reads it on
MainWindow.config_changed, so they can never disagree (tool/SPEC_ui_retro.md section 3's
"which one is the real one" trap, solved by sync instead of by making one read-only).
"""
from __future__ import annotations

import shutil

import pytest

from config.output_routing import PROJECTS_ROOT

PROJECT_NAME = "_one_home_test"


def circuits_sigma(window):
    return window.tabs.widget(3).param_form._widget_by_path["noise.sigma"]


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def test_goal_sigma_is_editable(qtbot, clean_project):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    goal_tab = window.tabs.widget(4)
    assert goal_tab.sigma_spin.isEnabled(), "Goal tab's sigma control is editable"
    goal_tab.sigma_spin.setValue(0.05)
    assert window.get_config().noise.sigma == pytest.approx(0.05)
    assert circuits_sigma(window).value() == pytest.approx(0.05), "Circuits tab follows the Goal tab"
    window.save()


def test_changing_sigma_on_circuits_tab_updates_goal_tab_live(qtbot, clean_project):
    """The actual bar this fix needs to clear: the Goal tab's display
    reflects a change made through the Circuits tab WITHOUT being told
    to refresh separately -- it reads live config.noise.sigma via
    MainWindow.config_changed, not a value snapshotted once at
    construction."""
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    goal_tab = window.tabs.widget(4)
    circuits_tab = window.tabs.widget(3)
    sigma_widget = circuits_tab.param_form._widget_by_path["noise.sigma"]

    original = goal_tab.sigma_spin.value()
    new_value = original + 0.05
    sigma_widget.setValue(new_value)

    assert window.get_config().noise.sigma == pytest.approx(new_value)
    assert goal_tab.sigma_spin.value() == pytest.approx(new_value), (
        "Goal tab's read-only sigma display did not update when the Circuits "
        "tab's own widget changed it"
    )
    window.save()


def test_both_editors_write_the_same_config_value(qtbot, clean_project):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    window = MainWindow(ToolProject.create(PROJECT_NAME))
    qtbot.addWidget(window)
    goal_tab = window.tabs.widget(4)
    circuits_sigma(window).setValue(0.02)
    assert goal_tab.sigma_spin.value() == pytest.approx(0.02)
    goal_tab.sigma_spin.setValue(0.03)
    assert window.get_config().noise.sigma == pytest.approx(0.03)
    assert circuits_sigma(window).value() == pytest.approx(0.03)
    window.save()
