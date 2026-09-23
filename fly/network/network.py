"""fly/network/network.py -- REFACTOR_PLAN.md section 5.1: "A circuit
becomes a named configuration that builds a Network -- a function or a
small factory, not a type." `Network` is that one concrete class; nothing
subclasses it, per section 5.1's own rejection of a `Circuit` base class
(the mushroom body's plasticity and RetinotopicMap's role as an input
transform, not a circuit, are exactly why that base class was wrong).

The mushroom body's own KC->MBON update is deliberately NOT migrated onto
`Network` this phase -- see docs/RUNS.md's phase 3 note and
docs/REFACTOR_PLAN.md section 6: it has no recurrent self-connection, no
per-frame SUBSTEPS loop, no noise term, and reads `dynamics.ALPHA`/`phi`
directly rather than through either `dynamics.step` or `HybridState`. It
was never one of the six duplicated sites this phase counted (there are
exactly six without it); forcing it onto this shape would be a redesign of
a genuinely different computation, not a move.
"""

from __future__ import annotations

import numpy as np

from fly.network.integrator import Integrator


class Network:
    """`weights` (the connectome-derived W) and `g` (the circuit's one
    hand-set gain) are fixed at construction -- every circuit this project
    has ever built already treats both as constants for a run's whole
    duration, never reassigned mid-episode.

    `populations`, if given, is a dict of named boolean masks into `h`.
    REFACTOR_PLAN.md section 5.1's own sketch says `dict[str, slice]`;
    masks are used here instead because every one of the six circuits
    already selects populations with a boolean mask
    (`bodies["type"]==...`), not a contiguous range, and reordering six
    real connectome-derived weight matrices to get literal contiguous
    slices is a separate, higher-risk change than "unify the update math"
    -- not attempted this phase (docs/RUNS.md's phase 3 note). Existing
    call sites are not migrated to read through `populations` this phase
    either; it is stored for real, but nothing yet requires going through
    it rather than the same masks constructed alongside it, as before.

    `weights` stays a dense `ndarray`, not `scipy.sparse` -- REFACTOR_
    PLAN.md section 6 names that as the eventual shape, but converting six
    real weight matrices is a genuine optimisation with its own profiling
    obligation (CLAUDE.md's "profile before proposing a port" applies
    here too), not a rename, and is out of scope for a phase whose only
    mandate is behaviour-preserving unification."""

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
        """CLAUDE.md's own perf note: `h[h < 1e-30] = 0.0`, measured 84x on
        affected runs. Deliberately a method the CALLER invokes explicitly,
        never something `step()` does automatically: run_steering.py's six
        sites flush at different granularity (once per FRAME, after an
        entire SUBSTEPS loop -- not once per substep), and, found while
        building this unification, the jump circuit's own site never
        called this at all before phase 3 (docs/RUNS.md's phase 3 report
        has the full finding). Baking an automatic flush into `step()`
        would silently change both of those facts -- exactly what
        "byte-identical, not tolerance-based" rules out. Each of the six
        call sites in run_steering.py invokes this (or, for jump,
        deliberately still doesn't) at exactly the point in the frame loop
        it always did."""
        self.h[self.h < threshold] = 0.0

    @property
    def mem(self) -> np.ndarray:
        return self.integrator.mem

    @property
    def just_spiked(self) -> np.ndarray:
        return self.integrator.just_spiked
