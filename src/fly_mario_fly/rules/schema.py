"""The plug-in declaration: what every sense, action, object, character, shape, scene and mechanism says about itself.

Imports nothing from fly_mario_fly (so any folder may use it), only the standard library.

Colour rule:  teal = real wiring read off the MaleCNS connectome ("fly")   orange = invented by us ("invented").
A plug-in file puts one `DECLARATION = declare(...)` next to its `PLUGIN`. The validator (rules/validate.py) checks it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

ORIGINS = ("fly", "invented")
KINDS = ("sense", "action", "object", "character", "shape", "scene", "mechanism")
BUTTONS = ("A", "B", "left", "right", "up", "down", "start", "select")
GAME_READS = ("airborne", "modifiers")        # the only game facts an action's decision may also use (each must be justified)


@dataclass(frozen=True)
class Route:
    """The real MaleCNS wiring an item rides on: which circuit, which cell types, in plain words."""
    mechanism: str              # a name in fly/mechanisms (escape, walking, hearing, attraction, aversion)
    cell_types: tuple           # MaleCNS cell types it passes through; "JO*" means every type starting with JO
    wiring: str                 # e.g. "LC4/LPLC2 -> DNp01 (Giant Fiber) -> TTMn"


@dataclass(frozen=True)
class Declaration:
    kind: str                   # one of KINDS
    origin: str                 # "fly" (teal) or "invented" (orange)
    what: str                   # one plain sentence: what is real here and what is invented
    route: Optional[Route] = None        # required for origin "fly", senses and actions
    drives: tuple = ()          # sense: the neuron groups it may write (input groups of its route's mechanism)
    modulates: tuple = ()       # sense that drives no neuron: the modifiers it raises for another sense
    reads_groups: tuple = ()    # action: the neuron groups it may read (its source_groups)
    buttons: tuple = ()         # action: the NES buttons it may press or release
    game_reads: tuple = ()      # action: game facts its decision also uses (subset of GAME_READS); say why in `what`


def declare(kind: str, origin: str, what: str, **kw) -> Declaration:
    """Build a Declaration (a short spelling for plug-in files)."""
    return Declaration(kind=kind, origin=origin, what=what, **kw)
