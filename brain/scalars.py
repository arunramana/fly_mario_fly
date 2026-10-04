# What this file does, in plain English:
# The brain's own list of every hand-set or derived number, each tagged as
# measured (taken from the literature or the data), calibrated (derived on a
# synthetic test) or invented (a modelling choice). It is the single source for
# docs/SCALARS_BRAIN.md, which is generated from here and never written by hand.
# The old fly's list (config/params.py, docs/SCALARS.md) is not touched.
"""brain/scalars.py -- the brain registry (CLAUDE.md invariant 3, brain path).

    python -m brain.scalars        # rewrite docs/SCALARS_BRAIN.md

Values are read from `brain/calibration.py` (constants), `brain/manifest.py` (network rule) and
`brain/calibration.json` (derived), so the registry cannot drift from what the code runs; a test checks that every
public constant of `brain/calibration.py` is registered and that the document equals the generator's output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from brain import calibration as C
from brain import manifest as M

MEASURED, CALIBRATED, INVENTED = "measured", "calibrated", "invented"
KINDS = (MEASURED, CALIBRATED, INVENTED)
DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "SCALARS_BRAIN.md"


@dataclass(frozen=True)
class BrainScalar:
    name: str
    value: float | int
    unit: str
    kind: str                 # MEASURED | CALIBRATED | INVENTED
    lo: float                 # allowed range, a sanity bound, not a search interval
    hi: float
    source: str               # where the value or its convention comes from

    def __post_init__(self):
        assert self.kind in KINDS, self.kind
        assert self.lo <= self.value <= self.hi, f"{self.name}={self.value} outside [{self.lo}, {self.hi}]"


def _constants() -> list[BrainScalar]:
    S = BrainScalar
    return [
        S("ALPHA", C.ALPHA, "per substep", INVENTED, 0.05, 1.0, "tau ~3 substeps (~5 ms); same as fly.network.dynamics.ALPHA"),
        S("SUBSTEPS", C.SUBSTEPS, "steps/frame", INVENTED, 1, 100, "time discretisation: 10 network steps per 60 fps frame (SPEC_jump.md)"),
        S("CLIP_HZ", C.CLIP_HZ, "Hz", INVENTED, 50.0, 500.0, "cap chosen from central-neuron peak rates of order 1e2 Hz (Bhandawat 2007; supports the order of magnitude only)"),
        S("SPIKE_AMP_HZ", C.SPIKE_AMP_HZ, "Hz", INVENTED, 1.0, 200.0, "one spike per 16.7 ms frame = 60 Hz (a convention of the frame rate)"),
        S("REFRACTORY_STEPS", C.REFRACTORY_STEPS, "substeps", INVENTED, 0, 10, "~5 ms absolute refractory period of the spiking cells"),
        S("NOISE_SIGMA", C.NOISE_SIGMA, "units/substep", INVENTED, 0.0, 0.1, "membrane noise per neuron, the project's value"),
        S("STABILITY_MARGIN", C.STABILITY_MARGIN, "ratio", INVENTED, 0.1, 1.0, "largest allowed loop gain rho(W)*g (15 % margin for noise)"),
        S("G_NOMINAL", C.G_NOMINAL, "ratio", INVENTED, 0.1, 10.0, "weights are fractions of each neuron's input, unit gain is the natural scale"),
        S("THETA_GF_DEG", C.THETA_GF_DEG, "deg", MEASURED, 10.0, 90.0, "GF fires at a consistent ~40 deg (Ache et al. 2019 Curr Biol 29:1073)"),
        S("REST_Z", C.REST_Z, "std", INVENTED, 1.0, 20.0, "motor threshold = rest mean + REST_Z * rest std (convention, rest test only)"),
        S("A_FRACTION", C.A_FRACTION, "fraction", INVENTED, 0.05, 1.0, "A threshold = this fraction of the weakest calibration disc's peak muscle drive"),
        S("MUSCLE_DECAY", C.MUSCLE_DECAY, "per frame", INVENTED, 0.0, 0.999, "A-muscle leaky integral, tau ~10 frames (as MotorDirectParams.decay)"),
        S("CALIBRATION_NOISE_SEEDS", C.CALIBRATION_NOISE_SEEDS, "seeds", INVENTED, 1, 1000, "noise seeds each derived threshold is averaged over (docs/SPEC_phase3.md section 12); a convention, never chosen on game outcomes"),
        S("CALIBRATION_SEED0", C.CALIBRATION_SEED0, "seed", INVENTED, 0, 10**6, "first calibration noise seed (7000-7029); an identifier, not a tuned value"),
        S("MOTOR_FLOOR_HZ", C.MOTOR_FLOOR_HZ, "Hz", INVENTED, 0.0, 0.1, "a motor threshold is never below this"),
        S("ELEVATION_LIMIT_DEG", C.ELEVATION_LIMIT_DEG, "deg", INVENTED, 10.0, 90.0,
          "elevation beyond which an object leaves the looming field (same as the validated bio_strict path)"),
        S("LC10A_GAIN", C.LC10A_GAIN, "Hz per unit salience", INVENTED, 0.0, 100.0, "pursuit drive onto LC10a at full arousal; midpoint of the window where the real brain steers correctly and MDN stays silent (docs/SPEC_phase3.md section 3, synthetic dot test only)"),
        S("LC10A_AZIMUTH_SPLIT", C.LC10A_AZIMUTH_SPLIT, "deg", INVENTED, 1.0, 90.0, "azimuth beyond which a target drives one LC10a side only; largest candidate that still steers and walks correctly on the synthetic dot test (docs/SPEC_phase3.md section 3)"),
        S("PURSUIT_AROUSAL", C.PURSUIT_AROUSAL, "fraction", INVENTED, 0.0, 1.0, "default of the tool's fly-state arousal input that scales pursuit; midpoint of the window where the real brain steers correctly on a synthetic dot and a static dot gives nothing (docs/SPEC_phase3.md section 11). Not read from the fly's output"),
        S("GOAL_CUE_SALIENCE", C.GOAL_CUE_SALIENCE, "Hz", INVENTED, 0.0, 100.0, "home landmark: static drive onto the right LC10a. It moves the 'go right' assumption to the senses, it does not remove it; midpoint of the window where the real brain walks right and nothing presses Left (docs/SPEC_phase3.md section 3)"),
        S("K_HOPS", M.K_HOPS, "hops", INVENTED, 1, 6, "network rule: neurons within k hops of a path (INVEST_phase0 2.4 B)"),
        S("MIN_SYNAPSES", M.MIN_SYNAPSES, "synapses", INVENTED, 1, 50, "network rule: smallest connection kept (INVEST_phase0 2.4 B)"),
    ] + [S(f"CALIBRATION_LV_MS[{i}]", v, "ms", INVENTED, 5, 200, "disc speeds used to derive the GF threshold") for i, v in enumerate(C.CALIBRATION_LV_MS)]


def _experiments() -> list[BrainScalar]:
    """E1 scene and evaluation conventions (docs/SPEC_tool_phase2.md). Conventions of the experiment, fixed before any run."""
    from brain import e1
    from brain.scenes import load_scene
    S, log = BrainScalar, load_scene().log
    return [
        S("E1_SCENE_WALK_FRAMES", log[0][1], "frames", INVENTED, 1, 300, "scene log: run right from reset until the first Goomba is on screen (checked only that it is)"),
        S("E1_SCENE_SETTLE_FRAMES", log[1][1], "frames", INVENTED, 1, 120, "scene log: release all buttons so Mario's x speed decays to zero"),
        S("E1_GRACE_FRAMES", e1.E1_GRACE_FRAMES, "frames", INVENTED, 1, 600, "survived = alive this long after the Goomba stops being a threat (1 s)"),
        S("E1_MAX_FRAMES", e1.E1_MAX_FRAMES, "frames", INVENTED, 100, 3000, "episode bound; the Goomba reaches a Mario who starts stationary in ~150 frames (the shuffled arm's Left presses are looming-driven, not noise)"),
        S("E1_SPRITE_PX", e1.SPRITE_PX, "px", INVENTED, 8, 32, "contact box = the registry's 16 px sprite width (Goomba and small Mario only)"),
        S("E1_LESION_CLAMP_HZ", e1.E1_LESION_CLAMP_HZ, "Hz", INVENTED, 0.0, 0.0, "control-only lesion arm: both Giant Fiber cells held at zero output (removal, never injection); 0 is the definition of silenced"),
    ] + _phase3_experiments()


def _phase3_experiments() -> list[BrainScalar]:
    """E0 and E3 conventions (docs/SPEC_phase3.md section 6): experiment definitions fixed before any run, not circuit scalars."""
    from brain import goal_eval
    from brain.scenes import E3_SCENE_ID, load_scene
    S, log = BrainScalar, load_scene(E3_SCENE_ID).log
    return [
        S("E0_GOAL_X", goal_eval.E0_GOAL_X, "px", INVENTED, 100, 440, "E0 goal: world x on the flat stretch before the first pipe (x = 448); reached = Mario's x at or beyond it"),
        S("E0_MAX_FRAMES", goal_eval.E0_MAX_FRAMES, "frames", INVENTED, 100, 3000, "E0 episode bound (10 s)"),
        S("E3_MAX_FRAMES", goal_eval.E3_MAX_FRAMES, "frames", INVENTED, 50, 3000, "E3 episode bound: below the frame (183) at which the returning mushroom reaches a Mario who presses nothing, so passivity cannot pass"),
        S("E3_SCENE_WALK_FRAMES", log[0][1], "frames", INVENTED, 1, 300, "scene log: walk right to the first power-up block (checked only that a mushroom is released)"),
        S("E3_SCENE_STAND_FRAMES", log[1][1], "frames", INVENTED, 1, 120, "scene log: stand still under the block"),
        S("E3_SCENE_JUMP_FRAMES", log[2][1], "frames", INVENTED, 1, 60, "scene log: A held to jump straight up and hit the block"),
        S("E3_SCENE_LAND_FRAMES", log[3][1], "frames", INVENTED, 1, 120, "scene log: release everything so Mario lands and stands still"),
    ]


def _derived(cal: C.Calibration) -> list[BrainScalar]:
    """Numbers worked out on synthetic stimuli (disc or rest test); they carry the hash of the network they came from."""
    S, m = BrainScalar, cal.motor
    return [
        S("g", cal.g, "ratio", CALIBRATED, 0.0, 10.0, "min(G_NOMINAL, STABILITY_MARGIN / rho(W)); rho by sparse eigensolve"),
        S("gf_threshold", cal.gf_threshold, "membrane", CALIBRATED, 0.0, 10.0, "mean GF membrane at THETA_GF_DEG over the calibration discs and CALIBRATION_NOISE_SEEDS noise seeds"),
        S("a_threshold", m.a_threshold, "Hz", CALIBRATED, 0.0, 100.0, "A_FRACTION x weakest calibration disc's peak muscle drive (mean over the noise seeds)"),
        S("walk_threshold", m.walk_threshold, "Hz", CALIBRATED, 0.0, 100.0, "rest mean + REST_Z std of DNp09 (pooled over the noise seeds)"),
        S("steer_threshold", m.steer_threshold, "Hz", CALIBRATED, 0.0, 100.0, "rest mean + REST_Z std of |DNa01/02 left - right| (pooled over the noise seeds)"),
        S("back_threshold", m.back_threshold, "Hz", CALIBRATED, 0.0, 100.0, "rest mean + REST_Z std of MDN (pooled over the noise seeds)"),
    ]


def all_scalars() -> list[BrainScalar]:
    return _constants() + _experiments() + _derived(C.Calibration.load())


def generate() -> str:
    rows = all_scalars()
    counts = {k: sum(r.kind == k for r in rows) for k in KINDS}
    cal = C.Calibration.load()
    out = ["# Brain scalars (generated)", "",
           "Generated by `python -m brain.scalars` from `brain/calibration.py`, `brain/manifest.py` and `brain/calibration.json`. "
           "Do not edit by hand. The legacy registry (`config/params.py`, `docs/SCALARS.md`) is separate and frozen.", "",
           f"Total: **{len(rows)}** = {counts[INVENTED]} invented + {counts[CALIBRATED]} calibrated + {counts[MEASURED]} measured. "
           f"Derived numbers belong to network `{cal.network_hash}` (calibration file hash `{C.Calibration.file_hash()}`).", "",
           "Note: *measured* here means taken from the literature or the data, unlike the legacy registry (docs/SCALARS.md), where it means simulated and picked by a sweep. "
           "Kinds: *measured* = taken from the literature or the data; *calibrated* = derived on a synthetic stimulus "
           "(disc or rest test) and then fixed; *invented* = a modelling choice or convention. None is tuned on game outcomes. "
           "Ranges are sanity bounds, not search intervals.", "",
           "| Name | Value | Unit | Kind | Range | Source |", "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| `{r.name}` | {r.value:.6g} | {r.unit} | {r.kind} | [{r.lo:g}, {r.hi:g}] | {r.source} |")
    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    DOC_PATH.write_text(generate(), encoding="utf-8", newline="\n")
    print(f"wrote {DOC_PATH}")
