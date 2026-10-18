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

    HOME_SENSE: bool = True      # INVENTED (fixed), Part M2b: the home signal (HOME_R into LC10a-R); off = 0 input (v2 senses). Default on = every earlier result
    HUM_SENSE: bool = False      # INVENTED (fixed), Part Q1: unused reachable '?' blocks hum into the 20 JO neurons (needs the JO brain, v2 senses)
    HUM_GAIN: float = 14.5342    # INVENTED (fixed), Part Q1: hum loudness = HUM_GAIN x theta_block (rad) into each JO neuron. FROZEN: chosen once so the press falls in the middle of the hit window (runs/Q1.md)
    SMELL_SENSE: bool = False    # INVENTED (fixed), Part M2: the live mushroom smells sweet into the attractive ORNs of the antenna on its side (needs the ORN brain, v2 senses)
    SMELL_GAIN: float = 213.9495 # INVENTED (fixed), Part M2: smell level = SMELL_GAIN x theta_mushroom (rad) into each attractive ORN of that antenna. FROZEN: = 49.7706 (the level where steer crosses -0.01 with HOME_R on) / 0.23263 rad (theta of the mushroom 64 px behind), runs/M2.md
    SENSES_VERSION: str = "v1"   # INVENTED (fixed): v1 = senses of Parts 1-7 (unchanged); v2 = Part S1 (flyrun/senses_v2.py)

    # --- motor (nb 09/14/19/20) ---
    MOTOR_VERSION: str = "v1"    # INVENTED (fixed): v1 = A_HOLD + COOLDOWN (Parts 1-7); v2 = Part S2 fly-held jump (needs SENSES_VERSION v2)
    RELEASE_THRESH: float = None # INVENTED (fixed), v2 only: A is released when TTMn < this; None = TTMN_THRESH (no hysteresis). Not tuned in S2.
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

# --- Senses v2 (Part S1). Only read when Knobs.SENSES_VERSION == "v2". ---
# Object sizes (w, h) in px. Height sets theta = 2 atan(h / 2d); width is stored for later clearance use.
# Enemy ids are the RAM type byte (0x0016+slot), identified empirically on 1-1 (runs/S1_senses_v2.md): 0x06 Goomba, 0x00 green Koopa.
# A Koopa in RAM state 2/3 is treated as a shell (16 x 16): NOT verified (the scripted run never stomps the 1-1 Koopa).
SIZE_TABLE = {"goomba": (16, 16), "koopa": (16, 24), "shell": (16, 16)}   # INVENTED (fixed)
ENEMY_TYPES = {0x06: "goomba", 0x00: "koopa"}                              # INVENTED (fixed): any other type byte is ignored
MARIO_BOX = (12, 16)       # INVENTED (fixed): Mario's (w, h) in px (small Mario; x = sprite left edge); deaths happened at gap 0 = dx 12
ENEMY_FEET_OFFSET = 8      # INVENTED (fixed): an enemy's RAM y (0x00CF+slot) is its feet y + 8 (measured: ground 184 vs surface 176)
MAX_JUMP_HEIGHT = 68       # INVENTED (fixed), measured (Part S2c, flyrun/measure_jump.py): apex above take-off of a full walking jump, px; caps the S3b pit tower
HUM_REACH = 64            # INVENTED (fixed), Q1: a '?' block hums only if its underside is <= this many px above the ground under it (a ground jump reaches ~68 px of rise)
PIT_GAIN_V2 = 1.0          # INVENTED (fixed): the pit tower's theta at gain 1 (the evolved PIT_GAIN knob is ignored in v2)

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
    "MOTOR_VERSION": ("fixed", "v1 = forced A_HOLD + COOLDOWN; v2 = the fly holds A while TTMn stays above threshold (Part S2)"),
    "HOME_SENSE": ("fixed", "M2b: toggle of the home signal (HOME_R into LC10a-R each frame); on by default"),
    "HUM_SENSE": ("fixed", "Q1: the hum cue (invented): the nearest unused reachable ? block hums into the 20 direct JO -> GF neurons (real wiring); off by default"),
    "HUM_GAIN": ("fixed", "Q1: hum loudness = HUM_GAIN x the block's angular size (rad); 14.5342, chosen once from the hit window and frozen (runs/Q1.md)"),
    "SMELL_SENSE": ("fixed", "M2: the smell cue (invented): the live mushroom drives the attractive ORNs (DM1, VA2, DM4) of the antenna on its side; off by default"),
    "SMELL_GAIN": ("fixed", "M2: smell level = SMELL_GAIN x the mushroom's angular size (rad); chosen once so the steering crosses -0.01 at 64 px, then frozen (runs/M2.md)"),
    "HUM_REACH": ("fixed", "Q1: a ? block hums only if its underside is <= 64 px above the ground under it"),
    "QBLOCK_TILES (level.py)": ("fixed", "tile ids 192 / 193 = unused ? block (hand-identified, O0)"),
    "RELEASE_THRESH": ("fixed", "v2: TTMn level below which A is released (default = TTMN_THRESH)"),
    "SENSES_VERSION": ("fixed", "v1 = old senses (all Part 1-7 results); v2 = Part S1 senses"),
    "SIZE_TABLE / ENEMY_TYPES": ("fixed", "v2 object sizes (Goomba 16x16, Koopa 16x24, shell 16x16) and the RAM type bytes (0x06, 0x00)"),
    "MARIO_BOX / ENEMY_FEET_OFFSET": ("fixed", "v2 geometry: Mario 12x16, enemy feet = RAM y - 8 (measured on 1-1)"),
    "PIT_GAIN_V2": ("fixed", "v2 pit tower theta at gain 1"),
    "MAX_JUMP_HEIGHT": ("fixed", "apex height of a full walking jump (68 px, measured, S2c); caps the S3b pit tower (min(W, 68))"),
    "RIM_TILES": ("fixed", "tile ids 16/17 = the rim of 1-1 pipe 4, counted as wall by senses v2 (S3 0a); pipes 1-3 use 18/19"),
    "pit base + tower (senses_v2.choose)": ("fixed", "S3c / SPEC.md B9: base = the hole, tower = 16 px wide on its far edge, top = highest rim - min(W, MAX_JUMP_HEIGHT); an invented shape"),
    "tile IDs / rows (level.py)": ("fixed", "SOLID_WALL {18..21, 97}, ground rows 11-12, empty 0: hand-identified on 1-1 "
                                            "(run 001 notes); meaning unverified on other levels"),
    "W_steer construction": ("fixed", "cast choice, top-40 LC10a->DNa intermediates, predicted-NT signs, "
                                      "row-normalisation (tutorials/20_steering.ipynb)"),
}


def toggle_set(k, enemy_input=True):
    """The drives switched on in a run (every M2b+ run log records this): looming (enemy / pipe / pit), home, hum, smell."""
    return dict(looming_enemy=bool(enemy_input), looming_pipe=bool(k.PIPE_SENSE), looming_pit=bool(k.PIT_SENSE), home=bool(k.HOME_SENSE), hum=bool(k.HUM_SENSE), smell=bool(k.SMELL_SENSE))
