"""Saved states = deterministic action-log replay (nes-py has no state export)."""
from __future__ import annotations

import dataclasses
import shutil

import numpy as np
import pytest

from config.output_routing import PROJECTS_ROOT
from tool.core.project import ToolProject
from tool.core.run_spec import RunSpec
from tool.core.runner import run_one
from tool.core.savestates import list_states, load_state, save_state

NAME = "_savestate_test"


@pytest.fixture()
def project():
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)
    p = ToolProject.open("win_attempt").duplicate(NAME)
    yield p
    shutil.rmtree(PROJECTS_ROOT / NAME, ignore_errors=True)


def _spec(project, slug, frames=150, start_state=None):
    cfg = dataclasses.replace(project.config, scenario=dataclasses.replace(project.config.scenario, max_frames=frames))
    ts = project.tool_settings
    ts = dataclasses.replace(ts, experiment=dataclasses.replace(ts.experiment, start_state=start_state),
                             render=dataclasses.replace(ts.render, raw_frames=False))
    return RunSpec(NAME, cfg, ts, 0, f"{slug}.mp4")


def test_run_records_actions_and_replay_reaches_the_same_state(project):
    tel, info = run_one(_spec(project, "001_a"))
    actions = np.load(info["actions_path"])
    assert len(actions) == info["n_frames"] and info["actions_prefix_len"] == 0
    # Save at frame 100, start a new run from it: Mario begins exactly where run A was at frame 100.
    save_state(NAME, "f100", actions[:100], "1-1", 100, source_run=1)
    assert list_states(NAME) == ["f100"] and load_state(NAME, "f100")["frame"] == 100
    tel2, info2 = run_one(_spec(project, "002_b", frames=40, start_state="f100"))
    assert info2["start_state"] == {"name": "f100", "frame": 100, "source_run": 1}
    assert tel2["mario_x"].iloc[0] == tel["mario_x"].iloc[100]            # same emulator state
    assert info2["actions_prefix_len"] == 100 and len(np.load(info2["actions_path"])) == 100 + info2["n_frames"]


def test_power_on_is_the_default_and_ram_injection_records_no_actions(project):
    spec = _spec(project, "003_c", frames=30)
    assert spec.tool_settings.experiment.start_state is None
    cfg = dataclasses.replace(spec.config, scenario=dataclasses.replace(spec.config.scenario, inject_gap_frame=5))
    tel, info = run_one(RunSpec(NAME, cfg, spec.tool_settings, 0, "004_d.mp4"))
    assert "actions_path" not in info


def test_save_from_a_recorded_run_is_instant_and_old_runs_are_resimulated(project):
    from tool.core.run_store import list_runs, record_run
    from tool.core.savestates import capture_from_run
    spec = _spec(project, "001_a", frames=120)
    _tel, info = run_one(spec)
    record_run(NAME, 1, "001_a", 0, info, spec.to_dict())
    entry = list_runs(NAME)[0]
    fast = capture_from_run(NAME, entry, 60)
    assert fast["resimulated"] is False and load_state(NAME, fast["name"])["frame"] == 60
    # an older run with no action log: re-simulated, and reaches the same state
    old = {**entry, "summary": {k: v for k, v in entry["summary"].items() if k != "actions_path"}}
    slow = capture_from_run(NAME, old, 60, name="resim")
    assert slow["resimulated"] is True
    assert np.array_equal(load_state(NAME, "resim")["actions"], load_state(NAME, fast["name"])["actions"])
    with pytest.raises(ValueError):
        capture_from_run(NAME, {**old, "training": {"network": "real"}}, 10)
