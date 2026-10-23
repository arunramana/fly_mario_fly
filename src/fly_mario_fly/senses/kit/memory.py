"""What the runner hands every sense as `memory`: a dict that survives from frame to frame (picklable, so it
goes into a saved moment) plus the frame's read-only context."""
from __future__ import annotations


class SenseMemory(dict):
    """Per-sense state (a plain dict) with the run's context attached.

    rng, sigma  the run's sensor noise: a shared numpy Generator and the fraction of each input it perturbs
    world       every object found this frame, whatever is attached to what (a ceiling is a ceiling even when
                nothing looms at it)
    mods        modifiers emitted so far this frame by whole_fly senses, name -> float
    The context is rebound by the runner every frame and is not part of the saved state.
    """

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.rng = None
        self.sigma = 0.0
        self.world: list = []
        self.mods: dict = {}

    def noise(self, size=None):
        """A multiplicative noise factor 1 + sigma*N(0,1). With sigma 0 it is exactly 1.0 and draws nothing."""
        if not self.sigma > 0 or self.rng is None:
            return 1.0
        return 1.0 + self.sigma * (self.rng.standard_normal() if size is None else self.rng.standard_normal(size))

    def __reduce__(self):
        return (SenseMemory, (dict(self),))
