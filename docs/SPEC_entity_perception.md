# SPEC: per-kind entity perception, phase a (C8a) — gains, not new channels

Scopes `tool/PLAN.md` P6's C8: the first live use of the per-kind fields
`bridge/profiles/default.json` already documents but doesn't yet drive.
Read that file and `bridge/perception.py` before this SPEC — this document
proposes wiring what's already declared there, not inventing a new shape.

**Approved, revised draft.** `entity_profiles.json` as a dedicated
per-project file (section 3) is settled; `tool/PLAN.md`'s P6 bullet is
updated to match (section 9). Tabs 2–3 are in scope for this sprint
(section 6). C8a's perception-layer code, tab UI, and validation batch
are the deliverable (section 7).

---

## 0. C8a vs. C8b — name the boundary up front

This SPEC is **C8a: per-kind gains on the two aggregate signals that
already exist** (one food concentration, one threat concentration, one
visual angle, per hemisphere). No new circuit input, no new channel
reaching the connectome as a distinct receptor population — every change
here is a multiplier on numbers `bridge/full_policy.py` already computes
and feeds into the same DNa01/DNa02/LC4/LPLC2 populations as today.

**C8b (future work, no SPEC yet): separate channels mapped to distinct
connectome receptor populations** — e.g. an actual `threat_goomba`
channel driving one real ORN population and `threat_koopa` driving a
different one, so species discrimination is a property of *which
neurons fire*, not *how hard one shared population is driven*. That is a
materially bigger change (new wiring into the network, a real question
about which of MaleCNS's populations correspond to which odour, CLAUDE.md
invariant 4 in a much sharper way) and is explicitly not this sprint's
scope. `bridge/profiles/default.json`'s `channel` strings
(`"threat_goomba"` vs. `"threat_koopa"`) already anticipate C8b's
labelling; C8a does not consume the distinct label, only `sign`,
`intensity`, `looming_salience`, and `danger_weight` — a reader should
not infer species-distinct wiring from this sprint's use of
already-distinct channel names.

`bridge/profiles/default.json`'s own top comment says the same thing
plainly: per-kind channels are *possible*, not *switched on* —
`bridge/perception.py`'s `goomba_odor` sums every active non-powerup
entity into one undifferentiated aversive signal regardless of species.
C8a makes the file's numbers the runtime source of truth for four
things it already names, plus one new field:

| Concept          | Where it lives today                          | What C8a changes |
|------------------|------------------------------------------------|--------------|
| Odour channel    | `odours[].channel` (string)                    | Read as a label only (C8b territory to consume as a distinct wire) |
| Valence          | `odours[].sign` (`+1`/`-1`)                    | Already routes food vs. threat by convention; formalised as "valence" here |
| Intensity        | **doesn't exist yet**                          | **New field**: `odours[].intensity` (float, default `1.0`) — a per-sense knob |
| Looming salience | `looming_salience` (float, currently `1.0` or `0.0`) | A per-sense knob on visual angle |
| Danger weight     | `danger_weight` (float, currently `1.0`, `0.0`, or `1.0` for PIT) | **A per-kind master knob**, multiplying both senses (section 1) |

## 1. The master-knob structure

**`danger_weight` is a per-kind master knob over both looming and threat
odour; `intensity` and `looming_salience` are the per-sense knobs
underneath it.** Concretely, for a kind `k`:

```
looming_multiplier(k) = looming_salience(k) * danger_weight(k)
threat_odour_multiplier(k, channel) = intensity(k, channel) * danger_weight(k)
```

The idea: `danger_weight` answers "how dangerous is this kind, overall,"
and moves both senses together — a kind the fly should generally treat
as more dangerous gets both a bigger-looking silhouette and a stronger
threat smell from the same one dial. `looming_salience` and `intensity`
then let a kind's *sensory profile* deviate from that baseline
independently per sense: a fast, small, low-visual-salience threat that
still smells strong (`danger_weight` high, `looming_salience` low,
`intensity` high), or a visually striking but faint-smelling one, without
needing two separate "how dangerous" numbers that could drift apart from
each other for no biological reason. `intensity` alone (no `danger_weight`
multiplier) governs food-signed channels, where "how dangerous" has no
meaning — see 1.2.

`bridge/full_policy.py` computes three distinct signals from entity
records today (`full_policy.py:351,400-414`). Each gets this structure
applied independently — this sprint does not merge them into one circuit
input or add a new pathway into the network itself (CLAUDE.md invariant
4: the circuit stays a fixed recurrent network; only what it's *fed*
changes).

### 1.1 Visual looming (`enemy_thetas` → LC4/LPLC2 → Giant Fiber, DNp02)

Today, `theta[side] = max` over every active non-powerup entity of
`2*arctan(width / (2*|d|))` — every kind's angular size counts equally
toward "how big does the nearest threat look."

**Proposed**:

```
theta_scaled = min(pi, looming_salience(k) * danger_weight(k) * theta_raw)
```

per-side max taken over `theta_scaled`, which is also what's stored in
`self.prev_theta` and fed to `dtheta`/LC4/LPLC2 downstream. **Clamped at
`pi`**: `theta_raw` is a geometric half-angle and is always `< pi` by
construction (`2*arctan(...)` for any positive finite input), but a
salience/danger multiplier `> 1.0` can push the scaled value past a
physically meaningful angle — an angle above `pi` doesn't correspond to
anything a visual system could report, so it's clamped, not left to grow
unbounded. A kind with a high master/looming product reads as visually
larger than its true angular size, up to that ceiling.

**Backward compatibility**: every currently-defined threat kind
(GOOMBA/KOOPA/ENEMY) has `looming_salience: 1.0` and `danger_weight:
1.0`, so `theta_scaled == theta_raw` for every frame — identical
telemetry to today, and the clamp is inactive at these values (`theta_raw
< pi` always).

### 1.2 Food odour (`mushroom_odor` + `question_block_odor` → DNa01/DNa02)

Today: `conc = 1 / max(|d|, 1)` per source, summed, then
`* odour_gain * hunger` uniformly (`full_policy.py:400-405`) — hunger
gates the *whole* food channel, because both current food sources
(POWERUP, QUESTION_BLOCK) already have `hunger_gated: true`.

**Proposed**: `conc = intensity(k, channel) / max(|d|, 1)` (no
`danger_weight` term — it has no meaning for a `sign > 0` channel), still
summed per side, but hunger is now applied **per odour-list entry**
(`* hunger` only where that entry's `hunger_gated` is `true`), then the
whole sum is still scaled by `odour_gain` and passed through the same
`ORNAdaptation` instance as today.

**Backward compatibility**: POWERUP and QUESTION_BLOCK's only channel
(`"food"`) has `hunger_gated: true` today, and a default `intensity: 1.0`
reproduces `conc = 1/max(|d|,1)` exactly.

### 1.3 Threat odour (`goomba_odor` → DNa01/DNa02, opposite routing)

Today: `conc = 1 / max(|d|, 1)` per active non-powerup entity, summed,
`* odour_gain` (no hunger term — `full_policy.py:410-411`).

**Proposed**: `conc = intensity(k, channel) * danger_weight(k) /
max(|d|, 1)`. No hunger term is added here — fleeing stays un-hunger-
gated, as today.

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
  existing signatures or behaviour when profiles are off. The no-profile
  code path is the same code, not new code that happens to compute the
  same numbers.
- **`entity_profiles=<EntityProfiles object>`**: a new code path
  (`bridge/perception.py`'s new `profiled_enemy_thetas()` and
  `profiled_odor()`) activates, doing the per-kind math in section 1.

**Two required backward-compatibility tests, not one** (this is
stronger than "looks close"):

1. `entity_profiles=None` reproduces today's telemetry byte-for-byte
   (the old functions are provably still what's called).
2. `entity_profiles=<EntityProfiles loaded from default.json alone, no
   override>` **also** reproduces today's telemetry byte-for-byte — i.e.
   the *new* code path, fed nothing but today's implicit defaults, is
   numerically neutral, not just "close in spirit." This is the test
   that actually proves section 1's formulas collapse to today's at
   `intensity = looming_salience = danger_weight = 1.0`, rather than
   asserting it from the algebra alone.

`EntityProfiles` (`bridge/entity_profiles.py`): loads
`bridge/profiles/default.json` plus an optional per-project override,
merged **per kind, per field** — an override file that only mentions
`GOOMBA.danger_weight` leaves every other kind, and every other GOOMBA
field, exactly as `default.json` has it. Overriding a kind's `odours`
list replaces that kind's whole list (a partial single-field tweak to
one odour entry restates that entry in full) — merging list elements by
position or channel name is not attempted, to avoid an ambiguous partial-
list-merge rule.

## 3. The per-project override file

**`projects/<name>/entity_profiles.json`** — a new file, sibling to
`config.json`/`tool.json`, not a new key inside either (approved; see
section 9). Same shape as `bridge/profiles/default.json`, but every kind
and every field is optional; anything omitted falls back to the shipped
default. Example overriding GOOMBA's danger weight and its one odour
channel's intensity — this exact profile is also what section 5's
validation batch uses as "modified":

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
`entity_profiles` toggle is off (`tool/core/tool_settings.py`, a new
`EntityProfileSettings.enabled: bool = False`, same opt-in-by-default
shape as every other C-numbered control) — the file existing is not
itself what turns the feature on; the tool setting is (ground rule 4: no
control lies, no control turns itself on by the mere presence of a
file).

## 4. Hand-set scalars this sprint introduces (CLAUDE.md invariant 3)

`intensity` is a new field, so it introduces new hand-set numbers — the
invariant's "no fixed budget, but everything flagged and counted" applies
even though these live in a JSON profile table, not
`config/params.py`'s flat dataclasses (a per-kind table doesn't fit that
shape, same reason `bridge/profiles/default.json`'s existing
`looming_salience`/`danger_weight` aren't in `config/params.py` today
either). **Not `docs/SCALARS.md`**: that file is machine-generated
exclusively from `config/params.py` and byte-checked against it
(`tests/test_scalars_doc.py`) — a hand-written addition there would
either break that test or be silently erased by the next regeneration.
Every non-empty-odour kind's `intensity` default (5 kinds ship a channel
today — GOOMBA, KOOPA, ENEMY, POWERUP, QUESTION_BLOCK, one odour entry
each — so 5 new values, all `1.0`) gets a `_note` in
`bridge/profiles/default.json` matching the existing style (provenance:
`invented, default 1.0, matches today's implicit behaviour`), and
`docs/ENTITIES.md`'s own "Perceptual profiles" section — the doc that
already tracks this file's provenance — is updated to say the fields are
now live, not just documentation.

## 5. Validation: a 2×2 batch, prediction stated before running it

**Not a single real-vs-shuffled pair.** A single pair at one seed can't
distinguish "the gain numbers changed the outcome" from "the connectome's
structure interacted with them" — both would produce *some* visible
difference from a baseline run, and a single comparison can't attribute
which. The design: **{real, shuffled} × {default profile, modified
profile}**, at least **8 seeds** per cell, `config.noise.sigma > 0`
(e.g. `0.05`, inside `NoiseParams.sigma`'s own measured range) so
multiple seeds under the same condition actually differ — a single
noiseless seed per cell would make "spread across seeds" meaningless.
"Modified profile" is section 3's example (GOOMBA `danger_weight: 2.0`,
`intensity: 1.4`).

**Prediction, stated before running anything**: because C8a is a gains-
only change (section 0 — no new wiring, no new receptor population, the
same DNa01/DNa02/LC4/LPLC2 populations as today), **the gap between
default-profile and modified-profile outcomes should be approximately
the same size under the real connectome and the shuffled one.** A gains-
only change doesn't give the network anything new to discriminate with;
it changes the size of a number the network already receives, and a
bigger/smaller input should move the same fixed dynamical system by a
similar amount regardless of whether its recurrent weights are the real
or shuffled ones. If the real-vs-shuffled gap in "how much the profile
mattered" turns out to be large, that is the surprising result — it
would mean the connectome's specific structure amplifies or damps a
species-specific gain non-linearly, which C8a's own design doesn't
predict and would be worth its own follow-up. Report whichever outcome
actually happens; a confirmed prediction and a falsified one are both a
finding (this project's own CLAUDE.md log convention — a log that
records only successes teaches nothing).

Metrics per cell (aggregated over the ≥8 seeds): survival rate, mean
`max_x_abs`, mean fitness (`tool/core/fitness.py`'s existing weights),
and the aversive-odour-specific counters `run_steering.py` already
tracks (`odour avoids`, escape jump count). Report mean ± spread (e.g.
min/max or stdev) per cell, and the two differences that actually test
the prediction: `(modified − default)` under real, and `(modified −
default)` under shuffled — the SPEC's claim is that these two
differences are close to each other.

## 6. Tool UI scope (tabs 2–3) — in scope for this sprint

Tabs 2 (Enemies: GOOMBA, KOOPA, ENEMY) and 3 (Objects: POWERUP,
QUESTION_BLOCK, GROUND, USED_BLOCK, SOLID_OTHER, PIT) get a per-kind form,
one group box per `EntityKind`, mirroring
`bridge/profiles/default.json`'s structure (odour channel/valence/
intensity per entry, looming salience, danger weight), reading/writing
`projects/<name>/entity_profiles.json` through section 2/3's merge logic,
plus the `EntityProfileSettings.enabled` toggle (section 3).

**Greyed, not editable**: **PIT** (`default.json`'s own note: "not yet a
call site in main()'s decision loop" — editing a profile nothing reads
would be a control that lies) and the **terrain kinds** GROUND,
USED_BLOCK, SOLID_OTHER (`odours: []`, `looming_salience: 0.0`,
`danger_weight: 0.0` — no odour list to edit and no live consumer of
their looming/danger fields either, since they never appear in
`registry.enemy_records()` or the odour/looming call sites section 1
touches). GOOMBA, KOOPA, ENEMY, POWERUP, and QUESTION_BLOCK are the five
kinds this sprint's perception layer actually reads (section 1/4) and
are the only ones live-editable.

`tool/core/wiring.py`'s `enemies.smell_profile: NOT_WIRED` is promoted to
`live` only once a test proves changing a value in this editor changes
telemetry (ground rule 4), same bar every other control in this project
has cleared.

## 7. Deliverable

- `bridge/profiles/default.json`: add `intensity` (default `1.0`) to
  every existing `odours[]` entry, with a `_note` matching the existing
  style.
- `bridge/entity_profiles.py`: `EntityProfiles`/`KindProfile`/
  `OdourChannel` + `load(project_root=None)` (default-only or
  default-merged-with-override), with tests covering: load with no
  override, load with a partial override (unmentioned kinds/fields fall
  back correctly), and an unknown kind name in an override file raising
  loudly rather than being silently ignored (a typo in an override
  should not silently no-op).
- `bridge/perception.py`: `profiled_enemy_thetas()`, `profiled_odor()`
  (section 1); the existing `enemy_thetas`/`mushroom_odor`/
  `question_block_odor`/`goomba_odor` untouched.
- `bridge/full_policy.py`: `entity_profiles=None` constructor param,
  threaded through the three call sites in section 1.
- `run_steering.py` / `sim/project_runner.py`: `entity_profiles` threaded
  through, matching `shuffle_seed`/`hunger_override`'s existing pattern.
- `tests/test_c8a_entity_profiles.py`: the two backward-compatibility
  tests in section 2 (byte-identical with `None`, byte-identical with an
  all-default `EntityProfiles`); a profile that changes one kind's
  `danger_weight` changes telemetry relative to the all-`1.0` baseline;
  the `pi` clamp actually engages for a synthetic large
  salience/danger product.
- Full golden gate (`pytest tests/`) green — landed as its own
  `codebase:` commit before the tool/UI work (ground rule: codebase
  changes are additive, proven, and their own commit).
- `tool/core/tool_settings.py`: `EntityProfileSettings` (`enabled: bool =
  False`), threaded into `RunSpec`/`runner.py` the same way
  `CircuitSettings.shuffle_seed` is.
- `tool/core/entity_profiles_store.py` (or folded into
  `bridge/entity_profiles.py` if that ends up cleaner): read/write
  `projects/<name>/entity_profiles.json` for the tab editor.
- `tool/ui/tabs/enemies.py`, `tool/ui/tabs/objects.py`: the per-kind form
  (section 6), PIT/terrain greyed, wired into `MainWindow`'s
  get/set_tool_settings + a new get/set for the profile file itself.
  `tool/tests/`: a test proving a changed value round-trips to
  `entity_profiles.json` and changes a real run's telemetry.
- `wiring.py`: `enemies.smell_profile` → `live` once the above test
  exists.
- The 2×2×≥8-seed validation batch (section 5): one script (e.g.
  `scripts/validate_entity_profiles.py`), its aggregated numbers reported
  in the run note, and **exactly two videos** — one real-connectome run
  and one shuffled-connectome run, same seed, both under the modified
  profile (the condition where a viewer can actually see something
  different from a stock run) — `projects/<name>/runs/NNNa_real.mp4`,
  `projects/<name>/runs/NNNb_shuffled.mp4`, each with its own `.md` note
  (setup, numbers, which way the prediction went). **`docs/RUNS.md`
  itself is not touched by this sprint** — the user appends that entry.
- `docs/ENTITIES.md` updated per section 4 (not `docs/SCALARS.md` --
  machine-generated, see that section).

## 8. Explicitly out of scope

- **C8b** (section 0): distinct channels mapped to distinct connectome
  receptor populations. This SPEC's entire design is gains on shared
  aggregates; C8b is a different, larger change with its own SPEC.
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
- Writing `docs/RUNS.md`'s own entry for this sprint (section 7) — left
  to the user by explicit instruction.

## 9. Decisions locked in this revision

- `entity_profiles.json` as a dedicated per-project file (section 3):
  **approved**. `tool/PLAN.md`'s P6 bullet ("entity-profile editor in
  tabs 2–3 writing `projects/<name>/tool.json`") is corrected in that
  file to name `entity_profiles.json` instead, alongside this SPEC
  landing.
- `danger_weight` as a per-kind master knob over both looming and threat
  odour (section 1), with `intensity`/`looming_salience` as the per-
  sense knobs underneath it — supersedes this SPEC's earlier draft,
  which treated `danger_weight` as threat-odour-specific only.
- Validation is the 2×2×≥8-seed batch in section 5, not a single real-
  vs-shuffled pair — supersedes the earlier draft's section 5.
- Tabs 2–3 are in scope for this sprint (section 6), not a later pass —
  supersedes the earlier draft's section 6, which deferred them.
