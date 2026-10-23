"""What a video export is made of, as plain JSON (it is kept in the job's job.json).

A *side* is one run to replay: {fly, scene, options, label, run_id?, from_moment?, expect}. `expect` is what we already
know about how that run ends (outcome, max_x, frames, and the hash for a saved run), so the replay can be checked.
An export spec is {"export": "run" | "montage", "sides": [...], ...options}.

Sides come from two places: a saved run folder (`saved_side`) and a generation of an evolution job (`generation_side`).
Everything is read from the job / run folders; nothing is played here.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import yaml

from fly_mario_fly.runner import fly_from_dict, fly_to_dict
from fly_mario_fly.runner.record import runs_dir

# The test job plays its dev-set starts with these stop rules (evolve.devset.MAX_FRAMES / STUCK_FRAMES); render and api
# may not import evolve, and a start's {noop, sigma, seed} alone does not say them.
TEST_MAX_FRAMES, TEST_STUCK_FRAMES = 3000, 150
SPEEDS = (1, 2)
MONTAGE_SPEEDS = (1, 2, 4)


def _runs(root) -> Path:
    return Path(root) if root else runs_dir()


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---- sides --------------------------------------------------------------------------------------------------------
def saved_side(run_id: str, root=None, label: str = "") -> dict:
    folder = _runs(root) / run_id
    if "/" in run_id or "\\" in run_id or not (folder / "summary.json").exists():
        raise ValueError(f"no saved run {run_id!r}")
    cfg = yaml.safe_load((folder / "config.yaml").read_text(encoding="utf-8"))
    summ = _json(folder / "summary.json")
    sc = dict(cfg["scene"])
    return {"run_id": run_id, "fly": cfg["fly"], "scene": sc, "options": cfg.get("options", {}), "label": label,
            "rates": str(folder / "rates.npz") if (folder / "rates.npz").exists() else "",
            "expect": {"outcome": summ["outcome"], "max_x": summ["max_x"], "frames": summ["counts"]["frames"],
                       "hash": summ["hash"], "death": summ.get("death")}}


def generation_side(evo_id: str, gen: int, root=None) -> dict:
    """The best fly of one generation of an evolution (gen -1 = the fly it started from), on the level's start, no noise."""
    folder = _runs(root) / evo_id
    job, prog = _json(folder / "job.json"), _json(folder / "progress.json")
    if not job or job.get("kind") != "evolve" or not prog:
        raise ValueError(f"{evo_id!r} is not an evolution")
    row = next((r for r in prog["rows"] if r["gen"] == gen), None)
    if row is None:
        raise ValueError(f"the evolution has no generation {gen}")
    start = fly_from_dict(yaml.safe_load((folder / "start.yaml").read_text(encoding="utf-8")))
    fly = replace(start, name=f"{start.name}_gen{gen}", knobs={**start.knobs, **row["best_values"]})
    moment = job.get("start") if job.get("start") not in (None, "level_start") else None
    scene = {"level_id": job["level"], "rom": "v0", "modifiers": [], "start": "level_start", "noop": 0, "sigma": 0.0,
             "seed": 0, "max_frames": TEST_MAX_FRAMES, "stuck_frames": TEST_STUCK_FRAMES}
    return {"run_id": "", "fly": fly_to_dict(fly), "scene": scene, "options": {}, "from_moment": moment, "rates": "",
            "label": "Starting fly" if gen < 0 else f"Generation {gen}", "gen": gen, "expect": {}}


# ---- the three export specs ---------------------------------------------------------------------------------------
def _speed(speed, allowed=SPEEDS) -> int:
    if int(speed) not in allowed:
        raise ValueError(f"speed is {' or '.join(map(str, allowed))}, not {speed!r}")
    return int(speed)


def run_spec(run_id: str, show_senses: bool = True, show_brain: bool = True, speed: int = 1,
             frame_from: int | None = None, frame_to: int | None = None, root=None) -> dict:
    side = saved_side(run_id, root, label=run_id)
    last = int(side["scene"].get("noop", 0)) + int(side["expect"]["frames"]) - 1
    a, b = int(frame_from if frame_from is not None else 0), int(frame_to if frame_to is not None else last)
    a, b = max(a, int(side["scene"].get("noop", 0))), min(b, last)
    if a > b:
        raise ValueError(f"the frame range is empty: the run has frames {side['scene'].get('noop', 0)} to {last}")
    return {"export": "run", "sides": [side], "show_senses": bool(show_senses), "show_brain": bool(show_brain),
            "speed": _speed(speed), "frame_from": a, "frame_to": b}


def montage_spec(evo_id: str, speed: int = 2, show_senses: bool = True, show_brain: bool = True, root=None) -> dict:
    """One clip per generation of a finished evolution (its best fly), each played to its end, with the fitness chart
    along the bottom."""
    folder = _runs(root) / evo_id
    prog, job = _json(folder / "progress.json"), _json(folder / "job.json")
    if not prog or not job:
        raise ValueError(f"no evolution {evo_id!r}")
    if job.get("status") in ("queued", "running"):
        raise ValueError("the evolution is still running: the montage shows every generation, so wait until it has finished")
    rows = [r for r in prog["rows"] if r["gen"] >= 0]
    if not rows:
        raise ValueError("the evolution has not finished a generation yet")
    return {"export": "montage", "evo": evo_id, "speed": _speed(speed, MONTAGE_SPEEDS),
            "show_senses": bool(show_senses), "show_brain": bool(show_brain),
            "sides": [generation_side(evo_id, r["gen"], root) for r in rows],
            "bars": [{"gen": r["gen"], "best": float(r["best"]), "mean": float(r["mean"])} for r in rows]}


def title(spec: dict) -> str:
    sides = spec["sides"]
    if spec["export"] == "run":
        return f"Video of run {sides[0]['run_id']}"
    return f"Montage of {spec['evo']}"
