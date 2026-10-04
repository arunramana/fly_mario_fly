"""tool/SPEC_ui_retro.md section 10 (minimal scope): main_window.py builds
its tabs by iterating tool.core.tab_registry.TAB_REGISTRY -- registering a
dummy tab there must make window.tabs.count() include it, with no edit to
main_window.py's own construction code.
"""
from __future__ import annotations

import shutil

import pytest
from PySide6.QtWidgets import QLabel

from config.output_routing import PROJECTS_ROOT
from tool.core.tab_registry import TAB_REGISTRY, TabRegistryEntry

PROJECT_NAME = "_tab_registry_test"


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def dummy_tab_entry():
    entry = TabRegistryEntry("dummy_test_tab", "8 Dummy", lambda window: QLabel("dummy tab"))
    TAB_REGISTRY.append(entry)
    yield entry
    TAB_REGISTRY.remove(entry)


def test_a_dummy_tab_entry_appears_in_the_tab_widget(qtbot, clean_project, dummy_tab_entry):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    assert window.tabs.count() == 11
    assert window.tabs.tabText(10) == "8 Dummy"
    assert isinstance(window.tabs.widget(10), QLabel)
    window.save()


def test_the_real_registry_still_builds_exactly_ten_tabs_without_the_dummy(qtbot, clean_project):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    assert window.tabs.count() == 10
    assert window.character_tab is window.tabs.widget(0)
    assert window.run_tab is window.tabs.widget(6)
    window.save()
