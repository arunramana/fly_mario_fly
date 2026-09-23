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
