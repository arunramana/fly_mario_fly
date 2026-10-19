"""E1s: the genome of the run WITH sour smell, built from configs/drives.yaml: HOME_R, HUM_GAIN, SMELL_GAIN, SOUR_GAIN (the ON drives' gains) + TTMN_THRESH, RELEASE_THRESH, STEER_THRESH, MDN_THRESH (motor, always in).
Start = the E1 best + SOUR_GAIN 8.0587 + MDN_THRESH 0.10. Bounds: gains log-scale 1/4x..4x of the start raised to the measured floor; thresholds +-50%. Brain: the 907-neuron sour brain."""
import json
from dataclasses import replace
from pathlib import Path

import yaml

from .e1_genome import Gene
from .knobs import Knobs

ROOT = Path(__file__).resolve().parent
WFILE, BODIES = "W_steer_jo_orn_sour.npy", "steer_jo_orn_sour_bodies.parquet"


def load_config(path=ROOT / "configs" / "drives.yaml"):
    return yaml.safe_load(open(path, encoding="utf-8"))


def start_values(cfg=None):
    cfg = cfg or load_config()
    v = dict(json.load(open(ROOT / "runs" / "E1_progress.json"))["best"]["values"])
    v.update(cfg["start"]["extra"])
    return v


def build(floors=None, cfg=None):
    cfg = cfg or load_config()
    floors = floors or {}
    sv = start_values(cfg)
    lo_f, hi_f = cfg["bounds"]["gain_log_factor"]
    frac = cfg["bounds"]["threshold_fraction"]
    genes = []
    for name, d in cfg["drives"].items():
        if d["enabled"] and d["gain"]:
            s = float(sv[d["gain"]])
            genes.append(Gene(d["gain"], s, max(s * lo_f, float(floors.get(d["gain"], 0.0))), s * hi_f, True))
    for name in cfg["motor"]["genes"]:
        s = float(sv[name])
        genes.append(Gene(name, s, s * (1 - frac), s * (1 + frac), False))
    return genes


def knobs_for(values, cfg=None):
    """values: {gene name: value} -> (Knobs, enemy_input). Toggles from the config (drives and perception)."""
    cfg = cfg or load_config()
    kw = dict(SENSES_VERSION="v2", MOTOR_VERSION="v2")
    enemy_input = True
    for group in (cfg["drives"], cfg.get("perception", {})):
        for name, d in group.items():
            for key, v in d["toggles"].items():
                if key == "enemy_input":
                    enemy_input = bool(v and d["enabled"])
                else:
                    kw[key] = bool(v and d["enabled"])
    kw.update(values)
    return replace(Knobs(), **kw), enemy_input
