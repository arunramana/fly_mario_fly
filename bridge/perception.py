# What this file does, in plain English:
# Works out what Mario "sees" and "smells" from the game's memory, as input
# for the simulated fly brain. For the nearest enemy on each side it
# computes how big the enemy looks (as an angle) and how fast that grows. It
# also computes smells that weaken with distance: attractive ones from
# power-ups and "?" blocks, a repellent one from enemies, and a hunger boost.
"""bridge/perception.py -- what each entity looks and smells like to the
fly. The only module that reads mario/'s RAM and produces fly stimuli
(theta/dtheta, odour concentrations); fly/ never sees RAM.

Enemy slots are classified through mario.entities.registry, so each
function doesn't re-check POWERUP_ID itself. `question_block_odor` scans
tiles instead, a different data source (docs/ENTITIES.md).

bridge/profiles/default.json labels the odour channels: POWERUP and
QUESTION_BLOCK emit the hunger-gated "food" channel, ENEMY the un-gated
"threat" channel. Un-profiled (this file's original functions), the
profile is documentation only; the gains come from config.params.
OdourParams. C8a (docs/SPEC_entity_perception.md) adds profiled_
enemy_thetas/profiled_odor, which DO read the profile's per-kind
intensity/looming_salience/danger_weight numbers -- only reached when
FullPolicy is given entity_profiles=<EntityProfiles>, never by default.
"""

from __future__ import annotations

import numpy as np

from mario.entities.kinds import EntityKind
from mario.entities.registry import DEFAULT as DEFAULT_REGISTRY
from mario.ram import tile_ram
from mario.ram.addresses import ADDR_ENEMY_PAGE, ADDR_MARIO_PAGE, ADDR_MARIO_SIZE
from config.params import OdourParams
from bridge.entity_profiles import EntityProfiles

_odour_params = OdourParams()
HUNGER_MULT_HUNGRY = _odour_params.hunger_mult_hungry  # RAM 0x0756==0 (small Mario)
HUNGER_MULT_SATED = _odour_params.hunger_mult_sated    # RAM 0x0756>=1 (big/fiery) -- unboosted, not zeroed


def _dx(ram, slot, rec, mario_x, page_aware):
    """Enemy minus Mario, px. page_aware includes the page bytes, so an enemy
    just across a 256px page boundary is ahead, not ~230px behind."""
    if not page_aware:
        return rec.x - int(mario_x)
    return ((int(ram[ADDR_ENEMY_PAGE + slot]) * 256 + int(rec.x))
            - (int(ram[ADDR_MARIO_PAGE]) * 256 + int(mario_x)))


def enemy_thetas(ram, mario_x, prev_theta, registry=DEFAULT_REGISTRY, page_aware=False,
                 ignore_behind=False):
    """Nearest active THREAT's theta/dtheta per hemisphere. Enemies ahead of
    Mario (on-screen x >= mario_x) route Right; behind route Left -- our
    convention, SPEC doesn't fix one since retinotopy is skipped (section 2).
    Powerup-slot entities are skipped -- see mario.ram.addresses.POWERUP_ID's
    comment. `ignore_behind` (PagePerceptionParams, docs/SPEC_learning_v3.md A4): an enemy
    behind Mario (d < 0) produces no looming at all -- it is outside the frontal visual field, and
    theta computed from |d| otherwise keeps a receding enemy driving the left hemisphere."""
    theta = {"L": 0.0, "R": 0.0}
    d_out = {"L": None, "R": None}
    for slot, rec in enumerate(registry.enemy_records(ram)):
        if not rec.active or rec.kind == EntityKind.POWERUP:
            continue
        d = _dx(ram, slot, rec, mario_x, page_aware)
        if ignore_behind and d < 0:
            continue
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


def question_block_odor(ram, entity_width_px: int = 16):
    """SPEC_odour.md section 1: a second odour source at every `?` block
    tile_ram finds (0xC0 coin, 0xC1 power-up -- not distinguished, same as
    the mushroom not distinguishing power-up subtype). tile_ram.
    question_blocks_near returns signed TILE-COLUMN offsets relative to
    Mario, not pixels -- convert (*entity_width_px) before applying the
    same concentration formula and gain as the mushroom, so one gain
    constant covers both. Horizontal-only: it can pull Mario under a
    block, nothing more. Hitting it is left to the climb reflex, whose
    solid_ahead check excludes question tiles (they float overhead).

    `entity_width_px=16` is a reference default matching
    `config.entity.entity_width_px`'s own default (docs/CODE_AUDIT.md's
    "do not merge" section: this used to be a second, independent `16`
    literal under a different name; real callers with a config pass it
    explicitly, same pattern as fly/network/dynamics.py's ALPHA/CLIP)."""
    odor = {"L": 0.0, "R": 0.0}
    for offset_tiles in tile_ram.question_blocks_near(ram):
        d = offset_tiles * entity_width_px
        conc = 1.0 / max(abs(d), 1)
        side = "R" if d >= 0 else "L"
        odor[side] += conc
    return odor


def goomba_odor(ram, mario_x, registry=DEFAULT_REGISTRY):
    """docs/MECHANISMS.md section 1: every active non-powerup enemy is an
    AVERSIVE odour source, concentration ~ 1/distance. Returned by the side
    the threat is on (R if d>=0); the opposite-side routing into DNa01/DNa02
    and the gain are applied at the call site. No hunger term: fleeing is
    not hunger-gated the way foraging is."""
    odor = {"L": 0.0, "R": 0.0}
    for rec in registry.enemy_records(ram):
        if not rec.active or rec.kind == EntityKind.POWERUP:
            continue
        d = rec.x - int(mario_x)
        conc = 1.0 / max(abs(d), 1)
        side = "R" if d >= 0 else "L"
        odor[side] += conc
    return odor


def profiled_enemy_thetas(ram, mario_x, prev_theta, registry, profiles: EntityProfiles, page_aware=False,
                          ignore_behind=False):
    """C8a (docs/SPEC_entity_perception.md section 1.1): same as
    enemy_thetas, except each entity's raw angular size is scaled by its
    kind's `looming_salience * danger_weight` (the master-knob product)
    before the per-side max and before being stored for next frame's
    dtheta -- danger_weight is a per-kind master knob over BOTH looming
    and threat odour (profiled_odor below), looming_salience the
    per-sense knob on top of it. Clamped at pi: theta_raw is always < pi
    by construction (2*arctan(...) of any positive finite input), but a
    salience/danger product > 1.0 can push the scaled value past a
    physically meaningful half-angle. Only called when entity_profiles is
    not None -- enemy_thetas itself is untouched."""
    theta = {"L": 0.0, "R": 0.0}
    d_out = {"L": None, "R": None}
    for slot, rec in enumerate(registry.enemy_records(ram)):
        if not rec.active or rec.kind == EntityKind.POWERUP:
            continue
        d = _dx(ram, slot, rec, mario_x, page_aware)
        if ignore_behind and d < 0:
            continue
        side = "R" if d >= 0 else "L"
        ad = max(abs(d), 1)
        th_raw = 2.0 * np.arctan(rec.width / (2.0 * ad))
        profile = profiles.get(rec.kind)
        th = min(np.pi, th_raw * profile.looming_salience * profile.danger_weight)
        if th > theta[side]:
            theta[side] = th
            d_out[side] = d
    dtheta = {s: theta[s] - prev_theta[s] for s in ("L", "R")}
    return theta, dtheta, d_out


def profiled_odor(ram, mario_x, registry, profiles: EntityProfiles):
    """C8a (docs/SPEC_entity_perception.md sections 1.2/1.3): replaces
    mushroom_odor + question_block_odor (food) and goomba_odor (threat)
    with one per-entity, per-kind aggregation. For each active entity
    (every enemy-slot occupant, plus every `?`-block tile), each of its
    kind's odour-list entries contributes `intensity / max(|d|,1)` to a
    food sum (sign > 0) or `intensity * danger_weight / max(|d|,1)` to
    the threat sum (sign < 0; danger_weight has no meaning for a food
    channel and is not applied there). No hunger term on the threat
    side -- fleeing stays un-hunger-gated, as today.

    Returns (food_gated, food_ungated, threat): the food total is split
    by each entry's own `hunger_gated`, NOT pre-multiplied by hunger --
    the call site applies hunger to `food_gated` only, in one
    multiplication, same as the un-profiled functions' own
    `odor_gain_eff = odour_gain * hunger` convention. This split (rather
    than multiplying by hunger per-entry, in here) is what makes a
    profile whose entries are all hunger_gated -- true of every entry
    `bridge/profiles/default.json` ships today -- reproduce the old
    aggregate's floating-point operation order bit for bit: per-entry
    multiplication and a single combined multiplication are
    mathematically equal but not IEEE-754 identical, and the SPEC's own
    backward-compatibility test (section 2) checks for identical.

    Raw concentrations throughout -- no odour_gain applied here, same
    convention as the un-profiled functions. Only called when
    entity_profiles is not None."""
    # Entity-sourced and tile-sourced totals are accumulated as separate
    # running sums, combined only once at the end -- matching
    # mushroom_odor(...) + question_block_odor(...)'s own grouping
    # exactly, for the same bit-reproduction reason as the gated/ungated
    # split above.
    food_gated_entities = {"L": 0.0, "R": 0.0}
    food_gated_tiles = {"L": 0.0, "R": 0.0}
    food_ungated_entities = {"L": 0.0, "R": 0.0}
    food_ungated_tiles = {"L": 0.0, "R": 0.0}
    threat = {"L": 0.0, "R": 0.0}

    def add(kind, d, gated_bucket, ungated_bucket):
        side = "R" if d >= 0 else "L"
        ad = max(abs(d), 1)
        profile = profiles.get(kind)
        for odour in profile.odours:
            conc = odour.intensity / ad
            if odour.sign > 0:
                (gated_bucket if odour.hunger_gated else ungated_bucket)[side] += conc
            else:
                threat[side] += conc * profile.danger_weight

    for rec in registry.enemy_records(ram):
        if not rec.active:
            continue
        add(rec.kind, rec.x - int(mario_x), food_gated_entities, food_ungated_entities)

    for offset_tiles in tile_ram.question_blocks_near(ram):
        add(EntityKind.QUESTION_BLOCK, offset_tiles * 16, food_gated_tiles, food_ungated_tiles)

    food_gated = {s: food_gated_entities[s] + food_gated_tiles[s] for s in ("L", "R")}
    food_ungated = {s: food_ungated_entities[s] + food_ungated_tiles[s] for s in ("L", "R")}
    return food_gated, food_ungated, threat


def hunger_multiplier(ram, override: bool | None = None):
    """SPEC_odour.md section 2: RAM 0x0756==0 (small Mario) = hungry = the
    boosted odour gain; >=1 (big/fiery) = sated = the unboosted one.

    `override` (tool/PLAN.md C7): None (default) reads RAM as above. True
    forces hungry, False forces sated, independent of Mario's actual size
    -- a character-state control, not a RAM fact, so it never touches RAM
    itself. A science change when actually used (CLAUDE.md rule 3): it
    changes what the circuit does, not just what the tool displays."""
    if override is not None:
        return HUNGER_MULT_HUNGRY if override else HUNGER_MULT_SATED
    return HUNGER_MULT_HUNGRY if int(ram[ADDR_MARIO_SIZE]) == 0 else HUNGER_MULT_SATED
