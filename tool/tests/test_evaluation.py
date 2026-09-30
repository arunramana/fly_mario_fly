"""Standard eval: statistics, a tiny real-vs-shuffled run, and where the Learning tab / batch summary show it."""
from __future__ import annotations

import dataclasses
import shutil
from types import SimpleNamespace

import pytest

from config.output_routing import PROJECTS_ROOT
from tool.core.batch_summary import format_batch_result
from tool.core.evaluation import (bootstrap_ci, format_eval, load_eval_history, run_eval, summarize, wilson_ci)
from tool.core.project import ToolProject

NAME = "_eval_test"


def test_wilson_and_bootstrap_intervals():
    lo, hi = wilson_ci(0, 20)
    assert lo == 0.0 and 0.1 < hi < 0.2                      # 0/20 still allows up to ~16 %
    lo, hi = wilson_ci(10, 20)
    assert 0.29 < lo < 0.31 and 0.69 < hi < 0.71
    assert wilson_ci(0, 0) == (0.0, 0.0)
    a, b = bootstrap_ci([100, 200, 300, 400])
    assert 100 < a < 250 < b < 400 and bootstrap_ci([100, 200, 300, 400]) == (a, b)   # deterministic
    s = summarize([100, 300, 3156], [False, False, True])
    assert s["wins"] == 1 and s["n"] == 3 and s["median_max_x"] == 300


def test_batch_summary_shows_win_rate_with_ci():
    res = SimpleNamespace(fitnesses=[1.0, 2.0, 3.0], infos=[{"flag_get": True}, {"flag_get": False}, {"flag_get": False}])
    text = format_batch_result(res)
    assert "wins 1/3" in text and "95% CI" in text


@pytest.fixture()
def project():
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    p = ToolProject.open("win_attempt").duplicate(NAME)
    yield p
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def test_run_eval_real_vs_shuffled_saves_and_formats(project):
    result = run_eval(project, n=2, seed0=1000, workers=1, max_frames=80)
    assert result["seeds"] == [1000, 1001] and result["real"]["n"] == 2 and result["shuffled"]["n"] == 2
    assert load_eval_history(NAME)[-1]["real"]["max_x"] == result["real"]["max_x"]
    text = format_eval(result)
    assert "real:" in text and "shuffled:" in text and "95% CI" in text


def test_learning_tab_shows_the_latest_eval(qtbot, project):
    from tool.ui.main_window import MainWindow
    run_eval(project, n=1, seed0=1000, workers=1, max_frames=60)
    w = MainWindow(project)
    qtbot.addWidget(w)
    w._closing_confirmed = True
    w.run_tab.refresh_history([])
    assert "real:" in w.run_tab.learning.eval_label.text() and "seeds 1000-1000" in w.run_tab.learning.eval_label.text()
    assert w.run_tab.learning.eval_button.isEnabled()
