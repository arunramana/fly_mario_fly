"""Runtime guards: fail loudly, in plain English, when a rule is about to be broken while a run is going.

Standard library + numpy only, so fly/brain.py and runner/ can both use it. These stop mistakes and make the rule visible;
they are not a sandbox against code that goes out of its way to defeat them.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping

import numpy as np


class RuleViolation(ValueError):
    """A project rule was about to be broken. The message says which, and why."""


# ---- N1: the connectome weights are read-only -------------------------------------------------------------------

def frozen_copy(W) -> np.ndarray:
    """A private, read-only copy of a weight matrix (same numbers, same dtype)."""
    out = np.array(W, copy=True)
    out.setflags(write=False)
    return out


def weights_fingerprint(W) -> str:
    return hashlib.sha256(np.ascontiguousarray(W).tobytes()).hexdigest()


def check_weights(W, fingerprint: str) -> None:
    """Raise if the weights are not exactly what they were when the brain was built or loaded."""
    if weights_fingerprint(W) != fingerprint:
        raise RuleViolation("The connectome weights changed after the brain was built. Weights are read-only: "
                            "the wiring is untouched and only dials are tuned.")


# ---- N2: no firing neurons directly -----------------------------------------------------------------------------

def check_input_groups(names, allowed, who: str = "input") -> None:
    """Only groups declared as INPUT groups of a mechanism may be driven. Motor and descending neurons are outputs."""
    bad = sorted(set(names) - set(allowed))
    if bad:
        raise RuleViolation(f"{who} tried to drive {bad}, which is not an input group of any mechanism. Neurons may only be "
                            f"driven through a declared sensory route (input groups: {sorted(allowed)}); descending and motor "
                            f"neurons can only be read.")


def check_input_vector(I, input_mask) -> None:
    """The input vector of a brain step may be non-zero only on input-group neurons."""
    if np.any(np.asarray(I)[~input_mask] != 0):
        raise RuleViolation("An input vector puts drive on neurons that are not in any input group. Neurons may not be fired "
                            "directly; use brain.drive({group: level}) with a declared input group.")


# ---- S3 / S4: what a sense may write and an action may read, and which buttons ------------------------------------

def check_sense_output(sense: str, inputs, declared_drives) -> None:
    bad = sorted(set(inputs) - set(declared_drives))
    if bad:
        raise RuleViolation(f"sense '{sense}' drove {bad}, but its declaration only allows {sorted(declared_drives)}. "
                            f"A sense may only drive the groups it declares on its real route.")


class GuardedRates(Mapping):
    """The group rates an action is allowed to see: only its declared source groups.

    Reading any other group raises: the decision must come from the fly's own motor or descending neurons."""

    def __init__(self, rates, allowed, who: str):
        self._rates, self._allowed, self._who = rates, tuple(allowed), who

    def _check(self, key):
        if key not in self._allowed:
            raise RuleViolation(f"action '{self._who}' read group '{key}', but it declares only {list(self._allowed)}. "
                                f"An action decides from its declared motor/descending neurons and nothing else.")

    def __getitem__(self, key):
        self._check(key)
        return self._rates[key]

    def get(self, key, default=None):
        self._check(key)
        return self._rates.get(key, default)

    def __iter__(self):
        return iter(k for k in self._allowed if k in self._rates)

    def __len__(self):
        return sum(1 for k in self._allowed if k in self._rates)


def check_buttons(action: str, intent, declared_buttons) -> None:
    used = set(intent.press) | set(intent.release)
    bad = sorted(used - set(declared_buttons))
    if bad:
        raise RuleViolation(f"action '{action}' touched buttons {bad}, but it declares only {sorted(declared_buttons)}.")
