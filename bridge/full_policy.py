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
    profiled_enemy_thetas, profiled_odor,
)
from bridge.motor import action_index
from mario.actions.actions import action_from_buttons
from bridge.controller_modules import ActContext, PerceptionContext, Proposal, Stimulus, build_modules
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
from fly.circuits.load_posture_cached import load as load_posture
from fly.circuits.load_dnp02_cached import load as load_dnp02
from fly.circuits.load_mushroom_body_cached import load as load_mushroom_body
from mario.ram import tile_ram
from mario.ram.addresses import (
    ADDR_MARIO_X, ADDR_MARIO_PAGE, ADDR_MARIO_SIZE, ADDR_PLAYER_STATE,
    ADDR_ENEMY_ACTIVE, ADDR_ENEMY_TYPE, N_ENEMY_SLOTS, POWERUP_ID,
)
from fly.plasticity.dopamine import event_dopamine
from fly.plasticity.three_factor import update_eligibility, depress, recover

log = logging.getLogger(__name__)

# Loaded circuits are memoised per process: every episode reuses them.
_circuit_cache: dict = {}


def _memo_load(key, loader, *args, **kwargs):
    if key not in _circuit_cache:
        _circuit_cache[key] = loader(*args, **kwargs)
    return _circuit_cache[key]


def _load_maybe_shuffled(key, loader, shuffle_seed, *args, **kwargs):
    """tool/PLAN.md C5, CLAUDE.md invariant 6: the real (memoised, unshuffled)
    circuit is always what's cached -- `shuffle_seed=None` returns it as-is;
    otherwise rebuilds W from the SAME bodies/edges/signs with edges rewired
    at random (`fly.connectome.circuit.build_shuffled`: same neurons, same
    in/out degree distribution, same signs). Not cached itself (CLAUDE.md:
    skip performance work absent a measured need) -- a fresh shuffle per
    FullPolicy construction, same cost class as the rest of __init__."""
    bodies, edges, total_input, signs, W, order, diag = _memo_load(key, loader, *args, **kwargs)
    if shuffle_seed is None:
        return bodies, edges, total_input, signs, W, order, diag
    from fly.connectome import circuit
    W_shuf, order_shuf, diag_shuf = circuit.build_shuffled(bodies, edges, total_input, signs,
                                                            seed=shuffle_seed)
    return bodies, edges, total_input, signs, W_shuf, order_shuf, diag_shuf


def _make_steering_masks(bodies):
    dna = bodies["type"].isin(["DNa01", "DNa02"]).to_numpy()
    r = dna & (bodies["somaSide"] == "R").to_numpy()
    l = dna & (bodies["somaSide"] == "L").to_numpy()
    return r, l


class FullPolicy:
    def __init__(self, config: ProjectConfig | None = None, level: str = "1-1",
                 retinotopic: bool = False, frame_skip: int = 1, mb_weights=None,
                 event_proximal_dopamine: bool = False, shuffle_seed: int | None = None,
                 hunger_override: bool | None = None, entity_profiles=None,
                 powerup_reward: bool = False, gap_reward: bool = False):
        """`hunger_override`: None (default) reads hunger from Mario's real
        size, as always. True/False forces hungry/sated regardless of size
        (tool/PLAN.md C7) -- a character-state control, science-change-when-
        used (CLAUDE.md rule 3), passed straight to
        `bridge.perception.hunger_multiplier`.
        `shuffle_seed`: None (default) uses the real connectome. An int
        rebuilds every circuit's weight matrix with edges rewired at random
        (same neurons, same degree distribution, same signs -- CLAUDE.md
        invariant 6, tool/PLAN.md C5) -- the control this project's own
        rule says must ship WITH a feature, not be added after.
        `event_proximal_dopamine`: False (default, what the goldens use)
        rewards any forward progress, every frame. True rewards only a `?`
        block hit or a stomp, each within the ~1-2s synaptic-tag window
        (docs/TRACE_BIOLOGY.md). Like `retinotopic`, a mode flag, not a
        scalar, so it is not in config/params.py.
        `entity_profiles`: None (default) computes looming/odour exactly
        as before this parameter existed -- `enemy_thetas`/`mushroom_odor`/
        `question_block_odor`/`goomba_odor` unchanged, untouched code path
        (docs/SPEC_entity_perception.md, C8a). A `bridge.entity_profiles.
        EntityProfiles` switches to the profiled_* functions, applying each
        kind's intensity/looming_salience/danger_weight -- a science change
        when actually given a profile that differs from
        bridge/profiles/default.json's own shipped values (CLAUDE.md
        rule 3), byte-identical to the None path when it doesn't."""
        self.config = config or ProjectConfig()
        built = build_modules(self.config)  # ordered, from config
        self.modules = [m for m in built if m.kind == "control"]
        self.perception = [m for m in built if m.kind == "perception"]
        self.motor = next((m for m in built if m.kind == "motor"), None)
        self.readout = next((m for m in built if m.kind == "readout"), None)
        self.wall_module = next((m for m in built if m.name == "wall_ahead"), None)
        self.qblock_module = next((m for m in built if m.name == "qblock_ahead"), None)
        self.level = level
        self.retinotopic = retinotopic
        self.frame_skip = frame_skip
        self.event_proximal_dopamine = event_proximal_dopamine
        # Mode flag (docs/SPEC_learning_v2.md section 4): in event-proximal mode, Mario
        # becoming Super is also an appetitive dopamine event. Off = byte-identical to before.
        self.powerup_reward = powerup_reward
        # Same idea for a pit cleared (landed safely past one Mario was approaching), A3.
        self.gap_reward = gap_reward
        self.shuffle_seed = shuffle_seed
        self.hunger_override = hunger_override
        self.entity_profiles = entity_profiles
        c = self.config
        self.rules = c.rules   # docs/CONTROL_AUDIT.md: True = the hand-coded rule is active

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
        j_bodies, _, _, _, W_j, _, _ = _load_maybe_shuffled("jump", load_jump, self.shuffle_seed, N=60)
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
        s_bodies, _, _, _, W_s, _, _ = _load_maybe_shuffled("steering", load_steering, self.shuffle_seed)
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
        t_bodies, _, _, _, W_t, _, _ = _load_maybe_shuffled("takeoff", load_takeoff, self.shuffle_seed)
        self.Kt = W_t.shape[0]
        self.takeoff_dnp01_mask = (t_bodies["type"] == "DNp01").to_numpy()
        self.dlmn_mask = t_bodies["type"].isin(["DLMn c-f", "DLMn a, b"]).to_numpy()
        self.takeoff_network = Network(
            W_t, Integrator(alpha=c.network.alpha, clip=c.network.clip), g=c.takeoff.g,
            populations={"DNp01": self.takeoff_dnp01_mask, "DLMn": self.dlmn_mask})

        log.debug("Loading the speed circuit (DNp09, N=60, cached)...")
        p_bodies, _, _, _, W_p, _, _ = _load_maybe_shuffled("speed", load_speed, self.shuffle_seed)
        self.Kp = W_p.shape[0]
        self.dnp09_mask = (p_bodies["type"] == "DNp09").to_numpy()
        self.speed_network = Network(
            W_p, Integrator(alpha=c.network.alpha, clip=c.network.clip), g=c.speed.g,
            populations={"DNp09": self.dnp09_mask})

        log.debug("Loading the MDN circuit (backward walking, N=60, cached)...")
        m_bodies, _, _, _, W_m, _, _ = _load_maybe_shuffled("mdn", load_mdn, self.shuffle_seed)
        self.Km = W_m.shape[0]
        self.mdn_mask = (m_bodies["type"] == "MDN").to_numpy()
        self.mdn_network = Network(
            W_m, Integrator(alpha=c.network.alpha, clip=c.network.clip), g=c.mdn.g,
            populations={"MDN": self.mdn_mask})

        # Down / Up muscles (docs/SPEC_learning_v3.md A7): the posture circuit, only built when MotorDirect's
        # `buttons` switch is on, so every other run is untouched.
        self.buttons_on = self.motor is not None and self.motor.params.buttons
        if self.buttons_on:
            from fly.circuits.posture_circuit import DOWN_TYPES, UP_TYPES
            pb, _, _, _, W_po, _, _ = _load_maybe_shuffled("posture", load_posture, self.shuffle_seed)
            self.Kpo = W_po.shape[0]
            self.posture_masks = {f"{t}_{s}": ((pb["type"] == t) & (pb["somaSide"] == s)).to_numpy()
                                  for t in ("LC4", "LPLC2", "LPLC1") for s in ("L", "R")}
            self.down_mask = pb["type"].isin(DOWN_TYPES).to_numpy()
            self.up_mask = pb["type"].isin(UP_TYPES).to_numpy()
            self.posture_network = Network(
                W_po, Integrator(alpha=c.network.alpha, clip=c.network.clip), g=self.motor.params.posture_g,
                populations={"down": self.down_mask, "up": self.up_mask})
        log.debug("Loading the DNp02 circuit (second escape pathway, N=60, cached)...")
        dp_bodies, _, _, _, W_dp, _, _ = _load_maybe_shuffled("dnp02", load_dnp02, self.shuffle_seed)
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

        # pC1 arousal (docs/SPEC_arousal_pc1.md): per-circuit constant currents
        # g * w * h, computed once here. `arousal_source` (set by the caller) is a
        # callable returning the slider level each frame, so it can move mid-run.
        self.arousal_module = next((m for m in built if m.name == "arousal"), None)
        self.arousal_source = None
        self.pc1_gw = None
        if self.arousal_module is not None:
            from fly.circuits.pc1_arousal_weights import load_arousal_weights
            ids = {"jump": j_bodies["bodyId"], "steering": s_bodies["bodyId"], "takeoff": t_bodies["bodyId"],
                   "speed": p_bodies["bodyId"], "mdn": m_bodies["bodyId"], "dnp02": dp_bodies["bodyId"]}
            weights = load_arousal_weights({k: v.to_numpy() for k, v in ids.items()})
            nets = {"jump": self.jump_network, "steering": self.steering_network,
                    "takeoff": self.takeoff_network, "speed": self.speed_network,
                    "mdn": self.mdn_network, "dnp02": self.dnp02_network}
            two_hop = self.arousal_module.params.two_hop
            self.pc1_gw = {}
            for name, net in nets.items():
                v = weights[name]["direct"] + (weights[name]["hop"] if two_hop else 0.0)
                if self.shuffle_seed is not None:   # invariant 6: same weights dealt to random neurons
                    v = np.random.default_rng(self.shuffle_seed).permutation(v)
                self.pc1_gw[name] = net.g * v
        for m in built:
            if m.name == "dnp02_refractory":
                self.dnp02_network.integrator.refractory_steps = m.params.refractory_steps
            elif m.name == "dnp01_refractory":
                self.jump_network.integrator.refractory_steps = m.params.refractory_steps

        log.debug("Loading the mushroom body circuit (KC/MBON/DAN, cached)...")
        mb_bodies, _, _, _, W_mb_full, _, _ = _load_maybe_shuffled("mushroom_body", load_mushroom_body, self.shuffle_seed)
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
        self.mb_mbon_body_ids = mb_bodies["bodyId"].to_numpy()[self.mb_mbon_idx]
        # Copy a passed-in `mb_weights`: depress() mutates in place, and
        # the caller's matrix must survive the episode unchanged.
        self.W_kc_mbon = (mb_weights.copy() if mb_weights is not None
                          else W_mb_full[np.ix_(self.mb_mbon_idx, self.mb_kc_idx)].copy())
        # The untrained connectome weights: what recovery (A1) relaxes a depressed synapse toward.
        self.W_kc_mbon0 = W_mb_full[np.ix_(self.mb_mbon_idx, self.mb_kc_idx)].copy()
        self.mb_pam_reach = W_mb_full[np.ix_(self.mb_mbon_idx, mb_pam_idx)].sum(axis=1)
        self.mb_punish_reach = W_mb_full[np.ix_(self.mb_mbon_idx, mb_punish_idx)].sum(axis=1)
        # N_MB_SENSORY/features-per-KC/the projection seed are "Advanced"
        # config/params.py fields (docs/CODE_AUDIT.md section H) -- an
        # architecture dimension and a seed the golden depends on
        # bit-for-bit, not a gain; golden-safe because their defaults (7,
        # 3, 0) are exactly what was hardcoded here before.
        _mb_rng = np.random.default_rng(c.mushroom_body.kc_projection_seed)
        # MbSpatialInputModule adds 2 inputs (pit-edge and enemy closeness);
        # off -> exactly the original 7, so the goldens are untouched.
        # Every perception module that feeds the KCs (mb_spatial_inputs, qblock_ahead)
        # declares N_INPUTS; none present -> exactly the original 7.
        self.mb_spatial = any(m.name == "mb_spatial_inputs" for m in built)
        self.n_mb_extra = sum(getattr(m, "N_INPUTS", 0) for m in built if m.kind == "perception")
        n_mb_sensory = c.mushroom_body.n_mb_sensory + self.n_mb_extra
        self.mb_proj = np.zeros((self.n_kc, n_mb_sensory))
        for _i in range(self.n_kc):
            _feats = _mb_rng.choice(n_mb_sensory, size=c.mushroom_body.kc_features_per_cell,
                                     replace=False)
            self.mb_proj[_i, _feats] = 1.0
        self.MBON_DNA02_FRAC = {"L": c.mushroom_body.mbon_dna02_frac_l,
                                 "R": c.mushroom_body.mbon_dna02_frac_r}
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
        self.n_powerups = 0
        self.n_gaps_cleared = 0
        self._gap_end_col = None   # far edge (tile column) of the pit Mario is approaching
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
        # MbonReadoutModule: per-pathway bias currents, computed from the
        # previous frame's MBON activity (one-frame delay, like mb_bias_dnp02).
        self.mb_pathway_bias = {g: 0.0 for g in ("dnp01", "dlmn", "dnp09", "mdn")}
        self.mb_pathway_readout = dict(self.mb_pathway_bias)
        if self.readout is not None:
            from fly.circuits.mbon_pathway_weights import load_readout_weights
            w = load_readout_weights(self.mb_mbon_body_ids)
            if self.shuffle_seed is not None:  # invariant 6: the control rewires the readout too
                rng = np.random.default_rng(self.shuffle_seed)
                w = {g: rng.permutation(v) for g, v in w.items()}
            self.readout.weights = w
        self.prev_mario_x_abs = None
        self.max_x_abs = None
        self.last_info: dict = {}
        self._prev_gap_w = 0  # docs/SPEC_pits.md: rising-edge pit-encounter logging
        self._prev_press_a = False
        for module in self.modules + self.perception + [m for m in (self.motor, self.readout) if m]:
            module.reset()

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
        distance_to_edge = tile_ram.distance_to_gap(ram, c.takeoff.gap_lookahead_tiles)
        wall_ahead = tile_ram.solid_ahead(ram)
        refusing = self.rules.refusal and gap_w > c.terrain.refusal_gap_tiles
        if refusing:
            self.n_refusals += 1
        # docs/SPEC_pits.md: log exactly what the detector sees on the rising
        # edge of a real pit encounter -- diagnostic only (log output isn't
        # telemetry), always on regardless of graded_pit_response.
        if gap_w > 0 and self._prev_gap_w == 0:
            log.debug(f"  pit detected -- mario_x={mario_x} gap_width={gap_w} tiles "
                      f"distance_to_edge={distance_to_edge}")
        self._prev_gap_w = gap_w
        # Perception modules feed the circuit stimuli; they never act.
        stim = Stimulus()
        pctx = PerceptionContext(ram=ram, mario_x=mario_x, gap_w=gap_w,
                                 distance_to_edge=distance_to_edge, config=c,
                                 registry=self.registry, profiles=self.entity_profiles)
        for module in self.perception:
            module.perceive(pctx, stim)
        gap_input = gap_w if stim.gap_input is None else stim.gap_input
        self._stim = stim

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
            if i not in now_active_enemy_slots and abs(last_x - mario_x) < c.interaction.stomp_distance_px:
                stomp = True
        if stomp:
            self.n_stomps += 1
        self._prev_enemy_slots = {i: mario_x for i in now_active_enemy_slots}

        mario_size = int(ram[ADDR_MARIO_SIZE])
        powerup = mario_size > self.prev_mario_size
        if powerup:
            self.n_powerups += 1
            log.debug(f"  Mario grew (size {self.prev_mario_size} -> {mario_size}) -- ate the mushroom")
        self.prev_mario_size = mario_size

        # ---- cleared-gap event (docs/SPEC_learning_v3.md A3) ----------
        # Remember the far edge of a pit when it first enters the lookahead; landing on the ground
        # (RAM 0x001D == 0) at or past that column is a pit cleared. Always counted, rewarded only
        # when gap_reward is on.
        col0 = (int(ram[tile_ram.ADDR_MARIO_PAGE]) * 256 + mario_x) // 16
        if self._gap_end_col is None:
            grounded = tile_ram.ground_ahead(ram, c.takeoff.gap_lookahead_tiles)
            if not all(grounded):
                self._gap_end_col = (col0 + 1 + grounded.index(False)
                                      + tile_ram.upcoming_gap_width(ram, c.takeoff.gap_lookahead_tiles))
        gap_cleared = (self._gap_end_col is not None and col0 >= self._gap_end_col
                       and int(ram[ADDR_PLAYER_STATE]) == 0)
        if gap_cleared:
            self.n_gaps_cleared += 1
            self._gap_end_col = None

        # ---- escape jump + pit-triggered graded takeoff --------------
        if self.entity_profiles is None:
            theta, dtheta, d_out = enemy_thetas(ram, mario_x, self.prev_theta, registry=self.registry,
                                                   page_aware=stim.page_aware_looming,
                                                   ignore_behind=stim.ignore_behind)
        else:
            theta, dtheta, d_out = profiled_enemy_thetas(
                ram, mario_x, self.prev_theta, registry=self.registry, profiles=self.entity_profiles,
                page_aware=stim.page_aware_looming, ignore_behind=stim.ignore_behind)
        self.prev_theta = theta
        for _side in ("L", "R"):
            if d_out[_side] is not None:
                self.d_history[_side].append(d_out[_side])
                if len(self.d_history[_side]) > c.interaction.closing_speed_history_frames:
                    self.d_history[_side].pop(0)
            else:
                self.d_history[_side].clear()
        pc1_h = self._pc1_h()
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
            Ij[self.jump_dnp01_mask] += c.takeoff.gap_gain * gap_input
        # WallAheadPerceptionModule: a wall ahead is an object in the right visual
        # field (looming) and/or a takeoff current. Zeros unless the module is on.
        Ij[self.j_msk["LC4_R"]] += abs(stim.wall_dtheta)
        Ij[self.j_msk["LPLC2_R"]] += stim.wall_theta
        Ij[self.jump_dnp01_mask] += stim.wall_takeoff
        # QBlockAheadPerceptionModule's weak looming cue: zeros unless the module is on and its
        # looming_gain > 0. A stimulus like the wall's; the circuit decides.
        Ij[self.j_msk["LC4_R"]] += abs(stim.qblock_dtheta)
        Ij[self.j_msk["LPLC2_R"]] += stim.qblock_theta
        Ij[self.jump_dnp01_mask] += self.mb_pathway_bias["dnp01"]
        if pc1_h:
            Ij += self.pc1_gw["jump"] * pc1_h

        for _ in range(self.substeps):
            hj = self.jump_network.step(Ij, noise=self.noise)
            It = np.zeros(self.Kt)
            It[self.takeoff_dnp01_mask] = hj[self.jump_dnp01_mask]
            It[self.dlmn_mask] += self.mb_pathway_bias["dlmn"]
            if pc1_h:
                It += self.pc1_gw["takeoff"] * pc1_h
            h_takeoff = self.takeoff_network.step(It, noise=self.noise)
        self.takeoff_network.flush_denormals(c.network.denormal_flush_threshold)
        ttmn_val = max(hj[self.j_msk["TTMn_L"]].mean(), hj[self.j_msk["TTMn_R"]].mean())
        dlmn_val = h_takeoff[self.dlmn_mask].mean()

        # ---- DNp02: the second escape pathway -------------------------
        self.dnp02_ema["L"] = (1 - c.dnp02.alpha) * self.dnp02_ema["L"] + c.dnp02.alpha * abs(dtheta["L"])
        self.dnp02_ema["R"] = ((1 - c.dnp02.alpha) * self.dnp02_ema["R"]
                               + c.dnp02.alpha * (abs(dtheta["R"]) + abs(stim.wall_dtheta)))
        Idp = np.zeros(self.Kdp)
        Idp[self.dnp02_lc4_l] = self.dnp02_ema["L"]; Idp[self.dnp02_lc4_r] = self.dnp02_ema["R"]
        Idp[self.dnp02_idx] += self.mb_bias_dnp02
        if pc1_h:
            Idp += self.pc1_gw["dnp02"] * pc1_h
        for _ in range(self.substeps):
            h_dnp02 = self.dnp02_network.step(Idp, noise=self.noise)
        self.dnp02_network.flush_denormals(c.network.denormal_flush_threshold)
        ttmn_val_dnp02 = max(h_dnp02[self.dnp02_ttmn_l].mean(), h_dnp02[self.dnp02_ttmn_r].mean())

        # ---- steering: home bias + odour (mushroom + ?-blocks), WTA ---
        hunger = hunger_multiplier(ram, override=self.hunger_override)
        if self.entity_profiles is None:
            mush = mushroom_odor(ram, mario_x, registry=self.registry)
            qblock = question_block_odor(ram, entity_width_px=c.entity.entity_width_px)
            food_raw = {"R": mush["R"] + qblock["R"], "L": mush["L"] + qblock["L"]}
            avers_raw = goomba_odor(ram, mario_x, registry=self.registry)
            odor_gain_eff = c.odour.odour_gain * hunger
            prod_odor = {"R": odor_gain_eff * food_raw["R"], "L": odor_gain_eff * food_raw["L"]}
        else:
            food_gated, food_ungated, avers_raw = profiled_odor(
                ram, mario_x, registry=self.registry, profiles=self.entity_profiles)
            odor_gain_eff = c.odour.odour_gain * hunger
            # food_gated * odor_gain_eff (hunger folded in, one multiply) +
            # food_ungated * odour_gain (hunger never applied) -- matches
            # the un-profiled branch's own single-multiplication structure
            # bit for bit when food_ungated is all-zero, today's shipped
            # default.json's actual shape (profiled_odor's own docstring).
            prod_odor = {"R": odor_gain_eff * food_gated["R"] + c.odour.odour_gain * food_ungated["R"],
                         "L": odor_gain_eff * food_gated["L"] + c.odour.odour_gain * food_ungated["L"]}
        adapted_odor = self.orn_adapt.apply(prod_odor)
        odor_r_eff = adapted_odor["R"]
        odor_l_eff = adapted_odor["L"]

        avers_scaled = {"R": c.odour.odour_gain * avers_raw["R"], "L": c.odour.odour_gain * avers_raw["L"]}
        avers_adapted = self.orn_adapt_avers.apply(avers_scaled)
        avers_r_eff = avers_adapted["R"]
        avers_l_eff = avers_adapted["L"]

        # ---- mushroom body: KC coding, MBON readout, dopamine ---------
        mb_sensory = np.array([theta["L"], theta["R"], odor_l_eff, odor_r_eff,
                                float(gap_w), self.mb_prev_dnp09,
                                1.0 if hunger == HUNGER_MULT_HUNGRY else 0.0]
                               + (list(stim.mb_extra) if self.n_mb_extra else []))
        mb_raw = self.mb_proj @ mb_sensory
        k_active = max(1, int(round(c.mushroom_body.kc_sparsity * self.n_kc)))
        mb_top = np.argpartition(mb_raw, -k_active)[-k_active:]
        kc_active = np.zeros(self.n_kc)
        kc_active[mb_top] = 1.0

        mbon_drive = self.W_kc_mbon @ kc_active
        self.h_mbon = ((1.0 - c.network.alpha) * self.h_mbon
                       + c.network.alpha * dynamics.phi(mbon_drive, clip=c.network.clip))
        self.h_mbon[self.h_mbon < c.network.denormal_flush_threshold] = 0.0

        mario_x_abs = int(ram[ADDR_MARIO_PAGE]) * 256 + mario_x
        progress = 0.0 if self.prev_mario_x_abs is None else max(0, mario_x_abs - self.prev_mario_x_abs)
        self.prev_mario_x_abs = mario_x_abs
        self.max_x_abs = mario_x_abs if self.max_x_abs is None else max(self.max_x_abs, mario_x_abs)

        self.mb_elig = update_eligibility(self.mb_elig, kc_active, c.mushroom_body.trace_decay)
        # See __init__ for event_proximal_dopamine; the goldens use progress.
        if self.event_proximal_dopamine:
            reward, _punish_unused = event_dopamine(qblock_hit, stomp, died=False,
                                                    powerup=powerup and self.powerup_reward,
                                                    gap_cleared=gap_cleared and self.gap_reward)
        else:
            reward = progress
        if reward > 0:
            dopamine_reward = reward * self.mb_pam_reach
            self.W_kc_mbon = depress(self.W_kc_mbon, dopamine_reward, self.mb_elig,
                                      c.mushroom_body.learning_rate)
            self.W_kc_mbon = recover(self.W_kc_mbon, self.W_kc_mbon0, dopamine_reward, self.mb_elig,
                                      c.mushroom_body.recovery_rate)

        if self.readout is not None:
            pair = self.readout.readout(self.h_mbon)
            self.mb_pathway_readout = {g: v[0] for g, v in pair.items()}
            self.mb_pathway_bias = {g: v[1] for g, v in pair.items()}
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
        if pc1_h:
            Is += self.pc1_gw["steering"] * pc1_h
        for _ in range(self.substeps):
            h_steer = self.steering_network.step(Is, noise=self.noise)
        self.steering_network.flush_denormals(c.network.denormal_flush_threshold)

        r_team = h_steer[self.r_mask].mean()
        l_team = h_steer[self.l_mask].mean()
        if r_team > l_team:
            self.direction = "R"
        elif l_team > r_team:
            self.direction = "L"

        avoid_odor = bool(self.direction == "L" and avers_r_eff > c.odour.avers_presence_gate
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

        if not self.rules.climb_stall:
            self.stall_count = 0
            self._last_x = mario_x
        elif self.jump_hold == 0 and self.climb_hold == 0:
            if self._last_x == mario_x:
                self.stall_count += 1
            else:
                self.stall_count = 0
            self._last_x = mario_x
        else:
            self.stall_count = 0
            self._last_x = mario_x

        if (self.rules.climb_reflex and self.stall_count >= self.climb_stall_frames
                and self.direction == "R" and wall_ahead
                and self.jump_hold == 0 and self.climb_hold == 0 and self.climb_cooldown == 0):
            if not self.rules.climb_habituation or self.hab_climb.check(mario_x):
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
        # Controller modules (bridge/controller_modules.py): each observes this
        # frame, then proposes cooldown bypass / forced commit / forced B.
        # No modules -> an all-False Proposal -> behaviour unchanged.
        ctx = ActContext(
            ram=ram, mario_x=mario_x, gap_w=gap_w, distance_to_edge=distance_to_edge,
            dlmn_val=dlmn_val, enemy_d_px=d_out["R"], player_state=int(ram[ADDR_PLAYER_STATE]),
            prev_press_a=self._prev_press_a, jump_hold=self.jump_hold,
            jump_cooldown=self.jump_cooldown, config=c)
        prop = Proposal()
        for module in self.modules:
            module.observe(ctx)
        for module in self.modules:
            module.propose(ctx, prop)
        if self.jump_cooldown > 0 and not prop.bypass_cooldown:
            self.jump_cooldown -= 1
        elif self.jump_hold == 0:
            dnp01_ready = ttmn_val >= c.jump.ttmn_press_threshold or prop.force_dnp01
            dnp02_ready = ttmn_val_dnp02 >= c.jump.ttmn_press_threshold
            motor_edge = self.motor is None or self.motor.rising(dnp01_ready or dnp02_ready)
            if (dnp01_ready or dnp02_ready) and motor_edge:
                if dnp01_ready and dnp02_ready:
                    pathway_fired = "DNp01" if (prop.force_dnp01 or self.jump_network.just_spiked.any()) else (
                        "DNp02" if self.dnp02_network.just_spiked.any() else "DNp01")
                else:
                    pathway_fired = "DNp01" if dnp01_ready else "DNp02"
                if not self.rules.escape_habituation or self.hab_escape.check(mario_x):
                    if self.motor is None:
                        long_jump = prop.force_long_jump or (
                            self.rules.long_jump_select and dlmn_val >= c.takeoff.dlmn_recruit_threshold)
                        if self.rules.jump_hold:
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
                    if self.motor is not None:
                        self.motor.suppressed = True
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
            Im[self.mdn_mask] += self.mb_pathway_bias["mdn"]
            if pc1_h:
                Im += self.pc1_gw["mdn"] * pc1_h
            for _ in range(self.substeps):
                h_mdn = self.mdn_network.step(Im, noise=self.noise)
            self.mdn_network.flush_denormals(c.network.denormal_flush_threshold)
            mdn_val = h_mdn[self.mdn_mask].mean()
            if self.rules.mdn_backup and mdn_val >= c.mdn.mdn_threshold:
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
        if self.motor is not None:
            motor_a = self.motor.update(
                max(ttmn_val, ttmn_val_dnp02) / c.jump.ttmn_press_threshold, dlmn_val,
                player_state=int(ram[ADDR_PLAYER_STATE]))
            press_a = press_a or motor_a
        if self.jump_hold > 0:
            self.jump_hold -= 1
            if self.jump_hold == 0 and self.rules.jump_cooldown:
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
            odor_brake = (min(c.speed.walk_drive, max(0.0, odor_l_eff + odor_r_eff - c.steering.home_bias))
                          if self.rules.odour_brake else 0.0)
            Ip[self.dnp09_mask] = (c.speed.walk_drive
                                    - (c.speed.walk_suppression if busy and self.rules.walk_suppression else 0.0)
                                    - odor_brake
                                    + self.mb_pathway_bias["dnp09"])
        if pc1_h:
            Ip += self.pc1_gw["speed"] * pc1_h
        for _ in range(self.substeps):
            h_speed = self.speed_network.step(Ip, noise=self.noise)
        self.speed_network.flush_denormals(c.network.denormal_flush_threshold)
        dnp09_val = h_speed[self.dnp09_mask].mean()
        press_b = dnp09_val >= c.speed.dnp09_speed_threshold
        # docs/SPEC_pits.md, opt-in (False leaves press_b untouched): hold a
        # run-up on approach to a real pit -- a NES running jump clears more
        # horizontal distance than a standing one, and DNp09's own decision
        # has no notion of an upcoming gap to plan around.
        if prop.force_press_b:
            press_b = True
        self.mb_prev_dnp09 = dnp09_val

        action = action_index(self.direction, press_a, press_b)
        if self.buttons_on:
            # Down / Up / Left muscles (A7): looming drives the posture DNs through their real synapses,
            # steering's left-minus-right team drives Left; each button is a MotorDirect muscle.
            Ipo = np.zeros(self.Kpo)
            for _side in ("L", "R"):
                Ipo[self.posture_masks[f"LC4_{_side}"]] = abs(dtheta[_side])
                Ipo[self.posture_masks[f"LPLC2_{_side}"]] = theta[_side]
                Ipo[self.posture_masks[f"LPLC1_{_side}"]] = theta[_side]
            for _ in range(self.substeps):
                h_po = self.posture_network.step(Ipo, noise=self.noise)
            self.posture_network.flush_denormals(c.network.denormal_flush_threshold)
            self.down_val = float(h_po[self.down_mask].mean())
            self.up_val = float(h_po[self.up_mask].mean())
            self.pressed = self.motor.update_buttons(self.down_val, self.up_val, max(0.0, l_team - r_team))
            action = action_from_buttons(right=not self.pressed["left"], left=self.pressed["left"],
                                         down=self.pressed["down"], up=self.pressed["up"],
                                         a=bool(press_a), b=bool(press_b))
        self._prev_press_a = bool(press_a)

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
        extras = {}
        if self.motor is not None:
            extras["motor_drive"] = self.motor.drive
        if self.readout is not None:
            extras.update({f"mbon_{g}": v for g, v in self.mb_pathway_readout.items()})
            extras["mbon_agg"] = float(self.h_mbon.mean())
        if self.wall_module is not None:
            extras.update({"wall_tiles": stim.wall_distance_tiles, "wall_height": stim.wall_height_tiles,
                           "wall_theta": stim.wall_theta, "wall_dtheta": stim.wall_dtheta,
                           "wall_takeoff": stim.wall_takeoff})
        if self.buttons_on:
            extras.update({"down_val": self.down_val, "up_val": self.up_val,
                           "down_drive": self.motor.button_drive["down"], "up_drive": self.motor.button_drive["up"],
                           "left_drive": self.motor.button_drive["left"], "btn_down": self.pressed["down"],
                           "btn_up": self.pressed["up"], "btn_left": self.pressed["left"]})
        if self.qblock_module is not None:
            extras.update({"qblock_tiles": stim.qblock_tiles, "qblock_height": stim.qblock_height_tiles,
                           "qblock_theta": stim.qblock_theta})
        if self.arousal_module is not None:
            extras.update(self._pc1_extras(pc1_h))
        self.last_info["extras"] = extras
        return action

    def _arousal_level(self) -> float:
        if self.arousal_module is None:
            return 0.0
        level = self.arousal_source() if self.arousal_source is not None else self.arousal_module.params.arousal
        return float(min(1.0, max(0.0, level)))

    def _pc1_h(self) -> float:
        """pC1 activity this frame (0 -> no injection anywhere, so the run is unchanged)."""
        self._arousal_now = self._arousal_level()
        return self._arousal_now * self.arousal_module.params.arousal_max_h if self.arousal_module else 0.0

    def _pc1_extras(self, h: float) -> dict:
        gw = self.pc1_gw
        return {"arousal": self._arousal_now, "pc1_h": h,
                "pc1_drive_steer_r": float(gw["steering"][self.r_mask].mean() * h),
                "pc1_drive_steer_l": float(gw["steering"][self.l_mask].mean() * h),
                "pc1_drive_dnp09": float(gw["speed"][self.dnp09_mask].mean() * h),
                "pc1_drive_gf": float(gw["jump"][self.jump_dnp01_mask].mean() * h)}

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
            self.W_kc_mbon = recover(self.W_kc_mbon, self.W_kc_mbon0, dopamine_punish, self.mb_elig,
                                      c.mushroom_body.recovery_rate)

    def on_episode_end(self, steps: int) -> None:
        pass
