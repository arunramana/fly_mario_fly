# 002 fitness: combine A/B, variation, baselines (flyrun, part 3 of 6)

Videos: `002_fly_default.mp4` (seed 0, default knobs: dies at Goomba #1, x 296, see below) and `002b_fly_sigma0.mp4` (noise-free fly, seed 0: stuck at pipe 3, x 722). Raw numbers: `002_test_numbers.json`. Logs: `002_fly_default_log.csv`, `002b_fly_sigma0_log.csv`. Tests: 17/17 pass (6 part 1, 4 part 2, 7 part 3).

## 1. STIM_COMBINE max vs sum (fly only, 10 seeds, default noise)

| combine | mean fitness | mean max_x | min max_x | end (x_at_end) |
|---|---|---|---|---|
| max | 506.1 | 506.1 | 296 | died 296 x6, died 689 x1, stuck 722 x3 |
| sum | 509.3 | 509.3 | 296 | died 296 x5, stuck 722 x5 |

Noise-free (sigma 0, same fly): max reaches 687 (died to a Goomba behind the pipe-3 face, the part 2 death), sum reaches 723 (stuck at pipe 3, x 722). Sum wins on mean fitness in both settings, so the default is `STIM_COMBINE = "sum"`. With noise on the gap is small (509.3 vs 506.1), because both are dominated by the noise-driven early deaths at Goomba #1.

## 2. Episode variation: sigma and noise structure

Sensor noise is multiplicative Gaussian on the LC4 / LPLC2 inputs (zero input stays zero, so silence stays silent), from `default_rng(episode_seed)`; `episode_seed=None` means no noise. Max_x over 10 seeds, sum combine, fly only:

| noise structure | 2% | 5% | 10% | 20% | 30% |
|---|---|---|---|---|---|
| independent per neuron | 723 x10 | 723 x10 | 723 x10 | 723 x10 | 723 x10 |
| one draw per frame, shared by the detector population ("common") | 723 x10 | 723 x10 | 723 x10 | 296 x2, 723 x8 | 296 x5, 722 x2, 723 x3 |

- Per-neuron noise has no effect at any size: 55 LC4 and 91 LPLC2 neurons average their independent jitter away before TTMn reads them.
- Common-mode noise has no effect up to 10% either.
- **The 2%, 5% and 10% steps you named all give a single outcome.** I went past them, in the same steps, because the test needs at least 3 distinct max_x. 20% gives two outcomes; **30% common-mode is the smallest that gives three** (296, 722, 723), so `SENSOR_NOISE = 0.30`, `NOISE_MODE = "common"`. This is the criterion you set (at least 3 distinct), not a distance criterion, but 30% is large and **I want your decision on it**.
- What the 30% buys: half the seeds now die at Goomba #1 (x 296), because a gain jitter delays or skips the TTMn crossing. The variation is real but it is "survives Goomba #1 or not", plus a 1 px split (722 / 723) at pipe 3. It is not variation between obstacles later in the level.
- Same seed twice: identical summary. Different seeds: 3 distinct max_x.
- Flag: with this sigma the default fly (509) loses to the noise-free circuit (723). Any comparison of knob settings under noise partly measures how robust they are to a gain jitter at Goomba #1.

## 3. Baselines (same 10 seeds, same episode rules, stuck_frames 150)

| arm | mean fitness | min | max | where it stops (x_at_end: count) |
|---|---|---|---|---|
| stand (NOOP) | 40.0 | 40 | 40 | stuck 40: 10 |
| always Right | 296.0 | 296 | 296 | died 296: 10 (Goomba #1) |
| Right + random A (p 0.05) | 367.5 | 296 | 594 | died 296: 6, stuck 434: 3 (pipe 1), stuck 594: 1 |
| theta rule (Right, A at combined theta >= 43.6 deg, hold 12 / cooldown 10) | 723.0 | 723 | 723 | stuck 722: 10 (pipe 3) |
| fly, default knobs (sigma 30%) | 509.3 | 296 | 723 | died 296: 5, stuck 722: 5 |
| fly, sigma 0 (context) | 723.0 | 723 | 723 | stuck 722: 10 |

Ranking test: stand (40) < always Right (296) <= fly (509.3): passes.

**The theta rule is equal to the fly.** The no-brain rule gets 723, the same as the noise-free fly in every seed, and both stop at the same place (pipe 3, x 722). The default fly is *lower* (509) only because the fly's detectors get the noise and the rule's theta does not. So on this task, with these knobs, the connectome circuit does nothing a single theta threshold does not already do. (Both use the same hold / cooldown and the same trigger angle, so they have the same decision rule: TTMn crossing 0.10 in the circuit lands at the same 43.6 deg.)

## 4. Why everything stops at pipe 3 (x 722)

Pipe 3 (face x 736) is 64 px high. In the noise-free fly's log, A is pressed repeatedly at x = 722, d = 14, and Mario never gets over: the 12-frame hold probably gives too little jump height for a 4-tile face, and the cooldown makes it a stop-start press pattern. My reading, not tested here, is that it is a motor limit (hold length) and not a sensing one: the stimulus is strongly on (theta 2.6 to 2.9 rad) and A is pressed, yet the jump does not clear. I did not touch A_HOLD (per your rule). This is the first place hold length will matter for evolution.

## 5. Timing (for sizing evolution)

Measured on the 16-thread i7-13620H, no rendering, 10 seeds worth of episodes, spawn-based pool with one emulator per worker.

| workers | episodes / min |
|---|---|
| 1 | 52 |
| 4 | 89 |
| 8 | 142 |
| 12 | 174 |

1.5 s per episode on one worker (mean 490 frames, 3.1 ms per frame, the matvec plus the emulator). These episodes are short because they end at x 296 or 722; an episode that reaches the flag is about 2000 frames, so about 4x longer (6 s). A generation of 20 candidates x 10 seeds = 200 episodes takes about 1.4 min at 8 workers while the fly still dies early, and would take up to 5 min once candidates survive to the flag.

## 6. Level map (`001_level_map.csv`, extended; scripted scroll reached the flag, x 3161, flag_get True)

| kind | x | size | | kind | x | size |
|---|---|---|---|---|---|---|
| pipe 1 | 448 | H 32 | | stairs up (4) | 2368 / 2384 / 2400 / 2416 | H 16 / 32 / 48 / 64 |
| pipe 2 | 608 | H 48 | | **pit 3** | 2448 | W 32 |
| pipe 3 | 736 | H 64 | | stairs down (4) | 2480 / 2496 / 2512 / 2528 | H 64 / 48 / 32 / 16 |
| pipe 4 | 912 | H 48 | | pipe 5 | 2608 | H 32 |
| **pit 1** | 1104 | W 32 | | pipe 6 | 2864 | H 32 |
| **pit 2** | 1376 | W 48 | | final stairs (8) | 2896 ... 3008 | H 16, 32, 48, ... 128 |
| stairs up (4) | 2144 / 2160 / 2176 / 2192 | H 16 / 32 / 48 / 64 | | flagpole base | 3168 | H 16 |
| stairs down (4) | 2240 / 2256 / 2272 / 2288 | H 64 / 48 / 32 / 16 | | | | |

31 wall faces, 3 pits. Tile 97 confirmed: at the first stairs the buffer holds 97 on exactly the stair cells (row 10 at x 2144 to 2192, one more row per step). Note for later: the fly's `obstacles_ahead` merges adjacent wall columns into one face, so a staircase appears to the fly as a single face at its first step; the scripted driver uses raw columns. That is a gap for the stairs, not addressed here.

## Choices that were made here, for you to overrule

1. `SENSOR_NOISE = 0.30`, common-mode (see section 2).
2. `STIM_COMBINE = "sum"` (wins the A/B in both noise settings, by 3.2 and by 36).
3. `episode_seed=None` disables noise, so parts 1-2 tests and the scripted level scan are noise-free.
