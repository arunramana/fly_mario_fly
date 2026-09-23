"""bridge/perception.py -- REFACTOR_PLAN.md section 2: the first of bridge/'s
two questions, "what does this entity smell and look like to the fly?"
This is the only module that reads mario/'s RAM AND produces fly-relevant
stimuli (theta/dtheta, odour concentrations) -- fly/ itself never sees a
RAM array or an enemy slot, only the numbers this module hands it.

`enemy_thetas`, `mushroom_odor` and `goomba_odor` are moved here (from
run_mario.py and run_steering.py respectively) and rewritten to classify
each enemy slot through mario.entities.registry.DEFAULT.enemy_records()
instead of each reimplementing `ram[ADDR_ENEMY_TYPE+i] == POWERUP_ID`
independently -- see docs/ENTITIES.md and docs/REFACTOR_PLAN.md's phase 2
report for that duplication. The arithmetic is unchanged: same distance,
same 1/px concentration, same theta formula: EntityRecord.width is
ENTITY_WIDTH_PX (16), the exact value W_TILE already was at every one of
these call sites.

`question_block_odor` reads tile_ram directly rather than going through an
EntityRecord -- a genuinely different data source (a tile scan, not an
enemy slot), and unifying it is a deliberate phase-2 scoping decision left
for later, not an oversight (docs/ENTITIES.md says so explicitly).

Odour as a labelled channel, per REFACTOR_PLAN.md section 4 ("Odour must be
a list of labelled channels, not a scalar"): bridge/profiles/default.json
documents each EntityKind's channel(s) -- POWERUP and QUESTION_BLOCK both
emit the hunger-gated "food" channel, ENEMY emits the un-gated "threat"
channel -- matching exactly what mushroom_odor/question_block_odor (food)
and goomba_odor (threat) already computed. The profile is documentation
this phase, read by tests and docs/ENTITIES.md, not yet the live source of
the gain numbers themselves -- ODOUR_GAIN/HUNGER_MULT_* stay hand-set
scalars in run_steering.py (CLAUDE.md invariant 3); making the profile the
actual runtime source of those numbers is per-component config extraction,
REFACTOR_PLAN.md phase 4, not this one.
"""

from __future__ import annotations

import numpy as np

from mario.entities.kinds import EntityKind
from mario.entities.registry import DEFAULT as DEFAULT_REGISTRY
from mario.ram import tile_ram
from mario.ram.addresses import ADDR_MARIO_SIZE

HUNGER_MULT_HUNGRY = 3.0      # RAM 0x0756==0 (small Mario)
HUNGER_MULT_SATED = 1.0       # RAM 0x0756>=1 (big/fiery Mario) -- unboosted, not zeroed


def enemy_thetas(ram, mario_x, prev_theta, registry=DEFAULT_REGISTRY):
    """Nearest active THREAT's theta/dtheta per hemisphere. Enemies ahead of
    Mario (on-screen x >= mario_x) route Right; behind route Left -- our
    convention, SPEC doesn't fix one since retinotopy is skipped (section 2).
    Powerup-slot entities are skipped -- see mario.ram.addresses.POWERUP_ID's
    comment."""
    theta = {"L": 0.0, "R": 0.0}
    d_out = {"L": None, "R": None}
    for rec in registry.enemy_records(ram):
        if not rec.active or rec.kind == EntityKind.POWERUP:
            continue
        d = rec.x - int(mario_x)
        side = "R" if d >= 0 else "L"
        ad = max(abs(d), 1)
        th = 2.0 * np.arctan(rec.width / (2.0 * ad))
        if th > theta[side]:
            theta[side] = th
            d_out[side] = d
    dtheta = {s: theta[s] - prev_theta[s] for s in ("L", "R")}
    return theta, dtheta, d_out


def mushroom_odor(ram, mario_x, registry=DEFAULT_REGISTRY):
    """SPEC_steering.md section 2: powerups share the enemy slots.
    concentration ~ 1/distance, routed by sign of d exactly like enemy
    routing in enemy_thetas -- ahead/right excites the R team, behind/left
    the L team. Raw concentration, NO gain applied here -- ODOUR_GAIN/hunger
    are applied once, at the call site, so both odour sources share one
    gain constant (SPEC_odour.md section 0)."""
    odor = {"L": 0.0, "R": 0.0}
    for rec in registry.enemy_records(ram):
        if not rec.active or rec.kind != EntityKind.POWERUP:
            continue
        d = rec.x - int(mario_x)
        conc = 1.0 / max(abs(d), 1)
        side = "R" if d >= 0 else "L"
        odor[side] += conc
    return odor


def question_block_odor(ram):
    """SPEC_odour.md section 1: a second odour source at every `?` block
    tile_ram finds (0xC0 coin, 0xC1 power-up -- not distinguished, same as
    the mushroom not distinguishing power-up subtype). tile_ram.
    question_blocks_near returns signed TILE-COLUMN offsets relative to
    Mario, not pixels -- convert (*16) before applying the same
    concentration formula and gain as the mushroom, so one gain constant
    covers both. Limitation, stated here per spec, not discovered later:
    this is a horizontal-only signal -- it can pull Mario to stand under a
    block, nothing more. Actually hitting it from below is the existing
    contact-based climb reflex's job, and that reflex's tile_ram.solid_ahead
    check explicitly excludes question tiles from counting as a climb
    target (they float overhead, not underfoot) -- so whether stage two
    ever actually fires is an open question this sprint answers empirically,
    not by assumption. See the writeup for what was actually observed."""
    odor = {"L": 0.0, "R": 0.0}
    for offset_tiles in tile_ram.question_blocks_near(ram):
        d = offset_tiles * 16
        conc = 1.0 / max(abs(d), 1)
        side = "R" if d >= 0 else "L"
        odor[side] += conc
    return odor


def goomba_odor(ram, mario_x, registry=DEFAULT_REGISTRY):
    """docs/MECHANISMS.md section 1 / SPEC_odour.md sprint 016: every real
    (non-powerup) active enemy slot is an AVERSIVE odour source, same
    concentration ~ 1/distance formula as mushroom_odor/question_block_odor
    -- reuses enemy_thetas' own exclusion of powerup slots so a powerup
    never doubles as a threat. Returned by THE SIDE THE THREAT IS ON (R if
    d>=0, matching enemy_thetas' own convention) -- opposite-sign ROUTING
    into DNa01/DNa02 happens at the call site, not here, exactly mirroring
    how mushroom/qblock keep raw concentration separate from gain/routing.
    No gain, no hunger term applied here (this sprint's ODOUR_GAIN is reused
    at the call site; fleeing isn't hunger-gated the way foraging is)."""
    odor = {"L": 0.0, "R": 0.0}
    for rec in registry.enemy_records(ram):
        if not rec.active or rec.kind == EntityKind.POWERUP:
            continue
        d = rec.x - int(mario_x)
        conc = 1.0 / max(abs(d), 1)
        side = "R" if d >= 0 else "L"
        odor[side] += conc
    return odor


def hunger_multiplier(ram):
    """SPEC_odour.md section 2: RAM 0x0756==0 (small Mario) = hungry = the
    boosted odour gain; >=1 (big/fiery) = sated = the unboosted one."""
    return HUNGER_MULT_HUNGRY if int(ram[ADDR_MARIO_SIZE]) == 0 else HUNGER_MULT_SATED
