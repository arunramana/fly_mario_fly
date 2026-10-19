# RE2: looming from BEHIND (REAR_EYE) + sour smell from BEHIND (REAR_SOUR), toggles default OFF

Base: main after the audit (58c9722). Genome: the E1s champion (`runs/E1s_progress.json` best, generation 8), frozen, run as is. Brain: the 907-neuron sour brain, headroom looming ON, sour ON. "Dev set" = the 10 episodes that used to be called HOLDOUT (`episodes4.HOLDOUT`); it is no longer a held-out set (AUDIT.md §3), so nothing here is a generalisation claim.
Code: `senses_v2.py` (rear candidates, `sour_enemy(rear=)`, `headroom_factor` for a rear enemy), `motor.decide(block_backup=)`, `run.py` (passes the gate), `knobs.py` (3 knobs + INVENTED rows + `toggle_set`), `render/panels.py` + `e1s_log.py` (the "behind" ticks), `re2_run.py` (arms A-F), `re2_onesided.py`, `re2_clips.py`, `tests/test_re2.py` (13 tests; the full flyrun suite, run before the 13th was added: 119 passed in 3:27, no failures).

**Headline.**
1. The Koopa-scene death is **not** a rear-enemy death. The Koopa that trails him (RAM slot 1) is 56 px behind at hand-over and 124 px behind at the end, walking away at 0.4 px/frame; it was never the chosen threat. He is killed by the Koopa **ahead** (slot 2), the chosen threat from the first frame of hand-over, whose loom the headroom rule scales to 0, and whose sour back-up starts 5 frames before contact. No Left + A: he never pressed A in the whole fly segment.
2. All six scene arms (A-F) give the **same** run: died at x 889, same cause, same 5 back-up frames. REAR_EYE never fires in the scene (0 rear-loom frames); REAR_SOUR adds up to +0.015 MDN for 27 frames and presses no Left.
3. On the 1-1 dev set only **REAR_EYE alone (B) keeps 10/10** (identical flags, max_x, score, back-ups; 7 of 10 trajectories differ by a frame or more; 0 jumps caused by a rear threat). **Both REAR_SOUR modes lose flags: honest 8/10 (C, E), gated 9/10 (D, F).** Over 30 episodes with REAR_EYE on there was exactly one jump started while a rear threat was chosen (arm E, episode 7), and it was a backward hop inside a Goomba sandwich, not an avoided hit.
4. My recommendation (Arun decides): keep all three toggles OFF in the champion config. REAR_EYE is harmless on 1-1 but earns nothing; REAR_SOUR costs flags in both modes.

## 0. Trace check (no code changes): the AV1 / E1s Koopa scene, arm A, 572 frames
The scene: L2 button replay to x 780 (grounded), hand-over at frame 509 (x 782), the fly walks right and dies at frame 571 (x 889, "enemy dx=11"). The trace ends at frame 571, so "frame ~600" does not exist; I use 509 (hand-over) to 571 (death). Names by RAM slot (`runs/RE2_scene_A_trace.csv`; the old `runs/AV1_E1sfloor_scene_trace.csv` has the same trajectory, hash c028f53ee1):
| name | slot | what | x at hand-over (f509) | x at death (f571) | direction | state |
|---|---|---|---|---|---|---|
| Koopa 1 | 0 | the shell Mario stomped | 671 | gone at f558 | still | shell (state 4) |
| **Koopa 2** | 1 | the Koopa he passed at f~460-470 (the replay's own moves) | 710 | 749 | **right, away from him**, 0.4 px/frame | walking (0) |
| Koopa 3 | 2 | **the killer**, ahead | 938 | 900 | **left, toward him**, 0.6 px/frame | walking (0) |
| Goombas | 3, 4 | appear at f530, f544 | 989 | 964 / 1007 | left | walking |

- **Was Koopa 2 ever the chosen threat? No.** `threat_id` is `enemy:2` (Koopa 3) on every one of the 63 fly frames, because the senses ignore anything behind his left edge. Koopa 2 never mattered anyway: the gap behind him grows 56 -> 79 -> 101 -> 124 px (f509 / 530 / 550 / 571).
- **Koopa 3, the chosen threat, was seen but its loom is zeroed.** Unscaled theta 9.3 deg at f509, 22 deg at f545, 50 deg at f560, 106 deg at f567, 170 deg at f571; the headroom factor is 0.0 all the way (rise 0, need 26), so the loom input is 0, TTMn stays at 0.0004 and he never jumps (A frames 0). This is the AV1 finding again, with the champion genome.
- **The sour back-up starts too late.** MDN 0.100 at f566 (gap to Koopa 3: 9 px), above the champion's MDN_THRESH 0.109 at f567 (gap 7 px): Left for the last 5 frames (f567-571), A never. He is still moving right from momentum (x 883 -> 889) and touches it at f570-571.

Last 30 frames (Left / Right / A are the buttons, MDN and TTMn the readouts, air = airborne flag; K1 is gone from f558; gap = Koopa 3 left edge - Mario right edge):
| frame | Left | Right | A | MDN | TTMn | air | Mario x | K1 shell | K2 | K3 | gap to K3 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 542 | 0 | 1 | 0 | 0.034 | 0.0004 | 0 | 839 | 671 | 731 | 917 | 66 |
| 545 | 0 | 1 | 0 | 0.036 | 0.0004 | 0 | 845 | 671 | 732 | 915 | 58 |
| 548 | 0 | 1 | 0 | 0.039 | 0.0004 | 0 | 850 | 671 | 734 | 914 | 52 |
| 551 | 0 | 1 | 0 | 0.043 | 0.0004 | 0 | 855 | 671 | 736 | 912 | 45 |
| 554 | 0 | 1 | 0 | 0.047 | 0.0004 | 0 | 860 | 671 | 738 | 910 | 38 |
| 557 | 0 | 1 | 0 | 0.053 | 0.0004 | 0 | 866 | 671 | 740 | 908 | 30 |
| 560 | 0 | 1 | 0 | 0.062 | 0.0004 | 0 | 871 |  | 742 | 906 | 23 |
| 563 | 0 | 1 | 0 | 0.077 | 0.0004 | 0 | 876 |  | 744 | 904 | 16 |
| 565 | 0 | 1 | 0 | 0.090 | 0.0004 | 0 | 880 |  | 745 | 903 | 11 |
| 566 | 0 | 1 | 0 | 0.100 | 0.0004 | 0 | 881 |  | 746 | 902 | 9 |
| 567 | **1** | 0 | 0 | 0.112 | 0.0004 | 0 | 883 |  | 746 | 902 | 7 |
| 568 | 1 | 0 | 0 | 0.125 | 0.0004 | 0 | 885 |  | 747 | 901 | 4 |
| 569 | 1 | 0 | 0 | 0.141 | 0.0004 | 0 | 886 |  | 747 | 900 | 2 |
| 570 | 1 | 0 | 0 | 0.162 | 0.0004 | 0 | 888 |  | 748 | 900 | 0 |
| 571 | 1 | 0 | 0 | 0.181 | 0.0004 | 1 | 889 |  | 749 | 900 | -1 |
(Every frame 542-571 is in `runs/RE2_scene_A_trace.csv`; I show every third plus the last ten.)

**Verdict: neither (a) nor (b).** He did not die to Koopa 2 (it trails and recedes), and he did not jump backward into anything (no A at all). He died head-on to Koopa 3 because the headroom rule removed the only output that could have saved him (the jump) and the sour back-up crossed its threshold 5 frames before contact. If "Koopa 2" meant the killer, the answer is: it was the chosen threat from the hand-over frame (509), seen as a Koopa with theta 9 deg, scaled to 0.
For Arun's decision, not changed here: the headroom rule (AV1) is what turns this scene into a death; the sour back-up with this genome is too slow for a head-on Koopa (MDN reaches 0.109 only at theta ~ 100 deg).

## 1. One-sided sour (907 brain, scratch build, default brain untouched) (`runs/RE2_onesided_sour.json`, `python -m flyrun.re2_onesided`)
Steady drive, 100 frames x 10 substeps, the champion's genes (SOUR_GAIN 4.909, HOME_R 0.465 into LC10a-R as in the game, MDN_THRESH 0.109, STEER_THRESH 0.0095); level = SOUR_GAIN x theta. The brain contains **13 DC4 ORNs: 4 left, 9 right** (not 60 per side: that is how the 907 brain is built), so "left only" drives 4 neurons and "right only" 9, each at the same per-neuron level.
| theta | level | left only: MDN | right only: MDN | both: MDN | DNa R-L (all three) |
|---|---|---|---|---|---|
| 20 deg | 1.71 | 0.0174 | 0.0319 | 0.0350 | +0.0464 |
| 43.6 deg | 3.74 | 0.0211 | 0.0527 | 0.0596 | +0.0464 |
| 50 deg | 4.28 | 0.0221 | 0.0584 | 0.0662 | +0.0464 |
| 70 deg | 6.00 | 0.0252 | 0.0760 | 0.0872 | +0.0464 |
| 90 deg | 7.71 | 0.0284 | 0.0937 | 0.1089 | +0.0464 |
- **Turn: none.** DNa R-L is +0.0464 in all three conditions at every level, identical to the home-only value (DNa L 0.0258, DNa R 0.0722, DNp09 0.198); with HOME off it is 0.0000 everywhere. The sour drive does not touch steering from either side.
- **MDN difference: yes, large.** Left-only gives 0.26-0.50 of the both-sides MDN (0.33 at 50 deg), right-only 0.86-0.91 (e.g. 50 deg: 0.022 / 0.058 / 0.066). With the champion's threshold 0.109, **only both sides at theta ~ 90 deg crosses it; neither side alone crosses at theta <= 90 deg** (right only 0.094). So in the game, where both antennae always get the same level, the asymmetry has no effect; it would matter only if a future cue fed one antenna.
- The 4 vs 9 split is a property of the model's DC4 subset, not something I verified against the connectome totals; the right/left ratio is what the build produces.

## 2. REAR_EYE (looming from behind)
What the code does (toggle `REAR_EYE`, default False; with it off the code path and the logs are byte-identical to before: `test_off_is_identical_to_before`, and the dev-set hashes of arm A equal E1s: `test_arm_a_reproduces_the_e1s_dev_set_trajectories`):
- The threat choice takes live, uncleared enemies (Goomba, Koopa, shell, piranha) on **both** sides, the nearest by the same 2-D gap (an enemy behind is measured from his left edge). Faces and pits stay ahead-only (`test_rear_eye_leaves_faces_and_pits_ahead_only`).
- A rear threat feeds the same inputs: theta = 2 atan(h / 2d) into LPLC2-R, |dtheta| into LC4-R (tracked per identity), the headroom factor applied from the enemy's left edge to his right edge.
- **One added rule, INVENTED (orange), that the brief did not spell out: a rear enemy is a candidate only while its gap is shrinking from the previous frame** (and not on the first frame it is seen). Reason: the loom detectors answer an expanding object and the input uses |dtheta|; without the rule a receding enemy that is the nearest object would be chosen, would feed LC4 with |dtheta| and LPLC2 with a large theta, and would hide a farther threat ahead (the choice is single-threat). With it, "moving away never triggers a jump" holds by construction and is tested with the real brain. I did not measure the variant without the rule.
- Overlay: the red box on the rear enemy plus a small red triangle "behind" tick; log columns `threat_rear`, `sour_rear` exist only when the toggles are on.
Tests (`tests/test_re2.py`, all pass): off identical; a closing rear enemy is chosen, theta grows on every frame to > 0.9 rad and dtheta > 0; with the real 907 brain the Giant Fiber drive (TTMn) reaches the jump threshold (>= 0.0992) for a Goomba walking up to 4 px behind him and stays < 0.01 for one moving away; a threat ahead wins against a farther rear one and loses to a nearer one.

## 3. REAR_SOUR (sour from behind), `REAR_SOUR_MODE` honest / gated
- `honest`: the sour source is the nearest sour enemy (Goomba, Koopa, piranha; a shell does not smell) on either side, the same 2-D gap, the same SOUR_GAIN x theta into both DC4 ORN groups. Real wiring DC4 -> MDN unchanged (`test_sour_off_ignores_an_enemy_behind_and_honest_smells_it_like_one_ahead`: the mirror image at the same gap gives the same level).
- `gated` (INVENTED, orange): same smell, but `motor.decide(block_backup=True)` while the nearest source is behind: MDN is still read and logged, Left is not pressed (`test_gated_blocks_left_only_while_the_source_is_behind`); A and the steering are untouched.
- Overlay: dotted yellow box on the rear enemy plus a yellow "behind" tick (checked on a rendered frame, `clips/RE2_rear_jump.mp4`).
Note on the rear definition: "behind" = fully behind his left edge; an enemy that overlaps him counts as ahead (as before).

## 4. Runs (champion genome, sour + headroom on)
### 4a. Koopa scene (1-2, L2 replay to x 780, hand-over at frame 509; noop 0, sigma 0) `runs/RE2_scene_<ARM>.json` + `_trace.csv`
| arm | REAR_EYE | REAR_SOUR | outcome | max_x | death x, cause | frames | back-up frames | MDN max | rear-loom frames | rear-sour frames |
|---|---|---|---|---|---|---|---|---|---|---|
| A | off | off | died | 889 | 889, enemy dx=11 | 572 | 5 | 0.1808 | 0 | 0 |
| B | on | off | died | 889 | 889, enemy dx=11 | 572 | 5 | 0.1808 | 0 | 0 |
| C | off | honest | died | 889 | 889, enemy dx=11 | 572 | 5 | 0.1808 | 0 | 27 |
| D | off | gated | died | 889 | 889, enemy dx=11 | 572 | 5 | 0.1808 | 0 | 27 |
| E | on | honest | died | 889 | 889, enemy dx=11 | 572 | 5 | 0.1808 | 0 | 27 |
| F | on | gated | died | 889 | 889, enemy dx=11 | 572 | 5 | 0.1808 | 0 | 27 |
All six trajectories have the same hash (c028f53ee1); Left in frames 567-571 only. Per frame around the event (arms A and E; chosen threat side, theta, sour source side, MDN, TTMn, buttons):
| frame | x | chosen threat (side) | theta (scaled / unscaled) | sour source side (E) | MDN A | MDN E | TTMn | buttons |
|---|---|---|---|---|---|---|---|---|
| 509 | 782 | Koopa 3 (front) | 0 / 9.3 deg | **rear** (Koopa 2) | 0.0063 | 0.0096 | 0.0001 | R |
| 520 | 801 | front | 0 / 11.3 | rear | 0.0258 | 0.0359 | 0.0004 | R |
| 530 | 818 | front | 0 / 14.3 | rear | 0.0286 | 0.0326 | 0.0004 | R |
| 536 | 829 | front | 0 / 16.5 | front (K3 now nearer) | 0.0309 | 0.0313 | 0.0004 | R |
| 545 | 845 | front | 0 / 22.3 | front | 0.0363 | 0.0363 | 0.0004 | R |
| 560 | 871 | front | 0 / 49.6 | front | 0.0621 | 0.0621 | 0.0004 | R |
| 567 | 883 | front | 0 / 106 | front | 0.1122 | 0.1122 | 0.0004 | L |
| 571 | 889 | front | 0 / 170 | front | 0.1808 | 0.1808 | 0.0004 | L |
REAR_EYE never chose a rear threat: Koopa 2 only recedes, so it is never "closing". REAR_SOUR (C-F): for the first 27 frames (f509-535) the nearest sour source is Koopa 2 behind (gap 56-80 px, theta 16-25 deg) instead of Koopa 3 ahead (gap 144-95 px); the sour level there is 1.48-2.11 against 0.80-1.22 for the front one in arm A, so MDN is up to +0.015 for those frames. After f535 Koopa 3 is nearer and the arms coincide to the last digit. Nothing changes in what he presses, so the scene cannot tell any arm from baseline.

### 4b. 1-1 dev set, 10 episodes (5 at sigma 0, 5 at sigma 0.05), `runs/RE2_holdout_<ARM>.json`
| arm | REAR_EYE | REAR_SOUR | flags | mean max_x | mean score | blocks / ep | back-up presses | rear-loom frames | A onsets caused by a rear threat | Left+A frames | deaths |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | off | off | **10/10** | 3161 | 2275 | 2.7 | 87 | 0 | 0 | 1134 | none; trajectory hashes = E1s (10/10 equal) |
| B | on | off | **10/10** | 3161 | 2275 | 2.7 | 87 | 341 | 0 | 1134 | none |
| C | off | honest | 8/10 | 2804 | 2165 | 2.7 | 90 | 0 | 0 | 1122 | ep 6 (sigma 0.05, seed 102) x 1529 "enemy dx=-18"; ep 7 (seed 103) stuck x 1219 |
| D | off | gated | 9/10 | 2967 | 1520 | 1.8 | 76 | 0 | 0 | 1061 | ep 8 (seed 104) stuck x 1220 |
| E | on | honest | 8/10 | 2804 | 2165 | 2.7 | 90 | 322 | 1 | 1122 | the same two as C |
| F | on | gated | 9/10 | 2967 | 1520 | 1.8 | 76 | 355 | 0 | 1061 | the same one as D |
The brief asked for B, E, F (flags must stay 10/10); C and D are there to separate the two features. **Flags are not kept by E (8/10) or F (9/10).** The loss comes from REAR_SOUR, not from REAR_EYE: C = E and D = F in flags, deaths and scores. B is 10/10 and identical to A in every outcome column; 7 of its 10 trajectory hashes differ from A (a rear Goomba is chosen for a few frames and the loom input differs for those frames), but the flags, max_x, score, causes and back-ups are the same.
- **Jumps caused by rear threats:** 0 in B (341 rear-loom frames), 0 in F (355), **1** in E (episode 7, frame 1137, x 1179): he has just landed between two Goombas and presses Left + A with the rear Goomba chosen at theta 127 deg (`clips/RE2_rear_jump.mp4`). It is a hop Left, not a rescue.
- **New stalls:** the dev set had none in A. C / E stall at x 1219 (ep 7) and D / F at x 1220 (ep 8); that is the old x 1220 hum + Goomba stall the E1s ablation had when the back-up was nearly off. What I saw in ep 7 (arm E, f1131-1145): the sour source is the Goomba **behind** him for 15 frames (`sour_rear` true), MDN 0.13-0.16, Left + A is held, and the front Goomba's sour drive is not what MDN is following. I did not trace the stall itself to the end, so "the rear source steals the sour drive from the Goomba ahead" is consistent with this window but not shown for the stall.
- **New death (C / E, ep 6, x 1529, "enemy dx=-18"):** in the air over a Goomba, MDN rises 0.10 -> 0.19 and Left is pressed for the last 3 frames of the descent; he lands on the Goomba beside/behind him. Arm A finishes this episode. Cause not analysed beyond the last 8 frames.
- REAR_SOUR also lowers the number of frames in view of "a source" being the front enemy: the rear source is the nearest in 6181-7011 of ~21,500-23,700 frames (about 28-32 %) because Goombas that he has just passed walk behind him for a long time. That is why it changes so much more than REAR_EYE.
- Gated costs score and blocks (1520, 1.8 blocks per episode vs 2275, 2.7): not investigated.
- Baseline fact for Arun (not a finding of RE2): arm A already has 1134 Left + A frames in 364 A onsets over 10 episodes (Left from the back-up or the steering, A from the jump); the Koopa scene has none (A frames 0). No rule was added for it.

### 4c. Full 1-2 (noop 0, sigma 0), arm B (the only rear arm that keeps 10/10 on 1-1), information only; `runs/RE2_12_<ARM>.json`
| arm | max_x | end | back-up frames / presses | rear-loom frames |
|---|---|---|---|---|
| A | 891 | died, enemy dx=8, 596 frames | 14 / 3 | 0 |
| B | 891 | died, enemy dx=8, 596 frames | 14 / 3 | 14 |
The same Koopa at x ~ 890 (the E1s 1-2 result). REAR_EYE was active for 14 frames and changed nothing.

## 5. Clips (R3 layout, `clips/` is gitignored; `python -m flyrun.re2_clips ...`)
- `clips/RE2_koopa_arms.mp4` (8.3 s, 0.5x, 1-2 scene from x 520): arm A against **arm E** (REAR_EYE + honest REAR_SOUR). All six arms tie, so there is no "best arm"; I show E because it is the one with both ticks. The two sides play the same game: the only visible difference is the yellow dotted box + "behind" tick on Koopa 2 for 27 frames on the right, and 0.01 more MDN.
- `clips/RE2_rear_jump.mp4` (6.4 s, 0.5x, 1-1 dev episode 7, arm E, from frame 987): the one rear-loom jump found (frame 1137): red box + red "behind" tick on the Goomba behind him, yellow dotted box + tick (same Goomba is the sour source), Left + A. The brief said "if any happens on 1-1": it happened once, in an arm that fails the flag check.

## 6. What this does not show
- The scene does not test either feature: nothing ever closes from behind there, and the one rear sour enemy is farther than the front one by f536. I did not build a synthetic rear-approach scene (outside the brief); the rear-loom behaviour is shown only by the unit tests with the real brain and by the 1-1 frames above.
- Nothing was evolved: the genome is the E1s champion; REAR_SOUR changes the sour source of ~30 % of frames and the genome was not re-fitted to it, so the 8/10 and 9/10 are "added to an old genome", not "the best this feature can do".
- The dev set is no longer held out (AUDIT.md §3); a pass here would not have been evidence of generalisation, and B's 10/10 is only "no regression on the same 10 episodes".
- Orange (invented) additions in this part: the REAR_EYE closing rule, REAR_SOUR_MODE gated, the "behind" ticks are rendering only. Teal: nothing new; the wiring is unchanged (LC4 / LPLC2 -> GF -> TTMn, DC4 -> MDN).
