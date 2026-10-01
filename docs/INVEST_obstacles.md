# INVEST: obstacles under bio_strict + calibration (e9ca06f)

Investigation only. No code, config, test or project changed; traces and queries are in untracked `audit/`
(`diag_trace.py`, `pre_query.py`, `pre_sum.py`). Setting: honest_1 #36 + `bio_strict` + 40 deg calibration, 20 seeds from 1000.
**Literature confidence:** *V* = looked up online during this sprint, at abstract/summary level (please still cross-check);
*M* = from memory, not verified; *L* = low. Connectome numbers are synapse counts from the MaleCNS v1.0 weights file
(`audit/pre_edges.pkl`, presynaptic partners of the target cells, 54,013 edges). Counts are synapses, not weights in the model.

## 1. Pits
**What the real fly does.** A walking fly meets a gap by visual and tactile assessment: it reaches, and climbs across only gaps its body
can span (Pick & Strauss 2005, *M*; Triphan et al. 2010 / 2016 on visual targeting and the decision to cross, *V*). That is a
*walking/leg* decision tied to the central complex and the mushroom body, not an escape take-off. The visual cue is a static ground
edge and a far target, not an expanding object.

**What the connectome offers.**
- The take-off effectors have no visual input at all: TTMn 0 % visual presynaptic, DLMn a/b 0 %, DLMn c-f 0 %, GFC1-4 0 %. They are driven by VNC
  interneurons (TTMn: IN13A022 987, IN21A026 507, GFC2 481; DLMn: IN19B067/IN19B043/IN03B089/IN06B066) and by DNs.
- The visual routes into DNs are looming/size cells: DNp01 (GF) <- LC4 6,362, LPLC2 4,862; DNp02 <- LC4 4,209; DNp04 <- LC4 11,597,
  LPLC2 3,398, MeVP53, PVLP046; DNp06 <- LPLC1 2,773, LPLC2 1,719; DNp03 <- LPLC4 3,740, LPLC1 3,602; DNp05 <- LPLC4 1,431, LC22;
  DNp11 <- LC4 3,666, Tm4 1,480, LPLC1 1,041, LC9 958; DNp09 (walking) <- LC9 1,977, LC31a 763.
- None of these respond to a static edge or to the absence of floor; a pit does not loom. The only edge-sensitive cells in the list are LC9
  and LC31a (to the walking DN DNp09), and I do not have a verified claim that they signal gaps.

**Verdict.** There is **no honest route from a pit to a jump** in this circuit. The cue exists in a real fly but belongs to a different
(walking/climbing) system whose neurons we do not simulate. If a pit is to be perceived, the only defensible form is a *perception
module* that feeds LC9/LC31a-class cells a ground-edge stimulus and lets DNp09/steering respond; whether that produces an A press is then
the circuit's business, and the expected answer is that it won't.
Validate on a synthetic floor: a static edge ahead of a stationary fly, a moving edge vs a no-edge control, real vs shuffled; the readout is
LC9/LC31a rates and DNp09, not the game. **"Our code doing the work" risk: high** (any mapping of "pit" to a press is us).

## 2. Pipes and walls (wall-looming route on, x ~ 700, 5 real seeds: 1002, 1003, 1006, 1010, 1016)
- The wall (4 tiles) is perceived from 6 tiles out; theta_wall rises to ~3 rad. On the approach the GF spikes and phasic A presses
  (32-50 frames) occur, with jumps up to ~86 px high: **the wall does drive a phasic A press on approach**.
- At the wall (x ~ 722) the stimulus is static (theta 2.32 rad): TTMn sits at a tonic 16-22, GF spikes continuously (800-1,200 frames), but
  the A press is only 1-frame taps (36-58 presses in 2,000+ frames, hops of 25-44 px). The 30-frame adaptation baseline absorbs the tonic
  drive, so there is no sustained climb. A real GF also needs a *changing* size; a stationary wall is not a looming stimulus.
- **Real-fly basis.** Obstacle/landing responses use LPLC1-type cells and other DNs (Ache et al. 2019 on landing and state-dependent
  decoupling, *V* for the existence of landing DNs, *M* for details); wing/leg-driven approach to a surface uses optic-flow cues
  (small-field optic-flow VPN preprint, *V*, not peer reviewed). Flies climb obstacles by leg-driven climbing, not by jumping.
- **Candidates:** LPLC1 -> DNp06 (2,773), DNp03 (3,602), DNp11 (1,041); LPLC4 -> DNp03/05; LC22 -> DNp03/05. These DNs are not the
  GF; whether they reach leg/wing premotor cells is not established here.
- **Honest route:** let LPLC1 receive the wall's expansion (it already is a looming-class cell) and read DNp06/DNp03/DNp11, then map their
  *circuit* activity to the existing muscle readout. **Risk: medium-high**, because the mapping from those DNs to "jump now" is
  currently ours. Validate on a synthetic expanding bar/square that stops growing (hold at theta 2.3): the output must be
  a transient, then decay, and must differ between real and shuffled; the game is not used.

## 3. The 4 real seeds that die at the first Goomba (1001, 1004, 1014, 1015; max_x 299-302)
Per-stage trace (as in DIAG_bio_strict_escape):
- The latch is gone: rest TTMn 0.01. The GF fires only at enemy dx 38-46 px, ~0.6 s before contact.
- A is pressed and the jump is ~50 px, so the escape circuit **does** act; it is not a missing-spike failure.
- The failure is in *direction*: aversive odour sets direction left in 51-74 % of frames 90-175, so Mario flees left to x -> 0 and is hit
  when landing close to the screen edge (dx 8-13).
- 1001 survives, but ends stuck at the left edge, held by food odour from the "?" block (odor_l up to 2.9 vs home_bias 1.0).
So the cause is steering/odour, not escape. Item 4 is where it can be addressed.

## 4. Steering vs odour
- **Is odour overriding forward walking plausible for a hungry fly?** Partly. Hungry flies are more attracted to food odour and walk
  upwind to it when wind-borne odour is present (Álvarez-Salvado et al. 2018, *V*; hunger modulation, Root et al. 2011 and others, *M*).
  But attraction to an odour that is *behind* the fly on a side-scroller screen has no wind to go with; the plausible behaviour is a turn
  towards it, not a permanent stop at the left edge.
- **What `home_bias` is biologically.** Nothing. It is an invented scalar (1.0) that biases direction to the right, i.e. a goal heading.
  The nearest real structure is a central-complex goal heading acting on the steering DNs (PFL3 -> DNa02), but connectome evidence for
  that route is small here: PFL3 supplies only 736 of DNa02's 49,357 inputs (1.5 %), and DNa01's largest inputs are VES007/LT51/VES074, so
  a CX heading signal is not dominant. I cannot support "home_bias is the CX goal" from this data.
- **Options (no tuning on game outcomes):**
  1. Keep home_bias and flag it as invented (status quo, honest but not derived).
  2. Represent the rightward goal as a heading signal fed to PFL3-class cells (CX heading vs goal), and read DNa02; the goal itself stays
     an invented scalar, but the mechanism is real. Risk: medium.
  3. Make odour a gradient, not a scalar: use left/right odour difference between the antennae (bilateral comparison, *M*) so odour from
     behind produces a turn but not a stop. Risk: medium; the sign of the difference is a perception change, not a decision.
  Validate on a synthetic odour source at fixed bearing and distance, no enemies: measure heading vs time for real and shuffled.

## 5. Summary table
| item | honest route exists? | validation (synthetic) | risk of "our code doing the work" |
|---|---|---|---|
| pits | **no** for a jump; only a ground-edge perception to LC9/LC31a/DNp09 | static edge vs none, real vs shuffled | high |
| walls | partly: transient on approach already works; sustained climb needs a non-GF route | stopped-expansion stimulus, transient then decay | medium-high |
| first-Goomba deaths | cause is odour direction (item 4), not escape | n/a | n/a |
| steering/odour | options 2 or 3 are justifiable; none is derived from the connectome | fixed odour source, heading vs time | medium |

**Not claimed:** that LPLC1-linked DNs drive a jump or climb; that LC9/LC31a signal gaps; any literature detail marked *M*.
