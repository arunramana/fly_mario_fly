"""tool/PLAN.md P7: presets round-trip through tool/core/presets.py, and
loading one through a tab's preset bar actually changes window state (not
just the file on disk) -- ground rule 4, "no control lies".
"""
from __future__ import annotations

import shutil

import pytest

from config.output_routing import PROJECTS_ROOT
from tool.core.presets import PRESETS_ROOT, list_presets, load_preset, save_preset

PROJECT_NAME = "_presets_test"


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def clean_presets():
    tab_dir = PRESETS_ROOT / "_test_tab"
    shutil.rmtree(tab_dir, ignore_errors=True)
    yield
    shutil.rmtree(tab_dir, ignore_errors=True)


def test_save_load_list_round_trip(clean_presets):
    assert list_presets("_test_tab") == []
    save_preset("_test_tab", "aggressive", {"a": 1, "b": [1, 2, 3]})
    save_preset("_test_tab", "cautious", {"a": 2})
    assert list_presets("_test_tab") == ["aggressive", "cautious"]
    assert load_preset("_test_tab", "aggressive") == {"a": 1, "b": [1, 2, 3]}


def test_settings_tab_preset_changes_window_state(qtbot, clean_project, clean_presets):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    settings_tab = window.tabs.widget(5)
    save_preset("settings", "_test_workers_9", settings_tab._preset_data() | {"parallel_workers": 9})

    settings_tab._apply_preset(load_preset("settings", "_test_workers_9"))
    assert window.get_tool_settings().render.parallel_workers == 9
    # reload_tab swapped in a fresh SettingsTab reflecting the new value.
    new_tab = window.tabs.widget(5)
    assert new_tab is not settings_tab
    assert new_tab.workers_spin.value() == 9

    shutil.rmtree(PRESETS_ROOT / "settings", ignore_errors=True)
    window.save()  # leave clean: qtbot's teardown close() would else hit the real unsaved-changes prompt


def test_character_tab_preset_changes_window_state(qtbot, clean_project, clean_presets):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    character_tab = window.tabs.widget(0)
    data = character_tab._preset_data() | {"player": "luigi", "starting_powerup": True}
    save_preset("character", "_test_luigi_big", data)

    character_tab._apply_preset(load_preset("character", "_test_luigi_big"))
    settings = window.get_tool_settings()
    assert settings.character.player == "luigi"
    assert settings.character.starting_powerup is True

    shutil.rmtree(PRESETS_ROOT / "character", ignore_errors=True)
    window.save()  # leave clean: qtbot's teardown close() would else hit the real unsaved-changes prompt
