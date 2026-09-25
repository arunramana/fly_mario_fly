# Codebase changes made for tool/

Log of every change made outside `tool/` to let it back a GUI, per
`tool/PLAN.md`'s ground rule 2: additive, default-preserving, proven by
the golden gate, its own `codebase:`-prefixed commit.

## C1 — `run_steering.main(config=None)`

**What.** `main()` takes a new `config: ProjectConfig | None = None`
argument. `None` (the default) builds a fresh `ProjectConfig()`, exactly
as before. A real `ProjectConfig` is used as-is instead — its 49 circuit
scalars now actually drive the run, not just its scenario fields.
`sim/project_runner.run_from_config` passes `config=config` through
(previously it only forwarded `level`/`max_frames`/`sigma`/`seed`/
`inject_gap_frame`/`retinotopic`, silently dropping every circuit scalar
a caller had set).

**Why.** Before this, `main()` built its own internal default
`ProjectConfig()` regardless of what was passed to `run_from_config` — a
GUI's Circuits tab could change `jump.g` all it wanted and the run would
never see it.

**Default that keeps behaviour.** `config=None` → `ProjectConfig()`,
identical code path to before. `sigma` still always overrides
`config.noise.sigma` (unchanged override semantics either way) — a
caller that wants the config's own sigma to win passes
`sigma=config.noise.sigma` explicitly, which `run_from_config` already
does.

**Proof.** `tests/test_golden.py` (3/3 byte-identical) and
`tests/test_config_roundtrip.py` (`projects/legacy/config.json` still
reproduces `017_reprise_telemetry.csv` exactly) prove nothing broke.
`tests/test_config_sensitivity.py` (new) proves the fix itself: tripling
`jump.g` in a passed config changes TTMn telemetry; `config=None` and
`config=ProjectConfig()` (explicit, unmodified) produce byte-identical
telemetry.

## C2 — wire `NetworkParams`, `HabituationParams`, `EntityParams`,
`RetinotopyParams` through constructors

**What.**
- `fly/network/integrator.py`'s `Integrator` already took `alpha`/`clip`
  as constructor args (default `dynamics.ALPHA`/`CLIP`) but `FullPolicy`
  never passed them — every `Integrator(...)` call site now gets
  `alpha=config.network.alpha, clip=config.network.clip`.
- `dynamics.phi(x, clip=CLIP)` gains an optional `clip` param (was
  hard-coded to the module constant); `FullPolicy`'s mushroom-body block
  (the one direct `dynamics.phi`/`dynamics.ALPHA` call outside
  `Integrator`) now uses `config.network.alpha`/`clip`.
- `FullPolicy.substeps = config.network.substeps`, replacing every
  `for _ in range(dynamics.SUBSTEPS)` (5 call sites) with
  `for _ in range(self.substeps)`.
- `fly/state/reflex_habituation.py`'s `ReflexHabituation` already took
  `give_up`/`progress_px` constructor overrides — `FullPolicy` now passes
  `config.habituation.hab_give_up`/`hab_progress_px` when building
  `hab_escape`/`hab_climb`. The MDN trigger's own comparison
  (`hab_level >= HAB_GIVE_UP`) switched from the module constant to
  `self.hab_escape.give_up`, so it can't drift from the instance's own
  configured threshold.
- `mario/entities/registry.py`'s `KindRegistry` gains an
  `entity_width_px` constructor arg; `FullPolicy.registry =
  KindRegistry(entity_width_px=config.entity.entity_width_px)`, passed to
  `enemy_thetas`/`mushroom_odor`/`goomba_odor` instead of their
  `DEFAULT_REGISTRY` fallback.
- `fly/sensing/retinotopy.py`'s `receptive_field_centers` gains
  `spread_fallback`/`spread_floor` args (were bare literals); its
  `azimuth_target` already took `d_ref` — both wired from
  `config.retinotopy.*` at `FullPolicy`'s two retinotopic call sites.

**Why.** `docs/CODE_AUDIT.md`'s S3: these four groups were documentation-
only, checked equal to their live module constants by
`test_params_match_live.py` but never actually read by the live system —
editing them in a project JSON did nothing.

**Default that keeps behaviour.** Every new default matches the module
constant it used to read unconditionally (`NetworkParams`: alpha=0.3,
clip=50.0, substeps=10; `HabituationParams`: hab_give_up=3,
hab_progress_px=16; `EntityParams`: entity_width_px=16;
`RetinotopyParams`: unchanged, and inert anyway since `retinotopic=False`
is the permanent default).

**Proof.** `tests/test_golden.py` (3/3) unaffected. `tests/
test_c2_wiring.py` (new): changing `network.substeps` or `network.clip`
changes TTMn/LC4 telemetry; changing `entity.entity_width_px` changes
`theta` telemetry (it enters `theta = 2*arctan(width / (2*|d|))`
directly); `FullPolicy.hab_escape.give_up`/`hab_climb.give_up` carry a
custom `habituation.hab_give_up` (checked directly — a full episode
rarely fires the reflex enough times in a short run to show habituation
either way); `receptive_field_centers`/`azimuth_target` use their new
parameters directly (skipped if `fly.sensing.retinotopy`'s own `mcns`
dependency isn't importable, pre-existing, nothing in this suite has ever
exercised that permanently-off module before).

## C3 — `run_steering.main(on_frame=None, should_stop=None)`

**What.** `on_frame(frame, obs, row)` is called once per emulator frame
(both the frame-skip repeat-row branch and the main decision branch),
right after the telemetry row is finalised and (if `record_video`) its
PNG is saved, right before `env.step()` advances to the next frame.
`should_stop()` is called right after, once per frame; a true return
`break`s the loop early, same effect as reaching `max_frames`.

**Why.** The live preview needs the raw frame and that frame's telemetry
as they happen, not after the whole episode ends; Cancel needs a way to
actually stop a run in progress.

**Default that keeps behaviour.** `None` for either (the default): never
called, no branch taken beyond the `is not None` check. The existing
`record_video`/telemetry code paths are untouched.

**Proof.** `tests/test_golden.py` (3/3) unaffected. `tests/
test_frame_callback.py` (new): `on_frame` is called exactly once per
emulator frame with the matching frame index, an `obs` array of constant
shape, and a `row` whose own `"frame"` key matches; `should_stop`
returning `True` at frame 50 ends the episode at exactly 50 frames;
passing harmless (no-op) callbacks produces byte-identical telemetry to
not passing them at all.

## C4 — score/coins/time/flag into the summary `info`

**What.** The returned summary dict gains `score`, `coins`, `time`,
`flag_get` -- read from the gym wrapper's own per-step `info` dict (`env.
step()`'s fourth return value), specifically its state after the LAST
step of the episode. `info = {}` before the loop guards the (never
actually reachable today) `max_frames=0` case, so reading `.get(...)`
after the loop can never raise.

**Why.** Fitness's "points" weight (tool/PLAN.md tab 5) had nothing to
read -- the gym wrapper already tracks score/coins/time/flag every step,
but none of it left `main()`.

**Default that keeps behaviour.** Additive only: the telemetry CSV's
column set is untouched (these never went into `TelemetryObserver`, only
the returned summary dict), and no existing summary key changes meaning.

**Proof.** `tests/test_golden.py` (3/3) unaffected. `tests/
test_summary_info_keys.py` (new): the four keys are present with the
expected types; two separate runs of the same scenario still produce
byte-identical telemetry CSVs (the new keys never reached the CSV).

## C10 — `FullPolicy._prev_avoid_odor`/`_last_x` per instance, not per class

**What.** These two moved from CLASS attributes (shared by every
`FullPolicy` instance in one process, a documented quirk since phase 5b)
to instance attributes, reset to `False`/`None` in `reset()` like every
other piece of per-episode state on `self`.

**Why.** `_prev_avoid_odor` only gates a log line and a counter --
harmless either way. `_last_x` feeds `stall_count`, which feeds the real
climb-reflex trigger (`bridge/full_policy.py`'s `act()`): a leftover
value from a PREVIOUS episode's last frame could equal a NEW episode's
spawn `mario_x` (level 1-1 always spawns at the same x) and falsely
register a stall on frame 0 of a new episode, biasing when climbing first
fires. tool/PLAN.md's own P2 planning named this as the reason persistent
warm workers (below) need a byte-for-byte identity test before they ship
-- a warm worker running episode 2 right after episode 1 is exactly the
scenario that used to leak.

**Not caught by any golden before now, and not because the bug wasn't
real:** every golden is a single episode per process, and none of their
specific scenarios happened to have episode N's last `mario_x` collide
with episode N+1's spawn `mario_x` -- there was only ever one episode, so
the question never arose. The fix and its risk were sitting in
`bridge/full_policy.py`'s own module docstring since phase 5b, waiting
for a reason to fix it before persistent workers made it one.

**A real behaviour change for multi-episode-per-process scripts** -- not
default-preserving the way C1-C4 were, logged here rather than folded in
as if it were:
- `scripts/train_mushroom_body.py` (500 sequential episodes, one process,
  one reused savestate/env): every episode from #2 onward now starts
  `stall_count` from a genuinely clean slate instead of possibly already
  primed by episode N-1's final `mario_x`. Any episode whose early
  climb-reflex timing depended on that leftover value will diverge from a
  pre-C10 training run at that point onward -- expected and intended, not
  a regression to chase down.
- `scripts/record_mb_videos.py` (two sequential `main()` calls in one
  process, "before" then "after" training): the "after" video/telemetry
  may differ from a pre-C10 recording for the same reason.
- `scripts/bench_episodes.py` (24 episodes, timing-focused): frame counts
  may shift slightly; its own numbers were never meant to reproduce
  bit-for-bit run to run, so this doesn't invalidate what it measures.
- Not affected: every scenario in `tests/golden/` and every test in this
  suite (each already exercises a single episode's worth of `FullPolicy`
  state, by construction) -- proven, not assumed, below.

**Proof.** `tests/test_golden.py` alone: 3/3 byte-identical. Full suite
(69 tests) in the normal collection order: 69/69. Full suite in REVERSED
file order (`test_telemetry_observer.py` first, ..., `test_c2_wiring.py`
last -- deliberately moving every other `FullPolicy`-constructing test to
the opposite side of `test_golden.py` from where it falls normally):
69/69, same result. Together these rule out both "some other test's
leftover class state was quietly saving the goldens" and "the fix only
works in whatever order tests happen to run in today."

## C5 — `shuffle_seed` (the shuffled-connectome control)

**What.** `FullPolicy`/`main(shuffle_seed=None)`. `None` (default) loads
each circuit's real weight matrix as always. An int rebuilds W for
*every* circuit (jump, steering, takeoff, speed, MDN, DNp02, mushroom
body) from the same bodies/edges/signs `fly.connectome.circuit.
build_shuffled` already implements: same neurons, same in/out degree
distribution, same signs, edges rewired at random (CLAUDE.md invariant
6). Not cached (CLAUDE.md: skip performance work absent a measured need)
-- a fresh shuffle per `FullPolicy` construction.

**Why.** CLAUDE.md invariant 6: "the shuffled-connectome control ships
with the feature, not afterwards." tool/PLAN.md tab 4 needs it as a
toggle.

**Default that keeps behaviour.** `shuffle_seed=None` -> the exact same
`_memo_load(...)` call as before, unchanged. Proven, not assumed:
`shuffle_seed=None` (explicit) and leaving the argument out entirely
produce byte-identical telemetry.

**Proof.** `tests/test_golden.py` (3/3) unaffected. `tests/
test_c5_shuffle.py` (new): `shuffle_seed=1` changes TTMn telemetry vs. the
real connectome; the same seed is deterministic across two separate runs;
`shuffle_seed=None` explicit == omitted.

## C7 — `hunger_override` (starting power-up needs no new surface)

**What.** `bridge.perception.hunger_multiplier(ram, override=None)`
gains an `override: bool | None` -- `None` (default) reads RAM as
always; `True`/`False` forces hungry/sated regardless of Mario's actual
size. Threaded through `FullPolicy`/`main(hunger_override=None)`. The
OTHER half of tab 1's character state, starting power-up, needed **no
new codebase change at all** -- `main()` already has `force_mario_size`/
`force_size_from_frame`; "start big" is `force_mario_size=1,
force_size_from_frame=0`, unchanged from before this phase.

**Why.** Hunger has never been settable independent of Mario's real
size; tab 1's hunger control has nothing else to drive.

**Default that keeps behaviour.** `override=None`/`hunger_override=None`
reproduce the RAM read exactly (proven, not assumed, below).

**This is a science change when actually used**, per CLAUDE.md rule 3 --
this entry proves the plumbing is correct, not that a forced-hunger run
is scientifically meaningful; that needs its own recorded run and
`docs/RUNS.md` entry (tool/PLAN.md P5's own deliverable) before anyone
draws a conclusion from one.

**Proof.** `tests/test_golden.py` (3/3) unaffected. `tests/
test_c7_character_state.py` (new): `hunger_override=False` forces
`hungry` False every frame, `=True` forces it True every frame, both
differing from the RAM-driven default; `hunger_override=None` (explicit)
== omitted; `force_mario_size=1, force_size_from_frame=0` holds
`mario_size==1` the whole episode (proving the pre-existing mechanism
already does what "starting power-up" needs, with no new code).

## C11 — `render/brain_panel.py`: MDN and mushroom-body soma positions

**What.** `render.brain_panel`'s soma-position cache only ever knew
LC4/LPLC2/DNp01/TTMn/DNa01/DNa02/DNp09/DLMn (`COL`'s old eight keys).
Added `MDN` (selected by `type`, same as everything else already there),
`KC`/`MBON` (selected by `class` -- `Kenyon_Cell`/`MBON` respectively,
since each has many distinct `type` values, exactly the split
`fly/circuits/mushroom_body_circuit.py`'s own `core_bodies()` already
uses), and `DAN` (the union of `PAM`/`PPL`/`PPM`-prefixed types, same
regex as that file's `DAN_TYPE_RE`). `_build()` now also reads the
annotations feather's `class` column, not just `type`/`somaLocation`.
Also adds `highlight_populations(pops) -> PIL.Image`, a thin wrapper over
the existing `_draw_brain` that clamps every named population to full
brightness (`act=norm=1.0` each) -- a circuit card's static brain-map
image, not a per-frame telemetry composite.

**Why.** tool/SPEC_ui_retro.md section 8's own stated gap: the MDN and
mushroom-body circuit cards had no real soma positions to draw at all --
their brain-map images would have been blank silhouettes.

**Default that keeps behaviour.** Every existing `COL` key's own
selection logic is untouched; the four new keys are additive. No
existing caller passes the new keys, so `render_run`'s own per-frame
composite (used by every existing recorded run) is byte-for-byte
unaffected.

**Proof.** `tests/test_brain_panel_populations.py` (new): all four new
populations resolve to a non-empty soma-position array (real coordinates
from the connectome annotations, not placeholders); `MDN`'s count matches
what `fly/circuits/mdn_circuit.py`'s own `CORE_TYPES` selection finds
(4); `KC`/`MBON`/`DAN`'s counts are close to (within the expected
somaLocation-coverage gap of) `fly/circuits/mushroom_body_circuit.py`'s
own asserted `EXPECTED_KC`/`EXPECTED_MBON`/`EXPECTED_DAN`; `highlight_
populations` renders without crashing for each of the six circuit cards'
own population lists. Full golden gate (97/97) unaffected -- this module
is never on the golden's own telemetry path.

## C12 — `render/brain_panel.py`: `panel_for_row` + `radius_scale`

**What.** `render_run`'s per-frame body (build a `_panel_context` once,
then draw one `PIL.Image` per telemetry row) is now two standalone
functions, `_panel_context(tel)` and `panel_for_row(tel, i, ctx,
caption="")`, instead of code living only inside `render_run`'s own loop.
`_draw_brain`/`highlight_populations` also gain an additive `radius_scale:
float = 1.0` parameter that scales each highlighted soma's dot radius.

**Why.** The Run tab's video player needs a live "Brain map" toggle that
renders one frame on demand from whatever telemetry row the player is
currently showing -- the same drawing code `render_run` already used to
bake a whole video, but callable for a single row without encoding
anything. `radius_scale` is separate: `tool/ui/widgets/circuit_card_image.
py`'s ~160px circuit cards were shrinking sparse populations (Speed=1
neuron, MDN=4 neurons) to single dark pixels, invisible against the brain
silhouette -- the user's own explicit "make the circuit brain-map
highlights visible on every card."

**Default that keeps behaviour.** `radius_scale=1.0` reproduces the exact
prior radius at every call site that doesn't pass it (`render_run`
itself, unchanged). `panel_for_row`/`_panel_context` are new code, not a
rewrite of `render_run`'s loop -- `render_run` still exists and still
produces the same bytes it always did.

**Proof.** `tests/test_panel_for_row.py` (new): `panel_for_row(tel, i,
ctx)` for every `i` produces byte-identical output to what `render_run`'s
own inline loop drew for that row before the refactor. `tests/
test_brain_panel_populations.py`'s new `radius_scale` test: a sparse
population's highlighted dot covers measurably more pixels at
`radius_scale=4.0` than at the default. Golden gate (97/97, run once
after this change) unaffected -- `render/brain_panel.py` is never on the
golden's own telemetry path.

## C13 -- `mario_y` in every on_frame row + `death_animation_frames`

**What.**
- Every `row` `run_steering.main()`'s `on_frame` receives now also carries
  `mario_y` (`int(ram[ADDR_MARIO_Y])`), set AFTER `observer.record(row)`
  in both the frame-skip repeat branch and the main decision branch --
  `TelemetryObserver.to_dataframe()` only ever reads its own fixed
  `columns` tuple, so a key set on the dict after `record()` (which keeps
  the same dict reference) never becomes a CSV column.
- `main(death_animation_frames=0)`: on a real death or flag (`done` True
  -- never a Cancel, which breaks the loop without setting it, and never
  hitting max_frames), a positive value steps this many EXTRA emulator
  frames afterward, calling `on_frame` for each with the last real
  telemetry row's dict (just `"frame"` updated). Reuses the last real
  action -- the NES ignores input during this animation regardless.
  Requires `env.unwrapped.done = False` before each extra `env.step()`:
  nes-py's own `NESEnv.step()` (not a Gym wrapper) refuses to step past a
  `done` it just returned ("cannot step in a done environment! call
  `reset`"), on the assumption every caller wants a fresh episode next --
  checked directly, not assumed, after this raised `ValueError` on the
  first attempt. `env.reset()` is never called, so no new episode starts;
  clearing the one instance flag lets the SAME episode's own emulator
  state keep running.

**Why.** tool/ui/widgets/palette.py's Luigi-recolour box needed Mario's
real vertical position, not a fixed band (see the paired tool: commit
restricting it) -- `mario_y` is that value, already computed in
run_steering.py's own loop but never threaded through `on_frame` before.
`death_animation_frames` is the Run tab video player's own ask: show the
NES's own death animation instead of cutting to the last standing frame,
without letting a display choice touch telemetry or fitness.

**Default that keeps behaviour.** `death_animation_frames=0` (default):
the new block's `if death_animation_frames > 0` guard is never entered,
byte-identical to before this existed. `mario_y` is additive on the same
`row` dict CSV-writing already ignores past its fixed columns -- proven,
not assumed, below.

**Proof.** `tests/test_golden.py` (3/3) and `tests/test_config_
roundtrip.py` unaffected. `tests/test_c13_display_extensions.py` (new):
every `on_frame` row carries `mario_y`, which never appears in `tel.
columns`; on tests/test_golden.py's own `test_sigma0_baseline` scenario
(1-1, sigma=0, seed=0, dies at frame 689) `death_animation_frames=90` adds
exactly 90 more `on_frame` calls (frames 689-778) while `tel`, `n_frames`,
and `max_x_abs` stay byte-for-byte identical to `death_animation_frames=0`;
a run that hits max_frames instead of dying gets zero extra frames
regardless of the setting.
