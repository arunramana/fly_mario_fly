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
