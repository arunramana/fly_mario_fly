"""Ease-of-use redesign: a Home button in the header returns to the
project gate, guarded by the same unsaved-changes prompt closing the
window already uses (main_window.py's _confirm_discard_or_save(), shared
by closeEvent and _go_home()).
"""
from __future__ import annotations

import shutil

import pytest
from PySide6.QtWidgets import QMessageBox

from config.output_routing import PROJECTS_ROOT

PROJECT_NAME = "_home_button_test"


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def test_home_emits_home_requested_when_nothing_unsaved(qtbot, clean_project):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)
    assert not window._dirty

    fired = []
    window.home_requested.connect(lambda: fired.append(True))
    window._go_home()

    assert fired == [True]
    assert window._closing_confirmed is True


def test_home_is_blocked_by_cancelling_the_unsaved_changes_prompt(qtbot, clean_project, monkeypatch):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)
    window.mark_dirty()
    assert window._dirty

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)

    fired = []
    window.home_requested.connect(lambda: fired.append(True))
    window._go_home()

    assert fired == [], "Cancelling the unsaved-changes prompt must block Home"
    assert window._closing_confirmed is False
    window.save()  # leave clean for qtbot's own teardown close()


def test_home_saves_and_proceeds_when_the_prompt_is_answered_save(qtbot, clean_project, monkeypatch):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)
    window.mark_dirty()

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Save)

    fired = []
    window.home_requested.connect(lambda: fired.append(True))
    window._go_home()

    assert fired == [True]
    assert window._dirty is False, "answering Save must actually save before proceeding"
