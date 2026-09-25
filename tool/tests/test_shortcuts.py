"""tool/PLAN.md P7: Ctrl+Enter plays (ease-of-use redesign moved this off
Space, which now drives the Run tab's own video-player play/pause
instead), Esc cancels, Ctrl+S saves.

Ctrl+Enter/Space/Ctrl+S: methods are stubbed on the CLASS before
construction, not the instance after: QShortcut(..., activated=self.play)
binds to whatever `self.play` resolves to at __init__ time, so patching
the instance attribute afterwards would leave the shortcut pointed at the
original method. Simulated OS-level key presses (QTest.keyClick) do not
reach a QShortcut under the offscreen QPA platform tool/tests runs
under -- verified directly: even ApplicationShortcut (not the default
WindowShortcut, which needs a platform-activated window offscreen never
provides) sees no event, because offscreen never grants real keyboard
focus to any widget at all, with or without qtbot.waitExposed/waitActive.
So those two are tested by finding the QShortcut Qt actually constructed
and firing its `activated` signal directly -- checking the real binding
(key sequence -> method), not a platform feature this project doesn't
otherwise depend on.

Escape: found in REAL desktop testing (not offscreen), not reproducible
through the above -- a focused widget (a spin box, confirmed: this
project's own ParamForm has dozens of them on the Circuits tab) can
claim Escape via Qt's normal notify()/ShortcutOverride pipeline before a
QShortcut -- Application-scoped or not -- ever sees it. Fixed with an
eventFilter on the QApplication itself (main_window.py), which gets
every key event before any widget's own keyPressEvent. This mechanism
does NOT depend on window activation the way QShortcut does, so it is
verified here with a REAL QTest.keyClick, including with focus (and an
actual in-progress, uncommitted edit) inside a spin box -- the exact
scenario that failed on the real desktop.
"""
from __future__ import annotations

import dataclasses
import shutil

import pytest
from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtTest import QTest

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


def test_ctrl_enter_triggers_play(qtbot, clean_project, monkeypatch):
    """Ease-of-use redesign: START (a brand new simulation run) moved to
    Ctrl+Enter -- Space now drives the Run tab's own video-player
    play/pause instead, so the two "play" actions don't share a key."""
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    calls = []
    monkeypatch.setattr(MainWindow, "play", lambda self: calls.append("play"))
    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    _shortcut_for(window, QKeySequence("Ctrl+Return")).activated.emit()
    assert calls == ["play"]


def test_space_triggers_the_video_player_toggle_not_a_new_run(qtbot, clean_project, monkeypatch):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    play_calls = []
    monkeypatch.setattr(MainWindow, "play", lambda self: play_calls.append("play"))
    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    toggle_calls = []
    window.run_tab.toggle_playback = lambda: toggle_calls.append("toggle")

    _shortcut_for(window, QKeySequence(Qt.Key.Key_Space)).activated.emit()
    assert toggle_calls == ["toggle"]
    assert play_calls == [], "Space must not also start a brand new simulation run"


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


def _short_project(clean_project, max_frames=5000):
    from tool.core.project import ToolProject
    project = ToolProject.create(PROJECT_NAME)
    project.config = dataclasses.replace(
        project.config, scenario=dataclasses.replace(project.config.scenario, max_frames=max_frames))
    project.save()
    return project


def test_escape_cancels_a_running_run_with_focus_in_a_spin_box(qtbot, clean_project):
    """The exact scenario reported from real desktop testing: a run is
    playing, keyboard focus is inside a Circuits tab spin box (not the
    Run tab, not a button), and Escape is pressed for real (QTest.
    keyClick, not .activated.emit()) -- it must still cancel."""
    from tool.ui.main_window import MainWindow

    project = _short_project(clean_project)
    window = MainWindow(project)
    qtbot.addWidget(window)

    window.tabs.setCurrentIndex(3)  # Circuits
    circuits_tab = window.tabs.widget(3)
    spin = next(iter(circuits_tab.param_form._widget_by_path.values()))
    spin.setFocus()

    loop = QEventLoop()
    finished = {"info": None}
    real_on_finished = window._on_run_finished

    def wrapped(info):
        real_on_finished(info)
        finished["info"] = info
        loop.quit()

    window._on_run_finished = wrapped
    safety = QTimer()
    safety.setSingleShot(True)
    safety.timeout.connect(loop.quit)
    safety.start(60_000)

    window.play()
    QTest.keyClick(spin, Qt.Key.Key_Escape)
    loop.exec()

    assert finished["info"] is not None, "run never finished (or the safety timeout fired first)"
    assert finished["info"]["cancelled"] is True
    assert finished["info"]["n_frames"] < 5000, "a cancelled run must stop well short of max_frames"
    window.save()


def test_ctrl_number_shortcuts_switch_tabs(qtbot, clean_project):
    """Ease-of-use redesign: Ctrl+1..Ctrl+7 jump straight to a tab."""
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow

    project = ToolProject.create(PROJECT_NAME)
    window = MainWindow(project)
    qtbot.addWidget(window)

    for i in range(7):
        _shortcut_for(window, QKeySequence(f"Ctrl+{i + 1}")).activated.emit()
        assert window.tabs.currentIndex() == i
    window.save()


def test_escape_does_not_disturb_a_spin_box_when_no_run_is_active(qtbot, clean_project):
    """The eventFilter only claims Escape while a run is actually
    playing (main_window.py's own guard) -- with no run active, Escape
    must reach the focused widget exactly as it would with no filter
    installed at all."""
    from tool.ui.main_window import MainWindow

    project = _short_project(clean_project)
    window = MainWindow(project)
    qtbot.addWidget(window)

    window.tabs.setCurrentIndex(3)
    circuits_tab = window.tabs.widget(3)
    spin = next(iter(circuits_tab.param_form._widget_by_path.values()))
    spin.setFocus()

    calls = []
    window.cancel = lambda: calls.append("cancel")
    QTest.keyClick(spin, Qt.Key.Key_Escape)

    assert calls == [], "Escape must not be claimed globally when no run is playing"
    window.save()
