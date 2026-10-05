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
    assert tab.table.rowCount() == 11
    assert tab.selected().id == "E1"
    html = tab.detail.toHtml()
    assert "e1_goomba_approach" in html and "feature-level (D1)" in html and "Ache et al. 2019" in html
    assert tab.run_real_button.isEnabled() and tab.run_shuffled_button.isEnabled()
    assert tab.seed_spin.value() == 9100 and not 3000 <= tab.seed_spin.value() <= 3019       # Run default is a development seed
    assert "held-out, run once" in _tab(window, "results").run_button.text()
    assert not [b for b in tab.findChildren(type(tab.run_real_button)) if "lesion" in b.text().lower()]
    tab.table.selectRow(2)                        # E2a: runnable (docs/SPEC_e2a.md), labelled as a Mario's-eye-view assumption
    assert tab.selected().id == "E2a" and tab.run_real_button.isEnabled() and "Mario's-eye-view assumption" in tab.detail.toHtml().replace("&#39;", "'")
    tab.table.selectRow(3)                        # E2b: planned, nothing to run
    assert tab.selected().id == "E2b" and not tab.run_real_button.isEnabled()
    from PySide6.QtWidgets import QAbstractItemView
    assert tab.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers


def test_mechanisms_library_labels_each_mechanisms_input_tier(window):
    tab = _tab(window, "mechanisms")
    assert tab.table.rowCount() == 10
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


# ---- Phase 3 (docs/SPEC_phase3.md): E0 / E3 in the tool, Mechanisms settings ------------------------------------------------------
def _fake_goal_eval(experiment="E0"):
    def arm(k):
        return {"n": 20, "reached": k, "reached_ci": [0.1, 0.3], "deaths": 0, "timeouts": 20 - k, "lost": 0, "collected": 0,
                "gf_fired": 3 if k == 0 else 0, "a_pressed_runs": 0, "gf_output_max_hz": 6.0 if k == 0 else 0.0, "ttmn_max_hz": 0.07,
                "frames_to_reach": {"n": k, "median": 135.0 if k else None}, "left_frames_mean": 600.0 if k == 0 else 0.0, "max_x_median": 40.0}
    ep = {"experiment": experiment, "arm": "real", "seed": 4000, "shuffle_seed": None, "reached": True, "outcome": "reached", "died": False,
          "frames": 135, "reached_frame": 135, "max_x": 402, "gf_fired": False, "first_gf_frame": None, "gf_output_max_hz": 0.0,
          "ttmn_max_hz": 0.009, "a_pressed": False, "a_frames": 0, "left_frames": 0, "right_frames": 135, "b_frames": 135, "collected": False}
    return {"experiment": experiment, "metric": "reached world x 400 within 600 frames", "seeds": [4000, 4019], "max_frames": 600,
            "scene": {"id": "e0_walk_goal", "scene_hash": "abc"}, "stamp": {"build_hash": "h", "neurons": 16464, "calibration_hash": "c",
                                                                           "senses": {"pursuit_kinds": [], "goal_cue_salience": 15.0}},
            "criterion": {"real_reached_min": 18, "shuffled_reached_max": 2, "n": 20},
            "arms": ["real", "shuffled", "shuffled_class", "real_no_landmark"], "real": arm(19), "shuffled": arm(0), "shuffled_class": arm(0),
            "real_no_landmark": arm(0),
            "episodes": [ep, {**ep, "arm": "shuffled", "reached": False, "outcome": "timeout", "reached_frame": None},
                         {**ep, "arm": "shuffled_class", "reached": False, "outcome": "timeout", "reached_frame": None},
                         {**ep, "arm": "real_no_landmark", "reached": False, "outcome": "timeout", "reached_frame": None}]}


def test_results_shows_an_e0_evaluation_with_gf_and_ttmn_fields_for_every_arm(window):
    from tool.core.brain_runner import save_brain_eval
    from tool.ui.tabs import results
    save_brain_eval(PROJECT_NAME, _fake_goal_eval())
    tab = _tab(window, "results")
    tab.refresh()
    assert tab.summary_table.rowCount() == 4 and tab.summary_table.item(2, 0).text().startswith("shuffled_class")
    assert tab.summary_table.item(3, 0).text() == "real_no_landmark (control)"           # control-only, labelled like the lesion arm
    headers = [tab.summary_table.horizontalHeaderItem(c).text() for c in range(tab.summary_table.columnCount())]
    assert "GF crossed threshold" in headers and "GF output / TTMn max (Hz)" in headers
    assert tab.summary_table.item(1, 8).text() == "6.00 / 0.070" and tab.summary_table.item(0, 1).text() == "19/20"
    assert "met" in tab.criterion_label.text() and "not met" not in tab.criterion_label.text()
    assert tab.episode_table.rowCount() == 4 and "E0" in tab.header_label.text() and "senses" in tab.header_label.text()
    tab.experiment_combo.setCurrentText("E3")
    assert "5100-5119" in tab.run_button.text() and "held-out, run once" in tab.run_button.text()
    bad = _fake_goal_eval()
    bad["real"]["reached"] = 5
    assert "not met" in results.criterion_text(bad)


def test_e1_results_still_show_the_gf_and_ttmn_columns(window):
    from tool.core.brain_runner import save_brain_eval
    save_brain_eval(PROJECT_NAME, _fake_eval())
    tab = _tab(window, "results")
    tab.refresh()
    headers = [tab.summary_table.horizontalHeaderItem(c).text() for c in range(tab.summary_table.columnCount())]
    assert "GF crossed threshold" in headers and "GF output / TTMn max (Hz)" in headers


def test_experiments_tab_runs_e0_and_e3_and_keeps_the_development_seed(window):
    tab = _tab(window, "experiments")
    for row, eid in ((0, "E0"), (4, "E3")):
        tab.table.selectRow(row)
        assert tab.selected().id == eid and tab.run_real_button.isEnabled()
        assert eid in tab.run_real_button.text() and eid in tab.run_shuffled_button.text()
    assert tab.seed_spin.value() == 9100
    assert "landmark" in tab.run_note.text() and tab.class_check.text().startswith("class-preserving")


def test_mechanisms_tab_has_the_per_object_pursuit_setting_and_the_landmark_strength(window):
    from brain import calibration as C
    from tool.core.brain_runner import load_sense_settings
    tab = _tab(window, "mechanisms")
    assert set(tab.kind_checks) == {"goomba", "koopa", "enemy", "powerup"}
    assert tab.kind_checks["powerup"].isChecked() and not tab.kind_checks["goomba"].isChecked()      # Goomba NOT pursued by default
    assert tab.landmark_spin.value() == C.GOAL_CUE_SALIENCE
    tab.kind_checks["goomba"].setChecked(True)
    tab.landmark_spin.setValue(9.5)
    assert tab.arousal_spin.value() == C.PURSUIT_AROUSAL and (tab.arousal_spin.minimum(), tab.arousal_spin.maximum()) == (0.0, 1.0)
    tab.arousal_spin.setValue(0.4)
    saved = load_sense_settings(PROJECT_NAME)
    assert set(saved.pursuit_kinds) == {"powerup", "goomba"} and saved.goal_cue_salience == 9.5 and saved.pursuit_arousal == 0.4
    assert tab.settings() == saved
    html = tab.detail.toHtml()
    tab.table.selectRow(next(i for i, m in enumerate(__import__("brain.library", fromlist=["x"]).MECHANISMS) if m.id == "goal_direction"))
    text = tab.detail.toPlainText()
    assert "does not remove it" in text and "invented" in text                                         # the honest label
    tab.table.selectRow(2)
    assert "no innate effect" in tab.detail.toPlainText().lower() or "no innate effect" in tab.table.item(2, 0).text().lower()


def test_goal_run_note_is_auto_filled(clean_project):
    from tool.core.brain_runner import write_brain_run_note
    e = {"experiment": "E0", "arm": "shuffled", "shuffle_seed": 1, "frames": 600, "outcome": "timeout", "reached": False,
         "reached_frame": None, "max_x": 40, "gf_fired": True, "first_gf_frame": 50, "gf_output_max_hz": 6.0, "ttmn_max_hz": 0.073,
         "a_pressed": False, "a_frames": 0, "left_frames": 600, "right_frames": 0, "b_frames": 600}
    text = write_brain_run_note(PROJECT_NAME, 2, "002_e0_shuffled_seed9100", 9100, {"experiment": "E0", "episode": e}).read_text(encoding="utf-8")
    assert "fill in" not in text and "E0 walk to the goal" in text and "Left pressed 600" in text and "6.00 Hz" in text


@needs_net
def test_an_e0_run_is_recorded_and_loads_in_the_watch_tab(window):
    from tool.core.brain_runner import run_brain_one, write_brain_run_note
    from tool.core.run_store import list_runs, record_run
    slug = "001_e0_real_seed9100"
    tel, info, spec = run_brain_one(PROJECT_NAME, slug, 9100, None, experiment="E0")
    assert spec["kind"] == "brain_e0" and info["episode"]["reached"] and info["actions_prefix_len"] == 0
    assert {"arousal", "pursuit_az"} <= set(tel.columns)
    record_run(PROJECT_NAME, 1, slug, 9100, info, spec)
    write_brain_run_note(PROJECT_NAME, 1, slug, 9100, info)
    window.run_tab.refresh_history(list_runs(PROJECT_NAME))
    window.load_history_run(list_runs(PROJECT_NAME)[0])
    assert window.run_tab.player._n_frames == len(tel)


def test_results_shows_a_b11_baseline_evaluation_without_a_criterion(window):
    from tool.core.brain_runner import save_brain_eval
    arm = {"n": 20, "max_x_mean": 400.0, "max_x_mean_ci": [350.0, 450.0], "max_x_median": 390.0, "max_x_min": 100, "max_x_max": 900,
           "level_complete": 0, "level_complete_ci": [0.0, 0.16], "end_reasons": {"died_enemy": 18, "stuck": 2},
           "goombas_encountered": 20, "goombas_jumped": 5, "episodes_with_a_jump": 5, "a_episodes": 10, "tap_episodes": 4,
           "tap_fraction": 0.4, "tap_ci": [0.2, 0.6], "a_run_hist": {"1": 3}, "a_runs_total": 3, "powerup_released_runs": 1,
           "collected": 1, "collected_ci": [0.0, 0.2], "gf_fired": 10, "gf_output_max_hz": 12.0, "ttmn_max_hz": 0.3, "frames_median": 300.0}
    ep = {"experiment": "B11", "arm": "real", "seed": 6000, "outcome": "died_enemy", "frames": 300, "max_x": 400, "goombas_jumped": 1,
          "goombas_encountered": 1, "first_a_run": 3, "collected": False, "powerup_released": False, "gf_output_max_hz": 12.0, "ttmn_max_hz": 0.3}
    res = {"experiment": "B11", "metric": "m", "seeds": [6000, 6019], "max_frames": 3000, "stuck_frames": 300, "tap_max_frames": 2,
           "scene": {"id": "b11_baseline", "scene_hash": "abc"}, "stamp": {"build_hash": "h", "neurons": 16464, "calibration_hash": "c", "senses": {}},
           "criterion": None, "arms": ["real", "shuffled", "shuffled_class"], "real": arm, "shuffled": arm, "shuffled_class": arm, "episodes": [ep]}
    save_brain_eval(PROJECT_NAME, res)
    tab = _tab(window, "results")
    tab.refresh()
    assert tab.summary_table.rowCount() == 3 and tab.summary_table.item(0, 1).text() == "400 (350-450)"
    assert tab.summary_table.item(0, 4).text() == "5 / 20" and tab.summary_table.item(0, 5).text() == "4/10"
    assert "not a criterion" in tab.criterion_label.text() and "no pass/fail" in tab.criterion_label.text()
    assert tab.episode_table.rowCount() == 1 and "B11" in tab.header_label.text()
    tab.experiment_combo.setCurrentText("B11")
    assert "6100-6119" in tab.run_button.text()


def test_experiments_tab_lists_the_b11_baseline_as_runnable_with_honest_labels(window):
    from brain.library import experiment
    e = experiment("B11")
    assert e.status == "runnable" and e.runner == "brain.baseline" and set(e.mechanisms) == {"looming", "pursuit", "goal_direction", "expanding_obstacle"}
    assert "no pass/fail" in e.criterion and "invented world cue" in e.controls
    tab = _tab(window, "experiments")
    row = next(r for r in range(tab.table.rowCount()) if tab.table.item(r, 0).text() == "B11")
    tab.table.selectRow(row)
    assert tab.selected().id == "B11" and tab.run_real_button.isEnabled() and "B11" in tab.run_real_button.text()


def test_results_tab_shows_an_e2a_evaluation_minimally(window):
    from brain import e2a
    arm = {"n": 20, "cleared": 15, "cleared_ci": [0.5, 0.9], "end_reasons": {"cleared": 15, "died": 0, "stuck": 5, "timeout": 0},
           "gf_fired": 20, "gf_before_face": 20, "a_pressed_runs": 20, "tap_episodes": 2, "tap_fraction": 0.1,
           "first_a_x_median": 425.0, "takeoff_x_median": 426.0, "gf_output_max_hz": 12.0, "ttmn_max_hz": 0.3}
    ep = {"arm": "real", "seed": 7100, "outcome": "cleared", "cleared": True, "frames": 90, "max_x": 500, "gf_before_face": True,
          "first_a_x": 425, "first_a_run": 9, "takeoff_x": 426}
    res = {"experiment": "E2a", "metric": e2a.METRIC, "seeds": [7100, 7119], "max_frames": 600, "scene": {"id": "e2a_pipe1", "scene_hash": "x"},
           "stamp": {"build_hash": "h", "neurons": 1, "calibration_hash": "c", "senses": {}}, "criterion": dict(e2a.CRITERION),
           "arms": ["real", "shuffled", "real_no_obstacle"], "real": arm, "shuffled": {**arm, "cleared": 0}, "real_no_obstacle": {**arm, "cleared": 0},
           "episodes": [ep]}
    from tool.ui.tabs import results
    assert results.summary_rows(res)[0][:2] == ["real", "15/20"] and results.summary_rows(res)[2][0] == "real_no_obstacle (control)"
    assert "met" in results.criterion_text(res) and "not met" not in results.criterion_text(res) and "Mario's-eye-view" in results.criterion_text(res)
    assert results.EVAL_SEEDS["E2a"] == (7100, 7119) and "E2a" in results.EVAL_EXPERIMENTS
    from tool.core.brain_runner import RUNNABLE
    assert "E2a" in RUNNABLE
