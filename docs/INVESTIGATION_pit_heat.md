# Pit as a heat source: does thermosensory drive turn, back or stop the fly?

Date 2026-10-05. Investigation only: no code, manifest, calibration or motor map changed; synthetic stimuli only, no game runs. Network 3848f3e70b2051ef (16,464 neurons), `brain/calibration.json` unchanged (thresholds: walk 0.01691, steer 0.01092, back 0.01393 Hz). Scratch: `audit/p9h_ann.py`, `p9h_net.py`, `p9h_reach.py`, `p9h_sim.py`, `p9h_an.py`, `p9h_ramp.py` (+ `p9h_sim.pkl`, `p9h_ramp.pkl`). 3 worker processes.
Tags: **[M]** measured here (MaleCNS via mcns.py, committed brain); **[S]** simulated here; **[L-ft]** literature, full text read through the fetch summariser; **[L-abs]** abstract/snippet; **[L-m]** memory; **[A]** assumed or invented.

## 1. Answer

- **Real wiring: thermo drive lowers DNp09 and weakly raises DNa02, MDN barely moves, nothing reaches the Giant Fiber [S].** With the baseline walking drive on (right LC10a 15), the strongest effect is cold or all-thermo drive of 300/cell on both sides: DNp09 3.6x -> 0.0-0.8x walk threshold, so B (run) is released. **Right stays pressed 100%** because steer sits at 9.9x its threshold from the landmark. Left (back/steer) appears only for hot (VP2) bilateral 300: 35% of frames. **The fly slows to a walk, it does not stop and does not back away.**
- **This is avoidance at best, never crossing, and is separate from heat as a learning punishment (dropped).** Without the walking drive the fly is already below walk threshold (0.40x), so there is nothing to stop. Thermo drive on one side gives a contralateral turn (right-side heat -> Left 97% at 300), the geometrically correct "turn away".
- **Shuffles are not a usable comparison here.** With the landmark on, all 5 shuffles are saturated (walk 8.4x, back 13x, GF spiking every frame) and thermo drive only raises DNp09 and MDN (never lowers). The real-brain DNp09 decrease has no shuffle counterpart: it is a property of the real wiring (or of its unsigned-NT cells), not shown to be specific to its structure beyond that.
- **Verdict: not worth building for the 1-1 goal.** At best it slows Mario at a pit edge, at drive 30-100x the amplitudes in the looming calibration, with 2 invented scalars, and a pit is death whether he walks or runs into it. It cannot make him cross. Keep only if Arun wants an avoidance demo.

## 2. Evidence

### Cell inventory

| claim | data or source | conf. |
|---|---|---|
| MaleCNS thermo/hygro sensory cells (whole CNS): TRN_VP1m 11, TRN_VP2 7, TRN_VP3a 6, TRN_VP3b 1 (thermosensory, 25); HRN_VP4 28, HRN_VP1d 18, HRN_VP5 12, HRN_VP1l 8 (hygrosensory, 66). All entry nerve AN. | `audit/p9h_ann.py` (annotations `class`, `type`) | [M] |
| In the committed network: all 25 TRN (sensory tier "THERMO"); only 2 HRN (HRN_VP1l 1, HRN_VP1d 1) as interior cells, not drivable; 64 HRN absent. Side split (L/R): VP2 4/3, VP3a 3/3 + VP3b 0/1, VP1m 5/6. Plus about 170 VP-labelled second-order cells (VP PNs, LoVP/MeVP types matched by name) as interior. | `audit/p9h_net.py` | [M] |
| Hot = VP2 (7 cells, Gr28b.d); cold = VP3a/b (7 cells, Ir21a). Marin names VP2 heating, VP3 cooling. | Marin et al. 2020 Curr Biol, PMC7443704 (full text via fetch summary) | [L-ft] |
| VP1m (11 in MaleCNS): expresses Ir68a, "proposed to respond to humidity", not confirmed. Not hot or cold. | same | [L-ft] |
| Frank 2015: arista has 3 warm- and 3 cold-responsive cells; hot receptors Gr28b; PNs narrowly tuned (hot or cold) or broadly tuned (both, largest group ~10); silencing broadly tuned PNs impairs hot and cold avoidance. | Frank et al. 2015 Nature, PMC4554763 (fetch summary) | [L-ft] |
| Jouandet et al. 2023 Nat Commun ("Rapid threat assessment in the Drosophila thermosensory system", this is the "Tang/Liu 2015" slot I could not match to a paper with that name): TPN-III -> TLHON ON-responses to rate of change; TLHONs connect to DNp01 (Giant Fiber), DNp09, DNp06, DNp02, DNp04, DNp05, DNp11, DNp13, DNb05; primes "early turns" at a hot/cool boundary. | PMC10624821 (fetch summary) | [L-ft] |
| Liu 2015 (Gallio) cited by Arun: not read here; no number from it is used. TLHONs and TPN-IIIs are **not annotated by those names** in MaleCNS (synonym search `TLHON|TPN|Jouandet` finds only one unrelated "Kim 2017: TPN3", ANXXX470, 2 bodies). | `audit/p9h_syn.py` | [M] absent |

### Wiring reach (full graph, edges >= 2 synapses, signed, hops 1-3, per unit drive on each source cell, mean over target type)

| source (n) | DNp09 hop3 | DNa02 hop3 | MDN hop3 | GF hop3 | DNb05 hop1/2 | conf. |
|---|---|---|---|---|---|---|
| VP2 hot (7) | -1.7e-5 | +3.7e-5 | +7.7e-6 | -2.6e-7 | +5.6e-5 / +1.5e-3 | [M] |
| VP3 cold (7) | -4.7e-5 | +7.7e-6 | -3.3e-6 | -1.7e-5 | +1.2e-2 / +1.5e-2 | [M] |
| VP1m (11) | -1.5e-6 | +1.5e-6 | +6.4e-7 | -3.4e-7 | +1.1e-4 / +7.8e-5 | [M] |
| LC10a (275), for scale | -5.5e-4 (hop1 +4.0e-3) | +1.6e-2 (hop2) | -2.2e-4 | -5.5e-5 | | [M] |

No direct thermo-to-descending edge except cold/hygro to DNb05 (not in our motor table). Thermo reach to the GF is at most 4e-5 (unsigned), 4 orders below LC4 -> GF (0.16, Phase 6). The Jouandet TLHON -> DNp01 route is **not visible in this network**. Reach is linear and ignores recurrence and sign-unknown cells; the simulation below is what counts.

### Simulation (real brain, `p9h_sim.py`; landmark = right LC10a 15; thermo from frame 40, window frames 60-99, drive per cell in the same rad-as-Hz convention as looming; values as x motor threshold)

Real, landmark on, 4 noise seeds; reference (no thermo) walk 3.58 +/- 0.10, steer 9.94 +/- 0.30, back 0.58 +/- 0.11 (frame noise), B and Right 100%, Left 0% [S].

| thermo drive | walk (DNp09) | steer | back (MDN) | B / Right / Left frac | conf. |
|---|---|---|---|---|---|
| HOT VP2 both, 30 / 100 / 300 | 3.3 / 2.7 / 1.9 | 9.7 / 9.2 / 8.5 | 0.62 / 0.75 / 0.96 | 1/1/0 ; 1/.98/.02 ; 1/.65/.35 | [S] |
| COLD VP3 both, 30 / 100 / 300 | 3.0 / 1.5 / 0.84 | 10.0 / 10.2 / 10.3 | 0.52 / 0.41 / 0.38 | 1/1/0 ; 1/1/0 ; B .11, Right 1 | [S] |
| ALL both, 30 / 100 / 300 | 2.8 / 0.76 / 0.02 | 9.9 / 9.7 / 9.1 | 0.56 / 0.56 / 0.70 | B 1 / .02 / 0, Right 1, Left 0 | [S] |
| HOT right only, 300 | 2.1 | 7.9 | 0.76 | Right .98, Left .02 | [S] |
| VP1m (humid?) both, 300 | 3.5 | 9.9 | 0.58 | no change | [S] |
| GF membrane / threshold, GF spikes, A frames | max 0.169, 0, 0 in every real cell | | | | [S] |

- **DNp09 below walk threshold: yes** (cold both 300, all both >= 100, ~3-30x as strong as the 10-30/cell looming amplitudes of the earlier calibration). **Back over Left over walk: no.** Left = back or steer < -thr, and steer stays at 8-10x. Back (MDN) never exceeds 0.96x threshold, so the back button alone is never triggered. Right wins because the landmark's steer is 9.9x.
- **Ramp (a heat field rising linearly over 60 frames, bilateral, `p9h_ramp.py`):** ALL 300: B off by frame ~20 (walk 0.35x), Right pressed throughout; HOT 300: Left share rises to 40% by frame 40-49; COLD 100 and HOT 100: B stays on; ALL 100: B off only in the last 10 frames (57%) [S].
- **Without the landmark (rest, 2 seeds):** walk starts at 0.40x so the fly is not walking; thermo drive drops it to 0 (hot/all 100), steer goes negative for hot and all (HOT both 300: steer -1.5, Left 97%, back 0.92). One-sided drive gives contralateral turn: ALL right-only 300 Left 97%, left-only 300 Right 4% (steer +0.55, below threshold) [S].
- **Left-right confound:** the 25 cells are not balanced (hot 4 L/3 R, cold 3 L/4 R, VP1m 5 L/6 R). A "both sides, equal per cell" stimulus therefore gives net asymmetry; the negative steer under bilateral hot drive may partly be this (not isolated) [A].
- **Shuffles (5 degree-preserving, landmark on, 1 seed; landmark off, 1 seed):** landmark on, ref already saturated: walk 8.4x, back 13.4x, Left 100%, GF spikes in every window frame. Thermo drive only raises walk (to 13-56x), back and DNa02: no shuffle ever lowers DNp09. Landmark off: shuffles go from silent (walk 0.40x) to walk 6-43x with thermo 30-300, GF spiking 8-40 of 40 frames, A frames 3-9 (jump presses) [S]. So in shuffled wiring thermo drive reaches the GF and jump; in the real wiring it does not.

## 3. What this means for the plan

- **Heat is not a punishment (settled earlier) and not a crossing route.** D3 (gaps): this does not move it. Thermo drive does not reach the GF or A in the real brain (GF membrane 0.17 of threshold, 0 spikes, 0 A frames at every strength), so it cannot help a jump over a pit. The only A presses in this study are in shuffled wiring, which is a saturation artefact.
- **Usefulness in 1-1:** pits are lethal at the edge or beyond. Releasing B at the edge makes Mario walk instead of run towards the pit (Right still pressed), which arguably makes it worse (less momentum, same fall). A true stop would need Right released, which the real wiring never does with the landmark on. Only a bilateral hot field at the top of the range gives Left, 35-40% of frames (jitter back and forth at the edge), not a retreat.
- **World property:** a declared heat field around each pit: strength S(d) = S0 x max(0, 1 - d/R) (or a step), delivered to the TRN neurons by an azimuth rule like `azimuth_shares`; hot field to VP2 (7 cells), cold to VP3 (7), or both. Scalars: S0 (Hz-equivalent, invented, no TRN calibration available), R (px, invented), and the choice of hot vs cold subtype (a modelling choice, since a "pit" is neither). Entry stays at sensory neurons only, so the rule holds. No new population; the 64 HRN could be added, but they are not needed.
- **Mechanism ruled out:** "heat makes the fly stop at the pit" (needs Right released). **Mechanism not enabled:** "thermo -> escape jump" (Jouandet's TLHON-> DNp01 route is not in this network at >= 2 synapses, 3 hops).

## 4. Confounds

- Amplitude has no anchor: 100-300/cell is borrowed from ORN max (~300 Hz, [L-ft in Phase 4b]); no TRN firing-rate source was read, so every "fraction of threshold" above depends on an invented strength. At physiological drive 3-30 the real-brain effects are 0-0.8x walk, no button change.
- The landmark is itself invented and dominates steer (9.9x); results are conditional on it. A different walking drive changes the "Right wins" conclusion.
- Shuffles saturate under the landmark (GF 100% spiking), so the control cannot test specificity of the DNp09 drop. Landmark-off shuffles show GF/jump drive that the real brain lacks, so real vs shuffle differs in the favourable direction for the real brain, but this is "structure is far from random", not "structure implements avoidance".
- Cold (not hot) is more effective at lowering walk, yet literature says nothing about what a pit "should" be.
- Zacarias 2018: DNp09 also gives freezing; the motor map reads DNp09 as forward walking. A DNp09 decrease is read here as "run released"; whether that is a stop is an interpretation.

## 5. Open questions and decisions for Arun

1. Do you want a pit-avoidance demo at all, knowing the best case is "walks instead of runs" at drive 100-300 and cannot cross? **Recommendation: no, for the 1-1 goal.**
2. If yes: hot (VP2) or cold (VP3) subtype, and accept two invented scalars (S0, R) plus an azimuth rule. Hot gives Left, cold gives release of B; neither gives a stop.
3. Whether to add HRN (64 absent cells) or TLHON-like cells: they would need a path to the GF/DNp09 that this network (k=3, N=5) lacks; not recommended before D3.
4. A TRN firing-rate source (Frank 2015 / Liu 2015 full text, not read) would be needed before any strength is called calibrated.
5. Gap crossing (D3) remains unsolved; thermo does not help it.
