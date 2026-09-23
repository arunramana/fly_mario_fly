# Entities

REFACTOR_PLAN.md section 4's entity model, as actually built in phase 2 --
what exists, what it replaced, and what it deliberately doesn't cover yet.

## The model

`EntityRecord` (`mario/entities/record.py`) is a frozen dataclass: `kind`,
`x`, `y`, `width`, `height`, `active`, `traits`. No methods -- nes-py
simulates the game, this project only reads RAM (or, for a pit, the
absence of a tile), so an entity has no behaviour of its own to own.

`EntityKind` and `Trait` (`mario/entities/kinds.py`) are the vocabulary:
`ENEMY`, `POWERUP`, `GROUND`, `QUESTION_BLOCK`, `USED_BLOCK`, `EMPTY`,
`PIT`, `SOLID_OTHER`. This is coarser than SMB's real cast -- see "What
this model is NOT" below.

`KindRegistry` (`mario/entities/registry.py`, one shared instance,
`DEFAULT`) is the single home the plan asked for: `enemy_kind()`/
`enemy_record()`/`enemy_records()` classify an enemy slot from
`ADDR_ENEMY_TYPE`; `tile_kind()` gives a named view onto tile_ram.py's own
tile-id constants; `pit_record()` synthesises a `PIT` record from
`tile_ram.gap_width()`.

## What actually changed behaviourally: none. What changed structurally.

Three real call sites -- `bridge/perception.py`'s `enemy_thetas`,
`mushroom_odor`, `goomba_odor` -- used to each write their own
`ram[ADDR_ENEMY_TYPE + i] == POWERUP_ID` (or `!=`) comparison independently.
They now all call `registry.enemy_records(ram)` and branch on
`rec.kind == EntityKind.POWERUP`. Same RAM byte, same comparison, same
`EntityRecord.width` value (`ENTITY_WIDTH_PX = 16`, exactly the `W_TILE`
constant every one of these functions already used) -- verified
byte-identical against `tests/golden/` before and after.

## What this model is NOT (read before assuming more discrimination exists)

**`ENEMY` is not "Goomba."** `ADDR_ENEMY_TYPE` is read in exactly one way
anywhere in this codebase, before or after this phase: is it the powerup ID
or not. A Goomba, a Green Koopa Troopa and a Piranha Plant are the same
`EntityKind.ENEMY`, with the same traits, the same width, the same odour
channel -- not because they're alike, but because no pathway in this
project has ever looked past that one bit. REFACTOR_PLAN.md section 4's own
worked example (`GOOMBA`, `KOOPA`, `PIPE` as separate kinds with "Koopa has
shell state, Piranha is not stompable") describes a richer model than the
one that exists to move. Building that richer model is new behaviour, not a
move, and is out of phase-2's "zero logic edits" scope.

**Every entity is 16px wide, always.** `ENTITY_WIDTH_PX` is a single
constant applied to every enemy-slot kind. Real Goombas, Koopas and
mushrooms don't share a hitbox width in SMB; this project has simply never
modelled the difference (`run_mario.py`'s old `W_TILE` and `sensory.py`'s
own `W_TILE` already carried this same flattening, independently, before
this phase).

**`QUESTION_BLOCK` doesn't go through `EntityRecord`.** It's a genuinely
different data source -- a tile-buffer scan, not an enemy slot -- and
`bridge/perception.py`'s `question_block_odor` still reads `tile_ram`
directly. `KindRegistry.tile_kind()` exists and is tested
(`tests/test_entities.py`), but nothing wires it into that call site yet.
A real scoping decision, not an oversight: unifying it would touch the
tile-scanning hot path for no behavioural gain this phase.

**`pit_record()` isn't in the decision loop.** It builds a correct,
tested `EntityRecord`, but `run_steering.py`'s `main()` still calls
`tile_ram.gap_width()` directly for the real long-jump/refusal logic.
Wiring `pit_record()` into that state machine is deferred.

**Pipe tiles (`0x10`-`0x15`) have no dedicated kind.** Confirmed in
`tile_ram.py`'s own docstring (cross-checked against SMBDIS.ASM and a live
screenshot), but no code path has ever branched on them separately from
ground/brick -- `solid_ahead()` treats them all as one undifferentiated
wall. `KindRegistry.tile_kind()` folds them into `SOLID_OTHER` rather than
inventing a `PIPE` kind nothing consumes.

## ROM facts found duplicated or inconsistently treated, building this

Per REFACTOR_PLAN.md phase 2's request to report this separately -- these
are the actual findings, not just the POWERUP_ID one already described
above:

1. **The same `POWERUP_ID` classification, written independently three
   times**: `run_mario.py`'s `enemy_thetas`, `run_steering.py`'s
   `mushroom_odor`, `run_steering.py`'s `goomba_odor`. Identical
   comparison, identical RAM addresses, never factored out until this
   phase. This is the headline finding -- it's exactly the shape of
   duplication `KindRegistry` exists to remove.

2. **Two RAM addresses were never named constants at all**: Mario's own Y
   (`0x00B5`) and the enemy-slot Y array (`0x00B6`), both documented in
   `docs/SPEC_jump.md`'s own RAM table, both used only as bare literals in
   `run_steering.py` (`mario_y = int(ram[0x00B5])`, `ram[0x00B6 + slot] =
   ...`). Named `ADDR_MARIO_Y`/`ADDR_ENEMY_Y` in
   `mario/ram/addresses.py` this phase, values unchanged.

3. **`W_TILE = 16.0` was defined independently, with the same value, in
   two unrelated files** (`run_mario.py` and `sensory.py`) before this
   phase -- not a bug (both copies agree), but the same "nobody's fact"
   pattern the plan's section 4 warns about. Registry's `ENTITY_WIDTH_PX`
   is now the one definition the enemy-classification path uses;
   `sensory.py`'s own copy (used only by offline diagnostics, `tune.py`/
   `diag4.py`, never by the live game loop) was left alone -- consolidating
   it isn't required for this phase's behaviour-preservation goal and
   would touch diagnostic scripts for no functional gain.

4. **The jump circuit's own hand-set scalars live somewhere different
   from every other circuit's.** `G`, `DNP01_SPIKE_THRESHOLD`,
   `SPIKE_AMP`, `TTMN_PRESS_THRESHOLD` are defined in `run_mario.py`;
   `G_STEER`, `G_TAKEOFF`, `G_SPEED`, `G_MDN`, `G_DNP02`, `KC_SPARSITY`,
   etc. are all defined directly in `run_steering.py`. Not a bug -- every
   number is still exactly one hand-set scalar, CLAUDE.md invariant 3 is
   unaffected -- but it's a real inconsistency in *where* a circuit's
   config lives, the kind of thing REFACTOR_PLAN.md phase 4 (per-component
   config extraction) exists to fix uniformly. Flagged, not fixed here.

5. **Pipe metatiles are a confirmed, verified ROM fact that was never
   given a name** -- see "What this model is NOT" above. Not a
   duplication; the opposite problem, a fact that's real and checked but
   was never centralised anywhere because nothing needed it to be.

## Perceptual profiles

`bridge/profiles/default.json`, one entry per `EntityKind` (except `EMPTY`
-- the absence of a tile, not an entity). Each entry documents:

- `odours`: a **list** of labelled channels (REFACTOR_PLAN.md section 4:
  "Odour must be a list of labelled channels, not a scalar... the only way
  'a Goomba smells bad and a Koopa smells bad differently' is expressible").
  Today every `ENEMY` shares one `threat` channel and `POWERUP`/
  `QUESTION_BLOCK` share one `food` channel -- because that's what
  `run_steering.py`'s `main()` actually computes (`mush["R"] + qblock["R"]`
  summed into one signal before `ODOUR_GAIN`; `goomba_odor` kept
  separate). The list shape is what would let a future, real per-species
  channel exist; nothing here fabricates one that doesn't.
- `looming_salience`, `danger_weight`, `is_food`, `body_scale`: present for
  every kind, matching the plan's `PerceptionProfile` shape, but **not**
  yet read by any live code path -- `run_steering.py` still computes
  looming/danger/hunger-gating from its own scalars and RAM reads directly.
  This file is documentation this phase, verified by
  `tests/test_entities.py` to cover every kind the registry can assign,
  not yet the runtime source of the numbers themselves. Making it that is
  per-component config extraction -- REFACTOR_PLAN.md phase 4.

## Enforcement

`tests/test_import_guard.py` parses (doesn't import) every `.py` file
under `fly/` and fails if any of them names `mario` or `bridge` in an
`import`/`from` statement. Verified to actually fail on a real violation,
not just pass trivially, before being kept (see the phase 2 commit).
