# E1b: ablation of the E1 best genome (post-hoc, explanation only; base 5fcf70b; no selection, no new evolution, no rule change)

**HOLDOUT is reused here for explanation only. The official E1 test result stays 8/10 (`runs/E1.md`); nothing was chosen from these numbers.** Same 881 brain, all four drives on, every arm on the 12 training episodes AND the 10 HOLDOUT episodes (`runs/E1b_episodes.json`, 220 episodes). The genes reset to the START value (arm C: HOME_R 0.5, HUM_GAIN 14.5342, SMELL_GAIN 213.9495, TTMN_THRESH 0.10, RELEASE_THRESH 0.10, STEER_THRESH 0.01) against the E1 best (0.4536, 13.69, 439.4, 0.1275, 0.0978, 0.0101). "Early hum+loom jump" = a grounded A onset with a hum and a loom threat at once at a loom angle below 40 deg (arm A's smallest trigger in C1). Two arms at the bottom are EXTRA (not in the brief): the reverse direction, start with the evolved thresholds put in.

## Training (12 episodes)
| arm | flags | mean max_x | mean score | ? blocks | mushroom eaten | deaths (cause @ x) | early hum+loom jumps | A with nothing in view |
|---|---|---|---|---|---|---|---|---|
| arm | flags | mean max_x | mean score | ? blocks | mushroom eaten | deaths (x) | early hum+loom jumps | A with nothing in view |
|---|---|---|---|---|---|---|---|---|
| 1 evolved | 12/12 | 3161 | 2258 | 3.8 | 11 | - | 82 | 0 |
| - TTMN_THRESH reset | 7/12 | 2541 | 1450 | 1.9 | 11 | {'enemy@1789': 2, 'enemy@1784': 1, 'enemy@1222': 1, 'enemy@1786': 1} | 91 | 0 |
| - SMELL_GAIN reset | 12/12 | 3161 | 2258 | 3.8 | 11 | - | 82 | 0 |
| - RELEASE_THRESH reset | 9/12 | 2689 | 2088 | 4.8 | 12 | {'stuck@1248': 2, 'stuck@1255': 1} | 78 | 0 |
| - HOME_R reset | 10/12 | 2935 | 958 | 3.9 | 0 | {'enemy@1807': 2} | 58 | 0 |
| - HUM_GAIN reset | 10/12 | 2932 | 1083 | 2.3 | 0 | {'enemy@1784': 2} | 68 | 0 |
| - STEER_THRESH reset | 12/12 | 3161 | 2258 | 3.8 | 11 | - | 82 | 0 |
| 6 start (= arm C) | 0/12 | 1212 | 283 | 1.9 | 0 | {'enemy@1220': 11, 'pit@1127': 1} | 59 | 0 |
| extra: start + evolved TTMN_THRESH only | 12/12 | 3161 | 1167 | 2.5 | 0 | - | 87 | 0 |
| extra: start + evolved TTMN + RELEASE | 10/12 | 2932 | 1083 | 2.3 | 0 | {'enemy@1784': 2} | 68 | 0 |

## HOLDOUT (10 episodes; explanation only)
| arm | flags | mean max_x | mean score | ? blocks | mushroom eaten | deaths (cause @ x) | early hum+loom jumps | A with nothing in view |
|---|---|---|---|---|---|---|---|---|
| arm | flags | mean max_x | mean score | ? blocks | mushroom eaten | deaths (x) | early hum+loom jumps | A with nothing in view |
|---|---|---|---|---|---|---|---|---|
| 1 evolved | 8/10 | 2890 | 1940 | 3.6 | 7 | {'enemy@1806': 2} | 62 | 0 |
| - TTMN_THRESH reset | 7/10 | 2692 | 1480 | 1.9 | 9 | {'enemy@1222': 1, 'enemy@1786': 2} | 78 | 0 |
| - SMELL_GAIN reset | 8/10 | 2890 | 1940 | 3.6 | 7 | {'enemy@1806': 2} | 62 | 0 |
| - RELEASE_THRESH reset | 5/10 | 2270 | 1840 | 4.2 | 9 | {'stuck@1255': 3, 'enemy@1806': 1, 'stuck@1248': 1} | 59 | 0 |
| - HOME_R reset | 8/10 | 2890 | 970 | 3.7 | 0 | {'enemy@1806': 2} | 48 | 0 |
| - HUM_GAIN reset | 8/10 | 2888 | 1120 | 2.6 | 0 | {'enemy@1784': 1, 'enemy@1805': 1} | 57 | 0 |
| - STEER_THRESH reset | 8/10 | 2890 | 1940 | 3.6 | 7 | {'enemy@1806': 2} | 62 | 0 |
| 6 start (= arm C) | 0/10 | 1220 | 280 | 1.9 | 0 | {'enemy@1220': 10} | 50 | 0 |
| extra: start + evolved TTMN_THRESH only | 9/10 | 3025 | 1070 | 2.2 | 0 | {'enemy@1805': 1} | 69 | 0 |
| extra: start + evolved TTMN + RELEASE | 8/10 | 2888 | 1120 | 2.6 | 0 | {'enemy@1784': 1, 'enemy@1805': 1} | 57 | 0 |

## Which gene did what
**The 0/10 -> 8/10 recovery is TTMN_THRESH alone: 0.10 -> 0.1275.** Putting only that one gene into the start genome gives 12/12 training flags and 9/10 on HOLDOUT (even one flag better than the full evolved genome's 8/10), while the start genome is 0/12 and 0/10. Resetting it in the evolved genome costs flags (7/12 training, 7/10 HOLDOUT) and the blocks and score. I did not establish the mechanism: the early hum+loom jump count does not fall (59 for the start, 82 for the evolved genome, per 12 episodes), so he still jumps early at times; what changes is that the jumps stop ending in the x ~1220 death (the start dies there in 10/10 HOLDOUT episodes; with the evolved threshold only one of the 22 episodes of the reset arm dies at x 1222). In the arm with TTMN_THRESH reset the lost flags are mostly at the Goomba pair near x 1784-1789 (5 of the 22 episodes), not at x 1220. **The mushroom and the score come from HUM_GAIN and HOME_R together:** resetting either one alone (HUM_GAIN 13.69 -> 14.53, or HOME_R 0.4536 -> 0.5, each a change of ~6-10%) keeps the flags (10/12, 8/10) but the mushroom is eaten 0 times and the score falls from ~2260 to ~1000 (HUM_GAIN also loses ~1.5 blocks); the TTMN-only genome likewise eats none (score ~1100). So the 7 mushrooms of the evolved fly need the evolved HUM_GAIN (at its floor, 13.69) and the evolved HOME_R at once: a narrow, fragile combination (the block 1248 mushroom hit and the walk to it), not a robust improvement. **SMELL_GAIN (x2.05) and STEER_THRESH made no difference at all:** resetting either gives results identical to the evolved genome, episode for episode (the smell never beat the home signal in 1-1 here, and the steer threshold was never crossed in a way that mattered). **RELEASE_THRESH 0.0978 is needed by the evolved genome but is not needed for the flags:** with it reset to 0.10 the evolved genome gets stuck at x 1248-1255 (5/10 HOLDOUT, 9/12 training), yet the TTMN-only genome (release 0.10) gets 9/10, so the damage comes from the interaction of the other evolved genes with a 0.10 release, not from release as such. Caveats: single runs per cell (deterministic given the seeds), 12 and 10 episodes, no interaction search beyond these arms, and the training and HOLDOUT episodes of the two deaths at x 1784-1807 (a Goomba pair, mostly at sigma 0.05) are present in most arms.

Clip: `clips/E1b_threshold.mp4` (R3 layout, 11 s: x 1120-1250 at noop 0, sigma 0, first the evolved genome with TTMN_THRESH reset to 0.10, then the evolved genome). Note that in this particular episode (noop 0, sigma 0) the reset arm also gets past the x ~1220 spot; its run ends at the Goomba pair at x 1789 (frame 1328), outside the clip window, so the clip shows the same spot being passed by both rather than a visible failure of arm 2. Files: `flyrun/e1b.py`, `runs/E1b_episodes.json`, `runs/E1b_E1b_*` (the two logged runs for the clip).
