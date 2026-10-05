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

from brain import calibration as C


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


class ObstacleExpansion(LoomingMechanism):
    """Looming from static obstacles (docs/SPEC_e2a.md). Cue: the face of the nearest wall, pipe, block or step ahead, whose
    angular size grows only because Mario walks toward it. Same channel and the same encoding as `LoomingMechanism` (it IS
    that encoding, fed a different theta): LPLC2 gets theta, LC4 gets |dtheta|. Nothing deeper, no new population."""
    name = "obstacle_expansion"
    label = ("looming from static obstacles (biology: expansion cue; no source for obstacle-triggered jumps in flies; "
             "this is a Mario's-eye-view assumption)")
    evidence = ("Ache et al. 2019 for the detectors; NO source that flies jump at static obstacles (Pick & Strauss 2005: "
                "flies climb) -- a Mario's-eye-view assumption, entering at the existing looming inputs only")


# ---- Phase 3: LC10a mechanisms (docs/SPEC_phase3.md section 4) ------------------------------------------------------------
def azimuth_shares(azimuth_deg: float, split_deg: float) -> tuple[float, float]:
    """(left share, right share) of a target at `azimuth_deg` (negative = left of Mario, positive = right): the same-side
    eye carries it. Beyond +-split_deg the target drives one side only; straight ahead both sides equally."""
    r = min(1.0, max(0.0, 0.5 + azimuth_deg / (2.0 * split_deg)))
    return 1.0 - r, r


class TargetMechanism:
    """Base of the two LC10a mechanisms. LC10a neurons respond to small moving objects (Ribeiro et al. 2018 Cell 174:607);
    left LC10a = left eye. The only population named is LC10a, so Brain.apply refuses anything deeper."""
    populations = ("LC10a",)
    name = "target"
    evidence = ""

    def __init__(self, network):
        idx = network.pops["LC10a"]
        self._ids = {s: network.ids[idx[network.side[idx] == s]] for s in ("L", "R")}

    def drive(self, drive_left: float, drive_right: float) -> Stimulus:
        ids = np.concatenate([self._ids["L"], self._ids["R"]])
        vals = np.concatenate([np.full(len(self._ids["L"]), drive_left), np.full(len(self._ids["R"]), drive_right)])
        return Stimulus(ids, vals, self.name)


class PursuitMechanism(TargetMechanism):
    """Pursuit of a small moving object seen on screen: the same-side eye drives an ipsilateral turn (Ribeiro et al. 2018;
    Hindmarsh Sten et al. 2021 Nature 595:549; the turn direction is the same-side-eye assumption). Drive per side =
    LC10A_GAIN * arousal * salience * share(azimuth); `arousal` is a fly-state INPUT in [0, 1] set in the tool
    (SenseSettings.pursuit_arousal), never read from the fly's own output. Which object kinds count is a per-object setting (brain/settings.py)."""
    name = "pursuit"
    evidence = ("Ribeiro et al. 2018 Cell 174:607; Hindmarsh Sten et al. 2021 Nature 595:549 (snippet level); "
                "gain scaled by a fly-state (arousal) input set in the tool; locomotion state raises visual gain in flies "
                "(Chiappe 2010, Maimon 2010, from memory)")

    def __init__(self, network, gain: float | None = None, split_deg: float | None = None):
        super().__init__(network)
        self.gain = C.LC10A_GAIN if gain is None else gain
        self.split_deg = C.LC10A_AZIMUTH_SPLIT if split_deg is None else split_deg

    def encode(self, azimuth_deg: float, salience: float, arousal_state: float) -> Stimulus:
        left, right = azimuth_shares(azimuth_deg, self.split_deg)
        k = self.gain * arousal_state * salience
        return self.drive(k * left, k * right)


class HomeLandmarkMechanism(TargetMechanism):
    """Home landmark: a persistent static cue on the right, strength GOAL_CUE_SALIENCE (a world property, invented, counted).
    It moves the 'go right' assumption into the senses; it does not remove it. Not a visible object, and LC10a prefers
    small moving objects, so the literature does not license a static cue."""
    name = "home_landmark"
    evidence = "invented world-level cue (GOAL_CUE_SALIENCE); enters at right LC10a only"

    def __init__(self, network, salience: float | None = None):
        super().__init__(network)
        self.salience = C.GOAL_CUE_SALIENCE if salience is None else salience

    def encode(self) -> Stimulus:
        return self.drive(0.0, self.salience)
