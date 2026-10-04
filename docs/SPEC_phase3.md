# SPEC: sensed pursuit and home landmark, E0 and E3 (redesign phase 3)

Scope: `docs/REDESIGN_PLAN.md` section 7 phase 3, as narrowed by Arun's decisions after `docs/INVESTIGATION_phase3.md`. The legacy path is
frozen. Smell is NOT used (investigation: no innate effect); the odour mechanism stays in the library as "no innate effect; revisit with
learning". No builder, no taste or pain, no gaps.

**The rule.** Stimuli enter only at sensory-tier neurons. Both new mechanisms add drive to LC10a (a manifest sensory population) through
`Brain.apply`, which refuses every other id. `Brain` gains no public method (guard test unchanged). The motor map only reads; its
thresholds are the calibrated ones and are not inputs. Nothing is tuned on game outcomes: each value below is fixed by a rule written
here, run once on synthetic stimuli (a small moving dot; a static cue on the right), then frozen.

## 1. Files (plan section 6)

| File | Status | Role |
|---|---|---|
| `brain/manifest.py` | adapted | population `LC10a` (SENSORY, 275 = L135 + R140, ACh) and segment `LC10a->outputs` (k 3, N 5). Nothing else changes. |
| `brain/builder.py` | adapted | default file `brain_k3_N5_p3.npz` (the Phase 1 file is kept untouched); `shuffled(seed, mode)` adds the class-preserving mode (section 5) |
| `brain/calibration.json`, `brain/calibrate.py` | re-run once | new network hash; gates of section 2 |
| `brain/calibration.py`, `brain/scalars.py`, `docs/SCALARS_BRAIN.md` | adapted | `LC10A_GAIN`, `LC10A_AZIMUTH_SPLIT`, `GOAL_CUE_SALIENCE` (invented); experiment conventions of E0 and E3 registered like E1's |
| `brain/mechanisms.py` | adapted | `TargetMechanism` base on LC10a, `PursuitMechanism`, `HomeLandmarkMechanism`, `arousal()` |
| `brain/settings.py` | new | `SenseSettings`: pursued object kinds, landmark strength (what the Mechanisms tab edits) |
| `brain/perception.py` | adapted | `pursuit_target`: nearest visible, small, moving object of a pursued kind: azimuth and salience |
| `brain/policy.py` | adapted | attaches the new mechanisms when asked; reads its own previous output for the arousal state |
| `brain/senses_calibrate.py` | new | the synthetic dot / cue sweep that derives the three values (section 3), prints real vs 5 shuffles |
| `brain/scenes.py`, `brain/scenes/e0_walk_goal.json`, `e3_mushroom.json` | adapted / new | action-log scenes; optional per-frame scene rules (`clear_enemies`) |
| `brain/goal_eval.py` | new | E0 and E3 episodes, metrics, evals, CLI (`python -m brain.goal_eval E0|E3`) |
| `brain/e1.py`, `brain/library.py` | adapted | `shuffled_class` arm allowed; wording fix; library entries |
| `tool/core/brain_runner.py`, `tool/ui/brain_runs.py`, `tool/ui/tabs/{experiments,mechanisms,results}.py` | adapted | run and evaluate E0/E1/E3; Mechanisms controls; results columns |
| `tests/test_phase3.py`, `tool/tests/test_brain_tool.py` | new / adapted | section 7 |

## 2. LC10a in the network; calibration run ONCE

`python -m brain.builder` (new file) then `python -m brain.calibrate` once. Reported: new hash, both edge counts (built, non-zero), neurons.
Gates, unchanged from Phase 1 and NOT re-tuned if they fail (a fail is reported): disc, real GF fires at 38-48 deg for l/v 10, 20, 40, 80
with spread <= 8 deg, the 5 shuffles do not fire; rest, 0 GF spikes and motor signals below threshold (real, and printed for shuffles).

## 3. Value-fixing rules (written before any test; synthetic stimuli only)

Bench: `brain/senses_calibrate.py`. A dot is a constant drive for 50 frames from rest. Real network, noise seeds 9400-9404. "Per-neuron
drive e" is the value added to every LC10a neuron of a side each frame (rad treated as Hz one to one, as the looming encoding does).
Grid E = 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40. Measured on frames 20-49 (steady state); all of the following must hold in
all 5 seeds for a grid value to pass a test:

* **R test** (drive e on right LC10a only): right button on >= 90 % of frames; Left button on <= 5 %; MDN above its threshold on <= 5 %.
* **L test** (left only): steer < -threshold (the DNa steering rule, not MDN) on >= 90 %; Right on <= 5 %; MDN above threshold <= 5 %.
* **C test** (e/2 on both sides): Left button on <= 5 %.
* **B test** (R test drive): B (walk) on >= 90 % of frames.
* No GF threshold crossing in any test.

Window for a test set = the contiguous run of grid values, starting at the smallest passing one, that pass.

1. `GOAL_CUE_SALIENCE` (static cue, right only): window of {R, B}. Value = arithmetic midpoint of the window, rounded to 2 significant figures.
2. `LC10A_GAIN` (pursuit): arousal a (section 4) lies in [a_lo, 1] with a_lo = rest mean of DNp09 / walk threshold (from calibration.json).
   Window of {R, L, C} = [e_lo, e_hi]. Pursuit drive is G * a, so both ends must be inside: need e_lo / a_lo < e_hi. Value = arithmetic
   midpoint of [e_lo / a_lo, e_hi], 2 significant figures. **If that interval is empty the build stops and reports.**
3. `LC10A_AZIMUTH_SPLIT` (degrees): azimuth az in [-90, 90] gives the right share share_R = clip(0.5 + az / (2 SPLIT), 0, 1), share_L = 1 -
   share_R; drive onto each side = G * a * salience * share. Candidates 10, 20, 30, 45, 60, 90. Value = the LARGEST candidate for which, at
   both a = a_lo and a = 1, a dot at az = +45 passes the R test, az = -45 the L test and az = 0 the C test (with G fixed from rule 2).
   If none passes the build stops and reports.

Reporting only (not criteria): the same sweeps on 5 degree-preserving shuffles of the new network, and a no-stimulus rest.

## 4. Mechanisms

**Pursuit** (Ribeiro et al. 2018 Cell 174:607; Hindmarsh Sten et al. 2021 Nature 595:549 -- LC10 / small-object tracking circuits; snippet
level, orientation of the turn is the same-side-eye assumption [A]). Cue: a visible object of a pursued kind that is small (every
registry sprite is 16 px) and MOVING relative to the background (its world position changed since the previous frame; a static object
drives nothing). Nearest such object only. Azimuth = 90 deg * clip(dx / 128, -1, 1), dx = object minus Mario on screen, 128 = half the
NES screen; salience = the elevation weight of `brain/perception.py` (the object leaves the field at ELEVATION_LIMIT_DEG). Left of
Mario drives the left LC10a, right of him the right LC10a (same-side eye, ipsilateral turn). Pursued kinds are a per-object setting
(Mechanisms tab): goomba, koopa, enemy, powerup; default {powerup} (mushroom and other collectibles); a Goomba is NOT pursued by default.

**Arousal (the fly-state gain). OBSOLETE, REMOVED in section 11 (kept as history): it fed the fly's own DNp09 back into its sensory gain.** a = clip(DNp09 pooled activity of the PREVIOUS frame / walk_threshold, 0, 1): the fly's own walking-
related descending activity relative to its calibrated walking threshold, read from the brain's output, never from the game, no new
scalar (the threshold is the calibrated one; the one-frame delay is the frame loop). Biological basis: locomotion state raises visual gain in
the fly (Chiappe et al. 2010 Curr Biol; Maimon et al. 2010 Nat Neurosci; both from memory, [L-m]). It is a read of the fly applied at the
sensory entry; it forces no action. The loop is bounded (a <= 1, gain G <= e_hi by rule 2).

**Home landmark** (invented, counted, `GOAL_CUE_SALIENCE`). A persistent static cue at azimuth +90 deg: drive GOAL_CUE_SALIENCE onto the
right LC10a every frame. Honest label (library, docs, tool): it moves the "go right" assumption to the senses; it does not remove it. It
is a world-level fact (a goal is on the right), not a visible object, and LC10a prefers small moving objects, so a static cue is not
licensed by the literature. The shuffled arms receive exactly the same cue. Strength is a tool setting (a world property) with the
default above; 0 switches it off.

## 5. Controls

Degree-preserving shuffle (shuffle seed 1 + i, as before) in every eval. Class-preserving shuffle `shuffled_class` (same seeds): edges
are permuted only among edges whose post neuron is in the same tier group (each output population by name, each sensory population by
name, KC, MBON, DAN, interior), so random wiring cannot land looming input on output cells with few inputs (investigation row 9). It
is one small function; it is an extra arm in E0 and E3 evals and selectable in E1 (`--arms`), not part of E1's default arms. The GF-lesion
arm is not used in E0 or E3. MDN -> Left stays.

## 6. Experiments (conventions fixed before any run; invented, registered in `brain/scalars.py`)

Common: each result stores `gf_crossed` (the GF membrane crossed threshold, "GF fired"), `gf_output_max_hz`, `ttmn_max_hz` per episode and
per arm; the tool Results shows them (all experiments, all arms). Wilson 95 % intervals. Run default seed 9100 (smoke only);
held-out seeds E0 4000-4019, E3 5000-5019; the experimenter runs them once. The implementer runs seed 9100 only.

* **E0 walk to the goal.** Level 1-1 from reset (flat ground to the first pipe at x = 448), `clear_enemies` on (no Goomba: the experiment
  is the landmark alone), landmark on, looming on, pursuit on (nothing to pursue). **Reached** = Mario's world x >= E0_GOAL_X (400)
  within E0_MAX_FRAMES (600, 10 s); no death. Also reported: frames to reach, max x, deaths, A-press runs, GF crossed.
  Plan criterion: real >= 18/20, shuffled not (reported, not tuned).
* **E3 pursue the mushroom by sight.** Scene `e3_mushroom` (action log, deterministic, hashed: right 165 frames, none 45, A 14, none 60): Mario walks to the first
  power-up block (x about 336), stands under it, hits it from below and stands still; a mushroom (type POWERUP) is active, on screen and ahead (checked only that, like E1's scene). Non-powerup enemies cleared
  each frame (`clear_enemies`). Landmark OFF (so the only drive to the right is pursuit by sight), pursuit on with the default kinds,
  looming on. **Reached** = first frame Mario's box overlaps the mushroom's (|dx| < 16 and vertical centre gap < (16 + Mario height) / 2),
  or Mario's size changes (collecting it implies an overlap), within E3_MAX_FRAMES (**150**, not 600: found by running the scene with
  NO fly at all, a Mario who presses nothing, the mushroom walks right, turns at the pipe and reaches him at frame 183, so a longer bound
  would let standing still pass; the bound is a property of the scene and was fixed before any fly ran it; `tests/test_phase3.py` checks
  a passive Mario fails both E0 and E3). Also reported: frames to reach, whether Mario's size changed (collected), deaths, GF crossed. Plan
  criterion: real >= 14/20, shuffled not. The scene log is written once and checked only for what it promises; never edited against
  the fly's behaviour. Pursuit-off is not an arm (not asked); an E3 pass therefore does not by itself show pursuit is necessary.
* **E1** unchanged in definition (landmark off, pursuit off); it reruns on the new network hash, so its numbers are not comparable with
  Phase 2's without the experimenter's rerun.

Finding while building the E3 scene: SMB keeps the power-up in enemy-object slot 5 (type 0x2E), but `mario.ram.addresses.N_ENEMY_SLOTS`
is 5, so the legacy perception never sees a mushroom. The new code reads slots 0-5 (`brain/perception.OBJECT_SLOTS`); the frozen constant
is untouched.

## 7. Synthetic tests before any game scene (`tests/test_phase3.py`)

* Disc with landmark ON (and, worst case, pursuit ON with the Goomba set as a pursued kind): GF fires at 38-48 deg for l/v 10-80, spread
  <= 8; the shuffles' behaviour printed.
* Rest, mechanisms attached, no cue, 5 seeds x 3000 frames: 0 GF spikes and 0 presses of any button. After a 100-frame cue is removed,
  no press after 40 frames (nothing latches).
* Landmark alone: right/B pressed, no Left (real). Pursuit dot: Right for a right dot, Left for a left dot, nothing for a static one.
* Guard tests: only `Brain.apply` writes current; new mechanisms name only LC10a; a non-sensory id is refused; no `Brain` public
  method added; pursuit reads `pursuit_kinds` per object; arousal reads the readout only; class shuffle preserves tier groups, degrees
  and signs; scalars doc current; E0 and E3 metrics on made-up numbers; scenes deterministic; Results/Mechanisms tab tests.
* Full root `tests/` once at the end in chunks (goldens byte-identical); affected `tool/tests` files only.

## 8. Doc corrections

"Shuffled walks Left under noise" is wrong: the shuffled arm's Left is looming-driven (LPLC2 reaches MDN through random wiring; with no
stimulus it presses Left 0 times, docs/INVESTIGATION_phase3.md rows 10-12). Corrected in `docs/SPEC_tool_phase2.md`,
`docs/NOTE_e1_shuffled_contact_spread.md`, `docs/RESULTS_redesign_phase2.md`, `brain/e1.py`, `brain/scalars.py`. `docs/RUNS.md` is
append-only and is not edited.

## 9. Results of the build (implementer; the experimenter judges)

**Calibration, run once** (`python -m brain.calibrate`, network `3848f3e70b2051ef`: 16,464 neurons, 637,176 built edges, 612,566 non-zero weights;
calibration file hash `9cf9317984a0b28c`; g 0.85; thresholds walk 0.01688, steer 0.01098, back
0.01400 Hz, GF 0.16736). Disc gate: real GF fires at 47.2 / 47.2 / 47.2 / 40.6 deg for l/v 10 / 20 / 40 / 80 (spread 6.6); the 5 shuffles
never fire. Rest gate: 0 GF spikes, real max/threshold 0.82-0.83. PASS, no re-tuning.

**Values from the rules of section 3** (`docs/senses_calibration_output.txt`, one run, seeds 9400-9404): R window 3..25, L window 3..25, C window
all, B window 5..25. Goal window (R and B) 5..25, so GOAL_CUE_SALIENCE = 15. Pursuit window 3..25 with a_lo = 0.379, so the gain interval
is [7.9, 25] and LC10A_GAIN = 16. Every azimuth split candidate passed at both arousal bounds; the largest is LC10A_AZIMUTH_SPLIT = 90.
Reported only: on 5 degree-preserving shuffles the cue gives Left on 100 % of frames and a GF crossing on 87-100 % in 4 of 5; on the 5
class-preserving shuffles the cue gives Left 100 % and no GF crossing.

**Synthetic checks** (tests): disc with the landmark ON 47.2 / 47.2 / 47.2 / 40.6 deg; worst case pursuit at full arousal dead ahead
47.2 / 47.2 / 47.2 / 43.6 deg; both 47.2 / 47.2 / 47.2 / 40.6 (all inside 38-48, spread <= 8). Rest with the mechanisms attached, 3 seeds
x 2000 frames: 0 GF spikes, 0 presses of any button; after a 100-frame cue (landmark plus a left dot) is removed, no walking or steering
press from 40 frames on. Shuffle 1 with the landmark fires its GF at about 2 deg (a property of the degree-preserving control, not of the fly).

**Smoke, seed 9100 only** (not a result): E0 real reached at frame 135, shuffled and class-shuffled timed out (Left 600 frames; the degree
shuffle's GF crossed). E3 real reached at frame 101, both shuffled arms timed out. Held-out seeds are not run.

## 10. Review annotations (2026-10-04)

E1 caveat (stated plainly): the Phase 2 result 18/20 belongs to the Phase 2 network (`brain_k3_N5.npz`, hash `4736dc554136ac98`). On the Phase 3 network
(`3848f3e70b2051ef`, LC10a added) the same E1 regression gives real 13/20 (the criterion >= 16 FAILS), shuffled 0/20, lesion 0/20, on the previously used
seeds 3000-3019, so it is not a fresh held-out result. The GF still fires before contact in 20/20; deaths held A for 4-9 frames against 11-20 for survivors.
The cause was not diagnosed (a correlation only).

Footnotes. (a) E0 real is one deterministic trajectory (it reaches at frame 135 on all 20 seeds), so its Wilson interval overstates independence.
(b) LC10A_AZIMUTH_SPLIT = 90 was a non-discriminating pick: every candidate passed, so the rule chose the largest by default.
(c) E3 has no pursuit-off arm: a pass shows the wiring turns this cue into walking, not that pursuit is necessary. E0 has the landmark on, so "go right" is an input.
(d) OBSOLETE (section 11A; history kept): arousal was 0 on the first frame (`last_readout` was None), so the first frame had no pursuit drive. Arousal is now a tool setting, constant over an episode, so the first frame has the full pursuit drive.
(e) Provenance of the section 3 rules: in the implementer's session the SPEC was written before the calibration runs, but the artefacts cannot show it:
`brain/calibration.py` has mtime 12:50:00.298 against 12:50:00.481 for `docs/senses_calibration_output.txt`, and the SPEC was last modified at 13:01 (it was edited
after the runs to add section 9). No earlier copy of the SPEC exists. The ordering is therefore unverifiable from artefacts; what can be checked is that the
chosen values match the section 3 rules applied to the windows printed in `docs/senses_calibration_output.txt`.

## 11. Decisions round 2 (2026-10-04): arousal becomes a tool setting; necessity arms; docs

**A. Arousal is a fly-state input set in the tool, not read from the fly.** The section 4 rule "a = DNp09 of the previous frame / walk
threshold" is REMOVED: it fed the fly's own output back into its own sensory gain (an invented feedback loop). Nothing reads DNp09 for
any gain anywhere; `mechanisms.arousal()` and `policy.last_readout`-based arousal are deleted. Section 4's paragraph and footnote (d) are
kept below as history and marked OBSOLETE. New rule: pursuit drive per side = LC10A_GAIN * PURSUIT_AROUSAL * salience * share(azimuth),
where `PURSUIT_AROUSAL` is a `SenseSettings.pursuit_arousal` value in [0, 1] (Mechanisms tab, saved in `brain_settings.json`), labelled in
the tool as a fly-state input (how aroused the fly is), constant over an episode. It is an invented scalar (`PURSUIT_AROUSAL` in
`brain/scalars.py`). First frame: it has the same value as every other frame, so the first frame has the full pursuit drive (the
one-frame hole of footnote (d) no longer exists).

**Rule for the default (written before the run; synthetic stimuli only; `brain/senses_calibrate.py --arousal`).** Grid a = 0.1, 0.2, ...,
1.0. LC10A_GAIN (16) and LC10A_AZIMUTH_SPLIT (90) are frozen. For each a, the real brain, noise seeds 9400-9404, hold 50 frames, measure
frames 20-49, drive per side = 16 * a * share(az): the dot at az +45 must pass the R test, az -45 the L test, az 0 the C test (section 3
definitions, no GF crossing in any), and a STATIC dot (no drive: nothing to track) must give no button above 5 % and no GF crossing.
Window = the contiguous run of passing grid values starting at the smallest passing one. **Default = the arithmetic midpoint of the
window, rounded to 2 significant figures.** If the window is empty the build stops and reports. Reported only: the same sweep on 5
degree-preserving shuffles; and, with the default fixed, the synthetic looming disc with pursuit (arousal at the default, and at 1.0)
and the landmark on (GF must still fire at 38-48 deg, spread <= 8) and rest with the mechanisms attached (nothing latches).

**B. Necessity arms (controls, eval only).** `real_no_landmark` (E0: the real connectome with the landmark off) and `real_no_pursuit`
(E3: the real connectome with pursuit off). Real connectome, same noise seeds, `settings` with the mechanism removed; no shuffle seed.
Shown in the Results tab labelled "(control)" like the GF-lesion arm; not selectable in Run / play. E3 is re-run by the experimenter on
fresh seeds 5100-5119 (all arms: real, shuffled, shuffled_class, real_no_pursuit); E0 stays on 4000-4019 with `real_no_landmark`
added. Reading: if real_no_landmark reaches the goal in E0, or real_no_pursuit reaches the mushroom in E3, that mechanism is not what
did the work.

**C. Documentation.** E0 real 20/20 is ONE deterministic trajectory (the scene has no Goomba and the fly's noise does not change the
route: it reaches on the same frame on every seed), not 20 independent successes. LC10A_AZIMUTH_SPLIT = 90 is the left/right eye boundary
and was NOT selected by the data (every candidate passed; the rule picked the largest). All E0 / E3 scene constants (E0_GOAL_X,
E0_MAX_FRAMES, E3_MAX_FRAMES, the scene log) stay registered as invented.

**D. Unchanged.** Motor map, thresholds, `brain/calibration.json` (no `brain.calibrate` rerun).

**Results of 11A (one run, `docs/senses_arousal_output.txt`, seeds 9400-9404).** Window of the grid: a = 0.3 .. 1.0 (0.1 and 0.2 fail the R and L
tests: too little drive; the C and static tests pass everywhere). **PURSUIT_AROUSAL = 0.65** (midpoint of 0.3 and 1.0), registered invented. Reported
only: on 5 degree-preserving shuffles (2 seeds, a = 0.5 and 1.0) R, L and C all fail and the static dot passes. Synthetic looming disc with pursuit
(dead ahead) and the landmark both on: GF fires at 47.2 / 47.2 / 47.2 / 40.6 deg for l/v 10 / 20 / 40 / 80, at arousal 0.65 and at 1.0 (spread 6.6).
Rest with the mechanisms attached: 0 GF spikes, 0 presses; nothing latches after a cue (tests/test_phase3.py, passing). Seed 9100 smoke (not a
result): E0 real reached at 135, real_no_landmark timed out with no key pressed; E3 real reached at 105, real_no_pursuit timed out with no key pressed.
LC10A_GAIN, LC10A_AZIMUTH_SPLIT, GOAL_CUE_SALIENCE, all E0 / E3 constants, `brain/calibration.json` and the motor map are unchanged.

**Provenance of the 0.65 rule (reviewer note).** The rule-before-run ordering is unverifiable from artefacts (mtimes: `brain/calibration.py` 13:50:31, `docs/senses_arousal_output.txt` 13:50:41, SPEC 13:55:17); what can be checked is that 0.65 equals the midpoint of the stated 0.3-1.0 window.

## 12. Many-seed calibration (option C of docs/NOTE_e1_regression.md; decided by Arun 2026-10-04)

Why: `a_threshold` was derived from ONE noise seed per disc, and that seed's weakest-disc peak sat 7 % below the 30-seed mean, which
moved the threshold onto the first TTMn upstroke (NOTE_e1_regression.md). Rule, written before the re-run: **every derived value that
came from a single noise seed is derived from K = `CALIBRATION_NOISE_SEEDS` = 30 noise seeds, 7000-7029, on the same synthetic stimuli,
by the same rule as before**. K is a new invented scalar (`brain/calibration.py`, registered in `brain/scalars.py`). Seeds 7000-7029 are
used by nothing else. Nothing is chosen from game outcomes; A_FRACTION, REST_Z, THETA_GF_DEG, MUSCLE_DECAY and the motor map are unchanged.

| value | before | after (many-seed form) |
|---|---|---|
| `g` | deterministic: min(G_NOMINAL, STABILITY_MARGIN / rho(W)) | unchanged (no noise) |
| `gf_threshold` | mean over the 3 discs (l/v 20/40/80) of the GF membrane at 40 deg, noise seed 0 | the same mean over the 3 discs AND the 30 seeds (spiking disabled) |
| `walk` / `steer` / `back` thresholds | rest mean + REST_Z * std of the pooled signal, rest runs of 2000 frames (first 500 skipped) at seeds 0 and 1 | the same pooled mean + REST_Z * pooled std over the 30 rest runs (seeds 7000-7029; 30 x 1500 frames) |
| `a_threshold` | A_FRACTION * min over discs of the peak muscle drive, seed 0 | A_FRACTION * min over discs of the MEAN over 30 seeds of the peak muscle drive |
| `muscle_decay`, rho | constants / deterministic | unchanged |
| `derivation` record | single-seed numbers | per-seed mean (and std where relevant) of the same quantities |

Not derived from noise: `LC10A_GAIN`, `LC10A_AZIMUTH_SPLIT`, `PURSUIT_AROUSAL` (synthetic dot sweeps with fixed grids, section 3 / 11; kept;
the checks in tests/test_phase3.py re-run against the new calibration). `report()` (disc / rest printout) stays on seed 0: it reports, it derives nothing.
The old file is kept as `brain/calibration_v1_singleseed.json`. Network unchanged (3848f3e70b2051ef).

Validation (synthetic only; any failure stops the work, nothing adjusted): disc gate (real GF 38-48 deg at l/v 10/20/40/80, spread <= 8, the
5 degree shuffles never fire), rest gate (0 GF spikes, motor below thresholds; max/threshold real vs shuffles reported), the pursuit/landmark
synthetic tests of `tests/test_phase3.py`, and the brain-only tap fraction of NOTE_e1_regression.md (200 noise seeds, E1 approach theta, share with a
first A run <= 2 frames) before / after.

## 13. Criteria wording (decided 2026-10-04)

The **degree-preserving shuffle is the pass/fail null**: for the survival / reach criteria it must reach <= 2/20. The **class-preserving
shuffle is an informative arm** answering "does type-level wiring suffice?"; it has NO pass/fail. E3 stays accepted with class-shuffle 3/20 reported as
is. Plain statement: E1 shows that type-level wiring matters, not neuron-level wiring (the class-shuffled arm survives about as often as
the real one). Earlier sections (5, 6, 9, 11) that call the class shuffle a null are superseded by this section; their text is not rewritten.

**Result of section 12 (one run, `python -m brain.calibrate`, calibration file hash 343d8f60abcdba25; old file kept as `brain/calibration_v1_singleseed.json`).**
| value | single seed (old) | 30 seeds 7000-7029 (new) |
|---|---|---|
| g | 0.85 | 0.85 |
| gf_threshold | 0.16736 | 0.16965 |
| a_threshold | 0.12359 | 0.13230 (mean peaks 0.324 / 0.310 / 0.265 at l/v 20 / 40 / 80) |
| walk / steer / back | 0.016884 / 0.010984 / 0.014003 | 0.01691 / 0.01092 / 0.01393 |
Gates: real GF 47.2 / 47.2 / 47.2 / 40.6 deg at l/v 10 / 20 / 40 / 80 (spread 6.6); 5 degree shuffles never fire; rest 0 GF spikes, rest max / threshold real
0.83 / 0.83 / 0.82 (walk / back / steer), shuffles 0.88-0.94 / 0.86-0.93 / 0.81-0.86. Brain-only tap fraction (200 noise seeds, E1 approach theta, first A run <= 2
frames): 0.42 before (old calibration), 0.30 after. The synthetic rest / disc / phase 3 pursuit checks pass.

**Disclosures for section 12 (reviewer round 3, appended).**
- Ordering: unverifiable from artefacts; the code (calibrate.py / calibration.py, 16:10) precedes calibration.json (16:40) but this SPEC text was last saved 16:43. Same status as the PURSUIT_AROUSAL note.
- Motivation: E1 12/20 on seeds 3100-3119 prompted the recalibration (those seeds are context only, not validation). The tap fraction is non-monotone in the A threshold (docs/NOTE_e1_regression.md), so the post-change 0.30 is partly luck.
- The 0.30 tap figure comes from the same 200-seed brain-only analysis that motivated the change; it is not independent validation.
