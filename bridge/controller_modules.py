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

from mario.ram.addresses import (
    ADDR_ENEMY_ACTIVE, ADDR_ENEMY_PAGE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X, ADDR_MARIO_PAGE,
    ADDR_MARIO_X, N_ENEMY_SLOTS, POWERUP_ID,
)
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


class GroundedPitModule:
    """SCAFFOLDING (docs/SPEC_pits.md follow-up). A hand-placed rule keyed on
    a RAM tile read and Mario's player state, not something the wiring
    produces. Near a pit edge it bypasses the jump cooldown and launches the
    long jump -- but only when Mario is standing on the ground (RAM 0x001D
    == 0) and A was up on the previous frame, so the press is a fresh one.
    The un-grounded GradedPitModule fired mid-air, held A through the
    landing, and never took off before the edge. Holds B for a run-up."""
    name = "grounded_pit"

    def __init__(self, params):
        self.params = params

    def reset(self) -> None:
        pass

    def observe(self, ctx: ActContext) -> None:
        pass

    def propose(self, ctx: ActContext, out: Proposal) -> None:
        d = ctx.distance_to_edge
        if d is None:
            return
        if d <= self.params.run_up_tiles:
            out.force_press_b = True
        if d <= self.params.trigger_distance_tiles:
            if ctx.player_state == 0 and not ctx.prev_press_a:
                out.bypass_cooldown = out.force_dnp01 = out.force_long_jump = True
            else:
                log.debug(f"  grounded_pit waiting: state={ctx.player_state} "
                          f"prev_A={ctx.prev_press_a} distance={d}")


class ThreatCooldownBypassModule:
    """SCAFFOLDING. The escape jump's cooldown (a mechanical output-interface
    constant, not part of the circuit) can still be running when a Goomba
    arrives -- e.g. right after a long pit jump -- so TTMn crosses its
    threshold and nothing happens. With a threat within `distance_px`
    ahead, Mario on the ground and A up, this lifts ONLY the cooldown; the
    commit itself is still the circuit's own TTMn crossing."""
    name = "threat_bypass"

    def __init__(self, params):
        self.params = params

    def reset(self) -> None:
        pass

    def observe(self, ctx: ActContext) -> None:
        pass

    def propose(self, ctx: ActContext, out: Proposal) -> None:
        d = ctx.enemy_d_px
        if (d is not None and 0 <= d <= self.params.distance_px
                and ctx.player_state == 0 and not ctx.prev_press_a):
            out.bypass_cooldown = True


class PageAwareThreatModule:
    """SCAFFOLDING, and a perception repair the circuit cannot make for itself.
    bridge/perception.enemy_thetas measures an enemy's distance as its x byte
    minus Mario's, ignoring the page byte. Across a 256px page boundary a
    Goomba 15px ahead reads as ~230px BEHIND, so looming stays silent until
    the enemy is almost on top of Mario and the escape jump fires too late
    (win_attempt iteration 3, x=1782). This module recomputes the distance
    with page bytes (RAM 0x006E+slot) and, for a ground enemy within
    `trigger_px` ahead, with Mario grounded and A up, commits the short hop
    through DNp01 (cooldown bypassed). Fixing enemy_thetas itself would
    change the goldens, so the repair lives here, behind the win config."""
    name = "page_threat"

    def __init__(self, params):
        self.params = params

    def reset(self) -> None:
        pass

    def observe(self, ctx: ActContext) -> None:
        pass

    def propose(self, ctx: ActContext, out: Proposal) -> None:
        if ctx.player_state != 0 or ctx.prev_press_a:
            return
        ram = ctx.ram
        mario = int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X])
        for slot in range(N_ENEMY_SLOTS):
            if not ram[ADDR_ENEMY_ACTIVE + slot] or int(ram[ADDR_ENEMY_TYPE + slot]) == POWERUP_ID:
                continue
            d = int(ram[ADDR_ENEMY_PAGE + slot]) * 256 + int(ram[ADDR_ENEMY_X + slot]) - mario
            if 0 <= d <= self.params.trigger_px:
                log.debug(f"  page_threat fires: slot={slot} true_distance={d}px")
                out.bypass_cooldown = out.force_dnp01 = True
                return


# Config field name (in ProjectConfig.modules) -> module class. Field order
# in ModulesConfig is the execution order.
MODULE_CLASSES: dict[str, type] = {"grounded_pit": GroundedPitModule,
                                    "threat_bypass": ThreatCooldownBypassModule,
                                    "page_threat": PageAwareThreatModule}


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
