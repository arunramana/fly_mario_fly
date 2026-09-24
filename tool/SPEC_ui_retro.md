# SPEC: tool UI retrospective — full parameter control, entity valence flip

**Scope note, stated up front rather than silently guessed around:** this
was asked for "as discussed," but no record of that discussion is in
this session's own visible context — the two content requirements given
explicitly ("full parameter control (promote the audit's H-list values
into params)" and "the entity valence flip") are what this document
builds from, plus the real audit run below. Where a design choice below
is an inference rather than something stated, it's marked as one. Please
correct anything that doesn't match what was actually discussed — this
is a draft for that correction, not a claim of having reconstructed the
conversation.

**This is a design document only, matching every other SPEC in this
project.** No code changes in this commit.

---

## 0. Retrospective: where the tool stands

P0–P7 are done (`tool/PLAN.md`'s own status header), including C8a
(per-kind entity perception gains, tabs 2–3 live) and a pass of GUI bugs
found in manual testing (`tool:` commits `f397869`, `dc1e05a`). Two
threads from that bug-fixing pass are what this SPEC picks up:

1. Fixing the Luigi palette swap and the preview bars required
   introducing several new hand-set numbers directly as Python module
   constants (`tool/core/palette.py`, `tool/ui/widgets/preview.py`) —
   outside `config/params.py`'s tracked-scalar system entirely, and in
   one case (the preview bars' TTMn max) duplicating a value
   (`jump.spike_amp`) that already lives there under a different name,
   with no mechanism to notice if the two ever drift apart.
2. C8a's own per-kind editor (tabs 2–3) exposes `intensity`,
   `looming_salience`, and `danger_weight` per kind, but not `sign`
   (valence) — an entity's odour channel is fixed as attractive or
   aversive by `bridge/profiles/default.json`, with no tool-level control
   to flip it.

## 1. The audit: hand-set values introduced without a tracked home

Real audit, run against the current tree (not reconstructed from
memory), of every module-level constant the GUI bug-fix pass added:

| Constant | File | Value | Already tracked elsewhere? |
|---|---|---|---|
| `MARIO_WIDTH_PX` | `tool/core/palette.py` | 16 | **Yes** — `config.entity.entity_width_px` (`mario/entities/registry.py`'s `ENTITY_WIDTH_PX`, itself a `config/params.py` scalar) |
| `MARIO_X_MARGIN_PX` | `tool/core/palette.py` | 8 | No |
| `MARIO_Y_MIN` | `tool/core/palette.py` | 140 | No |
| `MARIO_Y_MAX` | `tool/core/palette.py` | 240 | No (equals `NES_HEIGHT_PX`, itself fixed by the NES's own screen size, not really "tunable") |
| `NES_WIDTH_PX`, `NES_HEIGHT_PX` | `tool/core/palette.py` | 256, 240 | No, but these are hardware constants (the NES's real screen size), not a measured/invented scalar in `config/params.py`'s sense — SPEC section 3 excludes them |
| LC4 bar max | `tool/ui/widgets/preview.py` | 4.0 | No |
| LPLC2 bar max | `tool/ui/widgets/preview.py` | 6.0 | No |
| TTMn bar max | `tool/ui/widgets/preview.py` | 50.0 | **Yes** — `config.jump.spike_amp`, same value, different name, no link between them |
| DNa01 bar max | `tool/ui/widgets/preview.py` | 12.0 | No |
| DNa02 bar max | `tool/ui/widgets/preview.py` | 12.0 | No |
| DNp09 bar max | `tool/ui/widgets/preview.py` | 1.0 | No |
| MDN bar max | `tool/ui/widgets/preview.py` | 12.0 | No |

**This is the "H-list" this SPEC promotes** (Hand-set, matching
CLAUDE.md invariant 3's own term) — nine genuinely new values plus two
that duplicate an existing scalar under a different name.

## 2. A distinction before promoting anything: these are not simulation scalars

`config/params.py` is specifically the *simulation's* own scalar
registry — `docs/SCALARS.md` is generated from it, `ProjectConfig`
carries it into a `RunSpec` so a run is reproducible, and
`tests/test_scalars_doc.py` keeps it byte-exact. None of section 1's
values affect a simulation's outcome even slightly: `MARIO_Y_MIN` only
changes which pixels a *displayed* frame recolours, and a bar's max only
changes how full a *displayed* progress bar looks. Two identically-run
episodes produce byte-identical telemetry regardless of any of these —
they are display/rendering choices, not circuit inputs.

Putting them in `config/params.py` alongside `jump.g` or `odour_gain`
would blur the exact distinction this project already draws elsewhere:
`config.json` (`ProjectConfig`, simulation scalars) vs. `tool.json`
(`ToolSettings`, the tool's own settings) are already two separate
files for exactly this reason. **Proposed: a parallel, tool-only
registry**, not an addition to `config/params.py`:

- `tool/core/display_params.py` — same shape as `config/params.py`
  (typed, ranged, provenance-documented dataclass fields, generated into
  a `tool/SCALARS_UI.md` the same way `config/scalars_doc.py` generates
  `docs/SCALARS.md`), but for display-only constants. `home` in each
  field's provenance points at the file that used to hardcode it.
- Duplicated-elsewhere values (`MARIO_WIDTH_PX`, the TTMn bar max) are
  **not** re-declared here — they're read directly from the real config
  scalar (`config.entity.entity_width_px`, `config.jump.spike_amp`) at
  the point of use, removing the duplication and the drift risk instead
  of tracking two copies. `tool/ui/widgets/preview.py`'s TTMn bar
  becomes `config.jump.spike_amp`-driven, not a separate `50.0` literal.
- `NES_WIDTH_PX`/`NES_HEIGHT_PX` stay exactly as they are (plain module
  constants) — they're the real, fixed NES screen resolution, not a
  hand-set choice with a provenance story; `display_params.py` is for
  *invented or measured* display numbers, matching `config/params.py`'s
  own "invented"/"measured" provenance categories, not hardware facts.

### 2.1 What becomes GUI-controllable, and where

`display_params.py`'s fields surface on the **Settings tab** (tab 6,
already the home of `render.*`), in a new "Display" group box, using the
exact same `ParamForm`-style pattern as the Circuits tab — including
this session's own fix: ranges are advisory tooltips, never a hard
`setRange()` limit. Concretely:

| Field | Default | Provenance (proposed) |
|---|---|---|
| `mario_x_margin_px` | 8.0 | invented (generous padding either side of `mario_x`; no measurement backs this number, a wider or narrower margin hasn't been compared) |
| `mario_y_min_px` | 140.0 | measured (checked against a real 689-frame run — near-Mario red pixels stayed within roughly rows 190-239 in the common case; 140 adds headroom for a jump apex not fully sampled) |
| `mario_y_max_px` | 240.0 | fixed (`NES_HEIGHT_PX`, not independently tunable — kept as a field only so the Display group box can show the whole box, not because 240 is a free parameter) |
| `bar_max_lc4` | 4.0 | measured (689-frame run, observed max ~3.36) |
| `bar_max_lplc2` | 6.0 | measured (observed max ~5.49) |
| `bar_max_dna01` | 12.0 | measured (observed max ~10.4) |
| `bar_max_dna02` | 12.0 | measured (observed max ~10.4) |
| `bar_max_dnp09` | 1.0 | measured (observed max ~0.94) |
| `bar_max_mdn` | 12.0 | invented (no fire observed in the one run measured; set to match DNa01/DNa02's own WTA-circuit scale as the closest analogue, not a direct measurement) |

`bar_max_ttmn` is deliberately **not** a field here — see section 2,
it reads `config.jump.spike_amp` directly, so it can never drift from
the value that actually determines what "100%" means for a real spike.

## 3. Entity valence flip

C8a's `bridge/entity_profiles.OdourChannel.sign` (+1 attractive / -1
aversive) is set by `bridge/profiles/default.json` and is not currently
editable from tabs 2–3 (`intensity`/`looming_salience`/`danger_weight`
are the only live controls, `docs/SPEC_entity_perception.md` section 6).
Proposed: a **valence toggle per live-editable kind's own odour entry**
(GOOMBA, KOOPA, ENEMY, POWERUP, QUESTION_BLOCK — the same five kinds
section 6 of the C8a SPEC already scopes as live; PIT/terrain stay
greyed, unchanged).

- **UI**: a `QComboBox` ("Attractive" / "Aversive") or a `QCheckBox`
  ("Flip valence") next to each kind's existing intensity spin box in
  `enemies.py`/`objects.py`, showing the channel's current `sign`.
- **Storage**: `tool/core/entity_profiles_store.py`'s existing
  `set_kind_odour_intensity` already restates a kind's whole `odours`
  list from the merged profile when changing one field on one entry
  (SPEC section 2's own merge rule: overriding `odours` replaces the
  whole list). A parallel `set_kind_odour_sign(project_name, kind_name,
  odour_index, sign)` follows the identical pattern, changing only
  `sign` instead of `intensity`.
- **Runtime**: nothing changes in `bridge/perception.py` or
  `bridge/full_policy.py` — `profiled_odor()` already reads
  `odour.sign` per entry to route into the food or threat sum (SPEC
  section 1.2/1.3). A flipped GOOMBA (`sign: +1`) would route its
  concentration into the *food* sum instead of *threat*, using its own
  `intensity` (danger_weight would then do nothing for that entry,
  since section 1's design only applies it to threat-signed channels —
  worth restating in the UI's own tooltip so a flipped kind's
  now-inert danger_weight control doesn't look like a bug).
- **This is a science change when actually used** (CLAUDE.md rule 3,
  same bar as `hunger_override`/`shuffle_seed`/every other C-numbered
  control): flipping GOOMBA's valence to attractive is a substantive
  behavioural experiment ("what does the fly do if it's drawn toward
  what should be a threat"), not a display choice. `entity_profile.
  enabled` already gates the whole per-kind system off by default
  (opt-in); a flipped-valence run should still get its own recorded
  run + `docs/RUNS.md` entry when it's actually used for a finding,
  matching this project's own standard for every other science-relevant
  control.

### 3.1 Test bar this would need to clear (ground rule 4)

- A test loading a profile with GOOMBA's `sign` flipped to `+1` and
  confirming `profiled_odor`'s *food* sum (not threat) picks up its
  contribution — the same shape as
  `tests/test_c8a_entity_profiles.py::test_modified_danger_weight_changes_telemetry`,
  asserting the signal moved to the other channel, not just that
  *something* changed.
- A `tool/tests/` GUI test proving the valence control round-trips
  through `entity_profiles.json` and changes real telemetry end to end,
  matching `test_entity_profiles_tab.py`'s existing pattern.

## 4. Deliverable

- `tool/core/display_params.py` + `tool/scripts/display_scalars_doc.py`
  (or folded into the existing `config/scalars_doc.py` pattern,
  whichever ends up cleaner) generating `tool/SCALARS_UI.md`.
- `tool/core/palette.py`, `tool/ui/widgets/preview.py`: read from
  `display_params`/`config.jump.spike_amp` instead of module constants.
- Settings tab: a new "Display" group box, `ParamForm`-style advisory
  ranges (this session's own fix, not the old hard-clamp behaviour).
- `bridge/entity_profiles.py`: no change needed (`OdourChannel.sign`
  already exists and is already read correctly).
- `tool/core/entity_profiles_store.py`: `set_kind_odour_sign`.
- `tool/ui/tabs/enemies.py` / `objects.py`: a valence control per live
  kind's odour entry.
- Tests per section 3.1, plus a `tool/tests/` test proving the new
  Display group box's controls change what's actually drawn (not just
  that a config value changed) — the same "no control lies" bar
  section 1's own bug-fix pass was held to.

## 5. Explicitly out of scope

- Re-tuning any of section 1's *values* (e.g. finding a better
  `mario_y_min_px` than 140) — this SPEC promotes what's already
  measured into a tracked home, it doesn't re-measure it.
- C8b (distinct channels mapped to distinct connectome receptor
  populations) — valence flip stays within C8a's gains-only design
  (section 3's own point: nothing in `bridge/full_policy.py` changes).
- Any change to which five kinds are live vs. greyed
  (`docs/SPEC_entity_perception.md` section 6's own scope) — PIT and
  the terrain kinds stay greyed for the same reasons stated there.
