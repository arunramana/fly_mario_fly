# What this file does, in plain English:
# Checks the "learning v3" pieces that live outside the tool (docs/SPEC_learning_v3.md):
# synapses that can recover toward their untrained strength (so a reward or
# punishment now moves weights both down and up), the cleared-pit reward, the
# gap-width and speed inputs, the fix for receding enemies driving the jump
# circuit, the muscle adaptation that stops A being held by a limit cycle, and
# the full 64-combination button space with its Down / Up / Left muscles.
"""Learning v3: recovery + sign test, cleared gap, MB gap/speed inputs, TTMn plateau fixes, all buttons."""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import numpy as np

from bridge.controller_modules import (MbGapSpeedInputModule, MotorDirectModule, PerceptionContext, Stimulus)
from bridge.full_policy import FullPolicy
from bridge.perception import enemy_thetas
from config.params import (MbGapSpeedInputParams, ModulesConfig, MotorDirectParams, PagePerceptionParams)
from config.project_config import ProjectConfig
from fly.network import dynamics
from fly.plasticity.dopamine import event_dopamine
from fly.plasticity.three_factor import depress, recover
from mario.actions.actions import BUTTONS, MOVES, MOVES_ALL, action_from_buttons, action_index, buttons_of
from mario.entities.kinds import EntityKind
from mario.ram import tile_ram
from mario.ram.addresses import ADDR_MARIO_XSPEED, ADDR_MARIO_X, ADDR_PLAYER_STATE
from sim.fitness import FitnessWeights, compute_fitness


# ---- A1: recovery + the new sign test ------------------------------------------------

def test_recover_moves_a_depressed_synapse_up_toward_baseline_and_never_past_it():
    W0 = np.ones((1, 3))
    W = np.array([[0.5, 0.5, 1.0]])
    elig = np.array([0.0, 1.0, 0.0])                    # KC 0 silent, KC 1 active, KC 2 silent but intact
    out = recover(W.copy(), W0, np.array([50.0]), elig, recovery_rate=0.001)
    assert out[0, 0] > 0.5 and out[0, 0] <= 1.0          # silent + depressed: recovers
    assert out[0, 1] == 0.5                              # active KC: no recovery
    assert out[0, 2] == 1.0                              # already at baseline: never above it
    assert np.array_equal(recover(W.copy(), W0, np.array([50.0]), elig, 0.0), W)   # rate 0 = off
    huge = recover(W.copy(), W0, np.array([50.0]), elig, recovery_rate=10.0)
    assert huge[0, 0] == 1.0                             # the step is clamped at the baseline


def test_sign_test_with_recovery_reward_and_punishment_move_weights_both_ways():
    """Same rule the live circuit calls. Two KC groups: A was active before (so depressed by an
    earlier pulse), B was not. A new pulse while only B is active depresses B (eligible) and lets
    the depressed A recover -- weights move down AND up -- and reward vs punishment do so on
    different MBONs."""
    rng = np.random.default_rng(0)
    n_mbon, n_kc = 12, 40
    W0 = rng.random((n_mbon, n_kc)) + 0.5
    group_a = np.arange(n_kc) < 20
    lr, rr = 0.001, 0.0005
    W = W0.copy()
    depress(W, np.full(n_mbon, dynamics.CLIP), group_a.astype(float), lr)          # earlier pulse: A depressed
    assert (W[:, group_a] < W0[:, group_a]).all()
    reach_pam = np.array([1.0] * 6 + [0.1] * 6)
    reach_ppl = reach_pam[::-1].copy()
    elig_b = (~group_a).astype(float)
    results = {}
    for name, d in (("reward", dynamics.CLIP * reach_pam), ("punish", dynamics.CLIP * reach_ppl)):
        W1 = W.copy()
        depress(W1, d, elig_b, lr)
        recover(W1, W0, d, elig_b, rr)
        results[name] = W1 - W
        assert (W1[:, group_a] >= W[:, group_a]).all() and (W1[:, group_a] > W[:, group_a]).any()   # up
        assert (W1[:, ~group_a] <= W[:, ~group_a]).all() and (W1[:, ~group_a] < W[:, ~group_a]).any()  # down
        assert (W1 <= W0 + 1e-12).all()                                            # never above baseline
    # reward acts mostly on the first six MBONs, punishment on the last six, in BOTH directions
    for sign_group in (group_a, ~group_a):
        r, p = results["reward"][:, sign_group], results["punish"][:, sign_group]
        assert abs(r[:6]).sum() > abs(p[:6]).sum() and abs(p[6:]).sum() > abs(r[6:]).sum()


# ---- A2: gap width + speed ----------------------------------------------------------

def _ram(mario_x=0, pit_cols=()):
    ram = np.zeros(0x800, dtype=np.uint8)
    ram[ADDR_MARIO_X] = mario_x
    for col in range(16):
        if col not in pit_cols:
            ram[tile_ram.BUF1_ADDR + tile_ram.GROUND_ROW * 16 + col] = tile_ram.GROUND_ID
    return ram


def test_mb_gap_speed_inputs_read_pit_width_and_signed_speed():
    m = MbGapSpeedInputModule(MbGapSpeedInputParams(perceive_tiles=8))
    ram = _ram(pit_cols=(4, 5))
    ram[ADDR_MARIO_XSPEED] = 0xD8                       # -40 as a signed byte: full speed leftward
    s = Stimulus()
    m.perceive(PerceptionContext(ram=ram, mario_x=0, gap_w=0, distance_to_edge=None, config=ProjectConfig()), s)
    assert s.mb_extra == (2 / 8, 1.0)
    ram[ADDR_MARIO_XSPEED] = 0
    s = Stimulus()
    m.perceive(PerceptionContext(ram=_ram(), mario_x=0, gap_w=0, distance_to_edge=None, config=ProjectConfig()), s)
    assert s.mb_extra == (0.0, 0.0)
    cfg = dataclasses.replace(ProjectConfig(), modules=ModulesConfig(mb_gap_speed_inputs=MbGapSpeedInputParams()))
    assert FullPolicy(config=cfg).mb_proj.shape[1] == 9


# ---- A3: cleared gap ----------------------------------------------------------------

def test_event_and_fitness_for_a_cleared_gap():
    assert event_dopamine(False, False, False, gap_cleared=True) == (dynamics.CLIP, 0.0)
    assert event_dopamine(True, False, False, gap_cleared=True) == (dynamics.CLIP, 0.0)   # never adds up
    assert compute_fitness(FitnessWeights(gap=7.0), distance=10, gaps=2) == 24.0
    assert compute_fitness(FitnessWeights(), distance=10, gaps=2) == 10.0


def _cross_a_pit(gap_reward: bool):
    policy = FullPolicy(config=ProjectConfig(), level="1-1", event_proximal_dopamine=True, gap_reward=gap_reward)
    policy.reset(seed=0)
    ram = _ram(mario_x=8, pit_cols=(4, 5))              # a 2-tile pit 4 tiles ahead of column 0
    ram[ADDR_PLAYER_STATE] = 0
    policy.act(SimpleNamespace(ram=ram))                # sees the pit approaching: remembers its far edge
    assert policy._gap_end_col == 6 and policy.n_gaps_cleared == 0
    w_before = policy.W_kc_mbon.copy()
    ram[ADDR_MARIO_X] = 6 * 16                          # ... lands on the ground at the far edge
    policy.act(SimpleNamespace(ram=ram))
    return policy, w_before


def test_landing_past_a_pit_is_counted_and_rewarded_only_when_switched_on():
    on, w_on = _cross_a_pit(True)
    assert on.n_gaps_cleared == 1 and on._gap_end_col is None
    assert not np.array_equal(on.W_kc_mbon, w_on)
    off, w_off = _cross_a_pit(False)
    assert off.n_gaps_cleared == 1 and np.array_equal(off.W_kc_mbon, w_off)     # counted, no dopamine


def test_being_in_the_air_past_the_pit_is_not_a_landing():
    policy = FullPolicy(config=ProjectConfig(), level="1-1", event_proximal_dopamine=True, gap_reward=True)
    policy.reset(seed=0)
    ram = _ram(mario_x=8, pit_cols=(4, 5))
    policy.act(SimpleNamespace(ram=ram))
    ram[ADDR_MARIO_X], ram[ADDR_PLAYER_STATE] = 6 * 16, 1     # jumping
    policy.act(SimpleNamespace(ram=ram))
    assert policy.n_gaps_cleared == 0


# ---- A4: TTMn plateau ---------------------------------------------------------------

class _Reg:
    def __init__(self, recs):
        self.recs = recs

    def enemy_records(self, ram):
        return self.recs


def test_ignore_behind_silences_a_receding_enemy_but_not_one_ahead():
    rec = lambda x: SimpleNamespace(active=True, kind=EntityKind.GOOMBA, x=x, width=16)   # noqa: E731
    behind = enemy_thetas(np.zeros(0x800, np.uint8), 100, {"L": 0, "R": 0}, registry=_Reg([rec(60)]))
    assert behind[0]["L"] > 0                            # today: |d| gives a left-hemisphere looming
    quiet = enemy_thetas(np.zeros(0x800, np.uint8), 100, {"L": 0, "R": 0}, registry=_Reg([rec(60)]),
                         ignore_behind=True)
    assert quiet[0] == {"L": 0.0, "R": 0.0} and quiet[2] == {"L": None, "R": None}
    ahead = enemy_thetas(np.zeros(0x800, np.uint8), 100, {"L": 0, "R": 0}, registry=_Reg([rec(140)]),
                         ignore_behind=True)
    assert ahead[0]["R"] > 0
    from bridge.controller_modules import PagePerceptionModule
    s = Stimulus()
    PagePerceptionModule(PagePerceptionParams(ignore_behind=True)).perceive(
        PerceptionContext(ram=None, mario_x=0, gap_w=0, distance_to_edge=None, config=ProjectConfig()), s)
    assert s.ignore_behind and not Stimulus().ignore_behind


def _peak_drive(adapt_frames: float) -> float:
    """MotorDirect fed learn_1's plateau: TTMn cycling 4.1 -> 8.3 -> 17.0 (ratios / 3.0)."""
    m = MotorDirectModule(MotorDirectParams(a_threshold=4.0, decay=0.7, ttmn_gain=1.0, dlmn_gain=0.0,
                                            release_on_landing=False, adapt_frames=adapt_frames))
    peak = 0.0
    for i in range(150):
        m.update([4.09, 8.33, 17.0][i % 3] / 3.0, 0.0)
        if i > 100:
            peak = max(peak, m.drive)
    return peak


def test_muscle_adaptation_stops_a_sustained_cycle_from_holding_a_but_not_a_fresh_onset():
    assert _peak_drive(0.0) >= 4.0                       # today: the cycle holds A down
    assert _peak_drive(30.0) < 4.0                       # adapted: released
    m = MotorDirectModule(MotorDirectParams(a_threshold=4.0, decay=0.7, dlmn_gain=0.0, adapt_frames=30.0))
    m.update(0.0, 0.0)
    assert m.update(17.0 / 3.0, 0.0)                     # a fresh onset from rest still presses A


def test_muscle_adaptation_also_stops_a_tonic_dlmn_holding_a_but_not_a_fresh_pit_onset():
    """learn_1 sets dlmn_gain 1.0 and DLMn sits at 1.5-2.9 while the jump circuit is latched: drive
    ~ gain*DLMn/(1-decay) = 5-10 > a_threshold 4, so A is held for hundreds of frames."""
    def held_after(adapt, dlmn_of):
        m = MotorDirectModule(MotorDirectParams(a_threshold=4.0, decay=0.7, ttmn_gain=0.0, dlmn_gain=1.0,
                                                release_on_landing=False, adapt_frames=adapt))
        pressed = [m.update(0.0, dlmn_of(i)) for i in range(200)]
        return pressed
    tonic = held_after(0.0, lambda i: 2.0)
    assert all(tonic[20:])                                    # today: A held for as long as DLMn stays up
    adapted = held_after(30.0, lambda i: 2.0)
    assert not any(adapted[150:])                             # adapted: released
    onset = held_after(30.0, lambda i: 2.0 if i < 150 else 8.0)
    assert onset[152] and not onset[149]                      # a fresh DLMn onset (a pit takeoff) still holds A


# ---- A7: all buttons ------------------------------------------------------------------

def test_action_space_covers_every_combination_and_keeps_the_old_indices():
    assert len(MOVES_ALL) == 64 and MOVES_ALL[:8] == [list(m) for m in MOVES]
    seen = {tuple(sorted(buttons_of(i).items())) for i in range(64)}
    assert len(seen) == 64                                # 64 distinct combinations
    for direction in ("R", "L"):
        for a in (False, True):
            for b in (False, True):
                idx = action_index(direction, a, b)
                assert idx == action_from_buttons(right=direction == "R", left=direction == "L", a=a, b=b) < 8
    assert not any(buttons_of(action_from_buttons()).values())            # NOOP
    every = action_from_buttons(*(True,) * 6)
    assert all(buttons_of(every)[b] for b in BUTTONS)


def test_emulator_accepts_every_action_index_and_down_ducks():
    import mario.emulator.env as mario_env
    env = mario_env.make_env("1-1")
    env.reset()
    for _ in range(80):                                   # settle onto the ground first
        env.step(action_index("R", False, False))
    for a in range(64):
        _o, _r, done, _i = env.step(a)
        if done:
            env.reset()
    env.close()


def test_button_muscles_press_only_above_their_threshold_and_drive_decays():
    m = MotorDirectModule(MotorDirectParams(buttons=True, down_gain=1.0, down_threshold=3.0, up_threshold=99.0,
                                            left_threshold=2.0, button_decay=0.5))
    assert m.update_buttons(0.0, 5.0, 0.0) == {"down": False, "up": False, "left": False}   # no neuron activity, no press
    assert m.update_buttons(3.0, 0.0, 0.0)["down"]                                          # 3.0 >= threshold
    for _ in range(10):
        pressed = m.update_buttons(0.0, 0.0, 0.0)
    assert not pressed["down"] and m.button_drive["down"] < 0.01                            # it decays away
    assert m.update_buttons(0.0, 0.0, 2.5)["left"]


def _policy(buttons: bool):
    md = MotorDirectParams(buttons=buttons, down_threshold=0.0, up_threshold=99.0, left_threshold=99.0)
    cfg = dataclasses.replace(ProjectConfig(), modules=ModulesConfig(motor_direct=md))
    p = FullPolicy(config=cfg, level="1-1")
    p.reset(seed=0)
    return p


def test_full_policy_down_muscle_comes_from_the_posture_circuit_and_presses_down():
    import mario.emulator.env as mario_env
    env = mario_env.make_env("1-1")
    env.reset()
    ram = env.unwrapped.ram
    on = _policy(True)
    assert on.buttons_on and on.down_mask.sum() > 0 and on.up_mask.sum() > 0
    action = on.act(SimpleNamespace(ram=ram))
    b = buttons_of(action)
    assert b["down"] and not b["up"] and b["right"] and not b["left"]     # threshold 0 -> Down; others stay off
    extras = on.last_info["extras"]
    assert {"down_val", "up_val", "left_drive", "btn_down"} <= set(extras) and extras["btn_down"]
    off = _policy(False)
    assert not off.buttons_on
    act_off = off.act(SimpleNamespace(ram=ram))
    assert act_off < 8 and "down_val" not in off.last_info["extras"]      # old 8-way action, no new columns
    env.close()
