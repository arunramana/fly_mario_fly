"""fly/network/integrator.py -- REFACTOR_PLAN.md phase 3 (sections 5.1, 6):
one Integrator, replacing the six independent call sites run_steering.py
had accumulated across 26 sprints, each stepping `fly/network/dynamics.py`'s
`step()` or `HybridState.step()` with its own W/g/I.

Not a new equation -- `HybridState.step()` was already the general case: a
leaky-ReLU population update, plus an OPTIONAL leaky-integrate-and-fire
spiking override on a named sub-population (DNp01's role in the jump
circuit, DNp02's in the second escape pathway). With an EMPTY spike index
array, that update reduces exactly to plain `dynamics.step()`:
`h_new[np.array([])] = spike_out` is a no-op assignment on an empty
selection, so `h_new` is exactly `(1-alpha)*h + alpha*phi(drive)` and
nothing else runs. That identity is the entire unification -- one class,
used by all six sites; the four non-spiking circuits (takeoff, steering,
mdn, speed) are simply never given a spike index.

`fly/network/dynamics.py` itself is UNCHANGED -- still used by
`run_mario.py`'s own sprint-001 demo and by every `tune_*.py`/`diag4.py`
diagnostic script. This phase migrates only `run_steering.py`'s six live
call sites onto `Integrator`/`Network` (`network.py`, this package), not
every historical or diagnostic use of the older classes.
"""

from __future__ import annotations

import numpy as np

from fly.network.dynamics import ALPHA, CLIP


class Integrator:
    """Owns the recurrent update's math: the leaky step, ReLU+clip (`phi`),
    the noise term, and -- only for neurons named in `spike_idx` -- the
    leaky-integrate-and-fire override (SPEC_jump.md section 1b's DNp01
    fallback, reused unchanged for DNp02 in SPEC_second_escape.md).

    `h` is NOT stored here -- it belongs to whichever `Network` owns this
    Integrator, and is passed in explicitly every call, exactly like
    `dynamics.step()`'s own signature. `mem`/`just_spiked` DO live here:
    they're the spiking sub-population's own persistent state, with no
    equivalent for a purely rate-coded population.

    Denormal flushing is deliberately NOT done inside `step()` -- see
    `Network.flush_denormals()`'s docstring for why."""

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
        """`h(t+1) = (1-alpha)*h(t) + alpha*phi(g*W@h(t) + I(t) + eta)`,
        SPEC_jump.md section 3 -- verbatim from `dynamics.step`, plus the
        optional spiking override described above, verbatim from
        `dynamics.HybridState.step`. Order of operations matches
        `HybridState.step` exactly: `phi(drive)` is computed for every
        neuron (including ones about to be overwritten by the spike
        override) before the override is applied, matching the original's
        sequencing bit for bit."""
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
