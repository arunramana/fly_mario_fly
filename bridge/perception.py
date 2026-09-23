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
"threat" channel. The profile is documentation; the gains come from
config.params.OdourParams.
"""

from __future__ import annotations

import numpy as np

from mario.entities.kinds import EntityKind
from mario.entities.registry import DEFAULT as DEFAULT_REGISTRY
from mario.ram import tile_ram
from mario.ram.addresses import ADDR_MARIO_SIZE
from config.params import OdourParams

_odour_params = OdourParams()
HUNGER_MULT_HUNGRY = _odour_params.hunger_mult_hungry  # RAM 0x0756==0 (small Mario)
HUNGER_MULT_SATED = _odour_params.hunger_mult_sated    # RAM 0x0756>=1 (big/fiery) -- unboosted, not zeroed


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
    covers both. Horizontal-only: it can pull Mario under a block, nothing
    more. Hitting it is left to the climb reflex, whose solid_ahead check
    excludes question tiles (they float overhead)."""
    odor = {"L": 0.0, "R": 0.0}
    for offset_tiles in tile_ram.question_blocks_near(ram):
        d = offset_tiles * 16
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


def hunger_multiplier(ram):
    """SPEC_odour.md section 2: RAM 0x0756==0 (small Mario) = hungry = the
    boosted odour gain; >=1 (big/fiery) = sated = the unboosted one."""
    return HUNGER_MULT_HUNGRY if int(ram[ADDR_MARIO_SIZE]) == 0 else HUNGER_MULT_SATED
