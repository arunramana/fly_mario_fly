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

from fly.network import dynamics
from fly.network.integrator import Integrator
from fly.network.network import Network
from fly.sensing.olfactory_adaptation import OlfactoryAdaptation
from fly.state.reflex_habituation import ReflexHabituation, HAB_GIVE_UP
from mario.ram import tile_ram
from mario.ram.addresses import (
    ADDR_MARIO_X, ADDR_MARIO_PAGE, ADDR_MARIO_Y, ADDR_MARIO_SIZE,
    ADDR_ENEMY_X, ADDR_ENEMY_Y, ADDR_ENEMY_ACTIVE, ADDR_ENEMY_TYPE,
    N_ENEMY_SLOTS, POWERUP_ID,
)
from mario.actions.actions import MOVES, action_index
from mario.emulator.env import make_env
from bridge.perception import (
    enemy_thetas, mushroom_odor, question_block_odor, goomba_odor,
    hunger_multiplier, HUNGER_MULT_HUNGRY,
)
from fly.connectome.load_cached import load as load_jump
from fly.circuits.load_steering_cached import load as load_steering
from fly.circuits.load_takeoff_cached import load as load_takeoff
from fly.circuits.load_speed_cached import load as load_speed
from fly.circuits.load_mdn_cached import load as load_mdn
from fly.circuits.load_dnp02_cached import load as load_dnp02
from fly.circuits.load_mushroom_body_cached import load as load_mushroom_body
from config.params import (
    Dnp02Params, MdnParams, MushroomBodyParams, OdourParams, SpeedParams,
    SteeringParams, TakeoffParams, TerrainParams, DemoParams,
)

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


# run_mario.py still owns G/DNP01_SPIKE_THRESHOLD/SPIKE_AMP/TTMN_PRESS_
# THRESHOLD/JUMP_HOLD_FRAMES/JUMP_COOLDOWN_FRAMES -- the jump circuit's own
# hand-set scalars, never moved. Consolidating these alongside every other
# circuit's own gain (which all live here in run_steering.py instead) is a
# real inconsistency, flagged in docs/REFACTOR_PLAN.md's phase 2 report --
# out of scope for a phase whose rule is "move code, don't change it".
from run_mario import (JUMP_HOLD_FRAMES, JUMP_COOLDOWN_FRAMES,
                        G, DNP01_SPIKE_THRESHOLD, SPIKE_AMP, TTMN_PRESS_THRESHOLD)
from compare_controllers import _ensure_ffmpeg_on_path

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
_odour_params = OdourParams()
ODOUR_GAIN = _odour_params.odour_gain
# HUNGER_MULT_HUNGRY/SATED moved to bridge/perception.py with
# hunger_multiplier() itself, phase 2 -- imported above. Values unchanged
# (3.0/1.0); tune_odour.py's own sweep, referenced above, is what picked them.

# ---- ORN adaptation, sprint after SPEC_odour.md -------------------------
# A real olfactory receptor neuron's response to a SUSTAINED concentration
# decays over ~1-2 seconds and recovers once the stimulus is gone -- this is
# receptor physiology, not a steering rule, so it is applied entirely
# within the sensory layer (OlfactoryAdaptation, moved to
# fly/sensing/olfactory_adaptation.py in phase 2), and the WTA code
# downstream never needs to know it exists. Applied to the
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
# HOME_BIAS takes back over. ALPHA_ADAPT=1/90 (fly/sensing/
# olfactory_adaptation.py) gives a ~1.5s time constant at 60fps -- this runs
# once per EMULATOR frame, same cadence as the odour reading itself, so 90
# FRAMES really is ~1.5s of wall-clock game time.

# ---- hand-set scalars, SPEC_steering.md section 5 -----------------------
# REFACTOR_PLAN.md phase 4: sourced from config.params.SteeringParams
# (docs/SCALARS.md), not redefined here.
_steering_params = SteeringParams()
G_STEER = _steering_params.g                              # tune_steering.py
HOME_BIAS = _steering_params.home_bias                     # constant "go home" current, R-hemisphere only
CLIMB_STALL_FRAMES = _steering_params.climb_stall_frames   # mario_x unchanged this long while steering=R -> blocked
CLIMB_HOP_SMALL_FRAMES = _steering_params.climb_hop_small_frames  # small Mario's first-try hop hold
CLIMB_HOP_BIG_FRAMES = _steering_params.climb_hop_big_frames      # big/fiery Mario's first-try hop hold (taller hitbox)
CLIMB_JUMP_FRAMES = _steering_params.climb_jump_frames     # escalated full jump hold, same magnitude as the escape jump
CLIMB_COOLDOWN_FRAMES = _steering_params.climb_cooldown_frames
CLIMB_CLEAR_DISTANCE = _steering_params.climb_clear_distance  # px of forward progress that resets the attempt counter

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
# REFACTOR_PLAN.md phase 4: sourced from config.params.TakeoffParams/
# SpeedParams (docs/SCALARS.md), not redefined here.
_takeoff_params = TakeoffParams()
G_TAKEOFF = _takeoff_params.g                                    # tune_terrain.py
GAP_GAIN = _takeoff_params.gap_gain                              # external current per non-ground tile ahead, onto DNp01
DLMN_RECRUIT_THRESHOLD = _takeoff_params.dlmn_recruit_threshold  # DLMn mean activation -> recruit the long jump
LONG_JUMP_HOLD_FRAMES = _takeoff_params.long_jump_hold_frames    # vs the escape jump's JUMP_HOLD_FRAMES=25
GAP_LOOKAHEAD_TILES = _takeoff_params.gap_lookahead_tiles

_speed_params = SpeedParams()
G_SPEED = _speed_params.g                                    # tune_terrain.py
WALK_DRIVE = _speed_params.walk_drive                        # constant "walk" current onto DNp09
WALK_SUPPRESSION = _speed_params.walk_suppression            # cancels WALK_DRIVE while jumping/stalled
DNP09_SPEED_THRESHOLD = _speed_params.dnp09_speed_threshold  # DNp09 mean activation -> press B

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
# HAB_PROGRESS_PX/HAB_GIVE_UP moved to fly/state/reflex_habituation.py with
# ReflexHabituation itself, phase 2 (HAB_GIVE_UP imported above -- main()
# still compares against it directly for MDN's own trigger). Values
# unchanged (16px / 3 firings).

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
# REFACTOR_PLAN.md phase 4: sourced from config.params.MdnParams
# (docs/SCALARS.md), not redefined here.
_mdn_params = MdnParams()
G_MDN = _mdn_params.g
MDN_DRIVE = _mdn_params.mdn_drive
MDN_THRESHOLD = _mdn_params.mdn_threshold
MDN_BACKUP_FRAMES = _mdn_params.mdn_backup_frames

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
# REFACTOR_PLAN.md phase 4: sourced from config.params.Dnp02Params
# (docs/SCALARS.md), not redefined here.
_dnp02_params = Dnp02Params()
G_DNP02 = _dnp02_params.g
DNP02_SPIKE_THRESHOLD = _dnp02_params.spike_threshold
DNP02_ALPHA = _dnp02_params.alpha

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
# REFACTOR_PLAN.md phase 4: sourced from config.params.MushroomBodyParams
# (docs/SCALARS.md), not redefined here.
_mb_params = MushroomBodyParams()
KC_SPARSITY = _mb_params.kc_sparsity
TRACE_DECAY = _mb_params.trace_decay
LEARNING_RATE = _mb_params.learning_rate

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
# REFACTOR_PLAN.md phase 4: sourced from config.params.TerrainParams
# (docs/SCALARS.md), not redefined here.
REFUSAL_GAP_TILES = TerrainParams().refusal_gap_tiles

# ADDR_MARIO_SIZE/ADDR_ENEMY_TYPE/POWERUP_ID now live in
# mario/ram/addresses.py (imported above), phase 2 -- enemy_thetas() needed
# some of them too, to fix the contamination bug SPEC_habituation.md's
# investigation found.

# 8-way action space (was: hold B unconditionally) -- {left,right} x
# {A on/off} x {B on/off}. Index = direction_base + 2*press_a + press_b.
# MOVES/action_index moved to mario/actions/actions.py, phase 2 (imported
# above), make_env moved to mario/emulator/env.py, same phase.

MAX_FRAMES = 1200
# No default injection frame any more (sprint 011: opt-in only, see main()'s
# `inject_frame` docstring) -- callers that want the odour demo pass their
# own frame number explicitly, e.g. run_008()'s inject_frame=60.
# REFACTOR_PLAN.md phase 4: sourced from config.params.DemoParams
# (docs/SCALARS.md), not redefined here.
MUSHROOM_OFFSET = DemoParams().mushroom_offset  # spawn BEHIND Mario so it competes with HOME_BIAS's rightward pull


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
    ram[ADDR_ENEMY_Y + slot] = int(mario_y)
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
         mushroom_offset=None, inject_gap_frame=None, write_telemetry=True,
         retinotopic=False, sigma=0.0, seed=None):
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
    real pit wide enough to need it.

    `retinotopic`, sprints 023-024, CLOSED: True drives LC4/LPLC2
    per-cell, weighted by each real cell's own receptive-field alignment
    to the approaching enemy's actual position (`retinotopy.py`). False
    (default) reproduces the exact pre-023 behaviour -- the same theta/
    dtheta scalar broadcast identically to every cell in a hemisphere.
    Default is False, permanently: 023 found the per-cell weighting
    starves DNp01/TTMn of drive at the moment escape needs it most
    because its foveal origin sat at the sparsest edge of each real RF
    distribution; 024 fixed exactly that (origin moved to the real
    measured density mode, a real 4.4x weight improvement, confirmed) and
    still got 0 commitments and the SAME frame-170 death as 023 -- the
    recurrent circuit needs something close to the old uniform population
    engagement to reach threshold, which no single-target Gaussian tuning
    curve supplies regardless of where its centre sits. Two pre-
    registered attempts, both failed on the same criteria; per 024's own
    hard-stop (docs/RUNS.md 024), this is closed. Kept in code (not
    deleted) as a real, working, negative-result artifact -- not a
    starting point for a third mapping convention.

    `sigma`, sprint 025: standard deviation of `eta ~ N(0, sigma)`, added
    to every neuron's drive, every substep, in every circuit
    (`dynamics.NoiseConfig`) -- W, I, and every reward/threshold are
    untouched. 0.0 (default) draws no random numbers and is bit-identical
    to every pre-025 run. `seed`, sprint 025: seeds the one
    `np.random.Generator` this episode's noise is drawn from (`None`
    draws a fresh OS-entropy seed and PRINTS it -- seed discipline is
    non-negotiable here, since noise is the only thing that can make this
    otherwise-deterministic emulator+circuit stack non-reproducible;
    replaying the same seed at the same sigma must reproduce the episode
    exactly). Returned in `info["seed"]`/`info["sigma"]` either way, so a
    caller that didn't choose a seed can still recover and log the one
    that was actually used."""
    if seed is None:
        seed = int(np.random.SeedSequence().entropy % (2**32))
    rng = np.random.default_rng(seed)
    noise = dynamics.NoiseConfig(sigma, rng)
    if sigma > 0.0:
        print(f"sprint 025: seed={seed} sigma={sigma}")
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
    jump_network = Network(W_j, Integrator(spike_idx=dnp01_idx,
                                            spike_threshold=DNP01_SPIKE_THRESHOLD,
                                            spike_amp=SPIKE_AMP),
                            g=G, populations=j_msk)

    # sprint 023: per-cell receptive fields for LC4/LPLC2 (retinotopy.py),
    # replacing the uniform-theta injection below with a per-cell weighted
    # one -- SAME 1255 neurons, SAME DNp01/TTMn, SAME thresholds, only the
    # input map changes. `retinotopic=False` reproduces the exact
    # pre-023 uniform injection, for the paired before/after comparison.
    if retinotopic:
        from fly.sensing import retinotopy as rt
        j_rf = {"LC4": rt.receptive_field_centers("LC4", j_bodies),
                "LPLC2": rt.receptive_field_centers("LPLC2", j_bodies)}
        # sprint 024: ORIGIN is now the real density mode of that type+
        # side's own per-cell RF centres (rt.density_mode -- data-derived,
        # not chosen), replacing 023's hex1.min(), the fix this sprint
        # exists to test. FAR is still hex1.max(), unchanged from 023.
        # HEX2_MID: that population's own real median hex2 ("eye level"),
        # since this game has no elevation signal to drive that axis with.
        j_azimuth_ref = {}
        for t in ("LC4", "LPLC2"):
            for side in ("L", "R"):
                m = j_msk[f"{t}_{side}"]
                h1 = j_rf[t]["hex1"][m]; h2 = j_rf[t]["hex2"][m]
                spread = j_rf[t]["hex1_spread"][m]
                origin = rt.density_mode(h1, spread)
                j_azimuth_ref[(t, side)] = (origin, h1.max(), float(np.median(h2)))

    print("Loading the steering circuit (DNa01/DNa02, N=60, cached)...")
    s_bodies, _, _, _, W_s, _, _ = _memo_load("steering", load_steering)
    Ks = W_s.shape[0]
    r_mask, l_mask = make_steering_masks(s_bodies)
    dna01_all = (s_bodies["type"] == "DNa01").to_numpy()
    dna02_all = (s_bodies["type"] == "DNa02").to_numpy()
    # sprint 017: by-TYPE means (dna01_all/dna02_all above) collapse L+R
    # together and are NOT what the WTA decides on -- r_team/l_team (by
    # HEMISPHERE, mixing DNa01+DNa02 on that side) are. Logging the by-side
    # split explicitly so a real asymmetry (or its absence) is visible
    # without having to re-derive it from the aggregate-by-type columns.
    sm = lambda t, s: ((s_bodies["type"] == t) & (s_bodies["somaSide"] == s)).to_numpy()
    dna01_l_mask, dna01_r_mask = sm("DNa01", "L"), sm("DNa01", "R")
    dna02_l_mask, dna02_r_mask = sm("DNa02", "L"), sm("DNa02", "R")
    steering_network = Network(W_s, Integrator(), g=G_STEER, populations={"R": r_mask, "L": l_mask})
    h_steer = steering_network.h
    orn_adapt = OlfactoryAdaptation()
    orn_adapt_avers = OlfactoryAdaptation()  # separate receptor identity/glomerulus, sprint 016

    print("Loading the takeoff circuit (DNp01 -> GFC1-4 -> DLMn, cached)...")
    t_bodies, _, _, _, W_t, _, _ = _memo_load("takeoff", load_takeoff)
    Kt = W_t.shape[0]
    takeoff_dnp01_mask = (t_bodies["type"] == "DNp01").to_numpy()
    dlmn_mask = t_bodies["type"].isin(["DLMn c-f", "DLMn a, b"]).to_numpy()
    takeoff_network = Network(W_t, Integrator(), g=G_TAKEOFF,
                               populations={"DNp01": takeoff_dnp01_mask, "DLMn": dlmn_mask})
    h_takeoff = takeoff_network.h

    print("Loading the speed circuit (DNp09, N=60, cached)...")
    p_bodies, _, _, _, W_p, _, _ = _memo_load("speed", load_speed)
    Kp = W_p.shape[0]
    dnp09_mask = (p_bodies["type"] == "DNp09").to_numpy()
    # REFACTOR_PLAN.md phase 3: Network/Integrator replace this circuit's own
    # standalone `h_speed = np.zeros(Kp)` + `dynamics.step(...)` call site.
    speed_network = Network(W_p, Integrator(), g=G_SPEED, populations={"DNp09": dnp09_mask})

    print("Loading the MDN circuit (backward walking, N=60, cached)...")
    m_bodies, _, _, _, W_m, _, _ = _memo_load("mdn", load_mdn)
    Km = W_m.shape[0]
    mdn_mask = (m_bodies["type"] == "MDN").to_numpy()
    mdn_network = Network(W_m, Integrator(), g=G_MDN, populations={"MDN": mdn_mask})
    h_mdn = mdn_network.h  # read in the `else` branch below on frames MDN isn't stepped
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
    dnp02_network = Network(W_dp, Integrator(spike_idx=dnp02_idx,
                                              spike_threshold=DNP02_SPIKE_THRESHOLD,
                                              spike_amp=SPIKE_AMP),
                             g=G_DNP02,
                             populations={"L": dnp02_l_mask, "R": dnp02_r_mask,
                                          "TTMn_L": dnp02_ttmn_l, "TTMn_R": dnp02_ttmn_r})

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
        log = {k: [] for k in ("frame", "mario_x", "theta", "dtheta", "d_px", "frames_to_contact",
                                "lc4", "lplc2", "mem", "spike",
                                "ttmn", "dna01", "dna02", "direction", "climb", "conflict",
                                "dnp09", "dlmn", "gap", "long_jump", "press_b",
                                "odor_l", "odor_r", "hungry",
                                "raw_odor_l", "raw_odor_r", "orn_a_l", "orn_a_r",
                                "hab_escape", "hab_climb", "mdn", "mdn_backing_up",
                                "ttmn_dnp02", "spike_dnp02", "pathway_fired",
                                "avers_l", "avers_r", "avoid_odor", "refusing",
                                "qblock_hit", "mario_size",
                                "r_team", "l_team", "dna01_l", "dna01_r",
                                "dna02_l", "dna02_r", "is_r_mask_sum", "is_l_mask_sum",
                                "press_a", "lc4_l", "lc4_r", "lplc2_l", "lplc2_r")}

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
            mario_y = int(ram[ADDR_MARIO_Y])

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
            if retinotopic:
                # sprint 023: per-cell drive instead of one blanket scalar
                # per hemisphere -- same theta/dtheta magnitude as before,
                # now weighted by each real cell's own receptive-field
                # alignment to the SAME dominant enemy's real d_px that
                # already determines theta/dtheta (d_out, above) -- no new
                # enemy-selection logic, just a finer distribution of the
                # existing signal across the population it's driving.
                for _side in ("L", "R"):
                    if d_out[_side] is None:
                        continue
                    for t, mag in (("LC4", abs(dtheta[_side])), ("LPLC2", theta[_side])):
                        if mag == 0.0:
                            continue
                        origin, far, mid = j_azimuth_ref[(t, _side)]
                        az1 = rt.azimuth_target(d_out[_side], origin, far, mid)
                        w = rt.tuning_weights(az1, j_rf[t])
                        Ij[j_msk[f"{t}_{_side}"]] = mag * w[j_msk[f"{t}_{_side}"]]
            else:
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
                hj = jump_network.step(Ij, noise=noise)
                It = np.zeros(Kt)
                It[takeoff_dnp01_mask] = hj[jump_dnp01_mask]
                h_takeoff = takeoff_network.step(It, noise=noise)
            takeoff_network.flush_denormals()  # CLAUDE.md perf note
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
                h_dnp02 = dnp02_network.step(Idp, noise=noise)
            dnp02_network.flush_denormals()  # CLAUDE.md perf note
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

            # sprint 020 FIX: this was `+MBON_DNA02_FRAC * mbon_agg` (an
            # unconditional POSITIVE/excitatory bias) until a direct check
            # of every real edge onto DNa02 within a proper KC/MBON/DNa02
            # network found 243 of 295 real synapses inhibitory -- MBON31/
            # MBON32 (the two bodies MBON_DNA02_FRAC was actually measured
            # from) are BOTH GABAergic, confirmed against consensus_nt.
            # `MBON_DNA02_FRAC` itself is still the right real magnitude
            # (014's synapse-count fraction, unaffected by this) -- only
            # the SIGN was wrong. Real biology this now matches, not
            # invented for the occasion: mushroom-body appetitive learning
            # in the fly is understood as depression RELEASING a baseline
            # inhibitory MBON tone, not adding an attractive pull (Aso et
            # al. and the broader MB literature) -- exactly the shape
            # `SPEC_mushroom_body.md`'s own depression-only plasticity
            # rule already implements: dopamine depresses W_kc_mbon, which
            # lowers mbon_agg, which now correctly SHRINKS an inhibitory
            # term rather than shrinking a (wrongly-signed) excitatory
            # one. Naive (undepressed) MBON tone suppresses movement
            # toward a source; learning a source is rewarding depresses
            # that tone and disinhibits approach. No new scalar --
            # MBON_DNA02_FRAC unchanged, only its sign in the expression.
            mbon_agg = float(h_mbon.mean())
            mb_bias_r = -MBON_DNA02_FRAC["R"] * mbon_agg
            mb_bias_l = -MBON_DNA02_FRAC["L"] * mbon_agg
            # DNp02's own bias has no real synapse to take a sign from
            # (checked, zero -- SPEC_mushroom_body.md section 5); kept
            # structurally parallel to the now-fixed real DNa02 term
            # (same magnitude, same inhibitory-released-by-depression
            # shape) rather than left as the one asymmetric case, a
            # judgement call stated here, not a second real finding.
            mb_bias_dnp02 = -MBON_DNA02_FRAC["R"] * mbon_agg

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
                h_steer = steering_network.step(Is, noise=noise)
            steering_network.flush_denormals()  # CLAUDE.md perf note

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
            frames_to_contact = None  # sprint 023: captured into telemetry below, not just printed
            if jump_cooldown > 0:
                jump_cooldown -= 1
            elif jump_hold == 0:
                dnp01_ready = ttmn_val >= TTMN_PRESS_THRESHOLD
                dnp02_ready = ttmn_val_dnp02 >= TTMN_PRESS_THRESHOLD
                if dnp01_ready or dnp02_ready:
                    if dnp01_ready and dnp02_ready:
                        pathway_fired = "DNp01" if jump_network.just_spiked.any() else (
                            "DNp02" if dnp02_network.just_spiked.any() else "DNp01")
                    else:
                        pathway_fired = "DNp01" if dnp01_ready else "DNp02"
                    if hab_escape.check(mario_x):
                        long_jump = dlmn_val >= DLMN_RECRUIT_THRESHOLD
                        jump_hold = long_jump_hold_frames if long_jump else jump_hold_frames
                        escape_trigger = True
                        n_escape_jumps += 1
                        if pathway_fired == "DNp01":
                            n_dnp01_fired += 1
                            dnp02_network.h[:] = 0.0; dnp02_network.mem[:] = 0.0  # loser resets
                        else:
                            n_dnp02_fired += 1
                            jump_network.h[:] = 0.0; jump_network.mem[:] = 0.0  # loser resets
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
                    h_mdn = mdn_network.step(Im, noise=noise)
                mdn_network.flush_denormals()  # CLAUDE.md perf note
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
                # approach-to-food behaviour specifically).
                #
                # sprint 017 FIX: 016 shipped this using the raw odor_l_eff+
                # odor_r_eff (already HOME_BIAS-comparable via ODOUR_GAIN),
                # reasoning "no new scalar needed, it's already in the right
                # units." That reasoning was wrong -- confirmed by an A/B on
                # the real run, not assumed: with the original formula,
                # dnp09's median over 300 frames was 0.0 and B was pressed
                # 9.3% of the time; with odor forced to 0 (same run,
                # otherwise identical), median was 0.94 and B was pressed
                # 67.7% of the time. ODOUR_GAIN=16 was deliberately sized so
                # odor ALONE could out-compete a constant HOME_BIAS=1.0 at
                # long range (SPEC_odour.md section 0) -- reusing that same
                # inflated magnitude as a braking signal meant "close to a
                # block" and "merely aware of one 100px away, hunger-boosted"
                # produced comparable brake strength, near-fully cancelling
                # WALK_DRIVE across most of a `?`-block-dense stretch, not
                # just on final approach. Fixed the same way SPEC_odour.md's
                # OWN section-0 bug was fixed -- not by inventing a new
                # braking-specific scalar, but by finding the right existing
                # reference point: odor only brakes AFTER it has already
                # overpowered HOME_BIAS (i.e. Mario has actually committed to
                # approaching, not merely detected something) -- reuses
                # HOME_BIAS itself as the free allowance, no new scalar.
                odor_brake = min(WALK_DRIVE, max(0.0, odor_l_eff + odor_r_eff - HOME_BIAS))
                Ip[dnp09_mask] = WALK_DRIVE - (WALK_SUPPRESSION if busy else 0.0) - odor_brake
            for _ in range(dynamics.SUBSTEPS):
                h_speed = speed_network.step(Ip, noise=noise)
            speed_network.flush_denormals()  # CLAUDE.md perf note
            dnp09_val = h_speed[dnp09_mask].mean()
            press_b = dnp09_val >= DNP09_SPEED_THRESHOLD
            mb_prev_dnp09 = dnp09_val  # for next frame's KC input -- see mushroom-body block

            action = action_index(direction, press_a, press_b)

            log["frame"].append(frame)
            log["mario_x"].append(mario_x)
            log["theta"].append(max(theta["L"], theta["R"]))
            # sprint 023: dtheta on whichever side theta itself is dominant
            # this frame -- same side-selection convention as "theta" above,
            # not a new one -- needed to test corr(LC4_mean, dtheta) against
            # corr(LC4_mean, theta), the sprint's own decisive signature.
            log["dtheta"].append(dtheta["L"] if theta["L"] >= theta["R"] else dtheta["R"])
            # sprint 023: raw signed d_px on the same dominant side, so
            # commitment distance (003/011's "d_px ~= 0") is readable
            # straight from telemetry instead of back-solved from theta.
            _dom_side = "L" if theta["L"] >= theta["R"] else "R"
            log["d_px"].append(d_out[_dom_side] if d_out[_dom_side] is not None else np.nan)
            log["lc4"].append(hj[j_msk["LC4_all"]].mean())
            log["lplc2"].append(hj[j_msk["LPLC2_all"]].mean())
            # sprint 017 overlay audit: "lc4"/"lplc2" above blend both
            # hemispheres into one number, same failure-mode class as the
            # dna01/dna02 bug -- lower stakes here since TTMn (the actual
            # jump decision) already reads max(L,R) internally, not this
            # blended mean, but a one-sided Goomba's real drive still gets
            # diluted by the quiet far side in what gets displayed/logged.
            log["lc4_l"].append(hj[j_msk["LC4_L"]].mean())
            log["lc4_r"].append(hj[j_msk["LC4_R"]].mean())
            log["lplc2_l"].append(hj[j_msk["LPLC2_L"]].mean())
            log["lplc2_r"].append(hj[j_msk["LPLC2_R"]].mean())
            log["mem"].append(float(jump_network.mem.max()))
            log["spike"].append(bool(jump_network.just_spiked.any()))
            log["ttmn"].append(ttmn_val)
            log["dnp09"].append(dnp09_val)
            log["dlmn"].append(dlmn_val)
            log["gap"].append(gap_w)
            log["long_jump"].append(bool(long_jump))
            log["press_b"].append(bool(press_b))
            log["dna01"].append(h_steer[dna01_all].mean())
            log["dna02"].append(h_steer[dna02_all].mean())
            log["r_team"].append(r_team)
            log["l_team"].append(l_team)
            log["dna01_l"].append(h_steer[dna01_l_mask].mean())
            log["dna01_r"].append(h_steer[dna01_r_mask].mean())
            log["dna02_l"].append(h_steer[dna02_l_mask].mean())
            log["dna02_r"].append(h_steer[dna02_r_mask].mean())
            log["is_r_mask_sum"].append(float(Is[r_mask].sum()))
            log["is_l_mask_sum"].append(float(Is[l_mask].sum()))
            log["press_a"].append(bool(press_a))
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
            log["spike_dnp02"].append(bool(dnp02_network.just_spiked.any()))
            log["pathway_fired"].append(pathway_fired if pathway_fired else "")
            log["frames_to_contact"].append(frames_to_contact if frames_to_contact is not None else np.nan)
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
        if write_telemetry:
            # sprint 017: 006-012 always wrote one of these; 016 quietly
            # didn't, and the diagnosis had to be done by OCR-ing the video
            # instead of reading real numbers. Every column in `log` --
            # the full overlay, not a curated subset -- same
            # `{stem}_telemetry.csv` naming `runs/006_steering_telemetry.csv`
            # etc. already established. Independent of record_video: a fast,
            # headless (record_video=False) run is exactly where this
            # matters most for diagnosis.
            csv_path = Path(out_mp4).with_name(Path(out_mp4).stem + "_telemetry.csv")
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            tel.to_csv(csv_path, index=False)
            print(f"wrote {csv_path}")
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
                      mb_weights=W_kc_mbon, max_x_abs=max_x_abs,
                      seed=seed, sigma=sigma)


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


def run_023(max_frames=1500, gap_frame=600):
    """sprint 023: the paired before/after that decides whether per-cell
    retinotopy (retinotopy.py) moves commitment earlier. Same level (1-1),
    same max_frames/gap_frame as 016/017's own default configuration --
    NOT a fresh scenario, so any difference is attributable to the one
    thing that changed (`retinotopic`), not to a different run of Mario's
    own organic encounters. Both conditions run from the SAME code, same
    frame, so this is a true paired comparison, not "compare against 017's
    old CSV" (017 predates the `dtheta`/`d_px` telemetry columns this
    measurement needs, and predates the DNp09-brake fix landing in the
    same working tree -- rerunning `retinotopic=False` here controls for
    both, isolating the one real variable).

    `retinotopic=False` gets no video (identical visible behaviour to
    017 by construction -- the whole point of this sprint is that only
    the INPUT MAP to LC4/LPLC2 changes, not the WTA/threshold/output
    machinery), `retinotopic=True` gets `runs/023_retinotopy.mp4` -- the
    first video since 017 because this is the first sprint since then
    that changes what Mario does."""
    from commitment_report import report

    print("=" * 70)
    print("sprint 023: retinotopy paired comparison, level 1-1")
    print("=" * 70)

    print("\n[before] retinotopic=False (uniform theta/dtheta broadcast)...")
    tel_before, info_before = main(
        out_mp4="runs/023_retinotopy_before.mp4", level="1-1",
        max_frames=max_frames, record_video=False,
        inject_gap_frame=gap_frame, retinotopic=False)

    print("\n[after] retinotopic=True (per-cell receptive-field weighting)...")
    tel_after, info_after = main(
        out_mp4="runs/023_retinotopy.mp4", level="1-1",
        max_frames=max_frames, record_video=True,
        inject_gap_frame=gap_frame, retinotopic=True)

    before = report(tel_before, "BEFORE (retinotopic=False)")
    after = report(tel_after, "AFTER (retinotopic=True)")

    print("\n" + "=" * 70)
    print("sprint 023: verdict")
    print("=" * 70)
    if before["median_frames_to_contact"] is not None and after["median_frames_to_contact"] is not None:
        print(f"median frames_to_contact at commit: {before['median_frames_to_contact']:.2f} -> "
              f"{after['median_frames_to_contact']:.2f} "
              f"({'EARLIER' if after['median_frames_to_contact'] > before['median_frames_to_contact'] else 'not earlier'})")
    c_before = before["corr"]; c_after = after["corr"]
    print(f"corr(LC4,theta) before={c_before['corr_lc4_theta']:.4f} after={c_after['corr_lc4_theta']:.4f}")
    print(f"corr(LC4,dtheta) before={c_before['corr_lc4_dtheta']:.4f} after={c_after['corr_lc4_dtheta']:.4f}")
    flipped = (c_after["corr_lc4_dtheta"] > c_after["corr_lc4_theta"]) and \
              not (c_before["corr_lc4_dtheta"] > c_before["corr_lc4_theta"])
    print(f"velocity-tuning signature (dtheta corr now exceeds theta corr, "
          f"and didn't before): {flipped}")

    return dict(tel_before=tel_before, tel_after=tel_after,
                info_before=info_before, info_after=info_after,
                before=before, after=after)


def run_024(max_frames=1500, gap_frame=600):
    """sprint 024, second and final retinotopy attempt. 023 failed because
    d_px=0 mapped to hex1.min(), the sparsest edge of each population's
    real RF-centre distribution -- the ONE thing this sprint changes is
    that origin, now `retinotopy.density_mode()` (the real density peak),
    computed inside `main()` itself when `retinotopic=True` (see
    run_steering.py's own j_azimuth_ref block). Everything else identical
    to 023: same level (1-1), same max_frames/gap_frame, same
    TTMN_PRESS_THRESHOLD, same AZIMUTH_D_REF, same per-cell tuning
    bandwidth (each cell's own measured hex1_spread). Same pre-registered
    criteria as 023, decided before this function ran, not after seeing
    results: (1) frames_to_contact at commitment vs 017's own 32-frame
    baseline median -- earlier is the win; (2) whether corr(pop,dtheta)
    exceeds corr(pop,theta) for LC4 AND LPLC2 (023 found the LC4-only
    version of this check was confounded by LC4's own scalar drive
    already being dtheta -- see commitment_report.py); (3) survival and
    commitment count vs the 807-frame / 10-commit baseline. Hard stop,
    stated before running: if this fails, retinotopy is closed
    permanently -- `retinotopic` stays default False and no third mapping
    convention gets proposed."""
    from commitment_report import report

    print("=" * 70)
    print("sprint 024: retinotopy, fovea-at-density-mode, second and final attempt")
    print("=" * 70)

    print("\n[before] retinotopic=False (identical to 017/023's own baseline)...")
    tel_before, info_before = main(
        out_mp4="runs/024_retinotopy_fovea_before.mp4", level="1-1",
        max_frames=max_frames, record_video=False,
        inject_gap_frame=gap_frame, retinotopic=False)

    print("\n[after] retinotopic=True, origin=density_mode()...")
    tel_after, info_after = main(
        out_mp4="runs/024_retinotopy_fovea.mp4", level="1-1",
        max_frames=max_frames, record_video=True,
        inject_gap_frame=gap_frame, retinotopic=True)

    before = report(tel_before, "BEFORE (retinotopic=False)")
    after = report(tel_after, "AFTER (retinotopic=True, fovea=density_mode)")

    print("\n" + "=" * 70)
    print("sprint 024: verdict against the three pre-registered criteria")
    print("=" * 70)
    if before["median_frames_to_contact"] is not None and after["median_frames_to_contact"] is not None:
        print(f"(1) median frames_to_contact at commit: {before['median_frames_to_contact']:.2f} -> "
              f"{after['median_frames_to_contact']:.2f} "
              f"({'EARLIER than 017 baseline' if after['median_frames_to_contact'] > 32 else 'not earlier than 017 baseline (32)'})")
    else:
        print("(1) frames_to_contact: no commitments in one or both runs -- see (3)")
    c_before = before["corr"]; c_after = after["corr"]
    for pop in ("lc4", "lplc2"):
        exceeds = c_after[f"corr_{pop}_dtheta"] > c_after[f"corr_{pop}_theta"]
        print(f"(2) {pop.upper()}: corr(theta)={c_after[f'corr_{pop}_theta']:.4f}  "
              f"corr(dtheta)={c_after[f'corr_{pop}_dtheta']:.4f}  "
              f"velocity exceeds size: {exceeds}")
    print(f"(3) commitments: before={len(before['events'])} (baseline=10)  "
          f"after={len(after['events'])}  "
          f"survival: before={'died' if info_before['died_or_flagged'] else 'survived'} "
          f"({info_before['n_frames']} frames)  "
          f"after={'died' if info_after['died_or_flagged'] else 'survived'} ({info_after['n_frames']} frames)")

    return dict(tel_before=tel_before, tel_after=tel_after,
                info_before=info_before, info_after=info_after,
                before=before, after=after)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "008":
        run_008()
    elif len(sys.argv) > 1 and sys.argv[1] == "016":
        run_016()
    elif len(sys.argv) > 1 and sys.argv[1] == "023":
        run_023()
    elif len(sys.argv) > 1 and sys.argv[1] == "024":
        run_024()
    else:
        main()
