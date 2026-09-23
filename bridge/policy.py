# What this file does, in plain English:
# A cut-down controller (the part that picks the buttons each frame) that
# uses only the escape-jump circuit, a small network of simulated neurons
# wired like the real fly. It always holds right and run; when an approaching
# enemy pushes the simulated jump-muscle neurons past a threshold, it holds
# jump for a fixed time, then pauses. Used only by tests/test_episode.py.
"""bridge/policy.py -- `JumpPolicy`, a `sim.protocols.Policy` over the
escape/jump circuit alone: hold right and B, press A once TTMn crosses its
press threshold, hold the jump for `jump_hold_frames`.

Jump only. The full system is bridge/full_policy.py. tests/test_episode.py
runs this through a real Episode and MarioEnvironment; it reproduces no
golden run.
"""

from __future__ import annotations

import numpy as np

from bridge.perception import enemy_thetas
from bridge.motor import action_index
from config.params import JumpParams
from fly.connectome.load_cached import load as load_jump
from fly.network import dynamics
from fly.network.integrator import Integrator
from fly.network.network import Network
from mario.ram.addresses import ADDR_MARIO_X


class JumpPolicy:
    def __init__(self, params: JumpParams | None = None):
        self.params = params or JumpParams()
        j_bodies, _, _, _, self._W, _, _ = load_jump(N=60)
        self._K = self._W.shape[0]

        def mask(t, s):
            return ((j_bodies["type"] == t) & (j_bodies["somaSide"] == s)).to_numpy()

        dnp01_l, dnp01_r = mask("DNp01", "L"), mask("DNp01", "R")
        self._dnp01_idx = np.concatenate([np.where(dnp01_l)[0], np.where(dnp01_r)[0]])
        self._masks = {
            "LC4_L": mask("LC4", "L"), "LC4_R": mask("LC4", "R"),
            "LPLC2_L": mask("LPLC2", "L"), "LPLC2_R": mask("LPLC2", "R"),
            "TTMn_L": mask("TTMn", "L"), "TTMn_R": mask("TTMn", "R"),
        }
        self.network: Network | None = None
        self.reset(seed=0)

    def reset(self, seed: int) -> None:
        # No noise here, so `seed` is unused; the Policy protocol requires it.
        integrator = Integrator(spike_idx=self._dnp01_idx,
                                 spike_threshold=self.params.dnp01_spike_threshold,
                                 spike_amp=self.params.spike_amp)
        self.network = Network(self._W, integrator, g=self.params.g)
        self._prev_theta = {"L": 0.0, "R": 0.0}
        self._jump_hold = 0
        self._jump_cooldown = 0

    def act(self, observation) -> int:
        ram = observation.ram
        mario_x = int(ram[ADDR_MARIO_X])
        theta, dtheta, _ = enemy_thetas(ram, mario_x, self._prev_theta)
        self._prev_theta = theta

        I = np.zeros(self._K)
        I[self._masks["LC4_L"]] = abs(dtheta["L"]); I[self._masks["LPLC2_L"]] = theta["L"]
        I[self._masks["LC4_R"]] = abs(dtheta["R"]); I[self._masks["LPLC2_R"]] = theta["R"]

        for _ in range(dynamics.SUBSTEPS):
            h = self.network.step(I)
        ttmn_val = max(h[self._masks["TTMn_L"]].mean(), h[self._masks["TTMn_R"]].mean())

        press_a = False
        if self._jump_cooldown > 0:
            self._jump_cooldown -= 1
        elif self._jump_hold == 0 and ttmn_val >= self.params.ttmn_press_threshold:
            self._jump_hold = self.params.jump_hold_frames
        if self._jump_hold > 0:
            press_a = True
            self._jump_hold -= 1
            if self._jump_hold == 0:
                self._jump_cooldown = self.params.jump_cooldown_frames

        return action_index("R", press_a, True)
