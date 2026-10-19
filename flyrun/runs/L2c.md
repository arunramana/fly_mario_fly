# L2c: can the fly BACK AWAY? MDN in MaleCNS, the routes into it, scratch builds (branch l2b; facts only, default brain untouched)

**Result.** Yes, through one route class: **aversive smell**. MDN is not in the model; it is 4 neurons (2 L, 2 R), excitatory, and reaches the steering DNa directly but **not** DNp09 (0 direct synapses; 2 hops, mass ~1e-5). Adding the k/N set for **ORN_V (CO2)** (47 new neurons = 38 ORNs + 5 intermediates + 4 MDN) and driving the right-antenna ORNs with HOME_R on lifts MDN from **0.010** (rest) to **0.10 at level 5, 0.41 at 20, 0.53 at 40-60**, i.e. 2x the GF value at the looming trigger (0.22). At the same time **DNp09 drops from 0.114 to ~0 from level 20** (he stops walking forward) and steer goes **+0.04 -> +0.40 (toward the smell, as in L2b)**. **ORN_DC4 (acid, Ir64a)** also reaches MDN (0.22-0.31 at level 20-40) with DNp09 and steering nearly untouched (steer +0.04..+0.06 on one antenna, +0.01 to +0.02 with both driven). **DA2 and DL5 do nothing to MDN.** **Vision does not work:** LC16 -> MDN is weak (2 hops, mass 1e-4) and at a Koopa's theta (20-60 px) MDN stays at rest (<= 0.004); LPLC2 / LC4 raise MDN only with a drive that already makes GF 1-12, and at the looming trigger MDN is 0.02 at most (10x below GF). **MBON -> MDN is real in the graph but does nothing in the simulation** (MDN <= 0.001). Rates are in model units (rectified, G = 0.5, 100 frames), not Hz.

Code: `l2c_graph.py` (graph facts), `l2c_sim.py` (scratch builds + drives), `l2c_mbon_shuffle.py`. Data: `runs/L2c_graph.json`, `L2c_mdn_inputs.csv`, `L2c_routes.csv`, `L2c_adds.json`, `L2c_drive.csv`, `L2c_ref.json`, `L2c_mbon_shuffle.json`.

## 1. MDN in MaleCNS (N >= 5 graph, 211,577 bodies)
- Type `MDN`: **4 bodies**: 11288 (L), 12348 (L), 10763 (R), 11332 (R). Predicted transmitter sign +1. **None is in the 881-neuron brain.**
- Input: 17,538 synapses in >= 5 edges (of 21,573 total input), roughly symmetric (~4.2-4.6k from each side). **Top 15 presynaptic types** (synapses, neurons, sign): GNG577 796 (8, -), DNpe023 781 (8, +), AN06B012 596 (8, -), LAL112 359 (14, -), LT51 328 (8, -), AN06B075 319 (7, -), PS183 299 (7, +), DNge124 296 (8, +), AN08B026 295 (11, +), LAL162 287 (7, +), DNge134 278 (7, -), LAL051 261 (7, -), IB023 258 (7, +), LAL144 256 (7, +), AN17A026 255 (7, +). No sensory type among them: MDN is fed by descending / premotor / LAL neurons, so any sensory route is >= 2 hops.
- Output (top): IN07B010 476, IN12B003 466, LBL40 463, IN03B015 462, INXXX045 444 (ventral cord interneurons), then DNa13 345, DNge124 280.
- **MDN -> DNp09: no direct synapse; signed mass 5e-6 (2 hops), -2e-5 (3 hops): nothing.** **MDN -> DNa01/02: direct, 9 synapses onto DNa L and 31 onto DNa R (mass +0.0007 / +0.0021)**, then net negative at 2-3 hops (~ -3e-4). A strongly active MDN would nudge DNa R slightly above L through one hop and does not change walking. (From the graph; the sim below includes these edges once MDN is added.)

## 2. Routes into MDN (hops, in model?, smallest k/N addition)
| route | neurons (L/R) | in model | direct syn onto MDN | min hops | signed mass h3 | k/N addition (new neurons) |
|---|---|---|---|---|---|---|
| smell V (CO2) | 16 / 39 | no | 0 | **3 (right antenna only; the 16 left ORNs have no path of <= 3 hops)** | +7.0e-6 | **47** = 38 ORN + 5 (CL366, Z_vPNml1, CB0431, M_adPNm3, GNG519) + 4 MDN |
| smell DA2 (geosmin) | 21 / 20 | no | 0 | 3 | -4.7e-8 | 19 = 12 + 3 (SAD085, CB1824, DNpe023) + 4 |
| smell DL5 | 23 / 19 | no | 0 | 3 | -6.6e-8 | 20 = 13 + 3 + 4 |
| smell DC4 (acid, Ir64a) | 11 / 12 | no | 0 | 3 | +1.4e-6 | 26 = 13 + 9 + 4 |
| vision LC16 | 88 / 94 | no | 0 | 2 | +7.9e-4 (h2 1.3e-4) | 556 = 181 + 371 + 4 |
| vision LPLC2 | 94 / 91 | **yes** | 0 | 2 | +4.3e-4 | 549 = 0 + 545 + 4 |
| vision LC4 | 71 / 55 | **yes** | 0 | 2 | -7.4e-4 (h2 +3.4e-3) | 404 = 0 + 400 + 4 |
| MBON (97) | 48 / 49 | 4 of 97 | **60 (44 L, 16 R)** | 1 | h1 -2.9e-3, h2 -1.4e-2 | 2,022 = 93 + 1,925 + 4 |

- "Other aversive ORN types I can justify": only DC4 (Ir64a; acid/ammonia avoidance in the literature, recalled, not checked here). V, DA2 and DL5 are the three named in the brief; DA4l / VL2p stay out (mixed valence).
- **Re-check of MBON -> MDN against the shuffle** (post column permuted, degrees kept, 20 shuffles): direct synapses 60 vs 21.2 (**2.8x**, but one shuffle reached 82), |2-hop mass| 0.0141 vs 0.0015 (**9.5x**, shuffle max 0.0071), 1-hop mass 1.1x. The old 2.7x holds for direct synapses; it is not strong (the shuffle spread includes it).
- The literature claim LC16 -> backward walking is **not** supported here: MaleCNS has no direct LC16 -> MDN edge and the 2-hop mass is 1e-4.

## 3. Scratch builds (W_steer 881 + route k/N set; `Net2` = o0_sim `Net` + an MDN readout; HOME_R = 0.5; drive 0-60 on all sources of the route; final state at frame 100)
References: **walking (HOME_R only, 881 brain + MDN): DNp09 0.213, MDN 0.013, GF 0.0008.** **Looming trigger (theta 0.77 rad, dtheta 0.0635 + HOME_R): GF 0.220, TTMn 0.110, DNp09 0.248, MDN 0.013** (the trigger does not touch MDN).

| route (build, side) | level | MDN | DNp09 | steer (DNa R-L) |
|---|---|---|---|---|
| V (47 new), right antenna | 0 / 5 / 20 / 40 / 60 | 0.010 / 0.099 / 0.406 / 0.521 / 0.527 | 0.114 / 0.081 / **~0** / ~0 / ~0 | +0.042 / +0.111 / +0.319 / +0.398 / +0.402 |
| V, both antennae | same as right (left ORNs are not in the set) | | | |
| DC4 (26 new), right | 0 / 5 / 20 / 40 | 0.015 / 0.067 / 0.224 / 0.311 | 0.114 / 0.111 / 0.104 / 0.101 | +0.042 / +0.048 / +0.056 / +0.057 |
| DC4, both antennae | 0 / 5 / 20 / 40 | 0.015 / 0.075 / 0.262 / 0.324 | 0.114 / 0.109 / 0.096 / 0.092 | +0.042 / +0.043 / +0.020 / +0.012 |
| DA2 / DL5 (19 / 20 new) | 0-60 | 0.017 flat | 0.213 flat | 0.044 flat |
| LC16 (556 new), 1-60 both sides | 0 / 5 / 20 / 40 / 60 | 0.0005 / 0.022 / 0.089 / 0.144 / 0.151 | 0.025 / 0.32 / 1.22 / 1.95 / 2.02 | +0.016 / +0.015 / +0.007 / +0.005 / +0.007 |
| LC16 at a Koopa's theta (h 24 px; d = 20 / 30 / 40 / 50 / 60 px = 1.08 ... 0.39 rad), both sides | | 0.0039 / 0.0028 / 0.0022 / 0.0018 / 0.0015 | 0.089 / 0.070 / 0.059 / 0.052 / 0.048 | ~ +0.016 |
| LPLC2 (549 new, k/N), 1-60 both | 5 / 20 / 40 | 0.027 / 0.110 / 0.153 | 0.41 / 1.56 / 2.08 | (GF 1.5 / 5.9 / 8.4) |
| LPLC2 (24-neuron small set), both | 5 / 20 / 40 | 0.26 / 1.02 / 1.29 | 2.6 / 9.9 / 12.5 | (GF 2.4 / 9.4 / 11.9) |
| LPLC2 / LC4 at the looming trigger | | LPLC2 small 0.021 (rest 0.006), k/N 0.0015 (rest 0.0006); LC4 small 0.0024 | | GF 0.22 |
| LC4 (404 new, k/N), both | 5 / 20 / 40 | 0.008 / 0.033 / 0.053 | 0.044 / 0.079 / 0.110 | (GF 1.4 / 5.5 / 9.5) |
| MBON (2,022 new, k/N), all 97 | 5 / 20 / 60 | 0.0002 / 0.0004 / 0.0004-0.0009 | ~0.015 | ~0 |

Caveats read off the table: (a) **adding neurons changes the base rows' normalisation**, so DNp09 at level 0 is not the same in every build (0.213 in the plain brain, 0.114 in V / DC4, 0.025 in the LC16 k/N build): compare each build with its own level-0 row, not across builds (`L2c_drive.csv` has level 0 for every build). (b) The "small" (top-20-intermediate) sets rank intermediates by 2-3-hop |mass| and keep 52-100 % of it (V: all of it, so small = k/N; no further pruning of V was tried here, L2b's pruning rule is the next step). (c) V on the LEFT antenna does nothing (no path of <= 3 hops): the 16 / 39 imbalance seen in L2b. (d) The LC16-at-Koopa-theta drive reuses LPLC2's scale (theta in rad as the current), so it is only as comparable as that choice is.

## 4. Proposal (not implemented; no behaviour, motor or gain change was made)
- **A 4th output "back up"**: MDN (mean of the 4) above a threshold -> press Left, with Right released. The existing 3 outputs stay as they are.
- **Threshold: 0.10 (INVENTED, orange).** Reasoning, not a fit: MDN rests at 0.010-0.017 in every build, the smell drive crosses 0.10 at level ~5-10, and 0.10 equals the existing TTMn threshold and is about half of GF at the looming trigger (0.22), i.e. "MDN as active as a jump trigger is". It would be a registry row.
- **Carrier: aversive smell, not looming.** Looming (LC16, LPLC2, LC4) leaves MDN at rest at the trigger and at Koopa thetas; making MDN rise there needs a drive that already fires GF (back up *during* a jump). Smell works: V is the strong cue but also silences DNp09 and turns him toward the odour side, so the 4th output would fight the L2b steering readout; **DC4 is the gentler candidate** (MDN 0.22-0.31 at level 20-40 while walking and steering change by < 15 %, and symmetric drive gives no turn); its literature role (acid avoidance) is recalled, not verified. Both need the game to provide an aversive odour cue (code may supply a stimulus, never the action): that is a separate design question (what in RAM smells aversive?), not answered here.
- What would change this: if the real fly backs away through cells outside this k = 3 horizon, or the visual route is another type (e.g. LC16 -> a ventral-cord relay), the model would not see it.
