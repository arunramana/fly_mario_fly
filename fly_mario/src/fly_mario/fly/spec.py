"""Fly-side types that belong to the fly lane only (contracts.py stays Mario-agnostic and tiny).

A MechanismSpec satisfies contracts.Mechanism (name, label, input_groups, output_groups, neuron_sets) and
adds what the brain builder needs: which extra MaleCNS neurons the circuit brings, and whether they may
write into the neurons that were already there.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass(frozen=True, eq=False)
class ExtraNeurons:
    """Neurons a mechanism adds on top of the 636-neuron base.

    ids(conn) -> MaleCNS body ids, in the order their rows are appended.
    writes_into_base: True keeps edges FROM the new neurons onto neurons that were already in the brain
    (hearing and smell need this: JO -> Giant Fiber, smell relays -> DNa are the whole circuit). False makes
    the branch read-only: old rows see no input from it, so every earlier mechanism behaves exactly as before.
    recipe: json-able description of how the ids were chosen; goes into the brain's content hash.
    """
    ids: Callable
    writes_into_base: bool
    recipe: dict


@dataclass(frozen=True, eq=False)
class MechanismSpec:
    name: str
    label: str
    input_groups: list          # groups a sense may drive (names in groups.yaml)
    output_groups: list         # groups an action may read
    neuron_sets: list           # groups this circuit owns
    note: str = ""
    build_order: int = 0        # extras are appended in this order, so a brain's row order is reproducible
    extra: Optional[ExtraNeurons] = None   # None: the circuit lives entirely inside the 636-neuron base


@dataclass(frozen=True)
class BrainSpec:
    """Which brain: the 636-neuron base plus the named mechanisms (order does not matter)."""
    mechanisms: tuple = field(default_factory=tuple)
    base: str = "steer636"
