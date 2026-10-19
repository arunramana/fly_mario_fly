"""E2: the genome of Stage 2 = the E1s genes + brain dynamics (G, ALPHA, CLIP) + DNP09_THRESH + 4 box-geometry choices, from configs/genome_e2.yaml (16 genes). Start = the E1s best + the current values."""
import json
from pathlib import Path

import yaml

from . import e1s_genome as S
from .e1_genome import Gene
from .knobs import Knobs

ROOT = Path(__file__).resolve().parent
WFILE, BODIES = S.WFILE, S.BODIES


def load_config(path=ROOT / "configs" / "genome_e2.yaml"):
    return yaml.safe_load(open(path, encoding="utf-8"))


def start_values():
    v = dict(json.load(open(ROOT / "runs" / "E1s_progress.json"))["best"]["values"])
    for g in load_config()["extra_genes"]:
        v[g["name"]] = float(g["start"]) if g["kind"] == "range" else float(getattr(Knobs(), g["name"]))
    return v


def build(floors=None):
    """E1s genes first (same rules, floors, around the E1s best), then the new ones."""
    sv = start_values()
    cfg = S.load_config()
    base = load_config()
    floors = floors or {}
    lo_f, hi_f = base["bounds_e1s_genes"]["gain_log_factor"]
    frac = base["bounds_e1s_genes"]["threshold_fraction"]
    genes = []
    for name, d in cfg["drives"].items():
        if d["enabled"] and d["gain"]:
            s = float(sv[d["gain"]])
            genes.append(Gene(d["gain"], s, max(s * lo_f, float(floors.get(d["gain"], 0.0))), s * hi_f, True))
    for name in cfg["motor"]["genes"]:
        s = float(sv[name])
        genes.append(Gene(name, s, s * (1 - frac), s * (1 + frac), False))
    for g in base["extra_genes"]:
        s = sv[g["name"]]
        if g["kind"] == "frac":
            genes.append(Gene(g["name"], s, s * (1 - g["fraction"]), s * (1 + g["fraction"]), False))
        else:
            genes.append(Gene(g["name"], s, float(g["lo"]), float(g["hi"]), False))
    return genes


def knobs_for(values):
    return S.knobs_for(values)
