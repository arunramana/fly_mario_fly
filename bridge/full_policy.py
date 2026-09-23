# What this file does, in plain English:
# The full controller, used by run_steering.py: each frame it picks Mario's
# buttons. It turns the game's memory into sights and smells, runs them
# through small networks of simulated neurons wired like the real fly
# (escape jumps, long jumps over pits, steering, walking speed, backing up, a
# learning area), adds a hop-when-stuck rule, and picks direction, jump, run.
"""bridge/full_policy.py -- the full jump/steering/terrain/mushroom-body/
habituation/MDN system as one Policy, driven by ProjectConfig. Each
`act()` call is one emulator frame; only cross-frame state (hold/cooldown
counters, prev_theta, mushroom-body weights and trace, habituation) lives
on `self`.

`_prev_avoid_odor`/`_last_x` are per-instance, reset in `reset()`
(tool/PLAN.md C10). They used to be CLASS attributes, persisting across
every episode run in one process -- harmless for `_prev_avoid_odor` (it
only gates a log line/counter), but `_last_x` fed `stall_count`, which
feeds the real climb-reflex trigger: a leftover value from a PREVIOUS
episode's last frame could equal a NEW episode's spawn `mario_x` and
falsely register a stall on frame 0. Never caught by a golden (each is a
single episode per process, and none of their specific scenarios happened
to collide), but real for any multi-episode-per-process script -- see
tool/CODEBASE_CHANGES.md's C10 entry.
"""

from __future__ import annotations

import logging

import numpy as np

from bridge.perception import (
    enemy_thetas, mushroom_odor, question_block_odor, goomba_odor,
    hunger_multiplier, HUNGER_MULT_HUNGRY,
)
from bridge.motor import action_index
from mario.entities.registry import KindRegistry
from config.project_config import ProjectConfig
from fly.network import dynamics
from fly.network.integrator import Integrator
from fly.network.network import Network
from fly.sensing.olfactory_adaptation import OlfactoryAdaptation
from fly.state.reflex_habituation import ReflexHabituation
from fly.connectome.load_cached import load as load_jump
from fly.circuits.load_steering_cached import load as load_steering
from fly.circuits.load_takeoff_cached import load as load_takeoff
from fly.circuits.load_speed_cached import load as load_speed
from fly.circuits.load_mdn_cached import load as load_mdn
from fly.circuits.load_dnp02_cached import load as load_dnp02
from fly.circuits.load_mushroom_body_cached import load as load_mushroom_body
from mario.ram import tile_ram
from mario.ram.addresses import (
    ADDR_MARIO_X, ADDR_MARIO_PAGE, ADDR_MARIO_SIZE,
    ADDR_ENEMY_ACTIVE, ADDR_ENEMY_TYPE, N_ENEMY_SLOTS, POWERUP_ID,
)
from fly.plasticity.dopamine import event_dopamine
from fly.plasticity.three_factor import update_eligibility, depress

log = logging.getLogger(__name__)

# Loaded circuits are memoised per process: every episode reuses them.
_circuit_cache: dict = {}


def _memo_load(key, loader, *args, **kwargs):
    if key not in _circuit_cache:
        _circuit_cache[key] = loader(*args, **kwargs)
    return _circuit_cache[key]


def _make_steering_masks(bodies):
    dna = bodies["type"].isin(["DNa01", "DNa02"]).to_numpy()
    r = dna & (bodies["somaSide"] == "R").to_numpy()
    l = dna & (bodies["somaSide"] == "L").to_numpy()
    return r, l


class FullPolicy:
    def __init__(self, config: ProjectConfig | None = None, level: str = "1-1",
                 retinotopic: bool = False, frame_skip: int = 1, mb_weights=None,
                 event_proximal_dopamine: bool = False):
        """`event_proximal_dopamine`: False (default, what the goldens use)
        rewards any forward progress, every frame. True rewards only a `?`
        block hit or a stomp, each within the ~1-2s synaptic-tag window
        (docs/TRACE_BIOLOGY.md). Like `retinotopic`, a mode flag, not a
        scalar, so it is not in config/params.py."""
        self.config = config or ProjectConfig()
        self.level = level
        self.retinotopic = retinotopic
        self.frame_skip = frame_skip
        self.event_proximal_dopamine = event_proximal_dopamine
        c = self.config

        self.jump_hold_frames = max(1, round(c.jump.jump_hold_frames / frame_skip))
        self.jump_cooldown_frames = max(1, round(c.jump.jump_cooldown_frames / frame_skip))
        self.long_jump_hold_frames = max(1, round(c.takeoff.long_jump_hold_frames / frame_skip))
        self.climb_hop_small_frames = max(1, round(c.steering.climb_hop_small_frames / frame_skip))
        self.climb_hop_big_frames = max(1, round(c.steering.climb_hop_big_frames / frame_skip))
        self.climb_jump_frames = max(1, round(c.steering.climb_jump_frames / frame_skip))
        self.climb_cooldown_frames = max(1, round(c.steering.climb_cooldown_frames / frame_skip))
        self.climb_stall_frames = max(1, round(c.steering.climb_stall_frames / frame_skip))
        self.mdn_backup_frames = max(1, round(c.mdn.mdn_backup_frames / frame_skip))

        log.debug("Loading the jump circuit (unchanged, cached)...")
        j_bodies, _, _, _, W_j, _, _ = _memo_load("jump", load_jump, N=60)
        self.Kj = W_j.shape[0]
        jm = lambda t, s: ((j_bodies["type"] == t) & (j_bodies["somaSide"] == s)).to_numpy()
        self.j_msk = {
            "LC4_L": jm("LC4", "L"), "LC4_R": jm("LC4", "R"),
            "LPLC2_L": jm("LPLC2", "L"), "LPLC2_R": jm("LPLC2", "R"),
            "LC4_all": (j_bodies["type"] == "LC4").to_numpy(),
            "LPLC2_all": (j_bodies["type"] == "LPLC2").to_numpy(),
            "TTMn_L": jm("TTMn", "L"), "TTMn_R": jm("TTMn", "R"),
            "DNp01_L": jm("DNp01", "L"), "DNp01_R": jm("DNp01", "R"),
        }
        self.dnp01_idx = np.concatenate([np.where(self.j_msk["DNp01_L"])[0],
                                          np.where(self.j_msk["DNp01_R"])[0]])
        self.jump_dnp01_mask = self.j_msk["DNp01_L"] | self.j_msk["DNp01_R"]
        self.jump_network = Network(
            W_j, Integrator(alpha=c.network.alpha, clip=c.network.clip,
                             spike_idx=self.dnp01_idx,
                             spike_threshold=c.jump.dnp01_spike_threshold,
                             spike_amp=c.jump.spike_amp),
            g=c.jump.g, populations=self.j_msk)

        if retinotopic:
            from fly.sensing import retinotopy as rt
            self._rt = rt
            j_rf = {"LC4": rt.receptive_field_centers(
                        "LC4", j_bodies, spread_fallback=c.retinotopy.hex1_spread_fallback,
                        spread_floor=c.retinotopy.hex1_spread_floor),
                    "LPLC2": rt.receptive_field_centers(
                        "LPLC2", j_bodies, spread_fallback=c.retinotopy.hex1_spread_fallback,
                        spread_floor=c.retinotopy.hex1_spread_floor)}
            self.j_rf = j_rf
            self.j_azimuth_ref = {}
            for t in ("LC4", "LPLC2"):
                for side in ("L", "R"):
                    m = self.j_msk[f"{t}_{side}"]
                    h1 = j_rf[t]["hex1"][m]
                    h2 = j_rf[t]["hex2"][m]
                    spread = j_rf[t]["hex1_spread"][m]
                    origin = rt.density_mode(h1, spread)
                    self.j_azimuth_ref[(t, side)] = (origin, h1.max(), float(np.median(h2)))

        log.debug("Loading the steering circuit (DNa01/DNa02, N=60, cached)...")
        s_bodies, _, _, _, W_s, _, _ = _memo_load("steering", load_steering)
        self.Ks = W_s.shape[0]
        self.r_mask, self.l_mask = _make_steering_masks(s_bodies)
        self.dna01_all = (s_bodies["type"] == "DNa01").to_numpy()
        self.dna02_all = (s_bodies["type"] == "DNa02").to_numpy()
        sm = lambda t, s: ((s_bodies["type"] == t) & (s_bodies["somaSide"] == s)).to_numpy()
        self.dna01_l_mask, self.dna01_r_mask = sm("DNa01", "L"), sm("DNa01", "R")
        self.dna02_l_mask, self.dna02_r_mask = sm("DNa02", "L"), sm("DNa02", "R")
        self.steering_network = Network(
            W_s, Integrator(alpha=c.network.alpha, clip=c.network.clip), g=c.steering.g,
            populations={"R": self.r_mask, "L": self.l_mask})

        log.debug("Loading the takeoff circuit (DNp01 -> GFC1-4 -> DLMn, cached)...")
        t_bodies, _, _, _, W_t, _, _ = _memo_load("takeoff", load_takeoff)
        self.Kt = W_t.shape[0]
        self.takeoff_dnp01_mask = (t_bodies["type"] == "DNp01").to_numpy()
        self.dlmn_mask = t_bodies["type"].isin(["DLMn c-f", "DLMn a, b"]).to_numpy()
        self.takeoff_network = Network(
            W_t, Integrator(alpha=c.network.alpha, clip=c.network.clip), g=c.takeoff.g,
            populations={"DNp01": self.takeoff_dnp01_mask, "DLMn": self.dlmn_mask})

        log.debug("Loading the speed circuit (DNp09, N=60, cached)...")
        p_bodies, _, _, _, W_p, _, _ = _memo_load("speed", load_speed)
        self.Kp = W_p.shape[0]
        self.dnp09_mask = (p_bodies["type"] == "DNp09").to_numpy()
        self.speed_network = Network(
            W_p, Integrator(alpha=c.network.alpha, clip=c.network.clip), g=c.speed.g,
            populations={"DNp09": self.dnp09_mask})

        log.debug("Loading the MDN circuit (backward walking, N=60, cached)...")
        m_bodies, _, _, _, W_m, _, _ = _memo_load("mdn", load_mdn)
        self.Km = W_m.shape[0]
        self.mdn_mask = (m_bodies["type"] == "MDN").to_numpy()
        self.mdn_network = Network(
            W_m, Integrator(alpha=c.network.alpha, clip=c.network.clip), g=c.mdn.g,
            populations={"MDN": self.mdn_mask})

        log.debug("Loading the DNp02 circuit (second escape pathway, N=60, cached)...")
        dp_bodies, _, _, _, W_dp, _, _ = _memo_load("dnp02", load_dnp02)
        self.Kdp = W_dp.shape[0]
        self.dnp02_lc4_r = ((dp_bodies["type"] == "LC4") & (dp_bodies["somaSide"] == "R")).to_numpy()
        self.dnp02_lc4_l = ((dp_bodies["type"] == "LC4") & (dp_bodies["somaSide"] == "L")).to_numpy()
        self.dnp02_l_mask = ((dp_bodies["type"] == "DNp02") & (dp_bodies["somaSide"] == "L")).to_numpy()
        self.dnp02_r_mask = ((dp_bodies["type"] == "DNp02") & (dp_bodies["somaSide"] == "R")).to_numpy()
        self.dnp02_idx = np.concatenate([np.where(self.dnp02_l_mask)[0],
                                          np.where(self.dnp02_r_mask)[0]])
        self.dnp02_ttmn_l = ((dp_bodies["type"] == "TTMn") & (dp_bodies["somaSide"] == "L")).to_numpy()
        self.dnp02_ttmn_r = ((dp_bodies["type"] == "TTMn") & (dp_bodies["somaSide"] == "R")).to_numpy()
        self.dnp02_network = Network(
            W_dp, Integrator(alpha=c.network.alpha, clip=c.network.clip,
                              spike_idx=self.dnp02_idx,
                              spike_threshold=c.dnp02.spike_threshold,
                              spike_amp=c.jump.spike_amp),
            g=c.dnp02.g,
            populations={"L": self.dnp02_l_mask, "R": self.dnp02_r_mask,
                         "TTMn_L": self.dnp02_ttmn_l, "TTMn_R": self.dnp02_ttmn_r})

        log.debug("Loading the mushroom body circuit (KC/MBON/DAN, cached)...")
        mb_bodies, _, _, _, W_mb_full, _, _ = _memo_load("mushroom_body", load_mushroom_body)
        mb_kc_mask = (mb_bodies["role"] == "KC").to_numpy()
        mb_mbon_mask = (mb_bodies["role"] == "MBON").to_numpy()
        mb_is_pam = mb_bodies["type"].astype(str).str.startswith("PAM").to_numpy()
        mb_dan_mask = (mb_bodies["role"] == "DAN").to_numpy()
        mb_pam_mask = mb_dan_mask & mb_is_pam
        mb_punish_mask = mb_dan_mask & ~mb_is_pam
        self.mb_kc_idx = np.where(mb_kc_mask)[0]
        self.mb_mbon_idx = np.where(mb_mbon_mask)[0]
        mb_pam_idx = np.where(mb_pam_mask)[0]
        mb_punish_idx = np.where(mb_punish_mask)[0]
        self.n_kc, self.n_mbon = len(self.mb_kc_idx), len(self.mb_mbon_idx)
        # Copy a passed-in `mb_weights`: depress() mutates in place, and
        # the caller's matrix must survive the episode unchanged.
        self.W_kc_mbon = (mb_weights.copy() if mb_weights is not None
                          else W_mb_full[np.ix_(self.mb_mbon_idx, self.mb_kc_idx)].copy())
        self.mb_pam_reach = W_mb_full[np.ix_(self.mb_mbon_idx, mb_pam_idx)].sum(axis=1)
        self.mb_punish_reach = W_mb_full[np.ix_(self.mb_mbon_idx, mb_punish_idx)].sum(axis=1)
        _mb_rng = np.random.default_rng(0)
        N_MB_SENSORY = 7
        self.mb_proj = np.zeros((self.n_kc, N_MB_SENSORY))
        for _i in range(self.n_kc):
            _feats = _mb_rng.choice(N_MB_SENSORY, size=3, replace=False)
            self.mb_proj[_i, _feats] = 1.0
        self.MBON_DNA02_FRAC = {"L": 0.00379, "R": 0.00632}
        self.substeps = c.network.substeps
        self.registry = KindRegistry(entity_width_px=c.entity.entity_width_px)

        self.reset(seed=0)

    def reset(self, seed: int) -> None:
        rng = np.random.default_rng(seed)
        self.noise = dynamics.NoiseConfig(self.config.noise.sigma, rng)
        self.prev_theta = {"L": 0.0, "R": 0.0}
        self.d_history = {"L": [], "R": []}
        self.dnp02_ema = {"L": 0.0, "R": 0.0}
        self.jump_hold = self.jump_cooldown = 0
        self.climb_hold = self.climb_cooldown = 0
        self.climb_attempts = 0
        self.last_reset_x = None
        self.stall_count = 0
        self.direction = "R"
        self._prev_avoid_odor = False
        self._last_x = None
        self.prev_qblock_cols = set()
        self.prev_mario_size = None
        self.n_escape_jumps = self.n_climb_hops = self.n_climb_jumps = self.n_conflicts = 0
        self.n_long_jumps = 0
        self.n_dnp01_fired = self.n_dnp02_fired = 0
        self.n_qblock_hits = self.n_odor_avoids = self.n_refusals = 0
        self.n_stomps = 0
        self._prev_enemy_slots: dict[int, int] = {}  # slot -> mario_x, for the stomp proxy
        self.orn_adapt = OlfactoryAdaptation()
        self.orn_adapt_avers = OlfactoryAdaptation()
        self.hab_escape = ReflexHabituation(give_up=self.config.habituation.hab_give_up,
                                             progress_px=self.config.habituation.hab_progress_px)
        self.hab_climb = ReflexHabituation(give_up=self.config.habituation.hab_give_up,
                                            progress_px=self.config.habituation.hab_progress_px)
        self.mdn_backup_hold = 0
        self.mb_elig = np.zeros(self.n_kc)
        self.mb_prev_dnp09 = 0.0
        self.mb_bias_dnp02 = 0.0
        self.h_mbon = np.zeros(self.n_mbon)
        self.prev_mario_x_abs = None
        self.max_x_abs = None
        self.last_info: dict = {}

    def act(self, observation) -> int:
        c = self.config
        ram = observation.ram
        mario_x = int(ram[ADDR_MARIO_X])
        if self.last_reset_x is None:
            self.last_reset_x = mario_x
        if self.prev_mario_size is None:
            self.prev_mario_size = int(ram[ADDR_MARIO_SIZE])

        # ---- terrain sensing: SPEC_terrain.md section 1 --------------
        gap_w = tile_ram.gap_width(ram, c.takeoff.gap_lookahead_tiles)
        wall_ahead = tile_ram.solid_ahead(ram)
        refusing = gap_w > c.terrain.refusal_gap_tiles
        if refusing:
            self.n_refusals += 1

        cur_qblock_cols = {
            (int(ram[tile_ram.ADDR_MARIO_PAGE]) * 256 + mario_x) // 16 + off
            for off in tile_ram.question_blocks_near(ram)
        }
        qblock_hit = bool(self.prev_qblock_cols - cur_qblock_cols)
        if qblock_hit:
            self.n_qblock_hits += 1
            log.debug(f"  '?' block hit (column(s) "
                      f"{sorted(self.prev_qblock_cols - cur_qblock_cols)} emptied)")
        self.prev_qblock_cols = cur_qblock_cols

        # ---- stomp detection ------------------------------------------
        # An active non-powerup slot within 20px of Mario last frame and
        # gone this frame is a stomp; despawns happen far off-screen. Stomp
        # frames don't cluster at death frames, so this is not counting
        # Mario's own fatal collision (docs/RUNS.md, phase 5b correction).
        now_active_enemy_slots = {
            i for i in range(N_ENEMY_SLOTS)
            if ram[ADDR_ENEMY_ACTIVE + i] != 0 and ram[ADDR_ENEMY_TYPE + i] != POWERUP_ID
        }
        stomp = False
        for i, last_x in self._prev_enemy_slots.items():
            if i not in now_active_enemy_slots and abs(last_x - mario_x) < 20:
                stomp = True
        if stomp:
            self.n_stomps += 1
        self._prev_enemy_slots = {i: mario_x for i in now_active_enemy_slots}

        mario_size = int(ram[ADDR_MARIO_SIZE])
        if mario_size > self.prev_mario_size:
            log.debug(f"  Mario grew (size {self.prev_mario_size} -> {mario_size}) -- ate the mushroom")
        self.prev_mario_size = mario_size

        # ---- escape jump + pit-triggered graded takeoff --------------
        theta, dtheta, d_out = enemy_thetas(ram, mario_x, self.prev_theta, registry=self.registry)
        self.prev_theta = theta
        for _side in ("L", "R"):
            if d_out[_side] is not None:
                self.d_history[_side].append(d_out[_side])
                if len(self.d_history[_side]) > 10:
                    self.d_history[_side].pop(0)
            else:
                self.d_history[_side].clear()
        Ij = np.zeros(self.Kj)
        if self.retinotopic:
            rt = self._rt
            for _side in ("L", "R"):
                if d_out[_side] is None:
                    continue
                for t, mag in (("LC4", abs(dtheta[_side])), ("LPLC2", theta[_side])):
                    if mag == 0.0:
                        continue
                    origin, far, _ = self.j_azimuth_ref[(t, _side)]
                    az1 = rt.azimuth_target(d_out[_side], origin, far, d_ref=c.retinotopy.azimuth_d_ref)
                    w = rt.tuning_weights(az1, self.j_rf[t])
                    Ij[self.j_msk[f"{t}_{_side}"]] = mag * w[self.j_msk[f"{t}_{_side}"]]
        else:
            Ij[self.j_msk["LC4_L"]] = abs(dtheta["L"]); Ij[self.j_msk["LPLC2_L"]] = theta["L"]
            Ij[self.j_msk["LC4_R"]] = abs(dtheta["R"]); Ij[self.j_msk["LPLC2_R"]] = theta["R"]
        if not refusing:
            Ij[self.jump_dnp01_mask] += c.takeoff.gap_gain * gap_w

        for _ in range(self.substeps):
            hj = self.jump_network.step(Ij, noise=self.noise)
            It = np.zeros(self.Kt)
            It[self.takeoff_dnp01_mask] = hj[self.jump_dnp01_mask]
            h_takeoff = self.takeoff_network.step(It, noise=self.noise)
        self.takeoff_network.flush_denormals()
        ttmn_val = max(hj[self.j_msk["TTMn_L"]].mean(), hj[self.j_msk["TTMn_R"]].mean())
        dlmn_val = h_takeoff[self.dlmn_mask].mean()

        # ---- DNp02: the second escape pathway -------------------------
        self.dnp02_ema["L"] = (1 - c.dnp02.alpha) * self.dnp02_ema["L"] + c.dnp02.alpha * abs(dtheta["L"])
        self.dnp02_ema["R"] = (1 - c.dnp02.alpha) * self.dnp02_ema["R"] + c.dnp02.alpha * abs(dtheta["R"])
        Idp = np.zeros(self.Kdp)
        Idp[self.dnp02_lc4_l] = self.dnp02_ema["L"]; Idp[self.dnp02_lc4_r] = self.dnp02_ema["R"]
        Idp[self.dnp02_idx] += self.mb_bias_dnp02
        for _ in range(self.substeps):
            h_dnp02 = self.dnp02_network.step(Idp, noise=self.noise)
        self.dnp02_network.flush_denormals()
        ttmn_val_dnp02 = max(h_dnp02[self.dnp02_ttmn_l].mean(), h_dnp02[self.dnp02_ttmn_r].mean())

        # ---- steering: home bias + odour (mushroom + ?-blocks), WTA ---
        mush = mushroom_odor(ram, mario_x, registry=self.registry)
        qblock = question_block_odor(ram)
        hunger = hunger_multiplier(ram)
        odor_gain_eff = c.odour.odour_gain * hunger
        prod_odor = {"R": odor_gain_eff * (mush["R"] + qblock["R"]),
                     "L": odor_gain_eff * (mush["L"] + qblock["L"])}
        adapted_odor = self.orn_adapt.apply(prod_odor)
        odor_r_eff = adapted_odor["R"]
        odor_l_eff = adapted_odor["L"]

        avers_raw = goomba_odor(ram, mario_x, registry=self.registry)
        avers_scaled = {"R": c.odour.odour_gain * avers_raw["R"], "L": c.odour.odour_gain * avers_raw["L"]}
        avers_adapted = self.orn_adapt_avers.apply(avers_scaled)
        avers_r_eff = avers_adapted["R"]
        avers_l_eff = avers_adapted["L"]

        # ---- mushroom body: KC coding, MBON readout, dopamine ---------
        mb_sensory = np.array([theta["L"], theta["R"], odor_l_eff, odor_r_eff,
                                float(gap_w), self.mb_prev_dnp09,
                                1.0 if hunger == HUNGER_MULT_HUNGRY else 0.0])
        mb_raw = self.mb_proj @ mb_sensory
        k_active = max(1, int(round(c.mushroom_body.kc_sparsity * self.n_kc)))
        mb_top = np.argpartition(mb_raw, -k_active)[-k_active:]
        kc_active = np.zeros(self.n_kc)
        kc_active[mb_top] = 1.0

        mbon_drive = self.W_kc_mbon @ kc_active
        self.h_mbon = ((1.0 - c.network.alpha) * self.h_mbon
                       + c.network.alpha * dynamics.phi(mbon_drive, clip=c.network.clip))
        self.h_mbon[self.h_mbon < 1e-30] = 0.0

        mario_x_abs = int(ram[ADDR_MARIO_PAGE]) * 256 + mario_x
        progress = 0.0 if self.prev_mario_x_abs is None else max(0, mario_x_abs - self.prev_mario_x_abs)
        self.prev_mario_x_abs = mario_x_abs
        self.max_x_abs = mario_x_abs if self.max_x_abs is None else max(self.max_x_abs, mario_x_abs)

        self.mb_elig = update_eligibility(self.mb_elig, kc_active, c.mushroom_body.trace_decay)
        # See __init__ for event_proximal_dopamine; the goldens use progress.
        if self.event_proximal_dopamine:
            reward, _punish_unused = event_dopamine(qblock_hit, stomp, died=False)
        else:
            reward = progress
        if reward > 0:
            dopamine_reward = reward * self.mb_pam_reach
            self.W_kc_mbon = depress(self.W_kc_mbon, dopamine_reward, self.mb_elig,
                                      c.mushroom_body.learning_rate)

        mbon_agg = float(self.h_mbon.mean())
        mb_bias_r = -self.MBON_DNA02_FRAC["R"] * mbon_agg
        mb_bias_l = -self.MBON_DNA02_FRAC["L"] * mbon_agg
        self.mb_bias_dnp02 = -self.MBON_DNA02_FRAC["R"] * mbon_agg

        Is = np.zeros(self.Ks)
        Is[self.r_mask] = c.steering.home_bias + odor_r_eff + avers_l_eff
        Is[self.l_mask] = odor_l_eff + avers_r_eff
        if refusing:
            Is[self.l_mask] += c.takeoff.gap_gain * gap_w
        Is[self.dna02_all & self.r_mask] += mb_bias_r
        Is[self.dna02_all & self.l_mask] += mb_bias_l
        for _ in range(self.substeps):
            h_steer = self.steering_network.step(Is, noise=self.noise)
        self.steering_network.flush_denormals()

        r_team = h_steer[self.r_mask].mean()
        l_team = h_steer[self.l_mask].mean()
        if r_team > l_team:
            self.direction = "R"
        elif l_team > r_team:
            self.direction = "L"

        avoid_odor = bool(self.direction == "L" and avers_r_eff > 1e-6
                           and avers_r_eff >= odor_l_eff and not refusing)
        if avoid_odor and not self._prev_avoid_odor:
            self.n_odor_avoids += 1
            log.debug(f"  aversive odour steers AWAY (L) -- avers_r_eff={avers_r_eff:.3f} "
                      f"theta_R={theta['R']:.3f} d_px={d_out['R']}")
        self._prev_avoid_odor = avoid_odor

        # ---- contact-based climbing ------------------------------------
        climb_trigger = False
        if mario_x - self.last_reset_x >= c.steering.climb_clear_distance:
            self.climb_attempts = 0
            self.last_reset_x = mario_x

        if self.jump_hold == 0 and self.climb_hold == 0:
            if self._last_x == mario_x:
                self.stall_count += 1
            else:
                self.stall_count = 0
            self._last_x = mario_x
        else:
            self.stall_count = 0
            self._last_x = mario_x

        if (self.stall_count >= self.climb_stall_frames and self.direction == "R" and wall_ahead
                and self.jump_hold == 0 and self.climb_hold == 0 and self.climb_cooldown == 0):
            if self.hab_climb.check(mario_x):
                if self.climb_attempts == 0:
                    hold = self.climb_hop_small_frames if mario_size == 0 else self.climb_hop_big_frames
                    self.climb_attempts = 1
                    self.n_climb_hops += 1
                else:
                    hold = self.climb_jump_frames
                    self.climb_attempts = 2
                    self.n_climb_jumps += 1
                self.climb_hold = hold
                climb_trigger = True
                log.debug(f"  blocked-forward -> climb {'hop' if hold != self.climb_jump_frames else 'jump'} "
                          f"(hold={hold}, mario_size={mario_size})")
            else:
                log.debug(f"  climb HABITUATED (level={self.hab_climb.hab_level}) -- suppressed")
            self.stall_count = 0

        # ---- escape-jump trigger: DNp01 vs DNp02, COMPETE not sum ------
        escape_trigger = False
        long_jump = False
        pathway_fired = None
        frames_to_contact = None
        if self.jump_cooldown > 0:
            self.jump_cooldown -= 1
        elif self.jump_hold == 0:
            dnp01_ready = ttmn_val >= c.jump.ttmn_press_threshold
            dnp02_ready = ttmn_val_dnp02 >= c.jump.ttmn_press_threshold
            if dnp01_ready or dnp02_ready:
                if dnp01_ready and dnp02_ready:
                    pathway_fired = "DNp01" if self.jump_network.just_spiked.any() else (
                        "DNp02" if self.dnp02_network.just_spiked.any() else "DNp01")
                else:
                    pathway_fired = "DNp01" if dnp01_ready else "DNp02"
                if self.hab_escape.check(mario_x):
                    long_jump = dlmn_val >= c.takeoff.dlmn_recruit_threshold
                    self.jump_hold = self.long_jump_hold_frames if long_jump else self.jump_hold_frames
                    escape_trigger = True
                    self.n_escape_jumps += 1
                    if pathway_fired == "DNp01":
                        self.n_dnp01_fired += 1
                        self.dnp02_network.h[:] = 0.0; self.dnp02_network.mem[:] = 0.0
                    else:
                        self.n_dnp02_fired += 1
                        self.jump_network.h[:] = 0.0; self.jump_network.mem[:] = 0.0
                    side = "R" if theta["R"] >= theta["L"] else "L"
                    hist = self.d_history[side]
                    closing_px_per_frame = ((hist[0] - hist[-1]) / (len(hist) - 1)
                                             if len(hist) >= 2 else None)
                    frames_to_contact = (abs(d_out[side]) / closing_px_per_frame
                                          if (closing_px_per_frame and closing_px_per_frame > 0
                                              and d_out[side] is not None) else None)
                    ftc_str = f"{frames_to_contact:.1f}" if frames_to_contact is not None else "?"
                    log.debug(f"  {pathway_fired} commits -- theta={theta[side]:.3f} "
                              f"d_px={d_out[side]} est_frames_to_contact={ftc_str}")
                    if long_jump:
                        self.n_long_jumps += 1
                        log.debug(f"  gap_width={gap_w} DLMn={dlmn_val:.2f} >= "
                                  f"{c.takeoff.dlmn_recruit_threshold} -> LONG JUMP (hold={self.jump_hold})")
                else:
                    log.debug(f"  escape HABITUATED (level={self.hab_escape.hab_level}) -- suppressed")

        conflict = escape_trigger and (climb_trigger or self.climb_hold > 0)
        if climb_trigger and (self.jump_hold > 0 or escape_trigger):
            conflict = True
        if conflict:
            self.n_conflicts += 1
            log.debug("  CONFLICT -- escape and climb both want A")

        # ---- MDN: the escape-failed fallback ---------------------------
        if self.mdn_backup_hold == 0:
            Im = np.zeros(self.Km)
            Im[self.mdn_mask] = c.mdn.mdn_drive if self.hab_escape.hab_level >= self.hab_escape.give_up else 0.0
            for _ in range(self.substeps):
                h_mdn = self.mdn_network.step(Im, noise=self.noise)
            self.mdn_network.flush_denormals()
            mdn_val = h_mdn[self.mdn_mask].mean()
            if mdn_val >= c.mdn.mdn_threshold:
                self.mdn_backup_hold = self.mdn_backup_frames
                log.debug(f"  escape habituated -> MDN takes over, backing up (hold={self.mdn_backup_frames})")
        else:
            mdn_val = self.mdn_network.h[self.mdn_mask].mean()

        mdn_backing_up = self.mdn_backup_hold > 0
        if mdn_backing_up:
            self.direction = "L"
            self.mdn_backup_hold -= 1
            if self.mdn_backup_hold == 0:
                self.hab_escape.reset()

        # ---- resolve one shared A button -------------------------------
        press_a = self.jump_hold > 0 or self.climb_hold > 0
        if self.jump_hold > 0:
            self.jump_hold -= 1
            if self.jump_hold == 0:
                self.jump_cooldown = self.jump_cooldown_frames
        if self.climb_hold > 0:
            self.climb_hold -= 1
            if self.climb_hold == 0:
                self.climb_cooldown = self.climb_cooldown_frames
        if self.climb_cooldown > 0 and self.climb_hold == 0:
            self.climb_cooldown -= 1

        # ---- speed: DNp09 -----------------------------------------------
        busy = press_a or self.stall_count > 0
        Ip = np.zeros(self.Kp)
        if refusing:
            Ip[self.dnp09_mask] = 0.0
        else:
            odor_brake = min(c.speed.walk_drive, max(0.0, odor_l_eff + odor_r_eff - c.steering.home_bias))
            Ip[self.dnp09_mask] = (c.speed.walk_drive
                                    - (c.speed.walk_suppression if busy else 0.0) - odor_brake)
        for _ in range(self.substeps):
            h_speed = self.speed_network.step(Ip, noise=self.noise)
        self.speed_network.flush_denormals()
        dnp09_val = h_speed[self.dnp09_mask].mean()
        press_b = dnp09_val >= c.speed.dnp09_speed_threshold
        self.mb_prev_dnp09 = dnp09_val

        action = action_index(self.direction, press_a, press_b)

        # Read by the telemetry row and by on_step()'s death punishment.
        self.last_info = dict(
            mario_x=mario_x, theta=theta, dtheta=dtheta, d_px=d_out, gap_w=gap_w,
            hj=hj, h_takeoff=h_takeoff, h_dnp02=h_dnp02, h_steer=h_steer,
            ttmn_val=ttmn_val, dnp09_val=dnp09_val, dlmn_val=dlmn_val,
            long_jump=long_jump, press_b=press_b, r_team=r_team, l_team=l_team,
            Is=Is, press_a=press_a, direction=self.direction, climb_trigger=climb_trigger,
            conflict=conflict, odor_l_eff=odor_l_eff, odor_r_eff=odor_r_eff, hunger=hunger,
            prod_odor=prod_odor, hab_escape_level=self.hab_escape.hab_level,
            hab_climb_level=self.hab_climb.hab_level, mdn_val=mdn_val,
            mdn_backing_up=mdn_backing_up, ttmn_val_dnp02=ttmn_val_dnp02,
            pathway_fired=pathway_fired, frames_to_contact=frames_to_contact,
            avers_l_eff=avers_l_eff, avers_r_eff=avers_r_eff, avoid_odor=avoid_odor,
            refusing=refusing, qblock_hit=qblock_hit, stomp=stomp, mario_size=mario_size,
            max_x_abs=self.max_x_abs,
        )
        return action

    def on_step(self, step: int, observation, action) -> None:
        """FullPolicy is also registered as an Episode observer, so it sees
        the result of its own action: on death, apply the mushroom-body
        punishment."""
        if getattr(observation, "done", False):
            c = self.config
            _pam_unused, punish_magnitude = event_dopamine(qblock_hit=False, stomp=False, died=True)
            dopamine_punish = punish_magnitude * self.mb_punish_reach
            self.W_kc_mbon = depress(self.W_kc_mbon, dopamine_punish, self.mb_elig,
                                      c.mushroom_body.learning_rate)

    def on_episode_end(self, steps: int) -> None:
        pass
