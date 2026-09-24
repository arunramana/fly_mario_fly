"""tool/SPEC_ui_retro.md section 3: noise.sigma was found editable in
BOTH the Goal tab and the Circuits tab (schema.py's ParamForm covers all
49 scalars), nothing keeping the two in sync by construction -- a real
"which one is the real one" trap. Fixed: the Circuits tab is the one
writable home; the Goal tab's own control is read-only and stays live
via MainWindow.config_changed.
"""
from __future__ import annotations

import shutil

import pytest

from config.output_routing import PROJECTS_ROOT

PROJECT_NAME = "_one_home_test"


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def test_goal_sigma_is_read_only(qtbot, clean_project):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    goal_tab = window.tabs.widget(4)
    assert not goal_tab.sigma_spin.isEnabled(), "Goal tab's sigma control must be read-only"
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


def test_only_one_widget_writes_noise_sigma(qtbot, clean_project):
    """Structural check, not just this one value: the Goal tab's sigma
    widget must be disabled (never emits a user edit), so there is
    exactly one path that can ever call set_config with a new sigma."""
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    goal_tab = window.tabs.widget(4)
    assert not goal_tab.sigma_spin.isEnabled()
    window.save()
