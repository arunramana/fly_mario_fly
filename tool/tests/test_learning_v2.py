# What this file does, in plain English:
# Checks the tool half of the "learning v2" sprint (docs/SPEC_learning_v2.md):
# a different noise seed per training episode, the held-out frozen test that
# feeds the Learning chart, running Play and batch from a saved brain (frozen
# unless "keep learning" is on), the power-up weight in fitness, and the new
# controls in the Goal, Circuits and Objects tabs.
"""tool/tests/test_learning_v2.py -- docs/SPEC_learning_v2.md sections 1-3 and 5's UI."""

from __future__ import annotations

import dataclasses
import shutil

import numpy as np
import pytest

from config.output_routing import PROJECTS_ROOT
from tool.core.fitness import fitness_of
from tool.core.project import ToolProject
from tool.core.run_spec import RunSpec
from tool.core.tool_settings import (ExperimentSettings, FitnessSettings, ToolSettings, TrainingSettings,
                                     from_json)
from tool.core.training import (episode_seed, list_checkpoints, load_evals, run_training,
                                save_play_checkpoint)
from tool.ui.widgets.learning_chart import collect_scores, collect_tests

NAME = "_learning_v2_test"


@pytest.fixture()
def project():
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    p = ToolProject.open("win_attempt").duplicate(NAME)
    yield p
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


# ---- 1. seeds per episode -------------------------------------------------

def test_fixed_mode_uses_the_base_seed_every_episode():
    s = TrainingSettings(seed_mode="fixed")
    assert [episode_seed(s, 7, ep) for ep in range(4)] == [7, 7, 7, 7]
    assert episode_seed(dataclasses.replace(s, seed_base=3), 7, 5) == 3


def test_vary_mode_counts_up_and_never_trains_on_a_test_seed():
    s = TrainingSettings(seed_mode="vary")
    assert [episode_seed(s, 5, ep) for ep in range(4)] == [5, 6, 7, 8]
    assert [episode_seed(dataclasses.replace(s, seed_base=0), 99, ep) for ep in range(3)] == [0, 1, 2]
    held = dataclasses.replace(s, seed_base=98, test_every=5, test_seeds=(100, 101))
    assert [episode_seed(held, 0, ep) for ep in range(5)] == [98, 99, 102, 103, 104]
    off = dataclasses.replace(held, test_every=0)   # no test set -> nothing to skip
    assert [episode_seed(off, 0, ep) for ep in range(4)] == [98, 99, 100, 101]


def test_training_settings_defaults_change_nothing_and_round_trip():
    t = TrainingSettings()
    assert (t.seed_mode, t.seed_base, t.test_every) == ("fixed", None, 0)
    assert t.test_seeds == tuple(range(100, 110))
    with pytest.raises(ValueError):
        TrainingSettings(seed_mode="random")
    saved = ToolSettings(training=TrainingSettings(seed_mode="vary", test_every=5, test_seeds=(1, 2)))
    assert from_json(saved.to_json()).training.test_seeds == (1, 2)
    assert from_json(ToolSettings().to_json()) == ToolSettings()


def test_training_varies_seeds_and_tests_frozen_on_held_out_seeds(project):
    events = []
    settings = TrainingSettings(episodes=2, frame_cap=90, seed_mode="vary", seed_base=10,
                                test_every=1, test_seeds=(100, 101), event_proximal=True)
    run_training(project, settings, emit=lambda k, v: events.append((k, v)))
    from tool.core.run_store import list_runs
    entries = [e for e in list_runs(NAME) if e.get("group") == "Training · real"]
    assert [e["seed"] for e in entries] == [10, 11]                 # a seed per episode
    assert all("score" in e["training"] for e in entries)
    tests = [p for k, p in events if k == "test"]
    assert [t["episode"] for t in tests] == [-1, 0, 1]              # the starting brain, then after each episode
    assert all(t["seeds"] == [100, 101] for t in tests)
    assert load_evals(NAME) == tests
    assert all(0.0 <= t["win_rate"] <= 1.0 for t in tests)


def test_frozen_test_does_not_change_the_weights_it_tests(project):
    """test_frozen runs on net.weights with the rate at 0: training with tests must end with
    the same weights as training without (the tests are pure observation)."""
    base = dict(episodes=2, frame_cap=90, seed_mode="vary", seed_base=10, event_proximal=True)
    run_training(project, TrainingSettings(**base))
    plain = np.load(PROJECTS_ROOT / NAME / "checkpoints" / "real_ep001.npy")
    run_training(project, TrainingSettings(**base, test_every=1, test_seeds=(100,)))
    tested = np.load(PROJECTS_ROOT / NAME / "checkpoints" / "real_ep001.npy")
    assert np.array_equal(plain, tested)


def test_chart_series_helpers():
    entries = [{"number": 2, "training": {"network": "real", "episode": 1, "max_x": 300, "score": 900}},
               {"number": 1, "training": {"network": "real", "episode": 0, "max_x": 200, "score": None}},
               {"number": 3, "training": {"network": "baseline", "episode": -1, "max_x": 10, "score": 5}}]
    assert collect_scores(entries) == {"real": [(1, 900, 2)]}       # unscored / baseline skipped
    evals = [{"network": "real", "episode": 4, "baseline": 1, "win_rate": 0.5, "mean_max_x": 700.0},
             {"network": "real", "episode": 9, "baseline": 30, "win_rate": 0.25, "mean_max_x": 500.0},
             {"network": "real", "episode": 4, "baseline": 30, "win_rate": 0.0, "mean_max_x": 400.0}]
    assert collect_tests(evals) == {"real": [(4, 0.0, 400.0), (9, 25.0, 500.0)]}   # latest session only
    assert collect_tests([]) == {}


# ---- 2. checkpoints in Play / batch -------------------------------------------

def _spec(project, **experiment):
    ts = dataclasses.replace(project.tool_settings, experiment=dataclasses.replace(
        project.tool_settings.experiment, **experiment))
    cfg = dataclasses.replace(project.config, scenario=dataclasses.replace(project.config.scenario, max_frames=120))
    return RunSpec(project_name=NAME, config=cfg, tool_settings=ts, seed=0, out_filename="901_play_seed0.mp4")


def _trained_weights(project):
    """A checkpoint that differs from the fresh weights (a short training run)."""
    run_training(project, TrainingSettings(episodes=1, frame_cap=200, event_proximal=False))
    return "real_ep000.npy"


def test_default_run_is_the_run_it_always_was(project):
    from tool.core.runner import run_one
    _tel, info = run_one(_spec(project))
    assert "brain_weights" not in info and "saved_checkpoint" not in info


def test_checkpoint_run_is_frozen_and_recorded(project):
    from tool.core.runner import run_one
    from tool.core.training import load_checkpoint
    name = _trained_weights(project)
    saved = load_checkpoint(NAME, name)
    _tel, info = run_one(_spec(project, brain_weights=name), save_checkpoint=True)
    assert info["brain_weights"] == name and info["brain_frozen"] is True
    assert np.array_equal(info["mb_weights"], saved)            # rate 0: not a single synapse moved
    assert "saved_checkpoint" not in info                       # frozen runs save nothing


def test_keep_learning_updates_and_saves_a_new_checkpoint(project):
    from tool.core.runner import run_one
    from tool.core.training import load_checkpoint
    name = _trained_weights(project)
    spec = _spec(project, brain_weights=name, keep_learning=True)
    spec = dataclasses.replace(spec, config=dataclasses.replace(
        spec.config, scenario=dataclasses.replace(spec.config.scenario, max_frames=400)))
    _tel, info = run_one(spec, save_checkpoint=True)
    assert info["brain_frozen"] is False and info["saved_checkpoint"] == "play_901.npy"
    assert np.array_equal(load_checkpoint(NAME, "play_901.npy"), info["mb_weights"])
    assert not np.array_equal(info["mb_weights"], load_checkpoint(NAME, name))    # it learned
    assert np.array_equal(load_checkpoint(NAME, name), load_checkpoint(NAME, name))
    _tel, batch_info = run_one(spec)                            # a batch-style call never saves
    assert "saved_checkpoint" not in batch_info


def test_list_and_resume_names(project):
    save_play_checkpoint(NAME, 12, np.zeros((2, 2)))
    assert "play_012.npy" in list_checkpoints(NAME)
    from tool.core.training import _checkpoint_episode
    assert _checkpoint_episode("real_ep050.npy") == 50 and _checkpoint_episode("play_012.npy") == -1


def test_missing_checkpoint_is_a_clear_error(project):
    from tool.core.runner import run_one
    with pytest.raises(FileNotFoundError, match="nope.npy"):
        run_one(_spec(project, brain_weights="nope.npy"))


# ---- 4. power-up weight in fitness --------------------------------------------

def test_powerup_weight_adds_to_fitness_only_when_set():
    info = {"max_x_abs": 100, "n_frames": 50, "score": 0, "n_powerups": 2}
    assert fitness_of(FitnessSettings(), info) == 100.0
    assert fitness_of(FitnessSettings(powerup=25.0), info) == 150.0
    assert fitness_of(FitnessSettings(powerup=25.0), {"max_x_abs": 100, "n_frames": 50}) == 100.0   # older run


# ---- UI: Goal, Circuits, Objects, Config panel ----------------------------------

@pytest.fixture()
def window(qtbot, project):
    from tool.ui.main_window import MainWindow
    w = MainWindow(project)
    qtbot.addWidget(w)
    w._closing_confirmed = True   # a dirty window would open a save/discard dialog on close
    return w


def test_goal_tab_brain_weights_and_seed_controls(window):
    goal = window.goal_tab
    save_play_checkpoint(NAME, 3, np.zeros((2, 2)))
    goal.refresh_checkpoints()
    labels = [goal.brain_weights_combo.itemText(i) for i in range(goal.brain_weights_combo.count())]
    assert labels[0] == "fresh weights" and "played run 3" in labels
    goal.brain_weights_combo.setCurrentIndex(labels.index("played run 3"))
    assert window.get_tool_settings().experiment.brain_weights == "play_003.npy"
    goal.keep_learning_checkbox.setChecked(True)
    assert window.get_tool_settings().experiment.keep_learning is True
    goal.train_seed_mode_combo.setCurrentIndex(1)
    goal.train_test_every_spin.setValue(5)
    goal.train_seed_base_spin.setValue(40)
    goal.train_test_seeds_edit.setText("7 8 9")
    goal.train_test_seeds_edit.editingFinished.emit()
    t = window.get_tool_settings().training
    assert (t.seed_mode, t.test_every, t.seed_base, t.test_seeds) == ("vary", 5, 40, (7, 8, 9))
    goal.powerup_spin.setValue(3.0)
    assert window.get_tool_settings().fitness.powerup == 3.0


def test_config_panel_shows_the_brain_weights_block(qtbot):
    from tool.ui.widgets.run_detail_panels import ConfigPanelContent
    from config.project_config import ProjectConfig
    panel = ConfigPanelContent()
    qtbot.addWidget(panel)
    panel.set_config(ProjectConfig(), {"experiment": {"brain_weights": "real_ep050.npy", "keep_learning": False}})
    text = panel.panel.toPlainText()
    assert "[brain weights]" in text and "real_ep050.npy (frozen)" in text
    panel.set_config(ProjectConfig(), {"experiment": {"brain_weights": None}})
    assert "[brain weights]" not in panel.panel.toPlainText()


def test_mbon_readout_fracs_are_editable_up_to_0_2(window):
    circuits = window.tabs.widget(3)
    circuits._select_circuit("mushroom_body")
    circuits.module_checkboxes["mbon_readout"].setChecked(True)
    for pathway in ("dnp01", "dlmn", "dnp09", "mdn"):
        spin = circuits.module_editors[("mbon_readout", f"{pathway}_frac")]
        assert (spin.minimum(), spin.maximum()) == (0.0, 0.2)
        spin.setValue(0.15)
        assert getattr(window.get_config().modules.mbon_readout, f"{pathway}_frac") == 0.15
    from config.params import MbonReadoutParams, _f  # noqa: F401
    import dataclasses as dc
    assert all(f.metadata["range"] == (0.0, 0.2) for f in dc.fields(MbonReadoutParams))


def test_qblock_module_is_in_the_mushroom_body_card(window):
    circuits = window.tabs.widget(3)
    circuits._select_circuit("mushroom_body")
    assert "qblock_ahead" in circuits.module_checkboxes
    circuits.module_checkboxes["qblock_ahead"].setChecked(True)
    assert window.get_config().modules.qblock_ahead is not None
    circuits.module_editors[("qblock_ahead", "looming_gain")].setValue(0.5)
    assert window.get_config().modules.qblock_ahead.looming_gain == 0.5


def test_objects_tab_question_block_has_a_cue_weight_field(window):
    from bridge.entity_profiles import load as load_profiles
    from mario.entities.kinds import EntityKind
    objects = window.tabs.widget(2)
    qb_page = objects._grid._kind_boxes[EntityKind.QUESTION_BLOCK]
    from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout
    form = qb_page.layout()
    labels = [form.itemAt(i, QFormLayout.ItemRole.LabelRole).widget().text()
              for i in range(form.rowCount()) if form.itemAt(i, QFormLayout.ItemRole.LabelRole)]
    assert any(label.startswith("Cue weight") for label in labels)
    other = objects._grid._kind_boxes[EntityKind.POWERUP].layout()
    assert not any(other.itemAt(i, QFormLayout.ItemRole.LabelRole)
                   and other.itemAt(i, QFormLayout.ItemRole.LabelRole).widget().text().startswith("Cue weight")
                   for i in range(other.rowCount()))
    cue = next(w for w in qb_page.findChildren(QDoubleSpinBox) if w.toolTip().startswith("Scale on the '? block"))
    cue.setValue(2.5)
    assert load_profiles(project_root=PROJECTS_ROOT / NAME).get(EntityKind.QUESTION_BLOCK).cue_weight == 2.5
