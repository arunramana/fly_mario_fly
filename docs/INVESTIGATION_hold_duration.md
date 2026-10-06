# INVESTIGATION: what sets the A hold duration (Phase 6, investigator, 2026-10-06)

Read-only. No code, config, calibration, motor map or test changed; no new scalar. Scratch: `audit/p17h_*.py` (gitignored). Network 3848f3e70b2051ef, `brain/calibration.json` as committed (a_thr 0.13229, decay 0.9, g 0.85). Only non-eval seeds 9300-9399, `.venv`, 3 workers. Closed-loop replays: E1 real 100 (9300-9399), E1 class shuffle 30, E1 degree shuffle 20, E2a (pipe 1) real 100, E2a class 20, B11 real 20 (9300-9319, pipe 2/3). A per-frame logger wraps `MotorMap.read` in the worker process only. Tags: [M] measured here, [I] inferred, [L-v] literature verified (level stated), [L-m] from memory.
Survival was not used to choose or tune anything. The two threshold sweeps (section Q2) record A-run lengths only.

## Answer (verdicts)
1. **Mechanism [M].** `drive_t = 0.9*drive_{t-1} + max(0, TTMn_t - TTMn_{t-1})`, `TTMn = max(left, right)` single-cell activity, `A = drive >= 0.1323`. A is held by the integral's memory, not by TTMn: in a long hold TTMn is back at rest (0.005) for 8-10 of the 12 frames. Hold ~ 2-3 rise frames + 9.5*ln(peak/thr) frames (tail share corr 0.99 with length; predicts length exactly in 66%, within 1 frame in 88%, E1). The drive stops growing when TTMn stops rising: in E1 (Goomba) because theta collapses ~3 frames after take-off (elevation weight) and the GF burst ends; in E2a (pipe) theta keeps growing, the GF fires 11 frames in a row and the drive keeps climbing.
2. **Bimodality is partly stimulus regime, partly a threshold-crossing cliff of the rule [M].** E1 first runs are graded 1-10 (not bimodal); the 11-14-frame holds are SECOND presses made on the ground with the Goomba touching (theta 157 deg, TTMn 0.4, drive peak 0.35-0.5). In E2a the cliff is real: 21 one-frame taps, 78 holds of 10-15, one run between. Moving a_thr by 5% in closed loop changes the first-run tap share from 40% to 5% (x0.95) or leaves 54/100 episodes with no A press at all (x1.05).
3. **No connectome route to a graded or sustained hold [M + L-v].** PSI, DLMn, DVMn, GFC2 and the non-GF loom descending neurons all follow the TTMn burst within 0 frames, or carry no signal beyond random wiring. The hold length is set by an invented motor-map rule (decay 0.9, A_FRACTION 0.5) with no connectome backing.
Decision for Arun: fix the rule vs accept a ceiling (end of document).

## Q1. Trace of what presses and releases A (E1 real, seeds 9308 tap, 9302 mid, 9300 long; frame 0 = first A frame)
| case | GF | TTMn (side max) per frame | rise | drive | A | theta deg |
|---|---|---|---|---|---|---|
| Tap, L=1 (9308) | spikes -2..2 | .120 .131 **.164** .152 .146 .022 .006 | .117 .011 .033 0 0 | .124 .123 **.144** .130 .117 .105 .095 | 0 0 1 0 0 0 | 45 45 49 49 30 12 3 |
| Mid, L=6 (9302) | -1..1 | .039 .160 .113 .179 .012 .006 | .032 .121 0 .066 0 | .040 .157 .142 .193 .174 .157 .141 .129 .116 | 1,1,1,1,1,1,0 | 42 45 45 29 14 5 0 |
| Long, L=12 (9300, 2nd press) | 0..3 | .256 .414 .369 .219 .016 .004 .005... | .250 .158 0 0 0 | .263 .394 .355 .319 .287 .259 .235 ... .142 .127 | 1 x12 then 0 | 157 157 0 0 |
- The single GF upstroke gives rise 0.11-0.12 and drive 0.124 (below thr 0.1323 by 6%). Threshold is crossed only if a second rise follows (+0.03 in the tap, +0.12 in the mid case). [M]
- E1 first-run theta (median, deg, offsets -3..8 around the first A frame): 39 42 45 45 49 29 13 3 0 0 0 0; GF spike fraction 0.32 0.65 0.76 0.92 0.96 0.94 0.23 0 0...; Mario's y falls 5 px/frame from offset 1. The GF burst therefore lasts ~3 frames after A starts: closed-loop shortening through the elevation weight. [M]
- Near-regime burst (second press): GF membrane 0.163 (at threshold) vs far-regime 0.167 (equal), but TTMn 0.41 vs 0.16: drive at the sensory tier is theta 157 deg vs 45 deg (rad read as Hz). TTMn amplitude follows the stimulus through the circuit [I; GF output rate not logged].
- E2a (pipe 1, 9301, L=12): GF spikes every frame from offset -3 to 8; TTMn climbs .126 -> .384 while theta climbs 47 -> 116 deg; drive 0.19-0.23 for 8 frames, then decays 0.168 -> 0.124 over 4 frames (release at offset 12, TTMn at rest since offset 9). [M]
- Hold vs peak drive (all 203 E1 runs): peak .13-.15 -> L 1 (median; n 46); .15-.17 -> 3 (31); .17-.20 -> 5 (26); .20-.26 -> 7 (12); gap .26-.34 (5 runs); .34-.5 -> 12 (83). [M]

## Q2. Bimodality
| claim | data | conf |
|---|---|---|
| E1 first-run hist (n=100): 1:32 2:8 3:17 4:16 5:12 6:7 7:5 9:2 10:1. All runs: <=2 68, 3-6 62, 7-9 7, 9-13 64 | `p17h_e1_real.json` | M |
| Long holds in E1 = second run (median 12, theta 157 deg, ground start 100%); none among 35 deaths; 58 of 65 survivors | crosstab L1>=10 vs survived | M (descriptive, not used to tune) |
| E1 survival by first-run length: <=2 16/40, 3-6 41/52, >=7 8/8; 7 survivors had no long hold (stomped) | same | M |
| E2a first runs (n=100): 1:20 2:1 3:1 10:2 11:8 12:26 13:26 14:15 15:1; peak .13-.145 (21) vs .2-.31 (78) | `p17h_e2a_real.json` | M |
| Tap mechanism: drive at crossing 0.133-0.144 (median 0.137, +3.5% over thr); next frame 0.9*d0 + rise: tap d1 median 0.126, hold d1 0.157; taps have TTMn flat (0.130, 0.130, 0.136), holds have a second rise | E2a | M |
| E1: 82% of taps cross at drive < thr/0.9; tap d0 median 0.142 (+7%) | E1 | M |
| Closed-loop sweep E1, a_thr x0.95: first run <=2 5%, 3-9 32%, >=10 63% (median ~12); x1.00: 40/59/1; x1.05: only 46/100 episodes press A at all, 76% of those <=2 | `p17h_sw095/105.json` (A lengths only) | M |
| Offline recompute on recorded TTMn (counterfactual, drive rule exact at x1.00): E1 tap share .28/.29/.34/.40/.43/.49/.51 at x0.90/.95/.98/1/1.02/1.05/1.10; E2a .42/.31/.27/.21/.16/.15/.16 (non-monotone: a lower thr crosses on the first single rise and releases). Decay 0.85: E2a 3-9 band fills to 43%; 0.95: E1 >=10 52% | `p17h_off.py` | M (open loop understates the closed-loop swing) |
| Class shuffle E1: first runs 1:1 3:2 4:1 5:4 6:2 7:1 8:3 9:3 10:5 11:4 12:2 14:1 16:1; all runs up to 21; peak drive up to 0.86; 24/30 survive. Degree shuffle: 0/20 survive, no A run (GF never fires) | `p17h_e1_class/deg.json` | M |
- Verdict: the tap/hold cut is a **threshold-crossing artefact of the rule** (crossing margin 3-7%, a 5% change in a_thr is a regime change in closed loop; a_thr itself moved 7% between two calibration draws in NOTE_e1_regression). The *amplitude* of the TTMn response is the circuit's (the class shuffle on the same rule is graded, first-run median 9 vs 3 frames, 3% taps vs 40%), so the circuit sets how far above thr the drive goes; the rule sets the cliff.
- B11 pipe 2 (9300-9319), ground presses at x 528-549: first hold >=12 cleared pipe 2 in 7/7 (15,12,17,16,16,18,16); hold <=9 in 0/13 (1,1,1,1,1,1,2,2,3,5,6,6,9). Pipe-2 stalls 13/20 here vs 8/20 on 6500-6519 [M, sampling]. Pipe 3: presses occur at the wall (x 722); 2 clears (L 21, 32), not hold-only: timing confounds (stall doc).
- **New, B11 wall latch [M].** At pipe 2 (x 594) all 13 stuck episodes have GF firing 100% and TTMn 0.474 (saturated) for the last 100 frames; A is held 100% of frames in 7 (runs 274-318 frames, no fresh edge) and 0% in 6. A reads TTMn *rises*, so at saturation it is decided by a 0.06 ripple, not by the level; neither state can make a fresh jump. The model GF fires 300 times in a row; real GF is one spike per loom (von Reyn 2014, abstract [L-v]).

## Q3. Does the connectome support a graded or longer hold?
**Reconciliation, DLMn.** Phase 0 was a naming miss: it searched type "DLMn" (0 rows, query `type == 'DLMn'`). The annotations call them "DLMn a, b" (2) and "DLMn c-f" (8). Phase 6 is right. Now true [M, `mcns.load_annotations`, `p17h_ann.py`, `p17h_nt.py`]:
| type (superclass) | n (L/R) | in committed net | consensus_nt | GF -> (chem syn, edges >= 2) |
|---|---|---|---|---|
| DNp01 GF | 2 (1/1) | 2 | ACh | - |
| TTMn (vnc_motor) | 2 (1/1) | 2 | glutamate | 90 (1.3% of its input) |
| PSI (vnc_efferent) | 2 (1/1) | 2 | unclear | 16 (0.13%) |
| DLMn a,b / c-f | 2 + 8 = 10 (5/5) | 0 | unclear | 0 direct; 2 hops via IN18B034, GFC2, PSI |
| DVMn 1a-c / 2 / 3 | 14 (7/7) | 0 | glutamate/unclear | 4 |
| GFC1 / GFC2 / GFC3 / GFC4 | 3 / 10 / 13 / 8 | 1 / 7 / 0 / 0 | ACh (GFC2-4, conf 0.96) | 11 / 144 / 96 / 112 |
| STTMm 4, hDVM MN 2, wing steering+power MNs 36 (18 types x 2) | | 0 | unclear | 0 |
- Correction to Phase 6: **GFC2/3/4 are cholinergic (consensus_nt, 0.96), not "unclear".** GFC2 (7 of 10 in the net) therefore carries real weight: GF -> GFC2 144 syn, GFC2 -> TTMn 481 syn (7.1% of TTMn input), GFC2 -> DLMn 781, GFC2 -> GFC2 1,084 (79 edges). (An error in my first pass of the nt query was caught and rerun: the tallies above are the second pass.) PSI and the motor neurons stay "unclear" (sign 0, their outputs are dropped; irrelevant for a read-out cell). GFC1-4 are electrically coupled to the GF [L-v: Kennedy & Broadie 2018 eNeuro, fetched; the paper gives no takeoff function and says GFC optogenetic activation gave no behaviour]; electrical coupling is not in W.
- DLMn/DVMn are not in the committed network; they are probe-only (Phase 6 probe C). Duration, re-measured with seeds 9300-9302 (real) and 5+5 shuffles: frames between half-max end of the TTMn burst and of DLMn c-f / DVMn = 0.0 (range 0) real, 0.0 (-1..0) class shuffle; DLMn a,b -0.3; PSI -1 to -2. Half-max widths: TTMn 3 / 7 / 12.7 frames (discs 20/40/80), DLMn c-f identical. Degree shuffle: GF never spikes in 20/20 runs, so there is no burst to compare. Class shuffle: bursts longer (TTMn 4 / 8.6 / 16.8) and DLMn tracks them identically. [M]
- Committed net (GFC2 and non-GF loom DNs measured, discs 20/40/80, real): half-max width TTMn 2.7/4.3/6.0, GFC2 2.0/4.3/7.7, DNp06 2.0/3.0/5.7, DNp03 2.0/3.0/5.0: GFC2 tracks TTMn, none outlasts it. With the GF lesioned TTMn rises only to 0.012 Hz (rest 0.0065) while DNp04/DNp03/DNp06 respond at 1.1/0.37/0.29 Hz: the non-GF loom DNs reach the circuit but give TTMn almost nothing in this net. Degree shuffle: all cells x5-8 baseline, no GF spike; class shuffle: GFC2 x8-12 vs TTMn x85-99. [M]
- Anatomical parallel route: LC4/LPLC2 -> non-GF DNs (all 2 cells each, in net, ACh) -> premotor: DNp03 -> DLMn 526 / DVMn 84 syn; DNp06 -> GFC 391, PSI 83, TTMn 53; DNp103 -> GFC 269, PSI 94; DNp02 -> TTMn 26. Total non-GF DN -> {TTMn, DLMn, DVMn, GFC, PSI} 15,779 syn vs GF 473 [M, edges >= 2]. This matches the literature's parallel pathways: GF-independent visually guided escape (Fotowat 2009 J Neurophysiol 102:875, abstract [L-v]); GF spike timing against parallel circuits picks short vs long takeoff (von Reyn 2014 Nat Neurosci 17:962 [L-v abstract]; single-spike timing, von Reyn 2017 Neuron and Ache 2019 Curr Biol 29:1073 [L-v abstracts]); voluntary takeoff slower, better posture (Card & Dickinson 2008 [L-v abstract]); GF -> TTMn and GF -> PSI -> DLMn (Allen & Godenschwege 2010 [L-v, Phase 6]; Namiki 2018 eLife 7:e34272 for the DN map [L-v existence, content not read]). So the anatomy for a *different* takeoff exists. But no source maps either mode to a duration of leg extension that a held button could express: GF leg extension ~3.3 ms (Card & Dickinson Table via summariser, medium); TTM twitch duration vs spike count: no source found.
- Not verified: "Azevedo 2020 Parallel pathways for takeoff" and "Sen 2017 on GF-PSI": searches returned no such papers; not used. Tanouye & Wyman 1980 1:1 following: [L-m].
- **Plainly: there is no honest connectome-derived route to a graded or sustained hold in this model.** The wing/DLMn side tracks the TTMn burst within 0 frames; the non-GF DNs carry signal but no TTMn drive; the only graded quantity is TTMn amplitude, turned into frames by the invented decay (tau 9.5 frames) and a_thr (0.5 x the weakest calibration disc peak). Hold duration is set by an invented motor-map rule with no connectome backing.

## What this settles
- Symptoms 1-3 share one cause: hold = f(first-burst TTMn amplitude, a_thr, decay). E1 deaths: first hop of 1-6 frames; E2a/pipe 2: tap or hold >=10 by the crossing cliff (hold >=12 cleared pipe 2 7/7, <=9 0/13); pipe 3 is also timing and the wall latch.
- Rules out: choosing decay/a_thr to raise E1 (no biological target; 5% moves taps 5%-50%); a wing/DLMn muscle readout as a hold source.

## Options for Arun (none implemented)
| option | what | rule 8 | new scalar | note |
|---|---|---|---|---|
| A. Accept a ceiling | report E1/pipe 2-3 as hold-lottery limited; state hop height as an unmodelled SMB artefact | ok | 0 | pipe 3 (needs >=10-12) and E1 >=16 stay unreachable by design |
| B. Make the rule robust | a_thr by K-seed median, or from the single-spike rise (0.11-0.12), not 0.5 x weakest disc | ok | 0-1 | removes calibration noise, not the cliff; the 5% sensitivity is structural |
| C. Level readout | A = TTMn level above a rest-derived threshold (like walk/steer), no integral | ok | 0 invented (REST_Z exists); drops decay | hold = burst length 3-12 frames, not decayed; at the wall TTMn is saturated so A would latch on in 13/13 stalls (worse for fresh edges) |
| D. N-frame twitch per GF spike | A held N frames after a GF spike | borderline | 1 (N) | no source for N; fires on every GF spike |
| E. Fix the stimulus side | e.g. stop continuous GF firing (adaptation, matches one real spike) | ok if biological | 0-1 | changes the network dynamics; needs recalibration and a new hash |
Decision: fix the rule (B-E, each with a cost above) vs accept a ceiling (A). My reading: nothing in the data justifies a specific hold law; if the goal is pipes 2-3 and E1, the choice is between a declared actuator convention (D) and accepting A.

## Open questions
1. Closed-loop effect of a hair change in a_thr is large (x0.95 vs x1.05); the cause of the swing (earlier take-off, later burst end) was not isolated.
2. B11 shuffles not run (step-4 shuffles stuck at start); E2a class gives no GF/A; E2a degree not re-run.
3. GF output rate in the near vs far regime was not logged; "TTMn amplitude follows stimulus" is inferred.
4. Edge counts use edges >= 2 synapses; single-synapse edges and electrical coupling are not counted.
