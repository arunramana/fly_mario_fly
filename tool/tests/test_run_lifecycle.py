"""tool/PLAN.md: GUI bugs found in manual testing around a run's own
lifecycle -- plots never fed after a live run, cancelled runs recorded
indistinguishably from finished ones, the progress bar and preview frame
left in a mid-run state once the run is actually over.
"""
from __future__ import annotations

import dataclasses
import shutil

import pytest
from PySide6.QtCore import QEventLoop, QTimer

from config.output_routing import PROJECTS_ROOT

PROJECT_NAME = "_run_lifecycle_test"


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _short_project(clean_project, max_frames=100):
    from tool.core.project import ToolProject
    project = ToolProject.create(PROJECT_NAME)
    project.config = dataclasses.replace(
        project.config, scenario=dataclasses.replace(project.config.scenario, max_frames=max_frames))
    project.save()
    return project


def _play_and_wait(window, timeout_ms=120_000):
    loop = QEventLoop()
    finished = {"info": None}
    real_on_finished = window._on_run_finished

    def wrapped(info):
        real_on_finished(info)
        finished["info"] = info
        loop.quit()

    window._on_run_finished = wrapped
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)

    window.play()
    loop.exec()
    return finished["info"]


def test_plots_are_populated_after_a_live_run_finishes(qtbot, clean_project):
    from tool.ui.main_window import MainWindow
    project = _short_project(clean_project)
    window = MainWindow(project)
    qtbot.addWidget(window)

    info = _play_and_wait(window)
    assert info is not None, "run never finished (or the safety timeout fired first)"

    xd, _yd = window.run_tab.plots._curves["mario_x"].getData()
    assert xd is not None and len(xd) > 0, (
        "the Plots tab was never fed the just-finished run's own telemetry"
    )
    window.save()


def test_progress_bar_reads_100_when_a_run_finishes(qtbot, clean_project):
    from tool.ui.main_window import MainWindow
    project = _short_project(clean_project)
    window = MainWindow(project)
    qtbot.addWidget(window)

    info = _play_and_wait(window)
    assert info is not None
    assert window.run_tab.progress.value() == 100
    window.save()


def test_preview_keeps_its_last_frame_after_a_run_finishes(qtbot, clean_project):
    from tool.ui.main_window import MainWindow
    project = _short_project(clean_project)
    window = MainWindow(project)
    qtbot.addWidget(window)

    info = _play_and_wait(window)
    assert info is not None
    pixmap = window.run_tab.preview.frame_label.pixmap()
    assert pixmap is not None and not pixmap.isNull(), (
        "the preview's last frame should still be showing once the run is over"
    )
    window.save()


def test_cancelled_run_is_marked_in_index_and_note(qtbot, clean_project):
    from tool.ui.main_window import MainWindow
    from tool.core.run_store import list_runs

    project = _short_project(clean_project, max_frames=100_000)  # long enough to reliably cancel mid-run
    window = MainWindow(project)
    qtbot.addWidget(window)

    loop = QEventLoop()
    finished = {"info": None}
    real_on_finished = window._on_run_finished

    def wrapped(info):
        real_on_finished(info)
        finished["info"] = info
        loop.quit()

    window._on_run_finished = wrapped

    frames_seen = []
    real_show_frame = window.run_tab.preview.show_frame

    def counting_show_frame(obs, row):
        frames_seen.append(row.get("frame"))
        real_show_frame(obs, row)
        if len(frames_seen) == 3:  # cancel shortly after a few real frames have streamed
            window.cancel()

    window.run_tab.preview.show_frame = counting_show_frame

    safety = QTimer()
    safety.setSingleShot(True)
    safety.timeout.connect(loop.quit)
    safety.start(120_000)

    window.play()
    loop.exec()

    assert finished["info"] is not None, "run never finished (or the safety timeout fired first)"
    assert finished["info"].get("cancelled") is True
    assert finished["info"]["n_frames"] < 100_000, "a cancelled run must stop well short of max_frames"

    entries = list_runs(PROJECT_NAME)
    assert entries[-1]["summary"]["cancelled"] is True

    slug = entries[-1]["slug"]
    note_path = PROJECTS_ROOT / PROJECT_NAME / "runs" / f"{slug}.md"
    assert "CANCELLED" in note_path.read_text(encoding="utf-8")
    assert "CANCELLED" in window.run_tab.result_label.text()
    window.save()


def test_batch_stats_exclude_cancelled_runs(qtbot):
    from types import SimpleNamespace
    from PySide6.QtWidgets import QLabel
    from tool.ui.tabs.run import RunTab

    class _FakeResult:
        fitnesses = [10.0, 999.0, 20.0]
        infos = [{"cancelled": False}, {"cancelled": True}, {"cancelled": False}]

    # show_batch_result only touches self.batch_label -- no need to build
    # a full RunTab (and the MainWindow it requires) just to test it.
    fake_self = SimpleNamespace(batch_label=QLabel())
    RunTab.show_batch_result(fake_self, _FakeResult())

    text = fake_self.batch_label.text()
    summary_line = text.strip().split("\n")[-1]
    assert "999.0" not in summary_line, "the excluded run's fitness leaked into the summary line"
    assert "mean=15.0" in text  # (10+20)/2, the 999.0 cancelled outlier excluded
    assert "1 cancelled" in text
