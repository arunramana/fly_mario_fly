# What this file does, in plain English:
# The read-only catalogue the tool's Experiments and Mechanisms screens show:
# every planned experiment (E0-E8) and every mechanism of the plan, each with
# where it comes from, what it needs, how real its evidence is and whether it
# exists yet. It runs nothing and changes nothing. The honest labels matter:
# for example the looming mechanism enters at early feature neurons (LPLC2,
# LC4), not at the photoreceptors, and the catalogue says so.
"""brain/library.py -- docs/REDESIGN_PLAN.md sections 3.3 and 4 as data (docs/SPEC_tool_phase2.md section 5).

`status` is "built" (code exists and was validated), "runnable" (an experiment the tool can run today) or "planned".
Nothing in a library entry is an input to the brain; the list is documentation the UI renders.
"""

from __future__ import annotations

from dataclasses import dataclass

from brain.e1 import CRITERION
from brain.scenes import E1_SCENE_ID

PLAN = "docs/REDESIGN_PLAN.md"


@dataclass(frozen=True)
class MechanismEntry:
    id: str
    name: str
    cue: str                     # what in the scene drives it
    entry_neurons: str           # the sensory-tier neurons it may excite (nothing deeper)
    entry_tier: str              # "feature-level (D1)" | "receptor" | "n/a"
    evidence: str
    origin: str                  # where the code or the idea comes from
    status: str                  # "built" | "planned" | "investigation"
    note: str = ""


@dataclass(frozen=True)
class ExperimentEntry:
    id: str
    name: str
    scene: str
    mechanisms: tuple[str, ...]  # MechanismEntry ids switched on
    criterion: str
    controls: str
    origin: str
    status: str                  # "runnable" | "planned"
    runner: str = ""             # module that runs it ("" = none yet)


CONTROLS = "20 held-out seeds, real vs degree-preserving shuffled connectome"

MECHANISMS: tuple[MechanismEntry, ...] = (
    MechanismEntry("looming", "Looming threat", "an enemy ahead of Mario; its angular size theta = 2 atan(w / 2d) and its growth",
                   "LPLC2 (size), LC4 (speed), both hemispheres", "feature-level (D1)",
                   "Ache et al. 2019 Curr Biol 29:1073 (GF fires at ~40 deg); the encoding is derived on a synthetic disc",
                   "brain/mechanisms.py LoomingMechanism (ported from bridge/loom_disc.py); theta from brain/perception.py",
                   "built", "Enters at early feature neurons, not photoreceptors: the stimulus is already a looming signal, "
                   "not a retinal image. Validated on the disc and on a ground-level object, never on game outcomes."),
    MechanismEntry("expanding_obstacle", "Expanding obstacle", "a wall or pipe ahead", "same looming entry", "feature-level (D1)",
                   "same as looming", PLAN + " 3.3 (built opt-in in the legacy path only)", "planned",
                   "Not ported to the new path yet. Sprite geometry for non-Goomba objects must be re-validated first."),
    MechanismEntry("food_smell", "Food smell", "a mushroom or '?' block", "attractive olfactory receptor neurons, left and right",
                   "receptor", "to verify (INVEST_phase0)", PLAN + " 3.3; legacy odour circuit enters mid-pathway", "planned"),
    MechanismEntry("aversive_smell", "Aversive smell", "an enemy", "aversive olfactory receptor neurons", "receptor",
                   "to verify", PLAN + " 3.3", "planned"),
    MechanismEntry("sweet_taste", "Sweet taste (reward)", "touching the mushroom, hitting '?'",
                   "sugar taste neurons, then dopamine neurons through real wiring", "receptor", "to verify", PLAN + " 3.3", "planned",
                   "No dopamine injection: reward arrives only through the sensed pathway."),
    MechanismEntry("pain", "Pain or heat (punishment)", "getting hit, dying", "nociceptive neurons, then dopamine neurons through real wiring",
                   "receptor", "to verify", PLAN + " 3.3", "planned"),
    MechanismEntry("goal_direction", "Goal direction", "'right is the way'", "a light or attractive cue to the right (phototaxis)",
                   "feature-level (D1)", "to verify", PLAN + " 3.3, decision D2", "planned",
                   "Replaces the legacy home_bias and walk_drive (both injected drives)."),
    MechanismEntry("gap_width", "Gap width", "a pit ahead", "C2/C3 (parallax) toward the central complex", "feature-level (D1)",
                   "Pick & Strauss 2005, Triphan 2010/2016, Krause 2019", PLAN + " 3.3, decision D3", "investigation",
                   "The route in MaleCNS is not yet traced."),
    MechanismEntry("hunger", "Hunger", "fly state", "internal state", "n/a", "-", "legacy config (character tab)", "planned"),
)

EXPERIMENTS: tuple[ExperimentEntry, ...] = (
    ExperimentEntry("E0", "Walk to the goal", "flat ground", ("goal_direction",), "reaches the right edge in >= 18/20; shuffled does not",
                    CONTROLS, PLAN + " section 4", "planned"),
    ExperimentEntry("E1", "Jump the Goomba", E1_SCENE_ID, ("looming",),
                    f"survives the encounter in >= {CRITERION['real_survived_min']}/20; shuffled <= {CRITERION['shuffled_survived_max']}/20 "
                    "(also reported: GF fired before contact, theta and distance at the first GF spike)",
                    CONTROLS + "; plus a GF-lesion control arm (real connectome, both Giant Fiber cells silenced; control-only, "
                    "run only from the E1 eval/CLI, not selectable here)",
                    PLAN + " section 4; scene brain/scenes/e1_goomba_approach.json (scripted action log, deterministic)",
                    "runnable", "brain.e1"),
    ExperimentEntry("E2a", "Obstacle", "one pipe", ("looming", "expanding_obstacle"), "gets past in >= 14/20", CONTROLS, PLAN + " section 4", "planned"),
    ExperimentEntry("E2b", "Gap", "one pit", ("looming", "gap_width"), "crosses crossable gaps, refuses wide ones", CONTROLS, PLAN + " section 4", "planned"),
    ExperimentEntry("E3", "Find food", "mushroom released from a block", ("looming", "food_smell"), "touches the mushroom in >= 14/20",
                    CONTROLS, PLAN + " section 4", "planned"),
    ExperimentEntry("E4", "Learn from reward", "E3 repeated", ("food_smell", "sweet_taste"), "touch rate rises with training; shuffled does not",
                    CONTROLS, PLAN + " section 4", "planned"),
    ExperimentEntry("E5", "Learn from mistakes", "E1 repeated with hits", ("looming", "pain"), "hit rate falls with training", CONTROLS,
                    PLAN + " section 4", "planned"),
    ExperimentEntry("E6", "1-1 in segments", "1-1 split at savestates", ("looming", "goal_direction"), "each segment passes", CONTROLS,
                    PLAN + " section 4", "planned"),
    ExperimentEntry("E7", "Win 1-1", "full level", ("looming", "goal_direction"), "win rate rises on held-out seeds and beats shuffled",
                    CONTROLS, PLAN + " section 4", "planned"),
    ExperimentEntry("E8", "Transfer", "1-2, 1-3, 1-4", ("looming", "goal_direction"), "distance vs shuffled, no retraining", CONTROLS,
                    PLAN + " section 4", "planned"),
)


def mechanism(mechanism_id: str) -> MechanismEntry:
    return next(m for m in MECHANISMS if m.id == mechanism_id)


def experiment(experiment_id: str) -> ExperimentEntry:
    return next(e for e in EXPERIMENTS if e.id == experiment_id)
