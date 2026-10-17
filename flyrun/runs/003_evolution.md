# 003 evolution: fly vs theta rule (flyrun, part 4 of 6)

CMA-ES, popsize 12, sigma0 0.25 in the unit cube, up to 40 generations, 3 restarts per arm (CMA seeds 1, 2, 3), each starting from the defaults. Stop a restart on flag or after 10 generations with no improvement. Fitness = max_x + 10000 x flag_get, from one deterministic episode per evaluation (sigma 0, fly-only frames, the `driver != "fly"` guard stays). STIM_COMBINE = sum. Numbers: `003_report_numbers.json`. Per-individual logs: `evo/<arm>/all_evals.csv` (fly 612 evaluations, theta 768) and `evo/<arm>/gen.csv`.

**Wall-clock.** Evolution: 826 s (13.8 min) for both arms with 12 workers (fly 647 s, theta 169 s; the fly episodes are slower because they get further and run the network). The checks and report after it took about 4 more minutes.

**Pre-step (stair fix).** A face is now the nearest column ahead of Mario's column that is higher than his column, H = the difference. The scripted driver up the first staircase gives a new face per step (x 2144, 2160, 2176, 2192, each H 16); pipe 1 is still H 32. All earlier tests still pass (18/18 with the new stair test).

## Fly arm (6 knobs)

![fly curve](003_curve_fly.png)

| restart | gens run | best fitness | end of the best run | best genome |
|---|---|---|---|---|
| 1 | 14 | 1953 | died, enemy 7 px ahead, x 1953 | G .93, TTMN .147, hold 20, cool 2, HOME_R .10, PIT_GAIN 1.36 |
| 2 | 22 | 2015 | died, enemy 10 px ahead, x 2015 | G .79, TTMN .285, hold 27, cool 8, HOME_R 1.44, PIT_GAIN 1.49 |
| **3** | 15 | **13161** | **reached the flag (x 3161, 2121 frames)** | **G .847, TTMN .181, hold 18, cool 3, HOME_R .712, PIT_GAIN .839** |

Best genome (restart 3, generation 14): `G 0.8472, TTMN_THRESH 0.1806, A_HOLD 18, COOLDOWN 3, HOME_R 0.7123, PIT_GAIN 0.8386`. Only one of the 612 evaluated individuals reached the flag. Death map of the best run: no death; cleared every obstacle in the level map to the flagpole (x 3161; the pole base at 3168 is where the flag is taken).

## Theta-rule arm (3 knobs)

![theta curve](003_curve_theta.png)

| restart | gens run | best fitness | end of the best run | best genome |
|---|---|---|---|---|
| 1 | 19 | 2469 | died in pit 3, x 2469 | theta* 45.5 deg, hold 20, cool 9 |
| **2** | 26 | **2470** | **died in pit 3, x 2470** | **theta* 44.45 deg, hold 19, cool 4** |
| 3 | 19 | 2470 | died in pit 3, x 2470 | theta* 45.0 deg, hold 19, cool 4 |

Best genome: `THETA_RULE_DEG 44.45, A_HOLD 19, COOLDOWN 4`. Death map of the best run: cleared everything to x 2448, died in pit 3 (x 2448, W 32) at x 2470. Not cleared: pit 3 and everything after it (the 64 px wall column at 2480, the down-stairs, pipes 5 and 6, the final staircase). All three restarts end at 2469-2470 in the same place.

## Checks

| check | fly | theta |
|---|---|---|
| 1. gen 0 best >= 723 (all restarts) | pass (723, 723, 1138) | pass (1415, 723, 723) |
| 2. best fitness non-decreasing | pass | pass |
| 3. best genome re-run alone reproduces its logged fitness | pass (13161 = 13161) | pass (2470 = 2470) |
| 5. knobs at a range bound (within 2% of an edge) | none | none |

Generation 0 always includes the default genome as individual 0, so check 1 also confirms the decode reproduces the 723 default. No knob needed a wider range.

### 4. Robustness of each arm's best genome

| condition | fly: mean / min max_x, flag rate | theta: mean / min max_x, flag rate |
|---|---|---|
| sigma 0.05, 10 seeds (common-mode noise) | 1831 / 800, 1 of 10 | 2470 / 2470, 0 of 10 |
| sigma 0.10, 10 seeds | 1629 / 800, 0 of 10 | 2470 / 2470, 0 of 10 |
| noop_start 0 | 3161 / 3161, flag | 2470, no flag |
| noop_start 7 | 3161, flag | 1657, no flag |
| noop_start 17 | 3161, flag | 1657, no flag |
| noop_start 33 | 3161, flag | 1657, no flag |

- The fly's flag run is **not robust to sensor noise**: at sigma 0.05 only 1 of 10 seeds reaches the flag, and the others die to an enemy at x 800, pit 1 (x 1138) or the Goomba cluster at x about 2010. At sigma 0.10 none do.
- The theta rule is immune to the noise because its theta is read clean (the noise only touches the circuit's detector inputs), so that column is not a fair comparison; it says only that the rule's death at pit 3 is not noise.
- noop_start: the fly holds across all four starting delays. The theta rule drops from 2470 to 1657. So `noop_start` is not a pure time shift once a policy gets past the early level (my part 2 / 3 remark was true only while runs died by x 700): later enemy positions depend on the frame count.

## What the fly's flag run actually is

Behaviour of the best genome over the run (from `evo_report.py`):

| | fly (flag run) | theta (best) |
|---|---|---|
| A held, fraction of frames | 0.78 | 0.45 |
| A onsets | 92, median interval 21 frames (= hold 18 + cooldown 3, the minimum) | 38, median interval 23 |
| onsets with nothing within 60 px (or nothing seen) | 39 of 92 | 2 of 38 |
| TTMn median / 95th percentile (threshold 0.18) | 1.00 / 4.19 | n/a |

So the evolved fly is close to a **continuous hopper**: TTMn sits far above its threshold almost whenever anything is on screen (a Goomba, a pipe, a pit within the visible 256 px), so A is pressed at the fastest rate the hold and cooldown allow. It is not spontaneous: with no enemy, no pipe and no pit sensed, the same genome gives TTMn 0.02, no A at all, and Mario walks to x 296 and stops (checked over 600 frames). It is stimulus-driven, but with G 0.85 and the sum combine the stimulus is almost always present, so the selectivity that part 2 / 3 relied on (jump when theta reaches 43.6 deg) is gone. That also explains the noise fragility: a hopper's landing phase depends on exact frame timing.

## Head-to-head: fly vs theta rule

The fly beats the threshold rule on the headline number: 1 of 3 restarts reaches the flag (13161), against 0 of 3 for the rule (2470, all three at pit 3). But the evidence for "the circuit does something the threshold does not" is weaker than that: the other two fly restarts end at 1953 and 2015, both worse than every theta restart (2469-2470), so the median restart favours the rule and the fly's advantage rests on one genome out of 612 evaluations. The two arms differ at these places: (a) pit 3 (x 2448, W 32, followed by a 64 px wall column at 2480): the rule dies there in all three restarts, jumping at d about 26 (x 2424) and landing in the pit, while the flag-run fly takes off at d 12 (x 2437) with an 18-frame hold and presses again at x 2474 after the 3-frame cooldown; I did not test whether the later take-off is what matters. (b) The Goomba cluster at x 1950 to 2015: the rule clears it, two fly restarts die there (the fly's detector reading of several close Goombas at once is the likely difference, since the rule uses the same summed theta but does not pass it through the circuit). (c) Everything after x 2470 is only reached by the fly, and it is reached by hopping nearly continuously, not by a jump timed to a looming angle. The honest summary is that the circuit did not "discover" a better looming trigger: it found a different, much less selective operating point (low threshold relative to a high sum-combine drive), and that operating point happens to cross pit 3 and the stairs while being fragile to noise.

## Files

`evo/fly/best.mp4` and `evo/theta/best.mp4` (the best genomes), `evo/<arm>/montage.mp4` (generation 0 then each generation where best max_x jumped, labelled "gen N | max_x | cause"), `evo/<arm>/r<k>_gen_NN.mp4` (that generation's best, every 5 generations), `python -m flyrun.render_stage --arm fly --gen N` and `python -m flyrun.montage --arm fly` regenerate them. Fly montage stages: gen 0 (1138, pit), 1 (1222), 2 (1411), 5 (1948), 7 (2008), 11 (2011), 13 (2013), 14 (3161, flag). The shuffled control was not run (part 5).
