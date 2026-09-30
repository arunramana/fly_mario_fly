# What this file does, in plain English:
# Checks that a recorded run spec reproduces its run by itself: after the project's
# entity-profile file, its saved start state and its checkpoint are changed, replaying
# the spec still gives exactly the same button presses; a changed checkpoint is refused.
# Also checks that training runs the same way Play does (same telemetry for the same spec).
"""Phase 1 (docs/SPEC_bio_strict.md): run-spec snapshots and training == Play."""
from __future__ import annotations

import dataclasses
import json
import shutil

import numpy as np
import pandas as pd
import pytest

from config.output_routing import PROJECTS_ROOT
from tool.core.entity_profiles_store import override_path
from tool.core.project import ToolProject
from tool.core.run_spec import RunSpec, freeze
from tool.core.runner import run_one
from tool.core.savestates import save_state
from tool.core.tool_settings import TrainingSettings
from tool.core.training import checkpoint_dir, run_training

NAME = "_snapshot_test"


@pytest.fixture()
def project():
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    p = ToolProject.open("win_attempt").duplicate(NAME)
    yield p
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def _spec(project, **experiment):
    ts = dataclasses.replace(
        project.tool_settings,
        entity_profile=dataclasses.replace(project.tool_settings.entity_profile, enabled=True),
        character=dataclasses.replace(project.tool_settings.character, hunger_override=True),
        render=dataclasses.replace(project.tool_settings.render, raw_frames=False),
        experiment=dataclasses.replace(project.tool_settings.experiment, **experiment))
    cfg = dataclasses.replace(project.config, scenario=dataclasses.replace(project.config.scenario, max_frames=150))
    return RunSpec(project_name=NAME, config=cfg, tool_settings=ts, seed=3, out_filename="901_snap.mp4")


def test_snapshot_holds_profiles_state_and_checksums(project):
    from mario.actions.actions import action_index
    save_state(NAME, "s1", [action_index("R", False, True)] * 60, "1-1", 60)
    spec = freeze(_spec(project, start_state="s1"))
    snap = spec.snapshot
    assert set(snap["entity_profiles"]) >= {"GOOMBA", "KOOPA", "POWERUP", "QUESTION_BLOCK"}   # the FULL merged profiles
    assert snap["start_state"]["name"] == "s1" and len(snap["start_state"]["sha256"]) == 64
    assert RunSpec.from_dict(json.loads(json.dumps(spec.to_dict()))).snapshot == snap          # survives the index JSON
    assert freeze(_spec(project)).snapshot.get("start_state") is None


def test_replaying_a_recorded_spec_reproduces_the_actions_exactly(project):
    from mario.actions.actions import action_index
    save_state(NAME, "s1", [action_index("R", False, True)] * 60, "1-1", 60)
    path = override_path(NAME)
    path.write_text(json.dumps({"GOOMBA": {"looming_salience": 2.5}}), encoding="utf-8")
    spec = freeze(_spec(project, start_state="s1"))
    _tel, first = run_one(spec)
    recorded = np.load(first["actions_path"])
    # the project drifts afterwards: a different profile and a different saved state under the same name
    path.write_text(json.dumps({"GOOMBA": {"looming_salience": 0.1}, "KOOPA": {"looming_salience": 0.1}}), encoding="utf-8")
    save_state(NAME, "s1", [action_index("R", True, True)] * 60, "1-1", 60)
    replay = RunSpec.from_dict(json.loads(json.dumps(spec.to_dict())))
    _tel, second = run_one(replay)
    assert np.array_equal(np.load(second["actions_path"]), recorded)
    assert second["max_x_abs"] == first["max_x_abs"] and second["n_frames"] == first["n_frames"]
    # ... while an old spec with no snapshot reads the live (changed) files, as before
    live = run_one(dataclasses.replace(spec, snapshot=None))[1]
    assert not np.array_equal(np.load(live["actions_path"]), recorded)


def test_a_changed_checkpoint_is_refused(project):
    run_training(project, TrainingSettings(episodes=1, frame_cap=60, event_proximal=True))
    spec = freeze(_spec(project, brain_weights="real_ep000.npy"))
    w = np.load(checkpoint_dir(NAME) / "real_ep000.npy")
    np.save(checkpoint_dir(NAME) / "real_ep000.npy", w * 0.5)
    with pytest.raises(ValueError, match="checksum"):
        run_one(spec)


def test_training_runs_exactly_like_play(project):
    """The baseline episode (learning rate 0) and Play's run_one see the same entity profiles, character settings
    and first frame: identical telemetry for the same seed."""
    from config.output_routing import resolve_telemetry_path
    path = override_path(NAME)
    path.write_text(json.dumps({"GOOMBA": {"looming_salience": 2.5}}), encoding="utf-8")
    ts = dataclasses.replace(
        project.tool_settings,
        entity_profile=dataclasses.replace(project.tool_settings.entity_profile, enabled=True),
        character=dataclasses.replace(project.tool_settings.character, hunger_override=True),
        experiment=dataclasses.replace(project.tool_settings.experiment, seeds=(7,)))
    project.tool_settings = ts
    run_training(project, TrainingSettings(episodes=1, frame_cap=150))
    from tool.core.run_store import list_runs
    base = next(e for e in list_runs(NAME) if e.get("group") == "Baseline")
    train_tel = pd.read_csv(resolve_telemetry_path(project.config, base["slug"] + "_telemetry.csv"))
    cfg = dataclasses.replace(project.config,
                              scenario=dataclasses.replace(project.config.scenario, max_frames=150),
                              mushroom_body=dataclasses.replace(project.config.mushroom_body, learning_rate=0.0))
    spec = freeze(RunSpec(project_name=NAME, config=cfg, tool_settings=ts, seed=7, out_filename="902_same.mp4"))
    play_tel, _ = run_one(spec)
    cols = ["mario_x", "theta", "lc4", "lplc2", "ttmn", "press_a", "press_b", "direction"]
    pd.testing.assert_frame_equal(train_tel[cols].reset_index(drop=True), play_tel[cols].reset_index(drop=True))
