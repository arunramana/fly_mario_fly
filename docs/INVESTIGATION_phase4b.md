# Phase 4b investigation: physiological calibration of ORN -> KC -> MBON, conditioning re-measured, heat as punishment, DNp09

Date 2026-10-05. Investigation only: no code, config, manifest, calibration, motor map or test changed; synthetic stimuli, no game runs. Scratch `audit/p8i_*.py` (+ `.json`, `.log`). Calibration fixed (`brain/calibration.json`, network hash 3848f3e70b2051ef). At most 3 worker processes.
Tags: **[M]** measured here; **[S]** simulated here (scratch); **[L-ft]** literature, full text read online (through the fetch summariser, so numbers are as the summariser quoted them); **[L-abs]** abstract / search snippet only; **[L-m]** from memory, unverified; **[A]** assumed or invented. No [L-m] number is used as a target below except where stated.

## 1. Answer

1. **Unit mapping.** The ORN is the only stage with a clean mapping: an ORN has no recurrent drive, so its model rate equals the injected drive (ORN mean 13.1 vs injected 11.6 Hz-equivalent, i.e. identity within the small recurrent addition) [M]. So "ORN drive of x" is x spikes/s by convention, and the downstream stages are outputs, read directly in model Hz. At a physiological ORN input (8 Hz spontaneous on all ORNs [L-ft, Wilson 2013 review] plus +50 Hz on the 189 ORNs of three glomeruli, max ORN rate ~300 Hz [L-ft]) the **as-built chain is too dense and too weak in two different places**: KCs are not sparse (36% of KCs above 1 Hz; 82% with spontaneous ORN drive; baseline KC 1.7 Hz where real KCs are "nearly silent" [L-abs]) and MBONs are ~100x too small (strongest MBON response 0.57 Hz with the KC code sparsified; ~2 Hz as built, against about 85 Hz for a strongly responding MBON [L-ft, ambiguous unit, see 3a]).
2. **Two stage factors, no per-target ones, repair both.** An APL->KC gain of x100 (target: 5-10% of KCs active [L-ft, Lin 2014]; gives 8.1-8.8% above 1 Hz and baseline KC 0.08 Hz) and a KC->MBON gain of x100 (target: strongest MBON about 75-100 Hz; gives 75 Hz, MBON baseline 3.5 Hz, 44% of MBONs respond > 1 Hz). The KC amplitude itself needs **no** scale (top 7.5% of KCs fire 4-8 Hz). KC->MBON x150 already destabilises the loop (MBON baseline 33 Hz, response collapses), so x100 is close to the ceiling [S].
3. **Conditioning with calibrated amplitudes reaches the motor map at 2-5% of threshold, 100x more than Phase 4 (<=0.05%), still not 10%.** Real brain, learning rate set so the CS+ MBON response falls to 0.22 (Hige 80% depression target): MDN +5.2%, steer map 2.4% (DNa02 mean 19.6% of the steer threshold), DNp09 0.1%, GF membrane unchanged 0.0152 -> 0.0154 (threshold 0.1696). **The legacy depression-only rule is not associative here**: cue alone gives 0.55 (paired 0.22), unpaired 0.65. An order-dependent bidirectional rule is: paired 0.64, cue only 0.94, taste only 1.00, unpaired 0.96, US-before-cue 1.58 (potentiation), no weight drift (0.996), shuffles ~0.97. But the order dependence is built into my rule (Handler 2019 shape), not discovered.
4. **Heat/thermo is not a usable punishment signal**: thermo cells raise PPL1 (+0.132 Hz at drive 100, 18x rest 0.0078) and PAM (+0.126 Hz) equally (PPL1/PAM 1.04); warming cells (VP2) 0.71, cooling (VP3) 0.67, shuffles 3-4x more. Literature says PPL1 subsets respond to cooling not warming [L-abs, Tomchik 2013]. Nothing in 1-1 is a heat source: any punishment is an invented sensory event.
5. **DNp09 = P9** [L-ft]: forward walking with ipsilateral turn (Bidaye 2020); and also the freezing neuron of Zacarias 2018 (activation: running then freezing, freezing more likely at low speed). Our reading "DNp09 above threshold = walk right + B" is defensible as the forward-walking program, not as established for speed or for looming context, where the freezing literature points the other way.

## 2. Evidence

### 2a. Literature targets (verified online)

| # | Claim | Source | Conf. |
|---|---|---|---|
| L1 | Average ORN fires 8 spikes/s without odour; max ORN rate ~300 spikes/s; dynamic range ~2 orders of magnitude in concentration | Wilson 2013 review, PMC3933953 (quotes Hallem and Carlson 2006 and others); Hallem and Carlson 2006 itself: sparse strong responses, inhibitory responses widespread (abstract only) | [L-ft] review; [L-abs] H&C 2006 |
| L2 | KCs "nearly silent at rest"; odour responses very few spikes in a small subset; ~10 PNs per KC, high KC firing thresholds, fast-decaying EPSPs make the code sparse | Turner, Bazhenov, Laurent 2008 (J Neurophysiol 99:734), abstract and search snippets; no number extracted (the PDF could not be parsed) | [L-abs] |
| L3 | 5-10% of KCs respond to any odour; blocking APL or its KC input lowers sparseness, raises odour correlations | Lin et al. 2014 (Nat Neurosci), PMC4000970 | [L-ft] |
| L4 | Honegger 2011: imaging of >100 KCs "~5% of the total population". **That 5% is the recorded sample, not the responding fraction**; sparseness consistent across odours; no responding percentage in the abstract | CSHL repository abstract | [L-abs] |
| L5 | MBON-gamma1pedc>alpha/beta: CS+ response 118 +/- 8.3 spikes before, 24 +/- 7.4 after pairing (80 +/- 5.7% drop; EPSC charge -90%); 4 light pulses 1 ms at 2 Hz starting 0.2 s after odour onset; backward pairing (odour 0.5 s after the last pulse) no change. Spike window quoted as 0-1.4 s from odour onset by the summariser, i.e. **order 100 spikes/s, unit not certain** | Hige et al. 2015 Neuron, PMC4674068 | [L-ft], unit [ambiguous] |
| L6 | Bidirectional KC->MBON plasticity: depression when dopamine is concurrent or follows KC activity, potentiation when it precedes; DopR1/DopR2 | Handler et al. 2019 (Cell), abstract confirmed; details from Phase 4 full text | [L-abs] / [L-ft] |
| L7 | MBON spontaneous firing rate, KC odour-evoked spike rate in Hz, ORN rates in specific odours: **not verified** (the Hige 2015 Nature PMC text has calcium imaging, no rates; Hallem PDFs would not parse). MBON baseline of "a few Hz" and KC responders of "a few Hz" are [L-m] and used only as sanity ranges | none | [L-m] |
| L8 | PPL1 subsets innervating the vertical lobes respond to cooling (25 to 18 C), not warming (25 to 32 or 37 C); a nociception-to-escape route through dopamine/MBON exists (not read) | Tomchik 2013 (abstract via fetch); search snippet only for the nociception route | [L-abs] |
| L9 | Aristal thermosensory axons arborise in VP2 (warming) or VP3 (cooling); VP PNs project to MB and lateral horn | Marin et al. 2020 (Curr Biol), abstract snippet | [L-abs] |

### 2b. The model chain (real brain, `audit/p8i_a.py`, `p8i_a2.py`, `p8i_k.py`)

Odour A = ORN_DM1, VA2, DM4 (189 ORNs), +50 Hz for 60 frames after a 60-frame baseline, 20-frame mean; spontaneous = 8 Hz on all 2,638 ORNs. Real | five degree shuffles.

| # | Quantity | Literature target | Real | Shuffles (5) | Conf. |
|---|---|---|---|---|---|
| a1 | KC baseline, silent ORNs | ~0 | 0.008 Hz | n/a | [M] |
| a2 | KC baseline, ORN 8 Hz | nearly silent | **1.70 Hz** (92% of KCs above 0.1 Hz) | 1.0 Hz (all 5) | [M] |
| a3 | KCs above 1 Hz, odour A +50 Hz, silent ORNs | 5-10% active | **36%** (above 0.1 Hz: 50%; above 5 Hz: 9.5%; top 5% carry 29%) | 55-56% (spont) | [M] |
| a4 | KC responders (top 7.5%) mean rate | few Hz [L-m] | 7.9 Hz (silent), 10.0 Hz (spont) | max KC 24-29 Hz (heavier tail) | [M] |
| a5 | MBON mean, silent ORNs, odour A +50 / strongest MBON | strongest ~85 Hz | 0.62 Hz mean, 2.3 Hz max | mean 1.3-1.6 Hz, max 3.4-11.6 Hz | [M] |
| a6 | APL weight share of KC input | n/a | **22.3%** (KC 22.4%, DAN 3.4%, MBON 0.2%, ORN 0); APL is the largest single source type (906 of the KC in-weight). KC->APL 0.90 of APL's input | n/a | [M] |
| a7 | APL lesion (zero APL output), spont: KC mean | rises a lot [L-ft, Lin] | 1.70 -> 2.03 Hz (+20%), KCs above 0.1 Hz 92% -> 100%, top-5% share unchanged 0.08 | | [M] |
| a8 | APL->KC gain lam: KCs responding by >1 Hz, odour A +50 Hz (silent ORNs / spont) | 5-10% | lam 1: 36% / 35%; 3: 34 / 33; 10: 26 / 27; 30: 16 / 18; **100: 8.1 / 8.3**. KC baseline with spont at lam 100: 0.079 Hz | | [S] |
| a9 | KC->MBON gain kappa (lam 100, spont): MBON baseline mean / odour response mean / strongest | strongest ~85 Hz | kappa 1: 0.05 / 0.11 / 0.57; 10: 0.23 / 0.86 / 5.7; 30: 0.69 / 2.7 / 18; **100: 3.5 / 11.2 / 75 (44% of MBONs above 1 Hz)**; 150: baseline 33 Hz, KC base 0.7, response mean -0.06 (loop regime, unusable) | | [S] |
| a10 | Spontaneous ORN drive in the shuffled twins | n/a | motor outputs quiet (base DNp09 0.004, MDN 0.006) | outputs 0.7-1.1 Hz = 40-80x thresholds, GF spikes at rest (15-45 Hz) | [M] |

**Is 41% sparseness an artefact?** Yes, three missing things, all structural: (i) no spike threshold (ReLU at zero; the real KC needs ~several coincident PN inputs, L2); (ii) in-network normalisation makes each KC the weighted mean of its inputs (rows sum to 1), so KC rates are an average over ~10 PNs rather than a thresholded sum; (iii) APL is present (22% of KC input) but as a rate unit it subtracts the same offset from every KC (0.77 x mean KC x its weight), which barely moves the distribution (a7). A single APL->KC gain of x100 compensates for all three, and is a calibration to the 5-10% target, not a measurement.

**Conversion factors needed** (one per stage): ORN 1 (identity); KC amplitude 1 (no scale), KC sparsity: APL x100; MBON: KC->MBON x100 (stage ratio literature/model about 75/0.57 = 130 at the strongest MBON, 100 taken as the largest stable value). The MBON factor is a gain on the KC->MBON edges (convergence of thousands of KCs, normalised away by the in-network rule), not a unit conversion.

### 2c. Conditioning, S2 = lam 100, kappa 100, ORN 8 Hz tonic, cue +50 Hz, taste 100 Hz on PhG (`p8i_c.py`, `p8i_sum.py`)

lr (depression rate) interpolated on the real brain so the PAM-targeted MBON CS+ response falls to 0.2 (Hige 80%): lr 0.66 [S, calibrated to L5]. KC_REF = 3.78 Hz (p95 of the odour-A KC response). 8 trials x 90 frames, same protocol as Phase 4 section c. Ratios post/pre of the cue-A response; real | shuffle mean (min, max).

| Arm | depr rule: PAM-group CS+ | all MBON | bidir rule: PAM-group CS+ | all MBON | W sum depr / bidir |
|---|---|---|---|---|---|
| paired (cue then taste) | 0.223 \| 0.26 | 0.35 \| 0.55 | 0.643 \| 0.971 (0.953-0.983) | 0.73 \| 0.97 | 0.957 / 0.996 |
| fixed weights | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| cue only | 0.554 | 0.60 | 0.938 | 0.96 | 0.968 / 1.001 |
| taste only | 0.847 | 0.90 | 0.998 | 1.00 | 0.980 / 1.000 |
| unpaired | 0.651 | 0.72 | 0.960 | 0.97 | 0.972 / 1.000 |
| taste before cue (backward) | 0.559 | 0.61 | **1.578** (potentiation) | 1.46 | 0.961 / 1.012 |
| thermo paired (punishment) | 0.551 | 0.60 | 0.929 | 0.95 | 0.965 / 1.002 |
| thermo only | 0.951 | 0.97 | 0.999 | 1.00 | 0.986 / 1.000 |
| control odour B after paired | 0.862 | | 0.992 | | |

Shuffles: depr paired 0.26 equals their control-odour 0.26 and weights fall to 0.67 (cue-independent depression); bidir ~0.97 for every arm (no learning). All [S], rule shapes [A]. Peak PAM 0.197 Hz and PPL1 0.198 Hz in the paired trials: the US stage was not scaled (taste->PAM remains ~0.2% of drive, as in Phase 4 b1).

Reach to the motor map, real, cue A alone, post minus pre (`p8i_c_S2_table.csv`):

| Rule / arm | MBON26/27/31/32 response (Hz) pre -> post | MDN (back) | steer map \|R-L\| | DNa02 mean | DNp09 | TTMn | GF membrane |
|---|---|---|---|---|---|---|---|
| depr, paired | 0.364 -> 0.096 | +7.2e-4 = **5.2%** of 0.0139 | 2.4% of 0.0109 | +2.1e-3 = 19.6% of 0.0109 | 0.12% | 1e-5 | 0.0152 -> 0.0154 of 0.1696 |
| depr, cue only | 0.364 -> 0.265 | 1.6% | 0.3% | 7.0% | 0.07% | | unchanged |
| bidir, paired | 0.364 -> 0.169 | 2.4% | 0.9% | 10.2% | 0.14% | 4e-6 | unchanged |
| bidir, backward | 0.364 -> 0.724 | 5.1% (opposite sign) | 1.1% | 19.9% (opposite) | 0.14% | | unchanged |
| bidir, thermo paired | | 0.07% | 0.2% | 1.4% | 0.08% | | unchanged |
| fixed | no change | 0 | 0 | 0 | 0 | 0 | 0 |

The four MBON types that reach MDN/DNa02 respond weakly to odour A (0.36 Hz at kappa 100 vs 11 Hz for the mean MBON), so a large relative change is a small absolute one. Odour panel (16 random 6-glomerulus odours at +50 Hz, `p8i_panel.py`): those four MBON types respond 0.7-5.8 Hz (mean over the 8 cells; max cell 2-16 Hz) and the innate (pre-learning) motor effect of an odour is -0.4 to +0.5 of the back threshold, -0.2 to 0 of walk, up to +0.38 of steer [S]. So an odour that drives those MBONs well could move MDN/DNa02 by tens of percent of threshold when depressed 80%; none of the 16 reaches 100%. Baseline motor activity with ORN 8 Hz and kappa 100 stays below threshold (walk 0.0041 vs 0.0169, back 0.0060 vs 0.0139) [M].

As built (S1, lam = kappa = 1, same ORN drive; lr 0.21 for 0.2): paired 0.18, cue only 0.26, thermo paired 0.24, taste only 0.51; weights fall to 0.56 with no stimulus-specific cause (tonic KC 1.7 Hz and tonic DAN 0.3-0.5 Hz); motor reach 0.2-1.8% [S]. So the sparse code and the amplitude both matter.

### 2d. Heat / thermo -> PPL1 (`p8i_t.py`, no tonic ORN, no stage factors)

Rest: PAM 0.0072, PPL1 0.0078 Hz (rest sd 3e-5 and 1e-4). Real | five shuffles (response above rest, Hz):

| Drive 100 | dPAM | dPPL1 | PPL1/PAM | PPL1 x rest | shuffles dPAM / dPPL1 |
|---|---|---|---|---|---|
| all 25 thermo | 0.126 | 0.132 | 1.04 | 18x | 0.34-0.62 / 0.24-0.59 |
| VP2 warming (7) | 0.029 | 0.021 | 0.71 | 3.7x | 0.08-0.24 / 0.07-0.16 |
| VP3 cooling (7) | 0.047 | 0.031 | 0.67 | 5.0x | 0.15-0.34 / 0.10-0.34 |
| VP1m (11) | 0.075 | 0.088 | 1.18 | 12x | 0.09-0.17 / 0.07-0.20 |

At drive 30 all values are 0.28x of the drive-100 ones (linear). The PPL1 types lifted by all-thermo drive 100: PPL103 0.35, PPL104 0.27, PPL101 0.19, PPL105 0.13, PPL106 0.11; PPL102 and PPL108 not at all [M]. Real is far above rest noise (z in the hundreds) but 3-5x below random wiring, as for taste in Phase 4. No separation from PAM; the best split (warming, 0.71) leans toward PAM.

### 2e. DNp09 (full texts read through the summariser)

| Claim | Source | Conf. |
|---|---|---|
| "This line labels DNp09 (henceforth referred to as P9)." P9 activation initiates forward walking with an ipsilateral turning component; unilateral P9 gives ipsilateral turns; inputs LC9 (265 synapses onto one P9), pC1 (2 synapses from pC1d); LC10 did not activate P9; freezing seen in only one genotype, attributed possibly to high CsChrimson expression | Bidaye et al. 2020 Neuron 108:469, PMC9435592 | [L-ft] |
| DNp09: bilateral pair; activation gives initial running then freezing in 61.5% (492/800) of trials; freezing probability negatively correlated with walking speed (r2 = 0.87): 85% at low speed vs 55% at high speed; silencing cuts freezing to ~20% (controls 55-63%) while running stays intact; silenced flies walk faster at baseline (12.81 vs 9.38 mm/s); looming makes flies freeze or flee | Zacarias et al. 2018 Nat Commun 2018 (doi 10.1038/s41467-018-05875-1), PMC6135764 | [L-ft] |
| P9 (DNp09) listed among walking-promotion DNs ("drives forward turning") next to BPN (straight forward) and MDN (backward), all targets of the GABAergic walk-OFF halting neurons; oDN1 and BDN2 carry forward velocity | Sapkal et al. 2024 Nature, PMC11446846 | [L-ft] |

## 3. What this means for the plan

- The Phase 4 "~100x short" is located and repaired by two stage gains (lam, kappa), each calibrated to a verified or flagged target, not by a gain on the motor side. It lands conditioned motor reach at 2-5% of threshold (paired, real), not above 10%: the remaining limit is that only four MBON types reach MDN/DNa02 and odour A drives them at 0.36 Hz.
- Learning on the jump (GF 0.0152 -> 0.0154 of 0.1696, TTMn 1e-5) and on walking (DNp09 0.1%) remains out of reach. Steering and backing are reachable at tens of percent for odours that drive MBON26/27/31/32, as an extrapolation, not as a measurement of threshold crossing.
- The legacy depression-only rule fails associativity at physiological amplitudes (cue only 0.55 vs paired 0.22) and the as-built network collapses its weights without any stimulus (S1 0.56). An order-dependent rule with depression and potentiation removes drift and gives specificity, but its sign structure is invented (L6 only gives the shape).
- Real vs shuffles: real is the only network with cue-specific learning (shuffles ~0.97 under bidir; cue-independent depression under depr) and the only one whose motor outputs stay quiet under tonic ORN drive.

## 4. Open questions

- MBON literature unit (L5) and MBON baseline (L7) are unverified: kappa 100 rests on "about 75-100 Hz for the strongest MBON" with an ambiguous unit; if the real number is 10x smaller kappa is 10 and everything in 2c scales by 0.1.
- KC responder rate, spontaneous KC rate in Hz not verified (L2, L7).
- Taste -> PAM stays at 0.2% of drive; a stage factor for the US side would also be a calibration to a target not yet found. PAM/PPL1 responses to heat/taste in Hz are not in the sources read.
- ORN spontaneous drive 8 Hz uniformly on all ORNs ignores per-type rates (0 to >30 [L-m]).
- Shuffled twins are not interpretable for motor reach under tonic ORN drive (outputs saturated and GF spiking at rest).
- Threshold crossing by learning not demonstrated; DNa02 shares are of the steer threshold, which the map applies to |R-L| of DNa01+DNa02, not to DNa02 alone.
- One cue odour, 8 trials, one noise seed for plasticity, rate model, MBON compartments of the four reaching types unknown here.

## 5. Verdict, scalars, decisions

**Verdict.** Learned odour approach/avoidance is reachable honestly only as steering and backing, only after two calibrated stage gains and an order-dependent plasticity rule, and only for odours that drive MBON26/27/31/32; the modelled effect is 2-5% of motor threshold at the measured cue, plausibly tens of percent for the best odours, never the jump or walk. Heat as sensed punishment is not honest: there is no thermal event in 1-1, the thermo wiring does not separate PPL1 from PAM, and the literature ties PPL1 to cooling. Any reward or punishment in Mario's world (touching a mushroom, being hit) is an invented sensory event routed through real wiring, labelled as invented, like the looming synthesis. Cost: two stage gains, a rule with invented signs, a US drive, plus a statement that the motor thresholds were calibrated at a silent rest and hold under 8 Hz tonic ORN drive in the real brain only.

**Scalars that would be invented / calibrated** (registry tags): lam (APL->KC x100, calibrated to 5-10% active); kappa (KC->MBON x100, calibrated to strongest MBON ~75-100 Hz, unit uncertain); ORN spontaneous 8 Hz (measured, L1); cue increment 50 Hz (assumed, below the 300 Hz max); lr 0.66 (calibrated to 80% depression, L5); lrP = lr and wmax = 2 W0 (invented, bidirectional rule); eligibility and dopamine trace tau 60 frames (carried over, invented); KC_REF = p95 of KC response (a normalisation); taste drive 100 and thermo drive 100 (invented); DAN->MBON routing weights (legacy design). Unknown for taste: sugar GRN identity (Phase 0).

**Decisions for Arun.**
1. Build any learning demo at the mechanism level with lam and kappa and report "MBON response" plus "motor reach 2-5% of threshold", or stop. Recommended: only if a labelled invented reward event in a mushroom scene is wanted; otherwise drop.
2. If built, use the bidirectional order-dependent rule (not depression-only), and pre-register the controls: fixed weights, cue-only, unpaired, backward, five shuffles.
3. Decide whether to verify the MBON targets (Hige 2015 Neuron figure 1 spike counts and Aso/Owald baselines) before kappa is fixed; do not use kappa before then.
4. Drop heat/pain as punishment; if a punishment is wanted, state it as an invented sensed event (not heat), and expect PPL1/PAM non-separation (1.04) to keep valence the model's, not the connectome's.
5. DNp09: keep walk/B as "forward-walking program" in the motor map but label it as an interpretation; note the pooled map ignores P9's unilateral ipsilateral turn and the freezing literature (Zacarias) predicts a stop under looming at low speed, which the map would convert into a rightward run.

## 6. Decision (Arun, strict track), 2026-10-05

- **No learning demo.** E4 and E5 stay dropped.
- **This verdict is the strict finding.** Learned odour approach/avoidance is reachable only as steering and backing, at 2-5% of motor
  threshold, after two stage gains and an order-dependent plasticity rule. Reward or punishment in Mario's world (touching a mushroom,
  being hit) would be an invented sensory event routed through real wiring, so it is not part of the strict track.
- **Heat is DROPPED as a punishment (learning) signal.** Decision 4 above is settled as "drop"; no replacement punishment is built.
