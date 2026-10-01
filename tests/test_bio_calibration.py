# What this file does, in plain English:
# Tests the calibrated "honest fly" escape circuit on the looming-disc bench (no game): with
# nothing but noise it stays silent (real and shuffled wiring); the real Giant Fiber fires at
# a roughly constant angular size for slow-to-medium discs; the same fixed numbers applied to
# shuffled wiring give later or weaker responses; and the derived thresholds still match what
# the real circuit does at the target angle.
"""docs/SPEC_bio_calibration.md: disc and resting-state tests, all on the synthetic bench."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from bridge.full_policy import FullPolicy
from bridge.loom_disc import first, rest_test, run_disc
from config.params import BioStrictParams, ModulesConfig, MotorDirectParams
from config.project_config import ProjectConfig

BIO = BioStrictParams()
TARGET_DEG = 55.0


def _policy(shuffle=None, bio=BIO):
    cfg = ProjectConfig(bio_strict=True, bio=bio, modules=ModulesConfig(motor_direct=MotorDirectParams()))
    p = FullPolicy(config=cfg, level="1-1", shuffle_seed=shuffle)
    p.reset(0)
    return p


@pytest.fixture(scope="module")
def real():
    return _policy()


@pytest.fixture(scope="module")
def shuffled():
    return [_policy(shuffle=k) for k in (1, 2)]


def test_gains_obey_the_stability_criterion_and_shuffles_get_the_same_gain(real, shuffled):
    from fly.connectome import circuit
    from bridge.full_policy import _circuit_cache
    for key, net, cfg_g in (("jump", real.jump_network, real.config.jump.g), ("speed", real.speed_network, real.config.speed.g),
                            ("steering", real.steering_network, real.config.steering.g)):
        rho = circuit.spectral_radius(_circuit_cache[key][4], 1.0)
        assert net.g * rho <= BIO.stability_margin + 1e-9 and net.g <= cfg_g
    assert real.jump_network.g < 1.1                                    # the old 2.0 / 2.6 was supercritical (rho 0.82)
    for p in shuffled:
        assert p.jump_network.g == real.jump_network.g                 # the wiring changes, the calibration does not


def test_nothing_switches_itself_on_at_rest_real_or_shuffled(real, shuffled):
    for p in (real, *shuffled):
        r = rest_test(p, frames=2000, sigma=0.015)
        assert r["ttmn"] < 0.5 and r["dnp01"] < 0.5 and r["dnp02"] < 0.5 and r["dlmn"] < 0.5
        assert r["gf_spikes"] == 0 and r["dnp02_spikes"] == 0


def test_real_gf_fires_near_a_constant_angular_size_for_l_over_v_20_to_80(real):
    thetas = []
    for lv in (20, 40, 80):
        rec = run_disc(real, lv)
        s = first(rec, "spike")
        assert s is not None, f"GF silent for l/v {lv}"
        thetas.append(s["theta"])
        assert s["tau"] > 20                                             # well before collision
        assert rec[0]["ttmn"] < 0.5 and max(r["ttmn"] for r in rec[:5]) < 0.5   # TTMn no longer switches on at onset
    assert max(thetas) - min(thetas) < 20                               # roughly constant across a 4x range of l/v
    assert all(40 <= t <= 75 for t in thetas)                            # around the 50-60 deg target (medium-low confidence)


def test_fixed_thresholds_on_shuffled_wiring_respond_later_or_weaker(real, shuffled):
    for lv in (40, 80):
        rec = run_disc(real, lv)
        t_real = first(rec, "spike")["theta"]
        peak_real = max(r["ttmn"] for r in rec)
        for p in shuffled:
            rec_s = run_disc(p, lv)
            s = first(rec_s, "spike")
            assert s is None or s["theta"] > t_real + 10                 # mistimed (later) or absent
            assert max(r["ttmn"] for r in rec_s) < 0.5 * peak_real      # and a much weaker muscle-neuron response


def test_dnp02_is_off_the_noise_floor_and_fires_for_the_fastest_resolved_disc(real):
    rec = run_disc(real, 10)
    assert first(rec, "spike2") is not None                             # the rate-driven pathway responds to a fast loom
    assert rest_test(real, frames=500)["dnp02_spikes"] == 0            # ... and not to noise
    slow = run_disc(real, 80)
    assert first(slow, "spike2")["theta"] > first(rec, "spike2")["theta"] - 50   # slower discs recruit it no earlier (at larger theta)


def test_the_stored_thresholds_are_what_the_real_circuit_does_at_the_target_angle():
    p = _policy(bio=dataclasses.replace(BIO, gf_threshold=1e9, dnp02_threshold=1e9, dnp02_input_gain=1.0))
    mem = [np.interp(TARGET_DEG, [r["theta"] for r in rec], [r["mem"] for r in rec]) for rec in (run_disc(p, lv) for lv in (20, 40, 80))]
    assert abs(np.mean(mem) - BIO.gf_threshold) / BIO.gf_threshold < 0.02
    rec10 = run_disc(p, 10)
    m2 = float(np.interp(TARGET_DEG, [r["theta"] for r in rec10], [r["mem2"] for r in rec10]))
    assert abs(BIO.dnp02_input_gain - BIO.gf_threshold / m2) / BIO.dnp02_input_gain < 0.02
    assert BIO.dnp02_threshold == BIO.gf_threshold


def test_effective_config_carries_the_calibrated_values():
    from config.bio_strict import effective
    cfg = ProjectConfig(bio_strict=True, modules=ModulesConfig(motor_direct=MotorDirectParams(dlmn_gain=1.0)))
    e = effective(cfg)
    assert e.jump.dnp01_spike_threshold == BIO.gf_threshold and e.dnp02.spike_threshold == BIO.dnp02_threshold
    assert e.jump.ttmn_press_threshold == pytest.approx(cfg.jump.ttmn_press_threshold * BIO.ttmn_unit_factor)
    assert e.modules.motor_direct.dlmn_gain == pytest.approx(1.0 / BIO.dlmn_unit_factor)
    off = ProjectConfig()
    assert effective(off) is off
