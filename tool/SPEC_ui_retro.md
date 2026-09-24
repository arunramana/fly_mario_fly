# SPEC: tool UI retrospective — full parameter control, retro redesign, entity valence flip

Revision 2, from the actual discussion (the first draft was written
without it — see the previous git revision of this file for that
scope note; it's superseded by this one). **Design document only,
matching every other SPEC in this project — no code changes in this
commit.**

---

## 0. Retrospective: where the tool stands

P0–P7 are done (`tool/PLAN.md`'s own status header), including C8a
(per-kind entity perception gains, tabs 2–3 live) and a pass of GUI bugs
found in manual testing (`tool:` commits `f397869`, `dc1e05a`). This SPEC
covers three threads: (1) two categories of hand-set numbers still
outside a tracked home — the simulation's own long-standing ones
(`docs/CODE_AUDIT.md` section H) and the ones this session's own bug-fix
pass just added (`tool/core/palette.py`, `tool/ui/widgets/preview.py`);
(2) a full visual and structural redesign of the GUI itself, retro/
video-game styled, card-based, manifest-driven; (3) the entity valence
flip, extending C8a's existing per-kind editor.

## 1. Parameter control, part A: the simulation's own H-list

`docs/CODE_AUDIT.md` section H lists ten hard-coded literals live in the
simulation path, absent from `docs/SCALARS.md`'s 49. That same document's
own "Out of scope for cleanup" section says plainly: **"Move the H
values into `config/params.py`."** This SPEC does it anyway, but under
the exact discipline that line is warning against skipping: **identical
defaults, goldens byte-identical, verified — not "corrected" on the
way.** The audit's risk was real (a literal like `0.00379` looks like it
could round to `0.0038`, silently changing a golden); the fix is
promoting each value as data first and treating any "that number looks
wrong" instinct as a separate, later, explicitly-flagged question, never
folded into this move.

### 1.1 The ten items, classified

Not every H-list entry is a "gain" in the same sense as `jump.g` — some
are architecture (a fixed array dimension, a seed that's part of the
golden), and one pair is a duplicate-definition bug, not a missing
scalar. Promoting all ten identically into `config/params.py`'s existing
shape (a bare typed/ranged/provenance field) would misrepresent the ones
that aren't really free parameters. Proposed classification:

**Straightforward scalar promotion** (a single number that changes how
hard something pushes, same shape as the existing 49):

| Item | New home (proposed) | Default |
|---|---|---|
| `MBON_DNA02_FRAC` L | `mushroom_body.mbon_dna02_frac_l` | 0.00379 |
| `MBON_DNA02_FRAC` R | `mushroom_body.mbon_dna02_frac_r` | 0.00632 |
| stomp threshold (20px) | `full_policy.stomp_distance_px` (new group, or fold into an existing one — see 1.3) | 20 |
| distance-history cap | `full_policy.closing_speed_history_frames` | 10 |
| denormal flush threshold | `network.denormal_flush_threshold` | 1e-30 |
| aversive-odour presence gate | `odour.avers_presence_gate` | 1e-6 |
| `wide_gap_target_col`'s `lead_tiles` | `demo.wide_gap_lead_tiles` | 10 |
| `poke_wide_gap`'s `+2` | `terrain.refusal_gap_margin_tiles` | 2 |

**Not promoted as a new scalar — read the existing one instead**
(de-duplication, per `docs/CODE_AUDIT.md`'s own "Do not merge" section
already flagging `W_TILE`/`ENTITY_WIDTH_PX` as the same duplicate
pattern):

- `question_block_odor`'s `offset_tiles * 16` — reads
  `config.entity.entity_width_px` (already 16, already tracked), not a
  new `16` literal under a different name.
- `run_steering.MAX_FRAMES` — deleted; every call site that used the
  bare module constant instead of `config.scenario.max_frames` is
  updated to take `config` (or the resolved value) explicitly. Not a new
  scalar — the audit's own framing is "two homes," and the fix is having
  one, not adding a third.

**Not promoted at all — stays a documented structural constant**,
because it isn't a gain, it's part of the network's fixed shape or a
seed the golden depends on bit-for-bit, and `config/params.py`'s own
`range`/provenance shape doesn't fit "this number changes what shape the
projection matrix is":

- `N_MB_SENSORY = 7` and "3 features per KC" (Kenyon-cell projection
  input dimensionality).
- The KC projection's RNG seed `0` — `docs/CODE_AUDIT.md`'s own words,
  "the seed is part of the golden." Seeds get the same special
  treatment `shuffle_seed` already does elsewhere in this project, not
  the "invented/measured with a range" treatment a gain gets.

These three get a `_note` in `docs/CODE_AUDIT.md` itself (not a
`config/params.py` field) recording that they were considered and
deliberately left out, so a future pass doesn't re-open the same
question without the answer already being on record.

### 1.2 Deliverable and test bar

- Each promoted scalar becomes a real `config/params.py` field (existing
  group where one fits naturally, per 1.1's table; a new group only
  where none does), with the exact provenance category
  (invented/measured) and range this project's own convention requires
  — most of these are "invented" (no sweep backs `avers_presence_gate`,
  for instance), stated as such, not dressed up as measured.
- The live code (`bridge/full_policy.py`, `mario/ram/tile_ram.py`,
  wherever each literal currently sits) reads the new `config.*` field
  instead of the bare constant.
- **Golden gate stays green with the exact same three CSVs**
  (`tests/test_golden.py`) — this is the actual proof the promotion
  didn't "correct" anything, not just a claim.
- `docs/SCALARS.md` regenerates with the new rows (`config.scalars_doc`).
- `docs/CODE_AUDIT.md` section H is updated: promoted items move to
  "resolved, see git history" per that file's own convention (line 4-5),
  the three structural ones get the `_note` above, and the "Out of
  scope for cleanup" line about moving H values is struck with a
  pointer to this SPEC and the commit that did it.

## 2. Parameter control, part B: the tool's own display-only values

Separate from part A — these are values this session's *own* bug-fix
pass introduced (`tool/core/palette.py`, `tool/ui/widgets/preview.py`),
never part of the simulation at all. Confirmed by re-reading both files:
none of them affect a simulation's telemetry even slightly (`MARIO_Y_MIN`
only changes which pixels a *displayed* frame recolours; a bar's max
only changes how full a *displayed* progress bar looks) — two
identically-run episodes produce byte-identical telemetry regardless.
Putting these in `config/params.py` alongside `jump.g` would blur the
`config.json` (simulation) / `tool.json` (tool) split this project
already draws for exactly this reason.

**`tool/core/display_params.py`** — same shape as `config/params.py`
(typed, ranged, provenance-documented dataclass fields), generating a
`tool/SCALARS_UI.md` the same way `config/scalars_doc.py` generates
`docs/SCALARS.md`, but tracking display-only numbers:

| Field | Default | Provenance |
|---|---|---|
| `mario_x_margin_px` | 8.0 | invented |
| `mario_y_min_px` | 140.0 | measured (a real 689-frame run) |
| `bar_max_lc4` | 4.0 | measured |
| `bar_max_lplc2` | 6.0 | measured |
| `bar_max_dna01` | 12.0 | measured |
| `bar_max_dna02` | 12.0 | measured |
| `bar_max_dnp09` | 1.0 | measured |
| `bar_max_mdn` | 12.0 | invented |

Two values from the original audit are **not** fields here — they're
duplicates of an existing simulation scalar, and get read directly
instead of re-declared: `MARIO_WIDTH_PX` reads
`config.entity.entity_width_px`; the TTMn bar max reads
`config.jump.spike_amp` (post part A, both promoted, both now real
`config/params.py` fields, not literals). `NES_WIDTH_PX`/`NES_HEIGHT_PX`
stay plain module constants — the NES's actual screen resolution is a
hardware fact, not a hand-set choice with a provenance story.

`display_params.py`'s fields surface in the retro redesign's Settings
area (section 5) with the same advisory-range fix this session's own
bug-fix pass already applied to `ParamForm`.

## 3. One home per setting

Found while reviewing the current tabs for this SPEC: `noise.sigma` is
editable in **two** places today — the Goal tab's own `sigma_spin`
(`tool/ui/tabs/goal.py`) and, via `ParamForm`, the Circuits tab (every
one of the 49 scalars, `noise.sigma` among them). Nothing keeps them in
sync by construction; they happen to agree only because both write the
same `config.noise.sigma` and both tabs are rebuilt from the current
config often enough that staleness hasn't been observed yet — a real
"which one is the real one" trap, not a hypothetical.

**Rule going forward: every setting has exactly one editable home.**
Concretely for `noise.sigma`: the Circuits tab (schema-driven,
`config/params.py`'s own canonical home for all 49) keeps the live spin
box. The Goal tab's own control becomes a **read-only** display (a
disabled spin box or a plain label) showing the same value, with a
tooltip pointing at the Circuits tab as where to actually change it.
This generalises to any other value that turns out to have the same
problem once the redesign's card system (sections 6-8) is built — the
rule is checked once, structurally, not value-by-value: a manifest-driven
form only ever wires *one* widget per config path to `_on_change`; every
other place the same value is shown reads it and never connects a
setter.

**Test**: load a project, change `noise.sigma` through the Circuits
tab's own widget, assert the Goal tab's read-only display shows the new
value without being told to refresh separately (i.e. it reads live
`config.noise.sigma`, not a stale copy taken at construction) — the same
"displayed value always equals the config" bar `tool/tests/
test_param_form.py` already holds the Circuits tab to, extended to prove
no *second* writable copy exists anywhere else.

## 4. Entity valence flip

Unchanged from the previous revision — kept as originally written and
renumbered.

C8a's `bridge/entity_profiles.OdourChannel.sign` (+1 attractive / -1
aversive) is set by `bridge/profiles/default.json` and is not currently
editable from tabs 2–3 (`intensity`/`looming_salience`/`danger_weight`
are the only live controls, `docs/SPEC_entity_perception.md` section 6).
Proposed: a **valence toggle per live-editable kind's own odour entry**
(GOOMBA, KOOPA, ENEMY, POWERUP, QUESTION_BLOCK — the same five kinds
section 6 of the C8a SPEC already scopes as live; PIT/terrain stay
greyed, unchanged).

- **UI**: in the redesigned per-kind detail panel (section 7), a labelled
  control ("smells bad ↔ smells good," matching the phrasing agreed for
  the card detail panel) showing and setting the channel's current
  `sign`, alongside its existing intensity/looming/danger controls.
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
  `intensity` (danger_weight would then do nothing for that entry, since
  section 1's design only applies it to threat-signed channels — worth
  restating in the detail panel's own copy so a flipped kind's now-inert
  danger_weight control doesn't look like a bug).
- **This is a science change when actually used** (CLAUDE.md rule 3,
  same bar as `hunger_override`/`shuffle_seed`/every other C-numbered
  control): flipping GOOMBA's valence to attractive is a substantive
  behavioural experiment, not a display choice. `entity_profile.enabled`
  already gates the whole per-kind system off by default (opt-in); a
  flipped-valence run should still get its own recorded run +
  `docs/RUNS.md` entry when it's actually used for a finding.

**Test bar**: a profile with GOOMBA's `sign` flipped to `+1` moves its
contribution into `profiled_odor`'s *food* sum, not threat (same shape
as `tests/test_c8a_entity_profiles.py::test_modified_danger_weight_changes_telemetry`
— asserting the signal moved to the other channel, not just that
*something* changed); a `tool/tests/` GUI test proving the control
round-trips through `entity_profiles.json` and changes real telemetry
end to end.

## 5. Retro visual style

One QSS file, `tool/ui/style.qss`, loaded once
(`QApplication.setStyleSheet`) at startup (`tool/ui/app.py`) — no
per-widget inline styling scattered across tab files.

- **Font**: Press Start 2P (Google Fonts, SIL Open Font License 1.1 —
  licence text ships alongside it, `tool/assets/fonts/
  PressStart2P-OFL.txt`). Bundled, not system-installed:
  `tool/assets/fonts/PressStart2P-Regular.ttf`, loaded via
  `QFontDatabase.addApplicationFont` in `app.py` before any widget is
  constructed, so it's available to the QSS's own `font-family` rule
  regardless of what's installed on the machine running it. A pixel
  font at small sizes is often illegible — the QSS sets a minimum
  readable point size for body text and reserves the pixel font for
  headers/labels/buttons, not dense numeric fields (spin boxes keep a
  normal monospace font; a 49-field form in Press Start 2P at readable
  size would not fit on screen).
- **Palette**: a small, named NES-accurate set (not the full 54-colour
  NES palette, just the ones actually used) — sky blue `#5C94FC`
  (background), Mario red `#D82800`, Luigi green `#00A800`, brick brown
  `#A85400`, black `#000000`, white `#FCFCFC` — defined once as QSS
  properties/a Python constants module (`tool/ui/palette_colors.py`,
  distinct from `tool/core/palette.py`'s sprite-recolour module — naming
  collision noted so implementation doesn't conflate the two) and
  referenced from the QSS, not repeated as literal hex codes per rule.
- **Buttons**: large (generous min-height/padding), flat, thick-bordered,
  no gradients/shadows — matching an NES menu's own flat-colour blocks.
- **A START button**: the existing header's "▶ Play" button is restyled
  and relabelled "START" (the retro/arcade convention this asks for) —
  not a new, separate screen. The project gate (new/duplicate/open/
  recent) already serves as this app's own "insert coin" step; adding a
  *second* start screen ahead of the one that already exists would be
  new scope, not restyling. If a dedicated title/start screen before the
  gate is actually wanted, that's a explicit follow-up question, not
  assumed here.

## 6. Character select: picture cards

Replaces the Character tab's current radio-button pair with a card pair
— Mario and Luigi, each a clickable image (section 9's manifest/
placeholder system). Clicking a card selects that character (same
underlying `tool_settings.character.player` write as today) and the
card's own panel shows that character's internal state controls: hunger
override, starting power-up — the exact two controls the current tab
already has, moved from a form row into the selected card's own panel.
The not-wired arousal slider (C9) stays present, greyed, in the panel —
no change to what's live.

## 7. Enemies and Objects: picture-card grids

Replaces `enemies.py`/`objects.py`'s stacked group-box layout with a
grid of cards, one per `EntityKind` — live kinds (GOOMBA, KOOPA, ENEMY,
POWERUP, QUESTION_BLOCK) shown normally, greyed kinds (PIT, GROUND,
USED_BLOCK, SOLID_OTHER) shown desaturated/disabled, matching their
current greyed-out treatment (`docs/SPEC_entity_perception.md` section
6 — unchanged which five are live). Clicking a live card opens a detail
panel with: valence (section 4's "smells bad ↔ good" control), intensity,
looming salience, danger weight (master-knob relationship to looming
unchanged, `docs/SPEC_entity_perception.md` section 1). Clicking a
greyed card's detail panel states *why* it's greyed (the same reasons
`objects.py`'s current `GREYED_KINDS` table already gives), not just
that it's disabled.

The shared "Enable per-kind entity profiles" toggle stays a single
control visible above both grids (both tabs today keep it in sync via
`MainWindow.reload_tab` — the redesign keeps that mechanism, or replaces
it with the manifest system reading current state directly, whichever
turns out simpler once section 9 exists).

## 8. Circuits: cards with a real brain-map per circuit

A card per circuit — **jump/Giant Fiber, steering, speed, takeoff, MDN,
mushroom body** — each showing a static brain-map image generated from
`render/brain_panel.py`, highlighting that circuit's own real neurons at
their real soma positions, plus a one-line description. Clicking a card
opens its parameters (that circuit's `config/params.py` group(s), same
underlying `ParamForm` fields as today, just reached through a card
instead of a scrollable stack of all 49 at once).

**Circuit → population mapping** (from `render/brain_panel.py`'s own
`COL`/`ORDER`/`STEERING_ORDER`/`TERRAIN_ORDER`, checked directly, not
assumed):

| Card | Populations already drawable | `config/params.py` group(s) | `docs/SPEC_*.md` |
|---|---|---|---|
| Jump / Giant Fiber | LC4, LPLC2, DNp01, TTMn | `jump`, `dnp02` (the "second escape pathway" — not named as its own card in the request; folded in here as the closest fit, flagged for confirmation) | `SPEC_jump.md` |
| Steering | DNa01, DNa02 | `steering` | `SPEC_steering.md` |
| Speed | DNp09 | `speed` | none dedicated — falls back to `SpeedParams`'s own docstring |
| Takeoff | DLMn | `takeoff` | `SPEC_terrain.md` (covers the pit/long-jump territory takeoff serves) |
| MDN | **none yet** | `mdn` | none dedicated — falls back to `MdnParams`'s own docstring |
| Mushroom body | **none yet** | `mushroom_body` | `SPEC_mushroom_body.md` |

**Two real gaps, stated plainly rather than papered over**: MDN and
mushroom-body populations (KC/MBON/DAN/PAM/PPL/PPM, the MDN population
itself) have no soma-position entries in `render/brain_panel.py` at all
today — their cards' brain-map images would be blank silhouettes until
`brain_panel.py` is extended with those populations' real
`somaLocation` lookups, the same kind of connectome-position work that
gave the other four populations their real positions. This SPEC doesn't
do that extension; it's a prerequisite the deliverable list below
depends on, not assumed already done. Speed and MDN also have no
dedicated `SPEC_*.md` — their card's one-liner falls back to their own
`config/params.py` dataclass docstring (every group has one) until a
real SPEC exists for either.

**New public function needed**: `render/brain_panel.py`'s `_draw_brain`
is private and takes live per-frame activation, not "highlight these
populations at full brightness, statically, once." Proposed:
`render.brain_panel.highlight_populations(pops: list[str]) -> PIL.Image`
— wraps `_draw_brain` with `act={p: 1.0 for p in pops}`,
`norm={p: 1.0 for p in pops}`, no per-frame telemetry needed. Generated
once per circuit card (not per frame — these are static images, cached
to `tool/assets/generated/` or held in memory for the session, not
regenerated on every tab open).

## 9. Assets: a manifest, with a placeholder fallback

`tool/assets/manifest.json` — maps an asset id to a path relative to
`tool/assets/` (e.g. `"mario_card": "characters/mario.png"`), one entry
per card image this SPEC's sections 6-8 need (2 characters + however
many live entity kinds + 6 circuits). Images themselves are supplied by
the user, not generated — `tool/assets/` ships whatever's provided;
anything the manifest names that isn't actually on disk falls back to
**one placeholder image** (`tool/assets/placeholder.png`, a simple
"missing image" graphic, generated once as part of this deliverable
since it's not something the user needs to supply) rather than a crash
or a blank card. `tool/ui/widgets/asset_image.py`'s `load_asset(asset_id)
-> QPixmap` is the one place this fallback logic lives — every card
loads through it, never opens a file path directly.

## 10. Extensible: manifests and registries, proven

**"Adding an entity, circuit, or tab needs no UI code"** — concretely,
three registries, each with a test that adds a dummy entry through data
alone and confirms it appears, with no edit to the corresponding UI
module's own source:

- **Entity**: `enemies.py`/`objects.py` currently hardcode `LIVE_KINDS`/
  `GREYED_KINDS` as Python lists (checked directly — this SPEC replaces
  that). Proposed: the tabs iterate `bridge/profiles/default.json`'s own
  kinds directly (already a manifest in spirit — every `EntityKind` with
  a non-empty `odours` list is "live," everything else is "greyed,"
  derived, not hand-listed) plus `tool/assets/manifest.json` for each
  kind's card image. **Test**: add a dummy `EntityKind` + a
  `default.json`-shaped profile entry for it in a test-local override,
  assert a card for it renders — without touching `enemies.py`/
  `objects.py`.
- **Circuit**: a new `tool/core/circuit_manifest.py` (or a JSON file,
  matching the entity approach) listing each circuit card's id, display
  name, `config/params.py` group(s), population list, and `SPEC_*.md`
  path (section 8's own table, made data instead of prose). **Test**:
  register a dummy circuit entry (a fake group with one scalar) and
  assert a card appears for it.
- **Tab**: `main_window.py` currently hardcodes seven `self.tabs.addTab`
  calls directly in `__init__` (checked directly). Proposed: a
  `TAB_REGISTRY` list of `(tab_id, display_name, factory)` that
  `__init__` iterates generically — the biggest structural change this
  SPEC proposes, since every tab today is a fixed, named attribute
  (`self.character_tab`, `self.run_tab`) some other code reaches into
  directly (e.g. `on_player_changed` calls `self.run_tab.preview.
  set_player`). Making tabs fully generic needs those cross-tab reaches
  to go through the registry too (`self.tab("run").preview...`), not
  just the construction loop — flagged as the part of this SPEC most
  likely to need its own follow-up decision once scoped in detail.
  **Test**: register a dummy tab via the registry alone and assert
  `window.tabs.count()` includes it, with no edit to `main_window.py`'s
  own tab-construction code (only to the registry's own list/file).

## 11. Explicitly out of scope

- **Wiring edits** — everything in this SPEC is presentation and
  parameter *plumbing* (which config field a widget reads/writes), never
  a change to what a circuit computes. C8b, any new circuit input, any
  change to `bridge/full_policy.py`'s own decision logic: not here.
- **Noise and learning** — `noise.sigma`/`experiment.learning_enabled`
  keep their exact current behaviour; section 3's "one home" rule
  applies to *where* sigma is edited, not to noise or learning as
  features. No new noise model, no change to `event_proximal_dopamine`.
- Re-tuning any of section 1 or 2's *values* once promoted (e.g.
  deciding `avers_presence_gate` should really be `1e-5`) — promotion
  moves a number into a tracked home with its honest provenance stated;
  it doesn't re-measure it.
- Generating or sourcing the actual card/circuit images — the user
  supplies them (section 9); this SPEC only builds the manifest +
  placeholder mechanism that consumes them.
- The MDN/mushroom-body `brain_panel.py` population-position extension
  (section 8's own stated gap) and writing `SPEC_speed.md`/`SPEC_mdn.md`
  — prerequisites this SPEC depends on, not delivered by it.

## 12. Deliverable

- `config/params.py`: section 1's promoted scalars, in the groups
  proposed (or better ones found during implementation), each with a
  real provenance/range.
- `docs/SCALARS.md`, `docs/CODE_AUDIT.md`: regenerated / updated per
  section 1.2.
- `tool/core/display_params.py` + its own generated `tool/SCALARS_UI.md`
  (section 2).
- `tool/ui/tabs/goal.py`: `noise.sigma`'s own control becomes read-only
  (section 3), plus the test proving no second writable copy exists.
- `bridge/entity_profiles.py`/`entity_profiles_store.py`: valence flip
  storage (section 4), no `bridge/perception.py`/`full_policy.py` change.
- `tool/ui/style.qss` + `tool/assets/fonts/PressStart2P-Regular.ttf` +
  licence text (section 5).
- `tool/ui/tabs/character.py`, `enemies.py`, `objects.py`: card-grid +
  detail-panel redesign (sections 6-7).
- `render/brain_panel.py`: new `highlight_populations()` (section 8);
  MDN/mushroom-body soma positions flagged as a prerequisite, not
  delivered here.
- `tool/assets/manifest.json`, `tool/assets/placeholder.png`,
  `tool/ui/widgets/asset_image.py` (section 9).
- `tool/core/circuit_manifest.py`, entity-kind iteration replacing
  `LIVE_KINDS`/`GREYED_KINDS`, `main_window.py`'s `TAB_REGISTRY` (section
  10), each with its own dummy-entry test.
- Full golden gate green (section 1's own hard requirement); full
  `tool/tests/` green throughout.
