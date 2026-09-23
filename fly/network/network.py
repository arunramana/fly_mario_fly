"""fly/network/network.py -- a circuit is a named configuration that builds
a Network (REFACTOR_PLAN.md section 5.1), not a subclass of one.

The mushroom body's KC->MBON update does not run through Network: it has no
recurrent self-connection, no SUBSTEPS loop and no noise term, so it is a
different computation, not another instance of this one.
"""

from __future__ import annotations

import numpy as np

from fly.network.integrator import Integrator


class Network:
    """`weights` (the connectome-derived W) and `g` (the circuit's one
    hand-set gain) are fixed for the whole run.

    `populations` is a dict of named boolean masks into `h`. Masks rather
    than slices, because no circuit's populations are contiguous in its
    connectome-derived row order. `weights` stays a dense ndarray."""

    def __init__(self, weights: np.ndarray, integrator: Integrator, g: float = 1.0,
                 populations: dict[str, np.ndarray] | None = None):
        self.W = weights
        self.integrator = integrator
        self.g = g
        self.populations = populations or {}
        self.h = np.zeros(weights.shape[0])

    def step(self, I: np.ndarray, noise=None) -> np.ndarray:
        self.h = self.integrator.step(self.h, self.W, self.g, I, noise=noise)
        return self.h

    def flush_denormals(self, threshold: float = 1e-30) -> None:
        """Zero sub-threshold activity to avoid IEEE-754 denormal slowdowns.
        The caller decides when: circuits flush once per frame, after their
        SUBSTEPS loop, and the jump circuit does not flush at all. Flushing
        inside `step()` would change every golden."""
        self.h[self.h < threshold] = 0.0

    @property
    def mem(self) -> np.ndarray:
        return self.integrator.mem

    @property
    def just_spiked(self) -> np.ndarray:
        return self.integrator.just_spiked
