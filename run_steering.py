# What this file does, in plain English:
# The script that plays the game with the full simulated fly brain. Its
# main() runs one game: each frame the fly-brain decision-maker in
# bridge/full_policy.py picks the buttons; the script can plant test objects
# in the game's memory (a fake mushroom, a fake wide pit), logs 54 values
# per frame to a CSV file (telemetry) and can render a video. It returns the
# log and a summary such as jump counts and the learned brain weights.
# Given 008, 016, 023 or 024 on the command line, it re-runs that past run.
"""
run_steering.py -- SPEC_steering.md: DNa01/DNa02 steering under a constant
home bias, competing with a mushroom-odour signal read from RAM, plus a
contact-based climbing reflex. SPEC_terrain.md adds two more layers on top:
a pit-triggered graded long jump (DNp01's own output recruiting DLMn via
the real GFC1-4 relay) and a DNp09 speed circuit that finally lets Mario
stop holding B unconditionally. The circuits and the per-frame decision
live in bridge/full_policy.py; this module drives the emulator, the
test-harness injections and telemetry.

    .venv/Scripts/python.exe run_steering.py 008|016|023|024   # reproduce a run
    run_steering.main(out_mp4=...)                             # from Python
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import logging
import tempfile
from pathlib import Path
from types import SimpleNamespace

import setuptools  # noqa: F401  -- must import before gym on py3.12
import numpy as np
from PIL import Image

from sim.telemetry import TelemetryObserver
from mario.ram import tile_ram
from mario.ram.addresses import (
    ADDR_MARIO_X, ADDR_MARIO_Y, ADDR_MARIO_SIZE,
    ADDR_ENEMY_X, ADDR_ENEMY_Y, ADDR_ENEMY_ACTIVE, ADDR_ENEMY_TYPE,
    N_ENEMY_SLOTS, POWERUP_ID,
)
from mario.actions.actions import action_index
from mario.emulator.env import make_env
from bridge.perception import HUNGER_MULT_HUNGRY
from config.params import (
    Dnp02Params, MdnParams, MushroomBodyParams, OdourParams, SpeedParams,
    SteeringParams, TakeoffParams, TerrainParams, DemoParams,
)
from config.project_config import ScenarioParams

from render.video import _ensure_ffmpeg_on_path
from config.logging_setup import ensure_logging, setup_logging

log = logging.getLogger(__name__)

# Every scalar below is sourced from config/params.py (docs/SCALARS.md has
# the value, category and provenance of each). The jump scalars stay in
# run_mario.py; FullPolicy reads them from JumpParams.

# ---- SPEC_odour.md section 0 ---------------------------------------------
# Odour and HOME_BIAS are competing direction signals in different units;
# ODOUR_GAIN puts them on one scale. HOME_BIAS itself is not lowered -- that
# would make Mario permanently distractible.
_odour_params = OdourParams()
ODOUR_GAIN = _odour_params.odour_gain

# ORN adaptation (fly/sensing/olfactory_adaptation.py) is receptor
# physiology, applied inside the sensory layer to the gain- and
# hunger-scaled signal: adapting the raw ~0.04 concentration would do
# nothing. It also stops a place Mario has lingered near from smelling,
# letting the unadapted HOME_BIAS take back over.

# ---- SPEC_steering.md section 5 ------------------------------------------
_steering_params = SteeringParams()
G_STEER = _steering_params.g                              # tune_steering.py
HOME_BIAS = _steering_params.home_bias                     # constant "go home" current, R-hemisphere only
CLIMB_STALL_FRAMES = _steering_params.climb_stall_frames   # mario_x unchanged this long while steering=R -> blocked
CLIMB_HOP_SMALL_FRAMES = _steering_params.climb_hop_small_frames  # small Mario's first-try hop hold
CLIMB_HOP_BIG_FRAMES = _steering_params.climb_hop_big_frames      # big/fiery Mario's first-try hop hold (taller hitbox)
CLIMB_JUMP_FRAMES = _steering_params.climb_jump_frames     # escalated full jump hold, same magnitude as the escape jump
CLIMB_COOLDOWN_FRAMES = _steering_params.climb_cooldown_frames
CLIMB_CLEAR_DISTANCE = _steering_params.climb_clear_distance  # px of forward progress that resets the attempt counter

# ---- SPEC_terrain.md sections 2-3 ----------------------------------------
# DLMn's end-of-frame mean grows monotonically with gap width (~0.28 at one
# tile, ~1.18 at two); DLMN_RECRUIT_THRESHOLD sits between those, so a
# one-tile gap gets a normal hop and anything wider gets the long jump.
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

# ---- SPEC_habituation.md -------------------------------------------------
# Giant Fiber habituation: a reflex that fires without HAB_PROGRESS_PX of
# net x-progress raises its own habituation level. HAB_PROGRESS_PX and
# HAB_GIVE_UP live with ReflexHabituation in fly/state/reflex_habituation.py.

# MDN (backward walking) gets no direct synapse from DNp01/GFC1-4 in this
# connectome, so its drive is a placed external current, like
# HOME_BIAS/WALK_DRIVE/GAP_GAIN. Backing up is a discrete corrective action,
# hence the fixed MDN_BACKUP_FRAMES hold.
_mdn_params = MdnParams()
G_MDN = _mdn_params.g
MDN_DRIVE = _mdn_params.mdn_drive
MDN_THRESHOLD = _mdn_params.mdn_threshold
MDN_BACKUP_FRAMES = _mdn_params.mdn_backup_frames

# ---- DNp02, the second escape pathway (docs/RUNS.md 012) -----------------
# DNp02 is a real, direct, ipsilateral second path to TTMn, driven by
# essentially all of LC4 (4209 synapses) and almost no LPLC2 (5). Without
# expansion input it cannot tell a slow approach from a fast one, so it
# essentially never beats DNp01 to commitment -- a connectome result, not a
# tuning failure (docs/RUNS.md 012). Its "longer integration" is a slow EMA
# on the input current: a slower alpha on the whole step would also slow
# TTMn's decay and fire it on stale state.
_dnp02_params = Dnp02Params()
G_DNP02 = _dnp02_params.g
DNP02_SPIKE_THRESHOLD = _dnp02_params.spike_threshold
DNP02_ALPHA = _dnp02_params.alpha

# ---- SPEC_mushroom_body.md -----------------------------------------------
# 4,064 KC, 97 MBON, 354 dopaminergic neurons (PAM/PPL/PPM) in this
# connectome. KC_SPARSITY matches the fly's ~5% active-KC fraction, enforced
# by top-k rather than by simulating the APL inhibitory neuron. At
# LEARNING_RATE, one full-magnitude punishment (dopamine=CLIP) depresses an
# eligible synapse by 5%.
_mb_params = MushroomBodyParams()
KC_SPARSITY = _mb_params.kc_sparsity
TRACE_DECAY = _mb_params.trace_decay
LEARNING_RATE = _mb_params.learning_rate

# ---- SPEC_odour.md sprint 016: aversive odour, DNp09 brake, refusal -------
# The anatomy says no: this connectome has no innate olfactory path onto
# DNa01/DNa02 (3 lateral-horn synapses out of 76,248 inputs; the 259
# olfactory-adjacent ones are almost all MBON31/32, the learned pathway) and
# none at all onto DNp09. So every odour channel is a placed external
# current onto DNa01/DNa02/DNp09, the same category as HOME_BIAS/GAP_GAIN,
# and each reuses an already-calibrated gain rather than a new one: the
# aversive channel reuses ODOUR_GAIN (no hunger term), the DNp09 brake reuses
# the steering WTA's own odour signal, and the refusal push reuses GAP_GAIN.
# REFUSAL_GAP_TILES is the first gap width past the range the long jump was
# validated on (0-4 tiles).
REFUSAL_GAP_TILES = TerrainParams().refusal_gap_tiles

# 8-way action space: {left,right} x {A on/off} x {B on/off}
# (mario/actions/actions.py).

MUSHROOM_OFFSET = DemoParams().mushroom_offset  # spawn BEHIND Mario so it competes with HOME_BIAS's rightward pull
WIDE_GAP_LEAD_TILES = DemoParams().wide_gap_lead_tiles
REFUSAL_GAP_MARGIN_TILES = TerrainParams().refusal_gap_margin_tiles


def find_inactive_slot(ram):
    for i in range(N_ENEMY_SLOTS):
        if ram[ADDR_ENEMY_ACTIVE + i] == 0:
            return i
    return None


def inject_mushroom(ram, mario_x, mario_y, offset=None):
    """SPEC_steering.md section 2: a synthetic odour source for the demo, poked
    straight into the enemy-slot arrays. The game never populates its
    collision state, so Mario cannot actually eat it. `offset` overrides
    MUSHROOM_OFFSET (behind Mario, so it competes with HOME_BIAS); a
    positive offset places it ahead."""
    off = MUSHROOM_OFFSET if offset is None else offset
    slot = find_inactive_slot(ram)
    if slot is None:
        log.debug("  (no free enemy slot to inject the mushroom into -- skipped)")
        return False
    x = max(int(mario_x) + off, 0)
    ram[ADDR_ENEMY_ACTIVE + slot] = 1
    ram[ADDR_ENEMY_TYPE + slot] = POWERUP_ID
    ram[ADDR_ENEMY_X + slot] = x & 0xFF
    ram[ADDR_ENEMY_Y + slot] = int(mario_y)
    log.debug(f"  injected synthetic mushroom into slot {slot} at x={x} (mario_x={mario_x}, "
              f"i.e. {off:+d}px -- {'ahead, reachable' if off > 0 else 'behind, competes with HOME_BIAS'})")
    return True


def wide_gap_target_col(ram, mario_x, lead_tiles=WIDE_GAP_LEAD_TILES) -> int:
    """Pick the FIXED absolute tile-column the synthetic gap will live at,
    once, at the moment of injection -- `lead_tiles` ahead of Mario's
    column at that instant. Callers must hold onto this value and pass it
    back into `poke_wide_gap` every frame; recomputing "N tiles ahead of
    Mario" fresh each frame would make the gap a moving window Mario can
    never actually reach, not a fixed obstacle."""
    col0 = (int(ram[tile_ram.ADDR_MARIO_PAGE]) * 256 + int(mario_x)) // 16
    return col0 + lead_tiles


def poke_wide_gap(ram, target_col: int, width_tiles=REFUSAL_GAP_TILES + REFUSAL_GAP_MARGIN_TILES):
    """A synthetic wide pit for the refusal demo: 1-1's real pits are only
    2 tiles, well under REFUSAL_GAP_TILES. Pokes the collision-tile buffer
    that tile_ram.py decodes. Must be called every frame at the same
    `target_col` (from `wide_gap_target_col`, called once): the game's
    level streaming can overwrite a not-yet-drawn column before Mario
    arrives."""
    for k in range(width_tiles):
        col = target_col + k
        buf_addr = tile_ram.BUF1_ADDR if (col // 16) % 2 == 0 else tile_ram.BUF2_ADDR
        ram[buf_addr + tile_ram.GROUND_ROW * 16 + (col % 16)] = tile_ram.EMPTY_ID


def policy_extra_columns(policy) -> tuple:
    """Telemetry columns that exist only when an optional module is on, so
    runs without it stay byte-identical to the goldens."""
    cols = []
    if getattr(policy, "motor", None) is not None:
        cols.append("motor_drive")
    if getattr(policy, "readout", None) is not None:
        cols += [f"mbon_{g}" for g in policy.readout.PATHWAYS]
    return tuple(cols)


def main(out_mp4=None, level="1-1", max_frames=ScenarioParams().max_frames,
         force_mario_size=None, force_size_from_frame=None, record_video=True,
         inject_frame=None, frame_skip=1, savestate=None, mb_weights=None,
         mushroom_offset=None, inject_gap_frame=None, write_telemetry=True,
         retinotopic=False, sigma=0.0, seed=None, telemetry_path=None,
         event_proximal_dopamine=False, config=None, on_frame=None, should_stop=None,
         shuffle_seed=None, hunger_override=None, entity_profiles=None,
         death_animation_frames=0):
    """Run one episode of the full system and return (telemetry, info).

    out_mp4: required. Build it from a ProjectConfig with
        config.output_routing.resolve_run_path, or use
        sim.project_runner.run_from_config.
    telemetry_path: overrides the CSV location, which otherwise sits next
        to out_mp4 as `<stem>_telemetry.csv`.
    record_video: False skips frame capture and the brain panel, for a
        fast telemetry-only run.
    mb_weights: the KC->MBON matrix from a previous episode, the one piece
        of state that persists across training. None starts from the
        connectome's weights. The updated matrix is returned in
        info["mb_weights"].
    frame_skip: decide once every `frame_skip` frames and repeat the
        buttons in between (SPEC_throughput.md). Circuit dynamics are
        unchanged; the mechanical hold durations are divided by frame_skip.
    savestate: dict with an optional "env" (reused and left open) and
        "warmup_frames" (run once, then backed up with nes-py's _backup);
        every reset then restores that state instead of power-on.
    inject_frame: opt-in only. Places a synthetic mushroom odour source at
        this frame; None never does, so a clean baseline can't carry it.
    mushroom_offset: overrides MUSHROOM_OFFSET for that injection.
    inject_gap_frame: opt-in only. From this frame, holds a synthetic wide
        pit at a fixed column ahead of Mario, to exercise the refusal rule.
    force_mario_size: pokes Mario's size (small=0, big=1) from
        force_size_from_frame onward. Forcing it from frame 0 would change
        his hitbox against every earlier Goomba too, so the start frame
        must be explicit when inject_frame is None.
    retinotopic: per-cell LC4/LPLC2 drive from receptive fields
        (fly/sensing/retinotopy.py). Closed negative result (docs/RUNS.md
        023-024); keep False.
    sigma, seed: membrane noise eta ~ N(0, sigma) on every neuron. sigma=0
        draws nothing and is bit-identical to no noise. seed=None draws an
        OS-entropy seed and prints it; both are returned in info.
    event_proximal_dopamine: False (the goldens' setting) rewards any
        forward progress; True fires PAM dopamine only on a `?`-block hit
        or a stomp (docs/TRACE_BIOLOGY.md).
    config: a ProjectConfig to build FullPolicy from (its 49 circuit
        scalars, not just the scenario). None (default) builds a fresh
        default ProjectConfig, today's behaviour. sigma always overrides
        whatever config.noise.sigma was, same as with the default config
        -- a caller that wants config's own sigma to win passes
        sigma=config.noise.sigma explicitly (sim.project_runner.
        run_from_config already does).
    on_frame: called as on_frame(frame, obs, row) once per emulator frame
        (obs is the RGB frame the decision this row records was made from;
        row is the same dict written to telemetry), right before env.step
        advances to the next one. None (default): never called, no cost.
        For a live preview -- raises inside it propagate, same as any
        other caller error.
    should_stop: called with no arguments once per emulator frame, right
        after on_frame; a true return ends the episode early (frame count
        and telemetry reflect wherever it stopped, same as reaching
        max_frames). None (default): never called, the episode always
        runs to death or max_frames. For a Cancel button.
    shuffle_seed: None (default) uses the real connectome. An int rebuilds
        every circuit's weight matrix with edges rewired at random -- same
        neurons, same in/out degree distribution, same signs (CLAUDE.md
        invariant 6's control).
    hunger_override: None (default) reads hunger from Mario's real size, as
        always. True/False forces hungry/sated regardless of size -- a
        science change when actually used (CLAUDE.md rule 3), not just a
        display choice.
    entity_profiles: None (default) computes looming/odour exactly as
        before this parameter existed (docs/SPEC_entity_perception.md,
        C8a). A bridge.entity_profiles.EntityProfiles applies each kind's
        intensity/looming_salience/danger_weight -- a science change when
        it differs from bridge/profiles/default.json's shipped values.
    death_animation_frames: 0 (default): unchanged behaviour, the episode
        ends the instant `done` is True, as always. On a real death or
        flag (not a Cancel, not hitting max_frames), a positive value
        steps this many EXTRA emulator frames afterward, calling on_frame
        for each so a recording/live preview shows the NES's own death
        animation -- excluded from telemetry (observer.record is never
        called for them) and from fitness (`info`/`frame`/`tel` all still
        reflect the real end of the episode, not the extension)."""
    if out_mp4 is None:
        raise ValueError(
            "main() needs an explicit out_mp4 -- there is no default any "
            "more (REFACTOR_PLAN.md phase 5: a run without a named project "
            "must fail loudly, not silently write to a stray top-level "
            "runs/008_run.mp4). Pass out_mp4 directly, or route it through "
            "a ProjectConfig via config.output_routing.resolve_run_path() / "
            "sim.project_runner.run_from_config()."
        )
    ensure_logging(Path(out_mp4).stem)
    if seed is None:
        seed = int(np.random.SeedSequence().entropy % (2**32))
    if sigma > 0.0:
        log.info(f"sprint 025: seed={seed} sigma={sigma}")
    if force_mario_size is not None and force_size_from_frame is None:
        assert inject_frame is not None, (
            "force_mario_size needs an explicit force_size_from_frame when "
            "inject_frame is None -- there's no longer an injection frame "
            "to silently default to.")
        force_size_from_frame = inject_frame

    # FullPolicy owns the circuits and all per-episode decision state; main()
    # only drives the emulator, the test-harness injections and telemetry.
    from bridge.full_policy import FullPolicy
    import dataclasses as _dataclasses
    from config.project_config import ProjectConfig as _ProjectConfig
    _pc = config if config is not None else _ProjectConfig()
    _pc = _dataclasses.replace(_pc, noise=_dataclasses.replace(_pc.noise, sigma=sigma))
    policy = FullPolicy(config=_pc, level=level, retinotopic=retinotopic,
                         frame_skip=frame_skip, mb_weights=mb_weights,
                         event_proximal_dopamine=event_proximal_dopamine,
                         shuffle_seed=shuffle_seed, hunger_override=hunger_override,
                         entity_profiles=entity_profiles)
    policy.reset(seed)

    # Live sub-objects and masks the telemetry row reads.
    j_msk, jump_network = policy.j_msk, policy.jump_network
    r_mask, l_mask = policy.r_mask, policy.l_mask
    dna01_all, dna02_all = policy.dna01_all, policy.dna02_all
    dna01_l_mask, dna01_r_mask = policy.dna01_l_mask, policy.dna01_r_mask
    dna02_l_mask, dna02_r_mask = policy.dna02_l_mask, policy.dna02_r_mask
    orn_adapt = policy.orn_adapt
    hab_escape, hab_climb = policy.hab_escape, policy.hab_climb
    dnp02_network = policy.dnp02_network
    W_kc_mbon = policy.W_kc_mbon

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

    injected = False
    gap_target_col = None       # fixed once, on inject_gap_frame

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # Column order is the CSV's column order; the goldens depend on it.
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
        ) + policy_extra_columns(policy))

        frame = 0
        done = False
        info = {}  # gym's per-step info dict, in case max_frames=0 skips the loop entirely
        while frame < max_frames and not done:
            # ---- frame skip: repeat the last decision, no new circuit work -
            # Frame 0 always decides, so `action` exists here. The repeated
            # telemetry row keeps the video 1:1 with the brain panel.
            if frame_skip > 1 and frame % frame_skip != 0:
                mario_x = int(ram[ADDR_MARIO_X])
                row = dict(observer.last_row) if observer.last_row is not None else observer.new_row()
                row["frame"] = frame
                row["mario_x"] = mario_x
                observer.record(row)
                # mario_y set AFTER record(): TelemetryObserver.to_dataframe()
                # only ever reads its own fixed `columns` list, so this never
                # becomes a CSV column -- it's here purely for on_frame's
                # Luigi-recolour box (tool/core/palette.py).
                row["mario_y"] = int(ram[ADDR_MARIO_Y])
                if record_video:
                    Image.fromarray(obs).save(tmp / f"{frame:05d}.png")
                if on_frame is not None:
                    on_frame(frame, obs, row)
                obs, reward, done, info = env.step(action)
                frame += 1
                if should_stop is not None and should_stop():
                    break
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
                    gap_target_col = wide_gap_target_col(ram, mario_x, lead_tiles=_pc.demo.wide_gap_lead_tiles)
                    log.debug(f"  frame {frame}: sprint-016 synthetic wide gap poked at "
                              f"abs_col={gap_target_col} (mario_x={mario_x})")
                poke_wide_gap(ram, gap_target_col,
                              width_tiles=_pc.terrain.refusal_gap_tiles + _pc.terrain.refusal_gap_margin_tiles)

            # ---- decision: FullPolicy.act(); read back what telemetry needs -
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
            # dtheta and d_px come from the same dominant side as theta.
            row["dtheta"] = dtheta["L"] if theta["L"] >= theta["R"] else dtheta["R"]
            _dom_side = "L" if theta["L"] >= theta["R"] else "R"
            row["d_px"] = d_out[_dom_side] if d_out[_dom_side] is not None else np.nan
            row["lc4"] = hj[j_msk["LC4_all"]].mean()
            row["lplc2"] = hj[j_msk["LPLC2_all"]].mean()
            # "lc4"/"lplc2" blend both hemispheres and dilute a one-sided
            # threat; the per-side columns show it undiluted.
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
            row.update(info_f["extras"])
            observer.record(row)
            row["mario_y"] = mario_y  # after record() -- see the frame-skip branch's own comment
            if record_video:
                Image.fromarray(obs).save(tmp / f"{frame:05d}.png")
            if on_frame is not None:
                on_frame(frame, obs, row)

            obs, reward, done, info = env.step(action)
            frame += 1
            # Death-triggered punishment (SPEC_mushroom_body.md section 3).
            policy.on_step(frame, SimpleNamespace(done=done), action)
            if should_stop is not None and should_stop():
                break

        # Display-only death animation (ease-of-use redesign): `done` means
        # a real death or flag, never a Cancel (should_stop breaks the loop
        # without setting it) and never hitting max_frames. Reuses the last
        # real action -- the NES ignores input during this animation
        # regardless, so what's sent doesn't matter. Nothing here touches
        # `frame`, `info`, `observer`, or `tel`: fitness and telemetry see
        # the episode end exactly where it really did.
        if done and death_animation_frames > 0 and on_frame is not None:
            death_row = dict(row)
            for i in range(death_animation_frames):
                if should_stop is not None and should_stop():
                    break
                # nes-py's own NESEnv.step() (not a Gym wrapper -- checked
                # directly) refuses to step past the `done` it just
                # returned ("cannot step in a done environment! call
                # `reset`"), on the reasonable assumption every caller
                # wants a fresh episode next. We want the OPPOSITE here --
                # the death animation is the SAME episode's own emulator
                # state continuing to run -- so this clears just that one
                # instance flag before every extra step; `env.reset()` is
                # never called, so no new episode starts.
                env.unwrapped.done = False
                obs, _, _, _ = env.step(action)
                death_row["frame"] = frame + i  # `frame` is already one past the last recorded row
                on_frame(frame + i, obs, death_row)

        if owns_env:
            env.close()  # a caller-supplied env (savestate reuse across episodes) stays open
        n_escape_jumps, n_long_jumps = policy.n_escape_jumps, policy.n_long_jumps
        n_dnp01_fired, n_dnp02_fired = policy.n_dnp01_fired, policy.n_dnp02_fired
        n_climb_hops, n_climb_jumps = policy.n_climb_hops, policy.n_climb_jumps
        n_conflicts = policy.n_conflicts
        n_odor_avoids, n_qblock_hits, n_refusals = (policy.n_odor_avoids, policy.n_qblock_hits,
                                                     policy.n_refusals)
        n_stomps = policy.n_stomps
        max_x_abs = policy.max_x_abs
        log.info(f"\n{frame} frames -- escape jumps={n_escape_jumps} "
                 f"(of which long jumps={n_long_jumps}, DNp01={n_dnp01_fired}, DNp02={n_dnp02_fired})  "
                 f"climb hops={n_climb_hops}  climb jumps={n_climb_jumps}  "
                 f"conflicts={n_conflicts}  odour avoids={n_odor_avoids}  "
                 f"qblock hits={n_qblock_hits}  stomps={n_stomps}  refusal frames={n_refusals}  "
                 f"ended={'died/flagged' if done else 'hit max_frames'}")

        tel = observer.to_dataframe()
        if write_telemetry:
            # Written whether or not video is recorded: the CSV, not the
            # video, is the durable record of a run.
            csv_path = (Path(telemetry_path) if telemetry_path is not None
                        else Path(out_mp4).with_name(Path(out_mp4).stem + "_telemetry.csv"))
            observer.write(csv_path)
        if record_video:
            _ensure_ffmpeg_on_path()
            from render import brain_panel
            brain_panel.render_run(tel, tmp, out_mp4,
                                    caption=f"{level}: aversive+attractive odour, DNp09 brake, "
                                            "refusal rule, DNp01 vs DNp02, pit->DLMn long jump, "
                                            "DNa01/DNa02 steering, contact climb")
    return tel, dict(n_escape_jumps=n_escape_jumps, n_long_jumps=n_long_jumps,
                      n_dnp01_fired=n_dnp01_fired, n_dnp02_fired=n_dnp02_fired,
                      n_climb_hops=n_climb_hops, n_climb_jumps=n_climb_jumps,
                      n_conflicts=n_conflicts, n_frames=frame, died_or_flagged=done,
                      n_odor_avoids=n_odor_avoids, n_qblock_hits=n_qblock_hits,
                      n_stomps=n_stomps, n_refusals=n_refusals,
                      mb_weights=W_kc_mbon, max_x_abs=max_x_abs,
                      seed=seed, sigma=sigma,
                      score=info.get("score"), coins=info.get("coins"),
                      time=info.get("time"), flag_get=info.get("flag_get"))


LEVEL_RUNS = [
    ("1-1", "runs/008a_1-1.mp4"),
    ("1-2", "runs/008b_1-2.mp4"),
    ("1-3", "runs/008c_1-3.mp4"),
]


def run_008():
    """Reproduce run 008: does the long jump generalise across 1-1/1-2/1-3."""
    from sim.pit_report import find_pit_events, summarize, print_table

    log.info("=" * 70)
    log.info("SPEC_odour.md section 3: pit generalisation across 1-1/1-2/1-3")
    log.info("=" * 70)
    all_rows = {}
    for level, out_mp4 in LEVEL_RUNS:
        log.info(f"\n--- {level} -> {out_mp4} ---")
        tel, info = main(out_mp4=out_mp4, level=level, max_frames=2500, inject_frame=60)
        events = find_pit_events(tel)
        rows = summarize(tel, events, info["died_or_flagged"], info["n_frames"])
        print_table(level, rows)
        all_rows[level] = (rows, info)
    return all_rows


def run_016(out_mp4="runs/016_smell.mp4", max_frames=1500,
            mushroom_frame=None, mushroom_offset=50, gap_frame=600,
            record_video=True):
    """Reproduce run 016: avoid a Goomba, hit a `?` block, eat the mushroom,
    refuse a (synthetic) wide pit, all in one 1-1 run."""
    tel, info = main(out_mp4=out_mp4, level="1-1", max_frames=max_frames,
                      record_video=record_video,
                      inject_frame=mushroom_frame, mushroom_offset=mushroom_offset,
                      inject_gap_frame=gap_frame)

    log.info("\n" + "=" * 70)
    log.info("sprint 016: four-event report")
    log.info("=" * 70)

    avoid_frames = tel.index[tel["avoid_odor"] & ~tel["avoid_odor"].shift(1, fill_value=False)]
    if len(avoid_frames):
        log.info(f"1. avoids a Goomba (odour): frame {int(tel['frame'].iloc[avoid_frames[0]])} "
                 f"(and {len(avoid_frames) - 1} more time(s) later in the run)")
    else:
        log.info("1. avoids a Goomba (odour): DID NOT HAPPEN this run")

    qb_frames = tel.loc[tel["qblock_hit"], "frame"]
    if len(qb_frames):
        log.info(f"2. hits a real '?' block: frame {int(qb_frames.iloc[0])}")
    else:
        log.info("2. hits a real '?' block: DID NOT HAPPEN this run")

    grew = tel.index[tel["mario_size"] > tel["mario_size"].shift(1, fill_value=tel["mario_size"].iloc[0])]
    if len(grew):
        log.info(f"3. eats the mushroom: frame {int(tel['frame'].iloc[grew[0]])}")
    else:
        log.info("3. eats the mushroom: DID NOT HAPPEN this run")

    refuse_frames = tel.index[tel["refusing"] & ~tel["refusing"].shift(1, fill_value=False)]
    if len(refuse_frames):
        log.info(f"4. refuses a wide pit: frame {int(tel['frame'].iloc[refuse_frames[0]])}")
    else:
        log.info("4. refuses a wide pit: DID NOT HAPPEN this run")

    log.info(f"\n{info['n_frames']} frames, "
             f"{'died/flagged' if info['died_or_flagged'] else 'hit max_frames'}, "
             f"max_x_abs={info['max_x_abs']}")
    return tel, info


def run_023(max_frames=1500, gap_frame=600):
    """Reproduce run 023: paired retinotopic=False/True comparison on 1-1."""
    from sim.commitment_report import report

    log.info("=" * 70)
    log.info("sprint 023: retinotopy paired comparison, level 1-1")
    log.info("=" * 70)

    log.info("\n[before] retinotopic=False (uniform theta/dtheta broadcast)...")
    tel_before, info_before = main(
        out_mp4="runs/023_retinotopy_before.mp4", level="1-1",
        max_frames=max_frames, record_video=False,
        inject_gap_frame=gap_frame, retinotopic=False)

    log.info("\n[after] retinotopic=True (per-cell receptive-field weighting)...")
    tel_after, info_after = main(
        out_mp4="runs/023_retinotopy.mp4", level="1-1",
        max_frames=max_frames, record_video=True,
        inject_gap_frame=gap_frame, retinotopic=True)

    before = report(tel_before, "BEFORE (retinotopic=False)")
    after = report(tel_after, "AFTER (retinotopic=True)")

    log.info("\n" + "=" * 70)
    log.info("sprint 023: verdict")
    log.info("=" * 70)
    if before["median_frames_to_contact"] is not None and after["median_frames_to_contact"] is not None:
        log.info(f"median frames_to_contact at commit: {before['median_frames_to_contact']:.2f} -> "
                 f"{after['median_frames_to_contact']:.2f} "
                 f"({'EARLIER' if after['median_frames_to_contact'] > before['median_frames_to_contact'] else 'not earlier'})")
    c_before = before["corr"]; c_after = after["corr"]
    log.info(f"corr(LC4,theta) before={c_before['corr_lc4_theta']:.4f} after={c_after['corr_lc4_theta']:.4f}")
    log.info(f"corr(LC4,dtheta) before={c_before['corr_lc4_dtheta']:.4f} after={c_after['corr_lc4_dtheta']:.4f}")
    flipped = (c_after["corr_lc4_dtheta"] > c_after["corr_lc4_theta"]) and \
              not (c_before["corr_lc4_dtheta"] > c_before["corr_lc4_theta"])
    log.info(f"velocity-tuning signature (dtheta corr now exceeds theta corr, "
             f"and didn't before): {flipped}")

    return dict(tel_before=tel_before, tel_after=tel_after,
                info_before=info_before, info_after=info_after,
                before=before, after=after)


def run_024(max_frames=1500, gap_frame=600):
    """Reproduce run 024: retinotopy with the fovea at the RF density mode,
    against its three pre-registered criteria."""
    from sim.commitment_report import report

    log.info("=" * 70)
    log.info("sprint 024: retinotopy, fovea-at-density-mode, second and final attempt")
    log.info("=" * 70)

    log.info("\n[before] retinotopic=False (identical to 017/023's own baseline)...")
    tel_before, info_before = main(
        out_mp4="runs/024_retinotopy_fovea_before.mp4", level="1-1",
        max_frames=max_frames, record_video=False,
        inject_gap_frame=gap_frame, retinotopic=False)

    log.info("\n[after] retinotopic=True, origin=density_mode()...")
    tel_after, info_after = main(
        out_mp4="runs/024_retinotopy_fovea.mp4", level="1-1",
        max_frames=max_frames, record_video=True,
        inject_gap_frame=gap_frame, retinotopic=True)

    before = report(tel_before, "BEFORE (retinotopic=False)")
    after = report(tel_after, "AFTER (retinotopic=True, fovea=density_mode)")

    log.info("\n" + "=" * 70)
    log.info("sprint 024: verdict against the three pre-registered criteria")
    log.info("=" * 70)
    if before["median_frames_to_contact"] is not None and after["median_frames_to_contact"] is not None:
        log.info(f"(1) median frames_to_contact at commit: {before['median_frames_to_contact']:.2f} -> "
                 f"{after['median_frames_to_contact']:.2f} "
                 f"({'EARLIER than 017 baseline' if after['median_frames_to_contact'] > 32 else 'not earlier than 017 baseline (32)'})")
    else:
        log.info("(1) frames_to_contact: no commitments in one or both runs -- see (3)")
    c_after = after["corr"]
    for pop in ("lc4", "lplc2"):
        exceeds = c_after[f"corr_{pop}_dtheta"] > c_after[f"corr_{pop}_theta"]
        log.info(f"(2) {pop.upper()}: corr(theta)={c_after[f'corr_{pop}_theta']:.4f}  "
                 f"corr(dtheta)={c_after[f'corr_{pop}_dtheta']:.4f}  "
                 f"velocity exceeds size: {exceeds}")
    log.info(f"(3) commitments: before={len(before['events'])} (baseline=10)  "
             f"after={len(after['events'])}  "
             f"survival: before={'died' if info_before['died_or_flagged'] else 'survived'} "
             f"({info_before['n_frames']} frames)  "
             f"after={'died' if info_after['died_or_flagged'] else 'survived'} ({info_after['n_frames']} frames)")

    return dict(tel_before=tel_before, tel_after=tel_after,
                info_before=info_before, info_after=info_after,
                before=before, after=after)


if __name__ == "__main__":
    import sys
    setup_logging(f"run_steering_{sys.argv[1]}" if len(sys.argv) > 1 else "run_steering")
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
