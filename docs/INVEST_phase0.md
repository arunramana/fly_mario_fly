# Phase 0 report: sensory tiers, wiring to dopamine, unified network size, C2/C3 route

Date 2026-10-01. Investigator run; no code or config changed. Scratch scripts are in `audit/p0_*.py` (gitignored). The file name follows the investigator naming rule (`INVEST_<topic>.md`); the request asked for `PHASE0_REPORT.md`, so rename if wanted.

Conventions. **[M]** = measured from MaleCNS v1.0 files via `mcns.py` (annotations 211,577 bodies; weights streamed in Arrow batches, 151,856,684 rows, never loaded whole). **[L-v]** = literature, verified online (source named, abstract or snippet level unless stated). **[L-m]** = from memory, not verified.

Method notes that affect every number below.
- Side: `somaSide` is null for sensory neurons (somas are in the periphery). Side was taken from the `instance` suffix (`_L`, `_R`) and `rootSide`. Neurons with `rootSide = unknown` are listed as "unk".
- Edge table: one streaming pass kept every edge with weight >= 2 whose two ends are both annotated bodies. Of the 151.86M rows, 125.83M touch an unannotated body or are weight 1 and were dropped from the graph (I did not separate the two causes). Kept: 15,514,634 edges (w>=2), 10,653,945 (>=3), 6,300,108 (>=5), 2,769,379 (>=10), 1,067,386 (>=20), 161,299 (>=60). Each post neuron's total input was summed over all annotated-post rows regardless of the pre end.
- Path strength = sum over source neurons (mean-weighted, 1/n each) of products of w/total_input along paths, a unitless mass. Reference scale: LC4+LPLC2 -> DNp01 (Giant Fiber) is 1.7e-3 at 1 hop and 5.6e-5 over 3 hops (N>=5) [M]. Absolute values have no physiological meaning; only ratios against controls are used.

---

## 1. Answer

1. D7 is mostly settled in favour of the plan. Olfactory, taste, thermo/hygro and photoreceptor neurons are annotated with counts per type and side. **Nociceptors are not annotated at all** (no class, type, subclass, synonym or receptor tag). Sugar versus bitter taste neurons are also not labelled.
2. Taste reaches dopamine neurons by real wiring, in 2 hops, but weakly and not specifically. Pharyngeal taste neurons (9x a random-sensory null onto PAM) and thermo neurons (17x) stand out; labellar taste neurons are not above the null at 3 hops. Sugar-specific reward and nociceptive punishment cannot be built honestly from annotation alone.
3. Recommended unified network: k = 3, N = 5, built as a union of segment paths plus the whole mushroom body. That gives 15,551 neurons, 592,683 edges, measured 2.2 ms per network step single-threaded (about 22 ms per frame at 10 substeps). A vision-only k=3, N=5 core is 2,972 neurons and 0.5 ms per step.
4. C2/C3 -> central complex -> output: **no honest route.** A 3-hop topological path exists, but the C2/C3 mass through the central complex is lower than for random medulla neurons (Tm1, Mi1), and about 1e-5 to 1e-3 of the control routes.
5. D1 feature-neuron entry, D2 goal cue (olfactory or LC10a lateralised, not phototaxis from photoreceptors), D3 leave gaps unsolved or use a looming-style stand-in, flagged. Details in section 5.

---

## 2. Evidence

### 2.1 D7: sensory populations in MaleCNS [M]

Query: `mcns.load_annotations`, plus `rootSide`, `instance`, `receptorType`, `synonyms` read directly from the feather; group by `class`, `subclass`, `type`, side.

| Population | Annotation | Total | Left | Right | Unk | Notes |
|---|---|---|---|---|---|---|
| Olfactory receptor neurons (ORN) | `class=olfactory`, superclass cb_sensory, 53 types named `ORN_<glomerulus>` | 2,639 | 884 | 1,344 | 411 | Right antenna is more complete. DA1 204 (L51/R105/unk48), VA1v 130 (L15/R73/unk42), VA1d 132 (L23/R76/unk33) are strongly asymmetric. Most other types are roughly balanced. |
| ORN attractive candidates | ORN_DM1 | 74 | 35 | 39 | 0 | |
| | ORN_VA2 | 83 | 33 | 41 | 9 | |
| | ORN_DM4 | 32 | 16 | 15 | 1 | |
| ORN aversive candidates | ORN_DA2 | 48 | 21 | 20 | 7 | |
| | ORN_V | 55 | 16 | 39 | 0 | |
| Gustatory, head (cb_sensory) | `class=gustatory`: labellar bristle 163 (types LB1a..LB4b), pharyngeal sensillum 48 (PhG1..16), taste peg 60 (claw_tpGRN 50, dorsal_tpGRN 10), unassigned subclass 4 | 275 | 138 | 137 | 0 | Per-side split: labellar 82/81, pharyngeal 24/24, taste peg 30/30. |
| Gustatory, body (VNC) | leg bristle 688 + 80 ascending, wing bristle 385 | 1,153 | | | | Types LgLG*, LgAG*, WG1-4; `receptorType` putative_ppk23 / ppk25 / IR52b on 225 to 269 each. These are pheromone or contact chemo types. |
| Thermosensory | `class=thermosensory`, types TRN_VP1m 11, VP2 7, VP3a 6, VP3b 1 | 25 | 12 | 13 | 0 | Hot versus cold is not annotated. |
| Hygrosensory | HRN_VP4 28, VP1d 18, VP5 12, VP1l 8 | 66 | 29 | 36 | 1 | |
| Nociceptive | no class, type, subclass, synonym or `receptorType` matches `noci|pain|ppk(non-gust)|painless|class IV|TRPA`. `unknown_sensory` holds 1,712 neurons with codes `SNxx*`, `SAxx*`, `ENS*`. | **0 labelled** | | | | Unlabelled sensory types may include nociceptors, but nothing in the data says which. |
| Photoreceptors | `superclass=ol_sensory`: R1-R6 3,377 (L1,112 / R2,265); R7p 332, R7y 482, R7d 82; R8p 330, R8y 481, R8d 76; unclear R7/R8 931; HBeyelet 7 | 6,098 | 2,345 | 3,746 | | The left-side R1-R6 count is half the right: an incomplete retina on one side. |
| LC4 | type `LC4`, visual_projection | 126 | 71 | 55 | | |
| LPLC2 | type `LPLC2`, visual_projection | 185 | 94 | 91 | | LC4 + LPLC2 = 311, matches the escape-circuit count. |
| C2 | ol_intrinsic | 1,745 | 871 | 874 | | |
| C3 | ol_intrinsic | 1,779 | 887 | 892 | | |
| Also present | LC10a 275 (L135/R140); LC6 124 (L59/R65); Tm1 1,777; Mi1 1,773; T4a 1,684; T5a 1,664; L1-L5 about 1,775 each | | | | | |

Dopamine targets [M]. `class=DAN` 340: 316 PAM (types PAM01..PAM15, 15 types), 16 PPL1 (PPL101..108, one per side each), 8 PPL2 (PPL201..204), 0 PPL1 among PAM. Also Kenyon cells 4,064, MBON 97. Outputs: DNp01 (GF) 2, TTMn 2, DNp09 2, DNa01 2, DNa02 2, MDN 4. DLMn is absent from the annotations.

### 2.2 Valence of ORN types (literature)

| Claim | Source | Status |
|---|---|---|
| DM1 and VA2 are required for, and sufficient for, attraction to vinegar; DM1, DM4, DP1m, DM2, VA2, VM2 respond to it | Semmelhack and Wang 2009 (Nature), via PMC2702439 text snippet | verified (snippet; abstract level) |
| DA2 is the only glomerulus activated by geosmin; its activation is necessary and sufficient for aversion | Stensmyr et al. 2012 (Cell), via MPG press page and Cambridge listing | verified (abstract level) |
| DL1 and DL5 mostly activated by aversive odours; DM1-DM4 mostly attractive | a review snippet in the search result, source not identified | abstract only, do not use as a target |
| V glomerulus is the CO2 channel and CO2 is aversive | Suh et al. 2004 | from memory |
| The glomerulus-level valence map is not one-to-one with odour valence | Strutz et al. 2014 (eLife): paper classifies odours, not glomeruli, in its main figure (PMC4270039) | verified |

Consequence: use only DM1, VA2, DM4 (attractive) and DA2 (aversive, strongest evidence); treat V as aversive only after a source is checked.

### 2.3 Wiring from taste, thermo and others to dopamine neurons [M unless noted]

Graph N>=3, normalised as above. Per-neuron mean mass reaching each DAN class at exactly 3 hops, against a null of 300 random draws of 60 sensory neurons (null median PAM 7.8e-7, p95 1.4e-6, max 2.0e-6; PPL1 median 1.6e-6, p95 2.8e-6, max 3.9e-6). Script `audit/p0_null.py`.

| Source set (n) | Min hops to PAM and PPL1 (N>=3 and N>=5) | PAM per neuron at k=3 | x null median | PPL1 per neuron at k=3 | x null median |
|---|---|---|---|---|---|
| GRN labellar (163) | 2 and 2 | 1.2e-6 | 1 | 1.2e-6 | 1 |
| GRN pharyngeal (48) | 2 and 2 | 6.8e-6 | 9 | 7.6e-6 | 5 |
| GRN taste peg (60) | 2 and 2 | 2.8e-7 | 0 | 7.3e-7 | 0 |
| GRN leg and wing, VNC (1,073) | 2 and 2 | 1.4e-7 | 0 | 1.7e-7 | 0 |
| Thermosensory (25) | 2 and 2 (PPL1 hops 2 at N>=3, 3 at N>=5 to some outputs) | 1.3e-5 | 17 | 1.8e-5 | 11 |
| Hygrosensory (66) | 2 and 3 | 4.5e-6 | 6 | 6.9e-6 | 4 |
| ORN, all (2,639) | 2 and 2 | 4.8e-6 | 6 | 1.0e-5 | 6 |
| Photoreceptors R7/R8 (2,714) | 3 | 2.0e-8 | 0 | 2.2e-8 | 0 |
| Photoreceptors R1-R6 (3,377) | 4 | about 0 | 0 | about 0 | 0 |

Reading. Hop counts alone are uninformative here: almost every sensory class reaches PAM in 2 hops because of the small-world structure. The strength ratio is the useful number.
- The strongest 2-hop intermediates from head taste neurons to PAM are PRW044, PRW072, SLP234, GNG323, GNG597 and an ascending type ANXXX434. For PPL1 they are PRW003, GNG321 and PRW044 (top contributions about 1e-5 to 4e-5 of total input for PAM, about 3e-6 for PPL1).
- Within head taste, pharyngeal types PhG13, PhG1a/b/c, PhG10, PhG9 route most to PAM at k=3 (6.4e-3 to 2.7e-3 summed over all PAM); labellar types LB1b, LB2b, LB4a, LB2a are the labellar best (1.4e-3 to 1.1e-3), LB3a-d the weakest. Sweet versus bitter identity of these types is **not annotated**, so none of them can be called sugar neurons from the data.
- By DAN type (mean per neuron, k=3), head taste reaches PAM04(B2) (labellar 3.4e-6, pharyngeal 1.5e-5), PAM01(y5), PAM11(a1) and also PPL102(y1), PPL106 and PPL101(y1ped). There is no clean PAM-only (reward) or PPL1-only (punishment) split.
- Thermo reaches PPL103(y2a'1), PPL104(a'3) (4.3e-5 and 4.6e-5, the highest of any source for those types) and PPL201 (4.2e-5). Hot versus cold is not annotated, so whether these are heat-punishment neurons is open.
- Unlabelled sensory types that reach PPL1 above the median of their class (median 1.2e-7): SAxx02 (n=12, 1.4e-5), ENS5 (n=6, 5.5e-6), GNG643 (n=18, 3.5e-6). These are leads only; no literature link was checked.

Literature (the plan's mechanism claims).

| Claim | Source | Status |
|---|---|---|
| Most PPL1 neurons that drive taste conditioning respond to bitter; two alpha-lobe PPL1 subtypes are necessary and sufficient for aversive taste memory | Kirkhart and Scott 2015 (J Neurosci) | verified (abstract level) |
| PAM neurons respond to sweet taste, signal sugar reward and reinforce short-term appetitive memory; OAMB PAM neurons (beta'2, gamma4) carry sweet reinforcement; gamma5b carries nutrient long-term memory | Yamagata et al. 2015 and Huetteroth et al. 2015 | verified (abstract level) |
| PPL1 dopamine neurons carry heat or electric-shock punishment | many, e.g. Galili et al. 2014 | from memory |

### 2.4 Unified network size and speed [M]

Rule: a neuron is in the network if it lies on a path of at most k hops from the entry tier to the output set, keeping edges with at least N synapses. Output set: DNp01 (GF), TTMn, DNp09, DNa01, DNa02, MDN (14 neurons). Script `audit/p0_size.py` (single union), `audit/p0_mod.py` (segmented union).

**A. Single path-union, entry to outputs.** Mushroom-body neurons (Kenyon, MBON, DAN, 4,501 in total) appear only when on a path.

| Entry tier | N | k=3 neurons / edges | k=4 | k=5 | k=6 |
|---|---|---|---|---|---|
| vis (LC4, LPLC2; 311) | 3 | 4,509 / 264k | 47,883 / 3.34M | 102,167 / 7.27M | 154,984 / 10.2M |
| vis | 5 | 2,972 / 113k | 24,135 / 1.20M | 74,027 / 3.32M | 127,448 / 5.37M |
| vis | 10 | 1,700 / 34k | 8,991 / 269k | 34,692 / 902k | 79,863 / 1.75M |
| vis | 20 | 818 / 7.4k | 3,249 / 48k | 11,723 / 211k | 25,414 / 406k |
| vis + all ORN + head GRN + thermo (3,078 to 3,248 entries) | 5 | 6,132 / 158k | 35,966 / 1.78M | 88,242 / 3.89M | 136,869 / 5.68M |
| same | 10 | 3,708 / 46k | 16,358 / 452k | 49,165 / 1.20M | 94,697 / 2.02M |
| same | 20 | 1,805 / 10.5k | 7,570 / 93k | 21,039 / 322k | 39,049 / 551k |

Sizes explode between k=3 and k=4 because the connectome is small-world: the mushroom body is reached only at k>=4 (5 MB neurons at k=3, N=3 for vis; 1,582 at k=4, N=5 for all entries). A learning mushroom body therefore does not fall out of a single k-hop rule unless k is 5 or more (35k to 88k neurons), which is too slow for training. Entries at low N are also dropped (all-entry tier, N=20, k=3: 1,142 of 3,078 entries on a path).

**B. Segmented union (recommended rule).** Union of per-segment paths with k=3 each: vis -> outputs, ORN -> Kenyon cells, head GRN -> DAN, thermo -> DAN, MBON -> outputs; plus all Kenyon cells, MBON and DAN included by rule. One construction rule, k and N saved with the brain.

| N | k | Neurons | Edges | Entries on a path | Outputs |
|---|---|---|---|---|---|
| 3 | 3 | 19,436 | 1,269,514 | vis 311, ORN 2,639, GRN 273, thermo 25 | 14 |
| 5 | 3 | **15,551** | **592,683** | vis 311, ORN 2,638, GRN 269, thermo 25 | 14 |
| 10 | 3 | 11,895 | 213,763 | vis 311, ORN 2,612, GRN 191, thermo 25 | 14 |
| 3 | 4 | 75,852 | 5,521,605 | all | 14 |
| 5 | 4 | 49,739 | 2,431,729 | all | 14 |
| 10 | 4 | 28,369 | 761,705 | all | 14 |

**Speed** (this machine, `OMP_NUM_THREADS=1`, float32 CSR, step = `clip(0.9 h + W h + b, 0, 200)`, 300 to 500 steps averaged; script `audit/p0_mod.py`).

| Network | Neurons | Edges | ms per step | ms per frame at 10 substeps |
|---|---|---|---|---|
| Existing escape subgraph (CLAUDE.md, cited, not re-measured) | 1,255 | n/a | 0.039 | 0.39 |
| vis-only, N=5, k=3 | 2,972 | 113,422 | 0.51 | 5.1 |
| vis + olf + gus + thermo, path-union, N=5, k=4 | 35,966 | 1,783,216 | 4.74 | 47 |
| vis-only, N=5, k=4 | 24,135 | 1,200,501 | 4.01 | 40 |
| vis-only, N=5, k=5 | 74,027 | 3,317,620 | 10.4 | 104 |
| segmented, N=10, k=3 | 11,895 | 213,763 | 0.83 | 8.3 |
| segmented, **N=5, k=3** | **15,551** | **592,683** | **2.18** | **22** |

Substeps per frame is 10 (`docs/SPEC_jump.md` line 236). Cost scales roughly 4 to 5 ns per edge for the matvec. At 22 ms per frame, a 5,000-frame episode costs about 110 s of network time plus the emulator, plus plasticity updates (not measured). The GPU question for this size is open: the CLAUDE.md rule (sequential and under 1 ms on CPU means the GPU loses) does not clearly apply at 600k edges; benchmark both in Phase 1.

### 2.5 Reachability of the motor outputs [M]

Min hops from each entry to each output (N>=3 / N>=5), `audit/p0_out.py`.

| Entry | DNp01 | TTMn | DNp09 | DNa01 | DNa02 | MDN |
|---|---|---|---|---|---|---|
| LC4 + LPLC2 | 1 | 2 | 1 | 2 | 2 | 2 |
| LC10a | 2 | 3 | 1 | 2 | 2 | 2 |
| C2 / C3 | 3 / 3 | 4 / 3 | 3 / 3 | 3 / 3 | 3 / 3 | 3 / 3 |
| ORN attractive (DM1, VA2, DM4) | 3 | 4 | 3 | 3 | 3 | 3 |
| ORN aversive (DA2, V) | 3 | 3 | 3 | 3 (4 at N>=5) | 3 | 3 |
| Head GRN | 2 | 3 | 2 (3 at N>=5) | 2 | 2 | 2 (3 at N>=5) |
| R7/R8 | 3 | 4 | 3 | 3 | 2 (3 at N>=5) | 3 |
| R1-R6 | 4 | 4 | 4 | 4 | 3 (4 at N>=5) | 4 |

Strength over 3 hops (N>=3, mass units; selection): LC4+LPLC2 -> DNp01 7.6e-5, DNp09 2.4e-5, DNa01 1.3e-5. LC10a -> DNa02 7.2e-5, MDN 4.8e-5. Head GRN -> MDN 2.9e-6, DNa01 2.5e-6. Thermo -> DNp09 7.8e-6. ORN all -> DNa02 4.6e-7, MDN 4.9e-7. R7/R8 -> every output 1e-8 to 3e-7. R1-R6 about 0. So smell and light-from-photoreceptors reach the steering and walk neurons, but 2 to 3 orders of magnitude more weakly than the looming route reaches the Giant Fiber.

Laterality at 3 hops (N>=3, mass from left sources versus right sources onto left and right outputs; `audit/p0_lat.py`). Ipsilateral bias onto DNa02: LC10a 1.7x (L src: L 4.4e-5, R 2.6e-5; R src: R 4.6e-5, L 2.9e-5), ORN all 3.2x for the left antenna (3.5e-7 vs 1.1e-7) but about 1x for the right (2.5e-7 vs 3.2e-7), ORN attractive 3.4x left antenna, none right. LC4+LPLC2 and LC6 show no consistent bias.

Mushroom body outputs [M]. MBON -> output hops: DNa02 1, MDN 1, DNp01 2, DNp09 2, DNa01 2, TTMn 3. Direct MBON -> output edges (N>=3): 19, from MBON26, MBON27, MBON31, MBON32 only (14 at N>=5, 3 types at N>=10: MBON27, 31, 32). So the learned output from the mushroom body reaches the steering and walk neurons directly.

### 2.6 C2/C3 -> central complex -> output (D3) [M]

Central complex = `class=CX` (2,950 neurons, 292 types). Script `audit/p0_cx.py`, `p0_cx2.py`.

- Topology: C2/C3 reach CX in a minimum of 2 hops at N>=3 (89 CX neurons at distance 2, 1,593 at 3, 1,263 at 4, 5 at 5), 3 hops at N>=10. CX reaches DNa02 and MDN in 1 hop, DNp09, DNp01, DNa01 in 2, TTMn in 3. So a 3-hop topological route exists.
- First hops from C2/C3 are lamina cells (L2, L4, T1) and then medulla neurons (Dm19, Dm15, Dm6), i.e. the local optic-lobe circuit, not a parallax read-out stream. The first CX neurons reached are FB8B, ExR5 and IbSpsP.
- Strength through CX versus controls (N>=3; mass reaching outputs after arriving at CX at hop 3 and then 3 more hops):

| Source (n) | Mass into CX at hop 4 | Via CX to outputs (arrive 3, +3) |
|---|---|---|
| C2 + C3 (3,524) | 1.8e-5 | 1.1e-10 |
| Tm1 (1,777) | 4.9e-5 | 3.4e-10 |
| Mi1 (1,773) | 1.5e-4 | 1.1e-9 |
| T4a (1,684) | 1.6e-4 | 1.6e-9 |
| LC10a (275), a known visual-to-central-complex stream | 2.7e-3 | 8.6e-8 |
| LC4 + LPLC2 (311) | 4.4e-4 | 8.7e-9 |
| R7/R8 (2,714) | 3.6e-4 | 3.0e-9 |

C2/C3 are the lowest of all sources tested, 1,000x below LC10a, and their direct (non-CX) mass onto outputs (1.3e-6 at 3 hops) is 4 orders larger than the via-CX mass. A route exists on paper, but it is not specific to C2/C3 and carries about 1e-10 of mass.
- Literature: Triphan et al. 2016 (Sci Rep): inactivating C2 or C3 gives hyperactive climbing, depolarising them reduces climbing frequency, and the gap-width estimate uses parallax motion; **verified (abstract level)**. This is a behavioural suppression of climbing by C2/C3, not a jump. The central-complex link and the other gap citations were not found online by me in this session, but the user supplied the references and confirmed them: **VERIFIED (user confirmed, references supplied by the user)** Pick and Strauss 2005 (Curr Biol 15:1473), Triphan et al. 2010 (Curr Biol 20:663), Triphan et al. 2016 (Sci Rep 6:27000), Krause et al. 2019 (Curr Biol 29(11)). I did not read their content, so the claims they support are not checked here.

---

## 3. What this means for the plan

| Decision | Settled how |
|---|---|
| D7 | Settled: smell, taste, thermo, hygro and photoreceptors exist with counts above. Nociceptors do not exist as an annotated class. Sugar versus bitter identity is also not annotated. |
| D1 | Supported: feature neurons (LC4, LPLC2) reach the Giant Fiber at 1 hop and strength 1.7e-3; photoreceptors reach outputs at 3 to 4 hops with 1e-8 to 1e-7 mass, and their left retina is incomplete (1,112 vs 2,265 R1-R6). A photoreceptor entry is not feasible without a medulla and lobula model. |
| D2 | Phototaxis from photoreceptors is not supported (R7/R8 -> steering outputs 1e-8 to 3e-8). Options with data: an attractive odour at the right antenna (ORN DM1, VA2, DM4, direct MBON and other paths to DNa02, mass 3e-7 and ipsilateral bias only for the left antenna), or LC10a (object-tracking cells; strongest route to DNa02 and MDN at 7e-5, ipsilateral bias 1.7x). Neither has a published target amplitude here; a gain is needed and will be a calibrated scalar. |
| D3 | No honest C2/C3 route. Leave gaps unsolved, or treat a pit as a looming-class obstacle explicitly labelled as not the fly's gap circuit. |
| D6 | k=3, N=5, segmented rule: 15,551 neurons, 592,683 edges, 2.2 ms per step measured. k=4 is 49,739 to 75,852 neurons (about 9 ms per step or more), too slow for training. |

Mechanisms enabled. Looming (as today); food and aversive smell at ORN with per-side input; sensed reward and punishment are possible through taste and thermo -> DAN wiring but not specific (see section 2.3). Ruled out as stated in the plan: photoreceptor entry, a nociceptor-based pain mechanism, a C2/C3 gap mechanism.

---

## 4. Recommendations (D1, D2, D3, D6)

- **D1: feature-neuron entry.** Keep LC4 and LPLC2 as in the plan, label it in the tool. Evidence: photoreceptor entry would need a retina and medulla model (mass 1e-8 to 1e-7 onto outputs) and the left retina is partial.
- **D2: goal cue via a lateralised object or odour, no phototaxis.** First candidate LC10a (275 cells, strongest measured steering route: DNa02 7.2e-5, MDN 4.8e-5) or ORN attractive at the right antenna. Test both on synthetic stimuli in Phase 3 and keep whichever gives a lateral difference at DNa01/02; report the gain as a calibrated scalar. Not verified: that LC10a activity actually drives approach in the fly (from memory: LC10a tracks small moving objects; not checked here).
- **D3: leave gaps unsolved for now.** If something must be done, use looming-style expansion for the pit edge and label it as not a real gap circuit.
- **D6: k=3, N=5, segmented rule plus the whole mushroom body.** 15,551 neurons, 592,683 edges, 2.2 ms/step. If training needs it, N=10 (11,895 neurons, 213,763 edges, 0.83 ms/step) loses 30% of the head taste entries (191 of 273 on a path).
- Reward and punishment (Phase 4): use pharyngeal GRN (9x null onto PAM) as the sensed "sweet" channel only if a source identifies them as sugar neurons; it cannot be confirmed here. Punishment through thermo -> PPL1 (PPL103/104, 4.3e-5 and 4.6e-5) is the strongest route in the data but the hot/cold identity and noxious range are unknown. Alternatively keep dopamine as a flagged invented input for E4 and E5 and say so.

---

## 5. Open questions and unverified items

1. Which of the 275 head taste neurons are sweet and which are bitter. The LB, PhG and taste-peg types are labelled by sensillum, not by receptor. A literature mapping (e.g. from the FlyWire taste papers) could not be verified in this session.
2. Whether thermosensory TRN_VP1m, VP2, VP3a, VP3b are hot or cold cells, and whether hot cells reach the noxious range.
3. Whether any of the unlabelled sensory types (SAxx02, ENS5, GNG643) are nociceptors. The data shows only that they route to PPL1; nothing was checked in the literature.
4. ORN_V as CO2 and its aversive valence (from memory). DL1 and DL5 valence only at snippet level.
5. The plan's gap citations (Pick and Strauss 2005, Triphan 2010, Triphan 2016, Krause 2019) are VERIFIED (user confirmed; the user supplied the references). I read only the Triphan 2016 abstract myself.
6. Speed: plasticity update cost, the real step with spiking Giant Fiber and Hz clipping, and a GPU benchmark at 600k edges were not measured.
7. The graph drops edges that touch unannotated bodies (125.8M of 151.9M rows, mostly weight 1 or 2); this changes sparse-edge counts, but not the N>=5 edges used for the recommended network, except where a retained edge touches only annotated bodies (the cause split was not checked).
8. The strength metric is a mass of normalised weights, not a predicted firing rate. No claim here says the weak routes (1e-7) cannot drive behaviour with a large gain; only that they would need a gain calibrated to a physiological target that is not in hand.

---

## 6. Follow-up: what the dropped weight rows cost (added 2026-10-01)

Scripts: `audit/p0_drop.py` (one streaming pass over all 151,856,684 rows in Arrow record batches via `mcns._edge_batches`, never loaded whole; outputs `audit/drop_per.npz`, `audit/drop_S.pkl`). All numbers in this section are **[M] measured**. No literature number is used in this section.

**Correction to the method notes (line 9) and open question 7.** The "125.83M dropped rows" counted only rows touching an unannotated body. The weight-1 rows with both ends annotated (10.51M) were also left out of the kept graph, because only w>=2 was kept. The true number of rows not in the kept graph is 136.34M (151.86M minus 15.51M kept).

### 6.1 Split of rows and of synapse weight (sum of weights) [M]

Total weight in the file: 311,833,243 synapses. Annotated bodies: 211,577.

| Cause | Rows | Share of rows | Weight | Share of total weight |
|---|---|---|---|---|
| (a) weight 1, both bodies annotated | 10,513,752 | 6.92% | 10,513,752 | 3.37% |
| (b) touches an unannotated body, any weight | 125,828,298 | 82.86% | 186,467,310 | 59.80% |
| (b1) of (b), weight >= 2 | 42,156,131 | 27.76% | 102,795,143 | 32.97% |
| (c) of (b), weight 1 (both causes: weight 1 and unannotated) | 83,672,167 | 55.10% | 83,672,167 | 26.83% |
| Not in kept graph, total (a + b) | 136,342,050 | 89.78% | 196,981,062 | 63.17% |
| Kept (w>=2, both annotated) | 15,514,634 | 10.22% | 114,852,181 | 36.83% |

(b) = (b1) + (c). The disjoint parts are a, b1, c and kept; they sum to 151,856,684 rows and 311,833,243 weight. I read "(c) both" as weight 1 on a row that also touches an unannotated body; those rows are counted in (c) and not in (a).

63% of all synapse weight is outside the kept graph, 60% because a body is unannotated (mostly weight-1 rows: 83.7M). Normalisation is not affected: each post neuron's total input (the denominator of every weight fraction) was summed over all annotated-post rows regardless of whether the pre end is annotated, so kept fractions are fractions of the neuron's true input; dropped inputs are simply absent from the numerator.

### 6.2 Path neurons: input weight lost per cause [M]

Path set: LC4 and LPLC2 (311), the outputs DNp01 (Giant Fiber), TTMn, DNp09, DNa01, DNa02, MDN (14), plus the 196 neurons that sit between them in one hop at N>=5 (an edge LC -> X and an edge X -> output). Each cell is the fraction of the neuron's total input weight, input-weighted mean over the type. DLMn is not annotated and is not in the set.

| Type | n | Total input | w1, both annotated | unannotated pre, w>=2 | unannotated pre, w1 | Lost to annotation (sum of the three) | w 2 to 4 (in stored graph, under N=5) | Kept at N>=5 |
|---|---|---|---|---|---|---|---|---|
| LC4 | 126 | 314,772 | 5.2% | 0.8% | 2.1% | 8.0% | 21.5% | 70.5% |
| LPLC2 | 185 | 363,497 | 9.2% | 0.6% | 2.0% | 11.7% | 34.4% | 53.9% |
| DNp01 (Giant Fiber) | 2 | 43,478 | 0.7% | 5.6% | 7.9% | 14.2% | 1.8% | 84.0% |
| TTMn | 2 | 6,816 | 1.2% | 4.8% | 6.7% | 12.7% | 3.3% | 84.0% |
| DNp09 | 2 | 15,940 | 4.4% | 0.8% | 1.8% | 7.0% | 10.6% | 82.4% |
| DNa01 | 2 | 26,891 | 1.8% | 1.4% | 2.4% | 5.6% | 4.6% | 89.8% |
| DNa02 | 2 | 49,357 | 1.2% | 0.6% | 1.8% | 3.6% | 3.4% | 93.0% |
| MDN | 4 | 21,573 | 4.4% | 0.8% | 2.4% | 7.6% | 11.1% | 81.3% |
| 196 intermediates | 196 | n/a | 3.9% | 1.1% | 2.4% | 7.4% (per neuron 2.3% to 23.2%) | 10.2% | 82.4% (lowest single neuron 47%, an LC31b) |

The w 2 to 4 column is removed by the N=5 threshold, a design choice separate from the annotation problem. LC4 and LPLC2 inputs come from the optic lobe, which is not in the unified network (the synthetic looming stimulus replaces it), so their losses do not alter the simulated circuit.

### 6.3 Were any path edges dropped? [M]

- Every neuron above is annotated, so no edge between two of them can have been dropped for an unannotated end. The only annotation-side loss for an edge between two path neurons is weight 1.
- Weight-1 edges among path neurons: 11,983 (10 LC -> output, 2,558 LC -> intermediate, 53 intermediate -> output, the rest among other path pairs). All are under N=5 anyway.
- Direct LC4/LPLC2 -> output edges in the stored graph: 330 at N>=2, 323 at N>=3, 310 at N>=5. So 20 of 330 direct edges are lost to N=5, plus 10 weight-1 edges never stored. Not checked here: which of the 20 carry the Giant Fiber input.
- The lowest-retention path neurons (LC31b, SAD011) keep 47% to 54% at N>=5 and are small intermediates (436 to 3,118 total input).

### 6.4 Verdict

**VERDICT: k=3, N=5 is SAFE for the escape and motor path.** The outputs keep 81% to 93% of their input weight at N>=5. Annotation losses are 3.6% to 14.2% per output, the largest on the Giant Fiber (14.2%: 5.6% from unannotated bodies at weight >= 2 and 7.9% from weight-1 unannotated bodies). No edge on the LC -> GF -> TTMn path was removed for being unannotated. One item to watch: the 5.6% of GF input (4.8% for TTMn) that comes from unannotated bodies at weight >= 2 may include real inputs that the model lacks; which bodies they are was not checked. The whole-brain 63% figure does not transfer to this path.

### 6.5 Summary

1. Of 311.8M total synapse weight, 63.2% is outside the kept graph: 3.4% weight 1 between annotated bodies, 33.0% unannotated with weight >= 2, 26.8% unannotated with weight 1 [M].
2. Correction: 125.83M is the unannotated count only; 136.34M rows (89.8%) are not in the graph [M].
3. Normalisation uses true total input, so losses lower retained mass without rescaling kept weights [M].
4. DNp01 loses 14.2% of input to annotation (5.6% at weight >= 2), TTMn 12.7%, other outputs 3.6% to 7.6% [M].
5. LC4 and LPLC2 lose 8% and 12% to annotation; their upstream is replaced by the stimulus [M].
6. 330 direct LC -> output edges at N>=2, 310 at N>=5; none dropped for annotation [M].
7. N=5 removes 2% to 11% of output input and 22% to 34% of LC input (weight 2 to 4) [M].
8. VERDICT: k=3, N=5 is SAFE; the GF path is intact; watch the 5.6% of GF input from unannotated w>=2 bodies.
9. Gap citations (Pick and Strauss 2005, Triphan 2010, Triphan 2016, Krause 2019) are marked VERIFIED, user confirmed; I did not read their content.
10. All counts are measured; no literature number is used here.
