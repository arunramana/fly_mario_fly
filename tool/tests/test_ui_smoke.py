"""tool/PLAN.md P3-P5's UI smoke test: opens a project, builds the main
window (all seven tabs), flips a control, and plays a short run through a
real worker process with a live preview -- the explicit target this phase
was built against. No modal dialogs anywhere in this path: a run
finishing must show its result on the Run tab / status bar, not a
QMessageBox with nothing to dismiss it in an automated run (found the
hard way -- the first version of this hung indefinitely).
"""
from __future__ import annotations

import dataclasses
import shutil

import pytest
from PySide6.QtCore import QEventLoop, QTimer

from config.output_routing import PROJECTS_ROOT

PROJECT_NAME = "_ui_smoke_test"
SHORT_MAX_FRAMES = 100


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _short_project(clean_project):
    from tool.core.project import ToolProject
    project = ToolProject.create(PROJECT_NAME)
    project.config = dataclasses.replace(
        project.config, scenario=dataclasses.replace(project.config.scenario, max_frames=SHORT_MAX_FRAMES))
    project.save()
    return project


def test_main_window_builds_all_seven_tabs(qtbot, clean_project):
    project = _short_project(clean_project)
    from tool.ui.main_window import MainWindow
    window = MainWindow(project)
    qtbot.addWidget(window)
    assert window.tabs.count() == 7
    titles = [window.tabs.tabText(i) for i in range(7)]
    assert titles == ["1 Character", "2 Enemies", "3 Objects", "4 Circuits",
                       "5 Goal", "6 Settings", "7 Run"]


def test_flipping_a_circuit_control_marks_the_project_dirty(qtbot, clean_project):
    project = _short_project(clean_project)
    from tool.ui.main_window import MainWindow
    window = MainWindow(project)
    qtbot.addWidget(window)
    assert not window._dirty

    original_jump_g = project.config.jump.g
    circuits_tab = window.tabs.widget(3)
    jump_g_widget = circuits_tab.param_form._widget_by_path["jump.g"]
    jump_g_widget.setValue(jump_g_widget.value() + 0.1)

    assert window._dirty
    assert window.get_config().jump.g != original_jump_g
    assert window.title_label.text().endswith("*")

    # qtbot.addWidget's teardown calls window.close(), which (correctly)
    # prompts to save unsaved changes -- a real, blocking modal with
    # nothing to dismiss it here. Leave the window clean before returning
    # rather than weaken that prompt for real usage.
    window.save()


def test_play_streams_frames_and_finishes_without_a_modal_dialog(qtbot, clean_project):
    """The target this whole phase was built against: Play -> worker
    process -> live preview -> finishes cleanly."""
    project = _short_project(clean_project)
    from tool.ui.main_window import MainWindow
    window = MainWindow(project)
    qtbot.addWidget(window)

    frames_seen = []
    real_show_frame = window.run_tab.preview.show_frame

    def counting_show_frame(obs, row):
        frames_seen.append(row.get("frame"))
        real_show_frame(obs, row)

    window.run_tab.preview.show_frame = counting_show_frame

    loop = QEventLoop()
    finished = {"info": None}
    real_on_finished = window._on_run_finished

    def wrapped_on_finished(info):
        real_on_finished(info)
        finished["info"] = info
        loop.quit()

    window._on_run_finished = wrapped_on_finished

    timeout_timer = QTimer()
    timeout_timer.setSingleShot(True)
    timeout_timer.timeout.connect(loop.quit)
    timeout_timer.start(120_000)

    window.play()
    assert window._process is not None and window._process.is_alive()
    loop.exec()

    assert finished["info"] is not None, "run never finished (or the safety timeout fired first)"
    assert len(frames_seen) == finished["info"]["n_frames"]
    # No modal dialog was ever shown: the result went to the Run tab's own
    # label instead, and the event loop returned on its own.
    assert window.run_tab.result_label.text() != ""
    assert "Run #" in window.run_tab.result_label.text()
