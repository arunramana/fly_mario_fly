# clips/numbers.md

Every number drawn on screen, with its source. Per-frame values (frame, x, stim source, d, theta, TTMn, A)
are rows of the run's per-frame log in `clips/data/`; the clip is those rows rendered. Soma brightness = min(1, h/0.5).
Headline numbers below are those quoted in titles/banners or used to choose the clip.

## clip 01  (source: clips/data/default_knobs_log.csv)

| quantity | value |
|---|---|
| first A at frame | 155 |
| Mario x at first A | 289 |
| stim source | goomba |
| distance to threat at first A (px) | 20.0 |
| theta at first A (deg) | 43.6 |
| TTMn at first A | 0.101 |
| clip frames | 133 |
| episode end | stuck at x 722 (wall H64 @736) |

## clip 02  (source: clips/data/default_knobs_log.csv)

| quantity | value |
|---|---|
| max_x | 723 |
| end | stuck at x 722 |
| cause | wall H64 @736 |
| episode frames | 614 |
| clip frames | 306 |

## clip 03  (source: clips/data/fly4b_display_log.csv, clips/data/theta4b_display_log.csv)

| quantity | value |
|---|---|
| episode | HOLDOUT noop_start 3, seed 101, sigma 0 |
| theta rule: max_x / end / blind presses | 2010 / enemy dx=6 / 2 of 22 |
| fly 4b: max_x / end / blind presses | 2754 / enemy dx=8 / 21 of 44 |
| theta* (deg) | 47.04 |
| clip frames | 1820 |

## clip 04  (source: evo4/fly/montage.mp4 (copied), evo4/fly/gen.csv)

| quantity | value |
|---|---|
| labels | gen | max_x | death cause of that generation's best genome (HOLDOUT noop_start 3, sigma 0) |
| stages | runs/004_report_numbers.json, fly.montage_stages |

## clip 05  (source: clips/data/hopper_display_log.csv)

| quantity | value |
|---|---|
| end | flag x 3161 |
| frames | 2124 |
| A_frac | 0.77 |
| blind presses | 38 of 92 |
| 'fails under 5% noise' | flag 5 of 5 at sigma 0 but 0 of 5 at sigma 0.05 (HOLDOUT): runs/004_robust.md table 3, runs/005_controls.json holdout[real/part4_hopper] |
| clip frames | 2124 |

## clip 06  (source: clips/data/shuffle_median_log.csv, runs/007_fair_eval.json) -- Part 6b replacement

| quantity | value |
|---|---|
| shuffle seed (median of 0-2 by evolved HOLDOUT mean max_x) | 1 |
| episode (median max_x of 10) | {'noop_start': 3, 'seed': 101, 'sigma': 0.05} |
| max_x | 2470 |
| end | died (pit) |
| blind presses | 19 of 44 |
| that seed's HOLDOUT mean max_x / distinct trajectories | 2470 / 1 of 10 |
| selection | typical, not best: replaces Part 5's best-of-40 clip |
| clip frames | 1713 |

## clip 07  (clips/07_results_card.png; source: runs/007_fair_eval.json, runs/007_default_knobs.json)

| arm | HOLDOUT mean max_x | distinct trajectories of 10 | looming escapes | blind presses |
|---|---|---|---|---|
| real/evolved_best | 1172 | 3 | 10 | 7.8 |
| real/4b_original | 2487 | 2 | 10 | 19.0 |
| shuf0_rn/evolved_best | 1784 | 1 | 0 | 10.0 |
| shuf1_rn/evolved_best | 2470 | 1 | 0 | 19.0 |
| shuf2_rn/evolved_best | 3161 | 1 | 0 | 25.0 |
| timer_evolved | 2469 | 1 | 0 | 26.0 |
| theta_rule_evolved | 2056 | 2 | 10 | 2.0 |

HOLDOUT = 5 start timings x sigma {0, 0.05} on level 1-1: held-out start timings, not held-out levels. Part 5 and earlier HOLDOUT means count 10 episodes but fewer distinct trajectories: real 4b fly 2 distinct (max_x 2754 x8, 1421 x2); Part 4 hopper at sigma 0: 1 distinct (3161 x5); default-knob real: 1 (723 x10).

## Invented pieces

Nothing below is read off the connectome (source of truth: `knobs.INVENTED`). evolved = searched by CMA-ES on TRAIN; fixed = set by hand.

| piece | how set | what it is |
|---|---|---|
| G | INVENTED (evolved) | global recurrent gain |
| TTMN_THRESH | INVENTED (evolved) | TTMn activity that triggers A |
| A_HOLD | INVENTED (evolved) | frames A is held once triggered (a forced hold, CONTROL_AUDIT.md) |
| COOLDOWN | INVENTED (evolved) | frames A is refused after a hold |
| HOME_R | INVENTED (evolved) | constant rightward drive into LC10a-R every frame: the direction of travel is ours |
| PIT_GAIN | INVENTED (evolved) | scale of the pit cue |
| THETA_RULE_DEG | INVENTED (evolved) | no-brain baseline's threshold (theta arm only) |
| PIT_SENSE | INVENTED (fixed) | the PIT CUE: a pit has no face, so its width is fed to LC4/LPLC2 as a looming angle |
| PIPE_SENSE | INVENTED (fixed) | pipe/wall faces fed to LC4/LPLC2 as a looming angle (face height used as width) |
| W_ENEMY | INVENTED (fixed) | Goomba width used in theta = 2 atan(w / 2d) |
| STIM_COMBINE | INVENTED (fixed) | 'sum': every visible object adds its theta and |dtheta| |
| SENSOR_NOISE | INVENTED (fixed) | multiplicative Gaussian noise on the LC4/LPLC2 inputs (0 for display runs, 0.05 TRAIN/HOLDOUT) |
| NOISE_MODE | INVENTED (fixed) | 'common': one noise draw per frame for the whole population |
| ALPHA | INVENTED (fixed) | leak/mix rate of the rate update |
| CLIP | INVENTED (fixed) | activity ceiling |
| SUBSTEPS | INVENTED (fixed) | network steps per game frame |
| DNP09_THRESH | INVENTED (fixed) | DNp09 activity that means 'walk right' |
| STEER_THRESH | INVENTED (fixed) | |DNa_R - DNa_L| needed to steer |
| BLIND_PX | INVENTED (fixed) | blind-press metric distance |
| BLIND_PENALTY | INVENTED (fixed) | fitness penalty per blind press |
| FLAG_BONUS | INVENTED (fixed) | fitness bonus for the flag |
| SPAM_FIXED_HOLD/COOLDOWN | INVENTED (fixed) | spam_fixed baseline cadence 18/3 |
| RANDOM_A_P | INVENTED (fixed) | right_randA baseline P(A) |
| SCRIPT_HOLD | INVENTED (fixed) | scripted driver jump length (assisted tests only, never in fitness) |
| tile IDs / rows (level.py) | INVENTED (fixed) | SOLID_WALL {18..21, 97}, ground rows 11-12, empty 0: hand-identified on 1-1 (run 001 notes); meaning unverified on other levels |
| W_steer construction | INVENTED (fixed) | cast choice, top-40 LC10a->DNa intermediates, predicted-NT signs, row-normalisation (tutorials/20_steering.ipynb) |

What IS connectome: the 636-neuron cast and its synapse counts (MaleCNS v1.0); signs come from predicted neurotransmitter.

## Checksums (sha256)

| file | sha256 |
|---|---|
| W_steer.npy | 5c57f81f5b1d260eab6887d92a42544e35e6dfea081c4d29b125e9fba1a8e2cb |
| W_steer_shuf0.npy | 769f7b69f9d5ac3a3440cb5dafbaca079581d558b24c0f51e2f203633992b535 |
| W_steer_shuf0_rn.npy | c1c27754f02a836cd1326fa74925f9226c2401bc7f64707e1cee158663f974bf |
| W_steer_shuf1_rn.npy | e6df1f0ee4ee2fc56902bddf581b150146de2cfc244cea8ac65fe86af57c5f85 |
| W_steer_shuf2_rn.npy | 296882fb2bed8aca78337e7289c08f73bfb4992a8cb2223977a8d6b6b5b51888 |
| W_steer_shuf3_rn.npy | 4545dd09c967390467f293a41cd752cb79d6653cfaea4fb09d7edd10d06f11ec |
| W_steer_shuf4_rn.npy | 2dd72a6afedc5e69ea1c1eb09a70fc636b712815e9a9c92bdefd0125213db8c8 |
| steer_bodies.parquet | 47dcb32ae2690ae1f70b6d4b27cc4f12bd74c001ad58acdf587548295004798f |
| steer_edges.parquet | 0268e3a2e43fcd5033d685608bc9c8fb0e99bf07576303be1209a96f61614ba0 |
| soma_xyz.npz | bb51287ceed0c2991fcd059866057889671dc136f4bd30d0a1f2e1b9ff2e3cf3 |
