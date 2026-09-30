# What this file does, in plain English:
# Checks the tool half of "learning v3" (docs/SPEC_learning_v3.md): choosing
# Luigi recolours only Mario's sprite -- in the live preview and in replay --
# even after the screen has scrolled; the training curriculum of start states;
# the cleared-gap weight and start-state list in the Goal tab; and the new
# Circuits controls (muscles, adaptation, gap/speed inputs, readout cap 1.0).
"""tool/tests/test_learning_v3_tool.py -- B8 (Luigi) and A3/A5/A6/A7's tool side."""

from __future__ import annotations

import shutil

import numpy as np
import pytest

from config.output_routing import PROJECTS_ROOT
from tool.core.project import ToolProject
from tool.core.tool_settings import ToolSettings, TrainingSettings, from_json
from tool.core.training import POWER_ON, pick_start_state, run_training

NAME = "_learning_v3_test"


@pytest.fixture()
def project():
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    p = ToolProject.open("win_attempt").duplicate(NAME)
    yield p
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


# ---- B8: Luigi ---------------------------------------------------------------------

def _scrolled_frame():
    """A real 1-1 frame after the screen has started scrolling (RAM 0x0086 no longer equals where
    Mario is drawn), with the two positions."""
    import setuptools  # noqa: F401
    from mario.actions.actions import action_index
    from mario.emulator.env import make_env
    env = make_env("1-1")
    env.reset()
    ram = env.unwrapped.ram
    obs = None
    for _ in range(70):
        obs, _r, done, _i = env.step(action_index("R", False, True))
        assert not done
    out = (obs.copy(), int(ram[0x0086]), int(ram[0x03AD]), int(ram[0x03B8]))
    env.close()
    return out


def test_luigi_recolours_marios_drawn_sprite_after_the_screen_scrolls():
    from tool.core.palette import apply
    frame, page_x, screen_x, y = _scrolled_frame()
    assert abs(page_x - screen_x) > 30, "the screen must have scrolled for this test to mean anything"
    luigi = apply(frame, "luigi", mario_x=screen_x, mario_y=y)
    changed = (luigi != frame).any(axis=-1)
    assert changed.any(), "Mario's sprite must change colour"
    ys, xs = np.nonzero(changed)
    # ... and only Mario's sprite: every changed pixel is inside his box, nothing else in the level.
    assert xs.min() >= screen_x - 8 and xs.max() <= screen_x + 24 + 8
    assert ys.min() >= y and ys.max() <= y + 60
    # the old anchor (RAM 0x0086) points at empty scenery once scrolling starts: nothing recoloured there
    stale = apply(frame, "luigi", mario_x=page_x, mario_y=y)
    assert (stale != frame).any(axis=-1).sum() < changed.sum()


def test_luigi_without_a_known_position_leaves_the_level_alone():
    from tool.core.palette import apply
    frame, *_ = _scrolled_frame()
    assert np.array_equal(apply(frame, "luigi"), frame)
    assert np.array_equal(apply(frame, "luigi", mario_x=100), frame)


def test_frame_store_keeps_marios_drawn_position_for_replay(tmp_path):
    from tool.core.frame_store import FrameStore, load_frames, load_mario_positions
    store = FrameStore()
    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    store.write_frame(frame, (112, 176))
    store.write_frame(frame)                      # a frame with no position
    path = store.close(tmp_path / "r.npz")
    assert load_frames(path)[0].shape[0] == 2
    assert load_mario_positions(path).tolist() == [[112, 176], [-1, -1]]
    old = tmp_path / "old.npz"
    np.savez_compressed(old, frames=np.zeros((1, 4, 4), np.uint8), palette=np.zeros((1, 3), np.uint8))
    assert load_mario_positions(old) is None      # recordings from before positions were kept


def test_player_recolours_live_and_replay_at_the_drawn_position(qtbot, tmp_path):
    from tool.core.frame_store import FrameStore
    from tool.ui.widgets.run_player import RunPlayer
    frame, _page_x, screen_x, y = _scrolled_frame()
    player = RunPlayer()
    qtbot.addWidget(player)
    player.set_player("luigi")
    player.show_frame(frame, {"frame": 1, "mario_sx": screen_x, "mario_y": y})       # live
    live = player.canvas.pixmap().toImage()
    store = FrameStore()
    store.write_frame(frame, (screen_x, y))
    path = store.close(tmp_path / "raw.npz")
    import pandas as pd
    player.load_run(str(path), pd.DataFrame({"frame": [0], "mario_x": [screen_x + 60]}), {})   # replay
    replay = player.canvas.pixmap().toImage()
    assert live.size() == replay.size() and live == replay, "live and replay must recolour identically"
    player.set_player("mario")
    player.show_frame(frame, {"frame": 1, "mario_sx": screen_x, "mario_y": y})
    assert player.canvas.pixmap().toImage() != live


# ---- A5: curriculum ---------------------------------------------------------------------

def test_pick_start_state_is_seeded_and_empty_means_power_on():
    assert pick_start_state(TrainingSettings(), 5) is None
    s = TrainingSettings(start_states=(POWER_ON, "a", "b"))
    picks = [pick_start_state(s, seed) for seed in range(40)]
    assert set(picks) == {POWER_ON, "a", "b"}                    # all get sampled
    assert picks == [pick_start_state(s, seed) for seed in range(40)]   # reproducible
    assert from_json(ToolSettings(training=s).to_json()).training.start_states == (POWER_ON, "a", "b")


def test_training_starts_episodes_from_the_sampled_state(project):
    from tool.core.run_store import list_runs
    from tool.core.savestates import save_state
    from mario.actions.actions import action_index
    save_state(NAME, "s1", [action_index("R", False, True)] * 100, "1-1", 100)
    settings = TrainingSettings(episodes=3, frame_cap=60, seed_mode="vary", seed_base=0, start_states=("s1",))
    run_training(project, settings)
    entries = [e for e in list_runs(NAME) if e.get("group") == "Training · real"]
    assert [e["training"]["start_state"] for e in entries] == ["s1"] * 3
    # an episode from the saved state starts well past power-on's first frames
    tel = __import__("pandas").read_csv(PROJECTS_ROOT / NAME / "telemetry" / f"{entries[0]['slug']}_telemetry.csv")
    assert tel["mario_x"].iloc[0] > 30    # power-on frame 0 reads x=11
    plain = [e for e in list_runs(NAME) if e.get("group") == "Baseline"]
    assert plain and "start_state" not in plain[0].get("training", {})


# ---- UI ---------------------------------------------------------------------------------

@pytest.fixture()
def window(qtbot, project):
    from tool.ui.main_window import MainWindow
    w = MainWindow(project)
    qtbot.addWidget(w)
    w._closing_confirmed = True
    return w


def test_goal_tab_gap_weight_and_start_states(window):
    from mario.actions.actions import action_index
    from tool.core.savestates import save_state
    save_state(NAME, "s1", [action_index("R", False, True)] * 5, "1-1", 5)
    goal = window.goal_tab
    goal.refresh_states()
    names = [goal.train_states_list.item(i).text() for i in range(goal.train_states_list.count())]
    assert names[0] == POWER_ON and "s1" in names
    from PySide6.QtCore import Qt
    goal.train_states_list.item(names.index("s1")).setCheckState(Qt.CheckState.Checked)
    assert window.get_tool_settings().training.start_states == ("s1",)
    goal.gap_spin.setValue(4.0)
    assert window.get_tool_settings().fitness.gap == 4.0


def test_circuits_tab_exposes_the_muscles_adaptation_and_new_inputs(window):
    circuits = window.tabs.widget(3)
    circuits._select_circuit("jump")
    circuits.module_checkboxes["motor_direct"].setChecked(True)
    for name in ("adapt_frames", "buttons", "button_decay", "down_gain", "down_threshold", "up_gain",
                 "up_threshold", "left_gain", "left_threshold", "posture_g"):
        assert ("motor_direct", name) in circuits.module_editors, name
    circuits.module_editors[("motor_direct", "down_threshold")].setValue(7.5)
    circuits.module_editors[("motor_direct", "buttons")].setChecked(True)
    md = window.get_config().modules.motor_direct
    assert md.down_threshold == 7.5 and md.buttons is True
    circuits.module_checkboxes["page_perception"].setChecked(True)
    circuits.module_editors[("page_perception", "ignore_behind")].setChecked(True)
    assert window.get_config().modules.page_perception.ignore_behind is True
    circuits._select_circuit("mushroom_body")
    circuits.module_checkboxes["mb_gap_speed_inputs"].setChecked(True)
    assert window.get_config().modules.mb_gap_speed_inputs.perceive_tiles == 8
    circuits.module_checkboxes["mbon_readout"].setChecked(True)
    assert circuits.module_editors[("mbon_readout", "mdn_frac")].maximum() == 1.0
    # recovery_rate is an ordinary ranged Mushroom body parameter (a slider in the ParamForm)
    assert "mushroom_body.recovery_rate" in circuits.param_form._widget_by_path
