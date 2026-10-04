"""docs/SPEC_tool_phase2.md section 8: the Experiments / Mechanisms libraries, the Results screen and the brain run path
(a recorded E1 episode loads in the Watch tab). Episode tests need the cached network and skip with a reason otherwise."""
from __future__ import annotations

import shutil

import pytest

from brain import builder
from brain.calibration import CALIBRATION_FILE
from config.output_routing import PROJECTS_ROOT

PROJECT_NAME = "_brain_tool_test"
needs_net = pytest.mark.skipif(not builder.default_path().exists() or not CALIBRATION_FILE.exists(),
                               reason="unified network or calibration not built")


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def window(qtbot, clean_project):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow
    w = MainWindow(ToolProject.create(PROJECT_NAME))
    qtbot.addWidget(w)
    return w


def _tab(window, tab_id):
    index, _ = window._tab_factories[tab_id]
    return window.tabs.widget(index)


def _fake_eval():
    def arm(k, g):
        return {"n": 20, "survived": k, "survived_ci": [0.1, 0.3], "deaths": 20 - k, "timeouts": 0, "gf_before_contact": g,
                "gf_before_contact_ci": [0.1, 0.3], "gf_fired": g, "a_pressed_runs": g,
                "theta_at_gf_deg": {"n": g, "median": 41.0 if g else None, "min": 40.0, "max": 42.0},
                "distance_at_gf_px": {"n": g, "median": 21.0 if g else None}, "gf_output_max_hz": 60.0 if g else 0.0,
                "ttmn_max_hz": 30.0 if g else 0.0}
    ep = {"arm": "real", "seed": 3000, "shuffle_seed": None, "survived": True, "outcome": "passed", "died": False, "frames": 200,
          "contact_frame": None, "resolved_frame": 140, "gf_fired": True, "first_gf_frame": 100, "gf_before_contact": True,
          "theta_at_gf_deg": 41.0, "distance_at_gf_px": 21.0, "a_pressed": True, "a_frames": 3, "max_x": 226}
    return {"experiment": "E1", "seeds": [3000, 3019], "max_frames": 600, "grace_frames": 60,
            "scene": {"id": "e1_goomba_approach", "scene_hash": "abc"},
            "stamp": {"build_hash": "h", "neurons": 15551, "calibration_hash": "c"},
            "criterion": {"real_survived_min": 16, "shuffled_survived_max": 2, "n": 20},
            "arms": ["real", "shuffled", "lesion_gf"],
            "real": arm(17, 18), "shuffled": arm(1, 0), "lesion_gf": arm(0, 18),
            "episodes": [ep, {**ep, "arm": "shuffled", "survived": False, "outcome": "died", "theta_at_gf_deg": None,
                              "distance_at_gf_px": None}, {**ep, "arm": "lesion_gf", "survived": False, "outcome": "died"}]}


def test_experiments_library_lists_the_ladder_read_only_with_provenance(window):
    tab = _tab(window, "experiments")
    assert tab.table.rowCount() == 10
    assert tab.selected().id == "E1"
    html = tab.detail.toHtml()
    assert "e1_goomba_approach" in html and "feature-level (D1)" in html and "Ache et al. 2019" in html
    assert tab.run_real_button.isEnabled() and tab.run_shuffled_button.isEnabled()
    assert tab.seed_spin.value() == 9100 and not 3000 <= tab.seed_spin.value() <= 3019       # Run default is a development seed
    assert "held-out, run once" in _tab(window, "results").run_button.text()
    assert not [b for b in tab.findChildren(type(tab.run_real_button)) if "lesion" in b.text().lower()]
    tab.table.selectRow(2)                        # E2a: planned, nothing to run
    assert tab.selected().id == "E2a" and not tab.run_real_button.isEnabled()
    from PySide6.QtWidgets import QAbstractItemView
    assert tab.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers


def test_mechanisms_library_labels_each_mechanisms_input_tier(window):
    tab = _tab(window, "mechanisms")
    assert tab.table.rowCount() == 9
    html = tab.detail.toHtml()
    assert "LPLC2" in html and "feature-level (D1)" in html and "E1" in html
    tab.table.selectRow(2)
    assert "receptor" in tab.detail.toHtml()


def test_results_screen_shows_real_vs_shuffled_and_the_plan_criterion(window):
    from tool.core.brain_runner import save_brain_eval
    from tool.ui.tabs import results
    save_brain_eval(PROJECT_NAME, _fake_eval())
    tab = _tab(window, "results")
    tab.refresh()
    assert tab.summary_table.item(0, 0).text() == "real" and tab.summary_table.item(0, 1).text() == "17/20"
    assert tab.summary_table.item(1, 0).text() == "shuffled" and tab.summary_table.item(1, 1).text() == "1/20"
    assert tab.summary_table.rowCount() == 3 and tab.summary_table.item(2, 0).text() == "lesion_gf (control)"
    assert tab.summary_table.item(2, 1).text() == "0/20" and tab.summary_table.item(2, 9).text() == "60.00 / 30.000"
    assert tab.episode_table.rowCount() == 3 and tab.episode_table.item(2, 0).text() == "lesion_gf (control)"
    assert "met" in tab.criterion_label.text() and "not met" not in tab.criterion_label.text()
    bad = _fake_eval()
    bad["real"]["survived"] = 3
    assert "not met" in results.criterion_text(bad)


def test_run_note_is_auto_filled_not_a_placeholder(clean_project):
    from tool.core.brain_runner import write_brain_run_note
    e = {"arm": "real", "shuffle_seed": None, "frames": 200, "outcome": "stomped", "survived": True, "gf_before_contact": True,
         "gf_fired": True, "first_gf_frame": 100, "theta_at_gf_deg": 41.0, "distance_at_gf_px": 21.0, "a_pressed": True, "a_frames": 12}
    text = write_brain_run_note(PROJECT_NAME, 1, "001_e1_real_seed9100", 9100, {"e1": e}).read_text(encoding="utf-8")
    assert "fill in" not in text and "fired at frame 100, before contact" in text and "A was held 12 frames" in text


def test_the_legacy_runner_is_not_touched_by_the_brain_path():
    import tool.core.runner as legacy
    src = open(legacy.__file__, encoding="utf-8").read()
    assert "from brain" not in src and "import brain" not in src and "brain_runner" not in src


@needs_net
def test_a_brain_run_is_recorded_and_loads_in_the_watch_tab(window):
    from tool.core.brain_runner import run_brain_one, write_brain_run_note
    from tool.core.run_store import list_runs, record_run
    slug = "001_e1_real_seed9100"
    tel, info, spec = run_brain_one(PROJECT_NAME, slug, 9100, None)
    root = PROJECTS_ROOT / PROJECT_NAME
    assert (root / "telemetry" / f"{slug}_telemetry.csv").exists() and (root / "runs" / f"{slug}_raw.npz").exists()
    assert info["n_frames"] == len(tel) and info["e1"]["arm"] == "real" and spec["kind"] == "brain_e1"
    import numpy as np
    actions = np.load(info["actions_path"])
    assert len(actions) == info["actions_prefix_len"] + len(tel) and info["actions_prefix_len"] == 110
    record_run(PROJECT_NAME, 1, slug, 9100, info, spec)
    write_brain_run_note(PROJECT_NAME, 1, slug, 9100, info)
    window.run_tab.refresh_history(list_runs(PROJECT_NAME))
    entry = list_runs(PROJECT_NAME)[0]
    window.load_history_run(entry)
    assert window.run_tab.player._n_frames == len(tel)
    assert window.run_tab.player.current_action() is not None


@needs_net
def test_the_run_button_plays_an_episode_in_a_child_process_and_shows_it_in_watch(qtbot, window):
    """The real path: Experiments -> Run -> child process -> live preview -> recorded run loaded in the Run tab."""
    from tool.core.run_store import list_runs
    tab = _tab(window, "experiments")
    tab.seed_spin.setValue(9100)
    tab.run_real_button.click()
    assert window.brain_runs.run_active()
    assert window.tabs.currentWidget() is window.run_tab
    qtbot.waitUntil(lambda: not window.brain_runs.run_active() and len(list_runs(PROJECT_NAME)) == 1, timeout=180_000)
    entry = list_runs(PROJECT_NAME)[0]
    assert entry["run_spec"]["kind"] == "brain_e1" and entry["summary"]["e1"]["arm"] == "real"
    assert window.run_tab.player._n_frames == entry["summary"]["n_frames"]
    assert "E1" in window.run_tab.result_label.text()


@needs_net
def test_the_results_evaluation_runs_in_a_child_process_and_is_saved(qtbot, window):
    """Same code path as the Results button (here with 1 seed, not 20) -> brain_eval.json -> the table."""
    from tool.core.brain_runner import load_brain_evals
    tab = _tab(window, "results")
    assert window.brain_runs.start_eval(n=1, seed0=9100)
    qtbot.waitUntil(lambda: not window.brain_runs.eval_active() and len(load_brain_evals(PROJECT_NAME)) == 1, timeout=300_000)
    qtbot.waitUntil(lambda: tab.summary_table.item(0, 0) is not None, timeout=10_000)
    assert tab.summary_table.item(0, 1).text().endswith("/1") and tab.summary_table.item(1, 0).text() == "shuffled"
    assert tab.summary_table.rowCount() == 3 and tab.summary_table.item(2, 0).text() == "lesion_gf (control)"
