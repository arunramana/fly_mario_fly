# What this file does, in plain English:
# A small plug-in system for FullPolicy's decision rules. Each rule is a
# "module" with three steps: reset at the start of an episode, observe (read
# what this frame looks like), and propose (ask FullPolicy to bypass the jump
# cooldown, force a jump or hold the run button). FullPolicy runs whichever
# modules the project config lists, in order; a module is on because it is in
# the config, not because of an if-flag inside FullPolicy.
"""bridge/controller_modules.py -- the ControllerModule protocol and the
registry that builds FullPolicy's ordered module list from a ProjectConfig.

Every module's docstring must say whether it is CIRCUIT (behaviour that
falls out of the wiring) or SCAFFOLDING (a hand-placed controller rule keyed
on a RAM read, like gap_gain or HOME_BIAS) -- prefer circuit; take
scaffolding only when that is what wins, and say so.

Boundaries: RAM addresses live in mario/ram/addresses.py; this is glue
(bridge/), so it may import mario/ but fly/ never does.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)


@dataclass
class ActContext:
    """What a module may read this frame (all plain values, no RAM
    handle beyond `ram` itself for a module's own extra reads)."""
    ram: object
    mario_x: int
    gap_w: int
    distance_to_edge: int | None
    dlmn_val: float
    player_state: int          # RAM 0x001D: 0 == on the ground
    prev_press_a: bool         # was A held on the previous frame's action
    jump_hold: int
    jump_cooldown: int
    config: object


@dataclass
class Proposal:
    """What modules ask FullPolicy to do this frame. All False = no change,
    which is what keeps a module-less policy byte-identical to before."""
    bypass_cooldown: bool = False   # let the escape trigger run despite jump_cooldown
    force_dnp01: bool = False       # commit through DNp01 without its own TTMn threshold
    force_long_jump: bool = False   # launch the long (35-frame) jump
    force_press_b: bool = False     # hold B (run) this frame


class ControllerModule(Protocol):
    name: str

    def reset(self) -> None: ...
    def observe(self, ctx: ActContext) -> None: ...
    def propose(self, ctx: ActContext, out: Proposal) -> None: ...


class GradedPitModule:
    """SCAFFOLDING (docs/SPEC_pits.md). The original opt-in pit response, kept
    behind its legacy `scenario.graded_pit_response` switch because its
    golden-proven tests pin it: near a pit, bypass the cooldown, commit
    DNp01 and launch long; hold B for a run-up. Fires even mid-air, which
    is the flaw GroundedPitModule fixes."""
    name = "graded_pit"

    def reset(self) -> None:
        pass

    def observe(self, ctx: ActContext) -> None:
        pass

    def propose(self, ctx: ActContext, out: Proposal) -> None:
        d = ctx.distance_to_edge
        if d is None:
            return
        t = ctx.config.takeoff
        if d <= t.long_jump_trigger_distance_tiles:
            out.bypass_cooldown = out.force_dnp01 = out.force_long_jump = True
        if d <= t.run_up_tiles:
            out.force_press_b = True


# Config field name (in ProjectConfig.modules) -> module class. Field order
# in ModulesConfig is the execution order.
MODULE_CLASSES: dict[str, type] = {}


def register(name: str):
    def deco(cls):
        MODULE_CLASSES[name] = cls
        return cls
    return deco


def build_modules(config) -> list:
    """Ordered module list: the legacy graded-pit switch first, then every
    non-None field of config.modules, each built from its own params."""
    modules: list = []
    if config.scenario.graded_pit_response:
        modules.append(GradedPitModule())
    for f in dataclasses.fields(config.modules):
        params = getattr(config.modules, f.name)
        if params is not None:
            modules.append(MODULE_CLASSES[f.name](params))
    return modules
