# What this file does, in plain English:
# The one list that says what the redesigned fly brain is made of: which neurons
# are the senses (the only place the outside world may touch the brain), which
# are the outputs the game reads, which mushroom-body cells are always included,
# and which paths the network builder must keep. It also holds the fixed table
# that says which output neuron presses which button.
"""brain/manifest.py -- docs/SPEC_brain_core.md section 2.

Populations are picked from the MaleCNS annotations by class/type, never by id
lists, so the manifest stays readable and the counts can be asserted. The motor
table only NAMES output neurons; reading them (brain/motor_map.py) fires nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SENSORY, OUTPUT, MUSHROOM_BODY = "sensory", "output", "mushroom_body"


@dataclass(frozen=True)
class Select:
    """An annotation filter: every given field must match."""
    cls: str | None = None
    types: tuple[str, ...] = ()
    superclass: str | None = None

    def mask(self, ann: pd.DataFrame) -> np.ndarray:
        m = np.ones(len(ann), dtype=bool)
        if self.cls is not None:
            m &= (ann["class"] == self.cls).to_numpy()
        if self.types:
            m &= ann["type"].isin(self.types).to_numpy()
        if self.superclass is not None:
            m &= (ann["superclass"] == self.superclass).to_numpy()
        return m


@dataclass(frozen=True)
class Population:
    name: str
    role: str                      # SENSORY | OUTPUT | MUSHROOM_BODY
    select: Select
    expected: int | None = None    # asserted at resolve time (fail loudly if the data changed)
    note: str = ""


@dataclass(frozen=True)
class Segment:
    """A path segment of the network rule: keep every neuron on a walk of at most k hops from
    `sources` to `targets`."""
    name: str
    sources: tuple[str, ...]
    targets: tuple[str, ...]


@dataclass(frozen=True)
class MotorRow:
    """One line of the fixed motor table: these output populations drive this button."""
    button: str
    populations: tuple[str, ...]
    side: str | None = None        # "L" / "R" when only one side of the populations counts
    note: str = ""


# The entry tier for vision is D1 (docs/REDESIGN_PLAN.md): early feature neurons with published
# tuning, not photoreceptors. Labelled here so the tool can show it.
POPULATIONS = (
    Population("LC4", SENSORY, Select(types=("LC4",)), 126, "vision entry tier D1: loom speed (Ache 2019)"),
    Population("LPLC2", SENSORY, Select(types=("LPLC2",)), 185, "vision entry tier D1: loom size (Ache 2019)"),
    Population("ORN", SENSORY, Select(cls="olfactory"), 2639, "olfactory receptor neurons (no mechanism yet)"),
    Population("GRN_head", SENSORY, Select(cls="gustatory", superclass="cb_sensory"), 275,
               "head taste neurons (no mechanism yet)"),
    Population("THERMO", SENSORY, Select(cls="thermosensory"), 25, "thermosensory neurons (no mechanism yet)"),
    Population("GF", OUTPUT, Select(types=("DNp01",)), 2, "Giant Fiber"),
    Population("TTMn", OUTPUT, Select(types=("TTMn",)), 2, "jump muscle motor neuron"),
    Population("DNp09", OUTPUT, Select(types=("DNp09",)), 2, "walking descending neuron"),
    Population("DNa01", OUTPUT, Select(types=("DNa01",)), 2, "steering descending neuron"),
    Population("DNa02", OUTPUT, Select(types=("DNa02",)), 2, "steering descending neuron"),
    Population("MDN", OUTPUT, Select(types=("MDN",)), 4, "moonwalker descending neuron (backward walking)"),
    Population("KC", MUSHROOM_BODY, Select(cls="Kenyon_Cell"), 4064),
    Population("MBON", MUSHROOM_BODY, Select(cls="MBON"), 97),
    Population("DAN", MUSHROOM_BODY, Select(cls="DAN"), 340),
)

# Segmented union (docs/INVEST_phase0.md 2.4 B). The whole mushroom body is added on top.
SEGMENTS = (
    Segment("vision->outputs", ("LC4", "LPLC2"), ("GF", "TTMn", "DNp09", "DNa01", "DNa02", "MDN")),
    Segment("ORN->KC", ("ORN",), ("KC",)),
    Segment("GRN->DAN", ("GRN_head",), ("DAN",)),
    Segment("thermo->DAN", ("THERMO",), ("DAN",)),
    Segment("MBON->outputs", ("MBON",), ("GF", "TTMn", "DNp09", "DNa01", "DNa02", "MDN")),
)
WHOLE_POPULATIONS = ("KC", "MBON", "DAN")

# Fixed motor table (plan 3.4). Down and Up are deliberately unassigned (D4).
MOTOR_TABLE = (
    MotorRow("A", ("TTMn",), note="muscle drive from the TTMn onset; GF drives TTMn through the wiring"),
    MotorRow("walk", ("DNp09",), note="right + B"),
    MotorRow("left", ("DNa01", "DNa02"), side="L", note="left-minus-right team difference"),
    MotorRow("right", ("DNa01", "DNa02"), side="R", note="right-minus-left team difference"),
    MotorRow("back", ("MDN",), note="backing up = left button"),
)
UNASSIGNED_BUTTONS = ("down", "up")

K_HOPS = 3
MIN_SYNAPSES = 5


def side_of(ann: pd.DataFrame) -> np.ndarray:
    """'L'/'R'/'U' per annotation row. Sensory somas sit in the periphery (somaSide is null), so the
    instance suffix (_L/_R) comes first, then rootSide, then somaSide."""
    inst = ann["instance"].fillna("").astype(str)
    side = np.where(inst.str.endswith("_L"), "L", np.where(inst.str.endswith("_R"), "R", "U")).astype(object)
    for col in ("rootSide", "somaSide"):
        if col in ann.columns:
            alt = ann[col].fillna("").astype(str).str[:1].str.upper().to_numpy()
            fill = (side == "U") & np.isin(alt, ("L", "R"))
            side[fill] = alt[fill]
    return side.astype(str)


@dataclass(frozen=True)
class Manifest:
    populations: tuple[Population, ...] = POPULATIONS
    segments: tuple[Segment, ...] = SEGMENTS
    whole: tuple[str, ...] = WHOLE_POPULATIONS
    motor: tuple[MotorRow, ...] = MOTOR_TABLE
    k: int = K_HOPS
    min_synapses: int = MIN_SYNAPSES

    def population(self, name: str) -> Population:
        return next(p for p in self.populations if p.name == name)

    def names(self, role: str) -> tuple[str, ...]:
        return tuple(p.name for p in self.populations if p.role == role)

    def resolve(self, ann: pd.DataFrame) -> dict[str, np.ndarray]:
        """population name -> sorted bodyIds, asserting the verified counts."""
        out = {}
        for p in self.populations:
            ids = np.sort(ann.loc[p.select.mask(ann), "bodyId"].to_numpy(dtype=np.int64))
            if p.expected is not None:
                assert len(ids) == p.expected, (
                    f"{p.name}: found {len(ids)} neurons, expected {p.expected}. "
                    "The connectome data changed underneath us -- stop and check.")
            out[p.name] = ids
        return out

    def rule(self) -> dict:
        """The build rule, saved with every brain."""
        return {
            "kind": "segmented path-union plus whole mushroom body",
            "k_hops": self.k, "min_synapses": self.min_synapses,
            "segments": [{"name": s.name, "sources": list(s.sources), "targets": list(s.targets)}
                         for s in self.segments],
            "whole_populations": list(self.whole),
            "weights": "sign(pre, consensus_nt) * synapses / in-network input of post (circuit.py recipe)",
            "populations": {p.name: {"role": p.role, "expected": p.expected} for p in self.populations},
        }
