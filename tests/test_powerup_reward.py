# What this file does, in plain English:
# Checks the power-up reward (docs/SPEC_learning_v2.md section 4): when Mario
# turns into Super Mario the fly's learning centre gets a reward pulse, but
# only when that is switched on; the pulse and a death's punishment weaken
# different output cells, so the same memory trace is changed in opposite
# ways depending on which of the two arrived (the sign test).
"""Power-up dopamine: routing, the FullPolicy trigger, and the reward-vs-punishment sign test."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from bridge.full_policy import FullPolicy
from config.project_config import ProjectConfig
from fly.network import dynamics
from fly.plasticity.dopamine import event_dopamine
from fly.plasticity.three_factor import depress
from mario.ram.addresses import ADDR_MARIO_SIZE
from sim.fitness import FitnessWeights, compute_fitness


def test_powerup_is_an_appetitive_event_of_the_same_size():
    assert event_dopamine(False, False, False, powerup=True) == (dynamics.CLIP, 0.0)
    assert event_dopamine(False, False, False) == (0.0, 0.0)                       # default: unchanged
    assert event_dopamine(True, True, False, powerup=True) == (dynamics.CLIP, 0.0)  # events never add up
    assert event_dopamine(False, False, True, powerup=True) == (dynamics.CLIP, dynamics.CLIP)


def test_powerup_weight_in_fitness():
    w = FitnessWeights(powerup=10.0)
    assert compute_fitness(w, distance=100, powerups=3) == 130.0
    assert compute_fitness(FitnessWeights(), distance=100, powerups=3) == 100.0    # default weight 0


def _ram_with_size(size: int):
    import mario.emulator.env as mario_env
    env = mario_env.make_env("1-1")
    env.reset()
    ram = np.array(env.unwrapped.ram)     # a copy: the test sets the size byte itself
    env.close()
    ram[ADDR_MARIO_SIZE] = size
    return ram


def _grow(powerup_reward: bool, event_proximal: bool = True):
    """Frame 1 as small Mario, frame 2 as Super Mario (RAM 0x0756 0 -> 1); nothing else changes."""
    policy = FullPolicy(config=ProjectConfig(), level="1-1", event_proximal_dopamine=event_proximal,
                        powerup_reward=powerup_reward)
    policy.reset(seed=0)
    ram = _ram_with_size(0)
    policy.act(SimpleNamespace(ram=ram))
    w_before = policy.W_kc_mbon.copy()
    ram[ADDR_MARIO_SIZE] = 1
    policy.act(SimpleNamespace(ram=ram))
    return policy, w_before


def test_becoming_super_depresses_the_mushroom_body_only_when_switched_on():
    policy, w_before = _grow(powerup_reward=True)
    assert policy.n_powerups == 1
    assert not np.array_equal(policy.W_kc_mbon, w_before), "a power-up must reach the KC->MBON weights"
    assert (policy.W_kc_mbon <= w_before).all()                   # depression only

    off, w_off = _grow(powerup_reward=False)
    assert off.n_powerups == 1                                     # still counted (for fitness) ...
    assert np.array_equal(off.W_kc_mbon, w_off)                    # ... but no dopamine

    legacy, w_legacy = _grow(powerup_reward=True, event_proximal=False)
    assert np.array_equal(legacy.W_kc_mbon, w_legacy)              # only in the mode that uses events


def test_starting_big_is_not_an_event():
    policy = FullPolicy(config=ProjectConfig(), level="1-1", event_proximal_dopamine=True, powerup_reward=True)
    policy.reset(seed=0)
    ram = _ram_with_size(1)                                        # big from the first frame
    policy.act(SimpleNamespace(ram=ram))
    policy.act(SimpleNamespace(ram=ram))
    assert policy.n_powerups == 0


def sign_test_numbers(policy) -> dict:
    """Same eligibility, one power-up pulse vs one death pulse, through the real rule and the
    real PAM / PPL+PPM reach of every MBON. Returns per-group summed weight change."""
    rng = np.random.default_rng(0)
    elig = (rng.random(policy.n_kc) < 0.05).astype(float)         # a sparse code, as the KCs use
    lr = policy.config.mushroom_body.learning_rate
    pam, _ = event_dopamine(False, False, False, powerup=True)
    _, punish = event_dopamine(False, False, True)
    w0 = policy.W_kc_mbon
    d_reward = (depress(w0.copy(), pam * policy.mb_pam_reach, elig, lr) - w0).sum(axis=1)
    d_punish = (depress(w0.copy(), punish * policy.mb_punish_reach, elig, lr) - w0).sum(axis=1)
    pam_dom = policy.mb_pam_reach > policy.mb_punish_reach
    ppl_dom = policy.mb_punish_reach > policy.mb_pam_reach
    return {"n_pam_dominated": int(pam_dom.sum()), "n_ppl_dominated": int(ppl_dom.sum()),
            "pam_group": (float(d_reward[pam_dom].sum()), float(d_punish[pam_dom].sum())),
            "ppl_group": (float(d_reward[ppl_dom].sum()), float(d_punish[ppl_dom].sum())),
            "d_reward": d_reward, "d_punish": d_punish, "pam_dom": pam_dom, "ppl_dom": ppl_dom}


def test_sign_test_reward_and_punishment_move_different_mbons_in_opposite_directions():
    policy = FullPolicy(config=ProjectConfig(), level="1-1")
    n = sign_test_numbers(policy)
    assert n["n_pam_dominated"] > 0 and n["n_ppl_dominated"] > 0, "both DAN clusters must reach some MBONs"
    assert (n["d_reward"] <= 0).all() and (n["d_punish"] <= 0).all()          # depression only, both
    rew_pam, pun_pam = n["pam_group"]
    rew_ppl, pun_ppl = n["ppl_group"]
    # PAM-dominated MBONs lose more under reward than under punishment; PPL-dominated the reverse:
    # (reward effect - punishment effect) has opposite signs on the two groups.
    assert rew_pam < pun_pam
    assert rew_ppl > pun_ppl
    diff = n["d_reward"] - n["d_punish"]
    assert (diff[n["pam_dom"]] <= 0).all() and (diff[n["ppl_dom"]] >= 0).all()
