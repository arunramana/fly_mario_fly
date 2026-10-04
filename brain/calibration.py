# What this file does, in plain English:
# Holds every number the new brain runs with and says where each came from. The
# fixed physical choices (firing-rate cap, noise, time constants) are constants
# here; the numbers worked out on the synthetic looming disc (the gain, the Giant
# Fiber threshold, the motor-reading thresholds) are stored in a small JSON file
# next to this one, tied to the exact network they were derived on.
"""brain/calibration.py -- docs/SPEC_brain_core.md section 5.

`CONSTANTS` are chosen once with a stated reason (same values as the validated bio_strict path, so the parity check
is like for like). `Calibration` carries the derived numbers; its file hash stamps every result. Nothing here is
an experiment input and nothing is tuned on game outcomes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CALIBRATION_FILE = Path(__file__).resolve().parent / "calibration.json"

# One neuron model for the whole brain. Values equal config/params.py's validated bio_strict ones (cited there).
ALPHA = 0.3                 # leak per substep (tau ~3 substeps ~5 ms); same as fly.network.dynamics.ALPHA
SUBSTEPS = 10               # network steps per 60 fps frame (docs/SPEC_jump.md)
CLIP_HZ = 200.0             # rates read as Hz; central-neuron peaks are of order 1e2 Hz (Bhandawat 2007)
SPIKE_AMP_HZ = 60.0         # one spike per 16.7 ms frame = 1000/16.67 Hz
REFRACTORY_STEPS = 3        # 5 ms absolute refractory period of the spiking cells
NOISE_SIGMA = 0.015         # membrane noise per neuron per substep (the project's value)
STABILITY_MARGIN = 0.85     # largest allowed loop gain rho(W)*g (15 % margin for noise)
G_NOMINAL = 1.0             # weights are already fractions of each neuron's input, so unit gain is the natural scale
THETA_GF_DEG = 40.0         # GF fires at a consistent ~40 deg (Ache et al. 2019 Curr Biol 29:1073, verified)
CALIBRATION_LV_MS = (20, 40, 80)   # disc speeds used to derive the GF threshold (as bio calibration)
REST_Z = 6.0                # motor threshold = rest mean + REST_Z * rest std (invented convention, rest test only)
A_FRACTION = 0.5            # A threshold = this fraction of the weakest calibration disc's peak muscle drive
MUSCLE_DECAY = 0.9          # per-frame decay of the A muscle drive (tau ~10 frames; invented, as MotorDirectParams.decay)
MOTOR_FLOOR_HZ = 1e-3       # a motor threshold is never below this, even if the rest activity is exactly zero
ELEVATION_LIMIT_DEG = 60.0  # elevation beyond which an object leaves the looming detectors' field (invented; same value
                            # as the validated bio_strict path, a property of the scene encoding, not of the brain)


@dataclass(frozen=True)
class MotorThresholds:
    """Thresholds the motor map compares activity with. Derived on synthetic tests, never experiment inputs."""
    muscle_decay: float
    a_threshold: float          # on the leaky integral of the TTMn onset (Hz)
    walk_threshold: float       # DNp09 pooled activity (Hz)
    steer_threshold: float      # |left team - right team| of DNa01/DNa02 (Hz)
    back_threshold: float       # MDN pooled activity (Hz)


@dataclass(frozen=True)
class Calibration:
    network_hash: str           # the exact network these numbers were derived on
    rho: float                  # spectral radius of W at g = 1
    g: float                    # min(G_NOMINAL, STABILITY_MARGIN / rho)
    gf_threshold: float         # GF membrane threshold: mean membrane at THETA_GF_DEG over the calibration discs
    motor: MotorThresholds
    derivation: dict = field(default_factory=dict)   # the measurements behind each number (for the record)
    alpha: float = ALPHA
    substeps: int = SUBSTEPS
    clip_hz: float = CLIP_HZ
    spike_amp_hz: float = SPIKE_AMP_HZ
    refractory_steps: int = REFRACTORY_STEPS
    noise_sigma: float = NOISE_SIGMA

    def save(self, path: Path = CALIBRATION_FILE) -> None:
        path.write_text(json.dumps(asdict(self), indent=1, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path = CALIBRATION_FILE) -> "Calibration":
        d = json.loads(path.read_text(encoding="utf-8"))
        d["motor"] = MotorThresholds(**d["motor"])
        return cls(**d)

    @staticmethod
    def file_hash(path: Path = CALIBRATION_FILE) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

# Phase 3 (docs/SPEC_phase3.md section 3). Invented scalars, each fixed by a rule written before the test and run once on
# synthetic stimuli (a small moving dot, a static cue on the right) with `python -m brain.senses_calibrate`; never on game outcomes.
LC10A_GAIN = 16.0           # pursuit: per-neuron LC10a drive (rad read as Hz, as looming) at full arousal; midpoint of the window
LC10A_AZIMUTH_SPLIT = 90.0  # deg: azimuth at which a target is fully lateralised (share 0 / 1 beyond +-SPLIT)
GOAL_CUE_SALIENCE = 15.0    # home landmark: per-neuron drive onto the right LC10a, a world property set in the tool
PURSUIT_AROUSAL = 0.65      # fly-state input in [0, 1] scaling pursuit (set in the tool, never read from the fly); midpoint of the window 0.3-1.0
                            # where the real brain steers right/left/ahead on a synthetic dot and a static dot gives nothing (docs/SPEC_phase3.md section 11)
