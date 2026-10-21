"""What a video export is made of, as plain JSON (it is kept in the job's job.json).

A *side* is one run to replay: {fly, scene, options, label, run_id?, from_moment?, expect}. `expect` is what we already
know about how that run ends (outcome, max_x, frames, and the hash for a saved run), so the replay can be checked.
An export spec is {"export": "run" | "side_by_side" | "montage", "sides": [...], ...options}.

Sides come from three places: a saved run folder (`saved_side`), one start of a finished "test this fly" job at a
given dials setting (`test_side`), and a generation of an evolution job (`generation_side`). Everything is read from
the job / run folders; nothing is played here.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import yaml

from fly_mario.runner import fly_from_dict, fly_to_dict
from fly_mario.runner.record import runs_dir

# The test job plays its dev-set starts with these stop rules (evolve.devset.MAX_FRAMES / STUCK_FRAMES); render and api
# may not import evolve, and a start's {noop, sigma, seed} alone does not say them.
TEST_MAX_FRAMES, TEST_STUCK_FRAMES = 3000, 150
SPEEDS = (1, 2)


def _runs(root) -> Path:
    return Path(root) if root else runs_dir()


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def dials_of(fly: dict) -> str:
    return "original" if (fly.get("provenance") or {}).get("dials") == "original" else "tuned"


def with_dials(fly: dict, dials: str) -> dict:
    """The fly dict with every knob at its hand-set default ("original"), or as it is ("tuned")."""
    if dials == "tuned":
        return fly
    f = fly_from_dict(fly)
    return fly_to_dict(replace(f, knobs={}, provenance={**f.provenance, "dials": "original"}))


def dials_label(fly: dict) -> str:
    """"Original dials", or "Tuned dials (evolved)" when the fly came out of an evolution, else "Tuned dials"."""
    if dials_of(fly) == "original":
        return "Original dials"
    return "Tuned dials (evolved)" if (fly.get("provenance") or {}).get("evolution") else "Tuned dials"


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


def test_side(job_id: str, start: int, dials: str, root=None, label: str = "") -> dict:
    """Start number `start` (1-based, as the Test panel's rows) of a finished test job, played at `dials`."""
    folder = _runs(root) / job_id
    job, res = _json(folder / "job.json"), _json(folder / "result.json")
    if not job or job.get("kind") != "test" or not res:
        raise ValueError(f"{job_id!r} is not a finished test")
    got = res["results"].get(dials)
    if got is None:
        raise ValueError(f"the test {job_id!r} has no {dials!r} result")
    eps = got["episodes"]
    if not 1 <= start <= len(eps):
        raise ValueError(f"the test has starts 1 to {len(eps)}, not {start}")
    ep = eps[start - 1]
    st = ep["start"]
    fly = with_dials(job["fly_config"], dials)
    scene = {"level_id": job["level"], "rom": "v0", "modifiers": [], "start": "level_start", "noop": int(st["noop"]),
             "sigma": float(st["sigma"]), "seed": int(st["seed"]), "max_frames": TEST_MAX_FRAMES, "stuck_frames": TEST_STUCK_FRAMES}
    return {"run_id": "", "fly": fly, "scene": scene, "options": {}, "label": label, "rates": "",
            "expect": {"outcome": ep["outcome"], "max_x": ep["max_x"], "frames": ep["frames"], "hash": ep.get("hash", ""),
                       "death": ep.get("death")}}


def generation_side(evo_id: str, gen: int, clip_frames: int, root=None) -> dict:
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
            "label": "Starting fly" if gen < 0 else f"Generation {gen}", "gen": gen, "expect": {"frames": clip_frames}}


# ---- the three export specs ---------------------------------------------------------------------------------------
def _speed(speed) -> int:
    if int(speed) not in SPEEDS:
        raise ValueError(f"speed is 1 or 2, not {speed!r}")
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


def _same_start(a: dict, b: dict) -> None:
    keys = ("level_id", "rom", "start", "noop", "sigma", "seed", "modifiers")
    diff = [k for k in keys if a["scene"].get(k) != b["scene"].get(k)]
    if diff:
        raise ValueError("the two runs do not start from the same place (they differ in " + ", ".join(diff) + ")")


def side_labels(a: dict, b: dict, label_a: str = "", label_b: str = "") -> tuple:
    """Default labels: the dials when they differ, else the fly names (numbered when those are equal too)."""
    da, db = dials_of(a["fly"]), dials_of(b["fly"])
    if da != db:
        la, lb = dials_label(a["fly"]), dials_label(b["fly"])
    elif a["fly"]["name"] != b["fly"]["name"]:
        la, lb = a["fly"]["name"], b["fly"]["name"]
    else:
        la, lb = f"{a['fly']['name']} (1)", f"{b['fly']['name']} (2)"
    return label_a or la, label_b or lb


def side_by_side_spec(a: dict, b: dict, label_a: str = "", label_b: str = "", show_brain: bool = False,
                      show_senses: bool = True, speed: int = 1) -> dict:
    _same_start(a, b)
    a["label"], b["label"] = side_labels(a, b, label_a, label_b)
    return {"export": "side_by_side", "sides": [a, b], "show_senses": bool(show_senses), "show_brain": bool(show_brain),
            "speed": _speed(speed)}


def montage_spec(evo_id: str, gens: list | None = None, clip_seconds: float = 6.0, speed: int = 2,
                 include_start: bool = False, show_senses: bool = True, root=None) -> dict:
    folder = _runs(root) / evo_id
    prog = _json(folder / "progress.json")
    if not prog or not _json(folder / "job.json"):
        raise ValueError(f"no evolution {evo_id!r}")
    rows = [r for r in prog["rows"] if r["gen"] >= 0]
    if not rows:
        raise ValueError("the evolution has not finished a generation yet")
    have = {r["gen"] for r in rows}
    chosen = sorted(have) if not gens else sorted(set(int(g) for g in gens))
    bad = [g for g in chosen if g not in have]
    if bad:
        raise ValueError(f"the evolution has no generation(s) {bad}")
    speed = _speed(speed)
    frames = int(round(float(clip_seconds) * 60)) * speed
    if frames < 60:
        raise ValueError("a clip must be at least one second")
    ids = ([-1] if include_start and any(r["gen"] == -1 for r in prog["rows"]) else []) + chosen
    return {"export": "montage", "evo": evo_id, "speed": speed, "clip_seconds": float(clip_seconds),
            "show_senses": bool(show_senses), "show_brain": False,
            "sides": [generation_side(evo_id, g, frames, root) for g in ids],
            "bars": [{"gen": r["gen"], "best": float(r["best"]), "mean": float(r["mean"])} for r in rows]}


def title(spec: dict) -> str:
    sides = spec["sides"]
    if spec["export"] == "run":
        return f"Video of run {sides[0]['run_id']}"
    if spec["export"] == "side_by_side":
        return f"Side by side: {sides[0]['label']} and {sides[1]['label']}"
    return f"Montage of {spec['evo']}"
