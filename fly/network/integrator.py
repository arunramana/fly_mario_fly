# What this file does, in plain English:
# The update rule every live circuit uses to advance its neurons one step:
# activity fades, is pushed by inputs plus noise, and is kept between zero
# and a cap. Optionally a chosen few neurons (the Giant Fiber, or DNp02)
# instead build up charge and fire a spike when it crosses a threshold. A
# test checks it gives the same numbers as the older rule in dynamics.py.
"""fly/network/integrator.py -- the one recurrent update every live circuit
steps: a leaky-ReLU population plus an optional leaky-integrate-and-fire
override on a named sub-population (DNp01 in the jump circuit, DNp02 in the
second escape pathway). With no spike index it is exactly
`dynamics.step()`, so the four rate-only circuits (takeoff, steering, MDN,
speed) simply get none.

`fly/network/dynamics.py` keeps its own `step`/`HybridState` for
run_mario.py and the diagnostic scripts.
"""

from __future__ import annotations

import numpy as np

from fly.network.dynamics import ALPHA, CLIP


class Integrator:
    """The leaky step, ReLU+clip (`phi`), the noise term, and -- only for
    neurons in `spike_idx` -- the leaky-integrate-and-fire override
    (SPEC_jump.md section 1b).

    `h` belongs to the owning Network and is passed in each call.
    `mem`/`just_spiked` live here: they are the spiking sub-population's
    own state. No denormal flush here (see Network.flush_denormals)."""

    def __init__(self, alpha: float = ALPHA, clip: float = CLIP,
                 spike_idx=None, spike_threshold: float | None = None,
                 spike_amp: float | None = None):
        self.alpha = alpha
        self.clip = clip
        self.spike_idx = np.asarray(spike_idx if spike_idx is not None else [], dtype=int)
        self.spike_threshold = spike_threshold
        self.spike_amp = clip if spike_amp is None else spike_amp
        self.mem = np.zeros(len(self.spike_idx))
        self.just_spiked = np.zeros(len(self.spike_idx), dtype=bool)

    def phi(self, x: np.ndarray) -> np.ndarray:
        return np.clip(x, 0.0, self.clip)

    def step(self, h: np.ndarray, W: np.ndarray, g: float, I: np.ndarray,
             noise=None) -> np.ndarray:
        """`h(t+1) = (1-alpha)*h(t) + alpha*phi(g*W@h(t) + I(t) + eta)`
        (SPEC_jump.md section 3), then the spike override. The operation
        order matches `dynamics.HybridState.step` bit for bit: `phi(drive)`
        is computed for every neuron before spiking ones are overwritten."""
        drive = g * (W @ h) + I
        if noise is not None:
            drive = drive + noise.sample(len(h))
        h_new = (1.0 - self.alpha) * h + self.alpha * self.phi(drive)

        if len(self.spike_idx):
            spike_drive = np.maximum(drive[self.spike_idx], 0.0)
            self.mem = (1.0 - self.alpha) * self.mem + self.alpha * spike_drive
            spiking = self.mem >= self.spike_threshold
            spike_out = np.where(spiking, self.spike_amp, 0.0)
            self.mem = np.where(spiking, 0.0, self.mem)
            h_new[self.spike_idx] = spike_out
            self.just_spiked = spiking

        return h_new
