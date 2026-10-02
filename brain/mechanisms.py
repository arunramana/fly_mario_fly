# What this file does, in plain English:
# A "mechanism" turns something visible in the game into activity of real
# sensory neurons, and nothing else. This file holds the stimulus object (the
# only thing the brain accepts) and the looming mechanism: how big an approaching
# enemy looks drives one looming-detector type, how fast it grows drives the other.
"""brain/mechanisms.py -- docs/SPEC_brain_core.md section 6.

A mechanism = cue -> sense channel -> encoding. It can only name populations; Brain.apply() refuses any neuron that is
not in the manifest's sensory tier, so a mechanism cannot reach deeper even by mistake.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class Stimulus:
    """Drive for named sensory neurons for one frame: bodyIds and the value each receives."""
    body_ids: np.ndarray
    values: np.ndarray
    source: str


class Mechanism(Protocol):
    name: str
    populations: tuple[str, ...]      # sensory-tier populations this mechanism may drive
    evidence: str


class LoomingMechanism:
    """Looming threat. Cue: an enemy ahead whose angular size theta = 2 atan(w / 2|d|) grows. Channel: LPLC2 (size)
    and LC4 (speed), the detectors Ache et al. 2019 identified. Encoding (ported from bridge/loom_disc.py, which is
    what the calibration was derived on): theta (rad) into LPLC2, |dtheta| (rad/frame) into LC4, per hemisphere."""
    name = "looming"
    populations = ("LC4", "LPLC2")
    evidence = "Ache et al. 2019 Curr Biol 29:1073 (GF fires at ~40 deg); vision entry tier D1 (feature neurons)"

    def __init__(self, network):
        self._ids = {}
        for pop in self.populations:
            idx = network.pops[pop]
            for s in ("L", "R"):
                self._ids[(pop, s)] = network.ids[idx[network.side[idx] == s]]

    def encode(self, theta: dict[str, float], dtheta: dict[str, float]) -> Stimulus:
        ids, vals = [], []
        for s in ("L", "R"):
            for pop, v in (("LC4", abs(dtheta[s])), ("LPLC2", theta[s])):
                b = self._ids[(pop, s)]
                ids.append(b)
                vals.append(np.full(len(b), v))
        return Stimulus(np.concatenate(ids), np.concatenate(vals), self.name)
