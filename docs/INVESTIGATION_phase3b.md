# INVESTIGATION phase 3b: the short hop (investigator, 2026-10-04; nothing changed, tuned or evaluated on game outcomes)

Scripts (audit/, gitignored): p3b_jump_curve.py, p3b_jump_patterns.py (a); p3b_arun.py, p3b_why.py (c, brain-only, stored open-loop traces p3d_loom_e1_N200_manyseed.json = network 3848f3e70b2051ef, noise seeds 0-199, calibration.json a_thr 0.13229, decay 0.9); p3b_closed.py + p3b_closed_an.py (closed-loop diagnostic on UNUSED seeds 6000-6029; only A runs, TTMn and theta read, no outcome used for anything).

## 1. Answer
(a) In SMB the jump is variable-height and the height is set only by the length of the CONTIGUOUS A run starting on the takeoff frame: 1 frame gives 24 px apex / ~17 frames airtime, +3 px per extra frame up to about 6, then ~+1-2 px per frame, saturating at 64 px / 43 frames for a hold of >=24 frames. A re-press after release does nothing. The game has no "jump" event; a one-frame tap is the minimum hop.
(b) The biology says the opposite of a held button: a GF spike gives one TTMn/TTM spike (1:1 up to 300 Hz in the prep) and escape leg extension is a stereotyped ~3.3 ms event (IQR 0.46). 3.3 ms is 0.2 of a 16.7 ms frame, so the faithful game equivalent of one GF spike is a one-frame press. Hold length as height control has NO biological counterpart; it is an SMB artefact.
(c) Brain-only (200 seeds) the first A run is 1 frame in 22%, <=2 in 30%, bimodal (median 11, but truncated by the 125-frame trace); closed loop (30 unused seeds) <=2 in 37% (median 4, max 8). 9/20 (45%) on 3200-3219 is compatible with 30-37% (P(>=9 of 20 | 0.30) = 0.11; | 0.37 = 0.30). Cause of taps: the threshold sits on the single-spike upstroke (below), and in closed loop the loom collapses ~3 frames after takeoff, cutting the burst short.
(d) No honest derived route to a hold length exists. Options below; I recommend D (leave the motor map) plus a decision by Arun on whether the tool declares the hop-height mapping an actuator convention.

## 2. Evidence
| claim | data or source | confidence |
|---|---|---|
| Height vs hold (small Mario, 1-1 flat, standstill; also identical with Right held) | audit/p3b_jump_curve.py. hold n -> apex px / airtime frames: 1:24/17, 2:27/19, 3:30/20, 5:36/23, 8:44/26, 10:48/29, 15:57/34, 20:62/39, 23:64/41, >=24:64/42-43 (no change up to 60) | measured, high |
| Mechanism | RAM 0x0709 (vertical force) = 48 while A held and rising, = 168 from the first frame after release (hold 1: 168 from frame 2; hold 30: 168 from frame ~14, the apex of the held arc at vy=0) ; 0x009F vy -5 at launch both cases | measured, high; reading as "variable-jump gravity" is mine |
| Re-press does not recover height | patterns [1,0,1]: 24 px; [1,0]+10 held: 24; [1]+gap5+10 held: 24; 3+gap1+3: 30 (=3 contiguous); 8+gap2+8: 44 (=8 contiguous) | measured, high |
| Minimum hop | hold 1 = 24 px, 17-18 frames; hold 0 = no jump (airtime 5 = settling only) | measured, high |
| Game geometry of the tap deaths | Goomba closes ~0.6 px/frame (dx 22 at f109 -> 11 at f127, p3b_closed rows); 17-frame hop lands with dx ~9-11 inside the 16 px contact box, consistent with NOTE_e1_regression | measured, high |
| GF single spike drives TTM; 1:1 following | Allen & Godenschwege, Cold Spring Harb Protoc 2010 pdb.prot5453 (PMC2946074): "~0.8 ms after GF activation", 1:1 "up to 300 Hz"; Augustin et al., eNeuro 2019 (PMC6469880): "a single AP in a GF axon is sufficient to initiate patterned activity in jump and flight muscles", TTM latency 0.93 ms model | full-text fetch of both pages, high (the quoted 1:1 claim is the protocol's, not primary data) |
| Tanouye & Wyman 1980 / King & Wyman 1980 (GF-TTMn-TTM physiology and anatomy) | cited by the above for the pathway | cited secondhand; primary papers not read; from memory for details |
| Short vs long mode | von Reyn et al., Nat Neurosci 17:962-970 (2014), doi 10.1038/nn.3741, "A spike-timing mechanism for action selection": loom gives either a long-duration sequence with stable flight or a short-duration sequence; GF spike timing relative to parallel circuits picks which; GF has the higher threshold and can override to force a short takeoff | abstract verified (Europe PMC + secondary summary); full text not read |
| Non-GF "voluntary" mode exists and is slower and more variable | Card & Dickinson, J Exp Biol 211:341-353 (2008), "Performance trade-offs in the flight initiation of Drosophila": escape is stereotyped and GF-mediated, voluntary can occur without GF. Table 1 (via fetch): leg extension 3.3 ms (IQR 0.46) escape vs 5.5 ms (IQR 2.0) voluntary; wing-leg interval 1.0 vs 34.8 ms; escape latency median 190.7 ms | abstract verified; Table numbers from a fetch summariser of the full text, medium (check against the PDF before citing) |
| Pre-jump posture is not a fixed program | Card & Dickinson, Curr Biol 18:1300-1307 (2008): ~200 ms before takeoff postural adjustments depend on initial posture, "not the result of a simple feed-forward motor program" | abstract verified |
| Is GF active in some long-mode takeoffs? | a search summary says yes; I did not see it in an abstract | unverified, do not cite |
| TTM contraction duration / force vs spike count | no source found; the TDT mechanics papers surfaced give shortening velocity and tension, not twitch time | absent; no calibration target exists |
| First-run distribution, brain-only, 200 seeds | length 1:44, 2:16, 3:5, 4:4, 5:2, 6:2, 7:4, 8:2, 9:3, 10:10, 11:14, 12:28, 13:33, 14:29, 15:4; <=2 = 0.30; never = 0; runs of 10-15 are cut by the 125-frame trace end | measured, high; long runs truncated |
| Why taps: the threshold is a one-spike quantity | largest single-frame TTMn rise GF-1..GF+5: median 0.108 (p10 0.060, p90 0.122) vs a_thr 0.1323: a single upstroke reaches threshold in only 3.5% of seeds; crossing needs two consecutive rises and the crossing drive is then 0.141 (taps) vs 0.174 (long); 82% of taps cross at drive < a_thr/decay = 0.147, i.e. one frame without a new rise releases A; for 13% of long runs likewise | measured, high |
| TTMn alternates (GF refractory) | aligned median pooled/side-max TTMn GF-1..GF+9: 0.006 0.095 0.064 0.098 0.12 0.127 0.137 0.156 0.176 0.183 0.188 (p10 dips to 0.008 at +2) | measured, high |
| a_thr is 0.50 x the weakest disc peak 0.2646 (lv 80) | calibration.json; in the E1 approach the same drive peaks at median 0.212 (p10 0.178), so the threshold is 0.62 of the E1 peak | measured, high |
| Closed loop truncates the burst | Mario rising ~10 px makes the Goomba's elevation weight (1 - elev/limit, brain/perception.py) fall: theta 45.7 deg at takeoff -> 35.5 -> 24.8 -> 17.2 -> 0 within 5 frames (open loop would continue 47.9 -> 67 deg); TTMn pooled falls to 0.01 by +4 frames; first run median 4, max 8 vs 11 open loop | measured (seeds 6000-6029), high |
| Closed-loop first-run distribution on 6000-6029 | 1:8, 2:3, 4:5, 5:5, 6:2, 7:6, 8:1; <=2 = 11/30 = 0.37 | measured, n=30 |
| Sensitivity (open loop, tap<=2 vs decay x a_thr) | decay 0.9: 0.14 @0.08, 0.20 @0.10, 0.46 @0.115, 0.32 @0.13, 0.30 @0.1323, 0.40 @0.15; decay 0.95: 0.01, 0.06, 0.09, 0.26, 0.24, 0.06; decay 0.97: <=0.12 all. Same rule scaled 0.5 x peak: decay 0.9 -> 0.30, 0.95 -> 0.14, 0.97 -> 0.05 | measured; non-monotone, so a threshold cannot be chosen from it |

## 3. Options (none implemented)
| option | changes | rule 8 | new invented scalars | risks | synthetic validation |
|---|---|---|---|---|---|
| A. N-frame twitch per GF spike | A = N frames after each GF spike; independent of TTMn ripple | borderline: the trigger is the fly, the duration is code (same class as the counted "mechanical hold durations"); a fixed hold length is closest to a forced hold | 1 (N) | biology gives ~3.3 ms, i.e. N=1; any N>1 is an SMB-side artefact with no source; fires on every GF spike, removes the shuffled/lesion contrast on A shape | brain-only: A-run distribution = N by construction (trivial); check rest false presses = 0 and GF-lesion arm = 0 |
| B. longer integrator (MUSCLE_DECAY 0.95) | holds persist across TTMn dips; open-loop tap fraction 0.14 (0.05 at 0.97) with the same 0.5 x peak rule | compliant (low pass in the actuator) | 0 (re-values an invented one) | tau 10 -> 20 frames has no cited basis (no TTM twitch data); also lengthens holds after the loom has collapsed, so hops get taller for a reason the fly did not "decide"; re-derives a_thr, goldens | brain-only replay on disc lv 20/40/80 and E1 theta; rest max drive vs a_thr; shuffled arm A fraction |
| C. re-derive A_FRACTION/a_thr | moves the threshold off the one-spike level (e.g. above the single-rise ceiling or well below it) | compliant if derived by a rule stated before the run | 0-1 | non-monotone tap curve (0.14-0.46 over 0.08-0.115); any choice made to lower taps is tuning on the symptom | rule must come from stated structure (e.g. a fraction of the single-spike rise, 0.108 median), validated on rest false-press rate and disc peaks only |
| D'. hold from a derived relation | hold ~ number of TTMn spikes (muscle force summation) | compliant if the mapping is read from the fly | >=1 (slope) | no source gives twitch summation or force vs spike count; the present leaky integral is already this mapping, with an invented tau | none possible without a source |
| E. leave it | report 13-16/20 as the model's honest output; state that SMB's hold-height coding has no fly counterpart | compliant | 0 | E1 criterion >=16 stays marginal (16/20 on 3200-3219) | n/a |

## 4. What this means for the plan
- Settles: the tap is not a bug in the circuit; it is the faithful reading of a ballistic, ~3 ms twitch through a game that codes height as a hold. It argues against inventing a hold law (D3-style mechanical hold durations) and sharpens D-rule-8: option A is the only one that is biologically motivated and it still carries an invented N.
- Enables: the A threshold can be reported as "the single-spike level" and the tap fraction as an expected property (about 0.3-0.4), not a defect.
- Rules out: calibrating a hold-length mapping to a literature value (none exists) or tuning decay/threshold to the E1 survival rate.
- Closed loop self-truncates the burst through the elevation weighting; any integrator change interacts with that.

## 5. Open questions
1. Table 1 numbers (3.3 / 5.5 ms) should be checked against the PDF; they came through a fetch summariser.
2. Do real flies emit more than one GF spike in a loom escape? Not established here (von Reyn full text not read). In the model the GF fires repeatedly (ISI mostly 1 frame, median 14 spikes in 35 frames open loop); real single-spike behaviour would make "N GF spikes = hold" an unfaithful lever.
3. Does the closed-loop truncation (theta -> 0 as Mario rises) have a biological analogue worth keeping, or is it an artefact of the elevation weight? It drives the closed-loop tap rate.
4. Closed-loop n=30 on seeds 6000-6029 is a diagnostic only; the 0.37 vs 0.30 difference is not resolved.

## 6. Decision for Arun
Choose whether the tool's "A" is (i) a literal button read from the TTMn integrator with its invented tau (status quo, option E; admit hop height is an unmodelled game artefact and accept E1 marginal), or (ii) a declared actuator convention "one GF spike = N-frame press" (option A) with N as one counted invented scalar and a documented rule-8 exception. I recommend (i). I do not recommend B or C as fixes for survival: neither has a biological target, and both would be chosen against the thing they are meant to improve.

## Decision (Arun), 2026-10-04
- Option E accepted: the status quo. "A" stays a literal button read from the TTMn integrator; no hold law, no integrator or threshold change.
- The A-tap fraction (about 0.3-0.4 of episodes with a first A run of <= 2 frames) is recorded as an expected property of the motor map, not a defect.
- "One GF spike = N-frame press" (option A) is noted as a possible FUTURE decision. It is not adopted, and no scalar N is added.
