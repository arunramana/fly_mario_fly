# SPEC: learning v2 -- seeds per episode, checkpoints in Play/Batch, MBON readout strength, power-up reward, "?" block cue

**Status: decisions made before implementation (below); every new feature is off by default, so all
goldens stay byte-identical.** Rule for the whole sprint (CLAUDE.md invariant 8): perception and
reward are allowed, hand-coded control is not. Nothing here decides or forces an action.

## 1. Seeds per episode + held-out test set (`tool/`, no change outside)

Today every training episode reuses one seed, so the network can memorise one noise sequence and
there is no measure of generalisation.

- `TrainingSettings.seed_mode`: `"fixed"` (default, today's behaviour: every episode uses the base
  seed) or `"vary"` (episode `i` uses `seed_base + i`; `i` is the network's own episode counter, so a
  resumed checkpoint continues the sequence). `seed_base` `None` = the Goal tab's first seed.
- `TrainingSettings.test_every` (0 = never, default) and `test_seeds` (default 100..109). Every
  `test_every` episodes the current weights are evaluated on each test seed with **frozen weights**:
  the episode runs on a copy of the matrix with the learning rate forced to 0, so nothing (reward or
  punishment) changes it and nothing carries over. Held-out means the test seeds are never used for
  training (`vary` skips any seed in the test set).
- **Win** = the run reached the flag (`flag_get`). Also recorded: mean `max_x` over the test seeds.
  Test episodes are not written to the run store (10 episodes every N would drown the player); the
  result of each evaluation is appended to `projects/<name>/training_eval.json`
  (`{network, episode, seeds, wins, win_rate, mean_max_x, max_x: [...]}`).
- Learning tab: top plot is per-episode training `max_x` or `score` (selector; `score` is now stored
  on each training entry), bottom plot is test win-rate (with mean test `max_x`) against episode.

## 2. Checkpoint for Play / Batch (`tool/`)

- `ExperimentSettings.brain_weights`: `None` = fresh connectome weights (default, today), or a file
  name under `projects/<name>/checkpoints/`. `keep_learning` (default off).
- `runner.run_one` loads the file and passes it as `mb_weights`. **Without `keep_learning` the
  weights are frozen**: the run's learning rate is forced to 0 for the episode (otherwise the
  in-episode progress reward would keep depressing a checkpoint that is then thrown away, and a
  "checkpoint run" would not be a run *of that checkpoint*). With `keep_learning` the project's rate
  applies and, for a single Play, the updated matrix is saved as `play_<run number>.npy` in the same
  folder (never overwriting a training checkpoint) and recorded as `info["saved_checkpoint"]`.
- Batch: every seed starts from the same checkpoint (runs stay independent and parallel). With
  `keep_learning` each run learns inside its episode but nothing is chained or saved: chaining seeds
  would make batch results depend on order and break the worker pool.
- Recorded in the run spec (`tool_settings.experiment`) and in `info["brain_weights"]`; the Run tab's
  Config panel shows a `[brain weights]` block above the config diff.
- `list_checkpoints` lists `real_epNNN.npy` and `play_NNN.npy`; training "Start from" accepts both
  (a `play_` file resumes at episode 0).

## 3. MBON readout strength (`config/params.py` range; `tool/`)

`MbonReadoutParams.{dnp01,dlmn,dnp09,mdn}_frac` are current per unit of the connectome-weighted MBON
activity, negative sign. They were already editable as module parameters (range 0-0.1); the range
becomes **0-0.2** in `config/params.py` (so the ParamForm/`SCALARS.md` range column agrees) and in
the Circuits -> Mushroom body module editor. The defaults (0.005) are unchanged. A one-seed sweep
(`scripts/sweep_mbon_frac.py`) reports at which value the readout changes behaviour measurably; the
result is recorded in `docs/RUNS.md`. "Measurably" = telemetry diverges from `frac = 0` (first
divergent frame) **and** a behaviour summary changes (jumps or `max_x`).

## 4. Power-up reward (outside `tool/`: dopamine, FullPolicy, run_steering; default off)

- Event: Mario becomes Super = RAM `0x0756` (`ADDR_MARIO_SIZE`) rises from 0 to >= 1 (the check
  `FullPolicy.act` already makes for its debug log). The first frame's value is the baseline, so
  starting big (`starting_powerup`) is not an event; a RAM poke that forces size after frame 0 would
  be, and is not used together with this reward.
- `event_dopamine(..., powerup=False)` routes it to PAM (appetitive) with the same one-shot
  magnitude `dynamics.CLIP` as a `?` hit or stomp -- **no new scalar**, and coinciding events do not
  add. Only when `powerup_reward=True` is passed (mode flag like `event_proximal_dopamine`) and only
  in event-proximal mode, the mode that uses events.
- `FitnessSettings.powerup` (Goal tab, default 0.0): the weight of an after-the-fact `n_powerups`
  term in fitness (`sim.fitness`), and **> 0 is what switches the dopamine event on**. The weight's
  value does not scale the dopamine (the pulse is a fixed `CLIP`, invariant 3), and fitness is never
  read by anything that chooses an action (`fly/plasticity/dopamine.py` docstring). `info["n_powerups"]`
  is always reported; it is not a telemetry column.
- **Sign test** (`tests/test_powerup_reward.py`): the rule is depression-only, so reward and
  punishment differ by *which MBONs* they depress (PAM vs PPL/PPM reach), not by sign. With the same
  eligibility, a power-up pulse must depress PAM-dominated MBONs more than punishment does and
  PPL-dominated MBONs less; the difference (reward effect minus punishment effect) must have opposite
  signs on the two groups. Numbers go in `docs/RUNS.md`.

## 5. "?" block cue (`QBlockAheadPerceptionModule`, off by default)

- PERCEPTION only. Reads unhit `?` blocks (coin or power-up tile, `tile_ram`; a hit block reads as
  used and disappears from the list) at or ahead of Mario within `perceive_tiles`, nearest first, as
  **distance** (tiles) and **height** (tiles above the ground row).
- Feeds two extra Kenyon-cell inputs, like `mb_spatial_inputs` (`N_INPUTS = 2`, appended in module
  order; each present module grows `n_mb_sensory` by its own `N_INPUTS`, so `mb_spatial_inputs` alone
  is bit-identical to before): closeness `(n - d) / n` and height `/ GROUND_ROW`, both 0..1, both 0
  when no block is in range.
- Optional weak looming route (`looming_gain`, default 0 = off): the block as an expanding object,
  `theta = 2*arctan(16 px / (2*d_px))` added to the right LC4/LPLC2 drive like the wall. **Not** a jump
  command: the circuit's own thresholds decide. The existing `question_block_odor` (food odour into
  steering) is untouched.
- Entity/Objects tab profile: `KindProfile.cue_weight` (default 1.0, only meaningful for
  `QUESTION_BLOCK`) scales both routes when entity profiles are enabled; the Objects tab's
  Question Block card gets a "Cue weight" field. Absent profiles = weight 1.
- Two scalars flagged and counted (`QBlockAheadParams`: `perceive_tiles`, `looming_gain`), both
  invented; `docs/SCALARS.md` regenerated.

## Out of scope
Chained batch learning, saving checkpoints from batch runs, a learned (non-depressive) valence rule,
recording every test episode as a video/run.

## Results (2026-09-29)
Sweep and sign-test numbers are in `docs/RUNS.md` (`learning-v2-001`). Short version: readout strength
0.005-0.02 changes internal state only; Mario's position first differs at 0.05; a trained brain differs
from a fresh one only at 0.2 (top of the range). Power-up pulse vs death pulse depress opposite MBON
groups (23x and 15x ratios).
