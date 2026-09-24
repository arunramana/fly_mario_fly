# What this file does, in plain English:
# The list of circuit cards the Circuits tab shows: which real neurons
# each one lights up on the live-brain map, which of config/params.py's
# groups its own knobs live in, and where to read more.
"""tool/core/circuit_manifest.py -- tool/SPEC_ui_retro.md section 8/10:
one CircuitEntry per circuit card, data instead of hand-written tab code.
tool/ui/tabs/circuits.py iterates CIRCUIT_REGISTRY to build its card grid;
adding a circuit needs an entry here, not a tab-file edit (section 10's
own extensibility test proves this by registering a dummy entry).

`populations` are render/brain_panel.py's own COL keys (checked directly
against that module, not assumed) -- `highlight_populations(populations)`
turns them into that card's static brain-map image. `groups` are
ProjectConfig's own field names (config/project_config.py), each a real
config/params.py dataclass; a card's detail panel is a ParamForm scoped
to exactly those groups.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CircuitEntry:
    circuit_id: str
    display_name: str
    groups: tuple[str, ...]
    populations: tuple[str, ...]
    description: str
    spec_path: str | None  # None: falls back to the group's own dataclass docstring


CIRCUIT_REGISTRY: list[CircuitEntry] = [
    CircuitEntry(
        "jump", "Jump / Giant Fiber", ("jump", "dnp02"), ("LC4", "LPLC2", "DNp01", "TTMn"),
        "LC4/LPLC2 looming detectors drive the DNp01 Giant Fiber; TTMn is "
        "the jump muscle it fires. The original escape circuit.",
        "docs/SPEC_jump.md",
    ),
    CircuitEntry(
        "steering", "Steering", ("steering",), ("DNa01", "DNa02"),
        "DNa01/DNa02, winner-take-all left/right steering driven by food "
        "and aversive odour.",
        "docs/SPEC_steering.md",
    ),
    CircuitEntry(
        "speed", "Speed", ("speed",), ("DNp09",),
        "DNp09 -- forward-walking drive, brakes near an obstacle.",
        None,
    ),
    CircuitEntry(
        "takeoff", "Takeoff", ("takeoff",), ("DLMn",),
        "DLMn -- wing downstroke muscle, drives the pit long-jump.",
        "docs/SPEC_terrain.md",
    ),
    CircuitEntry(
        "mdn", "MDN", ("mdn",), ("MDN",),
        "MDN -- backward walking. Not currently wired into any decision.",
        None,
    ),
    CircuitEntry(
        "mushroom_body", "Mushroom body", ("mushroom_body",), ("KC", "MBON", "DAN"),
        "KC/MBON/DAN -- the mushroom body's associative-learning core "
        "(event-proximal dopamine).",
        "docs/SPEC_mushroom_body.md",
    ),
]

# Every config/params.py group NOT owned by one of the six circuit cards
# above still needs exactly one writable home (tool/SPEC_ui_retro.md
# section 3) -- an eighth, catch-all card, not folded into any one
# circuit it doesn't actually belong to.
OTHER_GROUPS: tuple[str, ...] = (
    "network", "noise", "habituation", "odour", "terrain",
    "interaction", "entity", "retinotopy", "demo",
)
OTHER_ENTRY = CircuitEntry(
    "other", "Other parameters", OTHER_GROUPS, (),
    "Every tracked scalar that isn't part of one specific circuit above "
    "-- network dynamics, noise, habituation, odour, terrain, entity "
    "geometry, the demo-only injection knobs.",
    None,
)
