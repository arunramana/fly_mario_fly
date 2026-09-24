"""tool/PLAN.md P7: Space plays, Esc cancels, Ctrl+S saves.

Methods are stubbed on the CLASS before construction, not the instance
after: QShortcut(..., activated=self.play) binds to whatever `self.play`
resolves to at __init__ time, so patching the instance attribute
afterwards would leave the shortcut pointed at the original method.

Simulated OS-level key presses (QTest.keyClick) do not reach these
shortcuts under the offscreen QPA platform tool/tests runs under --
verified directly: even an ApplicationShortcut (not the default
WindowShortcut, which needs a platform-activated window offscreen never
provides) sees no event, because offscreen never grants real keyboard
focus to any widget at all, with or without qtbot.waitExposed/waitActive.
So this test finds each QShortcut Qt actually constructed and fires its
`activated` signal directly -- checking the real binding (key sequence ->
method), not a platform feature this project doesn't otherwise depend on.
"""
from __future__ import annotations

import shutil

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence

from config.output_routing import PROJECTS_ROOT

PROJECT_NAME = "_shortcuts_test"


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _shortcut_for(window, key_sequence: QKeySequence) -> QShortcut:
    matches = [s for s in window.findChildren(QShortcut) if s.key() == key_sequence]
    assert len(matches) == 1, f"expected exactly one shortcut for {key_sequence.toString()!r}, found {len(matches)}"
    return matches[0]


def test_space_triggers_play(qtbot, clean_project, monkeypatch):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    calls = []
    monkeypatch.setattr(MainWindow, "play", lambda self: calls.append("play"))
    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    _shortcut_for(window, QKeySequence(Qt.Key.Key_Space)).activated.emit()
    assert calls == ["play"]


def test_escape_triggers_cancel(qtbot, clean_project, monkeypatch):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    calls = []
    monkeypatch.setattr(MainWindow, "cancel", lambda self: calls.append("cancel"))
    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    _shortcut_for(window, QKeySequence(Qt.Key.Key_Escape)).activated.emit()
    assert calls == ["cancel"]


def test_ctrl_s_triggers_save(qtbot, clean_project, monkeypatch):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    calls = []
    monkeypatch.setattr(MainWindow, "save", lambda self: calls.append("save"))
    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    _shortcut_for(window, QKeySequence(QKeySequence.StandardKey.Save)).activated.emit()
    assert calls == ["save"]
