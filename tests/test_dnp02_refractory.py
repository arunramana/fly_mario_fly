"""DNp02 refractory period (docs: the DNp02 <-> pIP1 latch)."""
import dataclasses

import numpy as np
import setuptools  # noqa: F401

from bridge.full_policy import FullPolicy
from config.params import Dnp02RefractoryParams, ModulesConfig
from config.project_config import ProjectConfig
from fly.network.integrator import Integrator


def _pulse_then_silence(policy, steps=300):
    net, idx = policy.dnp02_network, policy.dnp02_idx
    I = np.zeros(net.W.shape[0])
    spikes = []
    for t in range(steps):
        I[:] = 0.0
        if t < 10:
            I[idx] = 3.0
        net.step(I)
        spikes.append(int(net.just_spiked.sum()))
    return spikes


def test_default_off_latches_and_refractory_releases():
    off = FullPolicy(config=ProjectConfig())
    assert off.dnp02_network.integrator.refractory_steps == 0
    assert sum(_pulse_then_silence(off)[-100:]) == 100            # the latch: spikes every step, no input
    cfg = dataclasses.replace(ProjectConfig(), modules=ModulesConfig(dnp02_refractory=Dnp02RefractoryParams()))
    on = FullPolicy(config=cfg)
    assert on.dnp02_network.integrator.refractory_steps == 8
    assert sum(_pulse_then_silence(on)[-100:]) == 0               # released once the input ends
    assert sum(_pulse_then_silence(on)[:10]) > 0                  # but it still fires for a real input


def test_refractory_zero_is_bitwise_the_original_update():
    rng = np.random.default_rng(0)
    W = rng.random((6, 6)) * 0.1
    a = Integrator(spike_idx=[0, 1], spike_threshold=0.1, spike_amp=50.0)
    b = Integrator(spike_idx=[0, 1], spike_threshold=0.1, spike_amp=50.0)
    b.refractory_steps = 0
    ha = hb = np.zeros(6)
    for _ in range(50):
        I = rng.random(6)
        ha, hb = a.step(ha, W, 1.2, I), b.step(hb, W, 1.2, I)
    assert np.array_equal(ha, hb) and np.array_equal(a.mem, b.mem)
