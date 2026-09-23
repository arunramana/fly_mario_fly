# fly_mario tool — build plan

Status: P0 and P1 done 2026-09-23 (P0 results in section 6; P1 -- C1-C4 --
in `tool/CODEBASE_CHANGES.md`, golden gate green after each), awaiting
review before P2. Written 2026-09-23, after the September cleanup
(`docs/CHANGES_2026-09.md`, HEAD `f55396e`).

The goal (from the project doc `fly-mario-tool-vision.md`): a tool that feels like a game. Pick a character, tune the world and the
brain, press Play, watch the fly perform, and compare outcomes across runs.

---

## 0. Ground rules

1. **The tool lives in `tool/` and is a client of the codebase.** It imports
   `config/`, `sim/`, `render/`, `bridge/`, `run_steering`; nothing outside
   `tool/` ever imports `tool/`.
2. **The codebase is used as is, except where it cannot back a GUI.** Each
   such change (section 4, `C1`–`C9`) must be:
   - **additive and default-preserving**: a new optional argument whose
     default reproduces today's behaviour exactly;
   - **proven by the golden gate**: all 57 existing tests pass and the three
     golden CSVs stay byte-identical after it;
   - **documented** in `tool/CODEBASE_CHANGES.md` (what, why, which default
     keeps old behaviour, which test proves it) and in the commit message;
   - **its own commit**, prefixed `codebase:` (tool work is prefixed `tool:`).
3. **A change that alters behaviour when switched on** (per-entity smells,
   the character's hunger override) is a science change, not tool plumbing:
   it gets a `docs/SPEC_*.md`, a recorded run, a `docs/RUNS.md` entry and the
   shuffled-connectome control, per `CLAUDE.md`.
4. **No control lies.** Every GUI control is tagged `live`, `partial` or
   `not wired`. `not wired` controls are shown greyed with a tooltip saying
   what is missing. A control is only enabled once a test shows that changing
   it changes telemetry.
5. **Every run is reproducible.** A run stores a frozen snapshot of the full
   config, the seed and the git commit alongside its outputs.

---

## 1. User flow

```
 ┌──────────────── Project gate (cannot be skipped) ────────────────┐
 │  New project · Duplicate project (e.g. legacy) · Open · Recent    │
 └──────────────────────────────┬───────────────────────────────────┘
                                ▼
 ┌─ header: project name · dirty marker · Save · [▶ Play] ───────────┐
 │ 1 Character │ 2 Enemies │ 3 Objects │ 4 Circuits │ 5 Goal │ 6 Settings │ 7 Run │
 └──────────────────────────────────────────────────────────────────┘
```

Your seven tabs are kept, with the review's fixes folded in:

| Tab | Contents | Change from the original idea |
|---|---|---|
| 1 Character | Mario / Luigi; internal state: hunger, starting power-up, arousal (pC1) | Luigi is a display-only colour swap done in `tool/` (P0 found the RAM poke freezes movement — see the note below section 4's table); the game and telemetry are identical because it's the same Mario run underneath |
| 2 Enemies | Goomba, Koopa, generic enemy: odour channel, valence, intensity, looming salience, danger weight | Driven by `EntityKind` + `bridge/profiles/default.json`, not a hand-made list |
| 3 Objects & terrain | Power-ups, ? blocks, used blocks, pipes/solids, pits/gaps | Terrain added (pits, gaps, walls were missing) |
| 4 Circuits & control | Every scalar in `config/params.py` grouped per circuit, with range and provenance (invented/measured); noise σ + seed; **shuffled-connectome toggle** | Shuffle added (CLAUDE.md invariant 6); noise "off" = σ 0 |
| 5 Goal & fitness | Home signal (`home_bias`, side), fitness weights (points/distance/time), level, max frames, seeds × episodes, learning on/off | Seeds/episodes added: fitness only matters across many runs |
| 6 Settings & rendering | Parallel workers, frame skip, video on/off, brain panel on/off, live preview fps, output folder | No GPU toggle (CLAUDE.md: GPU loses on this workload); shown as info only |
| 7 Run | Live preview, progress, cancel; run history; telemetry plots; video playback; run comparison; RUNS-style note | Play is also always in the header so edit→play doesn't need a tab switch |

---

## 2. Technology

- **GUI: PySide6 (Qt)** — native Windows desktop app, real threads and
  processes, video widget (`QMediaPlayer`), image streaming for the live
  preview. Plots: `pyqtgraph`. Rejected: Streamlit/Gradio
  (rerun model fights live preview and long runs), NiceGUI (viable, but
  browser round-trip for 60fps frames). **Chosen: PySide6.**
- **Runs execute in a separate process** (`multiprocessing`, spawn on
  Windows), never in the GUI thread. nes-py is CPU-bound and sequential.
  The worker sends frames and telemetry rows back over a queue; the GUI
  throttles the preview.
- **Parallel seeds**: `ProcessPoolExecutor`, one run per worker,
  `OMP_NUM_THREADS=1` (CLAUDE.md, ~8× on this box).
- Dependencies go in `tool/requirements.txt` (on top of the pinned root
  `requirements.txt`; check PySide6 against `numpy<2`/Python 3.12 in P0).

---

## 3. `tool/` layout

```
tool/
  PLAN.md                 this file
  CODEBASE_CHANGES.md     log of every change made outside tool/
  README.md               how to launch and use
  requirements.txt
  __main__.py             python -m tool
  core/                   NO Qt imports -- fully testable headless
    project.py            ToolProject: open/create/duplicate/save projects/<name>/
    tool_settings.py      frozen dataclasses for what ProjectConfig doesn't hold:
                          CharacterSettings, EntityProfiles, FitnessSettings,
                          ExperimentSettings, RenderSettings
    schema.py             introspects config/params.py dataclasses -> ControlSpec
                          (name, type, default, range, provenance, group, wiring)
    wiring.py             the live/partial/not-wired table, one source of truth
    run_spec.py           RunSpec = ProjectConfig + tool settings + seed, frozen
    runner.py             worker entry point: RunSpec -> run_steering.main(...);
                          P2 also owns the persistent warm-worker pool (below)
    palette.py            Mario<->Luigi sprite colour remap on a displayed RGB
                          frame (tool-only, no RAM/game-state touch -- P0's
                          Luigi note below section 4's table)
    run_store.py          NNN numbering, snapshot, index.json, outputs per run
    batch.py              seeds x episodes, parallel, aggregate results
    fitness.py            thin wrapper over sim/fitness.py for a finished run
  ui/
    app.py                QApplication, theme, main window
    gate.py               project gate dialog
    main_window.py        header (Play/Save/dirty) + tab widget
    widgets/param_form.py auto-built form from ControlSpecs (sliders, spin
                          boxes, range clamps, provenance tooltips, greyed if
                          not wired, reset-to-default)
    widgets/preview.py    live preview: the raw `obs` RGB frame (through
                          `palette.py` if Luigi is selected) plus telemetry
                          bars (per-population activation as simple bars, not
                          the full anatomical brain panel -- P0's 14fps
                          finding rules that out for anything real-time). The
                          full `render.brain_panel` composition stays a
                          post-run, offline step (already proven at ~14fps,
                          fine when nothing needs to watch it live)
    widgets/plots.py      telemetry plots
    tabs/character.py enemies.py objects.py circuits.py goal.py settings.py run.py
  tests/                  core unit tests + pytest-qt smoke tests
```

**Project folder on disk** (extends what exists, nothing replaced):

```
projects/<name>/
  config.json        ProjectConfig (existing format, untouched)
  tool.json          tool settings (character, entity profiles, fitness, render)
  runs/              NNN_slug.mp4 + NNN_slug.md (existing convention)
  telemetry/         NNN_slug_telemetry.csv (existing convention)
  tool_runs/index.json   run history: NNN, time, git commit, seed, summary,
                         fitness, paths, full RunSpec snapshot
```

---

## 4. Codebase changes needed (C1–C9)

Audited against the current code. Ordered by need.

| ID | Change | Why the tool needs it | Default that keeps behaviour | Proof |
|---|---|---|---|---|
| **C1** | `run_steering.main(config=None)`; `sim/project_runner.run_from_config` passes the config through | Today `main()` builds a fresh default `ProjectConfig` and only swaps in σ, so every Circuits-tab change would be ignored | `None` → `ProjectConfig()` as today | goldens + roundtrip; new test: changing `jump.g` in a config changes telemetry |
| **C2** | Wire the four documentation-only param groups (`NetworkParams`, `HabituationParams`, `EntityParams`, `RetinotopyParams`, audit S3) through constructors instead of module constants | Otherwise those controls are `not wired` | constructor defaults = today's constants | goldens + `test_params_match_live` |
| **C3** | `main(on_frame=None, should_stop=None)`: per-frame callback (frame index, RGB frame, telemetry row) and a cancel check | Live preview, progress bar, Cancel button | `None` → no call, no check | goldens |
| **C4** | Put game score/coins/time/flag from the gym `info` dict into the returned summary `info` (not the CSV) | Fitness "points" has nothing to read today | summary dict gains keys; CSV untouched | goldens (CSV unchanged) + unit test |
| **C5** | `FullPolicy(shuffle_seed=None)` / `main(shuffle_seed=None)` using `fly/connectome/circuit.py`'s `shuffle_edges`/`build_shuffled` | Shuffled-connectome toggle in tab 4 | `None` → real connectome | goldens; new test: shuffled run differs |
| **C6** | **Retired, moved to tool scope.** No codebase change: see the Luigi note below the table. | — | — | — |
| **C7** | Character internal state: `hunger_override=None` (today hunger is read from Mario's size, RAM 0x0756) and starting power-up (reuse `force_mario_size` + `force_size_from_frame=0`) | Tab 1 controls | `None` → read from RAM | goldens; **science change when used** (rule 3) |
| **C8** | Per-entity perception: perception reads per-kind odour channels/gains/valence/looming salience from an entity-profile file (`bridge/profiles/default.json` already has the schema and distinct Goomba/Koopa channels) | Tabs 2–3: "smell differently, not just more or less" | `entity_profiles=None` → today's single aggregate | goldens; own SPEC + RUNS entry + shuffle control (**science sprint**) |
| **C9** | pC1 arousal as an input | Tab 1 "arousal" | not built; stays `not wired` until a SPEC exists | — |

Not changed: `FullPolicy`'s split (audit S1), the H-list literals, denormal
flush, anything under `projects/legacy/`. The tool works around them.

**Luigi, redesigned after P0 (was C6):** the RAM poke (0x0753) freezes
movement (P0, section 6) — it is not a display choice, it changes what the
game engine does. Dropped entirely; the codebase never learns a player
selection exists. Instead, `tool/core/palette.py` remaps Mario's sprite
colours to Luigi's on the **displayed** RGB frame only — the frame `obs`
array the emulator already returns, after it leaves `run_steering.main()`,
before it reaches the preview widget or an exported video. The RAM, the
telemetry, the circuit's decisions and the recorded CSV are all untouched
and identical to a Mario run with the same seed — there is no `player=`
argument anywhere in the codebase, and no golden gate exposure at all,
because nothing outside `tool/` changes. Wiring moves from P5 (it was
gated on C6 landing) to whichever phase first displays a frame — P4 in
section 6's numbering, since that's the live preview and the recorded
video are the only two places a frame is ever shown.

---

## 5. Wiring status per tab (at the end of each phase)

| Control | Today | After P1 | After P4 | After P5 | After P6 |
|---|---|---|---|---|---|
| Character Mario/Luigi | not wired | not wired | **live** (`tool/core/palette.py`, display-only, moved up from P5 now that C6 is gone) | live | live |
| Hunger / power-up | not wired | not wired | not wired | live (C7) | live |
| Arousal pC1 | not wired | not wired | not wired | not wired | not wired (C9) |
| Enemy/object smell, looming, danger | not wired | not wired | not wired | not wired | live (C8) |
| Circuit scalars (49) | partial (σ only via runner) | live (C1, C2) | live | live | live |
| Noise σ, seed | live | live | live | live | live |
| Shuffled connectome | not wired | not wired | not wired | live (C5) | live |
| Home bias, level, frames | live | live | live | live | live |
| Fitness weights | score-only | points live (C4) | live | live | live |
| Frame skip, video, brain panel | live | live | live | live | live |
| Parallel workers | — | — | live (tool batch) | live | live |

---

## 6. Phases

Each phase ends with the golden gate green and a short entry in
`tool/CODEBASE_CHANGES.md` (codebase phases) or `tool/README.md` (tool phases).

**P0 — Spikes (answer the unknowns first)** — done 2026-09-23, results below.

- **Timing** (1-1, σ=0, seed=0; `max_frames=1500` but the circuit always
  dies at 689 frames first, so every number below is one full 689-frame
  episode):
  - First `main()` call in a fresh process (pays the circuit-load cost
    run_steering.py's own docstring already flags, ~6.8s): **18.2s**
    total.
  - Warm process, `record_video=False`, `write_telemetry=False`:
    **6.9s** (99.2 frames/sec).
  - Warm process, `record_video=True` (per-frame PNG capture during the
    loop + `render.brain_panel.render_run` after it): **48.2s**
    (14.3 frames/sec) — **~7x slower (594% overhead)**.
  - Not broken down further here (PNG capture during the loop vs. the
    final `render_run`/ffmpeg pass) — that split needs its own profile
    before P4's preview design is finalised, per CLAUDE.md invariant 7.
  - **Decision this sets**: the live preview (P4) cannot push frames
    through the recording pipeline in real time (14fps is unusable as a
    preview rate) — it needs its own lightweight per-frame path (raw RGB
    over the queue; brain panel optional/throttled, not the recording
    composition). Parallel batches (P2) matter even for short runs: each
    fresh worker process pays ~7-8s of circuit-load cost before any
    simulation happens (confirmed again by the worker spike below), so N
    sequential short runs cost roughly N×8s before N×(frames/99) of
    actual simulation.

- **Luigi poke — fails, and not for the risk the plan named.** Poking RAM
  `0x0753` (SMB1 ROM-hacking references call this "current player":
  0=Mario, 1=Luigi) to `1` right after `env.reset()`:
  - Does not crash, and the gym wrapper's `info` dict is unaffected (same
    keys before and after: `coins, flag_get, life, score, stage, status,
    time, world, x_pos, y_pos`) over 120 held frames.
  - **But it is not cosmetic — it freezes movement outright.** Isolated
    from the circuit entirely (forced action, hold right+B, 60 frames):
    unpoked, `x_pos` goes 40 → 177; poked, `x_pos` stays at exactly 40 for
    all 60 frames, while `RAM[0x0753]` itself stays at 1 the whole time
    (confirmed still poked, not reverted by the game). This is a
    physics-level freeze, not a circuit-decision problem.
  - A full circuit-driven run confirms the same thing at the top level:
    the Mario baseline (σ=0, seed=0) dies at 689 frames, max_x=1432, 9
    escape jumps; the identically-configured "Luigi" run hits
    `max_frames=800` with **0** escape jumps and max_x=40 (never leaves
    the spawn tile — nothing in the circuit's repertoire ever gets
    triggered because nothing on screen ever changes). Telemetry is not
    remotely close between the two (every circuit-derived column
    differs), the opposite of the plan's "identical physics" assumption.
  - **Conclusion: C6 as scoped in section 4 does not work as written.**
    Candidates not root-caused here (P0 is a quick spike, not a
    disassembly session): `0x0753` may be the wrong address for this
    ROM/mapper build; the poke may need to happen before `reset()`
    rather than after, or be held every frame rather than applied once;
    or a companion RAM value (a "number of players"/game-mode byte) may
    also need setting for this build to honour it. Section 4's own "P0
    spike verifies the poke is safe" should be read as **verifies the
    poke does NOT work as assumed**, not as confirmation — C6 needs its
    own follow-up investigation (try before-reset, try held-every-frame,
    check what SMB1's real 2-player alternation reads at a life/level
    transition) before it belongs in P5's schedule as currently written.

- **PySide6 + pyqtgraph**: `pip install` into the pinned venv is clean —
  `numpy` stays at `1.26.4` (root pin: `<2`), confirmed both by pip's own
  dependency resolution (no numpy line in the install output) and by
  re-importing `numpy` afterward. `tests/golden/` stays 3/3 byte-identical
  after the install. `QApplication`, `QLabel`, and a `pyqtgraph.
  PlotWidget` all construct without error. Versions recorded in the new
  `tool/requirements.txt`: `PySide6==6.11.2`, `pyqtgraph==0.14.0`.
  - **Worker-process spawn**: Windows' default `multiprocessing` start
    method is already `spawn` (`mp.get_start_method()` confirms it
    without calling `set_start_method`). A `get_context("spawn").
    Process` target that imports `run_steering` and calls
    `main(max_frames=60, ...)`, returning a result dict over a `Queue`,
    completed cleanly: exit code 0, `{n_frames: 60, died: False, max_x:
    168}` back in **12.96s** wall time — dominated by the same ~7-8s
    fresh-process circuit-load cost the timing spike measured, not by
    the 60 simulated frames themselves.
  - **Framework decision confirmed**: PySide6 works in this venv without
    disturbing the numpy/gym/nes-py pins, and the spawn-worker shape
    `tool/core/runner.py` needs (import `run_steering` in a spawned
    process, return results over a queue) is proven end to end.

**Net effect on the plan.** The timing and PySide6 spikes came back
positive and confirm sections 1-3 and 6 as written. The Luigi spike found
a real problem, just not the one the risk table anticipated (it doesn't
break the gym wrapper; it breaks the character's ability to move at
all) — **decided:** C6 is dropped, redesigned as a display-only colour
swap entirely inside `tool/` (see the note under section 4's table, and
the updated section 1/3/5/6/8 entries above). No RAM poke, no codebase
change, no golden-gate exposure; wiring moves up from P5 to P4.

**P1 — Codebase enablement: C1, C2, C3, C4**
- Make configs actually drive runs, add the frame hook/cancel, expose score.
- New tests: config-sensitivity test (C1), callback/cancel test (C3),
  summary-keys test (C4).

**P2 — Tool core, headless (no Qt)**
- `project.py`, `tool_settings.py`, `schema.py`, `wiring.py`, `run_spec.py`,
  `runner.py`, `run_store.py`, `batch.py`, `fitness.py`.
- A CLI proves it end to end before any UI exists:
  `python -m tool.core.cli run <project> --seed 3` and `... batch --seeds 8`.
- **Persistent warm workers.** P0's timing spike found ~7-8s of fixed
  circuit-load cost per fresh process (section 6's P0 results above) —
  `runner.py` keeps a small pool of long-lived worker processes (each
  imports `run_steering`/`bridge.full_policy` once, keeping their
  `_circuit_cache` warm) instead of spawning fresh per run, so a batch of
  N runs pays that cost once per worker, not once per run.
- **The test this needs, before it ships**: a reused (warm) worker's
  telemetry for a given `RunSpec` must be byte-for-byte identical to the
  same `RunSpec` run in a fresh process. This is not assumed safe —
  `bridge/full_policy.py`'s `FullPolicy._prev_avoid_odor`/`_last_x` are
  documented CLASS-level attributes (a deliberately preserved quirk from
  `main._prev_avoid_odor`'s original function-attribute behaviour, phase
  5b), meaning they persist across `FullPolicy` INSTANCES within one
  process. A fresh process resets them to the class body's defaults every
  time; a warm worker running episode 2 right after episode 1 would not.
  Expect this test to fail on first write and to need a real fix (make
  them per-instance, reset in `reset()`) before persistent workers are
  safe — a small, additive, golden-gate-provable codebase change if so,
  not assumed here.
- Tests: project create/duplicate/save round-trip, schema covers all 49
  scalars with ranges, run numbering never reuses a number, snapshot
  reproduces telemetry byte-for-byte, warm-worker-vs-fresh-process
  telemetry identity (above).

**P3 — UI shell**
- Project gate (new / duplicate / open / recent), main window, header with
  Play/Save/dirty state, seven tabs as skeletons.
- `param_form` auto-builds tab 4 from `schema.py`: validation from ranges,
  provenance tooltips, reset-to-default, greyed `not wired` controls.
- Unsaved-changes guard on close and before Play.

**P4 — Run tab (the payoff)**
- Play → worker process → live preview: the raw `obs` RGB frame each
  `on_frame` callback (C3) hands back, recoloured through `palette.py`
  when Luigi is selected, plus telemetry bars (per-population activation,
  cheap to draw every frame) — not the full `render.brain_panel`
  composition, which P0 measured at 14fps, unusable live. Progress, Cancel.
- Luigi becomes live here (moved up from P5 — no codebase gate left once
  C6 was dropped; see the note under section 4's table).
- Run history table from `tool_runs/index.json`; select a run to see its
  summary, fitness, telemetry plots (x-progress, DNp01/Giant Fiber, steering
  L/R, odour, jumps) and play its video.
- Compare two runs, and a batch view: distribution of distance/fitness across
  seeds (the vision doc's "a distribution, not one trajectory").
- Auto-writes `runs/NNN_slug.md` with setup and numbers; the user adds the
  "what we learned" line. The tool never appends to `docs/RUNS.md` (decision 2).

**P5 — Tabs 1, 4, 5, 6 fully live: C5, C7**
- Character tab (hunger, starting power-up — Mario/Luigi is already live
  from P4), shuffled toggle, goal & fitness tab, settings tab with
  parallel batches.
- C7 used for the first time → one recorded run + RUNS entry.

**P6 — Tabs 2 and 3 live: C8 (science sprint)**
- `docs/SPEC_entity_perception.md` first. Then per-kind channels in
  perception, entity-profile editor in tabs 2–3 writing
  `projects/<name>/tool.json`, shuffled control, recorded runs, RUNS entry.

**P7 — Polish**
- Presets (save/load a tab's settings), keyboard shortcuts, export a run
  bundle (config + CSV + video + note), `tool/README.md` with screenshots.

---

## 7. Testing

- **Golden gate**: `pytest tests/` after every `codebase:` commit; the three
  golden CSVs must stay byte-identical.
- **Tool core**: `pytest tool/tests/` headless, no emulator for most tests;
  one slow test runs a 60-frame episode through the worker.
- **UI smoke**: `pytest-qt` opens the gate, creates a project, flips a
  control, presses Play on a short run, sees a history row.
- **Honesty test**: for every control marked `live` in `wiring.py`, a test
  checks that changing it changes telemetry. That test is the definition of
  `live`.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Runs are slow, so the preview feels dead | P0 timing; frame-skip and video-off defaults; preview throttled |
| nes-py / spawn issues on Windows | P0 spike before any UI |
| Module constants read at import (e.g. `run_steering.ODOUR_GAIN`) bypass the config | C1/C2 audit; each run in a fresh process; the honesty test catches misses |
| Warm-worker reuse leaks state between runs (e.g. `FullPolicy`'s class-level `_prev_avoid_odor`/`_last_x`) | P2's byte-for-byte warm-vs-fresh test; fix before shipping the pool, not after |
| Per-entity smell changes behaviour | C8 only as a SPEC'd science sprint with controls |
| Tool edits drift from `docs/SCALARS.md` ranges | `schema.py` reads ranges from `config/params.py`, never duplicates them |

---

## 9. Decisions (Arun, 2026-09-23)

1. GUI framework: **PySide6**.
2. `docs/RUNS.md`: the tool **never** appends to it. It writes only
   `runs/NNN_slug.md`; Arun writes the RUNS entry.
3. `not wired` controls: **shown greyed**, with a tooltip saying what is missing.
4. Implementation is done **only in Claude Code opened in `fly_mario/`**,
   one phase at a time, following this plan and `CLAUDE.md`.
