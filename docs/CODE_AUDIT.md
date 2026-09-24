# Code audit — open findings

Audit against `docs/REFACTOR_PLAN.md` §5 (SOLID), `CLAUDE.md` and
`docs/SCALARS.md`. Only open findings are listed; resolved ones are in git
history.

**Constraint for any cleanup:** zero behaviour change. The golden telemetry
(`tests/test_golden.py`) is the only complete specification of correct
behaviour. If a cleanup would change a number, list it here instead.

Already sound, no fix needed: the import guard holds (`fly/` never imports
`mario/` or `bridge/`; `sim/episode.py` and `sim/protocols.py` import
neither); there is no `Circuit` base class; `Episode` composes only
`Policy` + `Environment` + observers; `JumpPolicy` takes its own
`JumpParams`; `fly/sensing/retinotopy.py` is a deliberate negative-result
artifact (default `retinotopic=False` matches every golden).

## S — structure / SOLID

| ID | Finding | Risk if "fixed" now |
|---|---|---|
| **S1** | `FullPolicy` (`bridge/full_policy.py`) is a god-object: loads seven circuits, steps them, reads RAM, runs odour / habituation / climb / MDN / mushroom body, resolves buttons, and punishes on death in `on_step`. | High — splitting it restructures the golden path. |
| **S2** | `FullPolicy.__init__` takes a whole `ProjectConfig`; §5.3 wants each component to take its own frozen params, as `JumpPolicy` does. | Medium — safe without changing defaults, but large. |
| **S3** | `HabituationParams`, `NetworkParams`, `EntityParams`, `RetinotopyParams` are documentation-only at runtime: live code reads module constants, and `tests/test_params_match_live.py` keeps the pairs equal. Editing them in a project JSON does not change an episode. | Medium — wiring them through needs its own sprint. |

`AdaptiveHybridState(HybridState)` in `fly/network/dynamics.py` is the only
remaining inheritance. Diagnostic-only; the live path uses `Integrator`.

## Do not merge

Each of these lookalikes differs in one load-bearing way:

- `bridge/perception.py`'s `mushroom_odor` / `goomba_odor` /
  `question_block_odor` / `enemy_thetas` — different filters and units.
- The steering / MDN / speed / DNp02 circuit builders — different cores;
  DNp02 adds an explicit TTMn downstream exception.
- `Integrator.step` vs `HybridState.step` — locked bit-exact by
  `tests/test_integrator_equivalence.py`.
- `W_TILE = 16.0` (`fly/sensing/sensory.py`, `run_mario.py`) and
  `ENTITY_WIDTH_PX = 16` (registry) — unifying via the registry would make
  `fly/` import `mario/`.

`mario/ram/tile_ram.py` still defines `ADDR_MARIO_X` / `ADDR_MARIO_PAGE`
alongside `mario/ram/addresses.py` (same values).

## H — hard-coded values not among the 49 (RESOLVED, see git history)

All ten promoted into `config/params.py` (the codebase: commit that did
this promotion), each with identical defaults, the golden gate green
throughout, `docs/SCALARS.md` regenerated. The literal locations below
are retained as a record of what moved where, not as open items:

| Location | Value | New home |
|---|---|---|
| `FullPolicy.__init__` | `MBON_DNA02_FRAC` L `0.00379`, R `0.00632` | `mushroom_body.mbon_dna02_frac_l` / `_r` |
| `FullPolicy.__init__` | `N_MB_SENSORY = 7`, 3 features per KC, RNG seed `0` | `mushroom_body.n_mb_sensory` / `.kc_features_per_cell` / `.kc_projection_seed` — all three marked `advanced=True` in their own field metadata (an architecture dimension and a seed the golden depends on bit-for-bit, not a gain like the rest of `config/params.py`) |
| `FullPolicy.act` | stomp if `abs(last_x - mario_x) < 20` | `interaction.stomp_distance_px` (new `InteractionParams` group — not one circuit's own gain). Still deliberately not 16 (`entity_width_px`) — the field's own provenance restates the audit's warning |
| `FullPolicy.act` | distance history capped at `10` | `interaction.closing_speed_history_frames` |
| `FullPolicy.act` / `Network.flush_denormals` | `1e-30` | `network.denormal_flush_threshold` — `Network.flush_denormals` keeps its own hardcoded default for callers with no config (`scripts/denormal_probe.py`), kept in sync by `tests/test_params_match_live.py`, same pattern as `dynamics.ALPHA`/`CLIP` |
| `FullPolicy.act` | `avers_r_eff > 1e-6` | `odour.avers_presence_gate` |
| `wide_gap_target_col` | `lead_tiles=10` | `demo.wide_gap_lead_tiles` — exercised by `tests/test_golden.py::test_017_reprise` via `inject_gap_frame`, so this one is NOT purely demo-only the way `mushroom_offset` is (checked directly while promoting it) |
| `poke_wide_gap` | `REFUSAL_GAP_TILES + 2` | `terrain.refusal_gap_margin_tiles` (the `+2` itself) |
| `question_block_odor` | `offset_tiles * 16` | reads `entity.entity_width_px` directly — not a new field, a de-duplication (this file's own "Do not merge" section already flagged the same pattern for `W_TILE`/`ENTITY_WIDTH_PX`) |
| `run_steering.MAX_FRAMES` / `ScenarioParams.max_frames` | both `1200` | `run_steering.MAX_FRAMES` deleted; `main()`'s own `max_frames` default now reads `ScenarioParams().max_frames` directly — one home, not two kept equal by hand |

A real bug surfaced while promoting these:
`config.project_config._from_dict` (and `tool.core.tool_settings._from_dict`,
same pattern) passed an explicit `None` for any field name absent from a
saved JSON, instead of leaving it out of `kwargs` so the dataclass's own
default applies — harmless while every field had always existed, but a
`TypeError` two layers down the moment a new field (e.g.
`mushroom_body.n_mb_sensory`) was added and an older `config.json`
without it was loaded. Fixed in the same commit; both functions now skip
absent keys entirely rather than defaulting them to `None`.

Outside the 49 (and outside this promotion) by category: `N_THRESHOLD =
60` / `load_jump(N=60)` define subgraph membership; `FitnessWeights`
defaults; `AdaptiveHybridState`'s `alpha_a` / `beta` (diagnostic only).

## D — scripts out of step with the current layout

Diagnostic scripts only; nothing on the golden path. **Note only.**

| Location | Finding |
|---|---|
| `scripts/compare_controllers.py` | Writes its three videos to top-level `runs/004a_real.mp4`, `runs/004b_shuffled_best.mp4` and `runs/004c_theta.mp4`, not `projects/<name>/runs/`. |
| `scripts/bench_episodes.py` | Writes and deletes top-level `runs/_bench_tmp.mp4`. |
| `scripts/diag4.py` | Its docstring calls the no-argument run the "current run_mario.py config", but the default is `--g 3.5`, while `JumpParams.g` is 2.0. |
| `scripts/tune_steering.py`, `scripts/tune_terrain.py` | The closing "Decision" paragraphs, including their `rho(g=1)` values, are fixed text, not computed from that run. |

## Out of scope for cleanup

- Split `FullPolicy`, or migrate `run_steering.main()` onto `Episode`.
- ~~Move the H values into `config/params.py`~~ — **done** (section H
  above): promoted under the exact discipline this line was warning
  against skipping (identical defaults, golden gate green throughout),
  not by ignoring the warning. Struck, not deleted, so the reasoning
  for why it was originally flagged stays on record.
- Unify the circuit builders or odour helpers.
- Touch `fly/network/dynamics.py`, `Integrator`, plasticity, RAM maps, or
  anything under `projects/`.
- Flush denormals on the jump circuit (re-baselines goldens 001–026).
