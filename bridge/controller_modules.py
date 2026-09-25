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

from mario.ram import tile_ram
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
    enemy_d_px: int | None     # signed distance to the nearest threat ahead (right side), px
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
    kind = "control"  # LEGACY: forces actions, violates invariant 8 -- see docs/CONTROL_AUDIT.md

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


@dataclass
class PerceptionContext:
    """What a perception module may read before the circuit runs."""
    ram: object
    mario_x: int
    gap_w: int
    distance_to_edge: int | None
    config: object


@dataclass
class Stimulus:
    """What perception modules feed the circuit. Never an action: these only
    change what the fly SEES. Defaults reproduce the unmodified perception."""
    page_aware_looming: bool = False   # enemy distance uses page bytes (into enemy_thetas)
    gap_input: float | None = None     # replaces gap_w in the existing gap current onto DNp01


class PerceptionModule(Protocol):
    """PERCEPTION type: feeds the circuit stimuli, never decides or forces an
    action (project rule, CLAUDE.md invariant 8)."""
    name: str
    kind: str

    def reset(self) -> None: ...
    def perceive(self, ctx: PerceptionContext, stim: Stimulus) -> None: ...


class PagePerceptionModule:
    """PERCEPTION. bridge/perception.enemy_thetas measures an enemy's distance
    as its x byte minus Mario's, ignoring the page byte: across a 256px page
    boundary a Goomba 15px ahead reads ~230px BEHIND and looming stays silent
    until it is on top of Mario. This tells enemy_thetas to use the page-
    corrected distance (RAM 0x006E+slot) so the looming detectors see the
    right stimulus. Nothing is forced: the circuit still decides whether and
    when to jump. (Fixing enemy_thetas unconditionally would change the
    goldens, so it is enabled by presence in config.)"""
    name = "page_perception"
    kind = "perception"

    def __init__(self, params):
        self.params = params

    def reset(self) -> None:
        pass

    def perceive(self, ctx: PerceptionContext, stim: Stimulus) -> None:
        stim.page_aware_looming = True


class GapAheadPerceptionModule:
    """PERCEPTION. The existing gap input only lights up once Mario stands at
    the pit edge (gap_width reads offset 1). This feeds the same input from
    up to `perceive_tiles` away: the width of the upcoming pit, scaled up as
    the edge approaches (full strength at the edge, so identical to today's
    input there) -- a graded approach signal, like looming growth. It only
    changes the current onto DNp01; the circuit's own thresholds decide the
    jump."""
    name = "gap_ahead"
    kind = "perception"

    def __init__(self, params):
        self.params = params

    def reset(self) -> None:
        pass

    def perceive(self, ctx: PerceptionContext, stim: Stimulus) -> None:
        d = ctx.distance_to_edge
        n = self.params.perceive_tiles
        if d is None or d > n:
            return
        width = tile_ram.upcoming_gap_width(ctx.ram, ctx.config.takeoff.gap_lookahead_tiles)
        stim.gap_input = width * (n - d + 1) / n


# Config field name (in ProjectConfig.modules) -> module class. Field order
# in ModulesConfig is the execution order.
MODULE_CLASSES: dict[str, type] = {"page_perception": PagePerceptionModule,
                                    "gap_ahead": GapAheadPerceptionModule}


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
