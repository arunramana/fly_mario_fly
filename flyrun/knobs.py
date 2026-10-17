"""Every hand-set scalar for flyrun lives here (except the tile IDs/rows in level.py, hand-identified on 1-1, which
the INVENTED registry at the bottom lists).

All of these are INVENTED (none is read off the connectome); each is tagged "INVENTED (evolved)" (searched by
CMA-ES, flyrun/genome.py) or "INVENTED (fixed)" (set by hand). Scalars that are not Knobs fields (BLIND_PX, ...) are
at the bottom of this file, with the INVENTED registry that clips/numbers.md is generated from.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Knobs:
    # --- network dynamics (nb 04/09) ---
    G: float = 0.5               # INVENTED (evolved): global recurrent gain; nb04 pegs at CLIP for g=2
    ALPHA: float = 0.3           # INVENTED (fixed): leak/mix rate of the rate update
    CLIP: float = 50.0           # INVENTED (fixed): activity ceiling
    SUBSTEPS: int = 10           # INVENTED (fixed): network steps per game frame

    # --- senses (nb 08/09/19) ---
    W_ENEMY: float = 16.0        # INVENTED (fixed): Goomba width in px for theta = 2 atan(w / 2d)
    HOME_R: float = 0.5          # INVENTED (evolved): constant drive into LC10a-R (homing cue, nb 19/20)

    STIM_COMBINE: str = "sum"    # INVENTED (fixed), not evolved: "max" = largest-theta object only,
                                 # "sum" = every visible object adds its theta and |dtheta|
    SENSOR_NOISE: float = 0.30   # INVENTED (fixed), not evolved: sigma of multiplicative Gaussian noise on each
                                 # LC4/LPLC2 input (fraction of that input); per-episode seeded
    NOISE_MODE: str = "common"   # INVENTED (fixed), not evolved: "neuron" = independent per neuron,
                                 # "common" = one draw per frame shared by the whole detector population
    THETA_RULE_DEG: float = 43.6 # INVENTED (evolved): baseline-only A threshold of the no-brain theta rule
    PIPE_SENSE: bool = True      # INVENTED (fixed): feed pipe/wall faces to the loom detectors (nb 13)
    PIT_SENSE: bool = True       # INVENTED (fixed): feed pits to the loom detectors (a pit has no face; nb 15)
    PIT_GAIN: float = 1.0        # INVENTED (evolved): scale on the pit's theta (nb 15 used 1.0)

    # --- motor (nb 09/14/19/20) ---
    TTMN_THRESH: float = 0.10    # INVENTED (evolved): mean TTMn activity that triggers A (nb 09 cleared value)
    A_HOLD: int = 12             # INVENTED (evolved): frames A stays down once triggered (nb 09/14)
    COOLDOWN: int = 10           # INVENTED (evolved): frames A is refused after a hold (nb 14 grid: hold 24 + cd>=10 clears)
    DNP09_THRESH: float = 0.05   # INVENTED (fixed): mean DNp09 activity that means "walk Right" (nb 19/20)
    STEER_THRESH: float = 0.01   # INVENTED (fixed): |mean DNa_R - mean DNa_L| needed to steer (nb 20)


# ---------------------------------------------------------------------------------------------------
# Hand-set scalars that are not Knobs fields (moved here in Part 6b, audit 006 #3). Nothing below is read off
# the connectome. Imported by run.py / episodes4.py / fitness.py / baselines.py / scripted.py.
BLIND_PX = 60              # INVENTED (fixed): an A onset with no threat within this many px is counted "blind"
BLIND_PENALTY = 50         # INVENTED (fixed): fitness penalty per blind press (shapes the evolved genomes)
FLAG_BONUS = 10000         # INVENTED (fixed): fitness bonus for reaching the flag
SPAM_FIXED_HOLD = 18       # INVENTED (fixed): spam_fixed baseline A hold (the Part 4 fly's cadence)
SPAM_FIXED_COOLDOWN = 3    # INVENTED (fixed): spam_fixed baseline cooldown
RANDOM_A_P = 0.05          # INVENTED (fixed): right_randA baseline, per-frame P(A)
SCRIPT_HOLD = 28           # INVENTED (fixed): scripted driver's A frames per jump (assisted/diagnostic only)

# Every non-connectome piece, with how it got its value. clips/numbers.md "Invented pieces" is generated from this.
#   "evolved" = searched by CMA-ES on TRAIN episodes; "fixed" = set by hand and never searched.
INVENTED = {
    "G": ("evolved", "global recurrent gain"),
    "TTMN_THRESH": ("evolved", "TTMn activity that triggers A"),
    "A_HOLD": ("evolved", "frames A is held once triggered (a forced hold, CONTROL_AUDIT.md)"),
    "COOLDOWN": ("evolved", "frames A is refused after a hold"),
    "HOME_R": ("evolved", "constant rightward drive into LC10a-R every frame: the direction of travel is ours"),
    "PIT_GAIN": ("evolved", "scale of the pit cue"),
    "THETA_RULE_DEG": ("evolved", "no-brain baseline's threshold (theta arm only)"),
    "PIT_SENSE": ("fixed", "the PIT CUE: a pit has no face, so its width is fed to LC4/LPLC2 as a looming angle"),
    "PIPE_SENSE": ("fixed", "pipe/wall faces fed to LC4/LPLC2 as a looming angle (face height used as width)"),
    "W_ENEMY": ("fixed", "Goomba width used in theta = 2 atan(w / 2d)"),
    "STIM_COMBINE": ("fixed", "'sum': every visible object adds its theta and |dtheta|"),
    "SENSOR_NOISE": ("fixed", "multiplicative Gaussian noise on the LC4/LPLC2 inputs (0 for display runs, 0.05 TRAIN/HOLDOUT)"),
    "NOISE_MODE": ("fixed", "'common': one noise draw per frame for the whole population"),
    "ALPHA": ("fixed", "leak/mix rate of the rate update"),
    "CLIP": ("fixed", "activity ceiling"),
    "SUBSTEPS": ("fixed", "network steps per game frame"),
    "DNP09_THRESH": ("fixed", "DNp09 activity that means 'walk right'"),
    "STEER_THRESH": ("fixed", "|DNa_R - DNa_L| needed to steer"),
    "BLIND_PX": ("fixed", "blind-press metric distance"),
    "BLIND_PENALTY": ("fixed", "fitness penalty per blind press"),
    "FLAG_BONUS": ("fixed", "fitness bonus for the flag"),
    "SPAM_FIXED_HOLD/COOLDOWN": ("fixed", "spam_fixed baseline cadence 18/3"),
    "RANDOM_A_P": ("fixed", "right_randA baseline P(A)"),
    "SCRIPT_HOLD": ("fixed", "scripted driver jump length (assisted tests only, never in fitness)"),
    "tile IDs / rows (level.py)": ("fixed", "SOLID_WALL {18..21, 97}, ground rows 11-12, empty 0: hand-identified on 1-1 "
                                            "(run 001 notes); meaning unverified on other levels"),
    "W_steer construction": ("fixed", "cast choice, top-40 LC10a->DNa intermediates, predicted-NT signs, "
                                      "row-normalisation (tutorials/20_steering.ipynb)"),
}
