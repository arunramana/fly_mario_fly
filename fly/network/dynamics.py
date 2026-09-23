"""
dynamics.py — the leaky integrator from SPEC_jump.md section 3.

    h(t+1) = (1 - alpha) * h(t) + alpha * phi( g * W @ h(t) + I(t) + b + eta )

phi = ReLU, not tanh: these are firing-rate units, and a rate cannot go
negative — inhibition already enters through the sign of w_ij, baked into W
by circuit.py. An upper clip stops runaway when g pushes the recurrence past
its stable point. The bias `b` is not implemented (always 0). `eta ~ N(0,
sigma)` is membrane noise, `NoiseConfig` below.
"""

from __future__ import annotations

import numpy as np

ALPHA = 0.3        # leak; time constant ~= 1/alpha substeps (~3 substeps ~5ms)
SUBSTEPS = 10       # network steps per emulator frame (60fps frame = 16.7ms)
CLIP = 50.0         # upper clip on firing rate, arbitrary units


def phi(x: np.ndarray) -> np.ndarray:
    return np.clip(x, 0.0, CLIP)


class NoiseConfig:
    """Membrane noise eta ~ N(0, sigma), added to every neuron's drive
    before phi() in every circuit: one stochastic term, not a per-circuit
    knob. `sigma` is an attribute rather than a module constant so a GUI
    slider can bind to it.

    One `rng` per episode, shared by every circuit and substep, so a whole
    episode is reproducible from one seed. sigma=0.0 draws nothing and
    returns a bare 0.0, bit-identical to passing no noise at all."""

    def __init__(self, sigma: float, rng: np.random.Generator):
        self.sigma = sigma
        self.rng = rng

    def sample(self, k: int):
        if self.sigma == 0.0:
            return 0.0
        return self.rng.normal(0.0, self.sigma, size=k)


def step(h: np.ndarray, W: np.ndarray, g: float, I: np.ndarray,
         alpha: float = ALPHA, noise: NoiseConfig | None = None) -> np.ndarray:
    """One substep: h(t+1) = (1-alpha)*h(t) + alpha*phi(g*W@h(t) + I + eta)."""
    drive = g * (W @ h) + I
    if noise is not None:
        drive = drive + noise.sample(len(h))
    return (1.0 - alpha) * h + alpha * phi(drive)


def simulate(W: np.ndarray, g: float, I_trace: np.ndarray, h0: np.ndarray | None = None,
             alpha: float = ALPHA, substeps: int = SUBSTEPS) -> np.ndarray:
    """Run the integrator over a sensory trace.

    I_trace : (n_frames, K) — one sensory-input vector per EMULATOR frame.
              Held constant (zero-order hold) across all `substeps` network
              steps within that frame, per spec section 3.
    Returns : (n_frames * substeps + 1, K) history of h, including h0.
    """
    K = W.shape[0]
    h = np.zeros(K) if h0 is None else h0.copy()
    hist = [h.copy()]
    for I_frame in I_trace:
        for _ in range(substeps):
            h = step(h, W, g, I_frame, alpha)
            hist.append(h.copy())
    return np.array(hist)


class HybridState:
    """DNp01 spiking fallback. No g makes the population dynamics sharp
    (SPEC_jump.md section 1b: linear leak/gain or balanced E/I damping,
    never a bistable middle), so rather than fake sharpness with an
    unverified saturating phi, only the two DNp01 bodies become leaky
    integrate-and-fire units: once membrane potential crosses
    `spike_threshold`, emit one step of `spike_amp` and reset. Every other
    neuron keeps the plain ReLU rate dynamics.
    """

    def __init__(self, K: int, dnp01_idx: np.ndarray, spike_threshold: float,
                 spike_amp: float = CLIP):
        self.h = np.zeros(K)
        self.mem = np.zeros(len(dnp01_idx))
        self.dnp01_idx = np.asarray(dnp01_idx)
        self.spike_threshold = spike_threshold
        self.spike_amp = spike_amp
        self.just_spiked = np.zeros(len(dnp01_idx), dtype=bool)

    def step(self, W: np.ndarray, g: float, I: np.ndarray, alpha: float = ALPHA,
             noise: NoiseConfig | None = None):
        drive = g * (W @ self.h) + I
        if noise is not None:
            drive = drive + noise.sample(len(self.h))
        h_new = (1.0 - alpha) * self.h + alpha * phi(drive)

        # eta is already in `drive`, so DNp01's membrane sees the same noise
        # sample as everyone else this substep -- that is what lets noise
        # move its spike timing.
        dnp01_drive = np.maximum(drive[self.dnp01_idx], 0.0)
        self.mem = (1.0 - alpha) * self.mem + alpha * dnp01_drive
        spiking = self.mem >= self.spike_threshold
        spike_out = np.where(spiking, self.spike_amp, 0.0)
        self.mem = np.where(spiking, 0.0, self.mem)

        h_new[self.dnp01_idx] = spike_out
        self.h = h_new
        self.just_spiked = spiking
        return self.h


class AdaptiveHybridState(HybridState):
    """HybridState plus firing-rate adaptation on every rate-coded unit
    (everyone except DNp01, which already has its own reset via spiking).

    Diagnostic-4 finding: without this, LC4/LPLC2 have nothing to stop them
    integrating sustained drive forever -- real looming detectors adapt.
    Modeled the standard way for a rate unit: a slow trace `a` of the unit's
    own recent output is subtracted from its drive before phi (a Ca2+-gated
    K+ current or synaptic depression would do this biologically):

        a(t+1) = (1 - alpha_a) * a(t) + alpha_a * h(t)
        h(t+1) = (1 - alpha) * h(t) + alpha * phi(g*W@h(t) + I(t) - beta*a(t))

    Diagnostic only (scripts/adapt_sweep.py), not used by the live system.
    Adopting it would add two hand-set scalars, `alpha_a` and `beta`.
    """

    def __init__(self, K: int, dnp01_idx: np.ndarray, spike_threshold: float,
                 alpha_a: float, beta: float, spike_amp: float = CLIP):
        super().__init__(K, dnp01_idx, spike_threshold, spike_amp)
        self.a = np.zeros(K)
        self.alpha_a = alpha_a
        self.beta = beta
        self.adapt_mask = np.ones(K, dtype=bool)
        self.adapt_mask[self.dnp01_idx] = False

    def step(self, W: np.ndarray, g: float, I: np.ndarray, alpha: float = ALPHA,
             noise: NoiseConfig | None = None):
        drive = g * (W @ self.h) + I
        if noise is not None:
            drive = drive + noise.sample(len(self.h))
        drive[self.adapt_mask] -= self.beta * self.a[self.adapt_mask]
        h_new = (1.0 - alpha) * self.h + alpha * phi(drive)

        dnp01_drive = np.maximum(drive[self.dnp01_idx], 0.0)
        self.mem = (1.0 - alpha) * self.mem + alpha * dnp01_drive
        spiking = self.mem >= self.spike_threshold
        spike_out = np.where(spiking, self.spike_amp, 0.0)
        self.mem = np.where(spiking, 0.0, self.mem)

        h_new[self.dnp01_idx] = spike_out
        self.a = (1.0 - self.alpha_a) * self.a + self.alpha_a * self.h
        self.h = h_new
        self.just_spiked = spiking
        return self.h
