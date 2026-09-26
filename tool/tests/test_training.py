"""Training goes through the run store: baseline + episodes recorded,
frame-keep policy, checkpoints, cancel, compact run specs, run 033 visible."""

from __future__ import annotations

import shutil

import pytest

from config.output_routing import PROJECTS_ROOT
from tool.core.project import ToolProject
from tool.core.run_store import list_runs, resolve_run_spec
from tool.core.tool_settings import TrainingSettings
from tool.core.training import list_checkpoints, run_training

NAME = "_train_test"


@pytest.fixture()
def project():
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    p = ToolProject.open("win_attempt").duplicate(NAME)
    yield p
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def test_training_records_everything_through_the_run_store(project):
    events = []
    result = run_training(
        project, TrainingSettings(episodes=3, frame_cap=90, include_shuffled=True, n_shuffled=1),
        emit=lambda k, v: events.append((k, v)))
    entries = list_runs(NAME)
    groups = [e["group"] for e in entries]
    assert groups == ["Baseline"] + ["Training · real"] * 3 + ["Training · shuffled 1"] * 3
    assert result["baseline"] == entries[0]["number"]
    telemetry = PROJECTS_ROOT / NAME / "telemetry"
    for e in entries:                                     # telemetry for ALL
        assert (telemetry / f"{e['slug']}_telemetry.csv").exists()
    kept = {e["number"]: e["summary"]["raw_frames_path"] is not None for e in entries}
    real = [e for e in entries if e["group"] == "Training · real"]
    shuf = [e for e in entries if e["group"] == "Training · shuffled 1"]
    assert kept[entries[0]["number"]]                     # baseline
    assert kept[real[0]["number"]] and kept[real[-1]["number"]]   # ep 0 (10th/best) and last
    assert kept[shuf[-1]["number"]]                       # shuffled last
    assert sum(kept[e["number"]] for e in shuf) <= 2      # only best and last
    # compact spec resolves to a full one with the override applied
    full = resolve_run_spec(shuf[0], entries)
    assert full["tool_settings"]["circuits"]["shuffle_seed"] == 1
    assert full["config"]["scenario"]["max_frames"] == 90
    assert [p for k, p in events if k == "episode"]
    assert list_checkpoints(NAME) == ["real_ep000.npy", "real_ep002.npy"]


def test_cancel_marks_last_and_stops(project):
    stop = {"n": 0}

    def should_stop():
        return stop["n"] > 0

    def emit(kind, payload):
        if kind == "episode" and payload["network"] == "real":
            stop["n"] += 1

    run_training(project, TrainingSettings(episodes=5, frame_cap=60), emit=emit, should_stop=should_stop)
    real = [e for e in list_runs(NAME) if e.get("group") == "Training · real"]
    assert len(real) == 1                                  # stopped after the first episode
    assert real[0]["summary"]["raw_frames_path"] is not None   # the last episode keeps its frames


def test_start_from_checkpoint_continues_numbering(project):
    run_training(project, TrainingSettings(episodes=1, frame_cap=60))
    ckpt = list_checkpoints(NAME)[-1]
    run_training(project, TrainingSettings(episodes=1, frame_cap=60, checkpoint=ckpt))
    episodes = [e["training"]["episode"] for e in list_runs(NAME) if e.get("group") == "Training · real"]
    assert episodes == [0, 1]


def test_read_only_project_refuses():
    legacy = ToolProject.open("legacy")
    with pytest.raises(PermissionError):
        run_training(legacy, TrainingSettings(episodes=1))


def test_run_033_is_registered():
    entries = {e["number"]: e for e in list_runs("win_attempt")}
    assert entries[33]["slug"] == "033_first_win"
    assert entries[33]["summary"]["flag_get"] is True
