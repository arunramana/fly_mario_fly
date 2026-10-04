# NOTE: why E1 real fell from 18/20 to 13/20 (investigator, 2026-10-04; diagnosis only, nothing tuned or changed)

Scripts: audit/p3d_*.py (replay, loom, peak, 2x2). Old = network 4736dc554136ac98 + git HEAD calibration.json; new = 3848f3e70b2051ef + working-tree one.
Seeds 3000-3019 are a REPLAY of already-used seeds. Brain-only studies use noise seeds 0-199 on synthetic/recorded stimuli, never game seeds. 3100-3119 untouched.

## Finding (3 lines)
The deaths are not caused by the network or by LC10a. The A threshold (A_FRACTION x weakest disc's peak muscle drive) was derived from ONE noise seed
per disc; that seed gave a weakest-disc peak 7% lower on the new network, so a_threshold fell 0.1332 -> 0.1236. That value sits on the first TTMn upstroke
(0.11-0.13), so A is now pressed on a single frame and released before the TTMn burst builds: a minimum hop that lands with the Goomba 9-11 px away.

## Evidence (measured unless marked)
| claim | data | conf |
|---|---|---|
| Replay reproduces the records | old 18/20, new 13/20; survived, contact, first-GF, A frames, length identical to p2_e1_eval.json / p3_e1.json in 20/20 each | high |
| GF is not the difference | first GF frame median 110 vs 111; theta 38.4-43.6 vs 40.0-43.6; GF out max 9-18 Hz old, 6-15 Hz new (mostly 12) | high |
| TTMn amplitude unchanged | closed loop median TTMn side-max 0.341 vs 0.334; open loop (E1 approach theta, 200 noise seeds) 0.279 vs 0.286 (sd 0.02); rest mean 0.00646 vs 0.00643, max 0.0141 vs 0.0140 | high |
| TTMn wiring unchanged | 2 cells, 92 in-edges (42 exc, 50 inh) both nets; in-network input 2032/918 both; GF->TTMn W 0.034/0.022 both; 0 new->TTMn edges | high |
| LC10a is not acting | zeroing all LC10a output edges in the new net gives BIT-IDENTICAL TTMn traces (40 seeds E1, 30 seeds x 3 discs); no pursuit/landmark attached in E1 | high |
| Network did change upstream | +913 neurons (270 LC10a, 207 LC10d, ...), 568,527 edges among old neurons unchanged, +44,039 new; 2,397 old neurons' input normalisation changed (898 by >10%); 350 of 1,334 2-hop predecessors of TTMn | high (but no measurable output effect) |
| Recalibration | g 0.85 both (rho 1.000); gf_thr 0.16801 -> 0.16736 (-0.4%); walk .01709->.01688, steer .01093->.01098, back .01389->.01400; muscle_decay 0.9 both; a_thr 0.13318 -> 0.12359 (-7.2%) | high |
| a_thr change is calibration noise | peak drive lv80 seed 0: old 0.2664, new 0.2472 (harness reproduces calibration.json exactly); 30-seed mean 0.2624 vs 0.2714, sd 0.021-0.026; the same rule on 30-seed means gives 0.1312 vs 0.1357 (new HIGHER) | high |
| Threshold, not network, moves the taps | E1 approach, 200 seeds, first A run <=2 frames: old/0.1332 29%, new/0.1332 27%, old/0.1236 44%, new/0.1236 42% | high (brain-only) |
| Closed-loop signature | all 9 deaths (2 old, 7 new): first A press is 1 frame and takeoff <= frame 114, apex 152 (24 px) every time, landing 127-130, Goomba dx 9-11. 9/10 episodes with that signature died (one re-jumped); 0/30 others died. Taps at takeoff: old 4/20, new 10/20 | high (descriptive; the "<=114" split is post hoc) |
| Mechanism of the tap | TTMn trace alternates (0.12, 0.01-0.05, 0.12 ...: GF refractory); drive after one upstroke 0.113-0.124 vs thr 0.1236 (e.g. new 3004: 0.124 press, 0.111 release, 0.195 press) | high |
| "A held 4-9 vs 11-20" is confounded | total A includes a SECOND run of 8-13 frames at frame 144-155 in every survivor; deaths end at frame 130 and cannot have it. First-run length does not separate (new deaths 5-7 contiguous after the tap, survivors 1-7) | high |
| Why a one-frame tap is a minimal hop | SMB variable jump height by A hold; re-pressing after a 1-frame gap did not raise the apex (152 in all 9) | measured apex; the rule is inferred / from memory |
| Not like-for-like noise | same RNG seed but 15,551 vs 16,464 neurons, so different per-neuron draws; per-seed pairing in the table is not a paired test | high |

## Measured vs inferred
Measured: everything above marked high. Inferred: that the hop is short because the release follows one frame later (SMB physics not read from the ROM); that Phase 2's 18/20 was a favourable calibration draw (the old a_thr 0.1332 is near the 30-seed value 0.1312, so it was the "right" one by luck).
Caution: the tap fraction is NON-monotone in the threshold (decay 0.9: 0.34 at 0.115, 0.39 at 0.1236, 0.23 at 0.1332, 0.20 at 0.1357, 0.36 at 0.16). Do not pick a threshold from this; it shows how fragile the rule is.

## Options for the short hop (none implemented)
| option | changes | rule 8 (fly controls, code perceives) | new scalar | risks |
|---|---|---|---|---|
| A. Fixed-duration twitch per GF spike (A held N frames after a GF spike) | A no longer reads the TTMn ripple; every GF spike = same hop. Bio: GF -> TTMn -> TTM is a stereotyped short sequence (von Reyn 2014 Nat Neurosci 17:962: GF drives the short-duration takeoff, abstract verified; TTM 1:1 following of GF spikes, Tanouye & Wyman 1980 / King & Wyman 1980, FROM MEMORY; Card & Dickinson 2008 Curr Biol 18:1300 abstract says pre-jump posture is NOT a simple feed-forward program, so stereotypy is a short-mode claim only) | Borderline: the trigger is the fly's GF, the duration is code. Same class as "mechanical hold durations" already counted; Arun to decide whether it is an actuator model or a forced hold (docs/CONTROL_AUDIT.md) | 1 (N frames), invented | No source gives N in game frames; real twitch is ms, a hop-height hold is an SMB artefact, so N is a game-side pick and would be tuned on E1 geometry. Fires on every GF spike (post-stomp bursts too). Removes the TTMn ripple dependence, and with it the shuffled/lesion contrast on A shape |
| B. Longer TTMn integrator (MUSCLE_DECAY 0.9 -> ~0.95) | Drive stays above thr through the dip frame; at 0.95 tap fraction 0.08-0.2 across thr 0.115-0.16 (brain-only, flatter than at 0.9) | Compliant (pure actuator low-pass, already in the motor map) | 0 new (changes a registered invented value) | Re-derive a_thr, rest checks, goldens; tau 10 -> 20 frames has no cited basis; longer holds after every burst |
| C. Re-derive a_thr by the SAME rule with K noise seeds (median of peaks) instead of seed 0 | Removes the calibration noise that caused this (0.1357 on new). A_FRACTION stays 0.5 | Compliant (synthetic derivation only) | 1 (K), measured/convention | Does not fix the ripple fragility (tap fraction ~0.2 remains at 0.1332-0.1357); must not choose A_FRACTION to maximise E1. Needs re-run of E1 on FRESH seeds |
| D. Leave it | Report 13/20 with this diagnosis, criterion >= 16 stays FAIL on this network | Compliant | 0 | The 18 -> 13 swing is a calibration-draw effect of about 2 vs 7 deaths in 20; any E1 number on this rule carries it |

## Open questions
1. Is a_thr in other calibrations (walk/steer/back derive from 2000-frame rest runs, so far less noisy) also seed-fragile? Not measured here.
2. SMB hop height vs A-hold curve read from the game, not inferred from 40 episodes.
3. Does A (one frame tap) happen in E0/E3? A frame share there was 0 (real), so no.
