# 005 controls: shuffled wiring, pit-cue ablation, video assets (flyrun, part 5)

Same guard, TRAIN/HOLDOUT sets and fitness as part 4b. Numbers: `005_controls.json` (HOLDOUT, looming check), `005_extra.json` (assisted loom test, silence check). Evolution logs: `evo5/fly_shuf/{gen.csv, all_evals.csv, best_genome.json}`. Clips: `clips/`, with `clips/numbers.md`. Nothing committed.

**Short answer.** The real wiring does what the shuffle does not: with the default knobs it walks right and jumps at Goomba #1 at theta 43.6 deg; the shuffle walks left into the wall and never presses A. The shuffle can be partly rescued by evolution (it learns to walk and to jump at Goomba #1 with TTMn threshold cut to a third), but its best-fitness genome plateaus at x 1262 on HOLDOUT (the only shuffle individual that got further was an A-spamming timer, x 2469), against 2487 for the real fly at its 4b genome, and 2469 for a blind timer. One shuffle (seed 0) is one sample, not a distribution.

## 1. The shuffle

`W_shuf` (`shuffle.py`, saved to `tutorials/_cache/W_steer_shuf0.npy`): double edge swap, 464,066 accepted swaps over 29,961 edges, seed 0. W[i, j] is the weight j to i, so a swap exchanges two edges' targets and each edge keeps its source neuron and its weight. Every neuron keeps its in-degree, out-degree and its outgoing weights (so the sign, which is constant per source neuron in W_steer, too). No self loops, no duplicate edges. 73 edges still sit where they were. Tests (`tests/test_part5.py`): degrees and signs match exactly, W_shuf differs from W, and the shuffle is reproducible from the seed. All 20 flyrun tests pass.

The masks (which neurons are LC4, TTMn, ...) are the same; only the wiring differs. The input still goes to the same LC4_R / LPLC2_R / LC10a_R neurons.

### HOLDOUT, real vs shuffled matrix (10 episodes: 5 at sigma 0, 5 at 0.05)

| genome | matrix | flag | mean / min max_x | A_frac | blind presses (of onsets) | where it ends |
|---|---|---|---|---|---|---|
| default knobs | real | 0 | 723 / 723 | 0.30 | 2.1 (of 16) | stuck at pipe 3, 10 of 10 |
| default knobs | **shuffle** | 0 | **40 / 40** | 0.00 | 0 (of 0) | never walks right (see below) |
| part 4 hopper | real | 0.5 | 2173 / 1127 | 0.73 | 25.9 (of 61.9) | flag 5 of 5 at sigma 0, dead by x 1220 at sigma 0.05 |
| part 4 hopper | **shuffle** | 0 | **298 / 298** | 0.00 | 0 (of 0) | Goomba #1, 10 of 10 |
| part 4b fly | real | 0 | 2487 / 1421 | 0.71 | 19.0 (of 38.9) | Goomba x 2754 (8), pit 2 (2) |
| part 4b fly | **shuffle** | 0 | **298 / 298** | 0.00 | 0 (of 0) | Goomba #1, 10 of 10 |
| evolved on shuffle (2 restarts) | **shuffle** | 0 | **1262 / 1222** | 0.48 | 6.5 (of 16.9) | Goomba at x 1266 (9), Goomba at x 1222 (1) |
| evolved on shuffle | real (cross-check) | 0 | 298 / 298 | 0.55 | 4.0 (of 4) | Goomba #1, 10 of 10 |

The two real-wiring genomes that were evolved on the real matrix do nothing useful on the shuffle: A_frac is 0.00 and they die to Goomba #1 standing at x 298. The shuffle-evolved genome does not transfer back either (298 on the real matrix).

Evolution on the shuffle: 2 restarts, defaults then fresh (same fresh vector as 4b, CMA seeds 1 and 2), 28 generations each (patience stop), 541 s wall-clock. Best: restart 2 (fresh), TRAIN fitness 1065 (mean max_x 1398, 6.7 blind presses, 0 flags): G 0.913, TTMN_THRESH 0.036, A_HOLD 25, COOLDOWN 14, HOME_R 0.827, PIT_GAIN 2.38. Restart 1 ended at 1063 (mean max_x 1413). On the real matrix 4b gave 4844 to 4878 per restart, with a flag in 1 of 3 TRAIN episodes. Neither shuffle restart ever flagged (0 of 672 evaluations). One evaluated individual (restart 1, generation 1: G 1.13, TTMN_THRESH 0.072, hold 17, cooldown 2, HOME_R 0.14) reached x 2469 on all 3 TRAIN episodes, the same wall as the blind timer, but with A held 89% of frames and 41 blind presses per episode, so it is a timer in a fly costume and its penalised fitness is only 419; the other 671 evaluations stayed below x 1950 (mean). So the shuffle can reach the timer plateau by spamming A, but not by sensing.

### Does the shuffle still produce a looming escape?

Default knobs, sigma 0, closed loop (`controls.looming_check`) and an assisted test (`controls_extra.py`: the scripted driver, diagnostic only, never inside fitness, walks Mario to x 250 and the circuit takes over, so that the Goomba is met even if the circuit does not walk):

| | real | shuffle |
|---|---|---|
| closed loop, 400 frames | R 319, R+A 81 frames; x 40 to 612 | **L 151 frames, x 40 to 0**; no A; DNp09 mean 0.10 |
| first A at Goomba #1 | frame 155, x 289, d 20 px, **theta 43.6 deg**, TTMn 0.101 | **none** (Mario is killed by the Goomba at x 296, theta had reached 77 deg) |
| peak TTMn, assisted run | 0.548 (threshold 0.10) | **0.005** |
| peak LC4_R / LPLC2_R pop. mean | 2.11 / 8.05 | 0.57 / 1.84 |

So with the same stimulus into the same detector neurons, the shuffle's detector response is about 4 times weaker and its TTMn response 100 times weaker, and with the default thresholds it does not jump. In the closed loop it does not even walk right: the steering difference of DNa_R and DNa_L is negative, so it walks left. The real circuit's first A is at theta 43.6 deg, the value the theta rule was built on in part 3.

With the 4b-evolved shuffle genome the shuffle does jump at Goomba #1 (assisted test: first A at frame 149, x 278, d 33 px, theta 27.3 deg, TTMn peak 0.113), but only because evolution lowered the TTMn threshold to 0.036, a third of the default, and raised G to 0.91 and HOME_R to 0.83. Silence check (nothing sensed, 600 frames): A_frac 0, TTMn max 0.027, so it is stimulus-driven, not a free-running timer. It jumps earlier and at a smaller theta than the real circuit does, and it lands on the Goomba cluster: HOLDOUT max_x 1262, below the evolved timer (2469).

## 2. Pit-cue ablation (4b fly genome, PIT_GAIN set from 2.50 to 0, HOLDOUT, one run of 10 episodes)

| | max_x per episode | pit 3 crossed (max_x > 2480) | ends |
|---|---|---|---|
| 4b fly, PIT_GAIN 2.50 | 2754 x 8, 1421 x 2 | 8 of 10 | Goomba x 2754 (8), pit 2 (2) |
| 4b fly, **PIT_GAIN 0** | 1139 x 8, 1137 x 2 | **0 of 10** | **pit 1 (x 1139), 10 of 10** |

Without the pit cue the fly does not reach pit 3: it falls into pit 1 every time, mean max_x 1139 (A_frac 0.54, 7.0 blind presses of 12.8), below the evolved timer (2469) and level with the fixed timer (1138). So the fly's gain over the timer is the pit cue, in the sense that zeroing it removes the whole advantage. Two limits: the other five knobs were evolved with the pit cue present, so this shows the cue is necessary for this genome, not that the other knobs are optimal without it; and the pit loom is an invented stimulus (a looming angle built from the pit width and PIT_GAIN, fed to the same LC4 / LPLC2 neurons), so "the pit cue" is the experimenter's cue passing through the circuit, not something the connectome detects.

## 3. What the real wiring does that the shuffle doesn't (or doesn't)

At the default knobs, the real wiring does three things the degree-matched shuffle does not: it amplifies the looming input in the detector populations (LPLC2_R peaks at 8.05 against 1.84 for the same stimulus), it turns that into a TTMn response that crosses the threshold at theta 43.6 deg at Goomba #1 (0.548 against 0.005), and its walk and steer outputs walk Mario to the right (the shuffle walks left). Those three are the "fine wiring matters" result, for this circuit at these defaults, and the degree sequence plus sign pattern is not enough to reproduce them; Part 4 and 4b already showed the real circuit and a threshold rule coincide at the defaults, so what the real wiring buys here is a working front end, not a better trigger. What it does not show: (a) evolution closes part of the gap (the shuffle learns to walk and to jump at Goomba #1 by cutting TTMN_THRESH to 0.036 and raising G), so the rewiring is partly compensated by the global knobs; (b) the shuffle's best-fitness genome stops at x 1262, where the real fly reaches 2487 at the 4b genome and a blind timer reaches 2469, but this one shuffle (seed 0), with 2 restarts of CMA-ES, does not tell whether the stop is the escape circuit, the walk and steer circuit, or the evolution budget, because W_steer contains all three and I rewired all of them together; (c) nothing here separates "the real wiring is selective" from "the real wiring is a better hopper": the 4b real fly presses A blind 49% of the time, which is no better than a timer, and its advantage on the course is the pit cue (section 2). One caveat on timing: the fly's behaviour at the defaults is the part 3 result (stuck at pipe 3), so the real default wiring clears Goomba #1 and then stops, the same as the threshold rule.

## 4. Clips (`clips/`)

| clip | what | numbers |
|---|---|---|
| `01_goomba_jump.mp4` | default knobs, sigma 0, Goomba #1, brain panel (soma x-z, MaleCNS somaLocation, brightness min(1, h/0.5)) + readout of frame, x, stimulus, d, theta, TTMn, A | first A frame 155, x 289, d 20, theta 43.6 deg |
| `02_pipe3_stuck.mp4` | the same run from x 560 to the stuck end | stuck at x 722, wall H64 @736 |
| `03_theta_rule_vs_fly.mp4` | side by side, same HOLDOUT episode (noop_start 3, seed 101, sigma 0): theta rule (4b) vs fly (4b) | theta rule 2010 (2 blind of 22), fly 2754 (21 blind of 44) |
| `04_evolution_montage.mp4` | copy of `evo4/fly/montage.mp4`, labelled "gen N / max_x / death cause" | per `004_report_numbers.json` |
| `05_flag_run.mp4` | the part 4 hopper, same episode, banner "EVOLVED / deterministic / fails under 5% noise" | flag at x 3161, 2124 frames, 38 blind of 92; 0 of 5 flags at sigma 0.05 |
| `06_shuffle.mp4` | the shuffled brain's best HOLDOUT run (max_x over all 40 shuffle episodes; the shuffle-evolved genome, noop_start 11, seed 102, sigma 0.05) | x 1267, dies to a Goomba |

Every number drawn on screen is a row of the clip's per-frame log in `clips/data/`; the headline numbers and their files are in `clips/numbers.md`. Clip 05's banner says "fails under 5% noise": 5 of 5 HOLDOUT episodes reach the flag at sigma 0 and 0 of 5 at sigma 0.05 (`004_robust.md`). The panel brightness scale is the same in every clip, so clip 06 (shuffle) is dimmer than clip 01 for the reason in section 1: the activity is smaller. In clip 03 the theta rule has no brain, so it has no panel.

## Changes made this part

`shuffle.py`, `evolve5.py`, `controls.py`, `controls_extra.py`, `make_clips.py` (new); `brain.py` (the environment variable `FLYRUN_WFILE` selects a different W file, default unchanged); `run.py` (`record_h=True` also returns h per frame, default off); `evolve4.run_arm` (optional output dir and starts, default unchanged); `tests/test_part5.py`. Full flyrun suite: 20 passed. The shuffle was run on HOLDOUT only; the shuffled matrix was never evaluated on TRAIN apart from its own evolution.
