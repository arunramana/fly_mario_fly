# SPEC: shadow mode (human plays, the fly watches)

Written BEFORE any code or play. Status: spec fixed 2026-10-06; no data yet.

## Purpose

The B11 baseline stalls (pipe 2 at x ~596, pipe 3 at x ~724). Two explanations are open: the fly's signals are absent
when a competent player would act (the gap is in the brain), or they are present but the motor rule fails to turn them
into the right button (the gap is in the motor map). Shadow mode separates them without letting the fly act: a human
plays Mario with the keyboard, and the unchanged redesigned brain watches the same game on every frame. Its
would-be buttons are recorded and discarded. **The fly controls nothing.** This is a measurement of the brain's signals
at a human's decision moments, not a test of the fly's play; nothing is tuned on it and no fix follows from this spec.

## The rule, applied here

- Stimuli enter only through `BrainPolicy.act()`, i.e. exactly the B11 path (`SenseSettings.user_default()` passed through
  `settings_for("B11")`: looming + pursuit (powerup) + home landmark + obstacle expansion). No new scalars, no mechanism
  changes, nothing registered in `brain/scalars.py`. The stimulus conventions are the current committed ones.
- `BrainPolicy.act()` runs every frame on the same RAM the human sees (before the step), through the same
  `brain.step_frame()` / `apply` / `MotorMap.read()` path. Its return value is dropped; its `last_buttons` and
  `last_readout` are only written to the CSV. `env.step()` receives the human action and nothing else.
- Thresholds are read from `brain/calibration.json` (a_threshold 0.13229, walk_threshold 0.016908); nothing is exposed as an input.
- There is no "retinotopic" option in the redesigned path (`brain/`); the word appears only in the frozen legacy path
  (`fly/sensing/retinotopy.py`, `bridge/`, `run_steering.py`). It is therefore not used. Everything else is at its default.

## Controls

Arrows = D-pad. **X = A (jump)**, **Z = B (run)**. Esc = quit and save. Enter = Start: the key is read and recorded in the `human_start`
column, but the 64-action space (`mario/actions/actions.py`) has no Start/Select, so it is never sent to the emulator (the game starts
itself on reset). `human_select` and `fly_start/select` are always 0. Replay mode (`--replay actions.npy`) drives the human buttons from a
recorded uint8 array of indices into `MOVES_ALL`, headless, with no viewer.

## Runs

At least one **clean** run to the flagpole and one deliberately **slow, careful** run (`--label slow`), each its own CSV, every row
carrying the run label. A run ends at the flag, a death, Esc, or `--max-frames` (default 30000); the end reason is in the meta JSON.
Seed 9400 (the noise seed; held out from 1000-3000, 6000-6119, 9000-9200).

## Telemetry (one CSV row per frame, flushed every row)

All state columns are read before the step, i.e. what the human and the fly both saw on that frame; `flag_get_after`, `life_after` and
`done_after` come from the step's own info. Columns: `frame, label, mario_x (world), mario_sx, mario_y, mario_size, airborne`,
`human_{right,left,down,up,a,b,start,select}`, `fly_{same}` (would-be, discarded), `theta` (enemy, max of hemispheres, rad), `dtheta`,
`d_px` (surface distance of the nearest enemy), `obst_theta`, `obst_dtheta`, `obst_d_px`, `enemy_x`, `enemy_dx` (nearest on-screen enemy),
`gf_l_hz, gf_r_hz, ttmn_hz (pooled), ttmn_side_max_hz (what the motor map reads), dnp09_hz, dna01_hz, dna02_hz, mdn_hz`,
`gf_mem` (max membrane), `gf_mem_l, gf_mem_r` (last substep), `gf_spike` (any GF spike this frame), `muscle_drive`, `muscle_over`
(drive >= a_threshold), `walk_over` (pooled DNp09 > walk_threshold), `lc10a_l, lc10a_r` (the drive the mechanisms add, recomputed by
the pure `encode` functions; rates are not recorded), `landmark_on`, `goombas_on_screen`, `flag_get_after, life_after, done_after`,
`lc4_hz, lplc2_hz, arousal, pursuit_az, pursuit_dx, ttmn_rest_max`.
Per-hemisphere GF spike flags are not available (`Readout` carries one combined flag); the per-side membrane and rate are.
The human action array is saved as `NNN_label_actions.npy` (uint8 indices) beside the CSV, plus `NNN_label_meta.json` (stamp, settings,
seed, rest range, end reason, key map).

## Pre-registered questions (exactly as asked)

Definitions fixed now. A *frame* is one emulator frame. A *press* is a rising edge of the human A (A held on frame t, not on t-1).
A GF *spike frame* is a frame with `gf_spike` = 1.

**Resting range of TTMn (rule).** A rest run: the same brain, same noise seed (the run's seed), same network, NO stimulus at all (no
looming, no landmark, no pursuit), 3000 frames; discard the first 60 frames (settling from the all-zero state); `ttmn_rest_max` = the
maximum over the remaining frames of the pooled TTMn rate (the same quantity as the `ttmn_hz` column). "TTMn above its resting range" =
`ttmn_hz > ttmn_rest_max`. The rest run is made automatically at the start of every shadow run and stored in the meta JSON and the
`ttmn_rest_max` column.

- **Q1.** Of all frames where the human pressed A (A held), what fraction had the muscle drive >= a_threshold (0.1323, from
  calibration.json), and what fraction had `ttmn_hz > ttmn_rest_max` at all?
- **Q2.** Of all GF spike frames the fly produced, what fraction had a human A press (rising edge) within +-5 frames? (Secondary, reported
  too: A held on any frame within +-5.)
- **Q3.** Of all frames where the human pressed Right, what fraction had pooled DNp09 > walk_threshold (0.0169; calibration.json holds
  0.016908, which is the value used)?
- **Q4.** For each human A press: offset in frames to the nearest GF spike frame (negative = the fly was early, positive = late). Histogram
  (bins of 3 frames within +-30), counts of early / coincident / late, and the fraction with NO spike within +-30 frames ("absent"). Also
  reported per frame: the same offset for every frame with A held.

**The one read (decision criterion, fixed now).** The fly's signals are *present at the human's decision moments* iff ALL of:
(i) Q1 muscle-drive fraction >= 50%, (ii) Q2 >= 50%, (iii) Q4 median |offset| <= 3 frames, where a press with no spike within +-30 frames
counts as infinite |offset| (so (iii) needs more than half of the presses to have a spike within 3 frames).
If present: the gap is in the motor rule. If not present: the gap is in the brain. Then stop; no fixes follow from this spec.
Justification, a priori: 50% is "more often than not"; +-5 frames (83 ms) is the order of a human's press timing jitter and of the 3-frame
muscle decay constant scale; 3 frames (50 ms) is the order of a single frame of GF-to-A latency through the muscle integral (decay 0.9,
~10 frames) rounded to what a motor map could be expected to resolve. None of these is tuned on any data; they are fixed before there is any.
Caveat stated in advance: this is open loop (the fly watches the human's trajectory, not its own), and one human, two runs.

## Segments (pipe / gap stimulus streams)

Human crossings, defined by the first frame with `mario_x >=` the feature's world x: pipe 1 (x 448), pipe 2 (608), pipe 3 (736), first
pit/gap (x 1104, 32 px wide; 1-1's first pit). Window: 90 frames before to 30 after. For each, the analysis records the stimulus the fly
saw (max theta, max obstacle theta, min obstacle distance), the fly's outputs (max GF rate, GF spikes, max muscle drive) and the human's
A presses (rising edges and offsets), plus a trace table (every 6th frame).

## Files

New: `brain/shadow.py` (harness, CLI), `brain/shadow_analysis.py` (Q1-Q4, decision, segments, markdown writer), `tests/test_shadow.py`.
Reused unchanged: `BrainPolicy`, `MotorMap`, `Brain`, `SenseSettings`/`settings_for`, `make_env`, `action_from_buttons`, `nes_py._image_viewer`.
Adapted: nothing (the frozen legacy path is untouched). Validation: static AST checks that only the human action reaches `env.step`, a
headless 300-frame replay run with and without the policy giving bit-identical RAM and screen hashes every frame, column presence, and
the analysis functions on a synthetic CSV with known answers.

## How to play (for Arun)

```
.venv/Scripts/python.exe -m brain.shadow --label clean --out projects/shadow/telemetry/001_clean.csv --seed 9400
.venv/Scripts/python.exe -m brain.shadow --label slow  --out projects/shadow/telemetry/002_slow.csv  --seed 9400
.venv/Scripts/python.exe -m brain.shadow_analysis projects/shadow/telemetry/001_clean.csv projects/shadow/telemetry/002_slow.csv --out docs/RESULTS_shadow.md
```

A window opens and the game runs in real time at 60 fps. Arrows move, X jumps, Z runs, Esc quits (the CSV is already on disk, flushed per frame).
Run 1 "clean": play 1-1 normally to the flagpole as you would. Run 2 "slow": play deliberately slowly and carefully (stop, wait, jump each
obstacle on purpose). Do not try to help or hinder the fly; it cannot affect the game. If you die, the run still counts for the questions
but a clean run needs the flag: repeat.

## Entry template for docs/RUNS.md (to fill after play; do not append before there is data)

```
## NNN — shadow mode, human play vs the fly's signals (`projects/shadow/telemetry/...`)

**Setup.** Human keyboard play of 1-1 (clean: <end reason, frames>; slow: <end reason, frames>), seed 9400, B11 senses, brain
unchanged and discarded (fly controls nothing). Rest range ttmn_rest_max = <value>. Pre-registered in docs/SPEC_shadow.md.
**What happened.** Q1 muscle-drive fraction <x>, TTMn above rest <x>; Q2 <x>; Q3 <x>; Q4 median offset <x> frames, absent <x>;
decision criterion: <present / not present>. Per segment: <pipe 1/2/3, gap>.
**What we learned.** <the gap is in the motor rule / the brain; caveats: open loop, one human>.
```
