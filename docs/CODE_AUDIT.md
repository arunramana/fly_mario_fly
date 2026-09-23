# Code audit — SOLID, coupling, dead code, hard-coded scalars

Audit against `docs/REFACTOR_PLAN.md` §5 (SOLID pass), `CLAUDE.md`, and
`docs/SCALARS.md`. Method: AST import guards (`tests/test_import_guard.py`),
class/responsibility inventory, config vs live-path comparison, and a
literal scan of numbers not listed among the 49 documented scalars.

**Constraint for any cleanup that follows this audit:** zero behaviour
change. Golden telemetry (`tests/test_golden.py`) is the only complete
specification of correct behaviour. If a cleanup would change a number,
do not do it — list it here instead.

---

## 1. Scope and method

| Check | How |
|---|---|
| `fly/` never imports `mario/` or `bridge/` | AST walk of every `fly/**/*.py` import |
| `sim/episode.py` / `sim/protocols.py` stay generic | AST forbid of `fly`/`mario`/`bridge` |
| SOLID §5.1–5.3 | Class tree, constructor params, SRP on `Episode` / policies |
| Scalar honesty | `config/params.py` + `docs/SCALARS.md` vs bare literals in live path |
| Dead / duplicate code | Call-site search; do not merge lookalikes that differ |

Out of this document's cleanup mandate: circuit logic, integrator,
plasticity, RAM addresses, `projects/`, and dormant-but-intentional
`fly/sensing/retinotopy.py` (closed negative result, sprints 023–024).

---

## 2. Explicit non-findings

These already match the plan and need no fix from this audit.

- **Import guard holds.** No `fly/` module imports `mario` or `bridge`. No
  `mario/` module imports `fly`. `sim/episode.py` and `sim/protocols.py`
  import neither side.
- **No `Circuit` base class.** Circuits are factories/`Network` configs
  (`REFACTOR_PLAN.md` §5.1). `Network` has no subclasses.
- **`Episode` is clean.** Composes `Policy` + `Environment` + observers;
  does not own telemetry writing or circuit loading (§5.2).
- **`JumpPolicy` takes its own params.** Constructor accepts `JumpParams`
  only — the shape §5.3 asked for.
- **`retinotopy.py` is intentional.** Kept as a negative-result artifact;
  default `retinotopic=False` matches every golden.

---

## 3. Findings

Severity prefixes: **S** structure/SOLID, **C** coupling (names or
boundaries the import guard cannot see), **D** dead/duplicate, **H**
hard-coded scalars missed by the documented 49.

### S — structure / SOLID

| ID | Finding | Risk if "fixed" now |
|---|---|---|
| **S1** | `bridge/full_policy.py` `FullPolicy` is a god-object: loads seven circuits, steps them, reads RAM, runs odour / habituation / climb / MDN / mushroom body, resolves buttons, and implements `on_step` for death punishment. That is the old `run_steering.main()` loop moved into one type — SRP vs §5.2's thinner `Policy`. | High — splitting it is a restructuring of the golden path, not a rename. |
| **S2** | `FullPolicy.__init__` takes a whole `ProjectConfig`. §5.3: each component gets its own frozen params; `ProjectConfig` exists only to compose and serialise. `JumpPolicy` already does this correctly. | Medium — threading per-group params without changing defaults is safe but large; not a format pass. |
| **S3** | Four param groups are documentation-only at runtime: `HabituationParams`, `NetworkParams`, `EntityParams`, `RetinotopyParams`. Live code still reads module constants (`HAB_*`, `dynamics.ALPHA`/`CLIP`/`SUBSTEPS`, `ENTITY_WIDTH_PX`, retinotopy literals). `tests/test_params_match_live.py` keeps the pairs equal; editing those fields in a project JSON does not change an episode. Documented as deliberate in `config/params.py` (phase 4). | Medium — wiring them through without value drift is a dedicated sprint. |

`AdaptiveHybridState(HybridState)` in `fly/network/dynamics.py` is the
remaining inheritance relationship. Diagnostic-only (`adapt_sweep.py`,
`diag4.py`); live path uses `Integrator`. Do not touch in a cleanup pass
(integrator is off-limits).

### C — coupling the import guard misses

| ID | Finding | Cleanup status |
|---|---|---|
| **C1** | `ReflexHabituation.check(self, mario_x)` — fly/ takes a plain float and never reads RAM, but the parameter name is Mario-specific. `fly/sensing/sensory.py` mentions Goombas in a comment on a synthetic trace. | Rename `mario_x` → `x` (positional call sites only). Comment left as documentation. |
| **C2** | `bridge/motor.py` re-exports `action_index` as the planned motor boundary (`REFACTOR_PLAN.md` §2). Nothing imported it; `JumpPolicy` and `FullPolicy` called `mario.actions.actions.action_index` directly. | Route both policies through `bridge.motor.action_index` (same function object). |

`mario/ram/tile_ram.py` still defines `ADDR_MARIO_X` / `ADDR_MARIO_PAGE`
alongside `mario/ram/addresses.py`. Same literals; RAM addresses are
out of scope for this cleanup.

### D — dead code and false duplicates

| ID | Finding | Cleanup status |
|---|---|---|
| **D1** | `run_steering.py` still had `_circuit_cache`, `_memo_load`, and `make_steering_masks` after phase 5b moved the live copies into `bridge/full_policy.py`. Nothing called the `run_steering` copies. Unused imports (`Network`, `Integrator`, loaders, unused perception imports, etc.) were already removed before this pass. | Delete the three dead symbols; point `bench_episodes.py`'s comment at `full_policy`. |

**Do not merge** these lookalikes — each differs in one load-bearing way:

- Odour helpers in `bridge/perception.py` (`mushroom_odor` vs `goomba_odor`
  vs `question_block_odor` vs `enemy_thetas`) — different filters / units.
- Circuit builders (`steering` / `mdn` / `speed` / `dnp02`) — different
  cores; DNp02 adds an explicit TTMn downstream exception.
- `Integrator.step` vs `HybridState.step` — locked bit-exact by
  `tests/test_integrator_equivalence.py`; live vs diagnostic split is
  intentional.

`W_TILE = 16.0` (`fly/sensing/sensory.py`, `run_mario.py`) and
`ENTITY_WIDTH_PX = 16` (registry) are the same width in three homes.
Unifying via the registry would make `fly/` import `mario/` — forbidden.

Files unused by imports but **kept** (sprint scripts / stubs, not
garbage): `bridge/motor.py` (now wired), `load_lc10a_cached.py`,
`plot_mb_curve.py`, `lc10a_pursuit_circuit.py`, tune/diag scripts.
*Superseded by the later root-folder cleanup:* those three and four other
one-off scripts (`tune_climb_height2`, `sprint025_sweep`,
`rerun_battery_g2`, `profile_brain_panel`) were deleted. The surviving
tune/diag/sweep scripts moved to `scripts/`. `brain_panel.py` moved to
`render/`, and `pit_report.py`/`commitment_report.py` moved to `sim/`.

### H — hard-coded values not among the 49

These are live literals (or demo-only) absent from `docs/SCALARS.md`.
**Note only — do not move in this pass.** Extracting any of them risks a
silent golden mismatch if a value is "corrected" while editing.

| Location | Value | Role |
|---|---|---|
| `FullPolicy.__init__` | `MBON_DNA02_FRAC` L `0.00379`, R `0.00632` | MBON bias onto DNa02 / DNp02 every frame |
| `FullPolicy.__init__` | `N_MB_SENSORY = 7`, 3 features per KC, RNG seed `0` | Kenyon-cell projection (seed is part of the golden) |
| `FullPolicy.act` | stomp if `abs(last_x - mario_x) < 20` | Comment says one tile (16px); code is **20** — do not "fix" to 16 |
| `FullPolicy.act` | distance history capped at `10` | closing-speed estimate |
| `FullPolicy.act` / `Network.flush_denormals` | `1e-30` | denormal flush (jump still skips the call, phase 3) |
| `FullPolicy.act` | `avers_r_eff > 1e-6` | aversive-odour presence gate |
| `wide_gap_target_col` | `lead_tiles=10` | synthetic-gap demo only |
| `poke_wide_gap` | `REFUSAL_GAP_TILES + 2` | the `+2` is a second constant |
| `question_block_odor` | `offset_tiles * 16` | metatile width |
| `run_steering.MAX_FRAMES` / `ScenarioParams.max_frames` | both `1200` | two homes; scenario params are outside the 49 |

Also outside the 49 by category (not missed inventorship): `N_THRESHOLD = 60`
/ `load_jump(N=60)` define subgraph membership; `FitnessWeights` defaults;
`AdaptiveHybridState`'s `alpha_a` / `beta` (diagnostic only).

---

## 4. Out of scope for cleanup (do not do from this audit)

- Split `FullPolicy` or migrate `run_steering.main()` onto `Episode`
- Register or move H1 scalars into `config/params.py` / regenerate
  `SCALARS.md` as part of a format pass
- Unify circuit builders or odour helpers
- Touch `fly/network/dynamics.py`, `Integrator`, plasticity, RAM maps,
  or anything under `projects/`
- Delete sprint scripts (`plot_mb_curve.py`, `load_lc10a_cached.py`, etc.).
  Done later in the root-folder cleanup (see §3 D note).
- Flush denormals on the jump circuit (re-baselines goldens 001–026)

---

## 5. Cleanup applied from this audit

Behaviour-preserving only; verified with `pytest tests/` including
byte-identical goldens.

1. Unused imports already removed from `run_steering.py` (prior step).
2. Deleted dead `_circuit_cache`, `_memo_load`, `make_steering_masks` from
   `run_steering.py`; live copies remain in `bridge/full_policy.py`.
3. Renamed `ReflexHabituation.check` parameter `mario_x` → `x`.
4. Routed `JumpPolicy` / `FullPolicy` through `bridge.motor.action_index`.
