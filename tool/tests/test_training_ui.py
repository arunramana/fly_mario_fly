"""The training-facing UI: dropdown grouping, Learning chart, Circuits module
toggles, Goal tab Train controls, and the "telemetry only" player message."""
from __future__ import annotations

import shutil

from config.output_routing import PROJECTS_ROOT
from tool.ui.widgets.learning_chart import LearningChart, collect_series, rolling_mean
from tool.ui.widgets.run_picker import RunPicker, label_for

NAME = "_training_ui_test"


def _t(n, network, ep, max_x, died=True, flag=False, frames=False):
    return {"number": n, "seed": 0, "group": (
                "Baseline" if network == "baseline" else
                "Training · real" if network == "real" else f"Training · {network}"),
            "summary": {"died_or_flagged": died, "max_x_abs": max_x,
                        "raw_frames_path": "x.npz" if frames else None},
            "training": {"network": network, "episode": ep, "max_x": max_x, "died": died, "flag": flag}}


ENTRIES = [
    {"number": 1, "seed": 0, "summary": {"died_or_flagged": True, "max_x_abs": 50.0}},
    _t(2, "baseline", -1, 100),
    _t(3, "real", 0, 300, frames=True),
    _t(4, "real", 1, 500, died=False),
    _t(5, "shuffled 1", 0, 120),
    _t(6, "shuffled 2", 0, 90, flag=True),
]


def test_training_labels_show_episode_max_x_and_outcome():
    assert label_for(ENTRIES[2]) == "#3 · ep 0 · x 300 · died"
    assert label_for(ENTRIES[3]) == "#4 · ep 1 · x 500 · survived · telemetry only"
    assert label_for(ENTRIES[5]).startswith("#6 · ep 0 · x 90 · flag")
    assert label_for(ENTRIES[1]).startswith("#2 · baseline")


def test_dropdown_groups_real_then_shuffled(qapp):
    picker = RunPicker()
    picker.set_entries(ENTRIES)
    texts = [picker.combo.itemText(i) for i in range(picker.combo.count())]
    headers = [t for t in texts if t.startswith("──")]
    assert headers == ["── Training · real ──", "── Training · shuffled 1 ──", "── Training · shuffled 2 ──"]
    assert texts[0].startswith("#2") and texts[1].startswith("#1")        # baseline + plain runs first
    assert texts.index("── Training · real ──") < texts.index("── Training · shuffled 1 ──")


def test_chart_series_rolling_mean_and_click(qapp):
    series, baseline = collect_series(ENTRIES)
    assert baseline == 100
    assert series["real"] == [(0, 300, 3), (1, 500, 4)]
    assert set(series) == {"real", "shuffled 1", "shuffled 2"}
    assert rolling_mean([1, 3, 5], window=2) == [1, 2, 4]
    chart = LearningChart()
    chart.set_entries(ENTRIES)
    got = []
    chart.point_selected.connect(got.append)
    chart._on_clicked(None, [type("P", (), {"data": lambda self: 4})()])
    assert got == [4]


def test_circuits_toggles_survive_a_scalar_edit(qtbot):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    try:
        window = MainWindow(ToolProject.create(NAME))
        qtbot.addWidget(window)
        window._closing_confirmed = True  # skip the unsaved-changes prompt on teardown
        circuits = window.tabs.widget(3)
        for field in ("page_perception", "gap_ahead", "motor_direct", "mbon_readout"):
            assert getattr(window.get_config().modules, field) is None
            circuits.module_checkboxes[field].setChecked(True)
            assert getattr(window.get_config().modules, field) is not None
        circuits.module_checkboxes["motor_direct"].setChecked(False)
        assert window.get_config().modules.motor_direct is None
        # a later scalar edit through the ParamForm must not undo the toggles
        circuits.param_form._on_change("noise.sigma", 0.05)
        assert window.get_config().noise.sigma == 0.05
        assert window.get_config().modules.mbon_readout is not None
    finally:
        shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def test_goal_tab_train_controls_write_training_settings(qtbot):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    try:
        window = MainWindow(ToolProject.create(NAME))
        qtbot.addWidget(window)
        window._closing_confirmed = True  # skip the unsaved-changes prompt on teardown
        goal = window.goal_tab
        goal.train_episodes_spin.setValue(12)
        goal.train_frame_cap_spin.setValue(500)
        goal.train_lr_spin.setValue(0.002)
        goal.train_event_checkbox.setChecked(True)
        goal.train_shuffled_checkbox.setChecked(True)
        t = window.get_tool_settings().training
        assert (t.episodes, t.frame_cap, t.learning_rate, t.event_proximal, t.include_shuffled) == (
            12, 500, 0.002, True, True)
        goal.set_training_state(True, "x")
        assert not goal.train_button.isEnabled() and goal.train_cancel_button.isEnabled()
        assert goal.train_checkpoint_combo.itemText(0) == "fresh weights"
    finally:
        shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def test_player_says_telemetry_only(qapp):
    import pandas as pd
    from tool.ui.widgets.run_player import RunPlayer
    player = RunPlayer()
    player.load_run(None, pd.DataFrame({"frame": [0, 1]}), {"telemetry_only": True})
    assert player.canvas._placeholder.startswith("Telemetry only")
    assert player.readout_label.text() == "telemetry only"


def test_train_button_runs_in_background_and_updates_chart_live(qtbot):
    from tool.core.project import ToolProject
    from tool.core.tool_settings import TrainingSettings
    from tool.ui.main_window import MainWindow
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    try:
        base = ToolProject.open("win_attempt")
        window = MainWindow(base.duplicate(NAME))
        qtbot.addWidget(window)
        window._closing_confirmed = True
        window.set_tool_settings(__import__("dataclasses").replace(
            window.get_tool_settings(), training=TrainingSettings(episodes=2, frame_cap=60)))
        window.start_training()
        assert window.training_active()
        qtbot.waitUntil(lambda: not window.training_active() and window._train_process is None,
                        timeout=240_000)
        assert window.goal_tab.train_button.isEnabled()
        series = window.run_tab.learning.series()
        assert [p[0] for p in series["real"]] == [0, 1]
        assert window.run_tab.learning.baseline() is not None
        assert window.goal_tab.train_status.text() == "done"
    finally:
        shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def test_run_033_appears_and_loads_in_the_player(qtbot):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow
    window = MainWindow(ToolProject.open("win_attempt"))
    qtbot.addWidget(window)
    window._closing_confirmed = True
    picker = window.run_tab.playlist
    assert picker.select_number(33)
    window.select_history_run(33)
    assert window.run_tab.player._n_frames > 1000          # its frames and telemetry loaded
    assert "flag" in window.run_tab.result_label.text() or "max_x=3157" in window.run_tab.result_label.text()


def test_module_parameters_are_editable_only_while_on_with_tooltips(qtbot):
    from tool.core.project import ToolProject
    from tool.ui.main_window import MainWindow
    from tool.ui.tabs.circuits import MODULE_PARAM_UI
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    try:
        window = MainWindow(ToolProject.create(NAME))
        qtbot.addWidget(window)
        window._closing_confirmed = True
        c = window.tabs.widget(3)
        assert c.module_editor_boxes["motor_direct"].isHidden()
        c.module_checkboxes["motor_direct"].setChecked(True)
        assert not c.module_editor_boxes["motor_direct"].isHidden()
        c.module_editors[("motor_direct", "a_threshold")].setValue(1.5)
        assert window.get_config().modules.motor_direct.a_threshold == 1.5
        c.module_editors[("motor_direct", "release_on_landing")].setChecked(False)
        assert window.get_config().modules.motor_direct.release_on_landing is False
        tip = c.module_editors[("motor_direct", "a_threshold")].toolTip()
        assert "RISE" in tip and "ttmn_press_threshold" in tip           # says what it is compared against
        for f in ("gap_ahead", "dnp02_refractory", "dnp01_refractory", "mbon_readout"):
            c.module_checkboxes[f].setChecked(True)
        c.module_editors[("dnp02_refractory", "refractory_steps")].setValue(12)
        assert window.get_config().modules.dnp02_refractory.refractory_steps == 12
        assert window.get_config().modules.dnp01_refractory.refractory_steps == 8
        for field, specs in MODULE_PARAM_UI.items():                     # every param has range + tooltip
            for name, kind, lo, hi, step, tip in specs:
                assert lo < hi and len(tip) > 40
        # the values survive an edit through the scalar form
        c.param_form._on_change("noise.sigma", 0.02)
        assert window.get_config().modules.motor_direct.a_threshold == 1.5
        c.module_checkboxes["motor_direct"].setChecked(False)
        assert c.module_editor_boxes["motor_direct"].isHidden()
    finally:
        shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def test_save_state_button_and_start_from_dropdown(qtbot):
    import numpy as np
    from tool.core.project import ToolProject
    from tool.core.savestates import FRESH_BRAIN_NOTE, list_states, save_state
    from tool.ui.main_window import MainWindow
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    try:
        window = MainWindow(ToolProject.create(NAME))
        qtbot.addWidget(window)
        window._closing_confirmed = True
        assert window.run_tab.playlist.save_state_button.text() == "Save state here"
        assert FRESH_BRAIN_NOTE in window.run_tab.playlist.save_state_button.toolTip()
        goal = window.goal_tab
        assert goal.start_state_combo.itemText(0) == "power-on"
        save_state(NAME, "demo", np.zeros(5, dtype=np.uint8), "1-1", 5)
        goal.refresh_states()
        assert goal.start_state_combo.findData("demo") > 0
        goal.start_state_combo.setCurrentIndex(goal.start_state_combo.findData("demo"))
        assert window.get_tool_settings().experiment.start_state == "demo"
        goal.start_state_combo.setCurrentIndex(0)
        assert window.get_tool_settings().experiment.start_state is None
        assert list_states(NAME) == ["demo"]
    finally:
        shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
