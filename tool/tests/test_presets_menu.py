"""Ease-of-use redesign: presets move into one header "Presets" menu
(main_window.py), replacing the per-tab PresetBar. Each of the four
submenus (Character/Circuits/Goal/Settings) offers "Save current as..."
plus one action per preset already on disk, and loading one really
reaches the tab (same _apply_preset() mechanism the old PresetBar used).
"""
from __future__ import annotations

import shutil

import pytest

from config.output_routing import PROJECTS_ROOT
from tool.core.presets import PRESETS_ROOT, save_preset

PROJECT_NAME = "_presets_menu_test"


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def clean_presets():
    for key in ("character", "circuits", "goal", "settings"):
        shutil.rmtree(PRESETS_ROOT / key, ignore_errors=True)
    yield
    for key in ("character", "circuits", "goal", "settings"):
        shutil.rmtree(PRESETS_ROOT / key, ignore_errors=True)


def test_presets_menu_has_one_submenu_per_preset_tab(qtbot, clean_project, clean_presets):
    """Ease-of-use follow-up: Presets lives in the header, next to Save --
    a QToolButton with a dropdown menu, not a separate QMenuBar row."""
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow, PRESET_TAB_KEYS

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    assert window.presets_button.text() == "Presets"
    submenu_titles = {a.text() for a in window.presets_button.menu().actions()}
    assert submenu_titles == {label for _key, label in PRESET_TAB_KEYS}
    window.save()


def test_no_tab_builds_its_own_preset_bar_widget(qtbot, clean_project):
    """The old per-tab PresetBar is gone entirely -- presets only ever
    reach a tab through main_window.py's menu calling _apply_preset()."""
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    import importlib
    assert importlib.util.find_spec("tool.ui.widgets.preset_bar") is None
    window.save()


def test_loading_a_preset_through_the_menu_reaches_the_tab(qtbot, clean_project, clean_presets):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    settings_tab = window.tabs.widget(5)
    save_preset("settings", "_menu_test_workers_7", settings_tab._preset_data() | {"parallel_workers": 7})

    window._load_preset("settings", "_menu_test_workers_7")
    assert window.get_tool_settings().render.parallel_workers == 7
    new_tab = window.tabs.widget(5)
    assert new_tab.workers_spin.value() == 7
    window.save()
