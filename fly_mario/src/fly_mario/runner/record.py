"""Write a finished run to $FLY_MARIO_DATA/runs/<id>/.

    config.yaml   the fly (as a yaml you can load again), the scene, the options: enough to repeat the run
    frames.csv    one row per frame: x, buttons, every sense's calculation steps, the modifiers raised
    rates.npz     the mean rate of every neuron group, one value per frame
    replay.npz    every button byte sent to the emulator (idle frames included), plus ram.npy if it was recorded
    summary.json  outcome, max x, score, counts, the reproducibility hash
"""
from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import yaml

from fly_mario.fly import connectome as cn
from fly_mario.runner import config as C


def new_run_id(fly_name: str, level: str, seed: int) -> str:
    return f"{time.strftime('%Y%m%d-%H%M%S')}_{fly_name}_{level}_k{seed}"


def runs_dir() -> Path:
    return cn.data_dir() / "runs"


def scene_to_dict(scene) -> dict:
    d = asdict(scene)
    d["modifiers"] = [[n, dict(p)] for n, p in scene.modifiers]
    return d


def scene_from_dict(d: dict):
    from fly_mario.contracts import Scene
    d = dict(d)
    d["modifiers"] = tuple((n, dict(p)) for n, p in d.get("modifiers", ()))
    return Scene(**d)


def save_run(run, result, folder: Path | None = None) -> Path:
    folder = Path(folder) if folder else runs_dir() / (result.id or new_run_id(run.fly.name, run.scene.level_id, run.scene.seed))
    folder.mkdir(parents=True, exist_ok=True)
    cfg = {"fly": C.fly_to_dict(run.fly), "scene": scene_to_dict(run.scene), "options": asdict(run.options),
           "knobs_resolved": {k: float(v) for k, v in sorted(run.knobs.items())}}
    (folder / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    cols: list = []
    for r in run.rows:
        cols += [k for k in r if k not in cols]
    with open(folder / "frames.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, restval="")
        w.writeheader()
        w.writerows(run.rows)
    np.savez_compressed(folder / "rates.npz", **{g: np.asarray(v) for g, v in run.rates.items()})
    extra = {"ram": np.asarray(run.rams, dtype=np.uint8)} if run.rams else {}
    np.savez_compressed(folder / "replay.npz", buttons=np.asarray(run.replay, dtype=np.uint8), **extra)
    summary = {"id": folder.name, "fly": result.fly, "level": run.scene.level_id, "outcome": result.outcome,
               "death": result.death, "max_x": result.max_x, "score": result.score, "blocks": result.blocks,
               "mushroom": result.mushroom, "counts": result.counts, "hash": result.hash,
               "noop": run.scene.noop, "sigma": run.scene.sigma, "seed": run.scene.seed,
               "parent_moment": result.parent_moment, "objects_seen": sorted(run.seen)}
    (folder / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return folder
