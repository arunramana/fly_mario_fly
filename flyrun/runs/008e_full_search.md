# 008e — Part 7e: full search + the one HOLDOUT evaluation (flyrun, assisted, disclosed)

Stamps: see `evo7e/*/stamp.json`, `runs/008e_holdout.json`. Amendment 3 (`runs/008_preregistration.md`, commit aeec803) was committed before the search; the final genome (`runs/008e_final_genome.json`, commit a2f2fec) was committed before HOLDOUT. HOLDOUT ran once (`008e_holdout.lock` blocks a second run).

## Verdict: **NO WIN**

Final genome: **0/10 HOLDOUT flags**, mean max_x **1628.8**, min 1532, all constraints hold on all 10 episodes. Criterion was ≥ 3/10 flags and constraints on every episode: flags fail. By rule (e): best feasible HOLDOUT mean max_x 1628.8 < 2400, so **fallback (a)** applies (make floating block rows visible as obstacle faces, a new labelled sense, then repeat 7d → 7e). Fallback (b) is not available. The blind-press limit was not touched.

## 1. Per restart (TRAIN only)

| restart | gens run in 7e | wall | feasible genomes | best TRAIN fitness (gen) | best's TRAIN mean max_x | stop |
|---|---|---|---|---|---|---|
| R1 warm_7d | 16 (of 26) | 7.7 min | 161/256 | 1589.3 (gen 0 = the start genome; never beaten) | 1798 | early stop, 15 gens without improvement |
| R2 fresh_97 (continued from 7d state) | 28 (gens 10–37; of 22 + 10 freed) | 15.7 min | 433/448 | 1449.2 (gen 22) | 1782 | early stop |
| R3 fresh_96 | 12 | 4.2 min | 92/192 | 1056.2 (gen 6) | 1223 | allotment used |
| R4 fresh_95 | 12 | 4.8 min | 133/192 | **1730.3 (gen 11)** | **1980** | allotment used (still improving) |

Total search wall 32.5 min (the 3 h cap never bound: generations took ~25 s on an idle machine versus the ~2.5 min planned). 10 generations freed by R1's early stop went to R2 (R1 itself had stopped), which then early-stopped too. No restart reached a TRAIN flag with a feasible genome (0 feasible genomes with flags in any restart).

Death map of each restart's best genome (6 TRAIN episodes, max_x / cause):
- R1 warm_7d: 1805 enemy(behind, dx −14) · 2010 enemy · 1409 pit · 2015 enemy · 1532 enemy(behind) · 2015 enemy
- R2 fresh_97: 1783, 1782, 1782, 1783, 1782, 1783 — all enemy dx 9–10 (one trajectory, x≈1782)
- R3 fresh_96: 1220–1226 ×6, all enemy dx 7–10 (the x≈1220 ledge, not cleared)
- R4 fresh_95: 2017 · 1805 · 2017 · 2015 · 2013 · 2015 — all enemy (one is dx −16, behind)

Rejections (all infeasible genomes, per restart): "first A at a threat" is in almost every rejection again (R1 84/95 infeasible, R3 99/100, R4 56/59; R2's 15 are first_a only); silence fails appear only together with first_a; "blind" alone is rare.

## 2. Final genome (rule d: highest feasible TRAIN fitness, ties fewer blind) = fresh_95 gen 11

| knob | final | r3 | drift |
|---|---|---|---|
| G | 0.673 | 0.711 | −0.04 |
| TTMN_THRESH | 0.262 | 0.295 | −0.033 |
| A_HOLD | 21 | 18 | +3 |
| COOLDOWN | 9 | 2 | +7 |
| HOME_R | 1.582 | 1.684 | −0.10 |
| PIT_GAIN | 3.46 | 1.36 | +2.10 |

(It lands in the same region as the 7d warm best: COOLDOWN ~9–10, A_HOLD ~20–21, higher PIT_GAIN — found independently from a fresh start.) TRAIN: fitness 1730.3, mean max_x 1980, min 1805, 0 flags, blind presses 5 per episode.

### HOLDOUT (once)

| noop | seed | σ | max_x | end | blind | first A stim_d | constraints |
|---|---|---|---|---|---|---|---|
| 3 | 101 | 0.0 | 1532 | enemy dx=−12 | 5 | 22 | ok |
| 11 | 102 | 0.0 | 1532 | enemy dx=−12 | 5 | 22 | ok |
| 25 | 103 | 0.0 | 1532 | enemy dx=−12 | 5 | 22 | ok |
| 33 | 104 | 0.0 | 1532 | enemy dx=−12 | 4 | 22 | ok |
| 41 | 105 | 0.0 | 1532 | enemy dx=−12 | 5 | 22 | ok |
| 3 | 101 | 0.05 | 1532 | enemy dx=−12 | 4 | 22 | ok |
| 11 | 102 | 0.05 | 2015 | enemy dx=9 | 4 | 22 | ok |
| 25 | 103 | 0.05 | 1532 | enemy dx=−12 | 4 | 22 | ok |
| 33 | 104 | 0.05 | 2017 | enemy dx=5 | 5 | 22 | ok |
| 41 | 105 | 0.05 | 1532 | enemy dx=−12 | 5 | 22 | ok |

0 flags · mean 1628.8 · min 1532 · **3 distinct trajectories** (1532 ×7, 2015, 2017). Death map: 9/10 enemy contact (7 at x 1532 with the Goomba *behind* Mario, dx −12; 2 at x≈2015), 0 pits, 0 ledge deaths at x≈1220. The x≈1220 ledge is cleared on all 10 held-out episodes (this is real progress over r3: 8/10 died there). Silence A_frac 0. I did not diagnose the x 1532 or x≈2015 deaths (not in scope).

## 3. Reference only, NOT a candidate: best infeasible TRAIN genome (fresh_95 gen 6)

Selected by TRAIN mean max_x (1788.8) among infeasible genomes; infeasible because of **blind presses** (TRAIN mean 9.2 > 8). Knobs: G 0.827, TTMN_THRESH 0.391, A_HOLD 20, COOLDOWN 21, HOME_R 0.617, PIT_GAIN 2.27.

HOLDOUT: **0 flags**, mean max_x 1788.4, every episode dies to an enemy at x 1786–1791 (dx 8–10); blind presses 9–10 per episode (fails the ≤ 8 rule on all 10), first A at stim_d 51–52 (passes). Not a flag run, so it would not help fallback (b) even if (b) applied. (The 7d infeasible genome that flagged 3/6 on TRAIN is in `evo7d/` and was not evaluated on HOLDOUT; the rule here picked the best by TRAIN mean max_x in 7e only.)

## 4. Caveats
- TRAIN fitness ranks single genomes on 6 episodes; the final was picked from ~30 near-ties at 1.4–1.7k and landed on HOLDOUT at 1629 mean (TRAIN 1980): a modest generalisation gap, mostly the x 1532 deaths, which are rare on TRAIN (1 of 6 episodes).
- 1532 ×7 are one deterministic trajectory, so "7 deaths" is one event.
- The search plateaued: R1 and R2 early-stopped; R3 and R4 were cut by their 12-generation allotment (R4 was still improving).
- Nothing was changed in knobs, senses, constraints, or fitness. No clip was rendered (no flag, so no `clips/08e_win.mp4`). Montages: `evo7e/<restart>/montage.mp4` (gitignored).

Files: `evo7e/<restart>/{gen.csv,all_evals.csv,best_genome.json,state.pkl,stamp.json,montage.mp4}`, `runs/008e_final_genome.json`, `runs/008e_reference_genome.json`, `runs/008e_holdout.json`.
