"""
dynamics.py — the leaky integrator from SPEC_jump.md section 3.

    h(t+1) = (1 - alpha) * h(t) + alpha * phi( g * W @ h(t) + I(t) + b )

phi = ReLU, not tanh: these are firing-rate units, and a rate cannot go
negative — inhibition already enters through the sign of w_ij, baked into W
by circuit.py. An upper clip stops runaway when g pushes the recurrence past
its stable point.
"""

from __future__ import annotations

import numpy as np

ALPHA = 0.3        # leak; time constant ~= 1/alpha substeps (~3 substeps ~5ms)
SUBSTEPS = 10       # network steps per emulator frame (60fps frame = 16.7ms)
CLIP = 50.0         # upper clip on firing rate, arbitrary units


def phi(x: np.ndarray) -> np.ndarray:
    return np.clip(x, 0.0, CLIP)


def step(h: np.ndarray, W: np.ndarray, g: float, I: np.ndarray,
         alpha: float = ALPHA) -> np.ndarray:
    """One substep: h(t+1) = (1-alpha)*h(t) + alpha*phi(g*W@h(t) + I)."""
    drive = g * (W @ h) + I
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
    """DNp01 spiking fallback (SPEC section 1b sweep found no g that makes the
    POPULATION dynamics sharp -- linear leak/gain vs. balanced E/I damping,
    never a bistable middle). Rather than fake sharpness with a saturating
    phi we didn't verify, every OTHER neuron keeps the plain ReLU leaky rate
    dynamics from section 3, verbatim. Only the two DNp01 bodies are swapped
    for a leaky integrate-and-fire unit: accumulate, and once membrane
    potential crosses `spike_threshold`, emit one frame of `spike_amp` and
    reset to zero. This is a THIRD hand-set scalar beyond g and the TTMn
    press threshold -- flagged here and in the README per CLAUDE.md invariant
    3, forced by the section-3 negative result, not chosen for convenience.
    """

    def __init__(self, K: int, dnp01_idx: np.ndarray, spike_threshold: float,
                 spike_amp: float = CLIP):
        self.h = np.zeros(K)
        self.mem = np.zeros(len(dnp01_idx))
        self.dnp01_idx = np.asarray(dnp01_idx)
        self.spike_threshold = spike_threshold
        self.spike_amp = spike_amp
        self.just_spiked = np.zeros(len(dnp01_idx), dtype=bool)

    def step(self, W: np.ndarray, g: float, I: np.ndarray, alpha: float = ALPHA):
        drive = g * (W @ self.h) + I
        h_new = (1.0 - alpha) * self.h + alpha * phi(drive)

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

    This is exploratory (SPEC section 3, "check whether a leak/adaptation
    term is the missing piece") and adds TWO more hand-set scalars
    (`alpha_a`, `beta`) on top of the three already flagged in the README --
    only adopt it, and say so plainly, if it actually earns its place by
    making Diagnostic 4 pass at a workable g.
    """

    def __init__(self, K: int, dnp01_idx: np.ndarray, spike_threshold: float,
                 alpha_a: float, beta: float, spike_amp: float = CLIP):
        super().__init__(K, dnp01_idx, spike_threshold, spike_amp)
        self.a = np.zeros(K)
        self.alpha_a = alpha_a
        self.beta = beta
        self.adapt_mask = np.ones(K, dtype=bool)
        self.adapt_mask[self.dnp01_idx] = False

    def step(self, W: np.ndarray, g: float, I: np.ndarray, alpha: float = ALPHA):
        drive = g * (W @ self.h) + I
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
