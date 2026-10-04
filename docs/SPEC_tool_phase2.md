# SPEC: tool skeleton + E1 scene (redesign phase 2)

Scope: `docs/REDESIGN_PLAN.md` section 7 phase 2 and the approved scope (E1 scene and eval; Experiments and Mechanisms library
screens; Watch and Results wired to the brain path). Nothing else: no goal cue (E0 is Phase 3), no builder, no smell/taste/pain,
no Koopas. The legacy path (`bridge/full_policy.py`, `fly/circuits/`, `run_steering.py`, `config/params.py`, `tool/core/runner.py`
behaviour, their tests and goldens) is not edited.

**The rule.** Stimuli enter only at sensory-tier neurons. Phase 2 adds no code that adds current to a neuron. The scene replay and
the metrics only read the emulator and the fly's outputs; the one new brain method (`Brain.population_rate`) is a read. Nothing is
tuned on game outcomes: the scene log and the survival definition below were fixed before any E1 run (the only check on the log is
that the scene is as described, see section 2).

## 1. Files (plan section 6)

| File | Status | Role |
|---|---|---|
| `brain/scenes/e1_goomba_approach.json`, `brain/scenes.py` | new | the E1 scene manifest (action log) and its replay and check |
| `brain/e1.py`, `scripts/eval_e1.py` | new | E1 episode, metrics, 20-seed real-vs-shuffled eval and CLI |
| `brain/library.py` | new | read-only experiment and mechanism catalogue with provenance |
| `brain/brain.py`, `brain/policy.py` | adapted (read-only additions) | `Brain.population_rate` (read), `BrainPolicy.last_theta/last_distance` (what the fly saw, for the record) |
| `brain/scalars.py`, `docs/SCALARS_BRAIN.md` | adapted | the five E1 conventions registered (invented); doc regenerated |
| `tool/core/brain_runner.py` | new, beside `tool/core/runner.py` | run one E1 episode into the run store, evaluation store |
| `tool/ui/brain_runs.py` | new | child processes for Run and eval, feeds the Run tab |
| `tool/ui/tabs/experiments.py`, `mechanisms.py`, `results.py`; `tool/core/tab_registry.py` | new / adapted | tabs 8 Experiments, 9 Mechanisms, 10 Results |
| `tool/ui/main_window.py` | adapted (4 small edits) | owns the controller, cancel hook, Play guard, Ctrl+1..9 |
| `tests/test_e1.py`, `tool/tests/test_brain_tool.py` | new | tests below; `test_tab_registry.py`, `test_ui_smoke.py` updated 7 -> 10 tabs |

Watch is the existing tab 7 (Run: player, brain map, controller pad, plots): a brain run is recorded in the run store with the same
files a legacy run has (raw frames, telemetry CSV, action log, summary), so no player code changed.

## 2. The E1 scene

`brain/scenes/e1_goomba_approach.json`: level 1-1 from reset, then a fixed action log, stored in the repo, expanded to explicit per-frame
actions: right+B for 60 frames (until the first Goomba, type 0x06, has spawned and is on screen), then no buttons for 50 frames
(Mario's x speed decays to zero: he stands still). The emulator is deterministic, so replay always gives the same state (hash of the
manifest stamped on every result). The fly (`BrainPolicy`) takes over on the next frame. At takeover the Goomba is about 90 px ahead
of Mario and takes about 140 frames to reach him if he does not move; no walking is provided or needed.

The log was written once. `scenes.check_scene` checks only: a Goomba on screen, ahead of Mario, Mario's x speed 0. (The first draft
had 30 no-button frames; the check showed Mario still sliding, so it became 50 (measured later, docs/RESULTS_redesign_phase2.md:
x speed after 10/20/30/40 idle frames is 34/19/4/0, so 30 still slides). That was a check of the described scene, not a look
at the fly's behaviour.) It is never checked or edited against whether the fly survives.

Only Goomba geometry is used: the 16 px sprite width of the registry, the 8 px Y-byte offset and Mario's small/big height of
`brain/perception.py`, validated in Phase 1 for a Goomba against small Mario on flat ground. Koopas and tall enemies are not used;
their geometry must be re-validated on synthetic objects before they are (not done here).

## 3. Metrics (fixed before any run), `brain/e1.py`

Per episode, frames counted from takeover. A Goomba slot is tracked from the scene's first on-screen Goomba.

- **contact**: first frame where the Goomba is active, `|dx| < 16` px and the vertical centre gap is below `(16 + Mario height)/2`
  (both boxes overlap).
- **resolved**: first frame where the Goomba is no longer a threat: entirely behind Mario (`dx <= -16`, he went over it or it passed) or its
  slot no longer holds an active Goomba (stomped and removed).
- **survived** (a): Mario is alive `E1_GRACE_FRAMES` (60, 1 s) after `resolved`. Dying at any earlier frame is not survived. An episode
  with no resolution in `E1_MAX_FRAMES` (600) is "timeout", counted as not survived and reported separately.
  Outcome label: `passed`, `stomped`, `died`, `timeout`.
- **GF before contact** (b): first GF spike frame <= contact frame (or no contact). At that first spike we record theta (degrees,
  the elevation-weighted value the fly was given, as in `BrainPolicy`) and the distance in px.
- Also per run: deaths, A pressed (any frame, and the number of frames).

Summaries use Wilson 95% intervals (`tool.core.evaluation.wilson_ci`). The plan's criterion (real >= 16/20, shuffled <= 2/20) is
printed next to the numbers; nothing is adjusted to meet it. Eval: seeds 3000-3019 (held out; not 1000-1019, 2000-2019, 9000), shuffle
seed 1 + i, same noise seed in both arms. The implementer smoke-checks one seed (9100) only; the experimenter runs the 20.

The five numbers (scene walk 60 and settle 50 frames, grace 60, max frames 600, 16 px box) are conventions of the experiment, tagged
invented in `brain/scalars.py` (31 brain scalars now: 24 invented + 6 calibrated + 1 measured; the sixth is `E1_LESION_CLAMP_HZ`, section 3b).

Note: in the shuffled arm Mario does not stand still after takeover; he retreats Left under noise-driven steering, which is why its
contact frames spread (116-299): see `docs/NOTE_e1_shuffled_contact_spread.md`. The scene is stationary only at takeover.

## 3b. GF-lesion control arm (approved-with-fixes round)

A third arm, `lesion_gf`, on the same seeds (3000-3019), the same noise seeds and the real connectome: both Giant Fiber cells
(`GF` = DNp01, the manifest's two cells, left and right) are silenced. It answers: is the jump the GF's doing, or does something
else in the circuit produce it?

- **What the lesion is.** After every network step the GF population's activity is held at `E1_LESION_CLAMP_HZ` (0 Hz): its output
  edges carry nothing (`Brain(lesion=("GF",))`, `Brain.lesioned`, a write of 0 to those cells only). It is removal. No current is
  added to any neuron; the guard test (no other writer of `_current`; the only `h[...] =` write besides the reset is this clamp,
  checked by its exact text) still holds. Only OUTPUT-tier populations can be lesioned (others raise).
- **Where it can be requested.** Only `brain.e1` (`arm="lesion_gf"` in `run_e1_episode`; `run_eval(arms=...)`; CLI `--arms`).
  `BrainPolicy` and `Brain` carry the argument through but nothing else passes it: the tool's `brain_runner`, Run/Experiments tab,
  Watch, play and `brain/library.py` do not mention it (a test greps for it). The tab 10 evaluation button runs
  the default arms (all three), which is the E1 evaluation, not a Run option.
- **What "GF fired" means (all arms).** The GF membrane crossed the calibrated threshold (the integrator's spike flag, read
  BEFORE the clamp), i.e. "would have fired". In the lesion arm this stays informative: the GF's own inputs (LC4, LPLC2) are
  untouched, so it can still cross while its output is cut. Two further numbers are reported per arm: `gf_output_max_hz` (peak GF
  population activity after the clamp; 0 in the lesion arm by construction) and `ttmn_max_hz` (peak TTMn over the episode; any
  residual in the lesion arm is drive reaching TTMn by paths other than the GF).
- **Reported per arm:** survived, GF fired (crossed), GF before contact, A pressed (runs), deaths, plus the two numbers above.
  Nothing is adjusted to a criterion; the lesion arm has none.
- **Tool.** Tab 10 shows the lesion row labelled `lesion_gf (control)` next to real and shuffled in the summary and the
  per-episode list, from `brain_eval.json` (evaluations saved before this round simply have two rows).
- **Smoke check (implementer, seeds 9100-9101 only).** The 3-arm CLI ran; the experimenter runs 3000-3019.

## 3c. Run default seed (R4)

The Experiments tab (Run) default brain noise seed is 9100, a development seed, not 3000. Tab 10's evaluation button is
labelled "held-out, run once" and keeps seeds 3000-3019.

## 4. Running E1

- CLI: `.venv/Scripts/python.exe -m brain.e1 --n 20 --seed0 3000 --workers 8 --out result.json` (also `-m scripts.eval_e1`). One seed:
  `--n 1 --seed0 9100`. Arms: `--arms real shuffled lesion_gf` (default all three; `--arms lesion_gf` alone runs the control).
- Tool: tab 8 Experiments, select E1, Run (real or shuffled) -> plays in tab 7 with brain map and pad; tab 10 Results, "Run E1
  evaluation" -> table real vs shuffled, criterion line, per-episode rows, saved to `projects/<name>/brain_eval.json`.

## 5. Library screens (read-only)

`brain/library.py` lists E0-E8 (scene, mechanisms on, pass criterion, controls, origin, status runnable/planned) and the nine plan
mechanisms (cue, entry neurons, input tier, evidence, origin, status). The tier label is honest: looming is "feature-level (D1)"
(enters at LPLC2/LC4, not photoreceptors); smell, taste and pain are "receptor" and planned. No switches or sliders: nothing a user
sets reaches the brain. The Mechanisms screen has no Build button (Phase 5).

## 6. Brain run path in the tool (`tool/core/brain_runner.py`)

`run_brain_one` plays one E1 episode (real, or shuffle seed s) and writes `<slug>_raw.npz`, `<slug>_telemetry.csv`
(columns the player, data panel and brain map already read: theta, d_px, lc4, lplc2, mem, spike, ttmn, dna01, dna02, dnp09, ...),
`<slug>_actions.npy` (scene log + the fly's presses) and a summary; `record_run` stores it with
`run_spec = {"kind": "brain_e1", scene hash, seed, shuffle seed, brain stamp}`. The legacy `run_one` is not called or changed.

## 7. Screens' behaviour

Run is refused while a legacy Play, training or another brain run is active; Cancel (and Escape) stops the brain run. Tabs 8-10
are added to `TAB_REGISTRY`; Ctrl+1..9 switch tabs.

## 8. Validation

- `tests/test_e1.py`: scene manifest is a fixed explicit log; replay is deterministic and matches the manifest; contact and
  resolution rules on made-up numbers; defaults are held-out seeds and the plan's criterion; summary maths; one real episode
  records what the spec says and is reproducible for a seed; library complete, tier labels present, only E1 runnable.
- `tool/tests/test_brain_tool.py`: libraries list and are read-only; Results renders a saved evaluation and the criterion line;
  a recorded brain run loads in the Watch tab; the Run button and the eval button work end to end through child processes; the
  legacy runner does not reference the brain path. Existing tab-count tests updated to 10.
- Scalars doc regenerated and checked by the existing test; full root `tests/` run once at the end (goldens byte-identical).
- Lesion round: `tests/test_e1.py` (lesion refused with a shuffle seed; the word appears only where the spec says, not in the
  Run path; lesion episode: GF output 0, TTMn far below real, GF still crosses threshold, no A), `tests/test_brain_core.py` guard
  allows only the exact clamp write, `tool/tests/test_brain_tool.py` (Run default 9100, button label, lesion row 'control',
  auto-filled run note).
- Not done: the 20-seed E1 evaluation (experimenter), Koopa geometry re-validation, builder, goal cue.
