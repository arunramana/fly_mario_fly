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
    registry: object = None
    profiles: object = None    # bridge.entity_profiles.EntityProfiles, or None (profiles off)


@dataclass
class Stimulus:
    """What perception modules feed the circuit. Never an action: these only
    change what the fly SEES. Defaults reproduce the unmodified perception."""
    page_aware_looming: bool = False   # enemy distance uses page bytes (into enemy_thetas)
    gap_input: float | None = None     # replaces gap_w in the existing gap current onto DNp01
    mb_extra: tuple = ()               # extra Kenyon-cell inputs (MbSpatialInputModule)
    wall_theta: float = 0.0            # looming angle of the wall ahead (WallAheadPerceptionModule)
    wall_dtheta: float = 0.0           # its growth this frame
    wall_takeoff: float = 0.0          # takeoff current from the wall onto DNp01
    wall_distance_tiles: int = 0       # what was perceived (telemetry only): 0 = no wall
    wall_height_tiles: int = 0
    qblock_theta: float = 0.0          # looming angle of the ? block ahead (QBlockAheadPerceptionModule)
    qblock_dtheta: float = 0.0         # its growth this frame
    qblock_tiles: int = -1             # what was perceived (telemetry only): -1 = no block in range
    qblock_height_tiles: int = 0


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


class WallAheadPerceptionModule:
    """PERCEPTION. The first solid obstacle ahead (pipe, stair, block stack)
    from the tile RAM, as distance and height. It reaches the circuit only as
    stimuli, never as an action: (1) looming -- the wall is an object of angular
    size theta = 2*arctan(h / (2*d)) that grows as Mario walks at it (invariant
    1, Mario's-eye view: h is the wall's height in px, d the distance to its
    near face), added to the right-hemisphere LC4/LPLC2 drive like an enemy's;
    (2) takeoff -- height x proximity onto DNp01, like gap_ahead. Each route has
    its own gain (0 = off). Whether and when the fly jumps is the circuit's."""
    name = "wall_ahead"
    kind = "perception"
    TILE_PX = 16

    def __init__(self, params):
        self.params = params
        self.reset()

    def reset(self) -> None:
        self.prev_theta = 0.0

    def perceive(self, ctx: PerceptionContext, stim: Stimulus) -> None:
        import math
        p = self.params
        wall = tile_ram.obstacle_ahead(ctx.ram, p.perceive_tiles)
        theta = 0.0
        if wall is not None:
            from mario.ram.addresses import ADDR_MARIO_PAGE
            tiles, height = wall
            mario_abs = int(ctx.ram[ADDR_MARIO_PAGE]) * 256 + ctx.mario_x
            near_face = (mario_abs // self.TILE_PX + tiles) * self.TILE_PX
            d = max(near_face - mario_abs, 1)
            theta = 2.0 * math.atan(height * self.TILE_PX / (2.0 * d))
            stim.wall_takeoff = p.takeoff_gain * height * (p.perceive_tiles - tiles + 1) / p.perceive_tiles
            stim.wall_distance_tiles, stim.wall_height_tiles = tiles, height
        stim.wall_theta = p.looming_gain * theta
        stim.wall_dtheta = p.looming_gain * (theta - self.prev_theta)
        self.prev_theta = theta


class Dnp02RefractoryModule:
    """CIRCUIT. Carries the DNp02 refractory period (config.params.
    Dnp02RefractoryParams); FullPolicy applies it to the DNp02 network's
    spiking cells. Neither perceives nor acts."""
    name = "dnp02_refractory"
    kind = "circuit"

    def __init__(self, params):
        self.params = params

    def reset(self) -> None:
        pass


class ArousalModule:
    """CIRCUIT. Carries the pC1 arousal settings (config.params.ArousalParams);
    FullPolicy loads the cached pC1 weights and adds the drive to each circuit's
    input. Neither perceives nor acts (docs/SPEC_arousal_pc1.md)."""
    name = "arousal"
    kind = "circuit"

    def __init__(self, params):
        self.params = params

    def reset(self) -> None:
        pass


class Dnp01RefractoryModule:
    """CIRCUIT. Carries the DNp01 (Giant Fiber) refractory period; FullPolicy
    applies it to the jump network's spiking cells. Independent of
    Dnp02RefractoryModule."""
    name = "dnp01_refractory"
    kind = "circuit"

    def __init__(self, params):
        self.params = params

    def reset(self) -> None:
        pass


class MbSpatialInputModule:
    """PERCEPTION. Two extra Kenyon-cell inputs, both 0..1 "closeness" like
    looming: the next pit edge (1 at the edge, 0 beyond the takeoff
    lookahead) and the nearest enemy ahead by PAGE-CORRECTED distance (1 at
    contact, 0 at 128 px). Without them the mushroom body sees only gap width
    (0 until Mario stands at the edge) and theta, so it cannot learn to act
    before a pit or Goomba is close. Off by default (n_mb_sensory stays 7 and
    every golden is unchanged)."""
    name = "mb_spatial_inputs"
    kind = "perception"
    N_INPUTS = 2   # Kenyon-cell inputs it adds; FullPolicy sums these over all modules
    ENEMY_RANGE_PX = 128.0

    def __init__(self, params):
        self.params = params

    def reset(self) -> None:
        pass

    def perceive(self, ctx: PerceptionContext, stim: Stimulus) -> None:
        from bridge.perception import _dx
        from mario.entities.kinds import EntityKind
        look = ctx.config.takeoff.gap_lookahead_tiles
        d = ctx.distance_to_edge
        edge = 0.0 if d is None or d > look else (look - d + 1) / look
        nearest = None
        if ctx.registry is not None:
            for slot, rec in enumerate(ctx.registry.enemy_records(ctx.ram)):
                if not rec.active or rec.kind == EntityKind.POWERUP:
                    continue
                dx = _dx(ctx.ram, slot, rec, ctx.mario_x, True)
                if dx >= 0 and (nearest is None or dx < nearest):
                    nearest = dx
        enemy = 0.0 if nearest is None else max(0.0, 1.0 - nearest / self.ENEMY_RANGE_PX)
        stim.mb_extra = stim.mb_extra + (float(edge), float(enemy))


class QBlockAheadPerceptionModule:
    """PERCEPTION. Unhit `?` blocks at or ahead of Mario, from the tile RAM, as
    distance and height (a hit block reads as used and drops out of the list,
    so a cue never points at an emptied block). Reaches the circuit only as
    stimuli, never as an action (invariant 8): (1) two Kenyon-cell inputs, both
    0..1 like looming -- closeness (1 overhead, 0 at `perceive_tiles`) and
    height (tiles above the ground row / the ground row), so the mushroom body
    can learn where rewarding blocks are; (2) if `looming_gain` > 0, a weak
    looming cue theta = 2*arctan(16 px / (2*d_px)) into the right-hemisphere
    LC4/LPLC2 drive like the wall. Whether and when the fly jumps is the
    circuit's. Both routes are scaled by the QUESTION_BLOCK profile's
    `cue_weight` when entity profiles are on (Objects tab). Off by default:
    n_mb_sensory stays as it was and every golden is unchanged."""
    name = "qblock_ahead"
    kind = "perception"
    N_INPUTS = 2
    TILE_PX = 16

    def __init__(self, params):
        self.params = params
        self.reset()

    def reset(self) -> None:
        self.prev_theta = 0.0

    def perceive(self, ctx: PerceptionContext, stim: Stimulus) -> None:
        import math
        from mario.ram.tile_ram import GROUND_ROW, question_blocks_ahead
        p = self.params
        weight = 1.0
        if ctx.profiles is not None:
            from mario.entities.kinds import EntityKind
            weight = ctx.profiles.get(EntityKind.QUESTION_BLOCK).cue_weight
        blocks = question_blocks_ahead(ctx.ram, p.perceive_tiles)
        closeness = height = theta = 0.0
        if blocks:
            tiles, height_tiles = blocks[0]
            closeness = (p.perceive_tiles - tiles) / p.perceive_tiles
            height = height_tiles / GROUND_ROW
            d_px = max(tiles * self.TILE_PX, self.TILE_PX / 2)
            theta = 2.0 * math.atan(self.TILE_PX / (2.0 * d_px))
            stim.qblock_tiles, stim.qblock_height_tiles = tiles, height_tiles
        stim.mb_extra = stim.mb_extra + (weight * closeness, weight * height)
        stim.qblock_theta = weight * p.looming_gain * theta
        stim.qblock_dtheta = weight * p.looming_gain * (theta - self.prev_theta)
        self.prev_theta = theta


class MotorDirectModule:
    """MOTOR. Replaces the fixed jump-hold and cooldown counters (docs/
    CONTROL_AUDIT.md rows 1-3) with a readout of the motor neurons
    themselves: A is held while a leaky integral of the TTMn ONSET (its rise
    -- motor neurons are phasic, and a saturated TTMn pool stays high long
    after the muscle has fired) plus a DLMn term (sustained DLMn = a longer,
    graded jump instead of a binary long-jump choice) stays above
    `a_threshold`. Nothing is forced: the code
    only low-passes what the circuit's own output neurons are doing, as a
    muscle does. There is no cooldown -- a new commit needs a fresh rising
    edge of the motor output, so the Giant Fiber's own refractoriness is
    the only limit. Habituation still suppresses the commit (its bookkeeping
    is unchanged) and a suppressed press contributes no drive."""
    name = "motor_direct"
    kind = "motor"

    def __init__(self, params):
        self.params = params
        self.reset()

    def reset(self) -> None:
        self.drive = 0.0
        self.prev_ratio = 0.0
        self.was_ready = False
        self.suppressed = False
        self.prev_player_state = 0

    def rising(self, ready: bool) -> bool:
        """True on the frame the motor output first crosses threshold."""
        edge = ready and not self.was_ready
        if not ready:
            self.suppressed = False
        self.was_ready = ready
        return edge

    def update(self, ttmn_ratio: float, dlmn_val: float, player_state: int | None = None) -> bool:
        """Advance the integrator one frame; return whether A is down.
        `player_state` (RAM 0x001D): on the frame it returns to 0 (landed)
        A is released and the drive cleared, so the next jump is a new press
        (SMB ignores a held A). Skipped when release_on_landing is off."""
        p = self.params
        if p.release_on_landing and player_state is not None:
            landed = self.prev_player_state != 0 and player_state == 0
            self.prev_player_state = player_state
            if landed:
                self.drive = 0.0
                self.prev_ratio = ttmn_ratio
                return False
        rise = max(0.0, ttmn_ratio - self.prev_ratio)
        self.prev_ratio = ttmn_ratio
        drive_in = 0.0 if self.suppressed else p.ttmn_gain * rise + p.dlmn_gain * dlmn_val
        self.drive = self.drive * p.decay + drive_in
        if self.drive < 1e-12:
            self.drive = 0.0
        return self.drive >= p.a_threshold


class MbonReadoutModule:
    """READOUT. The mushroom body used to act through one scalar (the mean
    of all MBON activity). This gives each MBON its own connectome-derived
    weight onto each motor pathway (fly/circuits/mbon_pathway_weights.py:
    direct MBON->target synapses plus two-hop MBON->X->target paths), so
    learning that depresses particular MBONs changes particular pathways
    (jump, long jump, speed, backing up) differently. Output: a bias current
    per pathway, negative like the existing MBON->DNa02 path (the MBONs'
    dominant partners are GABAergic)."""
    name = "mbon_readout"
    kind = "readout"
    PATHWAYS = ("dnp01", "dlmn", "dnp09", "mdn")

    def __init__(self, params):
        self.params = params
        self.weights = None  # set by FullPolicy once the MBON ids are known

    def reset(self) -> None:
        pass

    def readout(self, h_mbon) -> dict:
        """{pathway: (weighted MBON activity, bias current it drives)}."""
        p = self.params
        frac = {"dnp01": p.dnp01_frac, "dlmn": p.dlmn_frac, "dnp09": p.dnp09_frac, "mdn": p.mdn_frac}
        out = {}
        for g in self.PATHWAYS:
            value = float(self.weights[g] @ h_mbon)
            out[g] = (value, -frac[g] * value)
        return out


# Config field name (in ProjectConfig.modules) -> module class. Field order
# in ModulesConfig is the execution order.
MODULE_CLASSES: dict[str, type] = {"page_perception": PagePerceptionModule,
                                    "gap_ahead": GapAheadPerceptionModule,
                                    "wall_ahead": WallAheadPerceptionModule,
                                    "motor_direct": MotorDirectModule,
                                    "mb_spatial_inputs": MbSpatialInputModule,
                                    "dnp02_refractory": Dnp02RefractoryModule,
                                    "dnp01_refractory": Dnp01RefractoryModule,
                                    "arousal": ArousalModule,
                                    "mbon_readout": MbonReadoutModule,
                                    "qblock_ahead": QBlockAheadPerceptionModule}


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
