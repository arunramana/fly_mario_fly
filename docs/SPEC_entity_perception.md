# SPEC: per-kind entity perception (C8) — odour channels, valence,
# intensity, looming salience, and danger weight, read from a profile

Scopes `tool/PLAN.md` P6's C8: the first live use of the per-kind channels
`bridge/profiles/default.json` already documents but doesn't yet drive.
Read that file and `bridge/perception.py` before this SPEC — this document
proposes wiring what's already declared there, not inventing a new shape.

**This is a design document only. No C8 code lands until this SPEC is
approved.** Everything below is the proposal, not a completed sprint.

---

## 0. What's already true, and what this sprint actually changes

`bridge/profiles/default.json`'s own top comment says it plainly:
per-kind channels are *possible*, not *switched on* --
`bridge/perception.py`'s `goomba_odor` sums every active non-powerup
entity into one undifferentiated aversive signal regardless of species,
and the file's own gain/hunger numbers are documentation, not a runtime
input. This sprint is the one that makes the file the runtime source of
truth for four things it already names, plus one it doesn't yet have:

| Concept          | Where it lives today                          | What changes |
|------------------|------------------------------------------------|--------------|
| Odour channel    | `odours[].channel` (string, e.g. `"threat_goomba"`) | Becomes the runtime aggregation key, not just a label |
| Valence          | `odours[].sign` (`+1`/`-1`)                    | Already routes food vs. threat by convention; formalised as "valence" here |
| Intensity        | **doesn't exist yet**                          | **New field**: `odours[].intensity` (float, default `1.0`) |
| Looming salience | `looming_salience` (float, currently `1.0` or `0.0` for every kind) | Becomes a runtime multiplier on visual angle, not documentation |
| Danger weight    | `danger_weight` (float, currently `1.0`, `0.0`, or `1.0` for PIT) | Becomes a runtime multiplier on threat-odour concentration |

Everything in the right column is additive to the JSON schema (one new
field) or a new *consumer* of fields that already exist. Nothing in
`bridge/profiles/default.json`'s existing shape needs to change.

## 1. The three pathways this touches, and exactly how each one changes

`bridge/full_policy.py` computes three distinct signals from entity
records today (`full_policy.py:351,400-414`). Each gets its own,
independent per-kind multiplier — this sprint does not merge them into
one circuit input or add a new pathway into the network itself
(CLAUDE.md invariant 4: the circuit stays a fixed recurrent network; only
what it's *fed* changes).

### 1.1 Visual looming (`enemy_thetas` → LC4/LPLC2 → Giant Fiber, DNp02)

Today, `theta[side] = max` over every active non-powerup entity of
`2*arctan(width / (2*|d|))` — every kind's angular size counts equally
toward "how big does the nearest threat look."

**Proposed**: `theta_scaled = looming_salience(kind) * theta_raw`, and the
per-side max is taken over `theta_scaled`, which is also what's stored in
`self.prev_theta` and fed to `dtheta`/LC4/LPLC2 downstream. A kind with
`looming_salience > 1.0` reads as visually larger than its true angular
size (a species evolution gave the fly extra reason to flee from, even
at a distance); `looming_salience == 0.0` (this file's own convention for
POWERUP/QUESTION_BLOCK) means "never visually alarming."

**Backward compatibility**: every currently-defined threat kind
(GOOMBA/KOOPA/ENEMY) already has `looming_salience: 1.0`. With
`entity_profiles=None`, or with a profile whose values all match
`default.json`'s, `theta_scaled == theta_raw` for every frame — identical
telemetry to today, not just "close."

### 1.2 Food odour (`mushroom_odor` + `question_block_odor` → DNa01/DNa02)

Today: `conc = 1 / max(|d|, 1)` per source, summed, then
`* odour_gain * hunger` uniformly (`full_policy.py:400-405`) — hunger
gates the *whole* food channel, because both current food sources
(POWERUP, QUESTION_BLOCK) already have `hunger_gated: true`.

**Proposed**: `conc = intensity(kind, channel) / max(|d|, 1)`, still
summed per side, but hunger is now applied **per odour-list entry**
(`* hunger` only where that entry's `hunger_gated` is `true`), then the
whole sum is still scaled by `odour_gain` and passed through the same
`ORNAdaptation` instance as today.

**Backward compatibility**: POWERUP and QUESTION_BLOCK's only channel
(`"food"`) has `hunger_gated: true` today, and a default `intensity: 1.0`
reproduces `conc = 1/max(|d|,1)` exactly. With `entity_profiles=None`,
per-entry hunger gating collapses to today's uniform gating (there is
only one entry, and it's gated) — identical output.

### 1.3 Threat odour (`goomba_odor` → DNa01/DNa02, opposite routing)

Today: `conc = 1 / max(|d|, 1)` per active non-powerup entity, summed,
`* odour_gain` (no hunger term — `full_policy.py:410-411`).

**Proposed**: `conc = intensity(kind, channel) * danger_weight(kind) /
max(|d|, 1)`. `intensity` is the channel's own generic "how strong does
this smell" (shared machinery with the food pathway); `danger_weight` is
a *second*, independent multiplier specific to the aversive pathway — a
kind can smell faint but read as very dangerous up close, or vice versa.
These are deliberately two separate knobs, not one folded into the
other: `intensity` is a property of the smell itself (reusable by a
food-signed channel too, per 1.2), `danger_weight` is a property of how
the fly's escape system specifically weights that kind, and doesn't mean
anything for a food-signed channel. Threat channels currently have no
distinguished species-level odour behaviour beyond this, so a run that
sets every kind's `danger_weight` and `intensity` to `1.0` (today's
implicit values) reproduces `goomba_odor`'s current sum exactly. No
hunger term is added here — fleeing stays un-hunger-gated, as today.

**Backward compatibility**: GOOMBA/KOOPA/ENEMY's `danger_weight: 1.0` and
a default `intensity: 1.0` reproduce `conc = 1/max(|d|,1)` per entity.

## 2. `entity_profiles`: the opt-in switch

New parameter threaded exactly like C5's `shuffle_seed` and C7's
`hunger_override` (`bridge/full_policy.py`'s existing pattern) —
`FullPolicy.__init__(..., entity_profiles=None)`, plumbed through
`run_steering.main()` and `sim/project_runner.run_from_config()`.

- **`entity_profiles=None` (default): behaves exactly as today.** The
  three call sites in `full_policy.py` keep calling
  `enemy_thetas`/`mushroom_odor`/`question_block_odor`/`goomba_odor`
  completely unchanged — this sprint does not touch those functions'
  existing signatures or behaviour when profiles are off. This is the
  literal meaning of "opt-in," not "opt-in but slightly different math
  when off": the no-profile code path is the same code, not new code
  that happens to compute the same numbers.
- **`entity_profiles=<EntityProfiles object>`**: a new code path
  (proposed: `bridge/perception.py`'s new `profiled_odor()` and
  `profiled_thetas()`, or equivalent) activates, doing the per-kind math
  in section 1. This is the only path new tests need to cover for
  correctness; the `None` path only needs a test that it's *unreached*
  (e.g. a profile object that would change telemetry if consulted, and a
  byte-identical-to-today assertion when `entity_profiles=None`).

`EntityProfiles` (proposed, `tool/core/` or `bridge/`): loads
`bridge/profiles/default.json` plus an optional per-project override,
deep-merged **per kind, per field** — an override file that only
mentions `GOOMBA.danger_weight` leaves every other kind and every other
GOOMBA field (its channel, sign, looming_salience, KOOPA's whole entry,
etc.) exactly as `default.json` has it. No override file present is the
same as `entity_profiles=None` upstream of this merge — the merge step
itself never invents defaults beyond what `default.json` already states.

## 3. The per-project override file

**`projects/<name>/entity_profiles.json`** — a new file, sibling to
`config.json`/`tool.json`, not a new key inside either. Same shape as
`bridge/profiles/default.json`, but every kind and every field is
optional; anything omitted falls back to the shipped default. Example
overriding only GOOMBA's danger weight and adding an `intensity` to its
one odour channel:

```json
{
  "GOOMBA": {
    "odours": [
      {"channel": "threat_goomba", "sign": -1, "hunger_gated": false, "intensity": 1.4}
    ],
    "danger_weight": 2.0
  }
}
```

Absent file (the common case, and every project created before this
sprint): `EntityProfiles.load(project_root)` returns the equivalent of
loading `default.json` alone, or `None` if the tool's own
`entity_profiles` toggle is off (`tool/core/tool_settings.py`'s
`CircuitSettings`-style `None`-by-default pattern, matching
`hunger_override: bool | None = None`) — the file existing is not itself
what turns the feature on; the tool setting is, same as every other C-
numbered control in this project (ground rule 4: no control lies, no
control turns itself on by the mere presence of a file).

**Note for `tool/PLAN.md`'s own P6 bullet**: it currently reads "entity-
profile editor in tabs 2–3 writing `projects/<name>/tool.json`." This
SPEC proposes a dedicated `entity_profiles.json` instead, for the same
reason `config.json`/`tool.json` are already two files rather than one:
a profile table (9 kinds × several fields) is a different shape of data
than `ToolSettings`' flat per-tab dataclasses, and mixing them would make
`tool.json` a dumping ground. If approved, P6's bullet should be
corrected to match this SPEC rather than the SPEC silently drifting from
the plan.

## 4. Hand-set scalars this sprint introduces (CLAUDE.md invariant 3)

`intensity` is a new field, so it introduces new hand-set numbers — the
invariant's "no fixed budget, but everything flagged and counted" applies
even though these live in a JSON profile table, not
`config/params.py`'s flat dataclasses (a per-kind table doesn't fit that
shape, same reason `bridge/profiles/default.json`'s existing
`looming_salience`/`danger_weight` aren't in `config/params.py` today
either). Proposed accounting: every non-empty-odour kind's `intensity`
default (5 kinds ship a channel today -- GOOMBA, KOOPA, ENEMY, POWERUP,
QUESTION_BLOCK, one odour entry each -- so 5 new values, all `1.0`) gets
a `_note` in
`bridge/profiles/default.json` exactly like `looming_salience`/
`danger_weight` already have, and a row added to `docs/SCALARS.md`'s own
accounting (or a new "profile scalars" section in it, if the existing
table's shape doesn't fit a per-kind field) — the point is that the
number is written down and its provenance stated (`invented, default
1.0, matches today's implicit behaviour`), not that it lives in one
specific file format.

## 5. The shuffled-connectome control (CLAUDE.md invariant 6)

This feature changes what's *fed into* the circuit, not the circuit
itself — so the shuffled-connectome control doesn't change shape, but it
is still required as part of this sprint's own validation, not assumed
to still be meaningful by inheritance from C5. **The deliverable run (section
7) must be a pair, same seed, same profile**: one against the real
connectome, one against `shuffle_seed`-rebuilt weights (C5's existing
mechanism, untouched). If per-kind odour differentiation produces a
behavioural difference (e.g. Mario reacting differently to a
`danger_weight`-boosted Goomba than a KOOPA at the same distance) under
the real connectome but *not* under the shuffled one, that's the
evidence the fly's actual wiring — not just the new per-kind gain
numbers — is doing the discriminating. If the shuffled run shows the
same difference, the finding is honestly "the gain numbers alone explain
this, the connectome's structure doesn't," and the writeup must say so.

## 6. Tool UI scope (tabs 2–3)

Out of scope for *this* SPEC to fully design (a GUI layout decision, not
a perception-pipeline one) but the shape this sprint's perception layer
must support: tabs 2 (Enemies) and 3 (Objects) get a per-kind form (one
group box per `EntityKind`, mirroring `bridge/profiles/default.json`'s
structure) that reads/writes `projects/<name>/entity_profiles.json`
through the merge-with-defaults logic in section 2 — greyed out today
per `tool/core/wiring.py`'s `enemies.smell_profile: NOT_WIRED`, promoted
to `live` only once a test proves changing a value there changes
telemetry (ground rule 4), same bar every other control in this project
has cleared.

## 7. Deliverable

- `bridge/profiles/default.json`: add `intensity` (default `1.0`) to
  every existing `odours[]` entry, with a `_note` matching the existing
  style.
- `bridge/perception.py`: new profile-aware odour/theta functions
  (exact names TBD at implementation time), the existing
  `enemy_thetas`/`mushroom_odor`/`question_block_odor`/`goomba_odor`
  untouched.
- `bridge/full_policy.py`: `entity_profiles=None` constructor param,
  threaded through the three call sites in section 1, `None` path
  provably unchanged (a test asserting the exact same function objects
  are called, or byte-identical telemetry against a pre-sprint golden).
- A new `EntityProfiles` load/merge module (`bridge/` or `tool/core/`,
  whichever ends up cleaner given section 3's file location) with a test
  covering: load with no override (== `default.json` alone), load with a
  partial override (unmentioned kinds/fields fall back correctly), and
  the `None`-means-off top-level switch.
- `tests/test_c8_entity_profiles.py`: `entity_profiles=None` reproduces
  today's telemetry byte-for-byte (a golden-style test, same bar as C10's
  own regression test); a profile that changes one kind's
  `danger_weight` changes telemetry relative to the all-`1.0` baseline.
- Two recorded runs at the same seed, real vs. shuffled connectome (section
  5), with a profile that gives at least one kind a non-default
  `danger_weight` or `intensity` so the comparison has something to show —
  `projects/<name>/runs/NNN{a,b}_*.mp4` plus their `.md` notes, and a
  `docs/RUNS.md` entry stating plainly whether the connectome's structure
  or the raw gain numbers explain what changed (section 5).
- `docs/SCALARS.md` (or its own new section) updated per section 4.
- `tool/PLAN.md` P6 bullet corrected if section 3's file-location
  proposal is approved as written.

## 8. Explicitly out of scope

- Tab 2/3 UI implementation (section 6 states the shape it must support;
  building it is its own pass once this SPEC and the perception-layer
  code it describes both exist).
- C9 (arousal, `character.arousal_pc1`) — a different control, no SPEC of
  its own yet, not touched here.
- Any change to `dynamics.py`, `circuit.py`, or the recurrent network's
  own structure (invariant 4) — every change here is upstream of the
  network, in what's computed to feed it.
- Retinotopic placement of per-kind odour sources — `enemy_thetas`'s
  retinotopic branch (`full_policy.py:361-372`) already handles azimuth
  for the visual pathway; extending retinotopy to the *odour* pathways
  is a separate, later question this SPEC doesn't answer.
- Learning / mushroom-body interaction with per-kind odour (a kind-
  specific eligibility trace) — flagged in `bridge/profiles/
  default.json`'s own comment as "phase 6's own eligibility-trace
  territory"; this SPEC's phase 6 is perception only, not learning.
