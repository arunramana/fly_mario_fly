# Candidate mechanisms

Fly circuits not yet built, with what each would buy Mario. One entry per
mechanism. **Nothing here is implemented** — this is the queue, and the
connectome check comes before the code every time.

Built already: escape (DNp01→TTMn), climbing/terrain, steering (DNa01/02),
DNp09 speed gating, odour + hunger, habituation + MDN, mushroom body.
See `docs/RUNS.md` for what each one actually did.

---

## 1. Aversive odour — replaces looming

**Circuit.** Labelled lines: geosmin → Or56a, CO₂ → Gr21a/Gr63a. Hard-wired
aversion, no learning. ORN → glomerulus → projection neurons → **lateral horn**,
which is the innate-valence structure. (Mushroom body is learned valence; the
two read the same olfactory input in parallel.)

**Mario.** A Goomba becomes an odour source whose concentration rises as it
closes. Aversion drives flight.

**Why it matters most.** It sidesteps the geometry problem entirely. Odour is a
scalar falling off with distance, and distance is already in RAM — no `arctan`,
no egocentric render, no radial pooling. And a gradient **rises smoothly from
far away**, which is exactly the early warning the Giant Fiber structurally
cannot give (011: theta rises for ~15 frames, TTMn crosses in the last 2–3).

**Build first.**

---

## 2. Evidence accumulation — pC1

**Circuit.** 85 neurons, described as "a small recurrent web that builds up a
decision," driving real descending neurons (pC1a→DNp37, pC1d→DNa11).

**Mario.** Integrate threat across the whole approach instead of thresholding
the current frame.

**Why.** This is a genuinely different decision mechanism from a reflex
threshold — a ramp to commitment rather than a comparison. It is the direct
answer to the late-commit problem that DNp02 failed to solve in 012, arriving
through a circuit actually built for it rather than a second copy of the same
reflex.

---

## 3. Efference copy

**Circuit.** A copy of the motor command is sent to the visual system to cancel
self-generated visual motion — how a fly distinguishes "the world moved" from
"I moved."

**Mario.** Separate *"a Goomba is closing on me"* from *"I am sprinting into a
Goomba."* Identical θ traces today; they should carry completely different
urgency.

**Note.** Cheap to compute (we already have DNp09's commanded speed), and it
makes every other threat signal better rather than adding a new one.

---

## 4. Persistent internal state

**Circuit.** P1-style arousal that outlasts its stimulus by tens of seconds.

**Mario.** Stay vigilant for a while after a near-miss instead of resetting
every frame.

**Note.** Gives context-dependent thresholds without adding a scalar — the state
does the modulating.

---

## 5. Odour braking — the missing half of approach

**Circuit.** Walking flies **decelerate** as odour concentration rises.
Approach is steering *plus* braking; we built only the steering.

**Mario.** Rising odour inhibits DNp09, so Mario slows near a `?` block instead
of sprinting past it. This is why he never hits the first one on 1-1.

**Check first.** Is there a real path from the odour pathway onto DNp09, or an
inhibitory population presynaptic to it? If the anatomy isn't there, say so
rather than inventing a brake.

---

## 6. The refusal rule — terrain's other half

**Circuit.** The terrain rule is two-sided and body-scaled: *"steps up anything
about half its body height, **and stops at a face taller than that**."* We
implemented the climbing half only.

**Mario.** Gap wider than a body-scaled reach → don't attempt, brake at the
edge. Small and big Mario are different animals, as the climb reflex already
knows.

**Evidence.** 1-3's 8-tile pit: DLMn fired correctly at 12.6 and Mario died
anyway. The decision was right, the body couldn't deliver — a refusal rule
would have stopped him.

**Caveat.** Refusing only helps if there's an alternative. That section is
crossed on the moving elevator platforms, which is a mechanism the fly does not
have.

---

## 7. Optomotor slip detection

**Circuit.** HS/VS wide-field motion cells compare visual motion against
intended motion.

**Mario.** Real stall detection, replacing the frame-counting hack currently in
the climb reflex (`CLIMB_STALL_FRAMES`). "I am commanding forward and the world
is not moving" is a measurement, not a timeout.

---

## 8. Real vision — **blocked**

**Circuit.** Photoreceptors (hex array, ~800 ommatidia) → lamina ON/OFF
contrast → medulla delay lines → T4/T5 Hassenstein–Reichardt correlators →
LPLC2 pooling outward-radiating motion. Looming falls out of **dendritic
geometry**, not code.

**Mario.** Pixels in, θ out. Would also restore **retinotopy** — LC4/LPLC2 have
no `assignedOlHex`, but the columnar cells feeding them (TmY3 and friends) do.

**Why blocked.** The NES view is third-person side-scrolling. A Goomba walking
toward Mario translates horizontally; it does not expand. T4/T5 would report
pure translation, LPLC2's radial pooling would stay silent, the Giant Fiber
would never fire. Needs an egocentric render first — at which point we are
drawing the fly's input, not reading the game's.

**Also.** ~81k optic-lobe neurons is the one place in this project where the
GPU earns its keep (9.6 ms/step on CPU at that scale).

---

## Not building: ranged attack

pC1 → DNp37/DNa11 gives a real **lunge**, which maps cleanly onto stomping —
targeted and committed, the opposite of escape's omnidirectional panic, and
naturally gated on power-up state the way hunger gates odour. But **flies have
no ranged attack**. Nothing in the connectome corresponds to hitting something
you aren't touching, so a fireball driven from pC1 would be an invention. Listed
so the gap is on the record.

---

## Order

1. **Aversive odour** — unblocks early warning without the geometry problem
2. **Odour braking** — small, and fixes a visible failure
3. **pC1 accumulation** — the real attack on late commitment
4. **Efference copy** — makes the threat signals above sharper
5. Refusal rule, persistent state, optomotor slip
6. Real vision — only after an egocentric render exists

Each entry gets a connectome check before any code. Twice now (LPLC1 in 007,
DNp02 in 012) the anatomy has said no to something the behaviour literature
implied, and both times that was the finding.
