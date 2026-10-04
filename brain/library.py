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
from brain.baseline import BASELINE_MAX_FRAMES, BASELINE_STUCK_FRAMES
from brain.goal_eval import CRITERIA, E0_GOAL_X, E0_MAX_FRAMES, E3_MAX_FRAMES
from brain.scenes import B11_SCENE_ID, E0_SCENE_ID, E1_SCENE_ID, E3_SCENE_ID

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
    MechanismEntry("food_smell", "Food smell (no innate effect; revisit with learning)", "a mushroom or '?' block",
                   "attractive olfactory receptor neurons, left and right", "receptor",
                   "docs/INVESTIGATION_phase3.md: on the real wiring attractive receptor neurons never drive walking and drive steering at "
                   "< 0.3 x threshold even at 200 Hz; their net effect on DNp09 and MDN is inhibitory",
                   PLAN + " 3.3; legacy odour circuit enters mid-pathway", "no innate effect",
                   "Kept in the library as an honest innate fail: not used by any experiment. Revisit once the mushroom body can learn "
                   "(Phase 4)."),
    MechanismEntry("aversive_smell", "Aversive smell", "an enemy", "aversive olfactory receptor neurons", "receptor",
                   "to verify", PLAN + " 3.3", "planned"),
    MechanismEntry("sweet_taste", "Sweet taste (reward)", "touching the mushroom, hitting '?'",
                   "sugar taste neurons, then dopamine neurons through real wiring", "receptor", "to verify", PLAN + " 3.3", "planned",
                   "No dopamine injection: reward arrives only through the sensed pathway."),
    MechanismEntry("pain", "Pain or heat (punishment)", "getting hit, dying", "nociceptive neurons, then dopamine neurons through real wiring",
                   "receptor", "to verify", PLAN + " 3.3", "planned"),
    MechanismEntry("pursuit", "Pursuit of small moving objects", "a visible, small, moving object of a pursued kind (set per object kind "
                   "on the Mechanisms tab; default: mushroom / other collectibles, a Goomba is NOT pursued)",
                   "LC10a, left and right (same-side eye -> ipsilateral turn)", "feature-level (D1)",
                   "Ribeiro et al. 2018 Cell 174:607; Hindmarsh Sten et al. 2021 Nature 595:549 (snippet level; the turn direction is an "
                   "assumption). Gain is scaled by a fly-state arousal input set in the tool (Chiappe 2010; Maimon 2010, from memory).",
                   "brain/mechanisms.py PursuitMechanism; docs/SPEC_phase3.md sections 3-4", "built",
                   "Scalars LC10A_GAIN and LC10A_AZIMUTH_SPLIT are invented, fixed on a synthetic dot test, never on the game. "
                   "Arousal (PURSUIT_AROUSAL, invented, default fixed on the same synthetic dot test) is a fly-state INPUT set on the Mechanisms tab; "
                   "nothing reads the fly's own output for it. Necessity control in E3: the real_no_pursuit arm (eval only)."),
    MechanismEntry("goal_direction", "Home landmark (goal on the right)", "a persistent cue on the right; strength GOAL_CUE_SALIENCE "
                   "(a world property, set on the Mechanisms tab)", "right LC10a only", "feature-level (D1)",
                   "invented world-level cue: LC10a prefers small moving objects, so the literature does not license a static cue",
                   "brain/mechanisms.py HomeLandmarkMechanism; docs/SPEC_phase3.md", "built",
                   "HONEST LABEL: this moves the 'go right' assumption into the senses; it does not remove it. The scalar is invented and "
                   "counted. The shuffled arms always receive the same cue. Replaces the legacy home_bias and walk_drive. Necessity control in "
                   "E0: the real_no_landmark arm (eval only). E0's 20/20 is one deterministic trajectory, not 20 independent successes."),
    MechanismEntry("gap_width", "Gap width", "a pit ahead", "C2/C3 (parallax) toward the central complex", "feature-level (D1)",
                   "Pick & Strauss 2005, Triphan 2010/2016, Krause 2019", PLAN + " 3.3, decision D3", "investigation",
                   "The route in MaleCNS is not yet traced."),
    MechanismEntry("hunger", "Hunger", "fly state", "internal state", "n/a", "-", "legacy config (character tab)", "planned"),
)

EXPERIMENTS: tuple[ExperimentEntry, ...] = (
    ExperimentEntry("E0", "Walk to the goal", E0_SCENE_ID, ("goal_direction",),
                    f"reaches world x {E0_GOAL_X} within {E0_MAX_FRAMES} frames in >= {CRITERIA['E0']['real_reached_min']}/20; "
                    f"shuffled <= {CRITERIA['E0']['shuffled_reached_max']}/20 (also reported: frames to reach, GF fired, GF output and TTMn max)",
                    CONTROLS + "; plus a class-preserving shuffle arm (informative, no pass/fail: does type-level wiring suffice?). The landmark is an invented world cue: it moves the 'go right' "
                    "assumption to the senses, it does not remove it",
                    PLAN + " section 4; scene brain/scenes/e0_walk_goal.json (level start, enemies cleared)", "runnable", "brain.goal_eval"),
    ExperimentEntry("E1", "Jump the Goomba", E1_SCENE_ID, ("looming",),
                    f"survives the encounter in >= {CRITERION['real_survived_min']}/20; shuffled <= {CRITERION['shuffled_survived_max']}/20 "
                    "(also reported: GF fired before contact, theta and distance at the first GF spike)",
                    CONTROLS + "; plus a GF-lesion control arm (real connectome, both Giant Fiber cells silenced; control-only, "
                    "run only from the E1 eval/CLI, not selectable here)",
                    PLAN + " section 4; scene brain/scenes/e1_goomba_approach.json (scripted action log, deterministic)",
                    "runnable", "brain.e1"),
    ExperimentEntry("E2a", "Obstacle", "one pipe", ("looming", "expanding_obstacle"), "gets past in >= 14/20", CONTROLS, PLAN + " section 4", "planned"),
    ExperimentEntry("E2b", "Gap", "one pit", ("looming", "gap_width"), "crosses crossable gaps, refuses wide ones", CONTROLS, PLAN + " section 4", "planned"),
    ExperimentEntry("E3", "Pursue the mushroom by sight", E3_SCENE_ID, ("pursuit",),
                    f"reaches the mushroom within {E3_MAX_FRAMES} frames in >= {CRITERIA['E3']['real_reached_min']}/20; "
                    f"shuffled <= {CRITERIA['E3']['shuffled_reached_max']}/20 (a Mario who presses nothing does not reach it in that time)",
                    CONTROLS + "; plus a class-preserving shuffle arm (informative, no pass/fail) and the necessity control real_no_pursuit (real wiring, pursuit off; E0 has real_no_landmark); both eval-only controls, not selectable in Run/play. Smell is NOT used (no innate effect, see the food_smell mechanism)",
                    PLAN + " section 4 (smell replaced by sight, docs/INVESTIGATION_phase3.md); scene brain/scenes/e3_mushroom.json "
                    "(action log, deterministic). Fresh-seed result (seeds 5100-5119): real 20/20 (near-deterministic, median 105.5, "
                    "frames 102-106), real_no_pursuit 0/20, degree shuffle 0/20 (the pass/fail null); the class-preserving shuffle reached 3/20, "
                    "reported as is (informative arm, no pass/fail; E3 accepted). Also: E1 class-shuffled survives about as often as real "
                    "(13/20 vs 12/20), so E1 shows type-level wiring matters, not neuron-level wiring", "runnable", "brain.goal_eval"),
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
    ExperimentEntry("B11", "1-1 innate baseline", B11_SCENE_ID, ("looming", "pursuit", "goal_direction"),
                    "none: a BASELINE, not a criterion, no pass/fail. Reported: max x (mean with bootstrap CI, median), how each run ends "
                    "(level complete, death by enemy / pit / other, stuck, timeout), Goombas jumped, A-tap fraction and A-run lengths, power-up "
                    "reached, GF output and TTMn max",
                    "real vs degree-preserving shuffled vs class-preserving shuffled connectome, 20 seeds (6000-6019: fresh, but 6000-6029 were "
                    "noise seeds of Phase 3b diagnostic runs on the E1 scene), run once. All three mechanisms are ON; the home landmark is an "
                    f"invented world cue (it moves the 'go right' assumption into the senses). Bounds are invented conventions: {BASELINE_MAX_FRAMES} "
                    f"frames, stuck = no new max x for {BASELINE_STUCK_FRAMES} frames",
                    "docs/SPEC_baseline_1-1.md; real level 1-1 from reset (brain/scenes/b11_baseline.json: no actions, no enemy clearing, no RAM edits)",
                    "runnable", "brain.baseline"),
)


def mechanism(mechanism_id: str) -> MechanismEntry:
    return next(m for m in MECHANISMS if m.id == mechanism_id)


def experiment(experiment_id: str) -> ExperimentEntry:
    return next(e for e in EXPERIMENTS if e.id == experiment_id)
