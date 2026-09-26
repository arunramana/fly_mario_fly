# What this file does, in plain English:
# Saves and loads "save states" for a project. nes-py cannot export the
# emulator's memory, so a saved state is the list of button presses that
# reaches that moment from power-on; starting from it replays those presses
# (fast, no brain), then the run continues normally with a fresh brain.
"""tool/core/savestates.py -- projects/<name>/savestates/<state>.npz:
{actions, level, frame, source_run}. Deterministic replay reaches the exact
emulator state because a run with no RAM injection is a pure function of its
action log. Runs that poke RAM (starting_powerup, inject_gap_frame) cannot
be replayed and record no action log.

Every Play/batch run records `<slug>_actions.npy` (one uint8 action per
frame, all of them, so a state can be saved at ANY frame instantly -- finer
than the every-60-frames checkpoints an emulator snapshot would need). Older
runs without one are re-simulated once (tool.core.runner.run_one)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from config.output_routing import PROJECTS_ROOT

FRESH_BRAIN_NOTE = "A run started from a saved state begins with a fresh brain (neural state is not restored)."


def _dir(project_name: str) -> Path:
    return PROJECTS_ROOT / project_name / "savestates"


def list_states(project_name: str) -> list[str]:
    d = _dir(project_name)
    return sorted(p.stem for p in d.glob("*.npz")) if d.exists() else []


def save_state(project_name: str, name: str, actions, level: str, frame: int,
               source_run: int | None = None) -> Path:
    d = _dir(project_name)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.npz"
    np.savez_compressed(path, actions=np.asarray(actions, dtype=np.uint8), level=level,
                        frame=int(frame), source_run=-1 if source_run is None else int(source_run))
    return path


def load_state(project_name: str, name: str) -> dict:
    with np.load(_dir(project_name) / f"{name}.npz") as z:
        return {"name": name, "actions": z["actions"].copy(), "level": str(z["level"]),
                "frame": int(z["frame"]),
                "source_run": None if int(z["source_run"]) < 0 else int(z["source_run"])}


def actions_path_for(summary: dict) -> Path | None:
    p = summary.get("actions_path")
    return Path(p) if p and Path(p).exists() else None


def actions_up_to(summary: dict, frame: int) -> np.ndarray | None:
    """The action log reaching `frame` of a run (its start-state prefix
    included), or None when the run recorded none."""
    path = actions_path_for(summary)
    if path is None:
        return None
    actions = np.load(path)
    return actions[: int(summary.get("actions_prefix_len", 0)) + int(frame)]


def capture_from_run(project_name: str, entry: dict, frame: int, name: str | None = None) -> dict:
    """Save a state at `frame` of a recorded run. Instant when the run has an
    action log; otherwise the run is re-simulated (headless, capped at
    `frame`) to obtain one -- possible only for a run whose spec fully
    determines it (not a training episode, whose start weights are not in
    its spec, and not one that poked RAM). Returns {name, frame, resimulated}."""
    from tool.core.run_store import resolve_run_spec
    summary = entry.get("summary", {})
    frame = max(0, min(int(frame), int(summary.get("n_frames") or frame)))
    actions = actions_up_to(summary, frame)
    resimulated = False
    if actions is None:
        if entry.get("training"):
            raise ValueError("training episodes record no action log, so no state can be saved from them")
        import dataclasses
        from tool.core.run_spec import RunSpec
        from tool.core.runner import run_one
        spec = RunSpec.from_dict(resolve_run_spec(entry, project_name=project_name))
        if spec.config.scenario.inject_gap_frame is not None or spec.tool_settings.character.starting_powerup:
            raise ValueError("this run poked RAM, so its state cannot be replayed")
        cfg = dataclasses.replace(spec.config, scenario=dataclasses.replace(spec.config.scenario, max_frames=frame))
        render = dataclasses.replace(spec.tool_settings.render, raw_frames=False, record_video=False)
        spec = dataclasses.replace(spec, config=cfg, out_filename=f"{entry['slug']}_resim.mp4",
                                   tool_settings=dataclasses.replace(spec.tool_settings, render=render))
        _tel, info = run_one(spec)
        actions = np.load(info["actions_path"])
        # the re-simulation is scratch: keep only the state we are about to save
        for p in (Path(info["actions_path"]),
                  PROJECTS_ROOT / project_name / "telemetry" / f"{entry['slug']}_resim_telemetry.csv"):
            p.unlink(missing_ok=True)
        resimulated = True
    name = name or f"run{entry['number']:03d}_f{frame}"
    level = resolve_run_spec(entry, project_name=project_name)["config"]["scenario"]["level"]
    save_state(project_name, name, actions, level, frame, entry["number"])
    return {"name": name, "frame": frame, "resimulated": resimulated}

