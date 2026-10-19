"""E1: the genome, BUILT from configs/drives.yaml. Each ON drive adds its gain gene (log scale between max(start/4, floor) and 4 x start); the motor thresholds are always in (linear, +-50% of the start);
an OFF drive's gain is not in the genome and its sense is switched off. Everything else in Knobs stays as it is (the current values = arm C).
CMA-ES works on the unit cube: u in [0, 1]^n -> value (gains: log-linear, thresholds: linear)."""
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import yaml

from .knobs import Knobs

ROOT = Path(__file__).resolve().parent
START = Knobs()


@dataclass
class Gene:
    name: str
    start: float
    lo: float
    hi: float
    log: bool

    def value(self, u):
        u = float(np.clip(u, 0.0, 1.0))
        return float(np.exp(np.log(self.lo) + u * (np.log(self.hi) - np.log(self.lo)))) if self.log else float(self.lo + u * (self.hi - self.lo))

    def unit(self, v):
        return float((np.log(v) - np.log(self.lo)) / (np.log(self.hi) - np.log(self.lo))) if self.log else float((v - self.lo) / (self.hi - self.lo))


def load_config(path=ROOT / "configs" / "drives_e1.yaml"):
    return yaml.safe_load(open(path, encoding="utf-8"))


def build(floors=None, cfg=None):
    """-> list of Gene. floors: {gain name: measured floor}; the effective lower bound = max(start / 4, floor)."""
    cfg = cfg or load_config()
    floors = floors or {}
    lo_f, hi_f = cfg["bounds"]["gain_log_factor"]
    frac = cfg["bounds"]["threshold_fraction"]
    genes = []
    for name, d in cfg["drives"].items():
        if d["enabled"] and d["gain"]:
            s = float(getattr(START, d["gain"]))
            genes.append(Gene(d["gain"], s, max(s * lo_f, float(floors.get(d["gain"], 0.0))), s * hi_f, True))
    for name in cfg["motor"]["genes"]:
        s = float(START.TTMN_THRESH if name == "RELEASE_THRESH" and getattr(START, name) is None else getattr(START, name))
        genes.append(Gene(name, s, s * (1 - frac), s * (1 + frac), False))
    return genes


def knobs_for(values, cfg=None):
    """values: {gene name: value} -> Knobs with v2 senses / motor, the drives' toggles from the config, the genes applied."""
    cfg = cfg or load_config()
    kw = dict(SENSES_VERSION="v2", MOTOR_VERSION="v2")
    enemy_input = True
    for name, d in cfg["drives"].items():
        for key, v in d["toggles"].items():
            if key == "enemy_input":
                enemy_input = bool(v and d["enabled"])
            else:
                kw[key] = bool(v and d["enabled"])
    kw.update(values)
    return replace(START, **kw), enemy_input


def start_values(genes):
    return {g.name: g.start for g in genes}
