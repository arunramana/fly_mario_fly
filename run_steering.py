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
from types import SimpleNamespace

import setuptools  # noqa: F401  -- must import before gym on py3.12
import numpy as np
import pandas as pd
from PIL import Image

from sim.telemetry import TelemetryObserver
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


def main(out_mp4=None, level="1-1", max_frames=MAX_FRAMES,
         force_mario_size=None, force_size_from_frame=None, record_video=True,
         inject_frame=None, frame_skip=1, savestate=None, mb_weights=None,
         mushroom_offset=None, inject_gap_frame=None, write_telemetry=True,
         retinotopic=False, sigma=0.0, seed=None, telemetry_path=None):
    """REFACTOR_PLAN.md phase 5: `out_mp4` has no default any more. It used
    to be `"runs/008_run.mp4"` -- a silent, stray, top-level fallback that
    every actual caller already overrode (checked: none of run_008/016/023/
    024, nor tests/golden/, ever relied on it). "Make a run without a named
    project fail loudly" means exactly that: pass an explicit `out_mp4`
    (as every real caller already does), or build one from a ProjectConfig
    via `sim/output_routing.py`'s `resolve_run_path`/`resolve_telemetry_path`
    and `sim/project_runner.py`'s `run_from_config`.

    `telemetry_path`, if given, overrides the telemetry CSV's location
    instead of deriving it from `out_mp4`'s own stem (the pre-phase-5
    behaviour, unchanged when this is left `None`) -- `sim/output_routing.py`
    uses this to put telemetry in `projects/<name>/telemetry/`, separate
    from `projects/<name>/runs/`.

    `mb_weights`, if given, is the KC->MBON weight sub-matrix (SPEC_
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
    if out_mp4 is None:
        raise ValueError(
            "main() needs an explicit out_mp4 -- there is no default any "
            "more (REFACTOR_PLAN.md phase 5: a run without a named project "
            "must fail loudly, not silently write to a stray top-level "
            "runs/008_run.mp4). Pass out_mp4 directly, or route it through "
            "a ProjectConfig via sim.output_routing.resolve_run_path() / "
            "sim.project_runner.run_from_config()."
        )
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

    # REFACTOR_PLAN.md phase 5b: circuit setup and all per-episode decision
    # state now live in bridge.full_policy.FullPolicy -- the same code,
    # moved (see that module's own docstring: a verbatim transcription,
    # not a redesign). This block only constructs it and unpacks its
    # public attributes back into the same local names the frame loop
    # below already uses, so the loop's own text is untouched by this
    # commit -- a golden mismatch here can only mean FullPolicy's
    # constructed/reset state itself diverged from main()'s own setup,
    # not a loop-logic bug (the loop body is migrated onto `policy.act()`
    # directly in the next commit).
    from bridge.full_policy import FullPolicy
    import dataclasses as _dataclasses
    from config.project_config import ProjectConfig as _ProjectConfig
    _pc = _ProjectConfig()
    _pc = _dataclasses.replace(_pc, noise=_dataclasses.replace(_pc.noise, sigma=sigma))
    policy = FullPolicy(config=_pc, level=level, retinotopic=retinotopic,
                         frame_skip=frame_skip, mb_weights=mb_weights)
    policy.reset(seed)

    Kj, j_msk = policy.Kj, policy.j_msk
    jump_dnp01_mask, jump_network = policy.jump_dnp01_mask, policy.jump_network
    if retinotopic:
        j_rf, j_azimuth_ref, rt = policy.j_rf, policy.j_azimuth_ref, policy._rt
    Ks, r_mask, l_mask = policy.Ks, policy.r_mask, policy.l_mask
    dna01_all, dna02_all = policy.dna01_all, policy.dna02_all
    dna01_l_mask, dna01_r_mask = policy.dna01_l_mask, policy.dna01_r_mask
    dna02_l_mask, dna02_r_mask = policy.dna02_l_mask, policy.dna02_r_mask
    steering_network = policy.steering_network
    h_steer = steering_network.h
    orn_adapt, orn_adapt_avers = policy.orn_adapt, policy.orn_adapt_avers

    Kt = policy.Kt
    takeoff_dnp01_mask, dlmn_mask = policy.takeoff_dnp01_mask, policy.dlmn_mask
    takeoff_network = policy.takeoff_network
    h_takeoff = takeoff_network.h

    Kp, dnp09_mask = policy.Kp, policy.dnp09_mask
    speed_network = policy.speed_network

    Km, mdn_mask = policy.Km, policy.mdn_mask
    mdn_network = policy.mdn_network
    h_mdn = mdn_network.h  # read in the `else` branch below on frames MDN isn't stepped
    hab_escape, hab_climb = policy.hab_escape, policy.hab_climb
    mdn_backup_hold = policy.mdn_backup_hold

    Kdp = policy.Kdp
    dnp02_lc4_r, dnp02_lc4_l = policy.dnp02_lc4_r, policy.dnp02_lc4_l
    dnp02_l_mask, dnp02_r_mask = policy.dnp02_l_mask, policy.dnp02_r_mask
    dnp02_idx = policy.dnp02_idx
    dnp02_ttmn_l, dnp02_ttmn_r = policy.dnp02_ttmn_l, policy.dnp02_ttmn_r
    dnp02_network = policy.dnp02_network

    n_kc, n_mbon = policy.n_kc, policy.n_mbon
    W_kc_mbon = policy.W_kc_mbon
    mb_pam_reach, mb_punish_reach = policy.mb_pam_reach, policy.mb_punish_reach
    mb_proj = policy.mb_proj
    mb_elig, mb_prev_dnp09 = policy.mb_elig, policy.mb_prev_dnp09
    mb_bias_dnp02, h_mbon = policy.mb_bias_dnp02, policy.h_mbon
    prev_mario_x_abs, max_x_abs = policy.prev_mario_x_abs, policy.max_x_abs
    MBON_DNA02_FRAC = policy.MBON_DNA02_FRAC

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
        # REFACTOR_PLAN.md phase 5, section 5.2: "Telemetry becomes an
        # observer the episode notifies, so adding a recorded field never
        # edits the loop." Column order fixed here, once, exactly as the
        # old `log = {k: [] for k in (...)}` dict comprehension fixed it --
        # sim.telemetry.TelemetryObserver doesn't know what any of these
        # mean, it just preserves this order in the CSV it writes.
        observer = TelemetryObserver((
            "frame", "mario_x", "theta", "dtheta", "d_px", "frames_to_contact",
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
            "press_a", "lc4_l", "lc4_r", "lplc2_l", "lplc2_r",
        ))

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
                row = dict(observer.last_row) if observer.last_row is not None else observer.new_row()
                row["frame"] = frame
                row["mario_x"] = mario_x
                observer.record(row)
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

            # ---- decision loop: bridge.full_policy.FullPolicy -------------
            # REFACTOR_PLAN.md phase 5b: terrain sensing through the final
            # action_index() call all now live in FullPolicy.act() -- the
            # same code (see that module's own docstring: a verbatim
            # transcription, not a redesign), moved so the mushroom body's
            # KC/MBON plasticity update exists in exactly one place before
            # phase 6's trace attaches to it. `policy` (constructed above)
            # carries every persistent piece of state (jump_hold, hab_escape,
            # W_kc_mbon, ...) that main()'s own locals used to hold directly;
            # this block reads back only what the telemetry row below needs,
            # via `policy.last_info` and the live sub-objects already
            # aliased above (h_steer's own mask lookups, jump_network.mem,
            # orn_adapt.a, ...).
            action = policy.act(SimpleNamespace(ram=ram))
            info_f = policy.last_info
            mario_x = info_f["mario_x"]
            theta, dtheta, d_out = info_f["theta"], info_f["dtheta"], info_f["d_px"]
            gap_w, refusing = info_f["gap_w"], info_f["refusing"]
            qblock_hit, mario_size = info_f["qblock_hit"], info_f["mario_size"]
            hj = info_f["hj"]
            h_steer = info_f["h_steer"]
            ttmn_val, ttmn_val_dnp02 = info_f["ttmn_val"], info_f["ttmn_val_dnp02"]
            dlmn_val, dnp09_val = info_f["dlmn_val"], info_f["dnp09_val"]
            long_jump, press_a, press_b = info_f["long_jump"], info_f["press_a"], info_f["press_b"]
            r_team, l_team, direction = info_f["r_team"], info_f["l_team"], info_f["direction"]
            climb_trigger, conflict = info_f["climb_trigger"], info_f["conflict"]
            odor_l_eff, odor_r_eff, hunger = info_f["odor_l_eff"], info_f["odor_r_eff"], info_f["hunger"]
            prod_odor = info_f["prod_odor"]
            mdn_val, mdn_backing_up = info_f["mdn_val"], info_f["mdn_backing_up"]
            pathway_fired, frames_to_contact = info_f["pathway_fired"], info_f["frames_to_contact"]
            avers_l_eff, avers_r_eff, avoid_odor = (info_f["avers_l_eff"], info_f["avers_r_eff"],
                                                     info_f["avoid_odor"])
            Is = info_f["Is"]

            row = observer.new_row()
            row["frame"] = frame
            row["mario_x"] = mario_x
            row["theta"] = max(theta["L"], theta["R"])
            # sprint 023: dtheta on whichever side theta itself is dominant
            # this frame -- same side-selection convention as "theta" above,
            # not a new one -- needed to test corr(LC4_mean, dtheta) against
            # corr(LC4_mean, theta), the sprint's own decisive signature.
            row["dtheta"] = dtheta["L"] if theta["L"] >= theta["R"] else dtheta["R"]
            # sprint 023: raw signed d_px on the same dominant side, so
            # commitment distance (003/011's "d_px ~= 0") is readable
            # straight from telemetry instead of back-solved from theta.
            _dom_side = "L" if theta["L"] >= theta["R"] else "R"
            row["d_px"] = d_out[_dom_side] if d_out[_dom_side] is not None else np.nan
            row["lc4"] = hj[j_msk["LC4_all"]].mean()
            row["lplc2"] = hj[j_msk["LPLC2_all"]].mean()
            # sprint 017 overlay audit: "lc4"/"lplc2" above blend both
            # hemispheres into one number, same failure-mode class as the
            # dna01/dna02 bug -- lower stakes here since TTMn (the actual
            # jump decision) already reads max(L,R) internally, not this
            # blended mean, but a one-sided Goomba's real drive still gets
            # diluted by the quiet far side in what gets displayed/logged.
            row["lc4_l"] = hj[j_msk["LC4_L"]].mean()
            row["lc4_r"] = hj[j_msk["LC4_R"]].mean()
            row["lplc2_l"] = hj[j_msk["LPLC2_L"]].mean()
            row["lplc2_r"] = hj[j_msk["LPLC2_R"]].mean()
            row["mem"] = float(jump_network.mem.max())
            row["spike"] = bool(jump_network.just_spiked.any())
            row["ttmn"] = ttmn_val
            row["dnp09"] = dnp09_val
            row["dlmn"] = dlmn_val
            row["gap"] = gap_w
            row["long_jump"] = bool(long_jump)
            row["press_b"] = bool(press_b)
            row["dna01"] = h_steer[dna01_all].mean()
            row["dna02"] = h_steer[dna02_all].mean()
            row["r_team"] = r_team
            row["l_team"] = l_team
            row["dna01_l"] = h_steer[dna01_l_mask].mean()
            row["dna01_r"] = h_steer[dna01_r_mask].mean()
            row["dna02_l"] = h_steer[dna02_l_mask].mean()
            row["dna02_r"] = h_steer[dna02_r_mask].mean()
            row["is_r_mask_sum"] = float(Is[r_mask].sum())
            row["is_l_mask_sum"] = float(Is[l_mask].sum())
            row["press_a"] = bool(press_a)
            row["direction"] = direction
            row["climb"] = bool(climb_trigger)
            row["conflict"] = bool(conflict)
            row["odor_l"] = odor_l_eff
            row["odor_r"] = odor_r_eff
            row["hungry"] = hunger == HUNGER_MULT_HUNGRY
            row["raw_odor_l"] = prod_odor["L"]
            row["raw_odor_r"] = prod_odor["R"]
            row["orn_a_l"] = orn_adapt.a["L"]
            row["orn_a_r"] = orn_adapt.a["R"]
            row["hab_escape"] = hab_escape.hab_level
            row["hab_climb"] = hab_climb.hab_level
            row["mdn"] = float(mdn_val)
            row["mdn_backing_up"] = bool(mdn_backing_up)
            row["ttmn_dnp02"] = ttmn_val_dnp02
            row["spike_dnp02"] = bool(dnp02_network.just_spiked.any())
            row["pathway_fired"] = pathway_fired if pathway_fired else ""
            row["frames_to_contact"] = frames_to_contact if frames_to_contact is not None else np.nan
            row["avers_l"] = avers_l_eff
            row["avers_r"] = avers_r_eff
            row["avoid_odor"] = avoid_odor
            row["refusing"] = refusing
            row["qblock_hit"] = qblock_hit
            row["mario_size"] = mario_size
            observer.record(row)
            if record_video:
                Image.fromarray(obs).save(tmp / f"{frame:05d}.png")

            obs, reward, done, info = env.step(action)
            frame += 1
            # REFACTOR_PLAN.md phase 5b: the death-triggered punishment
            # update (SPEC_mushroom_body.md section 3, dynamics.CLIP routed
            # through real PPL+PPM->MBON weights, same depression-only rule
            # as reward) now lives on FullPolicy.on_step(), the ONE place
            # the mushroom body's plasticity runs -- this used to read
            # main()'s own `mb_elig` local directly, which went stale the
            # moment policy.act() started reassigning `self.mb_elig` every
            # frame instead of mutating it in place; on_step() reads
            # `self.mb_elig` fresh, so there's no staleness to have.
            policy.on_step(frame, SimpleNamespace(done=done), action)

        if owns_env:
            env.close()  # a caller-supplied env (savestate reuse across episodes) stays open
        # REFACTOR_PLAN.md phase 5b: every one of these counters is now
        # incremented inside FullPolicy.act(), not main()'s own locals
        # (which stayed frozen at their commit-2 initial 0/None once the
        # per-frame decision loop moved onto `policy` -- read fresh here).
        n_escape_jumps, n_long_jumps = policy.n_escape_jumps, policy.n_long_jumps
        n_dnp01_fired, n_dnp02_fired = policy.n_dnp01_fired, policy.n_dnp02_fired
        n_climb_hops, n_climb_jumps = policy.n_climb_hops, policy.n_climb_jumps
        n_conflicts = policy.n_conflicts
        n_odor_avoids, n_qblock_hits, n_refusals = (policy.n_odor_avoids, policy.n_qblock_hits,
                                                     policy.n_refusals)
        max_x_abs = policy.max_x_abs
        print(f"\n{frame} frames -- escape jumps={n_escape_jumps} "
              f"(of which long jumps={n_long_jumps}, DNp01={n_dnp01_fired}, DNp02={n_dnp02_fired})  "
              f"climb hops={n_climb_hops}  climb jumps={n_climb_jumps}  "
              f"conflicts={n_conflicts}  odour avoids={n_odor_avoids}  "
              f"qblock hits={n_qblock_hits}  refusal frames={n_refusals}  "
              f"ended={'died/flagged' if done else 'hit max_frames'}")

        tel = observer.to_dataframe()
        if write_telemetry:
            # sprint 017: 006-012 always wrote one of these; 016 quietly
            # didn't, and the diagnosis had to be done by OCR-ing the video
            # instead of reading real numbers. Every column in `observer` --
            # the full overlay, not a curated subset -- same
            # `{stem}_telemetry.csv` naming `runs/006_steering_telemetry.csv`
            # etc. already established. Independent of record_video: a fast,
            # headless (record_video=False) run is exactly where this
            # matters most for diagnosis.
            #
            # REFACTOR_PLAN.md phase 5: `telemetry_path`, if given, overrides
            # the colocated-with-video default -- sim/output_routing.py uses
            # this to route telemetry into projects/<name>/telemetry/,
            # separate from projects/<name>/runs/. Every existing caller
            # leaves telemetry_path unset and gets byte-identical behaviour
            # to before this parameter existed.
            csv_path = (Path(telemetry_path) if telemetry_path is not None
                        else Path(out_mp4).with_name(Path(out_mp4).stem + "_telemetry.csv"))
            observer.write(csv_path)
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
