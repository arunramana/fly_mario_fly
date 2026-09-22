"""
run_steering.py -- SPEC_steering.md: DNa01/DNa02 steering under a constant
home bias, competing with a mushroom-odour signal read from RAM, plus a
contact-based climbing reflex. SPEC_terrain.md adds two more layers on top:
a pit-triggered graded long jump (DNp01's own output recruiting DLMn via
the real GFC1-4 relay) and a DNp09 speed circuit that finally lets Mario
stop holding B unconditionally. The jump circuit (DNp01/TTMn) itself is
untouched -- imported from run_mario.py and stepped exactly as
compare_controllers.py's make_circuit_decider does.

    .venv/Scripts/python.exe run_steering.py
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import tempfile
from pathlib import Path

import setuptools  # noqa: F401  -- must import before gym on py3.12
import numpy as np
import pandas as pd
from PIL import Image
import gym_super_mario_bros
from nes_py.wrappers import JoypadSpace

import dynamics
import tile_ram
from load_cached import load as load_jump
from load_steering_cached import load as load_steering
from load_takeoff_cached import load as load_takeoff
from load_speed_cached import load as load_speed
from load_mdn_cached import load as load_mdn
from load_dnp02_cached import load as load_dnp02

# SPEC_throughput.md: loading all 6 circuits from their on-disk parquet
# cache takes ~6.8s -- measured, not assumed -- versus well under a second
# for an actual short episode's worth of simulation. That gap dwarfs
# anything frame_skip/savestates/Pool can save, so it's the first thing
# fixed here: memoize each load_*() call per PROCESS (module-global, not
# per-call), so repeated main() calls in the same process (or the same
# worker, across a multiprocessing.Pool's episodes) pay the ~6.8s once and
# reuse it, instead of re-reading the cache from disk every episode.
_circuit_cache = {}


def _memo_load(key, loader, *args, **kwargs):
    if key not in _circuit_cache:
        _circuit_cache[key] = loader(*args, **kwargs)
    return _circuit_cache[key]
from run_mario import (ADDR_MARIO_X, ADDR_MARIO_PAGE, ADDR_ENEMY_X, ADDR_ENEMY_ACTIVE,
                        ADDR_ENEMY_TYPE, POWERUP_ID,
                        N_ENEMY_SLOTS, enemy_thetas,
                        JUMP_HOLD_FRAMES, JUMP_COOLDOWN_FRAMES,
                        G, DNP01_SPIKE_THRESHOLD, SPIKE_AMP, TTMN_PRESS_THRESHOLD)
from compare_controllers import _ensure_ffmpeg_on_path
from load_mushroom_body_cached import load as load_mushroom_body

# ---- hand-set scalars, SPEC_odour.md section 0 ---------------------------
# Run 006's finding: 1/40=0.025 vs HOME_BIAS=1.0 is a 40x gap BY
# CONSTRUCTION -- odour and home bias were never in comparable units, which
# is why odour never won, not a wiring bug. ODOUR_GAIN=16 chosen by
# simulating the real steering circuit end to end (tune_odour.py), not by
# comparing raw currents: it's the smallest gain that makes a close (16px)
# encounter cross HOME_BIAS's settled R_team output in the ACTUAL recurrent
# network. HUNGER_MULT_HUNGRY=3.0 / HUNGER_MULT_SATED=1.0 chosen the same
# way -- tune_odour.py's sweep shows hunger_mult=3.0 is the smallest value
# that still flips at d=40px (the existing MUSHROOM_OFFSET distance,
# unchanged from 006/008), while hunger_mult=1.0 (sated, unboosted) does
# not flip at that same distance -- see tune_odour.py's printed sweep for
# the full table. HOME_BIAS itself is untouched (SPEC section 0: fixing
# this is a scaling fix to two competing DIRECTION signals, not a reason to
# lower it -- that would just make Mario permanently distractible).
ODOUR_GAIN = 16.0
HUNGER_MULT_HUNGRY = 3.0      # RAM 0x0756==0 (small Mario)
HUNGER_MULT_SATED = 1.0       # RAM 0x0756>=1 (big/fiery Mario) -- unboosted, not zeroed

# ---- ORN adaptation, sprint after SPEC_odour.md -------------------------
# A real olfactory receptor neuron's response to a SUSTAINED concentration
# decays over ~1-2 seconds and recovers once the stimulus is gone -- this is
# receptor physiology, not a steering rule, so it is applied entirely
# within the sensory layer (see OlfactoryAdaptation below), and the WTA
# code downstream never needs to know it exists. Applied to the
# ODOUR_GAIN/hunger-scaled signal rather than the bare 1/distance
# concentration: ODOUR_GAIN and hunger already represent the receptor's own
# state-dependent sensitivity (hunger-modulated olfactory gain is itself a
# real, documented phenomenon, not unique to the decision layer), and
# adaptation has to act somewhere in the same units HOME_BIAS lives in to
# mean anything -- dividing a raw concentration of ~0.04 by (1+0.04) barely
# moves it, so a receptor-physiology fix implemented on the wrong side of
# the gain would silently do nothing (found by actually testing it against
# the real circuit in tune_orn_adapt.py before trusting the arithmetic).
# It is also the general anti-stuck mechanism asked for: a place Mario has
# sat near for a while stops smelling, so the still-fresh, never-adapted
# HOME_BIAS takes back over. ALPHA_ADAPT=1/90 gives a ~1.5s time constant at
# 60fps -- this runs once per EMULATOR frame, same cadence as the odour
# reading itself, so 90 FRAMES really is ~1.5s of wall-clock game time.
ALPHA_ADAPT = 1.0 / 90.0

# ---- hand-set scalars, SPEC_steering.md section 5 -----------------------
G_STEER = 1.2                # steering circuit gain -- tune_steering.py
HOME_BIAS = 1.0               # constant "go home" current, R-hemisphere only
CLIMB_STALL_FRAMES = 20       # mario_x unchanged this long while steering=R -> blocked
CLIMB_HOP_SMALL_FRAMES = 10   # small Mario's first-try hop hold
CLIMB_HOP_BIG_FRAMES = 14     # big/fiery Mario's first-try hop hold (taller hitbox)
CLIMB_JUMP_FRAMES = 25        # escalated full jump hold, same magnitude as the escape jump
CLIMB_COOLDOWN_FRAMES = 15
CLIMB_CLEAR_DISTANCE = 24     # px of forward progress that resets the attempt counter

# ---- hand-set scalars, SPEC_terrain.md sections 2-3 ----------------------
# GAP_GAIN/DLMN_RECRUIT_THRESHOLD/LONG_JUMP_HOLD_FRAMES picked by directly
# simulating the real jump + takeoff circuits together at gap widths
# 0/1/2/3/4/6/8 tiles (see the shell history for this sprint, or re-derive
# with tune_terrain.py's calibration pattern): GAP_GAIN=0.6 is the smallest
# value that reliably crosses DNp01's spike threshold even for a 1-tile
# gap (so no pit goes un-jumped); at that gain, one frame's worth of
# substeps gives DLMn end-of-frame means of ~0.28 (width 1), ~1.18 (width
# 2), ~2.14 (width 3), ~2.79 (width 4) -- a clean, monotonic, graded curve.
# DLMN_RECRUIT_THRESHOLD=1.0 sits between the width-1 and width-2 values,
# so a single-tile gap gets a normal hop and anything wider gets the long
# jump.
G_TAKEOFF = 0.8                    # takeoff circuit gain -- tune_terrain.py
GAP_GAIN = 0.6                      # external current per non-ground tile ahead, onto DNp01
DLMN_RECRUIT_THRESHOLD = 1.0        # DLMn mean activation -> recruit the long jump
LONG_JUMP_HOLD_FRAMES = 35           # vs the escape jump's JUMP_HOLD_FRAMES=25
GAP_LOOKAHEAD_TILES = 8

G_SPEED = 1.2                       # speed circuit gain -- tune_terrain.py
WALK_DRIVE = 1.0                    # constant "walk" current onto DNp09
WALK_SUPPRESSION = 1.0              # cancels WALK_DRIVE while jumping/stalled
DNP09_SPEED_THRESHOLD = 0.5          # DNp09 mean activation -> press B

# ---- hand-set scalars, SPEC_habituation.md -------------------------------
# Diagnosed, not assumed: CLIMB_COOLDOWN_FRAMES 15->40 changed nothing
# (byte-identical run); CLIMB_STALL_FRAMES 20->60 revealed the real clock
# governing the stuck loop was the escape/takeoff pathway's own
# LONG_JUMP_HOLD_FRAMES(35)+JUMP_COOLDOWN_FRAMES(40)=75-frame hold-then-
# cooldown cycle, not climb's state machine at all. Real GF habituation to
# repeated stimulation is documented biology -- modeled here as: any reflex
# that fires without HAB_PROGRESS_PX of net x-progress since the last time
# its trigger condition was checked increments its own habituation level;
# HAB_PROGRESS_PX=16 (one tile) is the same "did that actually help" bar
# CLIMB_CLEAR_DISTANCE already uses, just smaller (a single tile is a much
# lower bar than 24px, deliberately -- habituation should engage before a
# reflex has failed enough times to also blow through CLIMB_CLEAR_DISTANCE).
HAB_PROGRESS_PX = 16
HAB_GIVE_UP = 3              # consecutive no-progress firings before a reflex suppresses itself

# MDN (backward walking, 4 bodies, confirmed) has no direct synapse from
# DNp01/GFC1-4 in this connectome (checked) -- same situation DNp09 was in
# (007), so its drive is an external current, same category as
# HOME_BIAS/WALK_DRIVE/GAP_GAIN, not a new kind of thing. Picked by
# simulating the real MDN circuit directly (tune_mdn.py): G_MDN=1.2 keeps
# the real spectral radius (0.7345) comfortably under its ~1.36 linear
# boundary; MDN_DRIVE=2.0 settles to a clean MDN_mean=1.986, non-clipped;
# MDN_THRESHOLD=1.0 sits comfortably between that and the zero-drive
# baseline (which settles to exactly 0 -- no runaway, no spontaneous
# backing up). MDN_BACKUP_FRAMES=30 is a fixed mechanical hold, same
# pattern as every other reflex's hold duration -- backing up is a discrete
# corrective action, not an open-ended state.
G_MDN = 1.2
MDN_DRIVE = 2.0
MDN_THRESHOLD = 1.0
MDN_BACKUP_FRAMES = 30

# ---- hand-set scalars, SPEC_second_escape.md -----------------------------
# The scalar budget was 3 (g, dnp01_spike_threshold, ttmn_press_threshold);
# these are TWO MORE, taking it to 5 -- flagged here and in the README per
# CLAUDE.md invariant 3, on purpose, not buried. DNp02 (confirmed: 2 bodies,
# LC4->DNp02 4209 synapses/125 pairs -- essentially all of LC4; LPLC2->DNp02
# is 5 synapses/4 pairs, noise, the same bar that excluded LPLC1 from the
# original circuit) is a real, direct, ipsilateral second path to TTMn
# (21 syn R, 5 syn L) -- a genuine parallel pathway, not an invented one.
#
# THE NULL RESULT, kept honest rather than tuned away: a first calibration
# pass found DNp02 clearly out-committing DNp01 on a slow synthetic ramp --
# it was a bug. Passing a custom alpha to the whole HybridState.step() call
# also slows TTMn's own decay (TTMn sits in this subgraph too, for the real
# synapse), pinning it near the clip ceiling for dozens of frames after one
# spike and firing on stale state with no enemy present. Fixed by moving
# "longer integration" to a slow EMA on the INPUT current instead, leaving
# HybridState's own step at the normal, fast alpha. With that fixed, and
# after widening DNp02's own N threshold (60 -> 30 -> 15 -> 5, capturing
# 8 -> 77 -> 109 -> 124 of DNp02's 126 real LC4 partners -- tune_dnp02_
# widen.py, restricted throughout to g <= 0.85x each circuit's own real
# spectral-radius boundary, no fragile parameters): DNp02 never produces a
# clean win. N=60/N=5 found no stable combo where it out-commits DNp01 on
# the slow ramp AT ALL; N=30/N=15 found only a marginal 1-4 frame lead, and
# in both of those cases DNp02 ALSO won the fast case by more (4-5 frames)
# -- failing the actual requirement, not just falling short of it. DNp02
# lacks any real LPLC2 (expansion) input, so once it has enough drive to
# fire, angular velocity alone gets it there regardless of ramp speed --
# there is no real gap in its wiring to exploit that separates "slow" from
# "fast" the way the recruitment was hoped to. This is the finding, not a
# tuning failure to fix with a fragile g or an invented third scalar (e.g.
# a postural-preparation delay). N=60 is what ships (widening didn't help,
# so there's no reason to carry the much larger N=5 circuit); G_DNP02=1.2
# and DNP02_ALPHA=0.1 are safe, unremarkable values -- DNp02 remains a
# real, connectome-verified, independently-firing pathway that CAN spike
# under strong enough sustained input, it just essentially never wins the
# race against DNp01 in practice, which the real-game validation (below)
# confirms rather than contradicts.
G_DNP02 = 1.2
DNP02_SPIKE_THRESHOLD = 0.1
DNP02_ALPHA = 0.1

# ---- hand-set scalars, SPEC_mushroom_body.md -----------------------------
# Budget was 5 (g, dnp01_spike_threshold, ttmn_press_threshold, plus the
# DNp02 pair counted in SPEC_second_escape.md); these THREE are new,
# taking it to 8 -- flagged here and in the README per CLAUDE.md invariant
# 3. Real counts verified against this connectome (NOT the "4,554 KC ->
# 104 MBON" figure this project's own "Still open" notes had been
# repeating unchecked since sprint 006): 4,064 KC, 97 MBON, 354 real
# dopaminergic neurons (PAM/PPL/PPM). KC_SPARSITY=0.05 matches the real
# fly's ~5% concurrently-active KC fraction (enforced structurally via
# top-k, not by simulating the real APL feedback-inhibition neuron that
# actually produces it -- a stated simplification, same spirit as skipping
# the EPG ring in SPEC_steering.md). TRACE_DECAY=60 frames is ~1s at 60Hz,
# the real eligibility-trace timescale asked for. LEARNING_RATE=0.001 was
# chosen by direct isolated verification (not the naive first guess of
# 0.01, which gave a single punishment event a 50% one-shot depression on
# eligible synapses -- confirmed by hand-computing dW on a real KC->MBON
# weight before touching the training loop -- too aggressive for a
# 500-episode curve, since eligible synapses would floor toward zero
# within a handful of deaths). At 0.001, one full-magnitude punishment
# (dopamine=CLIP=50) depresses an eligible synapse by 5%; one frame of
# typical reward (a few px of progress) depresses by a fraction of a
# percent -- gradual, not a single-event wipeout.
KC_SPARSITY = 0.05
TRACE_DECAY = 60.0
LEARNING_RATE = 0.001

# ---- hand-set scalars/design notes, SPEC_odour.md sprint 016 (smell) -----
# CONNECTOME CHECK, DONE BEFORE ANY OF THIS WAS BUILT (docs/MECHANISMS.md
# section 1's own warning -- LPLC1 in 007 and DNp02-races-DNp01 in 012 both
# had the literature on their side and the anatomy said no):
#
#   a. Aversive pathway (Or56a->glomerulus DA2, 48 ORN_DA2 bodies; Gr21a/
#      Gr63a->glomerulus V, 55 ORN_V bodies) -> their real PNs (DA2_lPN: 10,
#      V_ilPN+V_l2PN: 4) -> lateral horn (422 LH-prefixed types in this
#      connectome, real and large) -> DNa01/DNa02: NO. Direct PN->DNa01/02
#      synapses: ZERO. Direct LH->DNa01/02 synapses (queried against DNa01/
#      02's FULL real presynaptic population, whole connectome, not just
#      this project's subgraph): 2 LH bodies, 3 synapses total -- against
#      DNa01/02's real total input of 76,248 synapses. Noise, the same bar
#      that excluded LPLC1 (1 synapse/1 pair).
#   b. Attractive food-odour pathway (Or42b->glomerulus DM1, 74 ORN_DM1
#      bodies -> DM1_lPN, 2 bodies) -> DNa01/DNa02: also NO -- zero direct
#      PN synapses. The ONLY real olfactory-adjacent input onto DNa01/DNa02
#      anywhere in the whole connectome is 259 synapses (0.34% of DNa01/02's
#      total real input), and 237 of those 259 are MBON31/MBON32 -- the
#      mushroom body's LEARNED-valence pathway, already built in
#      SPEC_mushroom_body.md/run 014, not an innate ORN/PN/LH pathway. No
#      single ALPN (projection neuron) type contributes more than 1 synapse.
#   c. Either pathway -> DNp09 (the section-5 brake): NO. Zero synapses,
#      full stop -- not one edge anywhere in the whole connectome from ANY
#      olfactory-class neuron (ORN/ALPN/ALLN/ALIN/ALON/Kenyon_Cell/DAN/MBON)
#      onto DNp09, out of DNp09's 15,940 total real synaptic input.
#
# So: a third real "anatomy says no" result (after LPLC1 and the DNp02
# race), and the honest response is the same one this project already used
# for DNp02's MBON bias (SPEC_mushroom_body.md section 5, no real MBON->
# DNp02 synapse either) -- model it as a PLACED external current, flagged
# as such, not a fabricated neuron population dressed up as "the real ORN
# pathway." Concretely, this means goomba_odor/the DNp09 brake/the refusal
# rule's steering push are external currents onto DNa01/DNa02/DNp09 (the
# SAME modelling category HOME_BIAS/GAP_GAIN/WALK_DRIVE/MDN_DRIVE already
# are), exactly like mushroom_odor/question_block_odor already were before
# this sprint -- nothing about HOW odour reaches steering changes; this
# sprint only adds a second (aversive, opposite-sign) channel through that
# same already-established mechanism, plus two more placed terms on DNp09.
#
# Per this sprint's own instruction ("prefer deriving from synapse counts
# over adding a constant"): since there ARE no real synapse counts to
# derive a magnitude from (checked, zero), the alternative taken is to
# REUSE the existing, already-calibrated ODOUR_GAIN/GAP_GAIN scalars for
# every new channel below rather than invent fresh ones. The aversive
# channel reuses ODOUR_GAIN (opposite-sign routing, no hunger term --
# fleeing isn't gated by hunger the way foraging is). The DNp09 brake
# reuses the same odor_l_eff/odor_r_eff the steering WTA already computes
# (so "rising odour inhibits DNp09" costs nothing new -- it's already in
# HOME_BIAS-comparable units). The refusal rule's steering push reuses
# GAP_GAIN (already "current per non-ground tile ahead"). The ONE genuinely
# new number is REFUSAL_GAP_TILES=5 -- and that's a body-scaled mechanical
# threshold (same non-neural category as CLIMB_STALL_FRAMES/
# CLIMB_CLEAR_DISTANCE), not a circuit gain or spike threshold. Derived
# from existing calibration, not guessed: SPEC_terrain.md's GAP_GAIN sweep
# (007) was clean and monotonic through gap widths 0-4 tiles; 008/011 found
# an 8-tile gap makes the long jump fire and fail anyway. 5 is the first
# width past the validated-safe range, i.e. "refuse anything not already
# shown to work." Small/big Mario aren't given separate reach values here
# (no real calibration data differentiates them for the long jump the way
# CLIMB_HOP_SMALL/BIG_FRAMES differentiates the climb hop) -- noted as a
# scoping decision, not an oversight, same pattern as 007's own
# "continuous hold-duration scaling... not done here."
#
# Budget was 8. This sprint adds ZERO new neural-circuit gains/thresholds
# (it reuses ODOUR_GAIN and GAP_GAIN throughout) and ONE new mechanical
# threshold (REFUSAL_GAP_TILES) -- stated both ways rather than picking
# whichever makes the number look better: still 8 if only circuit-dynamics
# scalars count (matching how JUMP_HOLD_FRAMES/CLIMB_*/HAB_* were never
# added to that running total either), 9 if every hand-set number of any
# kind is counted. Flagged here either way, per CLAUDE.md invariant 3.
REFUSAL_GAP_TILES = 5

ADDR_MARIO_SIZE = 0x0756
# ADDR_ENEMY_TYPE/POWERUP_ID now live in run_mario.py (imported below) --
# enemy_thetas() needed them too, to fix the contamination bug SPEC_
# habituation.md's investigation found.

# 8-way action space (was: hold B unconditionally) -- {left,right} x
# {A on/off} x {B on/off}. Index = direction_base + 2*press_a + press_b.
MOVES = [
    ["right"], ["right", "B"], ["right", "A"], ["right", "A", "B"],
    ["left"], ["left", "B"], ["left", "A"], ["left", "A", "B"],
]


def action_index(direction: str, press_a: bool, press_b: bool) -> int:
    base = 0 if direction == "R" else 4
    return base + 2 * int(press_a) + int(press_b)


MAX_FRAMES = 1200
# No default injection frame any more (sprint 011: opt-in only, see main()'s
# `inject_frame` docstring) -- callers that want the odour demo pass their
# own frame number explicitly, e.g. run_008()'s inject_frame=60.
MUSHROOM_OFFSET = -40  # spawn BEHIND Mario so it competes with HOME_BIAS's rightward pull


def make_env(level="1-1"):
    env = gym_super_mario_bros.make(f"SuperMarioBros-{level}-v0")
    return JoypadSpace(env, MOVES)


def mushroom_odor(ram, mario_x):
    """SPEC_steering.md section 2: powerups share the enemy slots,
    Enemy_ID==0x2E. concentration ~ 1/distance, routed by sign of d exactly
    like enemy routing in enemy_thetas -- ahead/right excites the R team,
    behind/left the L team. Raw concentration, NO gain applied here --
    ODOUR_GAIN/hunger are applied once, at the call site, so both odour
    sources share one gain constant (SPEC_odour.md section 0)."""
    odor = {"L": 0.0, "R": 0.0}
    for i in range(N_ENEMY_SLOTS):
        if ram[ADDR_ENEMY_ACTIVE + i] == 0 or ram[ADDR_ENEMY_TYPE + i] != POWERUP_ID:
            continue
        d = int(ram[ADDR_ENEMY_X + i]) - int(mario_x)
        conc = 1.0 / max(abs(d), 1)
        side = "R" if d >= 0 else "L"
        odor[side] += conc
    return odor


def question_block_odor(ram):
    """SPEC_odour.md section 1: a second odour source at every `?` block
    tile_ram finds (0xC0 coin, 0xC1 power-up -- not distinguished, same as
    the mushroom not distinguishing power-up subtype). tile_ram.
    question_blocks_near returns signed TILE-COLUMN offsets relative to
    Mario, not pixels -- convert (*16) before applying the same
    concentration formula and gain as the mushroom, so one gain constant
    covers both. Limitation, stated here per spec, not discovered later:
    this is a horizontal-only signal -- it can pull Mario to stand under a
    block, nothing more. Actually hitting it from below is the existing
    contact-based climb reflex's job, and that reflex's tile_ram.solid_ahead
    check explicitly excludes question tiles from counting as a climb
    target (they float overhead, not underfoot) -- so whether stage two
    ever actually fires is an open question this sprint answers empirically,
    not by assumption. See the writeup for what was actually observed."""
    odor = {"L": 0.0, "R": 0.0}
    for offset_tiles in tile_ram.question_blocks_near(ram):
        d = offset_tiles * 16
        conc = 1.0 / max(abs(d), 1)
        side = "R" if d >= 0 else "L"
        odor[side] += conc
    return odor


def goomba_odor(ram, mario_x):
    """docs/MECHANISMS.md section 1 / SPEC_odour.md sprint 016: every real
    (non-powerup) active enemy slot is an AVERSIVE odour source, same
    concentration ~ 1/distance formula as mushroom_odor/question_block_odor
    -- reuses enemy_thetas' own exclusion of POWERUP_ID slots so a powerup
    never doubles as a threat. Returned by THE SIDE THE THREAT IS ON (R if
    d>=0, matching enemy_thetas' own convention) -- opposite-sign ROUTING
    into DNa01/DNa02 happens at the call site, not here, exactly mirroring
    how mushroom/qblock keep raw concentration separate from gain/routing.
    No gain, no hunger term applied here (this sprint's ODOUR_GAIN is reused
    at the call site; fleeing isn't hunger-gated the way foraging is)."""
    odor = {"L": 0.0, "R": 0.0}
    for i in range(N_ENEMY_SLOTS):
        if ram[ADDR_ENEMY_ACTIVE + i] == 0 or ram[ADDR_ENEMY_TYPE + i] == POWERUP_ID:
            continue
        d = int(ram[ADDR_ENEMY_X + i]) - int(mario_x)
        conc = 1.0 / max(abs(d), 1)
        side = "R" if d >= 0 else "L"
        odor[side] += conc
    return odor


class OlfactoryAdaptation:
    """Sensory-layer ORN adaptation, one instance's worth of receptor state
    per hemisphere (L/R match the same split the odour sources already
    route by). Modeled divisively, not subtractively -- a real firing rate
    (or here, a concentration) can't be driven negative by adaptation, it
    can only be divided down towards zero -- as a slow trace `a` of the RAW
    concentration each side has actually been receiving:

        a(t+1) = (1 - ALPHA_ADAPT) * a(t) + ALPHA_ADAPT * raw(t)
        adapted(t) = raw(t) / (1 + a(t))

    Applied to the ODOUR_GAIN/hunger-scaled signal (see ALPHA_ADAPT's
    comment for why) -- `raw` here is that scaled value, not the bare
    1/distance concentration. A source Mario is stuck next to keeps `raw`
    constant, so `a` climbs toward that same value and `adapted` decays
    toward `raw/(1+raw)` -- e.g. a hungry Mario's scaled odour of 2.0
    (comfortably beating HOME_BIAS=1.0) decays toward 2.0/3.0=0.667, which
    loses to HOME_BIAS -- home wins the WTA back even though the raw
    stimulus never went away. Leaving the source (raw -> 0) lets `a` relax
    back down at the same ALPHA_ADAPT rate, and the next encounter starts
    fresh."""

    def __init__(self):
        self.a = {"L": 0.0, "R": 0.0}

    def apply(self, raw: dict) -> dict:
        out = {}
        for side in ("L", "R"):
            self.a[side] = (1.0 - ALPHA_ADAPT) * self.a[side] + ALPHA_ADAPT * raw[side]
            out[side] = raw[side] / (1.0 + self.a[side])
        return out


class ReflexHabituation:
    """SPEC_habituation.md section 1: any reflex that keeps firing without
    net forward progress since the last time it was checked progressively
    suppresses itself -- real, documented Giant Fiber pathway habituation,
    not a timeout. One instance per reflex (escape, climb), fully
    independent state.

    `last_check_x` updates every time `check()` is called, whether or not
    the reflex actually fires -- so a suppressed reflex keeps listening for
    the progress that would re-sensitise it (e.g. after MDN backs Mario up
    and a later attempt actually clears the obstacle)."""

    def __init__(self, give_up=None, progress_px=None):
        self.last_check_x = None
        self.hab_level = 0
        # read the module globals at construction time, not class-definition
        # time -- a mutable default here would silently ignore any later
        # override of HAB_GIVE_UP/HAB_PROGRESS_PX (found this the hard way
        # while building the baseline-vs-fix comparison for this sprint)
        self.give_up = HAB_GIVE_UP if give_up is None else give_up
        self.progress_px = HAB_PROGRESS_PX if progress_px is None else progress_px

    def check(self, mario_x) -> bool:
        """Call exactly once per frame the reflex's OWN trigger condition
        is true. Returns whether the reflex should actually fire this time
        (False once habituation has reached give_up)."""
        if self.last_check_x is not None:
            progress = mario_x - self.last_check_x
            if progress < self.progress_px:
                self.hab_level = min(self.hab_level + 1, self.give_up)
            else:
                self.hab_level = 0
        self.last_check_x = mario_x
        return self.hab_level < self.give_up

    def reset(self):
        """MDN's fixed-duration backup (SPEC section 2) ends with a clean
        slate for the escape reflex -- backing up is a discrete corrective
        action, not a lingering state."""
        self.last_check_x = None
        self.hab_level = 0


def hunger_multiplier(ram):
    """SPEC_odour.md section 2: RAM 0x0756==0 (small Mario) = hungry = the
    boosted odour gain; >=1 (big/fiery) = sated = the unboosted one."""
    return HUNGER_MULT_HUNGRY if int(ram[ADDR_MARIO_SIZE]) == 0 else HUNGER_MULT_SATED


def find_inactive_slot(ram):
    for i in range(N_ENEMY_SLOTS):
        if ram[ADDR_ENEMY_ACTIVE + i] == 0:
            return i
    return None


def inject_mushroom(ram, mario_x, mario_y, offset=None):
    """SPEC section 2: a synthetic RAM injection for the demo, the same
    move as tune.py driving the jump circuit with a synthetic theta(t)
    ramp before ever touching the emulator. Not a ?-block mechanic, not
    tile RAM -- a direct poke of the same enemy-slot arrays run_mario.py
    already reads for Goombas. `offset` overrides MUSHROOM_OFFSET (still
    the default, -40/behind, for the WTA-competition demo 006/008 use) --
    sprint 016's "eats the mushroom" success criterion needs one actually
    reachable, so its own runner passes a positive (ahead) offset instead."""
    off = MUSHROOM_OFFSET if offset is None else offset
    slot = find_inactive_slot(ram)
    if slot is None:
        print("  (no free enemy slot to inject the mushroom into -- skipped)")
        return False
    x = max(int(mario_x) + off, 0)
    ram[ADDR_ENEMY_ACTIVE + slot] = 1
    ram[ADDR_ENEMY_TYPE + slot] = POWERUP_ID
    ram[ADDR_ENEMY_X + slot] = x & 0xFF
    ram[0x00B6 + slot] = int(mario_y)  # Enemy_Y, same array run_mario.py's spec table lists
    print(f"  injected synthetic mushroom into slot {slot} at x={x} (mario_x={mario_x}, "
          f"i.e. {off:+d}px -- {'ahead, reachable' if off > 0 else 'behind, competes with HOME_BIAS'})")
    return True


def wide_gap_target_col(ram, mario_x, lead_tiles=10) -> int:
    """Pick the FIXED absolute tile-column the synthetic gap will live at,
    once, at the moment of injection -- `lead_tiles` ahead of Mario's
    column at that instant. Callers must hold onto this value and pass it
    back into `poke_wide_gap` every frame; recomputing "N tiles ahead of
    Mario" fresh each frame would make the gap a moving window Mario can
    never actually reach, not a fixed obstacle."""
    col0 = (int(ram[tile_ram.ADDR_MARIO_PAGE]) * 256 + int(mario_x)) // 16
    return col0 + lead_tiles


def poke_wide_gap(ram, target_col: int, width_tiles=REFUSAL_GAP_TILES + 2):
    """SPEC_odour.md sprint 016, item 4's success criterion: 1-1's own real
    pits (007/011: confirmed 2-tile) never exceed REFUSAL_GAP_TILES, so
    there is no REAL wide pit on this level to demonstrate refusal against.
    Same category of controlled test stimulus as inject_mushroom -- not a
    tile-RAM mechanic, a direct poke of the collision-tile buffer
    tile_ram.py already decodes, `width_tiles` chosen comfortably above
    REFUSAL_GAP_TILES so refusal is unambiguous. MUST be called every frame
    at the SAME `target_col` (from `wide_gap_target_col`, called once) --
    empirically confirmed (see the sprint's own connectome-check writeup)
    that a one-shot poke of a not-yet-drawn column can get silently
    reclaimed by the game's own level-streaming routine before Mario
    arrives (007's "doesn't force a redraw" finding was about ALREADY-drawn
    columns; a not-yet-loaded one has a second, different way to get
    overwritten). Re-asserting it every frame makes the synthetic gap
    unconditionally persistent regardless of engine timing."""
    for k in range(width_tiles):
        col = target_col + k
        buf_addr = tile_ram.BUF1_ADDR if (col // 16) % 2 == 0 else tile_ram.BUF2_ADDR
        ram[buf_addr + tile_ram.GROUND_ROW * 16 + (col % 16)] = tile_ram.EMPTY_ID


def make_steering_masks(bodies):
    dna = bodies["type"].isin(["DNa01", "DNa02"]).to_numpy()
    r = dna & (bodies["somaSide"] == "R").to_numpy()
    l = dna & (bodies["somaSide"] == "L").to_numpy()
    return r, l


def main(out_mp4="runs/008_run.mp4", level="1-1", max_frames=MAX_FRAMES,
         force_mario_size=None, force_size_from_frame=None, record_video=True,
         inject_frame=None, frame_skip=1, savestate=None, mb_weights=None,
         mushroom_offset=None, inject_gap_frame=None):
    """`mb_weights`, if given, is the KC->MBON weight sub-matrix (SPEC_
    mushroom_body.md) carried over from a previous call -- the ONE piece
    of state that must persist across training episodes. `None` (default)
    starts from the real, unmodified connectome weights. The (possibly
    now-depressed) matrix is returned in the info dict as `mb_weights` so
    a training loop can pass it straight into the next call."""
    """SPEC_throughput.md: `frame_skip` makes a decision once every
    `frame_skip` real NES frames instead of every frame (the standard RL
    action-repeat pattern -- the emulator still runs at 60Hz, only the
    circuit's decision cadence drops), repeating the same button state for
    the frames in between. No circuit internals change -- SUBSTEPS, alpha,
    thresholds are all untouched, since those ARE the neural model. What
    does change: the MECHANICAL hold-duration constants (JUMP_HOLD_FRAMES
    and its siblings -- already documented, since sprint 006, as "output-
    interface, not part of the neural model") are counted in DECISION TICKS
    here, not real frames, so they're divided by frame_skip (rounded, floor
    1) to keep real-world hold durations approximately unchanged. Verify
    this actually holds before trusting it -- that's an empirical claim,
    not a proof, which is exactly why SPEC_throughput.md's sprint checked
    it on 1-1 before keeping frame_skip>1 anywhere.

    `savestate`, if given (from `make_savestate()`), restores the emulator
    to that exact backed-up state on reset instead of the ROM's power-on
    state -- nes-py's own native `_backup`/`_restore` (a single slot),
    not something built here. Every episode then starts from an identical
    point with no warm-up to replay.

    `inject_frame`: EXPLICIT OPT-IN ONLY. `None` (the default) means no
    synthetic mushroom is ever placed in RAM -- sprint 011 found the
    injected mushroom was a static, permanent, unresolvable RAM object that
    `enemy_thetas()` (before its own fix, run_mario.py) was reading as a
    threat, contaminating three sprints (006/008/009) of "real" runs with
    fake escape-jump activity. `enemy_thetas()` itself is fixed now, but the
    injection stays opt-in regardless -- a clean baseline should never carry
    it by accident, and nothing in the normal run path should require it.
    Pass an explicit frame number only for a deliberate, clearly-labeled
    odour demonstration (as 008's `run_008()` still does, on purpose).

    `force_mario_size`, if given, pokes RAM 0x0756 (small=0, big=1) from
    `force_size_from_frame` onward -- used only by hunger-flip checks that
    need a SATED Mario at the moment of the test. Forcing it from frame 0
    is a confound, not a control: it changes Mario's hitbox against every
    earlier Goomba too, which affects whether he survives to the test at
    all for reasons that have nothing to do with odour (found this the
    hard way -- a force-small run died at frame 108, well before any
    injection, while force-big survived past it). Forcing only from just
    before the test isolates the actual variable of interest. Since
    injection is no longer the default, `force_size_from_frame` must be
    given explicitly if `force_mario_size` is used without `inject_frame`.
    `record_video=False` skips per-frame PNG capture and the brain_panel
    render entirely, for a fast telemetry-only check.

    `mushroom_offset`, sprint 016: overrides MUSHROOM_OFFSET for
    `inject_mushroom` -- pass a positive value to place it ahead of Mario
    (reachable, for the "eats it" demo) instead of the original behind-Mario
    competition test. `inject_gap_frame`, sprint 016, same opt-in-only
    convention as `inject_frame`: `None` means no synthetic wide gap is ever
    poked into the tile buffer; an explicit frame number picks a fixed
    target column (`wide_gap_target_col`, `lead_tiles` ahead of wherever
    Mario is at that frame) and re-pokes it every frame from then on
    (`poke_wide_gap`) to demonstrate the refusal rule, since 1-1 has no
    real pit wide enough to need it."""
    if force_mario_size is not None and force_size_from_frame is None:
        assert inject_frame is not None, (
            "force_mario_size needs an explicit force_size_from_frame when "
            "inject_frame is None -- there's no longer an injection frame "
            "to silently default to.")
        force_size_from_frame = inject_frame

    # Mechanical hold-duration constants, rescaled into decision ticks --
    # see frame_skip's docstring. A no-op at frame_skip=1 (every constant
    # divides by 1).
    jump_hold_frames = max(1, round(JUMP_HOLD_FRAMES / frame_skip))
    jump_cooldown_frames = max(1, round(JUMP_COOLDOWN_FRAMES / frame_skip))
    long_jump_hold_frames = max(1, round(LONG_JUMP_HOLD_FRAMES / frame_skip))
    climb_hop_small_frames = max(1, round(CLIMB_HOP_SMALL_FRAMES / frame_skip))
    climb_hop_big_frames = max(1, round(CLIMB_HOP_BIG_FRAMES / frame_skip))
    climb_jump_frames = max(1, round(CLIMB_JUMP_FRAMES / frame_skip))
    climb_cooldown_frames = max(1, round(CLIMB_COOLDOWN_FRAMES / frame_skip))
    climb_stall_frames = max(1, round(CLIMB_STALL_FRAMES / frame_skip))
    mdn_backup_frames = max(1, round(MDN_BACKUP_FRAMES / frame_skip))

    print("Loading the jump circuit (unchanged, cached)...")
    j_bodies, _, _, _, W_j, _, _ = _memo_load("jump", load_jump, N=60)
    Kj = W_j.shape[0]
    jm = lambda t, s: ((j_bodies["type"] == t) & (j_bodies["somaSide"] == s)).to_numpy()
    j_msk = {
        "LC4_L": jm("LC4", "L"), "LC4_R": jm("LC4", "R"),
        "LPLC2_L": jm("LPLC2", "L"), "LPLC2_R": jm("LPLC2", "R"),
        "LC4_all": (j_bodies["type"] == "LC4").to_numpy(),
        "LPLC2_all": (j_bodies["type"] == "LPLC2").to_numpy(),
        "TTMn_L": jm("TTMn", "L"), "TTMn_R": jm("TTMn", "R"),
        "DNp01_L": jm("DNp01", "L"), "DNp01_R": jm("DNp01", "R"),
    }
    dnp01_idx = np.concatenate([np.where(j_msk["DNp01_L"])[0], np.where(j_msk["DNp01_R"])[0]])
    jump_dnp01_mask = j_msk["DNp01_L"] | j_msk["DNp01_R"]
    jump_state = dynamics.HybridState(Kj, dnp01_idx, spike_threshold=DNP01_SPIKE_THRESHOLD,
                                       spike_amp=SPIKE_AMP)

    print("Loading the steering circuit (DNa01/DNa02, N=60, cached)...")
    s_bodies, _, _, _, W_s, _, _ = _memo_load("steering", load_steering)
    Ks = W_s.shape[0]
    r_mask, l_mask = make_steering_masks(s_bodies)
    dna01_all = (s_bodies["type"] == "DNa01").to_numpy()
    dna02_all = (s_bodies["type"] == "DNa02").to_numpy()
    h_steer = np.zeros(Ks)
    orn_adapt = OlfactoryAdaptation()
    orn_adapt_avers = OlfactoryAdaptation()  # separate receptor identity/glomerulus, sprint 016

    print("Loading the takeoff circuit (DNp01 -> GFC1-4 -> DLMn, cached)...")
    t_bodies, _, _, _, W_t, _, _ = _memo_load("takeoff", load_takeoff)
    Kt = W_t.shape[0]
    takeoff_dnp01_mask = (t_bodies["type"] == "DNp01").to_numpy()
    dlmn_mask = t_bodies["type"].isin(["DLMn c-f", "DLMn a, b"]).to_numpy()
    h_takeoff = np.zeros(Kt)

    print("Loading the speed circuit (DNp09, N=60, cached)...")
    p_bodies, _, _, _, W_p, _, _ = _memo_load("speed", load_speed)
    Kp = W_p.shape[0]
    dnp09_mask = (p_bodies["type"] == "DNp09").to_numpy()
    h_speed = np.zeros(Kp)

    print("Loading the MDN circuit (backward walking, N=60, cached)...")
    m_bodies, _, _, _, W_m, _, _ = _memo_load("mdn", load_mdn)
    Km = W_m.shape[0]
    mdn_mask = (m_bodies["type"] == "MDN").to_numpy()
    h_mdn = np.zeros(Km)
    hab_escape = ReflexHabituation()
    hab_climb = ReflexHabituation()
    mdn_backup_hold = 0

    print("Loading the DNp02 circuit (second escape pathway, N=60, cached)...")
    dp_bodies, _, _, _, W_dp, _, _ = _memo_load("dnp02", load_dnp02)
    Kdp = W_dp.shape[0]
    dnp02_lc4_r = ((dp_bodies["type"] == "LC4") & (dp_bodies["somaSide"] == "R")).to_numpy()
    dnp02_lc4_l = ((dp_bodies["type"] == "LC4") & (dp_bodies["somaSide"] == "L")).to_numpy()
    dnp02_l_mask = ((dp_bodies["type"] == "DNp02") & (dp_bodies["somaSide"] == "L")).to_numpy()
    dnp02_r_mask = ((dp_bodies["type"] == "DNp02") & (dp_bodies["somaSide"] == "R")).to_numpy()
    dnp02_idx = np.concatenate([np.where(dnp02_l_mask)[0], np.where(dnp02_r_mask)[0]])
    dnp02_pos = {"L": 0, "R": 1}
    dnp02_ttmn_l = ((dp_bodies["type"] == "TTMn") & (dp_bodies["somaSide"] == "L")).to_numpy()
    dnp02_ttmn_r = ((dp_bodies["type"] == "TTMn") & (dp_bodies["somaSide"] == "R")).to_numpy()
    dnp02_state = dynamics.HybridState(Kdp, dnp02_idx, spike_threshold=DNP02_SPIKE_THRESHOLD,
                                        spike_amp=SPIKE_AMP)

    print("Loading the mushroom body circuit (KC/MBON/DAN, cached)...")
    mb_bodies, _, _, _, W_mb_full, _, _ = _memo_load("mushroom_body", load_mushroom_body)
    mb_kc_mask = (mb_bodies["role"] == "KC").to_numpy()
    mb_mbon_mask = (mb_bodies["role"] == "MBON").to_numpy()
    mb_is_pam = mb_bodies["type"].astype(str).str.startswith("PAM").to_numpy()
    mb_dan_mask = (mb_bodies["role"] == "DAN").to_numpy()
    mb_pam_mask = mb_dan_mask & mb_is_pam
    mb_punish_mask = mb_dan_mask & ~mb_is_pam
    mb_kc_idx = np.where(mb_kc_mask)[0]
    mb_mbon_idx = np.where(mb_mbon_mask)[0]
    mb_pam_idx = np.where(mb_pam_mask)[0]
    mb_punish_idx = np.where(mb_punish_mask)[0]
    n_kc, n_mbon = len(mb_kc_idx), len(mb_mbon_idx)
    # W's convention (circuit.build_weight_matrix) is W[post, pre] -- rows
    # are postsynaptic. This IS the matrix the plasticity rule modifies;
    # `mb_weights`, if passed in, is this same sub-block carried over from
    # a previous episode (the one piece of state that must persist across
    # training -- everything else here resets fresh each call, as normal).
    W_kc_mbon = (mb_weights if mb_weights is not None
                 else W_mb_full[np.ix_(mb_mbon_idx, mb_kc_idx)].copy())
    # Real, static (not modified by plasticity) -- DAN->MBON is the actual
    # tripartite-synapse site in real anatomy, so reward/punishment reach
    # each MBON in proportion to its own real dopaminergic input, with no
    # extra hand-set scaling.
    mb_pam_reach = W_mb_full[np.ix_(mb_mbon_idx, mb_pam_idx)].sum(axis=1)
    mb_punish_reach = W_mb_full[np.ix_(mb_mbon_idx, mb_punish_idx)].sum(axis=1)
    # Fixed, seeded (not a hand-set scalar -- same precedent as circuit.py's
    # shuffle_edges seed elsewhere in this project), sparse random
    # projection from the sensory-state vector onto KCs -- SPEC section 1:
    # the randomness is the biologically correct part, nothing in this
    # project's sensory abstractions (theta, odour, gap width, DNp09,
    # hunger) has a real PN identity to look a synapse weight up for.
    # Order: theta_L, theta_R, odor_l_eff, odor_r_eff, gap_w, dnp09_val, hunger
    _mb_rng = np.random.default_rng(0)
    N_MB_SENSORY = 7
    mb_proj = np.zeros((n_kc, N_MB_SENSORY))
    for _i in range(n_kc):
        _feats = _mb_rng.choice(N_MB_SENSORY, size=3, replace=False)
        mb_proj[_i, _feats] = 1.0
    mb_elig = np.zeros(n_kc)
    mb_prev_dnp09 = 0.0  # one-frame delay: DNp09/speed runs after steering
    mb_bias_dnp02 = 0.0  # ditto for DNp02, which steps before this block
    h_mbon = np.zeros(n_mbon)
    prev_mario_x_abs = None
    max_x_abs = None
    # Real MBON->DNa02 (250 syn, checked against the connectome directly)
    # and real MBON->DNp02 fraction (checked: zero -- no real synapse, so
    # DNp02's modulation is a placed bias, SPEC section 5, at the SAME
    # real-data-derived magnitude as DNa02's genuine one, to avoid
    # inventing a fourth scalar just to size it).
    MBON_DNA02_FRAC = {"L": 0.00379, "R": 0.00632}  # real, per body, averaged by side

    owns_env = savestate is None or "env" not in savestate
    if owns_env:
        env = make_env(level)
    else:
        env = savestate["env"]
    obs = env.reset()  # nes-py's own reset auto-restores from _backup() if one exists
    ram = env.unwrapped.ram
    if savestate is not None and "warmup_frames" in savestate and not env.unwrapped._has_backup:
        warmup_action = action_index("R", False, True)  # hold right+B, plain running
        for _ in range(savestate["warmup_frames"]):
            obs, _, d, _ = env.step(warmup_action)
            if d:
                obs = env.reset()
        env.unwrapped._backup()
        obs = env.reset()  # land on the just-made backup, not the tail of warmup

    prev_theta = {"L": 0.0, "R": 0.0}
    d_history = {"L": [], "R": []}  # rolling d_px, for the frames-to-contact estimate at commit
    dnp02_ema = {"L": 0.0, "R": 0.0}  # DNp02's own "longer integration" -- see its call site
    jump_hold = jump_cooldown = 0
    climb_hold = climb_cooldown = 0
    climb_attempts = 0
    last_reset_x = int(ram[ADDR_MARIO_X])
    stall_count = 0
    direction = "R"
    injected = False
    gap_target_col = None       # sprint 016: fixed once, on inject_gap_frame
    prev_qblock_cols = set()    # sprint 016: for detecting a real "?"-block hit
    prev_mario_size = int(ram[ADDR_MARIO_SIZE])  # sprint 016: for detecting "ate the mushroom"
    n_escape_jumps = n_climb_hops = n_climb_jumps = n_conflicts = 0
    n_long_jumps = 0
    n_dnp01_fired = n_dnp02_fired = 0
    n_qblock_hits = n_odor_avoids = n_refusals = 0

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        log = {k: [] for k in ("frame", "mario_x", "theta", "lc4", "lplc2", "mem", "spike",
                                "ttmn", "dna01", "dna02", "direction", "climb", "conflict",
                                "dnp09", "dlmn", "gap", "long_jump", "press_b",
                                "odor_l", "odor_r", "hungry",
                                "raw_odor_l", "raw_odor_r", "orn_a_l", "orn_a_r",
                                "hab_escape", "hab_climb", "mdn", "mdn_backing_up",
                                "ttmn_dnp02", "spike_dnp02", "pathway_fired",
                                "avers_l", "avers_r", "avoid_odor", "refusing",
                                "qblock_hit", "mario_size")}

        frame = 0
        done = False
        while frame < max_frames and not done:
            # ---- frame skip: repeat the last decision, no new circuit work -
            # Standard RL action-repeat. `action` always exists here once
            # frame>0, since frame 0 (0 % anything == 0) always takes the
            # full decision path below at least once. A telemetry row is
            # still appended (repeating the last decision's values, frame/
            # mario_x updated) so recorded video stays 1:1 with brain_panel.
            if frame_skip > 1 and frame % frame_skip != 0:
                mario_x = int(ram[ADDR_MARIO_X])
                for key in log:
                    if key == "frame":
                        log[key].append(frame)
                    elif key == "mario_x":
                        log[key].append(mario_x)
                    else:
                        log[key].append(log[key][-1])
                if record_video:
                    Image.fromarray(obs).save(tmp / f"{frame:05d}.png")
                obs, reward, done, info = env.step(action)
                frame += 1
                continue

            if force_mario_size is not None and frame >= force_size_from_frame:
                ram[ADDR_MARIO_SIZE] = force_mario_size

            mario_x = int(ram[ADDR_MARIO_X])
            mario_y = int(ram[0x00B5])

            if inject_frame is not None and not injected and frame >= inject_frame:
                inject_mushroom(ram, mario_x, mario_y, offset=mushroom_offset)
                injected = True

            if inject_gap_frame is not None and frame >= inject_gap_frame:
                if gap_target_col is None:
                    gap_target_col = wide_gap_target_col(ram, mario_x)
                    print(f"  frame {frame}: sprint-016 synthetic wide gap poked at "
                          f"abs_col={gap_target_col} (mario_x={mario_x})")
                poke_wide_gap(ram, gap_target_col)

            # ---- terrain sensing: SPEC_terrain.md section 1 --------------
            gap_w = tile_ram.gap_width(ram, GAP_LOOKAHEAD_TILES)
            wall_ahead = tile_ram.solid_ahead(ram)
            refusing = gap_w > REFUSAL_GAP_TILES
            if refusing:
                n_refusals += 1

            # sprint 016: a real "?" block hit -- a column that carried a
            # QUESTION_IDS tile last frame and no longer does this frame,
            # detected via tile_ram directly rather than guessed from score
            # RAM (tile_ram.question_blocks_near already excludes USED_BLOCK_
            # ID by construction, so a disappearance IS the hit).
            cur_qblock_cols = {
                (int(ram[tile_ram.ADDR_MARIO_PAGE]) * 256 + mario_x) // 16 + off
                for off in tile_ram.question_blocks_near(ram)
            }
            qblock_hit = bool(prev_qblock_cols - cur_qblock_cols)
            if qblock_hit:
                n_qblock_hits += 1
                print(f"  frame {frame}: '?' block hit (column(s) "
                      f"{sorted(prev_qblock_cols - cur_qblock_cols)} emptied)")
            prev_qblock_cols = cur_qblock_cols

            mario_size = int(ram[ADDR_MARIO_SIZE])
            if mario_size > prev_mario_size:
                print(f"  frame {frame}: Mario grew (size {prev_mario_size} -> "
                      f"{mario_size}) -- ate the mushroom")
            prev_mario_size = mario_size

            # ---- escape jump + pit-triggered graded takeoff --------------
            # SPEC_jump.md's circuit itself is untouched; the only addition
            # is one extra additive term on DNp01's own per-frame input, a
            # pit being a threat modality no looming detector can see
            # (section 2) -- both hemispheres get it symmetrically, a gap
            # dead ahead isn't lateralised.
            theta, dtheta, d_out = enemy_thetas(ram, mario_x, prev_theta)
            prev_theta = theta
            for _side in ("L", "R"):
                if d_out[_side] is not None:
                    d_history[_side].append(d_out[_side])
                    if len(d_history[_side]) > 10:
                        d_history[_side].pop(0)
                else:
                    d_history[_side].clear()
            Ij = np.zeros(Kj)
            Ij[j_msk["LC4_L"]] = abs(dtheta["L"]); Ij[j_msk["LPLC2_L"]] = theta["L"]
            Ij[j_msk["LC4_R"]] = abs(dtheta["R"]); Ij[j_msk["LPLC2_R"]] = theta["R"]
            # docs/MECHANISMS.md #6, sprint 016: "do not attempt" is part of
            # the refusal rule itself, not just the steering push below --
            # a gap past the validated-safe reach stops feeding DNp01 via
            # this term, so the long jump this current alone would have
            # recruited never gets attempted. LC4/LPLC2 (real enemy looming)
            # are untouched -- a genuine Goomba threat next to a refused
            # pit is a different modality and must still be escapable.
            if not refusing:
                Ij[jump_dnp01_mask] += GAP_GAIN * gap_w

            # Takeoff circuit is stepped in lockstep with the jump circuit,
            # substep by substep -- it reads DNp01's real spiking output
            # (0 or spike_amp, never averaged away) as its own external
            # drive each substep, so a gap-driven burst of closely-spaced
            # DNp01 spikes integrates into a correspondingly higher GFC/DLMn
            # level. The jump circuit's own code/state is untouched; this is
            # a one-directional read.
            for _ in range(dynamics.SUBSTEPS):
                hj = jump_state.step(W_j, G, Ij)
                It = np.zeros(Kt)
                It[takeoff_dnp01_mask] = hj[jump_dnp01_mask]
                h_takeoff = dynamics.step(h_takeoff, W_t, G_TAKEOFF, It)
            h_takeoff[h_takeoff < 1e-30] = 0.0  # flush denormals, CLAUDE.md perf note
            ttmn_val = max(hj[j_msk["TTMn_L"]].mean(), hj[j_msk["TTMn_R"]].mean())
            dlmn_val = h_takeoff[dlmn_mask].mean()

            # ---- DNp02: the second escape pathway, SPEC_second_escape.md --
            # Raw dtheta, not the jump circuit's own (already fast-dynamics-
            # filtered) LC4 output -- tune_dnp02.py found reading the real
            # jump circuit's LC4 activation erases the very slow/fast
            # distinction this pathway exists to make. LPLC2 is not fed in
            # at all: its real input to DNp02 is noise-level (5 synapses/4
            # pairs, whole connectome), the same bar SPEC_jump.md used to
            # exclude LPLC1 from the original circuit.
            #
            # "Longer integration" lives in a slow EMA on the INPUT current,
            # not in HybridState's own alpha -- HybridState applies one
            # shared alpha to its WHOLE state vector, including TTMn's own
            # decay (TTMn is part of this subgraph too, for the real
            # DNp02->TTMn weight). Passing a small alpha there was found,
            # by actually watching it happen, to also slow TTMn's decay to
            # a crawl, leaving it pinned near the clip ceiling for dozens of
            # frames after a single spike and firing on stale state with no
            # enemy present. Smoothing the input instead keeps TTMn's own
            # dynamics at the normal (fast) rate; only DNp02's sensory
            # integration is slow.
            dnp02_ema["L"] = (1 - DNP02_ALPHA) * dnp02_ema["L"] + DNP02_ALPHA * abs(dtheta["L"])
            dnp02_ema["R"] = (1 - DNP02_ALPHA) * dnp02_ema["R"] + DNP02_ALPHA * abs(dtheta["R"])
            Idp = np.zeros(Kdp)
            Idp[dnp02_lc4_l] = dnp02_ema["L"]; Idp[dnp02_lc4_r] = dnp02_ema["R"]
            # Placed bias, one-frame delayed (mb_bias_dnp02 is computed
            # later in THIS SAME loop, after odour -- see the mushroom-body
            # block) -- no real MBON->DNp02 synapse exists (checked), SPEC
            # section 5.
            Idp[dnp02_idx] += mb_bias_dnp02
            for _ in range(dynamics.SUBSTEPS):
                h_dnp02 = dnp02_state.step(W_dp, G_DNP02, Idp)
            h_dnp02[h_dnp02 < 1e-30] = 0.0  # flush denormals, CLAUDE.md perf note
            ttmn_val_dnp02 = max(h_dnp02[dnp02_ttmn_l].mean(), h_dnp02[dnp02_ttmn_r].mean())

            # ---- steering: home bias + odour (mushroom + ?-blocks), WTA --
            # SPEC_odour.md section 0: both odour sources are raw
            # concentrations (1/px) until here -- ODOUR_GAIN and the hunger
            # multiplier are applied ONCE, together, so a close encounter is
            # actually comparable to HOME_BIAS in the real network's own
            # units (tune_odour.py), not 40x too small by construction.
            mush = mushroom_odor(ram, mario_x)
            qblock = question_block_odor(ram)
            hunger = hunger_multiplier(ram)
            odor_gain_eff = ODOUR_GAIN * hunger
            # pre-adaptation, but already gain/hunger-scaled -- see ALPHA_ADAPT's
            # comment for why adaptation sits on this side of the gain, not the
            # bare 1/distance concentration
            prod_odor = {"R": odor_gain_eff * (mush["R"] + qblock["R"]),
                         "L": odor_gain_eff * (mush["L"] + qblock["L"])}
            adapted_odor = orn_adapt.apply(prod_odor)
            odor_r_eff = adapted_odor["R"]
            odor_l_eff = adapted_odor["L"]

            # ---- aversive odour: every real enemy, docs/MECHANISMS.md #1 --
            # Reuses ODOUR_GAIN (no hunger term -- see the sprint-016 scalar
            # block above for why) and its own OlfactoryAdaptation instance
            # (a distinct receptor identity/glomerulus, same ALPHA_ADAPT).
            # goomba_odor returns concentration BY THE SIDE THE THREAT IS ON
            # -- routing here is the OPPOSITE of mush/qblock's own-side
            # routing: a threat on R pushes the L team up (turn away), a
            # threat on L pushes the R team up. DNp01/looming is untouched
            # (docs/MECHANISMS.md #1: "leave the DNp01 pathway wired") --
            # this is a second, earlier-acting avoidance channel competing
            # for the SAME steering decision, not a replacement in code.
            avers_raw = goomba_odor(ram, mario_x)
            avers_scaled = {"R": ODOUR_GAIN * avers_raw["R"], "L": ODOUR_GAIN * avers_raw["L"]}
            avers_adapted = orn_adapt_avers.apply(avers_scaled)
            avers_r_eff = avers_adapted["R"]  # threat on the RIGHT -> excites L team, see below
            avers_l_eff = avers_adapted["L"]  # threat on the LEFT  -> excites R team

            # ---- mushroom body: KC coding, MBON readout, dopamine, --------
            # ---- depression-only plasticity, SPEC_mushroom_body.md --------
            # mb_prev_dnp09 is last FRAME's dnp09_val (DNp09/speed steps
            # later in this same loop, after steering) -- a one-frame
            # delayed feedback, a deliberate, stated simplification rather
            # than reordering circuits that already work.
            mb_sensory = np.array([theta["L"], theta["R"], odor_l_eff, odor_r_eff,
                                    float(gap_w), mb_prev_dnp09,
                                    1.0 if hunger == HUNGER_MULT_HUNGRY else 0.0])
            mb_raw = mb_proj @ mb_sensory
            k_active = max(1, int(round(KC_SPARSITY * n_kc)))
            mb_top = np.argpartition(mb_raw, -k_active)[-k_active:]
            kc_active = np.zeros(n_kc)
            kc_active[mb_top] = 1.0

            mbon_drive = W_kc_mbon @ kc_active
            h_mbon = (1.0 - dynamics.ALPHA) * h_mbon + dynamics.ALPHA * dynamics.phi(mbon_drive)
            h_mbon[h_mbon < 1e-30] = 0.0  # flush denormals, CLAUDE.md perf note

            mario_x_abs = int(ram[ADDR_MARIO_PAGE]) * 256 + mario_x
            reward = 0.0 if prev_mario_x_abs is None else max(0, mario_x_abs - prev_mario_x_abs)
            prev_mario_x_abs = mario_x_abs
            max_x_abs = mario_x_abs if max_x_abs is None else max(max_x_abs, mario_x_abs)
            # punishment (death) is applied once, after env.step() reports
            # done, at the END of the frame below -- see that block.

            mb_elig = (1.0 - 1.0 / TRACE_DECAY) * mb_elig + (1.0 / TRACE_DECAY) * kc_active
            if reward > 0:
                dopamine_reward = reward * mb_pam_reach  # per-MBON, real-weighted
                # Depression only, both learning directions (SPEC section 4)
                # -- multiplicative, so it's automatically zero wherever
                # W_kc_mbon is already zero (no real synapse there).
                W_kc_mbon -= (LEARNING_RATE * dopamine_reward[:, None] * mb_elig[None, :]
                              * W_kc_mbon)

            mbon_agg = float(h_mbon.mean())
            mb_bias_r = MBON_DNA02_FRAC["R"] * mbon_agg
            mb_bias_l = MBON_DNA02_FRAC["L"] * mbon_agg
            mb_bias_dnp02 = MBON_DNA02_FRAC["R"] * mbon_agg  # placed bias, no real synapse -- see loading block

            Is = np.zeros(Ks)
            # avers_r_eff (threat ahead/right) excites the L team -- flee;
            # avers_l_eff (threat behind/left) excites the R team -- same
            # opposite-side routing on both hemispheres, mirrored.
            Is[r_mask] = HOME_BIAS + odor_r_eff + avers_l_eff
            Is[l_mask] = odor_l_eff + avers_r_eff
            # Refusal rule, docs/MECHANISMS.md #6 (sprint 016): a gap wider
            # than the validated-safe reach pushes the L team too, reusing
            # GAP_GAIN (already "current per non-ground tile ahead") rather
            # than a new scalar -- see REFUSAL_GAP_TILES's comment. Graded,
            # not a hard override, so it competes through the same WTA
            # instead of ignoring HOME_BIAS/odour outright.
            if refusing:
                Is[l_mask] += GAP_GAIN * gap_w
            # Real MBON->DNa02 synapse (not DNa01 -- checked directly) gets
            # the learned bias; DNa01 is untouched by the mushroom body.
            Is[dna02_all & r_mask] += mb_bias_r
            Is[dna02_all & l_mask] += mb_bias_l
            for _ in range(dynamics.SUBSTEPS):
                h_steer = dynamics.step(h_steer, W_s, G_STEER, Is)
            h_steer[h_steer < 1e-30] = 0.0  # flush denormals, CLAUDE.md perf note

            r_team = h_steer[r_mask].mean()
            l_team = h_steer[l_mask].mean()
            if r_team > l_team:
                direction = "R"
            elif l_team > r_team:
                direction = "L"
            # tie: keep previous direction (hysteresis, mechanical debounce)

            # sprint 016: "log which one initiates each avoidance" -- was
            # THIS frame's WTA choice of L attributable to the aversive
            # channel specifically (as opposed to attractive odour pulling
            # left, or the refusal push)? A pragmatic attribution, not a
            # counterfactual re-simulation -- same bar `pathway_fired`
            # already uses for DNp01-vs-DNp02 (a readiness check, not a
            # shadow network). Captured BEFORE MDN's hard override below,
            # so it reflects the steering WTA's own decision.
            avoid_odor = bool(direction == "L" and avers_r_eff > 1e-6
                               and avers_r_eff >= odor_l_eff and not refusing)
            if avoid_odor and not getattr(main, "_prev_avoid_odor", False):
                n_odor_avoids += 1
                print(f"  frame {frame}: aversive odour steers AWAY (L) -- "
                      f"avers_r_eff={avers_r_eff:.3f} theta_R={theta['R']:.3f} "
                      f"d_px={d_out['R']}")
            main._prev_avoid_odor = avoid_odor

            # ---- contact-based climbing ----------------------------------
            climb_trigger = False
            if mario_x - last_reset_x >= CLIMB_CLEAR_DISTANCE:
                climb_attempts = 0
                last_reset_x = mario_x

            # stall tracking: only while not already mid any jump
            if jump_hold == 0 and climb_hold == 0:
                if getattr(main, "_last_x", None) == mario_x:
                    stall_count += 1
                else:
                    stall_count = 0
                main._last_x = mario_x
            else:
                stall_count = 0
                main._last_x = mario_x

            # Gate on tile_ram.solid_ahead: SPEC_terrain.md section 1's
            # whole point is finally telling a wall apart from a pit. A
            # stall in front of a pit is DNp01/DLMn's job (above), not
            # this reflex's -- climbing only fires at a real obstacle.
            if (stall_count >= climb_stall_frames and direction == "R" and wall_ahead
                    and jump_hold == 0 and climb_hold == 0 and climb_cooldown == 0):
                if hab_climb.check(mario_x):
                    mario_size = int(ram[ADDR_MARIO_SIZE])
                    if climb_attempts == 0:
                        hold = climb_hop_small_frames if mario_size == 0 else climb_hop_big_frames
                        climb_attempts = 1
                        n_climb_hops += 1
                    else:
                        hold = climb_jump_frames
                        climb_attempts = 2
                        n_climb_jumps += 1
                    climb_hold = hold
                    climb_trigger = True
                    print(f"  frame {frame}: blocked-forward -> climb "
                          f"{'hop' if hold != climb_jump_frames else 'jump'} "
                          f"(hold={hold}, mario_size={mario_size})")
                else:
                    print(f"  frame {frame}: climb HABITUATED "
                          f"(level={hab_climb.hab_level}) -- suppressed")
                stall_count = 0

            # ---- escape-jump trigger: DNp01 vs DNp02, COMPETE not sum -----
            # SPEC_second_escape.md: each pathway's own TTMn readout crosses
            # its (shared) press threshold independently -- never summed
            # into one combined value, which would hide which pathway was
            # actually responsible. Firing is gated on ttmn_val alone,
            # EXACTLY the original, already-validated DNp01 condition --
            # NOT also requiring just_spiked on the same exact frame. Found
            # the hard way why that distinction matters: TTMn is a leaky
            # accumulator that can still be over threshold several frames
            # after the spike that pushed it there, and requiring
            # coincident spiking delayed a real trigger from frame 105 to
            # 108 in testing, by which point DLMn had ALSO climbed past its
            # own threshold -- turning an ordinary short hop into an
            # unrelated long jump and changing Mario's whole trajectory
            # from there. just_spiked is used only for ATTRIBUTION (which
            # pathway is logged as responsible), never for gating whether
            # the press happens. Ties go to DNp01, the fast pathway,
            # matching real GF latency priority. The LOSING pathway's state
            # is reset so it doesn't also fire on a trailing frame for the
            # same, already-handled threat.
            escape_trigger = False
            long_jump = False
            pathway_fired = None
            if jump_cooldown > 0:
                jump_cooldown -= 1
            elif jump_hold == 0:
                dnp01_ready = ttmn_val >= TTMN_PRESS_THRESHOLD
                dnp02_ready = ttmn_val_dnp02 >= TTMN_PRESS_THRESHOLD
                if dnp01_ready or dnp02_ready:
                    if dnp01_ready and dnp02_ready:
                        pathway_fired = "DNp01" if jump_state.just_spiked.any() else (
                            "DNp02" if dnp02_state.just_spiked.any() else "DNp01")
                    else:
                        pathway_fired = "DNp01" if dnp01_ready else "DNp02"
                    if hab_escape.check(mario_x):
                        long_jump = dlmn_val >= DLMN_RECRUIT_THRESHOLD
                        jump_hold = long_jump_hold_frames if long_jump else jump_hold_frames
                        escape_trigger = True
                        n_escape_jumps += 1
                        if pathway_fired == "DNp01":
                            n_dnp01_fired += 1
                            dnp02_state.h[:] = 0.0; dnp02_state.mem[:] = 0.0  # loser resets
                        else:
                            n_dnp02_fired += 1
                            jump_state.h[:] = 0.0; jump_state.mem[:] = 0.0  # loser resets
                        side = "R" if theta["R"] >= theta["L"] else "L"
                        hist = d_history[side]
                        closing_px_per_frame = ((hist[0] - hist[-1]) / (len(hist) - 1)
                                                 if len(hist) >= 2 else None)
                        frames_to_contact = (abs(d_out[side]) / closing_px_per_frame
                                              if (closing_px_per_frame and closing_px_per_frame > 0
                                                  and d_out[side] is not None) else None)
                        ftc_str = f"{frames_to_contact:.1f}" if frames_to_contact is not None else "?"
                        print(f"  frame {frame}: {pathway_fired} commits -- "
                              f"theta={theta[side]:.3f} d_px={d_out[side]} "
                              f"est_frames_to_contact={ftc_str}")
                        if long_jump:
                            n_long_jumps += 1
                            print(f"  frame {frame}: gap_width={gap_w} DLMn={dlmn_val:.2f} "
                                  f">= {DLMN_RECRUIT_THRESHOLD} -> LONG JUMP (hold={jump_hold})")
                    else:
                        print(f"  frame {frame}: escape HABITUATED "
                              f"(level={hab_escape.hab_level}) -- suppressed")

            conflict = escape_trigger and (climb_trigger or climb_hold > 0)
            if climb_trigger and (jump_hold > 0 or escape_trigger):
                conflict = True
            if conflict:
                n_conflicts += 1
                print(f"  frame {frame}: CONFLICT -- escape and climb both want A")

            # ---- MDN: the escape-failed fallback, SPEC_habituation.md sec 2 -
            # No real synapse from DNp01/GFC1-4 onto MDN in this connectome
            # (checked) -- MDN_DRIVE is an external current, same category
            # as HOME_BIAS/WALK_DRIVE/GAP_GAIN, only active once the escape
            # reflex has fully given up. A fixed-duration override (not an
            # open-ended state) once MDN's own real recurrent circuit
            # actually crosses threshold -- backing up is a discrete
            # corrective move, matching every other reflex's hold-duration
            # pattern here.
            if mdn_backup_hold == 0:
                Im = np.zeros(Km)
                Im[mdn_mask] = MDN_DRIVE if hab_escape.hab_level >= HAB_GIVE_UP else 0.0
                for _ in range(dynamics.SUBSTEPS):
                    h_mdn = dynamics.step(h_mdn, W_m, G_MDN, Im)
                h_mdn[h_mdn < 1e-30] = 0.0  # flush denormals, CLAUDE.md perf note
                mdn_val = h_mdn[mdn_mask].mean()
                if mdn_val >= MDN_THRESHOLD:
                    mdn_backup_hold = mdn_backup_frames
                    print(f"  frame {frame}: escape habituated -> MDN takes over, "
                          f"backing up (hold={mdn_backup_frames})")
            else:
                mdn_val = h_mdn[mdn_mask].mean()

            mdn_backing_up = mdn_backup_hold > 0
            if mdn_backing_up:
                direction = "L"  # hard override, not one more WTA bias
                mdn_backup_hold -= 1
                if mdn_backup_hold == 0:
                    hab_escape.reset()  # a clean slate, per SPEC section 2

            # ---- resolve one shared A button ------------------------------
            press_a = jump_hold > 0 or climb_hold > 0
            if jump_hold > 0:
                jump_hold -= 1
                if jump_hold == 0:
                    jump_cooldown = jump_cooldown_frames
            if climb_hold > 0:
                climb_hold -= 1
                if climb_hold == 0:
                    climb_cooldown = climb_cooldown_frames
            if climb_cooldown > 0 and climb_hold == 0:
                climb_cooldown -= 1

            # ---- speed: DNp09, SPEC_terrain.md section 3 ------------------
            # A jump/hop/stall transiently interrupts ongoing locomotion --
            # a real, documented phenomenon, not invented for convenience.
            # WALK_SUPPRESSION cancels WALK_DRIVE while any of those are in
            # progress, so DNp09 decays and B releases instead of holding
            # forever.
            busy = press_a or stall_count > 0
            Ip = np.zeros(Kp)
            if refusing:
                # docs/MECHANISMS.md #6: "brake at the edge" -- a gap past
                # the validated-safe reach gets zero walk drive outright,
                # not a graded suppression (WALK_SUPPRESSION already covers
                # the ordinary jump/stall case above). No real DNp09 synapse
                # from either odour pathway exists (connectome check c,
                # above) -- same placed-bias category as WALK_DRIVE itself.
                Ip[dnp09_mask] = 0.0
            else:
                # docs/MECHANISMS.md #5: rising ATTRACTIVE odour brakes
                # DNp09 (the aversive channel doesn't -- fleeing calls for
                # speed, not caution, and MECHANISMS.md #5 frames this as an
                # approach-to-food behaviour specifically). Reuses the SAME
                # odor_l_eff/odor_r_eff the steering WTA already computed
                # (already HOME_BIAS-comparable units via ODOUR_GAIN) --
                # capped at WALK_DRIVE so it can only bring the drive to
                # zero, never negative, no new scalar.
                odor_brake = min(WALK_DRIVE, odor_l_eff + odor_r_eff)
                Ip[dnp09_mask] = WALK_DRIVE - (WALK_SUPPRESSION if busy else 0.0) - odor_brake
            for _ in range(dynamics.SUBSTEPS):
                h_speed = dynamics.step(h_speed, W_p, G_SPEED, Ip)
            h_speed[h_speed < 1e-30] = 0.0  # flush denormals, CLAUDE.md perf note
            dnp09_val = h_speed[dnp09_mask].mean()
            press_b = dnp09_val >= DNP09_SPEED_THRESHOLD
            mb_prev_dnp09 = dnp09_val  # for next frame's KC input -- see mushroom-body block

            action = action_index(direction, press_a, press_b)

            log["frame"].append(frame)
            log["mario_x"].append(mario_x)
            log["theta"].append(max(theta["L"], theta["R"]))
            log["lc4"].append(hj[j_msk["LC4_all"]].mean())
            log["lplc2"].append(hj[j_msk["LPLC2_all"]].mean())
            log["mem"].append(float(jump_state.mem.max()))
            log["spike"].append(bool(jump_state.just_spiked.any()))
            log["ttmn"].append(ttmn_val)
            log["dnp09"].append(dnp09_val)
            log["dlmn"].append(dlmn_val)
            log["gap"].append(gap_w)
            log["long_jump"].append(bool(long_jump))
            log["press_b"].append(bool(press_b))
            log["dna01"].append(h_steer[dna01_all].mean())
            log["dna02"].append(h_steer[dna02_all].mean())
            log["direction"].append(direction)
            log["climb"].append(bool(climb_trigger))
            log["conflict"].append(bool(conflict))
            log["odor_l"].append(odor_l_eff)
            log["odor_r"].append(odor_r_eff)
            log["hungry"].append(hunger == HUNGER_MULT_HUNGRY)
            log["raw_odor_l"].append(prod_odor["L"])
            log["raw_odor_r"].append(prod_odor["R"])
            log["orn_a_l"].append(orn_adapt.a["L"])
            log["orn_a_r"].append(orn_adapt.a["R"])
            log["hab_escape"].append(hab_escape.hab_level)
            log["hab_climb"].append(hab_climb.hab_level)
            log["mdn"].append(float(mdn_val))
            log["mdn_backing_up"].append(bool(mdn_backing_up))
            log["ttmn_dnp02"].append(ttmn_val_dnp02)
            log["spike_dnp02"].append(bool(dnp02_state.just_spiked.any()))
            log["pathway_fired"].append(pathway_fired if pathway_fired else "")
            log["avers_l"].append(avers_l_eff)
            log["avers_r"].append(avers_r_eff)
            log["avoid_odor"].append(avoid_odor)
            log["refusing"].append(refusing)
            log["qblock_hit"].append(qblock_hit)
            log["mario_size"].append(mario_size)
            if record_video:
                Image.fromarray(obs).save(tmp / f"{frame:05d}.png")

            obs, reward, done, info = env.step(action)
            frame += 1
            if done:
                # Punishment, once, on death (SPEC section 3): dynamics.CLIP
                # (=50), an existing constant, not a new punishment-scaling
                # scalar. Routed through real PPL+PPM->MBON weights, same
                # depression-only rule as reward.
                dopamine_punish = dynamics.CLIP * mb_punish_reach
                W_kc_mbon -= (LEARNING_RATE * dopamine_punish[:, None] * mb_elig[None, :]
                              * W_kc_mbon)

        if owns_env:
            env.close()  # a caller-supplied env (savestate reuse across episodes) stays open
        print(f"\n{frame} frames -- escape jumps={n_escape_jumps} "
              f"(of which long jumps={n_long_jumps}, DNp01={n_dnp01_fired}, DNp02={n_dnp02_fired})  "
              f"climb hops={n_climb_hops}  climb jumps={n_climb_jumps}  "
              f"conflicts={n_conflicts}  odour avoids={n_odor_avoids}  "
              f"qblock hits={n_qblock_hits}  refusal frames={n_refusals}  "
              f"ended={'died/flagged' if done else 'hit max_frames'}")

        tel = pd.DataFrame(log)
        if record_video:
            _ensure_ffmpeg_on_path()
            import brain_panel
            brain_panel.render_run(tel, tmp, out_mp4,
                                    caption=f"{level}: aversive+attractive odour, DNp09 brake, "
                                            "refusal rule, DNp01 vs DNp02, pit->DLMn long jump, "
                                            "DNa01/DNa02 steering, contact climb")
    return tel, dict(n_escape_jumps=n_escape_jumps, n_long_jumps=n_long_jumps,
                      n_dnp01_fired=n_dnp01_fired, n_dnp02_fired=n_dnp02_fired,
                      n_climb_hops=n_climb_hops, n_climb_jumps=n_climb_jumps,
                      n_conflicts=n_conflicts, n_frames=frame, died_or_flagged=done,
                      n_odor_avoids=n_odor_avoids, n_qblock_hits=n_qblock_hits,
                      n_refusals=n_refusals,
                      mb_weights=W_kc_mbon, max_x_abs=max_x_abs)


LEVEL_RUNS = [
    ("1-1", "runs/008a_1-1.mp4"),
    ("1-2", "runs/008b_1-2.mp4"),
    ("1-3", "runs/008c_1-3.mp4"),
]


def run_008():
    """SPEC_odour.md section 3: does the long jump generalise? One hero
    video per level, MAX_FRAMES raised to give 1-2/1-3 a real chance at
    reaching a pit (1-1's pits sit well within 1200 frames; the others'
    don't necessarily). inject_frame=60 for all three -- moved earlier than
    the original MUSHROOM_INJECT_FRAME=220 after finding 220 sometimes lands
    after an already-fatal encounter near 1-1's first ?-block wobble (see
    the writeup) -- 60 is safely before that on every level tried."""
    from pit_report import find_pit_events, summarize, print_table

    print("=" * 70)
    print("SPEC_odour.md section 3: pit generalisation across 1-1/1-2/1-3")
    print("=" * 70)
    all_rows = {}
    for level, out_mp4 in LEVEL_RUNS:
        print(f"\n--- {level} -> {out_mp4} ---")
        tel, info = main(out_mp4=out_mp4, level=level, max_frames=2500, inject_frame=60)
        events = find_pit_events(tel)
        rows = summarize(tel, events, info["died_or_flagged"], info["n_frames"])
        print_table(level, rows)
        all_rows[level] = (rows, info)
    return all_rows


def run_016(out_mp4="runs/016_smell.mp4", max_frames=1500,
            mushroom_frame=None, mushroom_offset=50, gap_frame=600,
            record_video=True):
    """SPEC_odour.md sprint 016 ("make it a smell problem"), level 1-1 only.
    Success = four observable events in one run: avoids a Goomba (aversive
    odour steers away before DNp01 ever needs to), hits a real `?` block,
    eats the mushroom, refuses a wide pit.

    Tried the mushroom as a synthetic injection first (the established
    006-precedent test stimulus) and found something new: it doesn't
    actually work for THIS purpose. Confirmed empirically (not assumed) --
    walked Mario's real hitbox straight through/around an injected object
    for 100+ frames and its Active flag never clears, while an identical
    poke using a real enemy's own ID collides and kills Mario immediately.
    inject_mushroom only ever needed to produce an ODOUR value before this
    sprint (006/008/009 tested WTA competition and adaptation, never actual
    pickup) -- most likely explanation: the real game's own spawn routine
    caches per-object state (e.g. hitbox dimensions) that a raw RAM poke of
    just Active/ID/X/Y never populates, so collision has nothing to check
    against. Left `inject_mushroom`/`mushroom_offset` in place (still used
    by 006/008's own competition tests, and still useful as a pure odour
    source), but this sprint's own default run does NOT use it --
    `mushroom_frame=None` -- because it turned out to be unnecessary: with
    aversive odour + attractive odour + hunger all live, Mario organically
    survives long enough to hit a REAL power-up `?` block from below (an
    incidental climb-reflex/escape-jump arc, not a dedicated hit-blocks-
    from-below mechanism -- this project still doesn't have one) and the
    GAME's own spawn routine produces a real, properly-collidable mushroom
    that the existing odour pathway then pulls him into. All the more
    honest for being unscripted.

    The wide pit stays synthetic (`poke_wide_gap`) for the reason stated in
    the connectome-check comment block: 1-1's only real pits are 2 tiles,
    comfortably inside the validated-safe range, so there is no real pit
    on this level that SHOULD be refused. `gap_frame=600` is chosen
    empirically, from a first no-injection run of this exact configuration,
    to land after the real `?`-block hits/mushroom (frames 226/356/400 in
    that run) so it doesn't disturb them, and before the Goomba encounter
    that eventually ends the run."""
    tel, info = main(out_mp4=out_mp4, level="1-1", max_frames=max_frames,
                      record_video=record_video,
                      inject_frame=mushroom_frame, mushroom_offset=mushroom_offset,
                      inject_gap_frame=gap_frame)

    print("\n" + "=" * 70)
    print("sprint 016: four-event report")
    print("=" * 70)

    avoid_frames = tel.index[tel["avoid_odor"] & ~tel["avoid_odor"].shift(1, fill_value=False)]
    if len(avoid_frames):
        print(f"1. avoids a Goomba (odour): frame {int(tel['frame'].iloc[avoid_frames[0]])} "
              f"(and {len(avoid_frames) - 1} more time(s) later in the run)")
    else:
        print("1. avoids a Goomba (odour): DID NOT HAPPEN this run")

    qb_frames = tel.loc[tel["qblock_hit"], "frame"]
    if len(qb_frames):
        print(f"2. hits a real '?' block: frame {int(qb_frames.iloc[0])}")
    else:
        print("2. hits a real '?' block: DID NOT HAPPEN this run")

    grew = tel.index[tel["mario_size"] > tel["mario_size"].shift(1, fill_value=tel["mario_size"].iloc[0])]
    if len(grew):
        print(f"3. eats the mushroom: frame {int(tel['frame'].iloc[grew[0]])}")
    else:
        print("3. eats the mushroom: DID NOT HAPPEN this run")

    refuse_frames = tel.index[tel["refusing"] & ~tel["refusing"].shift(1, fill_value=False)]
    if len(refuse_frames):
        print(f"4. refuses a wide pit: frame {int(tel['frame'].iloc[refuse_frames[0]])}")
    else:
        print("4. refuses a wide pit: DID NOT HAPPEN this run")

    print(f"\n{info['n_frames']} frames, "
          f"{'died/flagged' if info['died_or_flagged'] else 'hit max_frames'}, "
          f"max_x_abs={info['max_x_abs']}")
    return tel, info


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "008":
        run_008()
    elif len(sys.argv) > 1 and sys.argv[1] == "016":
        run_016()
    else:
        main()
