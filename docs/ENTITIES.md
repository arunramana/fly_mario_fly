# Entities

REFACTOR_PLAN.md section 4's entity model, as actually built in phase 2 --
what exists, what it replaced, and what it deliberately doesn't cover yet.

## The model

`EntityRecord` (`mario/entities/record.py`) is a frozen dataclass: `kind`,
`x`, `y`, `width`, `height`, `active`, `traits`. No methods -- nes-py
simulates the game, this project only reads RAM (or, for a pit, the
absence of a tile), so an entity has no behaviour of its own to own.

`EntityKind` and `Trait` (`mario/entities/kinds.py`) are the vocabulary:
`GOOMBA`, `KOOPA`, `ENEMY`, `POWERUP`, `GROUND`, `QUESTION_BLOCK`,
`USED_BLOCK`, `EMPTY`, `PIT`, `SOLID_OTHER`. `GOOMBA`/`KOOPA` are real,
screenshot-verified species (phase 4, below); `ENEMY` is the fallback for
any enemy-slot occupant this project hasn't identified yet. Still coarser
than SMB's real cast -- see "What this model is NOT" below.

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

## Phase 4: species decoding -- what was verified, and how

REFACTOR_PLAN.md's phase-4 amendment (docs/REFACTOR_PLAN.md section 7)
asked for real per-species `EntityKind`s from `ADDR_ENEMY_TYPE`, "Goomba,
Koopa, and whatever else 1-1 and 1-2 actually contain" -- checked
empirically, not assumed from memory or a web table, the same standard
`mario/ram/tile_ram.py`'s own tile IDs were held to.

**Method.** The real circuit dies too early to see much of either level
(baseline: 1-1 dies at frame 689/x=1432; 1-2 at frame 84/x=184, both fully
deterministic at sigma=0 so every seed gives the identical trajectory --
seed only matters once sigma>0). A bot holding right and mashing jump on a
randomised duty cycle (bypassing the neural circuit entirely -- this is a
species census, not a circuit-behaviour test) was used instead to explore
much further into both levels across many simulated lives. Every distinct,
non-powerup `ADDR_ENEMY_TYPE` byte was logged at first sighting (frame,
level, on-screen position), and a screenshot was captured at that exact
frame for direct visual identification.

**Findings.** Two species confirmed, both screenshot-verified:

- **`0x06` = Goomba.** First seen 1-1 frame ~60 (the level's iconic first
  enemy, right where every SMB player expects it) and 1-2 frame 0.
  Screenshot shows the unmistakable brown, frowning mushroom shape at
  ground level.
- **`0x00` = Koopa Troopa.** First seen 1-2 frame ~338, in the underground
  section (screenshot shows two walking, shelled enemies; the underground
  palette recolours them, which is why they don't read as the usual
  green). This corroborates sprint 010's own independent, manual RAM-
  inspection identification of the same byte value as "Green Koopa
  Troopa" (docs/RUNS.md sprint 010) -- two separate identifications,
  different methods, same answer.

**1-1, as far as this project's own controllers can reach it, is entirely
Goombas.** Confirmed true for 1-1 -- the exact species-level scenario the
phase-3 amendment raised. **1-2 has both confirmed species** (a Goomba at
its very start, a Koopa in its underground section), but only past frame
~338, which today's baseline circuit doesn't survive to (it dies at frame
84 on 1-2 currently).

**Corrected, per the phase-3 amendment's own later correction
(REFACTOR_PLAN.md section 7): this is NOT a blocker for phase 6.** Phase
6's eligibility trace has a real two-class discriminable scenario with
differing outcomes on 1-1 alone already: the mushroom (appetitive, real
PAM->MBON reward pathway) versus an enemy (aversive, real PPL/PPM->MBON
punishment pathway, SPEC_mushroom_body.md/sprint 014) -- no species
decoding required. What this survey's one-class-on-1-1 finding actually
bears on is a RICHER, later experiment: whether the fly can learn a Goomba
is worse than a Koopa specifically. That experiment, if anyone builds it,
needs either a level-1-2 scenario that survives to the underground section
(a savestate starting there would work, matching sprint 013's own
savestate mechanism) or a different level entirely -- not 1-1 alone, which
this survey shows is genuinely one-species in practice. But nothing about
phase 6 itself depends on that richer experiment existing.

**A third type byte was found and deliberately NOT named.** `0x0D`
appeared further into 1-2 (abs_x~1400) during the same survey, but the
enemy scrolled off-screen before a screenshot could confirm it visually --
so it stays classified as generic `ENEMY`, not guessed from memory or a
table. This is the fallback design working exactly as intended: a real,
checked byte value without independent visual corroboration is reported
as "found, not yet identified," the same standard `tile_ram.py`'s own tile
IDs were held to, rather than silently named because a plausible guess
existed.

**Not exhaustive.** `species_survey.py`'s bot reached abs_x=1522 on 1-1
and abs_x=1941 on 1-2 (SMB 1-1 alone runs to roughly x=3160) before
running out of frame budget -- further than either level's full length.
More species may exist beyond that reach, or in 1-3 (this project's own
"invalid test level" per sprint 004/011 -- pits, not enemies). `ENEMY`
remains the correct, honest fallback for `0x0D` and any other byte this
survey didn't identify, rather than a guessed name.

## What this model is NOT (read before assuming more discrimination exists)

**Discrimination is possible, not switched on.** `bridge/perception.py`'s
`enemy_thetas`/`mushroom_odor`/`goomba_odor` still branch only on
`rec.kind == EntityKind.POWERUP` (or `!=`) -- exactly as before phase 4 --
so a Goomba and a Koopa still produce numerically identical looming and
odour contributions today. `bridge/profiles/default.json` now gives
`GOOMBA`/`KOOPA` distinct odour channels (`threat_goomba`/`threat_koopa`),
but nothing reads those channels separately yet; every non-powerup entity
still sums into one undifferentiated aversive signal (computed in
`bridge/full_policy.py`'s `FullPolicy.act()`).
Wiring a real per-species aggregate is live-behaviour work for whichever
phase actually needs it (phase 6, most likely), not this one.

**`ENEMY` still isn't every real SMB enemy.** Piranha Plant, Buzzy Beetle,
Hammer Bro, Lakitu, and anything else `ADDR_ENEMY_TYPE` can encode all
still fall back to generic `ENEMY` -- this project has verified exactly
two species, not SMB's full cast. REFACTOR_PLAN.md section 4's own worked
example (`GOOMBA`, `KOOPA`, `PIPE` as separate kinds with "Koopa has shell
state, Piranha is not stompable") still describes a richer model than
exists: shell state, stomp-vs-not, and every other real per-species
BEHAVIOUR difference remain unbuilt, only the KIND label itself is now
real for the two species this project has actually seen.

**Every earlier "avoided the Goomba" result in this log is really "avoided
the enemy" -- including this phase's own new evidence.** Every recorded
avoidance (006/008/016 and onward) was tested against whatever RAM put in
an enemy slot, never specifically a Goomba -- and this phase's own survey
confirms why that was actually fine on 1-1 (it's ALL Goombas there, in the
region any of those runs reached), while flagging that it would NOT be a
safe assumption on 1-2 past its underground section. The record should not
be read as claiming species-specific behaviour that was never actually
possible to produce, before or after this phase.

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
tested `EntityRecord`, but `FullPolicy.act()` (`bridge/full_policy.py`)
still calls `tile_ram.gap_width()` directly for the real long-jump/refusal
logic.
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
   `diag4.py`/`denormal_probe.py` in `scripts/`, never by the live game
   loop) was left alone -- consolidating
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
   *Since fixed in phase 4:* both files now read these values from the
   dataclasses in `config/params.py`.

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
  As of phase 4, `GOOMBA` and `KOOPA` each have their OWN channel
  (`threat_goomba`/`threat_koopa`) -- the discrimination the plan asked
  for is now expressible in data. The generic `ENEMY` fallback and
  `POWERUP`/`QUESTION_BLOCK` (sharing one `food` channel) still match what
  `FullPolicy.act()` (`bridge/full_policy.py`) actually computes today
  (`mush["R"] + qblock["R"]` summed before `ODOUR_GAIN`; `goomba_odor`
  kept separate but undifferentiated by species). See "Phase 4: species
  decoding" above for why the channels exist without yet being read.
- `looming_salience`, `danger_weight`, `is_food`, `body_scale`: present for
  every kind, matching the plan's `PerceptionProfile` shape, but **not**
  yet read by any live code path -- `bridge/full_policy.py` still computes
  looming/danger/hunger-gating from its own scalars and RAM reads directly.
  The file is read only by `tests/test_entities.py`.
  This file is documentation this phase, verified by
  `tests/test_entities.py` to cover every kind the registry can assign,
  not yet the runtime source of the numbers themselves. Making it that is
  per-component config extraction -- REFACTOR_PLAN.md phase 4.

## Enforcement

`tests/test_import_guard.py` parses (doesn't import) every `.py` file
under `fly/` and fails if any of them names `mario` or `bridge` in an
`import`/`from` statement. Verified to actually fail on a real violation,
not just pass trivially, before being kept (see the phase 2 commit).
