# What this file does, in plain English:
# Checks the option that makes the fly's learning signal (dopamine) fire
# only on real events. A ?-block hit or a stomp must give one reward pulse
# and death one punishment pulse; a known 800-frame game must find 5 stomps
# and 7 ?-block hits; switching the option on must change what is learned;
# and plain forward movement alone must then cause no learning.
"""
Event-proximal dopamine: a unit test of event_dopamine's routing and
magnitude, and an integration check that FullPolicy's
`event_proximal_dopamine=True` detects stomps live, fires PAM only on
qblock_hit/stomp, and changes the weight trajectory.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

import run_steering
from bridge.full_policy import FullPolicy
from config.project_config import ProjectConfig
from fly.network import dynamics
from fly.plasticity.dopamine import event_dopamine

SCENARIO = dict(level="1-1", max_frames=800, sigma=0.0, seed=0,
                 record_video=False, write_telemetry=False)


def test_event_dopamine_routing_and_magnitude():
    assert event_dopamine(qblock_hit=False, stomp=False, died=False) == (0.0, 0.0)
    assert event_dopamine(qblock_hit=True, stomp=False, died=False) == (dynamics.CLIP, 0.0)
    assert event_dopamine(qblock_hit=False, stomp=True, died=False) == (dynamics.CLIP, 0.0)
    assert event_dopamine(qblock_hit=True, stomp=True, died=False) == (dynamics.CLIP, 0.0), (
        "both appetitive events in one frame must not double the magnitude -- "
        "an event either happened or it didn't, this is a one-shot signal"
    )
    assert event_dopamine(qblock_hit=False, stomp=False, died=True) == (0.0, dynamics.CLIP)


def test_full_policy_detects_stomps_live():
    """The baseline sigma=0 seed=0 scenario is known (docs/RUNS.md's phase
    5b correction entry) to produce 5 stomps via an external RAM-scanning
    monkeypatch. FullPolicy's own live detection (now permanent, not a
    diagnostic patch) must find the same real signal."""
    tel, info = run_steering.main(out_mp4="IGNORED_test_stomps.mp4", mb_weights=None, **SCENARIO)
    assert info["n_stomps"] == 5, (
        f"expected 5 stomps (docs/RUNS.md's phase 5b correction measured this "
        f"exact scenario externally), got {info['n_stomps']} -- live detection "
        f"disagrees with the independently-measured value"
    )
    assert info["n_qblock_hits"] == 7


def test_event_proximal_mode_changes_the_learning_trajectory(tmp_path):
    legacy_tel, legacy_info = run_steering.main(
        out_mp4=str(tmp_path / "legacy.mp4"), mb_weights=None,
        event_proximal_dopamine=False, **SCENARIO)
    event_tel, event_info = run_steering.main(
        out_mp4=str(tmp_path / "event.mp4"), mb_weights=None,
        event_proximal_dopamine=True, **SCENARIO)

    assert not np.array_equal(legacy_info["mb_weights"], event_info["mb_weights"]), (
        "event-proximal mode produced the exact same learned weights as the "
        "legacy continuous-progress trigger -- the two reward mechanisms "
        "should not be indistinguishable"
    )
    # Both triggers still see the same qblock hits/stomps regardless of mode
    # (detection is unconditional; only what DRIVES dopamine changes).
    assert event_info["n_qblock_hits"] == legacy_info["n_qblock_hits"]
    assert event_info["n_stomps"] == legacy_info["n_stomps"]


def test_event_proximal_reward_fires_only_on_real_events():
    """Direct check on FullPolicy.act()'s own reward branch: with
    event_proximal_dopamine=True, a frame with real forward progress but no
    qblock_hit/stomp must NOT depress W_kc_mbon (unlike the legacy trigger,
    which would)."""
    policy = FullPolicy(config=ProjectConfig(), level="1-1", event_proximal_dopamine=True)
    policy.reset(seed=0)
    w_before = policy.W_kc_mbon.copy()

    import mario.emulator.env as mario_env
    env = mario_env.make_env("1-1")
    obs = env.reset()
    ram = env.unwrapped.ram
    # Run a handful of frames -- 1-1 opens with clear ground, no `?` block
    # or enemy in stomp range this early, so forward progress happens
    # (reward > 0 under the legacy trigger) with no qualifying event yet.
    for _ in range(20):
        action = policy.act(SimpleNamespace(ram=ram))
        obs, reward, done, info = env.step(action)
        if policy.last_info["qblock_hit"] or policy.last_info["stomp"]:
            break
    env.close()

    assert np.array_equal(policy.W_kc_mbon, w_before), (
        "W_kc_mbon changed even though no qblock_hit/stomp occurred in these "
        "frames -- event-proximal mode is still reacting to plain forward "
        "progress, the thing it's supposed to replace"
    )
