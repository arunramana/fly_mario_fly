# Run log

One entry per run, newest at the bottom. Four fields, always the same four.
Append after every behaviour-changing sprint — never edit an old entry to make
it look better, including the ones that failed. The failures are why the later
runs work.

Videos and per-run notes for runs 001-026 live in `projects/legacy/runs/`,
their telemetry CSVs in `projects/legacy/telemetry/` (REFACTOR_PLAN.md
phase 1 — moved, paths below rewritten, nothing else changed).

---

## 001 — first jump (`projects/legacy/runs/mario_jump.mp4`)

**Setup.** 313 neurons: LC4 (126) + LPLC2 (185) → DNp01 (Giant Fiber, 2) →
TTMn (jump muscle, 2). Enemy positions from RAM `0x0087–008B`, converted to
angular size θ = 2·arctan(w / 2d). Hold right, one bit of control: press A.
g = 3.5, rate dynamics, ReLU.

**What happened.** Mario jumped 9 times over 582 frames. Looked completely
convincing on video.

**What we learned.** The circuit was dead. Telemetry showed `LC4_mean` and
`LPLC2_mean` constant to three decimals from frame ~100 — identical with a
Goomba at 112px and with no enemy on screen at all. TTMn pinned at the 50.0
clip ceiling. The presses correlated with neither DNp01 nor TTMn. g=3.5
saturated the network within 100 frames under sustained input, and the
single-ramp diagnostic never caught it because it only tested one transient
from rest. **A video that looks right is not evidence.** Led directly to
Diagnostic 4.

---

## 002 — the brain overlay (`projects/legacy/runs/mario_with_brain.mp4`)

**Setup.** Same run as 001, re-rendered with a live-brain panel: 141,781 real
soma positions from `somaLocation`, projected x (left–right) against z
(brain → nerve cord). Brightness = population mean.

**What happened.** The full CNS silhouette, with LC4/LPLC2 lighting up inside
the optic lobes and TTMn down in VNC segment T2 — where those cells actually
are.

**What we learned.** The overlay paid for itself immediately: putting θ and
TTMn on the same time axis is what made 001's saturation visible at a glance.
Every run since carries the panel. (`brain_panel.py`)

---

## 003 — Diagnostic 4 and the honest jump

**Setup.** Circuit expanded to 1,255 neurons via a sign-agnostic threshold
(every neuron with ≥60 synapses onto LC4/LPLC2/DNp01), after discovering that
DNp01's real input is 35.8% inhibitory and we had excluded all of it. Input
coverage went LC4 7%→35%, LPLC2 13%→24%, DNp01 26%→67%. E/I balance flipped
from ~100% excitatory to 51.6/45.2. Diagnostic 4 added: a ≥2,000-step trace
with gaps, asserting detectors still track θ, nothing sits clipped, activity
returns to baseline, and A fires *iff* TTMn is over threshold and DNp01 spiked.

**What happened.** One legitimate jump. Detectors tracked θ monotonically and
returned to exactly zero in the gaps.

**What we learned.** Three things. The "winner-take-all recurrence" reading was
wrong — LC4/LPLC2/DNp01 are 100% cholinergic, so that recurrence is an
amplifier, not competition, and the system was linear across its whole range.
The missing inhibition was in the data, not missing from the fly: **PVLP011 and
LPi21**, one neuron per hemisphere, each touching ~100% of that hemisphere's
LPLC2 and zero on the other — the wiring diagram for divisive normalisation.
And the fly commits when the Goomba is at `d_px ≈ 0`: escape fires when a
threat is imminent, which is correct for a fly and too late for Mario.

---

## 004 — three controllers, g = 1.5 (`projects/legacy/runs/004a,b,c`)

**Setup.** A = real circuit at g=1.5 (chosen by a Diagnostic-4 sweep),
B = best of 20 degree-preserving shuffles at its own tuned g=3.0,
C = one-line baseline `θ > 1.125`. 3 levels × 3 seeds × 3 controllers.

**What happened.** A died at 8–41 frames on all 9 combinations. C was
**byte-for-byte identical to A**, every row. B survived 4000 frames on 1-1 and
1-2. On 1-3, all three died at exactly 30, 41, 38.

**What we learned.** Three separate things, two of them methodological.
**1-3 is an invalid test level** — when every controller including the shuffle
dies identically, it isn't about control: those are pits, and a looming
detector cannot see the absence of ground. **A ≢ B was confounded by gain**
(1.5 vs 3.0), not by wiring. And **A ≡ C** held here and in the earlier clean
run, on both sides of a known bug — the 1,255-neuron circuit and a scalar
threshold produce the same button presses.

Shuffle sweep, same Diagnostic-4 procedure on all 21 networks, grid 0.05–25:
**8/20 shuffles found a passing g, 12/20 found none anywhere.** ρ(W) at g=1 was
**0.821 real vs 0.302 ± 0.029** for shuffles — 17.8 SD, no shuffle above 0.386.
Degree-preserving rewiring collapses recurrent gain ~2.7×.

---

## 005 — the 2×2 and the rerun at g = 2.0 (`projects/legacy/runs/005a,b,c`)

**Setup.** 2×2 first: A at g=1.5 and g=2.0, each with and without the warm-up,
to separate "the gain is wrong" from "the warm-up drops Mario on a Goomba."
Then the battery rerun at the winning gain, 1-3 dropped, parallelised across
`Pool(8)`.

**What happened.** g=2.0 survives with *and* without the warm-up. And in the
rerun, **all three controllers survive all 4000 frames on every level and
seed** — A 2 jumps, B 2 jumps, C 2 jumps on 1-1; C takes 1 on 1-2 where A and
B take 2.

**What we learned.** The warm-up was never the bug — **g=1.5 was**, exactly as
the 2×2 predicted. Diagnostic 4 passed a gain that cannot play, which means it
tests responsiveness and saturation but **not timing competence**; that's a gap
in the test, not just in the gain.

And the deflating half, stated plainly: **at g=2.0 the real circuit, a shuffled
connectome, and a one-line θ threshold are behaviourally indistinguishable.**
1-1 and 1-2 with hold-right plus a jump reflex are survivable by any reasonable
controller, so the battery has no discriminative power. The only place the real
wiring wins is structural — 12/20 shuffles can't be tuned to work at all, and
ρ = 0.82 vs 0.30. **What the circuit computes is trivial; that the fly's wiring
can compute it where most random wiring can't is the actual finding.**

---

## 006 — steering (`projects/legacy/runs/006_steering.mp4`)

**Setup.** New 329-neuron circuit: DNa01/DNa02 plus their N≥60 inputs,
winner-take-all between hemispheres picking left/right every frame. Replaces
hardcoded hold-right with a computed output. Home bias = 1.0 pulling right,
mushroom odour (1/distance) competing against it, contact-based climb reflex
(stall detection → hop, escalating to full jump, gated on Mario's size).
Jump circuit untouched. G_STEER = 1.2.

**What happened.** Steering works — direction is computed, not hardcoded. The
climb reflex fired 6 times (1 hop, 5 escalated jumps) with 2 harmless conflicts
against the escape pathway. A synthetic powerup 40px behind Mario produced a
measurable bump in DNa01/DNa02 but **never flipped the decision**. Died at
frame 1138, wedged on an obstacle the climb reflex couldn't clear — worse than
the hold-right baseline on this seed.

**What we learned.** Odour at 1/40 against a constant bias of 1.0 was never
going to win — but shrinking the bias is the wrong fix, because it makes Mario
permanently distractible. The fly's own answer is **hunger** (540 neurons): a
gain that rises with need, so a small hungry Mario is pulled by the mushroom
and a big sated one isn't. Two independent circuits competing for one button is
the real descending-neuron conflict, and it showed up on the first run. Dying
earlier is expected — steering gives the controller the ability to make
mistakes it previously couldn't make.

---

## 007 — terrain: pits, graded takeoff, and speed (`projects/legacy/runs/007_terrain.mp4`)

**Setup.** Tile RAM decoder (`tile_ram.py`) for `Block_Buffer_1`/`_2`
(`0x0500-0x069F`, 13x16 row-major each). Tile IDs were NOT taken from a web
table on faith — two disagreed with each other (one said `?` blocks are
`0xC0`/`0xC1` with `0xC2`/`0xC3` as coins, another claimed the reverse).
Resolved against the actual SMB disassembly's `Palette3_MTiles` graphics
table and cross-checked frame-by-frame against real screenshots: ground =
`0x54`, `?` block (coin) = `0xC0`, `?` block (power-up) = `0xC1` — the
original guess of `0xC2`/`0xC3` was wrong. New circuit: DNp01's real
downstream relay to the wing motor neurons, found (not invented) by
querying the connectome directly — zero direct DNp01->DLMn synapses, but
144/112/107/97 synapses onto GFC1-4 (the literature's "Giant Fiber
Circuit" interneurons) and 80 real GFC1-4->DLMn edges. A pit's `gap_width`
adds current directly to DNp01 (both hemispheres, unlateralised — a pit
ahead isn't a left/right thing), `GAP_GAIN=0.6`; TTMn alone still gives the
existing short hop, TTMn+DLMn crossing `DLMN_RECRUIT_THRESHOLD=1.0` gives a
longer hold (`LONG_JUMP_HOLD_FRAMES=35` vs 25). Separately, DNp09 (own
25-neuron N>=60 subgraph, `WALK_DRIVE=1.0`, `G_SPEED=1.2`) now gates B
instead of it being held permanently, suppressed during any jump or
contact-stall. The existing contact-based climb reflex (006) now checks
`tile_ram.solid_ahead` before firing, so a stall in front of a pit defers
to DNp01/DLMn instead of wasting a hop on empty air.

**What happened.** A real 2-tile pit in 1-1 (frame ~476) drove DNp01 hard
enough to recruit DLMn (peaked at 1.08, over threshold) and triggered the
long jump — the pit was cleared. One climb hop + two escalated climb jumps
fired earlier at real obstacles, zero conflicts with the escape pathway.
DNp09 visibly gated B: it drops during every jump/stall and chatters
(on-off-on) for a few frames while resettling afterward, instead of C's
"always running" default. Mario died at frame 565 to what the telemetry
shows as an ordinary Goomba encounter (LPLC2/DNp01 elevated, DLMn back at
zero) — unrelated to any of this sprint's new circuits, which had already
done their job earlier in the same run. Items 4/5 (`?`-block odour +
hunger gating) were not attempted — 1-3 alone left no room to spare.

**What we learned.** **DNp01's spike amplitude is fixed — always the same
50.0, every spike, no exceptions — and the graded jump-vs-flight decision is
carried entirely by spike RATE instead, which is what the GFC1-4 relay
actually reads.** A wider gap doesn't make any single DNp01 spike bigger; it
keeps DNp01 crossing threshold faster and more often, and that higher rate
of closely-spaced, identical spikes is what integrates into a correspondingly
higher GFC/DLMn level downstream. This is the same graded-from-binary trick
real spiking neurons use to encode a continuous quantity on an all-or-none
signal, and it only showed up here because DLMn was fed DNp01's real
substep-by-substep spiking output rather than a once-a-frame average — this
is the strongest result in the project so far.

Also: a synthetic Block_Buffer edit does NOT force the PPU to redraw
already-displayed columns, so "poke the tile buffer and screenshot it" only
works for tiles not yet drawn — a real organic pit encounter was needed for
a visually honest test, unlike 006's mushroom (a live sprite object, which
*does* redraw every frame).

## 008 — odour that can win, and does the long jump generalise (`projects/legacy/runs/008a,b,c`)

**Setup.** Fixed the actual bug behind 006's "odour never wins": a mushroom
at 40px gave `concentration=1/40=0.025` against `HOME_BIAS=1.0` — a 40x
mismatch in units, not a subtlety. `ODOUR_GAIN=16` brings a close encounter
(~16px) into `HOME_BIAS`'s own range; picked by simulating the real
DNa01/DNa02 circuit directly (`tune_odour.py`), not by guessing. `HOME_BIAS`
itself was left untouched, per instruction — it stays a pure direction
signal, with `DNp09`/`speed_circuit.py` (007) still the only source of
drive, unchanged and unwired to this fix. Added `?`-block odour (same
`1/distance` mechanism, sourced from `tile_ram.question_blocks_near`,
converted from tile-column offsets to pixels) and hunger gating
(`HUNGER_MULT_HUNGRY=3.0` when `RAM 0x0756==0`, `SATED=1.0` otherwise) on
**both** odour sources. Then re-ran the pit-clearing result from 007 across
all three levels — 1-1, 1-2, **and 1-3**, which the pre-terrain battery
(004/005) had excluded as untestable, since every controller back then died
there identically on pits nothing could see.

**What happened.** The hunger fix works, and produced a genuinely isolated
demonstration, not a hoped-for one: running 1-1 twice with byte-for-byte
identical inputs except Mario's forced size at the moment of the test,
**frame 178 diverges** — hungry: `L_team=4.93` vs `home+odor_r=4.00` →
steers **left**; sated, same frame, same odour source: `L_team=1.64` vs
`home+odor_r=2.00` → stays **right**. Hunger alone is the difference; odour
now actually beats `HOME_BIAS` when it's supposed to, and doesn't when it
isn't. `?`-block odour fires correctly but (as flagged going in) is
horizontal-only — it can pull Mario to stand under a block, not hit it from
below; that second stage still belongs to the climb reflex.

The pit-generalisation test is where this sprint earned its keep by not
looking away from a bad result. **1-1 and 1-2 hit zero real pits** in 2500
frames each (steering plus the new long-jump's much longer air time changes
Mario's whole trajectory, so he never reaches the spot 007 found a pit at
with a simple hold-right run) — but the long-jump pathway still fired
constantly: **18 of 32 escape jumps on 1-1, 23 of 33 on 1-2**, every single
one logged at `gap_width=0`. DLMn is crossing `DLMN_RECRUIT_THRESHOLD=1.0`
from ordinary Goomba-triggered DNp01 spiking alone — sometimes reaching 7-9,
far past the ~1-3 range 007's calibration measured from gap-current in
isolation. **1-3 had exactly one real pit**, 8 tiles wide, at frame 84.
DLMn peaked at 12.60, the long jump fired correctly (hold=35) — and Mario
**died anyway**. An 8-tile gap is wider than anything 007 calibrated
against (up to 4 tiles), and the graded response didn't scale far enough.

**What we learned.** Two honest results, not one. First: the long jump does
**not** reliably generalise — the one real pit encountered outside 1-1 was
wide enough to beat it outright, and 007's single successful clearing was
against a narrower gap than the game actually contains. Second, and more
important: **the DLMn pathway isn't actually pit-specific in this build.**
It reads "how vigorously did DNp01 fire," and an intense Goomba encounter
fires DNp01 just as vigorously — via the same real GFC1-4 relay — as a
calibrated pit stimulus does, so most of the "long jumps" logged this
sprint had nothing to do with terrain at all. That's not a bug to quietly
patch; it's what you get from wiring a real graded relay to a real spiking
signal and *not* also gating the outcome on the specific sensory cause —
the connectome doesn't know or care why DNp01 fired, and neither does GFC.
Whether that's a problem to fix (gate long-jump on `gap_width>0`
explicitly) or a finding to keep (a sufficiently threatened fly might
genuinely recruit flight muscle regardless of *why* it's threatened) is a
real design question for the next sprint, not a call to make quietly here.

## 009 — the used-block bug and ORN adaptation (`projects/legacy/runs/009_orn_adapt.mp4`)

**Setup.** Two fixes. First, a real decoder bug: an already-hit `?` block
reads back as `USED_BLOCK_ID=0xC4` in the tile buffer, not `0xC0`/`0xC1` —
added as an explicit, asserted constant in `tile_ram.py` rather than relying
on it being incidentally absent from `QUESTION_IDS`, and confirmed with a
direct unit test (a fabricated RAM buffer with one unused and one used
block) that odour sourcing excludes exactly the used one. (Honest caveat:
several scripted attempts to trigger a *live* block hit in-game to confirm
0xC4 empirically — both timing-swept and RAM-pinned — didn't land the hit;
the value is corroborated by two independent sources, not independently
re-verified in the emulator this sprint.) Second, ORN adaptation: a new
`OlfactoryAdaptation` class in the sensory layer, divisively decaying
sustained odour (`adapted = signal/(1+a)`, `a` a ~1.5s trace of the
gain/hunger-scaled signal, ALPHA_ADAPT=1/90) so a source Mario can't get
away from stops smelling and the never-adapting `HOME_BIAS` takes back
over — implemented entirely upstream of the WTA, per instruction, so the
steering code downstream is unchanged.

**What happened.** The adaptation claim was checked against the real
DNa01/DNa02 circuit, not just arithmetic (`tune_orn_adapt.py`): with a
hungry Mario's odour held artificially constant at a realistic "wedged next
to a source" concentration, the WTA stays on odour forever *without*
adaptation, and returns home at **frame 62** *with* it — `R_team=0.9925`
overtaking `L_team=0.9879` as the effective odour decays from 1.41 to 0.99,
below `HOME_BIAS=1.0`. That's the requested proof, and it holds up.

The live recording surfaced something else, unprompted: from frame 543 to
1499 (956 frames, ~16 seconds) **Mario's x position never left the range
[127, 134]** — a 7-pixel window — while climb-jumping and long-jumping
**13 times each**, logging a conflict on every single one, and never dying.
He is not stuck on odour here — `direction` stays `R` (home wins)
throughout, exactly as it should. He is stuck in the *climb/long-jump*
machinery itself: an obstacle that the climb reflex keeps attempting and
failing to clear, immediately re-triggering `blocked-forward` on landing,
while the same encounter's DNp01 output separately crosses
`DLMN_RECRUIT_THRESHOLD` and fires a long jump on top of it, every ~75
frames, indefinitely.

**What we learned.** ORN adaptation does exactly what it was built for —
and *only* that. It has no purchase on this stuck loop, because this stuck
loop was never about odour. That's not a failure of the fix; it's a
reminder that "the anti-stuck mechanism" was always scoped to one specific
failure mode (a receptor that won't let go), and this sprint accidentally
found a second, unrelated one (a motor reflex that won't stop retrying) in
the same 1500-frame run. Both are real. Neither should be quietly folded
into the other's fix.

## 010 — habituation, MDN, and the bug that was driving the whole investigation (`projects/legacy/runs/010_enemy_thetas_fix.mp4`)

**Setup.** Built generalised habituation (`ReflexHabituation`, one instance
per reflex: any escape or climb trigger that fires without `HAB_PROGRESS_PX`
(16px) of net x-progress since the last time it was checked increments its
own suppression level, capping firing after `HAB_GIVE_UP=3` — a real,
documented Giant Fiber property, not a timeout) and MDN, the backward-
walking fallback (4 bodies, confirmed exactly as stated; own 97-neuron
N≥60 circuit, `mdn_circuit.py`; no direct DNp01/GFC1-4 synapse in this
connectome, so `MDN_DRIVE=2.0` is an external current, same category as
`HOME_BIAS`/`WALK_DRIVE`/`GAP_GAIN` — activated only once escape's
habituation hits `HAB_GIVE_UP`, overriding steering to press left for a
fixed `MDN_BACKUP_FRAMES=30`). `G_MDN=1.2` chosen the same way as every
other circuit gain this project, by simulating the real network directly
(`tune_mdn.py`) — spectral radius 0.7345, clean non-clipped settling.

Tested against 009's exact stuck scenario. Both pieces work exactly as
designed in isolation — habituation measurably cut retries (escape jumps
17→7, climb jumps 14→4), and MDN reliably fired and backed Mario up the
instant escape gave up (frame 773, then 1100, 1450, 2856...). But even
after 4000 frames and two different backup durations (30 and 90 frames),
**the pin never actually broke** — habituation+MDN just converted a tight
75-frame bounce into a stable ~365-frame mega-cycle. Before building
anything further to patch that, two direct diagnostic queries were run
against the live circuit instead of guessing:

1. **The enemy slot driving the stuck-in-place `theta` was the synthetic
   injected mushroom** (`type=0x2E`), not a Goomba — confirmed by reading
   the actual RAM at the pin (frame 600, mario_x=130): the only active slot
   was the mushroom at x=131, d=1px. `enemy_thetas()` (`run_mario.py`,
   unmodified since sprint 1) does zero type filtering — it treats every
   active slot as a threat. A real Goomba eventually gets walked past,
   changing `d`; a static injected test object never does, so it was
   feeding a **permanent, unresolvable fake threat** into the escape
   circuit. This is a bug in the shared function, not a wrapper-fixable
   quirk of one caller.
2. **Wall height at the pin: 4 tiles**, confirmed directly (rows 7-10 solid
   at cols 57-58, ground at row 11). Real SMB fact: small Mario clears 4
   tiles routinely (the 1-1 staircase) — this was never an impossibility,
   only a question of whether the existing hold durations were sized for
   it.

**Fix, and what it actually changed.** `enemy_thetas()` now skips
`ADDR_ENEMY_TYPE`-tagged powerup slots — fixed in `run_mario.py` itself, on
direct instruction, because a wrapper in `run_steering.py` would leave the
shared bug live for every other caller. Re-running 009's exact pin with the
fix: escape jumps at that location drop from 17 to **effectively zero** —
Mario now dies at frame 452, well before ever reaching the contaminated
region, because his trajectory (dominated by genuine odour-vs-home-bias
drift, which is not a bug) diverges too much from the original run to
reach the same spot. The wall itself was separately, directly confirmed
clearable: a scripted approach with a plain 25-frame hold — the *existing*
`CLIMB_JUMP_FRAMES`, unchanged since sprint 006 — crossed cols 57-58
cleanly and kept going for 117+ more frames. **No hold-duration constant
needed to change.** The real problem was never insufficient jump height;
it was that climb's own second (escalated) attempt never got a clean,
uninterrupted shot at firing while a fake, permanent threat was consuming
the shared A button and resetting its retry cadence.

**Scoping the contamination in 008, not editing it.** Re-ran 008's exact
check post-fix: 1-1's reported **18/32 escape jumps escalating at
`gap_width=0` is now confirmed to have been almost entirely the injected
mushroom** — post-fix, escape/long-jump activity in that region vanishes
because Mario dies before reaching it. **1-2's 23/33 does NOT get
corrected away** — re-run gives 22/28, essentially unchanged, and directly
verified via RAM inspection to be driven by a real, near-stationary Green
Koopa Troopa (`type=0x00`, d=+7px) sitting right next to Mario, not the
mushroom (which was d=-95px, harmless, at that frame). **008's core
finding — that DLMn reads DNp01's general vigor, not gap-width
specifically — stands, confirmed by a real enemy independent of any
mushroom.** Only the 1-1 illustration of it was contaminated. **The 006/
008/009 hunger-flip result is unaffected and stated here explicitly, not
left to inference**: both the hungry and sated arms of that comparison ran
byte-for-byte identical inputs, including whatever contaminated `theta`
was present — common-mode between the two compared arms, so it cancels
exactly. Frame 178's divergence (hungry flips, sated doesn't) is real.

**An honest process failure, logged rather than hidden.** While re-running
008's check, a background job was launched with `record_video` left at its
default (`True`) instead of explicitly set to `False` for what was meant
to be a numbers-only check — it began overwriting the already-shipped
`projects/legacy/runs/008a_1-1.mp4` before being caught and killed. The original bytes are
gone; there was no backup. `projects/legacy/runs/008b_1-2.mp4` and `projects/legacy/runs/008c_1-3.mp4` are
untouched. The accidentally-created content was moved to
`projects/legacy/runs/_recovered_postfix_1-1_accidental_overwrite.mp4` rather than
discarded, since it's real (if mislabeled) data. This violates CLAUDE.md's
"never overwrite an earlier run" rule; recorded here in full per the same
rule's spirit rather than quietly patched over.

**What we learned.** The habituation+MDN mechanism was never wrong — the
test scenario it was being validated against was contaminated by an
artifact of an *unrelated* demo (the mushroom injection), and no amount of
tuning a retry-suppression mechanism was ever going to fix a permanently
fake threat. Checking the two most falsifiable underlying facts (what's in
the enemy slot, how tall is the wall) before writing more mitigation code
found the actual bug in about the time it would have taken to tune
`MDN_BACKUP_FRAMES` once more. The wall was never the hard part; a shared,
untouched function silently feeding decorative RAM objects to a threat
detector was.

## 011 — the first uncontaminated baseline (`projects/legacy/runs/011a,b,c`)

**Setup.** Made the synthetic mushroom injection explicit opt-in
(`inject_frame=None` by default, `main()`) rather than a standing default —
it was a diagnostic built for one odour demo (006) and it silently rode
along in every recorded run since, contaminating three sprints' worth of
"real" numbers before 010 found why. Then ran 1-1, 1-2, and 1-3 completely
clean: no injection, `enemy_thetas()`'s fix in place, every other circuit
(habituation, MDN, all of it) left at its real shipped defaults — this is
the system as it actually stands today, not a stripped-down comparison
config.

**What happened.**

| Level | Frames | Escape jumps | Long jumps | Climb hops | Climb jumps | Conflicts | Died |
|---|---|---|---|---|---|---|---|
| 1-1 | 468 | 3 | 0 | 1 | 0 | 0 | yes |
| 1-2 | 728 | 7 | 2 | 1 | 4 | 1 | yes |
| 1-3 | 149 | 1 | 1 | 0 | 0 | 0 | yes |

All three deaths have a clean, unmysterious explanation, checked directly
against telemetry, not guessed:

- **1-1 (frame 468) and 1-2 (frame 728) die the same way**: `theta` climbs
  smoothly and monotonically for the ~15 frames before death (0.26→1.35 on
  1-1, 0.24→1.04 on 1-2) — a real Goomba closing in, not an artifact.
  `TTMn` only crosses `TTMN_PRESS_THRESHOLD` in the last 2-3 frames before
  contact (1-1: 10.5→10.8→[spike, reset to 3.9]→19.3→22.5; 1-2:
  1.2→11.4→13.3) — the escape circuit reacts, but too late to complete a
  jump before collision. This is not a new bug: it is 003's own finding,
  restated with clean data — *"the fly commits when the Goomba is at
  `d_px≈0`: escape fires when a threat is imminent, which is correct for a
  fly and too late for Mario."*
- **1-3 (frame 149) dies at the same 8-tile pit 008 found**: `TTMn` is
  pinned at the clip ceiling (50.0) for the entire visible approach, DNp01
  spiking continuously, the long jump fires correctly (`gap_width=8`) — and
  Mario falls in anyway. Also not new: 008 already established the graded
  long jump was calibrated against gaps up to 4 tiles, not 8.

**What we learned.** With the contamination gone, there is nothing left to
explain beyond what 003 and 008 already found. That is itself the finding:
the fly's circuit has exactly two known, real limits — it commits to a
jump only once a threat is already close (a documented property of the
real Giant Fiber, not a tuning failure), and its graded takeoff response
doesn't scale to gaps wider than what it was calibrated against. Neither
limit is new, invented, or a contamination artifact. **These numbers
replace 006-009's as the real baseline** — anything measured against the
old contaminated runs should be re-checked against this table, not the
old one.

## 012 — the second escape pathway, and a null result that survived widening (`projects/legacy/runs/012a,b,c`)

**Setup.** 011's baseline showed DNp01 committing only 2-3 frames before
contact — correct GF biology, but late. Real flies also have a slower,
non-GF escape that commits earlier with postural preparation. Checked
MaleCNS before building anything: **DNp02** (2 bodies, 10117 R/10197 L) is
the right candidate over DNp04/DNp11 — LC4→DNp02 is 4209 synapses/125
pairs (essentially all of LC4), LPLC2→DNp02 is 5 synapses/4 pairs (noise,
the same bar that excluded LPLC1 originally), and critically, **DNp02→TTMn
is a real, direct, ipsilateral synapse** (21 syn R, 5 syn L) — the only one
of the three candidates with an actual wired path to the jump muscle
(DNp04 has the most complete LC4+LPLC2 coverage of all three but zero
synapse onto TTMn). Built `dnp02_circuit.py` (DNp02 core + N≥60 threshold
partners + TTMn folded in explicitly to capture the real downstream edge)
and wired it to compete with DNp01, not sum with it, logging which pathway
fired and the theta/estimated-frames-to-contact at commit.

**Two real implementation bugs, both caught by symptoms before either
shipped.** First: passing a custom (slow) alpha to `HybridState.step()`
slows the WHOLE state vector, including TTMn's own decay (TTMn sits in
DNp02's subgraph too, for the real synapse) — so TTMn stayed pinned near
the clip ceiling for dozens of frames after a single spike, firing on
stale state with no enemy present. Fixed by moving "longer integration" to
a slow EMA on DNp02's *input* current instead, leaving `HybridState`'s own
step at the normal, fast alpha. Second, found only after the fix, by a
*behavioural regression* rather than a synthetic test: gating DNp01's own
firing on `ttmn_val >= threshold AND just_spiked.any()` (instead of the
original, already-validated `ttmn_val >= threshold` alone) delayed a real
trigger from frame 105 to frame 108 in an actual 1-1 run — by which point
`DLMn` had also climbed past its own threshold, turning what should have
been an ordinary short hop into an unrelated long jump and changing
Mario's whole trajectory from there. TTMn is a leaky accumulator; it can
stay over threshold well after the spike that pushed it there, so
requiring coincident spiking is simply the wrong condition. Fixed by
gating on the threshold alone (matching DNp01's original, validated
behaviour exactly) and using `just_spiked` only for attribution, never for
gating. Re-verified 1-3's post-fix run against 011's baseline: identical,
frame for frame.

**The null result — checked before and after widening, exactly as
predicted.** With both bugs fixed, swept g/threshold/EMA-alpha at N=60 (8
of DNp02's 126 real LC4 partners individually clear that threshold): no
stable, safe combo (g always kept ≤0.85× each circuit's own real
spectral-radius boundary — a fragile parameter is not a result) makes
DNp02 reliably out-commit DNp01 on a slow synthetic ramp. Widened N down
to 30 (77 LC4 partners), 15 (109), and 5 (124, essentially all of LC4):
N=60 and N=5 found no stable win at all; N=30 and N=15 found only a
marginal 1-4 frame lead, and in *both* of those cases DNp02 **also** won
the fast-loom case by more (4-5 frames) — failing the actual requirement,
not just falling short of it. **The prediction stated before widening
(N≥60 might be amputating DNp02's sparse real input the way the original
315-neuron circuit amputated DNp01's) does not hold** — DNp02 lacks any
real LPLC2 (expansion) gate, so once it has enough drive to fire, angular
velocity alone gets it there regardless of ramp speed. There is no real
structural gap to exploit that separates "slow" from "fast" the way the
recruitment was hoped to. N=60 ships (widening didn't help, so there's no
reason to carry the much larger reconstruction); `G_DNP02=1.2`,
`DNP02_SPIKE_THRESHOLD=0.1`, `DNP02_ALPHA=0.1` are safe, unremarkable
values — two more hand-set scalars, taking the budget from 3 to 5,
flagged in the README as CLAUDE.md invariant 3 requires.

**What actually happens in the real game.** DNp02 does fire — 3 times in
1-1, 5 times in 1-2 — but never by winning a race against a concurrently-
firing DNp01. It fires during *gaps*, when DNp01 isn't currently crossing
threshold but DNp02's own slower EMA has kept accumulating. Most of those
commits are far from imminent (estimated frames-to-contact of 50, 58, 108,
162, 204) — DNp02 reads as trigger-happy on a lingering, not-very-close
threat rather than a genuine early warning on a specific closing one. One
commit (1-2, frame 394) came in at an honest 7.4 frames, comparable to
DNp01's own warning window. Because DNp02 firing is real, additional
behaviour (not present in 011), the two runs' survival differs from 011's
own numbers (1-1: 354 vs 468 frames; 1-2: 426 vs 728) — an expected,
honest consequence of adding a second pathway that sometimes actually
acts, not a regression once you check what's actually causing it (both
runs' pre-DNp02-firing trajectories match 011 exactly, confirmed frame by
frame).

**The lateral asymmetry, checked and confirmed real.** DNp02→TTMn is 21
synapses on the right, 5 on the left. Holding DNp02's output at a constant
spiking level on each side independently and reading the settled TTMn
response in isolation: **TTMn_R reaches ~50.0 (full strength) while
TTMn_L reaches only ~35.7 (≈71%)** for the identical input. The
connectome's own wiring asymmetry shows up directly in motor readout
strength — a right-side DNp02 commitment drives the jump muscle harder
than an equivalent left-side one. Not observed as a clean latency
difference in this sprint's game runs (too few left-side DNp02 commits to
compare), but the mechanism is real and quantified, and worth watching for
in future runs with more left-side threats.

**What we learned.** A second, real, connectome-verified escape pathway
was built, correctly wired to compete rather than sum, and both bugs in
its implementation were caught by concrete symptoms (a spurious commit
with no enemy present; a real trajectory that changed) rather than
theoretical review. The actual biological question — does a second,
LC4-only pathway commit meaningfully earlier on a slow threat — has a
clean, negative, connectome-grounded answer: not reliably, because DNp02's
real wiring has no LPLC2 gate to make it selective. It still fires
sometimes, filling gaps DNp01 leaves open, which is its own honest finding
rather than the one it was built to test.

## 013 — making episodes cheap (no video: pure infrastructure, nothing new to watch)

**Setup.** No new circuits. Preparing for a future learning sprint that
needs ~100s of episodes, not single digits. Four levers specified: frame
skip, savestates, headless, `Pool(8)`.

**The actual bottleneck wasn't any of the four.** Timed a single episode
before touching anything: loading all 6 cached circuits (jump, steering,
takeoff, speed, MDN, DNp02) from their on-disk parquet files took **6.8s**
— of a ~7.3s total episode cost. The simulation itself was well under a
second. `main()` was reloading all six from scratch on every single call.
Fixed first, before the four specified levers, because it dwarfed anything
they could contribute on their own: `_memo_load()`, a per-process
memoization cache keyed by circuit name. Repeated `main()` calls in the
same process (or the same `Pool` worker, across many episodes) now pay the
6.8s once. Measured: 7.7s → 1.4s for a second call in the same process —
a 5.3x win from not doing unnecessary work, before any of the four
specified changes.

**The four levers, built and measured honestly:**
- **Headless** already existed (`record_video=False`) — just needed using
  in the benchmark.
- **`Pool(8)`, `OMP_NUM_THREADS=1`** — same pattern `compare_controllers.py`
  already established, with a pool initializer that pays each worker's one-
  time circuit-load cost before the timed episodes start.
- **Savestates** — nes-py's own native `_backup`/`_restore` (a single
  slot), not built here. `main()` accepts an optional `savestate` dict
  (`{"env": <persistent env>, "warmup_frames": N}`); the first call with a
  given env runs the warm-up once and backs it up, every later `reset()`
  restores it instantly. Verified deterministic: two consecutive calls with
  the same backup produced byte-identical telemetry.
- **Frame skip** — implemented as the standard RL action-repeat pattern
  (decision once every `frame_skip` real frames, same action held for the
  frames between). Mechanical hold-duration constants (`JUMP_HOLD_FRAMES`
  and its siblings — already documented since sprint 006 as "output-
  interface, not part of the neural model") are divided by `frame_skip` to
  keep real-world hold durations approximately unchanged; circuit internals
  (`SUBSTEPS`, alpha, thresholds) are untouched.

**Verification requested before keeping frame skip: it does not hold, and
that is the reported result, not a reason to hide it.** Ran 1-1, 1-2, 1-3
at frame_skip 1/2/4. Behaviour is not "substantially unchanged" — it's
**chaotically different**: 1-1 got much worse (354→108 frames at
frame_skip=4, zero escape jumps ever firing), 1-2 got much better
(426→892 frames), 1-3 was unaffected (same pit, same death, every time).
This is a real property of a deterministic system with no RNG: any change
to exact decision timing cascades into a completely different trajectory,
for better or worse, unpredictably. It is not evidence frame skip is
"broken" — it's evidence that a single-trajectory survival comparison is
the wrong instrument for judging it. Reported as a genuine, nuanced
finding: frame_skip is a real throughput lever, not a verified
behaviour-preserving one on any single seed.

**The actual numbers, `bench_episodes.py`, `Pool(8)`, 24 episodes per
configuration:**

| Configuration | episodes/minute | vs. before |
|---|---|---|
| **Before** (cold process, video on, frame_skip=1 — current usage as-is) | 2.51 | 1x |
| **After**: memoized loads + headless + `Pool(8)`, frame_skip=1 | 51.18 | **20.4x** |
| After + frame_skip=4 (chaotic-behaviour caveat above) | 84.95 | 33.9x |
| After + savestate (frame_skip=1) | 52.75 | 21.1x |

The stated target — "~100 episodes in the time one run takes now" (23.95s)
— is not literally met; 100 episodes at the safe (frame_skip=1) rate take
~117s, not 24s. What's real: **100 old-style episodes would have taken
~40 minutes; the same 100 now take about 2 minutes, with full behavioural
fidelity (frame_skip=1) and no need to touch the riskier lever at all.**
Savestate's own contribution is smaller than expected on 1-1 specifically,
because 1-1 dies early enough that a 60-frame warm-up replay was already a
small fraction of total episode time — it should matter more for longer-
surviving episodes or a level where more of the episode is warm-up.

**What we learned.** The obvious four-item plan wasn't wrong, it was
incomplete — the single biggest cost wasn't in any of the four named
levers, it was redundant work the existing code was already doing every
call. Measuring before optimizing (this sprint's very first step) is what
surfaced that; guessing which of frame-skip/savestates/pooling mattered
most would have gotten the wrong answer. Frame skip earns real throughput
but comes with a real, now-documented cost to single-trajectory fidelity
that a future learning sprint needs to design around (e.g. training on
reward across many episodes tolerates this kind of chaotic timing noise far
better than a "does it survive as long" comparison ever could). No video
this sprint — nothing about what Mario does changed, only how fast the
existing behaviour can be reproduced.

## 014 — the mushroom body: it learns, and it doesn't matter, and both are real (`projects/legacy/runs/014a,b`)

**Setup.** The learning sprint. Real counts checked against this
connectome before building anything, not assumed: **4,064 KC** (not the
4,554 this project's own "Still open" notes had repeated unchecked since
sprint 006), **97 MBON** (not 104), **354 real dopaminergic neurons**
(PAM/PPL/PPM). All real, all dense: KC→MBON 61,210 synapses (4,063/4,064
KCs, all 97 MBONs) — the one matrix that learns. Checked whether MBONs
reach anything already built in this project: **real MBON→DNa02** (250
synapses) and **real MBON→MDN** (88 synapses) exist; **MBON→DNp01 and
MBON→DNp02 do not** — same situation DNp04 was in for TTMn (008), handled
the same way: real wiring where it exists (DNa02), an explicitly-flagged
placed bias where it doesn't (DNp02).

Built: a fixed-seed sparse random projection from the existing sensory
state (theta, odour, gap width, DNp09, hunger — no real PN identity to
look up, the randomness itself is the biologically correct part) onto the
4,064 KCs, top-`KC_SPARSITY` (0.05) active. MBON readout via real KC→MBON
weights. Reward (`max(0, Δx)`, page-aware, unscaled) routed through real
PAM→MBON weights; punishment (`dynamics.CLIP`=50, once on death) through
real PPL+PPM→MBON weights — both depression-only, per-KC eligibility trace
(`TRACE_DECAY`=60 frames). **Verified in isolation before touching the
game loop**: hand-activated 3 real KC→MBON edges, fired a dopamine=50
pulse, confirmed exactly the predicted 50% depression on the active edges
and zero change on the inactive ones (`ΔW/W = -LEARNING_RATE·dopamine =
-0.01·50 = -0.5`, matching exactly). That first LEARNING_RATE (0.01) was
rejected before training on the strength of that same isolation test — a
single punishment event depressing an eligible synapse by half is too
aggressive for a smooth curve, since 500 further such events would floor
it near zero. Settled on `LEARNING_RATE=0.001` (5% per full-magnitude
punishment, gradual) — three new scalars total (`KC_SPARSITY`,
`TRACE_DECAY`, `LEARNING_RATE`), taking the budget from 5 to **8**.

**What happened.** Trained 80 episodes from an identical savestate
(headless, frame_skip=1 — 013's own finding that frame_skip changes
behaviour chaotically ruled it out for training). Not 500: the first 80
were **completely, exactly flat** — literally one unique value
(`max_x=682`) across all 80 episodes, same 354 frames, same 4 escape
jumps, same DNp01/DNp02 split, every single time. Continuing to 500 would
have re-confirmed the same result 420 more times, not produced new
information, so training stopped at 80 and that reasoning is stated here
rather than a round number presented without comment. The before and
after videos (identical savestate, one using the untrained weights, one
using the 80-episode-trained weights) are frame-for-frame behaviourally
identical.

**The weights genuinely changed. The behaviour did not, and the gap
between those two facts is measured, not guessed.** `W_kc_mbon`'s total
depressed 6.2% over 80 episodes (79.140 → 74.233), touching exactly the
61,210 real edges and no others — real learning happened at the synapse.
Separately measured the actual size of the MBON→DNa02 bias this produces:
under realistic sustained KC activity (5% active, matching `KC_SPARSITY`),
MBON output settles to ≈0.04–0.05; multiplied by the real anatomical
fraction (0.632% for the stronger of the two real synapses), the actual
bias reaching DNa02's WTA is **≈0.00026 — roughly 4,000x smaller than
`HOME_BIAS=1.0`**. No amount of training within this design can cross that
gap, because it isn't a training problem: the real connectome fraction is
just that small relative to the existing terms it's competing against.
This is the exact same shape of finding as SPEC_odour.md's original bug
(006's mushroom odour, 40x too small against `HOME_BIAS` before
`ODOUR_GAIN` fixed it) — except here, per this sprint's own explicit
scalar budget, no fourth new scalar was introduced to rescale it. That is
a deliberate choice stated openly, not an oversight: SPEC_mushroom_body.md
allowed exactly three new scalars, and inventing a fourth to force a
visible effect would have been curve-fitting the demo, the same
temptation SPEC_odour.md's own section 2 warned against for a different
gain.

**What we learned.** Three real, separately-verified facts, not one
muddled one: (1) the three-factor depression-only plasticity rule is
implemented correctly — confirmed in isolation before it ever touched the
game loop, and confirmed again by the measured 6.2% real depression after
training. (2) The real MBON→DNa02 anatomical connection is genuine, not
fabricated — 250 real synapses, checked directly against the weights
file. (3) At this circuit's realistic activation levels, that real
connection is roughly four orders of magnitude too weak to move a
decision already dominated by `HOME_BIAS` and odour. All three are true
at once. A flat learning curve here is not "the mushroom body doesn't
work" — it is "the mushroom body's real output, at its real anatomical
strength, cannot reach the decision it was asked to influence," which is
a sharper, more specific, and more useful finding than either "it worked"
or "it didn't" would have been alone. A future sprint choosing to
introduce an `MB_OUTPUT_GAIN` scalar (the ninth) to close this specific,
now-measured 4,000x gap would be doing so with the actual number in hand,
not a guess.

## 016 — make it a smell problem (`projects/legacy/runs/016_smell.mp4`)

**Setup.** docs/MECHANISMS.md sections 1/5/6, level 1-1 only, no vision.
Connectome check BEFORE any code, per instruction, since LPLC1 (007) and
the DNp02-vs-DNp01 race (012) both had the literature's backing and the
anatomy said no anyway — a third time here: (a) the aversive pathway
(Or56a→glomerulus DA2, 48 ORN_DA2 bodies; Gr21a/Gr63a→glomerulus V, 55
ORN_V bodies → their real PNs, 14 bodies total → 422 real lateral-horn
types) reaches DNa01/DNa02 with **2 LH bodies, 3 synapses** against DNa01/
02's 76,248 total real input — noise, the same bar that excluded LPLC1.
(b) the attractive food-odour pathway (Or42b/DM1, 74+2 bodies) is the
same **zero direct PN synapses**; the only real olfactory-adjacent input
onto DNa01/DNa02 anywhere in the connectome is 259 synapses (0.34%), and
237 of those are MBON31/32 — the mushroom body's already-built LEARNED
pathway (014), not an innate one. (c) either pathway onto DNp09 (the
section-5 brake): **zero synapses**, full stop, out of DNp09's 15,940 real
input. All three: anatomy says no. Response (matching how DNp02's MBON
bias was handled in 014 when its own real synapse didn't exist): model
Goomba-odour/the DNp09 brake/the refusal push as placed external currents
— the same category HOME_BIAS/GAP_GAIN/WALK_DRIVE already are, and exactly
how mushroom/`?`-block odour already worked before this sprint. Per
instruction ("prefer deriving from synapse counts over adding a
constant"), every new channel REUSES an existing scalar (ODOUR_GAIN for
aversion and for the DNp09 brake, GAP_GAIN for the refusal push) rather
than inventing new gains — the only genuinely new number is
`REFUSAL_GAP_TILES=5`, a body-scaled mechanical threshold (not a circuit
gain), derived from 007's clean 0-4-tile calibration and 008/011's 8-tile
failure. Budget: 8 neural-circuit scalars, unchanged; 9 if every hand-set
number of any kind is counted (full reasoning in run_steering.py).

Tried the established synthetic-injection pattern for "eats the mushroom"
first and found it doesn't work for that: walked Mario's hitbox directly
through an injected powerup object for 100+ frames and its Active flag
never cleared, while an identical poke using a real enemy's own ID
collides and kills Mario immediately — Y-coordinate wasn't the problem
(both read 1, the game's own normal "on ground" value, confirmed against
a real Goomba encounter). Most likely cause: the real spawn routine caches
per-object state (hitbox dimensions etc.) a raw Active/ID/X/Y poke never
populates. Not a previously-known bug — 006/008/009 only ever needed the
object to produce an odour value, never a real pickup. Turned out not to
matter: with aversive+attractive odour and hunger all live, Mario
organically survived long enough to hit a real power-up `?` block from
below (an incidental escape-jump/climb-hop arc — this project still has
no dedicated hit-blocks-from-below mechanism) and the GAME's own spawn
routine produced a real, collidable mushroom. The wide pit stayed
synthetic (`poke_wide_gap`, re-asserted every frame — a one-shot poke of
a not-yet-drawn tile column was found to get silently reclaimed by the
level streamer before Mario arrived) since 1-1's own pits are all 2 tiles,
comfortably inside the validated-safe range — there is no real pit on this
level that should be refused.

**What happened.** All four success events, one run, `inject_gap_frame=600`
the only synthetic stimulus (the mushroom is real, unscripted): avoids a
Goomba via odour at **frame 189** (7 total this run — DNp01/DNp02 stayed
available and fired independently, e.g. frame 141/606, so the new channel
is additive, not a replacement, per instruction), hits a real `?` block at
**frame 226** (4 total), eats the resulting real mushroom at **frame 400**
(`mario_size` 0→1, confirmed via RAM), refuses the synthetic wide pit at
**frame 757**. Survived to **frame 1035** — three times the pre-sprint
354-frame baseline, reaching x_abs=1388 vs 682 — before dying to a real
Goomba (`ttmn_dnp02` pinned at 50.0 at death). The refusal held exactly as
designed: `mario_x` topped out at 111 while `gap=6` for the rest of the
run (the synthetic pit's near edge), never crossing in, and — after a
same-run fix once the first cut showed DNp01 still firing a doomed long
jump into a refused gap (`GAP_GAIN`'s DNp01 term is now gated on `not
refusing` too, so "do not attempt" covers the jump pathway, not just
steering) — no jump was attempted into it either. But Mario still died at
that exact spot: cornered between the pit and an approaching Goomba, with
only "toward the pit" or "away from progress" to choose from, refusal
bought no way out.

**What we learned.** A third clean "anatomy says no," same shape as LPLC1
and the DNp02 race — worth taking seriously as a pattern now, not a fluke:
plausible, literature-backed circuits keep failing the connectome check in
this dataset specifically at the point where they'd need to reach a
descending neuron directly. The honest response (placed bias, flagged,
reusing existing scalars) is the same one already validated in 014 and it
worked again: real behavioural change (3x survival, an unscripted `?`-hit
and mushroom pickup, a genuine early Goomba avoidance) from currents that
carry no claim to being "the real ORN pathway." The refusal rule's failure
mode is not a bug — it's the exact caveat docs/MECHANISMS.md #6 wrote down
*before* any of this was built ("refusing only helps if there's an
alternative... crossed on the moving elevator platforms, which is a
mechanism the fly does not have"), now observed directly rather than
predicted: Mario refused correctly and died anyway, because standing still
at a dead end has its own cost this circuit has no way to price in. And a
smaller, concrete finding worth keeping for any future synthetic-object
test: `inject_mushroom`-style RAM pokes produce a visible, odour-active,
but **not collidable** object — real pickups need to go through the game's
own spawn path.

## 017 — the steering bug that wasn't, and two things not built (`projects/legacy/runs/017_step1_fixes.mp4`)

**Setup.** Three ordered steps; only the first shipped code. 016 shipped
no telemetry CSV (fixed first: `main()` now writes `{stem}_telemetry.csv`
unconditionally, every column, independent of `record_video`).

**Step 1 diagnosis.** The reported "0.016-unit, bimodal DNa01-vs-DNa02"
asymmetry was never the axis the WTA runs on. `dna01`/`dna02` are means
BY TYPE (each already blending its own L+R bodies), and DNa01/DNa02
receive the *identical* per-hemisphere current — so `dna01≈dna02` on
every frame **by construction**, regardless of whether steering works.
Pulled the real per-hemisphere numbers at frame 189: `dna01_L=11.008`,
`dna01_R=1.126`, `dna02_L=11.008`, `dna02_R=1.159`, `r_team=1.142`,
`l_team=11.008` — a genuine ~10x asymmetry, and exactly why `direction`
correctly flipped to `L` that frame. The circuit was never broken; the
telemetry/overlay just never exposed the axis that mattered. Added
`r_team`/`l_team` and per-hemisphere `dnaXX_l/r` to telemetry, and a
`steer R_team=… L_team=…` line to the overlay itself.

Separately, real bug, found while checking why "DNp09 sits at exactly
zero 25/51 frames yet Mario runs constantly": `MOVES`/`action_index`
gating is correct (`press_b == (dnp09>=threshold)` on 100% of frames,
checked directly). But 016's own DNp09 odour-brake reused
`odor_l_eff+odor_r_eff` — already scaled by `ODOUR_GAIN=16` so odour
alone could out-compete a *constant* `HOME_BIAS` at long range
(`SPEC_odour.md` section 0's whole point) — as a braking signal, where
"merely detecting a `?` block ~100px away, hunger-boosted" braked about
as hard as standing next to it. A/B on the same run: brake active →
`dnp09` median 0.0, B pressed 9.3% of frames; forced off → median 0.94,
B pressed 67.7%. Fixed the same way `SPEC_odour.md`'s own section-0 bug
was fixed once already — not a new scalar, but the right existing
reference point: braking only engages on the excess over `HOME_BIAS`,
i.e. after odour has already won the steering competition, not merely
been detected. Re-run of the same conditions: B-press fraction 24.7%→
48.7%. **Zero new scalars in this fix — both reuse existing constants.**

**Step 2, re-justified and declined.** The original premise for mutual
inhibition ("DNa01≈DNa02 almost always") is dead per the finding above.
Counted actual contradictory-command frames across 1-1/1-2/1-3 (~5,000
frames total, current fixed code): escape+steering(L)+climb same frame
= **0** on every level; climb-and-escape both wanting A = **≤1** per
level; aversive-vs-home near-tie (`|r_team-l_team|<0.1`) = **≤1** per
level. 006's own "2 harmless conflicts" was the only prior evidence and
it was thin; this is thinner. Declined to build arbitration for a
problem this rare — scaffolding for nothing, exactly as specced.

**Step 3, checked and declined.** pC1 is real: **156 bodies** (78L/78R),
not the ~85 `docs/MECHANISMS.md` had guessed — corrected, same pattern
as the mushroom body's 4,554→4,064 correction in 014. **DNp37 does not
exist anywhere in this connectome** — the `DNp*` series runs
...DNp35, DNp36, **DNp38**, DNp39... — an actual gap, not a naming
mismatch (checked `type`, `hemibrainType`, `flywireType`, `instance`,
all empty). **pC1→TTMn: 0 synapses, direct or otherwise checked** — a
*stronger* negative than DNp02's 012 case, which at least had a real
21R/5L direct TTMn synapse to justify building on. pC1's real output
(793,019 synapses total) is dominated by other pC1 subtypes and central-
brain arousal-adjacent neuropil (SIP/AVLP/mAL/aIPg) — consistent with
pC1's known role as a P1-like arousal integrator, not a dedicated
action-selection hub with descending authority. Its largest link to
anything already built in this project is real but modest: **DNa01,
115 synapses/20 pairs** (steering) — bigger than its link to the
literature-suggested DNa11 (27/12) — but that's steering, not an attack
effector. "Small flees, big jumps over" already exist (odour avoidance,
size-gated climb hop); "fiery attacks" has no real connectome path to
stand on, matching and exceeding the standard `docs/MECHANISMS.md`'s
own "Not building: ranged attack" section already set. Declined.

**Overlay audit** (requested directly): found one more instance of the
same failure mode, and one that isn't display-only. `lc4`/`lplc2` in the
overlay blend both hemispheres (lower stakes — `TTMn` itself already
reads `max(L,R)` for the actual jump decision — but a one-sided Goomba's
real drive still gets diluted in what's shown); added `lc4_l/r`,
`lplc2_l/r` to telemetry. More significant: the mushroom body's
`mbon_agg = h_mbon.mean()` blends **all 97 MBON bodies with no L/R split
at all**, then `mb_bias_l`/`mb_bias_r` are that SAME scalar times two
different *fixed* anatomical constants (0.00379 vs 0.00632) — meaning
the mushroom body cannot currently express a genuinely lateralized
learned preference under any circumstance, only a uniformly-R-biased
pull whose overall strength varies. Not fixed this sprint (a real
redesign of the KC→MBON→steering wiring, not a telemetry fix) — flagged
for `docs/MECHANISMS.md`'s queue.

**What happened.** `projects/legacy/runs/017_step1_fixes.mp4`, 807 frames, level 1-1,
same conditions as 016 (organic `?`-block/Goomba encounters, synthetic
wide gap at frame 600): B-press fraction 48.7% (vs 016's un-audited,
much lower true rate), first odour avoidance at frame 160
(`r_team=1.12` vs `l_team=3.21`, a real, now-visible asymmetry), 7 real
`?`-block hits, 60 refusal frames. Trajectory diverges from 016's own
recording past the first few hundred frames (expected — the DNp09 fix
changes exactly how fast Mario covers ground, so he meets each Goomba at
a different frame; same determinism, different path, per 013's own
finding about single-trajectory comparisons). No mushroom pickup this
specific run — a property of this trajectory, not a regression.

**What we learned.** Three real, separate findings, not one muddled
sprint: (1) a genuine circuit can look completely broken through a
telemetry axis that was never the right one — the 016 diagnosis was
sound investigative instinct, wrong target column, and the circuit
itself needed zero repair, only better visibility. (2) The right
response to "should we build arbitration/an attack pathway" is sometimes
counting first — both step 2 and step 3 looked plausible from the
literature and both failed on real numbers, exactly the pattern LPLC1
(007) and the DNp02 race (012) already established for this connectome.
(3) **Scalar count: unchanged** (both step-1 fixes reuse existing
constants — `HOME_BIAS`, no new number). **Scaffolding count: zero new**
— this is the first sprint in the project's history to net-decrease
planned complexity, by declining two builds on evidence rather than
shipping them because they were asked for.

## 018 — LC10a azimuth pursuit: checked, and the test that would decide it can't run on this data (no video — pure connectome analysis, nothing built)

**Setup.** Before any code: does LC10a exist, does the literature's
LC10a→AOTU→PFL3→DNa02 chain hold up hop by hop in real synapse counts,
and — the decisive test — does LC10a's arborization in AOTU order
cleanly along a principal axis (the geometric precondition for "azimuth
falls out of anatomy" the way looming θ falls out of LC4/LPLC2's real
wiring in `SPEC_jump.md`)?

**1. LC10 is real.** 960 bodies total across seven annotated subtypes:
**LC10a 275** (140R/135L), LC10d 214, LC10c-1 130, LC10c-2 125, LC10e
110, LC10b 95, LC10_unclear 11. LC10a is genuinely the largest subtype,
consistent with the literature's pursuit-specific framing — confirmed,
not assumed.

**2. The chain, traced hop by hop by real heaviest edges, not assumed
names.** LC10a's own real top targets (`AOTU008` 16,114 syn/1,489
pairs, `AOTU041` 14,304/564, `AOTU019` 14,210/206, plus dense LC10a/
LC10d self-recurrence) are **NOT** the neurons actually driving TuBu
(the literature bulb relay). Queried TuBu's own real total input
directly: dominated by `MeTu1-4` types (13,585/1,111 for the single
largest, `MeTu3c`) — a different medulla-derived visual stream
entirely. **LC10a→TuBu (any of the 10 subtypes, summed): 461 synapses/
172 pairs** — real, but thin next to MeTu's contribution, and thinner
still per-subtype (largest single link `TuBu01` 169/47). TuBu→ring
neurons is real (`ExR1` 6,105/508, `ER5` 1,737/58, spread across ~20
ER/ExR subtypes). Ring/compass input reaching PFL3 is real but a minor
fraction of PFL3's own total input (60,811 synapses) — `EPG` (the
actual compass signal) contributes 1,182/113, dwarfed by `Delta7`
(5,617/278), `hDeltaA/I/M/H`, and the `FC2` family (fan-shaped-body
columnar neurons carrying non-visual, internal-state-adjacent signals).
**So: five real hops (LC10a→AOTU→TuBu→ExR/ER→PFL3→DNa02), each real,
each correctly signed (below), and thin at exactly the two hops between
LC10a and the compass system** — the visual signal gets diluted by
non-visual central-complex inputs well before it reaches steering.
Consensus_nt at every hop, unanimous within type, no split votes:
LC10a ACh, AOTU008 ACh / AOTU041+AOTU019 GABA, TuBu ACh, ExR5 glutamate
/ ExR1 ACh, EPG ACh, Delta7 glutamate, PFL3 ACh.

**3. PFL2/PFL3 → DNa01/DNa02 — the one genuinely strong hop.** `PFL1
→ DNa01/DNa02`: **0** synapses (absent). `PFL2 → DNa01/DNa02`: **5
synapses/4 pairs** — noise, the same bar that excluded LPLC1 (1/1).
**`PFL3 → DNa02`: 736 synapses across all 24 PFL3 bodies, zero to
DNa01.** This is real and substantial — stronger, in fact, than any
other real link onto DNa02 found in this project so far, including the
mushroom body's MBON→DNa02 (250 synapses, run 014). If this project
ever builds a PFL3→DNa02 pathway on its own merits, the anatomy
supports it cleanly. The problem is entirely upstream of PFL3.

**4. The decisive test — cannot be run, not "didn't order cleanly."**
Checked every column in all three MaleCNS flat files before attempting
it: `body-annotations` has exactly one spatial field per body
(`somaLocation`, the cell-body position — already used by
`brain_panel.py`) and `tosomaLocation`; `body-neurotransmitters` has
none; `connectome-weights` has only `body_pre`/`body_post`/`weight` —
**no per-synapse or per-ROI coordinates anywhere in this data export.**
"Compute each LC10a cell's presynaptic-site centroid along the AOTU
principal axis" requires exactly that data, and it does not exist here.
Substituting soma location (a single point per neuron, typically distant
from the actual arbor for a neuron whose cell body sits outside the
neuropil it arborizes in — true of essentially every central-brain
neuron in this dataset, including LC10a) would answer a different,
much weaker question and call it the same thing — exactly the kind of
invented substitute the instruction warned against. Said so and stopped,
per instruction, rather than run a proxy test and report it as decisive.

**What happened.** No code changed. No video — a pure analysis sprint,
per CLAUDE.md's own rule for this case.

**What we learned.** A sixth "anatomy says no" in this project's
history (LPLC1 007, the DNp02 race 012, the aversive/attractive
olfactory pathway 016, pC1→attack 017, and now this), and the clearest
yet about *why* the pattern keeps recurring: this connectome captures
which neurons talk to which and how much, at body-level resolution —
it does not capture *where within a neuropil* they talk, and a real
fraction of every literature circuit's mechanism (retinotopy, azimuth
maps, receptive-field tiling) lives specifically in that missing spatial
layer. `SPEC_jump.md` already hit this once (LC4/LPLC2's `assignedOlHex`
is 0% populated, "skip retinotopy in v1") and it was treated as local to
those two types; it is not local — no neuron in this dataset has
synapse-level spatial data, which forecloses this whole class of test
for any future sprint, not just this one. **Scalars: 0 added, 0
removed** (nothing was built, so "net negative" doesn't apply — stated
plainly rather than forced). **Scaffolding: 0 added.** Third sprint
running at zero net new complexity.

**Correction, appended 019 — the "no spatial data" claim above is
wrong.** `assignedOlHex1`/`assignedOlHex2` ARE present in
`body-annotations`, for 23,720 bodies across 15 medulla columnar types
(L1/L2/L3/L5, C2/C3, Mi1/Mi4/Mi9, T1, Tm1/Tm2/Tm4/Tm9/Tm20) — checked and
missed in this entry's own investigation, which stopped at `somaLocation`/
`tosomaLocation` and the weights file's three columns without checking
the annotation column list against `assignedOlHex*` specifically, despite
that exact column name having already been printed to this same session
once before (the full 36-column dump done for an unrelated check).
**`SPEC_jump.md`'s own framing was closer to correct than this entry's
restatement of it** — it said the coordinates "exist only for columnar
optic lobe cells," which is exactly what's true; this entry generalised
that into "no neuron... has synapse-level spatial data," which overshot
the real finding into a false one. See `## 019` below for what the data
actually supports once checked properly, including a claim in the
correction request that turned out to also be wrong in an interesting
way (TmY3, cited as carrying hex data, carries none — it just happens to
receive heavily FROM cells that do). Not editing the paragraphs above;
this stands as the record of getting it wrong before getting it right.

## 019 — LC10a really does tile azimuth; the pathway to steer with it doesn't survive its own thinness (no video — connectome analysis + one calibration check, nothing wired into the live system)

**Setup.** Corrected 018 first (above). `assignedOlHex1`/`assignedOlHex2`
exist for 23,720 bodies across 15 medulla columnar types (L1/L2/L3/L5,
C2/C3, Mi1/Mi4/Mi9, T1, Tm1/Tm2/Tm4/Tm9/Tm20) — checked directly, unique
per (hex1,hex2) pair within a type (0 duplicates in 1,767 L1 bodies), and
per-EYE, not global: L and R both independently span the same 1-36 x
1-39 range. The occupied footprint is a hexagon inscribed in that
rectangle (corr(hex1,hex2)=0.57, occupancy narrowing toward both hex1
extremes) — the standard oblique axial hex-lattice signature, not an
orthogonal azimuth/elevation grid. Converting to true visual-angle
degrees needs an external hex-to-Cartesian shear and an inter-ommatidial
angle constant, neither of which lives in this data — so the ordering
test below is run in native hex-coordinate space, which is a linear
transform away from degrees and just as valid for asking "does the
population tile or pile up."

**TmY3 does not carry hex data — the specific claim was wrong, but the
mechanism behind it is real.** Checked directly: 0 of TmY3's 824 bodies
have `assignedOlHex1`/`2`. But TmY3 *receives* very heavily from
hex-carrying cells (Mi4/L5/Tm2/Mi9/Mi1/Tm4/L2/Tm20: 286,681 of 623,162
total real input, 46.0%, all 824 bodies reached) — a real, derivable
receptive field, just not the one the request named.

**LC10a's real one-hop hex-carrying input.** Checked LC10a's full real
presynaptic population, not assumed: dominated by non-hex types (LC9,
Tm5Y, TuTuA_2, AOTU042, other LC10 subtypes). Among the 15 hex-carrying
types, only `Tm1` (9 syn/6 pairs, noise), `Tm2` (77/20, thin), `Tm20`
(1,402/684), and `Tm4` (2,657/994) connect at all — **4,145 of 258,112
total real input, 1.61%** — but real, one hop, not two, per the rule set
before looking: two hops would have meant inherited coordinates smeared
across an unknown receptive field, and the answer would have been no
before the test even ran. It's one hop, so the test proceeds.

**The decisive test, LC10a: passes, with a real side asymmetry.** For
each LC10a body, computed its receptive-field centre as the synapse-
weighted mean hex position of its real Tm1/Tm2/Tm20/Tm4 partners (248/275
bodies reached, 90%), then compared each body's OWN input spread against
the nearest-neighbour distance between different bodies' centres:

| side | bodies w/ input | within-body spread (med) | nearest-neighbour dist (med) | "indistinguishable" (NN < own spread) | hex1 span | hex2 span |
|---|---|---|---|---|---|---|
| L | 112/135 | 0.68 | 1.42 | 6/112 (5%) | 3.0–34.7 | 1.0–38.0 |
| R | 136/140 | 1.37 | 1.60 | 47/136 (35%) | 4.4–34.0 | 1.2–36.4 |

Both sides cover nearly the full grid — this is tiling, not pile-up, on
either side. The left side is clean (95% of cells clearly separated from
their nearest neighbour); the right is noisier (65%) — a real,
unexplained asymmetry, reported as found rather than averaged away.
**Verdict: clean ordering, not degenerate. The population really does
carry a graded position signal, derived from real synapses, not invented
by binning.**

**The bigger prize, checked in the same pass: LC4/LPLC2, direct, not via
TmY3.** TmY3 being a dead end for its OWN hex identity doesn't block
this — LC4 and LPLC2 receive hex-carrying input DIRECTLY, one hop, no
relay needed: **LC4 16.47%** of total real input (Tm4 31,134/5,006 + Tm2
20,560/4,149, all 126 bodies reached), **LPLC2 5.84%** (Tm20 13,367/3,183
+ Tm4 7,758/2,401, all 185 bodies reached) — both an order of magnitude
denser than LC10a's 1.61%. Ran the same tiling test anyway, out of
curiosity about whether density alone would make it cleaner: it doesn't.
LC4 is markedly noisier than LC10a (58-62% "indistinguishable" on both
sides, vs LC10a-L's 5%), LPLC2 intermediate (28-34%). Both still span the
full hex grid, so this isn't pile-up either — it reads as real, broad,
overlapping receptive fields, which is what a wide-field looming detector
is *supposed* to have, unlike LC10a's narrow pursuit tuning. Denser
input does not automatically mean cleaner tiling; the two are answering
different questions. Confirmed present and worth a future sprint;
**not built here, as specified.**

**The pre-commit check that stopped the build.** Extracted the real,
named-population traced path as its own body-level circuit
(`lc10a_pursuit_circuit.py`: LC10a 275 + TuBu 156 (10 subtypes) + ring
ER/ExR 296 (29 subtypes) + PFL3 24 + DNa02 2 = 753 bodies, real edges/
signs/weight matrix via the same reused helpers every other circuit here
uses). Coverage matches 018's own warning: LC10a 11.6%, PFL3 3.9%, DNa02
1.5% (of each type's real total input — the rest is Delta7/hDelta/FC2/
PFNp and friends, entirely outside this subgraph, per 018). Spectral
radius scales exactly linearly with g (ρ=g, an unusually clean result —
the ring-neuron cluster's own near-total self-coverage, 0.6-0.95, forms
a near-closed recurrent loop dominating the top eigenvalue), so g<1 is
required for stability; tested g up to 0.95, safely under.

Drove LC10a with a synthetic azimuth stimulus (Gaussian tuning around a
target hex position, using each body's own measured spread as its
bandwidth — no invented constant) at g=0.5-0.95: **PFL3 and DNa02 output
stayed at 0.00000-0.00048, against HOME_BIAS's own scale of 1.0** — six
orders of magnitude down. Not a calibration miss: stress-tested by
driving ALL 275 LC10a bodies at the network's own clip ceiling (50.0,
full saturation) at g=0.95 — **DNa02 still only reaches 0.00072.**
Maximum possible drive through this real, correctly-signed, real-gain-
bounded circuit does not move DNa02 by an amount that could ever compete
with HOME_BIAS, odour, or anything else already in the steering WTA.
**Thinness is fatal at every realistic gain. Did not commit to the
build.**

**What happened.** No code changed in the live system.
`lc10a_pursuit_circuit.py`/`load_lc10a_cached.py` exist as real, cached,
reusable investigation artifacts (same category as `query_input_pools.py`
or `tune_dnp02.py`) — built, tested, and correctly report a negative
result; not imported by `run_steering.py`. No video: nothing about
Mario's behaviour changed.

**What we learned.** Three separate, real findings. (1) 018's "no
spatial data" claim was a genuine mistake, corrected above — the data
partially supports exactly what was asked for, and getting it wrong once
before getting it right is worth keeping on the record rather than
quietly fixing forward. (2) The decisive test itself is a good filter,
independent of its outcome here: LC10a's real one-hop hex input, thin as
a *fraction* of its total drive (1.61%), still produces genuinely clean
retinotopic tiling — thinness of input fraction and cleanness of spatial
order are different properties, and conflating them would have thrown
out a real result. (3) But a clean map at the *front* of a pathway
doesn't guarantee the *pathway* survives — this is the same shape of
finding as the mushroom body's real-but-4,000x-too-weak MBON→DNa02 bias
(014), here compounded across five hops and roughly three orders of
magnitude worse (six, not four). The chain LC10a→AOTU→TuBu→ring→PFL3→
DNa02 is real at every hop (018) and the input end of it is real and
spatially organised (this entry) — and none of that is sufficient, once
actually simulated, because each hop's real coverage inside a 753-body
subgraph compounds multiplicatively against everything real that hop
also does that this subgraph can't capture (Delta7/hDelta/FC2/PFNp at
PFL3 alone dwarf the ring input this pathway carries). **Invariant
restated, not left to imply more than it is:** this was never going to
give Mario pixels, and still isn't — RAM supplies a target's distance
and side exactly as it always has, synthesised into the SAME kind of
scalar `theta`/`d` already feeds LC4/LPLC2. What the hex data would have
added, had the pathway carried it, is which *specific* real LC10a cell
should receive that scalar — a real population map instead of one blanket
value per hemisphere — not vision, a better-targeted version of the same
compromise SPEC_jump.md made from the start.

## 020 — two checks on 019's methodology: it wasn't chained, and MBON isn't usable either (no video — pure verification, nothing built)

**Setup.** Two checks requested against 019's "fatal" verdict, explicitly
no building either way: (1) drive DNa02 through MBON and through PFL3
under an identical pipeline and compare magnitudes; (2) rebuild the
LC10a→DNa02 path as one single-normalisation network rather than
(assumed) five chained subgraphs, and re-measure with per-hop
attenuation reported.

**Check 2 first, because it turned out to be a non-issue: 019 was
already a single network.** Checked `lc10a_pursuit_circuit.py` directly
— one `mcns.body_subgraph` call over all 753 bodies, one
`circuit.build_weight_matrix` call, one resulting `W`. There was never a
second normalisation pass to introduce; "five hops" in 019's writeup
meant graph distance through that single sparse `W`, not five separately
row-normalised stages someone forgot to merge. Re-measured anyway, this
time reading out every intermediate population from the SAME settled `h`
(g=0.95, all 275 LC10a driven to the clip ceiling, 50.0, matching 019's
own maximal stress test):

| stage | n | mean activation | attenuation from previous hop |
|---|---|---|---|
| LC10a (driven) | 275 | 50.000 | — |
| TuBu | 156 | 5.978 | 8.4x |
| ring ER/ExR | 296 | 0.222 | 26.9x |
| **PFL3** | 24 | 0.00108 | **206x** |
| DNa02 | 2 | 0.000719 | 1.5x |

The loss is not spread evenly across hops (a uniform-per-hop artifact
from chained normalisation would look roughly equal at each step) — it
concentrates almost entirely at ring→PFL3, the exact hop 018 already
flagged as thin (PFL3's real input is 3.9% covered by this subgraph;
the rest is Delta7/hDelta/FC2/PFNp, entirely outside it). The 8.4x
TuBu loss roughly tracks TuBu's own ~11.6% LC10a-specific coverage too.
**The attenuation pattern matches the anatomy's own real coverage gaps,
hop by hop — the signature of a genuinely thin pathway, not a pipeline
artifact.**

**Check 1: built PFL3's exact comparison, KC→MBON→DNa02 as ONE network
(4,517 bodies: 4,064 KC + 354 DAN + 97 MBON + 2 DNa02, one
`body_subgraph` call, one weight matrix — same pipeline as the LC10a
circuit, not 014's original separate-fraction method). Drove 5% of KC
(203 bodies, matching `KC_SPARSITY`) to the clip ceiling, same style as
PFL3's own stress test. **Result: DNa02 = 0.000000. Exactly zero, not
small — MBON is not usable either, under a fair pipeline.**

**Why, and it's a real bug, found only because this comparison was done
properly.** Checked every real edge onto DNa02 within this subgraph:
295 synapses total, but **243 of them are inhibitory and only 52
excitatory** (net signed sum: −191). The two dominant real partners —
`MBON31` (133/3 pairs) and `MBON32` (104/2 pairs), together the same
population 014 built the mushroom-body bias on — are **both GABAergic**,
confirmed against `consensus_nt` directly. `ReLU` correctly clips a
net-inhibitory drive with no excitatory floor to zero; that's not a bug
in the test, it's the real fixed point.

**The bug is in the shipped code.** `run_steering.py`'s
`MBON_DNA02_FRAC = {"L": 0.00379, "R": 0.00632}` was computed in 014 as
a raw synapse-COUNT fraction, with no sign attached, and is applied as
`mb_bias_r/l = MBON_DNA02_FRAC * mbon_agg`, added UNCONDITIONALLY
POSITIVE onto `Is[dna02_all & r/l_mask]` — treating the mushroom body's
real influence on steering as attractive, when its dominant real
synapses are inhibitory. 014's own finding that this bias is "~4,000x
too small to matter" means the sign error hasn't changed any observed
behaviour to date — but it is a real correctness bug, independent of
everything else in this entry, sitting in currently-shipped code.
**Not fixed this sprint — no building was in scope — flagged below.**

**What we learned.** Both of the user's two possible outcomes were
partially right, in a way neither branch anticipated. The pathway
genuinely is too thin (019's verdict stands, now on a hop-by-hop basis
instead of an end-to-end one) — but the *reason* the MBON comparison
looked suspicious wasn't chained normalisation (there wasn't any) or a
pipeline bug in the PFL3 test. It was that the ORIGINAL MBON test (014)
and the new PFL3 test (019) were never actually comparable — 014 never
built DNa02 into a real weight-matrix node at all, it multiplied by a
hand-carried unsigned fraction, which cannot represent inhibition and so
silently reported a small positive number for a connection that's
really a hard-inhibited zero. Once both pathways are tested the same
honest way, **neither is usable**, for two completely different real
reasons (PFL3: genuinely thin coverage, multiplicatively compounded;
MBON: real, substantial, and inhibitory, previously mis-signed as
excitatory). No negatives elsewhere in this project need revisiting on
the "chained normalisation" theory specifically — nothing else here was
built as a multi-hop simulated network the way `lc10a_pursuit_circuit.py`
was; the other null results (LPLC1, the DNp02 race, the aversive
olfactory pathway, pC1) were direct single- or two-hop synapse-count
checks against a noise bar, not chained simulations, so this specific
failure mode doesn't apply to them. **Scalars: 0. Scaffolding: 0** —
still pure verification, as asked.

## 021 — the sign fix, and MBON really does modulate a live baseline (barely) (no video — a one-line behavioural sign flip plus a corrected re-test, nothing new to watch)

**Setup.** Two asks: fix the real bug 020 found (`MBON_DNA02_FRAC` applied
as an unconditional positive bias when the dominant real synapses are
inhibitory), and re-run 020's check 1 with DNa02 given a REAL excitatory
environment instead of none — 020's KC-rooted subgraph gave DNa02 no
possible positive baseline to inhibit, so its "exactly zero" result
couldn't distinguish "the effect is negligible" from "the test structurally
cannot show any effect at all." Both are real questions; only the second
one got a clean answer in 020.

**The fix.** `run_steering.py`: `mb_bias_r/l` is now
`-MBON_DNA02_FRAC * mbon_agg` (subtracted, not added), and `mb_bias_dnp02`
kept structurally parallel (same sign, same "no real synapse, judgement
call" status it already had). `MBON_DNA02_FRAC` itself is untouched —
014's magnitude was never wrong, only its sign. This matches real MB
physiology, not invented for the occasion: naive MBON tone is understood
to suppress approach, and appetitive depression releases it — exactly the
shape the existing depression-only plasticity rule already implements,
now finally pointed the right direction. No new scalar.

**The corrected test.** Built ONE combined network: `steering_circuit.py`'s
own real extraction (DNa01/DNa02 core + all 325 real N≥60 threshold
partners, 329 bodies — the *escape-circuit's own criterion*, not a
KC-rooted one, per instruction) UNION `mushroom_body_circuit.py`'s core
(KC 4,064 + MBON 97 + DAN 354) = 4,843 bodies, one real edge extraction,
one weight matrix (ρ(g=1)=0.983, same safe-gain shape as 020's). Drove
`HOME_BIAS` onto the real R-side DNa01/DNa02 units exactly as the live
game does — this is the piece 020 skipped — and let the network settle:
**DNa02_R = 0.9978, a genuine live baseline**, not the flat zero a
KC-only subgraph is structurally stuck at.

**MBON can modulate it. The direction is now right. The size is still
close to nothing.** Adding a 5%-KC odour drive (undepressed, full real
weight) pulls DNa02_R down to 0.99685 — a real, measurable,
correctly-signed **decrease** of 0.096% of baseline. Sweeping this
pattern's own KC→MBON depression from 0% (naive) to 100% (that pattern's
MBON drive fully eliminated) recovers DNa02_R to 0.99690 — the full
depression range moves the effect by about 5% of itself. **Realistic
depression levels (5–20%, matching what `LEARNING_RATE=0.001` actually
produces per reward event) move it by roughly 0.2% of the already-tiny
effect** — undetectable against `HOME_BIAS`'s own scale of 1.0 or
odour's typical 1–10 (sprint 016/017 telemetry).

**What we learned.** Not a repeat of 020's "exactly zero," and not a
reversal of it either — a sharper version of the same practical
conclusion, now honestly earned. MBON's real synapse onto DNa02 is
substantial (295 synapses, 243 inhibitory), correctly signed after this
fix, and genuinely, measurably responsive to learning — every part of
this circuit does real work. None of that changes what 014 already
found: at realistic anatomical strength, the effect is roughly three
orders of magnitude too small to move a decision already dominated by
`HOME_BIAS` and odour. **014's magnitude estimate (≈0.00026) turns out
to have been in the right ballpark all along** — what was wrong was only
its sign, not its size. `MBON_DNA02_FRAC`'s wrongness was behaviourally
silent for the same reason both before and after this fix: not because
the bias was zero, but because it was always going to be too small to
matter, and fixing the sign of a negligible number keeps it negligible,
correctly. **Scalars: 0 added, 0 removed** (only a sign flip on an
existing one). **Scaffolding: 0 added** — the combined test network is
an investigation artifact (matching `lc10a_pursuit_circuit.py`'s own
category), not wired into the live system.

## 022 — HOME_BIAS's natural range, and whether it's been drowning the connectome (no video — one measurement, nothing built)

**Setup.** A direct challenge to 019-021's methodology: `HOME_BIAS=1.0`
is injected DIRECTLY onto DNa01/DNa02 themselves, with zero synaptic
attenuation — a fundamentally different, and possibly unfairly
advantaged, mechanism compared to MBON/LC10a's signals, which both had
to survive real, normalised synaptic transmission to reach the same
target. If DNa02's own natural range (driven fairly, through real
synapses, not direct injection) turns out to be ~10⁻³ rather than ~1,
then HOME_BIAS's 1.0 was never a fair reference point and 019-021's
"too small to matter" verdicts were measured against the wrong ruler.

**The zero case, reported and set aside.** `HOME_BIAS=0` with literally
no other drive anywhere gives DNa02 = 0 exactly — mechanically
unavoidable for this leaky-ReLU rate model (no input, `h(0)=0`, stays 0
forever; there's no spontaneous/tonic firing in this framework). Not
informative on its own, so the real test is DNa02's range under a FAIR
real reference current instead of no current — matching exactly how
MBON's and LC10a's own external drives were tested, i.e. injected at the
network's real boundary, not directly on the target.

**The fair reference: `steering_circuit.py`'s own real N≥60 threshold
partners (325 bodies, 158 on the R side) — DNa01/DNa02's actual,
verified real input population, the escape circuit's own extraction
criterion, already in hand from 021.** Drove them exactly the way KC and
LC10a were driven (never DNa02 directly), same combined 4,843-body
network, same `g=0.8`:

| drive | fraction active | DNa02_R |
|---|---|---|
| HOME_BIAS=1.0, **direct** on DNa01/DNa02 (current mechanism) | — | **0.998** |
| unit(1.0) on real threshold partners, **boundary**-injected | 100% (325) | 0.197 |
| unit(1.0) on real threshold partners, boundary-injected | 5% (8) | 0.027 |
| clip-ceiling(50) on real threshold partners, boundary-injected | 100% (325) | **8.826** |

**So: direct injection really is unfair, but only by ~5x, not by orders
of magnitude.** Comparing the two boundary-injected rows at matched
methodology to HOME_BIAS's own direct-injected 0.998: a fully-driven
real population gives 0.197 (≈5x smaller) at the same unit magnitude,
and 8.8 (≈9x *larger*) at the clip ceiling. DNa02's real natural range,
fairly measured, spans roughly **0.03 to 8.8** depending on how much of
its real input population is active — landing solidly in the same
order of magnitude as 1.0, not three orders below it. **The premise
doesn't hold: the natural range is not ~10⁻³.**

**Re-running PFL3 and MBON in this now-established range — the nulls
get sharper, not weaker.** Testing LC10a and KC the IDENTICAL way
(boundary-injected, matched fractions, same network):

| pathway | 5% active, drive=1.0 | 100% active, drive=50 |
|---|---|---|
| **steering's own real partners** | 0.027 | 8.826 |
| MBON (via KC) | 0.000000* | 0.000000* |
| LC10a (019) | — | 0.00072 |

\* MBON's real dominant synapse is inhibitory (020/021) — a driveless
DNa02 has no positive activation to inhibit, so this reads as an
artifact of testing sign-only modulation without 021's live baseline,
not a magnitude finding on its own; 021's own baseline-included test is
the fair one for MBON specifically (~0.1% modulation of a 0.998
baseline). LC10a is purely excitatory, so its own boundary-injected
number is directly comparable here.

The gap between the real, working reference (steering's own N≥60
partners) and LC10a's real chain is **~12,000x at matched maximal
drive** (8.826 vs 0.00072) — both tested with the exact same mechanism,
same magnitude, same "drive everything to the ceiling" convention,
neither one direct-injected. **This is the decisive result: the
pipeline itself discriminates correctly between anatomically strong and
weak real pathways** (a >4-order-of-magnitude spread between two
populations tested identically) **— it does not uniformly crush every
real signal, which is what a genuine "chained normalisation is silently
attenuating everything" or "HOME_BIAS is drowning everything by
mechanism alone" bug would have to look like.** MBON, tested fairly with
a live baseline (021), and LC10a, tested fairly at matched maximal drive
(this entry), are each real, anatomically thin pathways on their own
terms — not victims of an unfair comparison to an inflated HOME_BIAS.

**Same units question: yes, roughly.** Drove the real jump circuit
(`load_cached`, `g=2.0`, the shipped gain) with realistic-to-near-
collision θ/θ̇ (1.5/0.3 through 2.9/0.6, matching sprint 016/017
telemetry ranges): DNp01 settles to 0.64-1.25, TTMn to 1.07-2.08 —
`TTMN_PRESS_THRESHOLD=3.0` sits just above that natural range, the same
relationship `HOME_BIAS=1.0` has to DNa02's own ~0.2-8.8 fair range.
Both circuits operate on the same O(0.1-10) scale, with their
respective hand-set thresholds/biases landing inside that same range,
not off by orders of magnitude in either direction. Different circuits,
same rough units — `g`, `alpha`, `CLIP=50` are shared machinery, not
independently calibrated per circuit, so this is expected rather than a
coincidence, but it was asked and worth confirming rather than assuming.

**What we learned.** The hypothesis was well-posed and worth testing
directly rather than dismissing — a genuinely different outcome
(natural range ~10⁻³) would have meant re-reading three sprints. It
came back ~1, with a real but modest (~5x) direct-injection advantage
for `HOME_BIAS` noted and left alone (no building, as instructed) rather
than either overstated or ignored. **019, 020, and 021 stand, and stand
on firmer ground than before**: the fair, matched-methodology comparison
this entry ran is a strictly stronger test than anything in those three
entries individually, and it reproduces the same ranking (steering's own
real partners ≫ MBON ≫ LC10a's chain) that the individual investigations
already found. **Scalars: 0. Scaffolding: 0.**

## 023 — retinotopy: a finer input map, and escape collapses instead of improving (`projects/legacy/runs/023_retinotopy.mp4`)

**Setup.** The prize was never "which hemisphere" (one bit, invisible at
the jump circuit's single-button output) — it's angular velocity. Every
LC4/LPLC2 cell received the identical θ/θ̇ scalar every frame; the
population had no spatial extent to move across, so there was no
velocity signal in the circuit, only size. `retinotopy.py` (new):
per-cell receptive-field centres for LC4 (126 bodies) and LPLC2 (185
bodies), synapse-weighted mean hex position over each cell's real
one-hop Tm1/Tm2/Tm4/Tm9/Tm20/Mi1/Mi4 input (019's own verified,
100%-coverage population), then a Gaussian per-cell weight — bandwidth
= that cell's own measured RF spread, no hand-set constant — around a
RAM-computed target azimuth that sweeps from `hex1_lo` (d_px≈0,
"foveal") to `hex1_hi` (d_px≥`AZIMUTH_D_REF`=128px, "peripheral") as
the tracked enemy closes. Wired into `run_steering.py` as a straight
replacement of the uniform broadcast (`Ij[LC4_mask] = abs(dtheta)`
becomes `Ij[LC4_mask] = abs(dtheta) * tuning_weights(...)`) — same 1,255
neurons, same DNp01/TTMn, same `TTMN_PRESS_THRESHOLD=3.0`, only the
input map changes. `retinotopic=False` reproduces the pre-023 code path
exactly, giving a true paired comparison rather than a comparison
against 017's old CSV (017 predates the `dtheta`/`d_px`/
`frames_to_contact` telemetry columns this sprint added, and predates
the DNp09-brake fix already sitting in this same working tree — rerunning
the baseline here, not reusing 017's numbers, controls for both).
**One new scalar**, named up front in the module docstring:
`AZIMUTH_D_REF`, an invented reference distance (no degree transform
exists for hex coordinates in this data, so "pixels per hex unit" isn't
derivable). It replaces, not adds to, the existing invented convention
(binary L/R hemisphere routing in `enemy_thetas`) — a continuous
per-cell position replacing a single bit is a strictly smaller invention
on top of the same underlying choice.

**What happened.** Paired run, level 1-1, identical seed/conditions to
016/017 (`max_frames=1500`, synthetic gap at frame 600). Baseline
(`retinotopic=False`) reproduced 017 exactly — same 807 frames, same
died/flagged ending, 10 escape commitments (1 DNp01, 9 DNp02), median
`frames_to_contact` at commit 32.1. The retinotopic run **died at frame
170 having never fired a single escape jump** — 0 commitments, 0 of
either pathway. Reading the telemetry at matched `d_px` (both runs see
the same first Goomba at the same distances, since nothing diverges
until Mario's own actions do): at `d_px=23` the baseline's `lc4` reads
0.039 and `ttmn` is already at 7.35 (over threshold, committing); the
retinotopic run's `lc4` at the identical `d_px=23` reads **0.0053** —
about 7x lower — and `ttmn` sits at 1.3e-148, not merely sub-threshold
but numerically inert. The gap widens as the enemy closes: by `d_px=9`,
baseline `lc4≈0.9` (already jumped and moved on), retinotopic `lc4`
still only 0.0082. Mario walks straight into the Goomba never having
crossed threshold once.

**Mechanism, checked, not guessed.** Queried `tuning_weights` directly
at the real per-side LC4/LPLC2 populations: mean per-cell weight across
the population is **0.02–0.24** depending on target position, and it is
LOWEST exactly at `d_px=0` (mean weight 0.05, LC4-L) — because `d_px=0`
maps to `hex1_lo`, the extreme edge of each population's real measured
hex1 range, where real RF-centre density is thinnest by construction
(it's the tail of a distribution, not its mode). The old uniform
broadcast gave every cell in the population the full scalar,
unconditionally (effective weight 1.0, ~55–94 cells); the new per-cell
weighting recruits only the few cells whose real RF sits near whatever
edge the target happens to map to, and recruits FEWEST of them at the
moment of greatest threat. Compounded by the circuit's own recurrence
(lateral connections 3–9.5x drive onto the Giant Fiber, CLAUDE.md
invariant 4): a smaller, spatially concentrated initial population gets
less lateral reinforcement than a broad, uniformly-driven one, which is
consistent with the ~7–100x gap observed being larger than the raw
mean-weight ratio alone would predict.

**The pre-registered falsification, and why it undershoots what actually
happened.** Stated before the run: if commitment time doesn't move
earlier and `corr(LC4_mean, θ̇)` doesn't newly exceed `corr(LC4_mean,
θ)`, retinotopy is anatomically real and behaviourally inert. What
happened is stronger than that null: commitment didn't just fail to move
earlier, it **stopped happening at all**. On the correlation check
specifically, the pre-registered signature doesn't discriminate here —
`corr(LC4,θ̇)` exceeds `corr(LC4,θ)` in BOTH conditions (0.92 vs 0.58
before, 0.94 vs 0.39 after), because LC4's scalar drive was already
`abs(θ̇)`, not θ, in the pre-023 code (`Ij[LC4_mask] = abs(dtheta)`,
unchanged by this sprint) — so a high LC4/θ̇ correlation was mechanically
guaranteed before 023 ever ran, and isn't evidence of the POPULATION-level
motion signal this sprint actually tested for. That correlation test was
a flawed operationalisation, caught by running it rather than trusted on
paper; the commitment-count result (10 → 0) is the real, decisive
measurement and needs no such caveat.

**What we learned.** Retinotopy is anatomically real (019) but this
particular, explicitly-invented azimuth convention makes the modelled
population WORSE at its job, not neutral and not better — mapping
imminent collision to a real distribution's sparse edge starves the
escape circuit at exactly the moment it matters most. Not a bug in the
sense of a coding error (checked: weights, masks, and injection sites
all do what their docstrings say); a real consequence of an honestly-
invented convention meeting a real, non-uniform anatomical distribution.
No fix attempted this sprint, as specified — the falsification is the
finding. `retinotopic=True` is NOT the new default pending a redesign of
the azimuth-to-edge mapping (e.g. anchoring "foveal" to the population's
real density peak instead of its extreme) — left for a future sprint,
not built here. **Scalars: 1 (`AZIMUTH_D_REF`, replacing not adding to
the existing hemisphere-routing invention). Scaffolding: the hex-to-RAM
azimuth convention itself, named in `retinotopy.py`'s own docstring
before this run, not discovered after.**

## 024 — retinotopy, second and final attempt: the fovea moved, the result didn't (`projects/legacy/runs/024_retinotopy_fovea.mp4`)

**Setup.** Two things, in the order they were done. First, the question
023 left open: is 023's own correlation check even valid? Recomputed
corr(pop, θ) vs corr(pop, θ̇) for BOTH LC4 and LPLC2 on 023's own
telemetry (the 170-frame retinotopic run, measurable with zero
commitments, and the 807-frame baseline). LC4: corr(θ)=0.58,
corr(θ̇)=0.92 (baseline); LPLC2: corr(θ)=0.92, corr(θ̇)=0.57 (baseline) —
θ̇ already dominant for LC4 and θ already dominant for LPLC2, in the
PRE-retinotopy code. That's not a coincidence needing a mechanism: LC4's
scalar drive has been `abs(dtheta)` and LPLC2's has been `theta` since
before any retinotopy sprint (`Ij[LC4_mask] = abs(dtheta)`,
`Ij[LPLC2_mask] = theta`, unchanged code). Each population's own
correlation with its own literal drive signal was always going to be
high; this was never evidence of population-level motion coding, and
023's single-population version of this check couldn't have shown
anything else. Second, the actual fix: 023's failure traced to
`hex1.min()` — an arbitrary edge of each population's real RF range —
being the SPARSEST part of the real density, not the densest, so
mapping "imminent collision" there starved the population exactly when
it mattered. `retinotopy.density_mode()` (new): sum of one Gaussian per
real cell (mean=that cell's own hex1, bandwidth=that cell's own already-
measured `hex1_spread`, no new constant) over the population's own real
range, reporting the peak. Measured, not assumed:

| population | side | n | hex1 range | density mode | mode as frac of range |
|---|---|---|---|---|---|
| LC4 | L | 71 | 4.36–33.86 | 16.34 | 0.41 |
| LC4 | R | 55 | 4.29–33.14 | 18.07 | 0.48 |
| LPLC2 | L | 94 | 3.86–34.20 | 17.15 | 0.44 |
| LPLC2 | R | 91 | 3.63–34.01 | 16.61 | 0.43 |

All four modes land near the middle of their own range, not at either
edge — a real, roughly-unimodal, roughly-centred distribution. The ONE
change: `azimuth_target`'s near/foveal anchor is now this per-population
density mode instead of `hex1.min()`. Far anchor stays `hex1.max()`,
unchanged from 023. Same level (1-1), same `max_frames`/`gap_frame` as
016/017/023, same `TTMN_PRESS_THRESHOLD`, same `AZIMUTH_D_REF`, same
per-cell tuning bandwidth. Three criteria pre-registered before this ran,
carried over from 023 unchanged: (1) frames_to_contact at commitment vs
017's 32-frame median — earlier is the win; (2) whether corr(pop,θ̇)
exceeds corr(pop,θ), now checked for both populations, not just LC4; (3)
survival and commitment count vs the 807-frame/10-commit baseline.

**What happened.** Confirmed the origin actually moved: mean per-cell
weight at `d_px=0` rose from 023's 0.05 to **0.22** (LC4-L) — a real
4.4x increase in engaged population mass at the moment that matters
most, exactly the predicted effect of anchoring at the density peak
instead of the sparse edge. At matched `d_px=23` (the frame the
baseline commits on), `lc4` activation rose from 023's 0.0053 to
**0.0094** — better, but still ~4x below the pre-retinotopy baseline's
0.039 at the same distance, and `ttmn` stayed at 1.2e-148 — as
numerically inert as 023, nowhere near `TTMN_PRESS_THRESHOLD=3.0`. The
retinotopic run **died at frame 170, the EXACT same frame as 023** (the
two runs are frame-for-frame identical up to that point — neither ever
fires a press, so nothing in the deterministic emulator diverges) — 0
escape commitments, 0 of either pathway, same as 023. Criterion (1):
unmeasurable, no commitment occurred. Criterion (2): LC4 θ̇ still exceeds
θ (0.94 vs 0.73) — but this was ALREADY true pre-retinotopy (see Setup),
so it is not a new signature; LPLC2 θ still exceeds θ̇ (0.99 vs 0.47) —
also unchanged in kind from baseline. Neither population's correlation
ordering flipped. Criterion (3): commitments 10 → 0, survival unchanged
(died both times), the same catastrophic result as 023, not a smaller
or partial one.

**Why a real, measured 4.4x weight improvement didn't reach threshold.**
The circuit is recurrent (CLAUDE.md invariant 4: lateral connections
3–9.5x drive onto the Giant Fiber). That amplification compounds
multiplicatively across substeps — a population that's 4.4x better
engaged at the input doesn't propagate to a 4.4x stronger DNp01 drive,
it propagates to whatever a 4.4x-larger seed becomes after many rounds
of recurrent self-reinforcement starting from a much smaller base than
the old uniform broadcast ever had. The gap between "4.4x more weight at
the origin" and "still 140 orders of magnitude short of threshold"
(1.2e-148 vs a threshold of 3.0) says the recurrent dynamics need
something close to the OLD uniform population engagement to bootstrap
at all — a Gaussian tuning curve over any single target point, however
well-centred, doesn't supply that, because most of the population is
still far from any one target by construction of a narrow, localised
receptive field.

**Hard stop, as pre-registered.** This was specified as the second and
final attempt before running it, not after seeing the result: if this
failed, retinotopy is closed permanently. It failed, on the same three
criteria as 023, decisively (0 commitments both times, identical death
frame). `retinotopic` stays default `False`. No third mapping
convention will be proposed — the failure mode this sprint found
(recurrent amplification needs population-wide engagement that no
single-target Gaussian tuning curve can supply, regardless of where its
centre sits) is a property of pairing THIS dynamical system with ANY
narrow per-cell weighting scheme, not a property of which point was
chosen as foveal. Moving the origin fixed the thing that was actually
wrong with 023's convention (checked: weight-at-origin really did rise
4.4x, exactly as predicted) and it still wasn't enough, which is a
stronger, more informative closure than 023's result alone — it rules
out "023 just picked the wrong point" as an explanation, not merely
"023 didn't move the needle."

**What we learned.** Two separable findings, kept separate. (1) The
correlation-based "is LC4/LPLC2 velocity-tuned" check, as specified in
both 023 and this sprint's own pre-registration, cannot discriminate
retinotopy's effect at all, for a reason that has nothing to do with
retinotopy: each population's correlation with its own historical scalar
drive was mechanically guaranteed before either sprint ran. This
criterion should not be reused in this form in any future sprint on this
circuit. (2) Retinotopy — real per-cell receptive fields, correctly
measured, correctly wired, with an honestly-invented convention replaced
by a data-derived one on the one axis that was actually wrong — still
cannot deliver enough population drive to move the escape circuit's
threshold-crossing behaviour, because this circuit's recurrence was
tuned around near-uniform population engagement. That is now a closed,
two-shot question, not an open one. **Scalars: 0 new** (`density_mode`
uses only already-measured per-cell data, `AZIMUTH_D_REF` unchanged from
023). **Scaffolding: relocated, not removed** — the near/foveal anchor
is now data-derived instead of an arbitrary edge, but an azimuth-to-hex
convention is still required to exist at all, and the far anchor
(`hex1.max()`) is still a hand-picked edge, left unchanged and
unjustified beyond "023 already used it." Retinotopy is closed.

## 025 — membrane noise: calibrated, and the fly gets variable, not better (`projects/legacy/runs/025a_noise_good.mp4`, `projects/legacy/runs/025b_noise_bad.mp4`)

**Setup.** One stochastic term, added once, in `dynamics.py`: `drive =
g*(W@h) + I`, now `drive = g*(W@h) + I + eta`, `eta ~ N(0, sigma)`,
resampled every substep, every neuron, in every circuit that calls
`dynamics.step`/`HybridState.step` (jump, takeoff, DNp02, steering,
speed, MDN — six call sites). W, I, thresholds, and every reward are
untouched. `sigma` lives on a new `dynamics.NoiseConfig` object (not a
module constant like `ALPHA`/`CLIP`) specifically so it has a settable
attribute a future GUI slider can bind to. Seed discipline: `main()`
takes `seed` (logged in `info["seed"]`, auto-drawn and printed if not
given) and builds ONE `np.random.Generator` shared across every circuit
for the whole episode — replaying the same seed at the same sigma
reproduces an episode exactly (checked directly: two `main()` calls,
same seed/sigma, produced byte-identical telemetry DataFrames;
`sigma=0.0` draws no random numbers at all and reproduces every pre-025
run bit-for-bit). Denormal flush kept as-is.

**Calibration, before recording anything.** Swept sigma on level 1-1, no
synthetic gap injection, `max_frames=800`, the SAME 50 seeds (0–49)
reused at every sigma value, `Pool(8)`, `OMP_NUM_THREADS=1`. Measured
per sigma: DNp01 commitment-frame median/IQR across episodes that ever
committed, how many of the 50 episodes committed at all, survival rate,
and median final distance (`max_x_abs`):

| sigma | DNp01 committed | median frame | IQR | survival | median distance |
|---|---|---|---|---|---|
| 0.0 (baseline) | 50/50 | 148.0 | 0.0 | 0% | 1432 |
| 0.01 | 50/50 | 148.0 | 0.0 | 0% | 1432 |
| 0.02 | 50/50 | 148.0 | 0.0 | 0% | 1432 |
| 0.03 | 50/50 | 148.0 | 0.0 | 0% | 1432 |
| 0.035 | 50/50 | 148.0 | 0.8 | 4% | 1432 |
| **0.04** | **50/50** | **148.0** | **1.0** | **4%** | **1432** |
| 0.045 | 50/50 | 148.0 | 1.0 | 6% | 1432 |
| 0.05 | 49/50 | 148.0 | 1.0 | 4% | 1430 |
| 0.06 | 38/50 | 148.0 | 1.0 | 6% | 1430 |
| 0.07 | 13/50 | 182.0 | 366.0 | 22% | 698 |
| 0.08 | 9/50 | 171.0 | 48.0 | 22% | 597 |
| 0.1 | 15/50 | 196.0 | 3.0 | 22% | 688 |
| 0.15 | 13/50 | 195.0 | 1.0 | 18% | 702 |
| 0.2 | 15/50 | 195.0 | 1.0 | 26% | 702 |

`sigma=0.0`'s median (148, IQR=0.0 across all 50 different seeds) exactly
reproduces 017's own deterministic commit frame — a real check that this
sweep's slightly different configuration (no gap injection, `max_frames
=800` vs 017's 1500) didn't change the reference point it's being
compared against. There is a sharp transition, not a gradual one:
0.0–0.03 show EXACTLY zero spread (every one of 50 different seeds lands
on frame 148 — the pre-025 system really is that deterministic); 0.035–
0.06 show real but small spread while DNp01 keeps firing in nearly every
episode; 0.07 onward, DNp01 frequently fails to fire AT ALL within 800
frames (9–15 of 50, down from 50/50) and survival jumps to 18–26% — a
qualitatively different regime (the pathway breaking down, not "realistic
jitter"), not explored further since it's well past what any rule below
would select.

**The stated rule, and the number it picked.** Smallest sigma producing
a visible (whole-frame, not sub-frame) spread in DNp01 commitment frame,
while DNp01 still commits in EVERY episode (50/50 — ruling out the regime
where the pathway itself starts failing to fire) and survival stays a
small, single-digit change rather than the double-digit jump seen once
that regime starts. **sigma=0.04**: IQR=1.0 (0.035's 0.8 is a weaker,
sub-frame signal — one or two outlier seeds, not a clean spread), 50/50
commit rate preserved, survival 4% (2/50) vs baseline's 0%. Full
per-seed distribution at 0.04: frame 147 (2 seeds), 148 (32, the
baseline value), 149 (8), 150 (1), 151 (1), 152 (6) — a real 5-frame
spread around the deterministic value, not noise in the measurement.

**The two-episode deliverable, and what it actually shows.** Same seed
set, sigma=0.04. `projects/legacy/runs/025b_noise_bad.mp4`, **seed 5**: DNp01 commits at
frame **149** (one frame later than 017's 148) — and dies at frame 406,
reaching only x=694, versus the deterministic baseline's death at frame
689 having reached x=1432. A one-frame delay in the FIRST commitment
cascaded into a completely different, much shorter run — this is the
"later commitment cost a life" case, real and clean. `projects/legacy/runs/025a_noise_
good.mp4`, **seed 25**: survived the full 800 frames (`died_or_flagged=
False`) despite an EVEN LATER first commit (frame 152) — but checked
the telemetry before calling this a win: `max_x_abs=658`, far short of
baseline's 1432, and the DNp02 log shows commits recurring every ~65
frames with `theta=0.000 d_px=None` (no real enemy) from frame 369
onward — Mario is stuck oscillating in place, not making progress, and
"survival" here means "never reached the threat that kills the
deterministic run" rather than "escaped better." **Stated plainly, as
pre-registered: neither seed matches the hypothesised "earlier
commitment clears a Goomba the baseline hit" shape** — in this sweep,
the baseline commits successfully at frame 148 against every seed's
first encounter regardless of sigma (DNp01 never fails the FIRST
encounter until sigma is well past 0.04), so there was no baseline
failure for an earlier commitment to correct. The real divergence this
sigma produces is a small commit-frame perturbation cascading into
categorically different DOWNSTREAM trajectories (different later deaths,
or a stuck loop) — reported as found, not reshaped to fit the
hypothesis.

**The suspicious case, stated separately, as instructed.** 2 of 50
seeds "survived" at sigma=0.04 (4% vs baseline's 0%) — technically an
improvement. Checked, per the pre-registered caution: both are the
stuck-oscillation artifact described above (seed 25 and seed 45, both
committing at frame 152, both plateauing around x=600–660 rather than
genuinely escaping further than baseline). This is NOT "the deterministic
run was sitting in a bad local corner that noise found a way out of" in
the sense of better escape behaviour — it's noise occasionally nudging
Mario into a different failure mode (stuck, not dead) rather than a
better outcome. Worth a future sprint's attention (why does this
particular stuck state recur at a fixed ~65-frame cadence), not
resolved here.

**What we learned.** The calibration rule worked exactly as designed:
it found a real, sharp transition between "no measurable effect" (sigma
<=0.03, confirmed against 50 different seeds each) and "the escape
pathway itself starts failing" (sigma>=0.07), and picked the value just
past the former. At that value, noise does what it was built to do —
real, small, seed-dependent variability in exactly the metric this
project has always reported as deterministic (DNp01 commitment frame)
— and does NOT make the fly better: median survival moved from 0% to
4%, a small change, and the mechanism behind that small change is a
stuck loop, not improved escape, exactly the "different finding, stated
separately" the pre-registration anticipated rather than a genuine
survival improvement. **Scalars: +1 (`sigma`, stated plainly, as
specified). Scaffolding: 0**, as expected — no RAM convention, no
invented distance or edge, just a real Gaussian on a real quantity
already in the model.

## 026 — brain panel: speed and layout, a rendering note (`projects/legacy/runs/026_panel_017_reprise.mp4`)

No behaviour changed (nes-py/circuits/telemetry untouched) — a brief
note, not a four-field entry, as specified for a pure rendering sprint.

Profiled `panel()` first (`profile_brain_panel.py`): 8.4ms median for one
frame (worst case, every banner active, 10.2ms) against a 16.7ms
real-time budget — already under budget before touching anything. The
one real waste: `_font()` reloaded three TTF files from disk on every
single call, ~2.7ms/frame for zero reason (fonts never change). Cached
it the same way the soma background already was; full panel() dropped
to 5.1ms median. Per the sprint's own stated rule ("if this lands under
budget, stop"), no GPU port was attempted — CuPy scatter_add was not
written, and nes-py remains a sequential CPU emulator that sets a floor
regardless, per CLAUDE.md's own GPU section.

New layout, 1536x1080: left column (512px) is the brain silhouette in
the upper 2/3 (512x720) with **nothing overlaid on it** — spikes and
population glow are still drawn at real soma positions, that's the
whole point of the panel, but every piece of text (legend, numeric
values, `steer R_team=…/L_team=…`, every banner: SPIKE/CLIMB/CONFLICT/
PIT/LONG JUMP/REFUSING/ODOUR OVERRIDE) moved to a dedicated 512x360
telemetry strip below it. Right column (1024px): the emulator frame at
integer 4x (256x240 -> 1024x960), `Image.NEAREST` (no interpolation —
pixel art), vertically centred with a 60px letterbox top and bottom.
After the layout change, full panel() re-profiled at 5.8ms median —
still comfortably under budget.

Re-rendered 017's exact scenario (same `main()` call: level 1-1,
`max_frames=1500`, `inject_gap_frame=600`) with the new panel rather
than inventing a new one, so the layout is comparable to something
already watched — reproduced 017 event-for-event (807 frames, same
commit/odour/`?`-block/long-jump frames down to the integer). Only the
rendering changed.

## Refactor phase 0-1 — characterisation tests and file moves

No behaviour changed (no circuit, telemetry column, or default touched) — a
short note, not a four-field entry, per `docs/REFACTOR_PLAN.md`'s own
instruction for a pure infrastructure step.

**Phase 0.** Froze telemetry for three runs -- 026's reprise of 017 (1-1,
gap injection at frame 600, sigma=0), 025b (seed=5, sigma=0.04), and a new
sigma=0 baseline at 025's own sweep config (1-1, `max_frames=800`, no
injection) -- into `tests/golden/`, with `tests/test_golden.py` asserting a
fresh `run_steering.main()` call reproduces each byte-for-byte. All three
were deterministic: green twice in a row (separate processes), ~27s total
per pass, and (017/025b) byte-identical to the CSVs already shipped in
`runs/` from weeks-old runs -- confirming 025's determinism claim still
holds today, not just at the time it was measured.

**Phase 1.** Moved `SPEC_jump.md` and `REFACTOR_PLAN.md` into `docs/`
(`MECHANISMS.md`/`RUNS.md` were already there, a surprise the plan's own
directory diagram didn't anticipate); migrated all 59 files under the old
`runs/` (26 sprints' worth of videos, notes, telemetry CSVs, one raw JSON
sweep) into `projects/legacy/runs/` and `projects/legacy/telemetry/` --
copy, verify count and byte-for-byte MD5 against the originals, remove,
never bulk `mv`, per CLAUDE.md's own rule; created the empty `fly/`,
`mario/`, `bridge/`, `sim/`, `render/`, `config/` package skeleton with
nothing but `__init__.py` in each, no code moved yet; rewrote every
`runs/NNN_*` path this log itself references, plus the handful of other
places (`CLAUDE.md`, `README.md`, `SPEC_steering.md`,
`profile_brain_panel.py`, two migrated per-run notes) whose pointers to
`SPEC_jump.md` or a specific migrated file would otherwise have gone stale.
Zero logic edits. Goldens re-run and green after the move, proving the
harness catches a real regression before phase 2 touches anything risky.

## Refactor phase 2 -- the fly/mario split and entity records

No behaviour changed (verified, not assumed -- see below) -- a short note,
not a four-field entry, same as phase 0-1's.

Housekeeping first, from phase 0-1's own findings: corrected
`docs/REFACTOR_PLAN.md` section 3's diagram in place (it wrongly implied
`RUNS.md`/`MECHANISMS.md` needed moving; they were already in `docs/`);
decided and wrote down run-media durability in `CLAUDE.md` (video stays
ephemeral and `.gitignore`d, telemetry CSVs and `.md` notes are the durable
artifact -- every finding in this log has always come from a CSV number,
never a video frame); flagged in the plan that `out_mp4="runs/..."`
defaults still point outside the new structure until phase 5.

Then the split: `fly/` (connectome, network, circuits, sensing, state) and
`mario/` (ram, entities, actions, emulator) now exist as real packages,
with `bridge/perception.py`/`motor.py` as the only modules importing both
-- enforced by `tests/test_import_guard.py`, which parses every `fly/*.py`
file's AST and was checked to actually fail on a real violation before
being trusted. `EntityRecord`/`KindRegistry`
(`mario/entities/`) replace three independent copies of
`ram[ADDR_ENEMY_TYPE+i] == POWERUP_ID` (`run_mario.py`'s `enemy_thetas`,
`run_steering.py`'s `mushroom_odor`/`goomba_odor`) with one classification
-- the one real duplicated ROM fact this phase found and fixed, not just
documented. `docs/ENTITIES.md` has the full report, including what the
entity model deliberately does NOT cover yet (no per-species
discrimination exists anywhere in this codebase -- a Goomba and a Koopa
are the same `ENEMY` kind, because nothing has ever read the type byte for
anything except the one powerup check).

Verification: `tests/golden/` byte-identical before and after every step
of the split, checked incrementally rather than once at the end. Along the
way, found and fixed a real test-harness fragility (not a behaviour bug):
running the new `tests/test_entities.py` before `tests/test_golden.py` in
one pytest session perturbed the goldens' floating-point output at the
16th significant digit -- BLAS latching its thread count from the ambient
environment before `run_steering.py`'s own thread-count `setdefault` could
run. `tests/conftest.py` now sets it before pytest imports any test module
at all. Full suite green twice, two separate processes, after the fix.

## Refactor phase 3 -- one Network, one Integrator, six sites unified

No behaviour changed -- verified byte-identical against `tests/golden/`
after every single one of the six sites, not just once at the end, plus a
dedicated equivalence test (`tests/test_integrator_equivalence.py`) written
and run BEFORE any live call site was touched. Short note, not a
four-field entry, same convention as phases 0-2.

Before touching anything, re-verified phase 2's BLAS thread-latching fix
(`tests/conftest.py`) was still holding: full suite green twice, plus the
specific ordering (`test_entities.py` before `test_golden.py`) that
exposed it originally, still passing on its own. It was.

`fly/network/integrator.py`'s `Integrator` and `fly/network/network.py`'s
`Network` replace `dynamics.step()`/`dynamics.HybridState.step()` at all
six of `run_steering.py`'s live call sites (jump, takeoff, dnp02, steering,
mdn, speed). The unification rests on one identity, checked directly
before relying on it: `HybridState` with an EMPTY spike index reduces
exactly to plain `dynamics.step()`, because `h_new[np.array([])] =
spike_out` is a no-op. So one `Integrator` class serves both shapes --
the four non-spiking circuits simply never get a spike index.
`fly/network/dynamics.py` itself is untouched (`run_mario.py`'s own
sprint-001 demo and every `tune_*.py`/`diag4.py` script still use it
directly).

**The six sites, what was asked to be reported: were they identical?**
Mostly, but not entirely -- one real, previously-undocumented
inconsistency was found, not just refactoring detail:

- **alpha** (leak rate): identical across all six -- the module default
  (0.3), never overridden at any site.
- **clip ceiling**: identical -- the module default (50.0) via `phi()`,
  including both spiking circuits' `spike_amp`, which also equals 50.0.
- **noise**: identical -- all six read from the SAME shared `NoiseConfig`
  instance (one `rng`, seeded once per episode).
- **SUBSTEPS** (10 per frame): identical at all six. MDN additionally
  skips its own substep loop entirely on frames it's already mid-backup
  (a mechanical hold-state gate, not a numeric difference between sites).
- **denormal flush -- DIFFERED.** Five of six (takeoff, dnp02, steering,
  mdn, speed) flush `h[h < 1e-30] = 0.0` once per frame, right after their
  own SUBSTEPS loop. **The jump circuit's own state has never been
  flushed, anywhere, since the flush was introduced** -- confirmed by
  reading every line touching `hj`/`jump_state` before writing a single
  line of the new code, not discovered by the goldens failing. This is
  preserved exactly as found: `jump_network` is the one of the six
  `Network` instances whose caller never calls `flush_denormals()`. Fixing
  it would change jump's numeric output (a denormal value survives into
  the next `W @ h` instead of being hard-zeroed first) -- a real behaviour
  change, not this phase's to make silently. Flagged here for whoever
  decides it next, with the exact fix (`jump_network.flush_denormals()`
  added after its SUBSTEPS loop, matching every other site) sitting one
  line away.
- **spiking sub-population**: jump and dnp02 use the leaky-integrate-and-
  fire override on DNp01/DNp02 respectively; the other four are plain
  rate-coded populations. This is a real structural difference, but by
  design, not inconsistency -- matches the connectome fact that only
  DNp01/DNp02 have a documented spiking role in this project (SPEC_jump.md
  section 1b, SPEC_second_escape.md).

**A seventh candidate, checked and excluded.** The mushroom body's own
`h_mbon` update (`mbon_drive = W_kc_mbon @ kc_active`, one line) reuses
`dynamics.ALPHA`/`dynamics.phi` but is not one of the six: no SUBSTEPS
loop (steps once per frame, not ten times), no noise term, no `g` gain,
and feedforward rather than recurrent (`kc_active` is an input, not
`h_mbon` itself, unlike every one of the six). REFACTOR_PLAN.md section 6
already separates this out ("the mushroom body's plasticity is an
injected collaborator, present only where it applies") -- confirmed here
that its underlying update shape is different enough that forcing it onto
`Network`/`Integrator` this phase would be a redesign of a genuinely
different computation, not a move. Left untouched.

**Scoping decisions from REFACTOR_PLAN.md's own sketch, stated plainly:**
`Network.populations` stores named boolean masks, not `dict[str, slice]`
-- every one of the six circuits already selects by mask
(`bodies["type"]==...`), and reordering six real connectome-derived weight
matrices into contiguous slices is a separate, higher-risk change than
unifying the update math. `Network.weights` stays a dense `ndarray`, not
`scipy.sparse` -- a real optimisation with its own profiling obligation
(CLAUDE.md's GPU section), not a rename. Existing mask-based indexing at
every call site is unchanged; `populations` is real and populated, but
nothing yet reads through it instead of the same masks constructed
alongside it.

Also, per this phase's own instruction: a plan amendment (separate commit)
schedules enemy-species decoding as an explicit phase-4 item, and
docs/ENTITIES.md now notes that every earlier "avoided the Goomba" result
is really "avoided the enemy" -- see that commit for the reasoning
(phase 6's eligibility trace needs at least two discriminable stimuli).

## Refactor phase 4 -- config extraction and species decoding

No behaviour changed -- verified byte-identical against `tests/golden/`
after config extraction and again after species decoding, each checked
separately. Short note, not a four-field entry, same convention as
phases 0-3.

**The denormal probe (separate commit, before this one).** Phase 3 found
the jump circuit's own state has never been flushed. Measured directly on
jump's real weight matrix (`denormal_probe.py`) rather than trusting
CLAUDE.md's inherited 84x claim: genuine denormals do occur (down to
float64's smallest representable subnormal), but the actual speedup is
~3.2x under a realistic trace and ~4.7x worst-case -- real, but nowhere
near 84x, and `shuffle_sweep.py` in the current repo applies no flush at
all, so the original measurement's supporting code no longer exists in
this form. CLAUDE.md corrected to state the measured numbers. Fix NOT
applied to jump -- flagged for a dedicated future sprint, since it
re-baselines every golden.

**Config extraction.** `config/params.py`: 15 frozen dataclasses, one per
component, every field typed with a default matching today's exact value
and a documented range or an explicit `unknown` -- an invented bound would
have been scaffolding that looked like data, so almost every field is
`unknown` on purpose. **The honest count: 49 hand-set scalars**, not the 8
or 9 this project's own comments had been citing across 26 sprints. Two
were found while building this file and had never been flagged anywhere:
bare numeric literals inside `retinotopy.py`'s `receptive_field_centers()`
(a fallback bandwidth and a spread floor), promoted to documented fields
even though that whole module is dormant. `docs/SCALARS.md` is generated
directly from the dataclasses (`config/scalars_doc.py`,
`tests/test_scalars_doc.py` keeps the two in sync) rather than written by
hand. `run_mario.py`/`run_steering.py`/`bridge/perception.py`'s own scalar
definitions now read from these dataclasses; `fly/network/dynamics.py` and
three other widely-reused modules deliberately still self-define theirs,
checked equal by `tests/test_params_match_live.py` instead of rewired, to
avoid a rename-only risk to code used by a dozen diagnostic scripts
outside the live path.

**Species decoding.** `KindRegistry` now decodes real species from
`ADDR_ENEMY_TYPE` for the two confirmed present in 1-1/1-2 -- `GOOMBA`
(`0x06`) and `KOOPA` (`0x00`), both screenshot-verified via a bot-driven
survey (the real circuit dies too early to see much of either level;
`docs/ENTITIES.md`'s phase 4 section has the full method and evidence).
Koopa's identification corroborates sprint 010's own independent manual
RAM-inspection finding of the same byte. A third byte, `0x0D`, appeared
further into 1-2 (abs_x~1400) but scrolled off-screen before a screenshot
could confirm it -- left as generic `ENEMY` rather than guessed, the same
standard `tile_ram.py`'s own tile IDs were held to. **1-1, surveyed to
abs_x=1522 (beyond any controller in this project has ever reached it, the
real circuit's own death point included), is entirely Goombas** -- exactly
the scenario the phase-3 plan amendment warned about. 1-2 has both
confirmed species, but only past its underground section (frame ~338),
which today's baseline circuit doesn't survive to (dies at frame 84).
Phase 6's
eligibility trace will need a savestate into 1-2's underground section,
or a different level, not 1-1 alone. `bridge/profiles/default.json` gives
`GOOMBA`/`KOOPA` distinct odour channels -- discrimination is now
POSSIBLE in data, not switched on: `bridge/perception.py`'s functions
still branch only on `== EntityKind.POWERUP`/`!=`, identically before and
after, so every non-powerup entity still sums into one undifferentiated
aversive signal. Verified byte-identical against goldens both before and
after this change, confirming the `!=`/`==` comparisons never depended on
which specific non-powerup kind something is.

## Refactor phase 5 -- Episode, protocols, fitness, output routing

No behaviour changed -- verified byte-identical against `tests/golden/`
after every piece, checked separately. Short note, not a four-field entry,
same convention as phases 0-4.

**Carry-over, done first:** CLAUDE.md invariant 3 still said "exactly two
hand-set scalars" against `docs/SCALARS.md`'s own generated 49 -- fixed as
this sprint's first commit, per its own instruction.

**Episode/Policy/Environment**, per section 5.2's own snippet verbatim
(`sim/protocols.py`). `sim/episode.py`'s `Episode` composes one of each and
notifies observers, importing nothing from `fly/`/`mario/`/`bridge/` --
enforced by a new import-guard test, checked to actually fail on a real
violation before being kept, same discipline as the original fly-vs-mario
guard. Proven end-to-end with REAL implementations, not a toy pair:
`mario/emulator/environment.py`'s `MarioEnvironment` (nes-py wrapped
directly) and `bridge/policy.py`'s `JumpPolicy` (the escape/jump circuit,
self-contained since phase 3). **Scoping decision, stated plainly:**
`JumpPolicy` is genuinely narrower than `run_steering.main()`'s full
system -- no steering, terrain, mushroom body, habituation, or MDN.
Migrating that whole system onto this interface is real, separate,
substantial work -- large enough that attempting it inside this same
sprint would have repeated phase 3's own lesson (a rewrite this size needs
its own dedicated, one-thing-at-a-time verification, not a bolt-on to
three other deliverables). `run_steering.main()` remains today's actual
entry point for a full scenario; whoever migrates it next has real,
tested scaffolding to migrate onto, not a stub.

**Telemetry is a live observer today, not deferred.** The old
`log = {k: [] for k in (...)}` + ~53 individual `log[col].append(value)`
calls + `pd.DataFrame(log)` -- the exact pattern sprints 017-022 kept
touching to add one field -- is now `sim/telemetry.py`'s
`TelemetryObserver`: `row = observer.new_row()`, `row[col] = value` per
frame, `observer.record(row)`, `observer.to_dataframe()`/`.write()` at the
end. Column order fixed once, at construction, exactly as the old dict
comprehension fixed it. Wired into `run_steering.py`'s actual `main()`,
verified byte-identical including the `frame_skip` repeat-last-row path.

**Fitness**, per section 6: `distance` defaults to 1.0 and rejects zero or
negative -- 025's finding (an episode "survived" 800 frames oscillating at
x=658 against a baseline that reached x=1432) made structural, not just
documented. Computed and recorded only, per this phase's own instruction
-- no live call site reads it, and none should yet.

**Output routing.** `run_steering.main()`'s `out_mp4` has no default any
more (was `"runs/008_run.mp4"`, a silent stray top-level fallback -- every
caller in this repo already passed an explicit one; checked before
removing it). A bare `main()` call now raises. `config/output_routing.py`
turns a `ProjectConfig` into `projects/<name>/runs/...` /
`projects/<name>/telemetry/...`, raising when `project_name` is unset.
`sim/project_runner.py` ties a `ProjectConfig` to `run_steering.main()`
directly -- not through `Episode`, which must never import fly/mario/
bridge; this is glue for today's real system, not a smaller stand-in.

**The config round-trip, proven:** `projects/legacy/config.json` (every
component param at its phase-4 default, scenario set to 017's own level/
max_frames/inject_gap_frame) loads, runs, and produces
`projects/legacy/telemetry/017_reprise_config_roundtrip_telemetry.csv`
byte-identical to `tests/golden/017_reprise_telemetry.csv`. First moment a
project is reproducible from one file, per this phase's own instruction.

Also checked and left alone: CLAUDE.md's own "every change ends with a
video in `runs/`" convention doesn't actually contradict the `out_mp4`
default's removal -- every sprint has always passed an explicit path
matching that convention already; only the *silent, unrequested* fallback
was the problem, and only main()'s own bare-call default did that.

Full 47-test suite (goldens, both import guards, integrator equivalence,
params-match-live, scalars-doc, entities, episode, fitness, telemetry
observer, config round-trip) green twice, two separate processes.

## Refactor phase 5b -- the full system onto Policy

Phase 5's own scoping decision closed here: `run_steering.main()`'s full
system (jump, takeoff, DNp02, odour, mushroom body, steering, climb,
escape resolution, MDN, speed) now runs through `bridge/full_policy.py`'s
`FullPolicy`, not main()'s own locals. Verbatim transcription, not a
redesign (that module's own docstring says so directly) -- three commits,
goldens between each, same discipline as phase 3's six-site migration:
add `FullPolicy` as dead code first (verified via a 300-frame smoke run
against the real emulator, whose printed commit/climb/qblock trace
matched `main()`'s own exactly); wire its constructor into `main()` while
leaving the frame loop's own text untouched (isolates "does construction
match" from any loop-logic question); then replace the loop body itself
with one `policy.act()` call. A fourth commit removed the per-episode
locals the first two left dead (jump_hold_frames and siblings, prev_theta,
d_history, ..., every counter's initial 0) -- actively misleading once
`policy.reset(seed)` owned all of it.

**The mushroom body now updates in exactly one place.** This was the
sprint's actual reason to exist: phase 6's eligibility trace attaches to
`FullPolicy`'s own KC/MBON update, and there is no second copy in main()
left to double-write it. Migrating the loop body surfaced a real bug this
sprint fixed rather than shipped: the death-triggered punishment block
read main()'s own `mb_elig` local directly, which goes stale the instant
`policy.act()` starts reassigning `self.mb_elig` every frame (a `+`, not
a mutating `+=`) instead of the old code's single per-call binding. Moved
onto `policy.on_step()` -- the dual Policy/Observer role phase 5's own
design sketched for exactly this ("the death-triggered mushroom-body
punishment... apply it via `on_step()`") -- which reads `self.mb_elig`
fresh and has no staleness to have. The end-of-run counter summary and
`max_x_abs` in the return dict had the identical problem (main()'s locals
froze at their initial 0/None once `policy.act()` took over incrementing
them) and got the same fix.

**Both import guards re-verified, not just re-run.** Per this sprint's
own instruction, each guard was made to actually fail: a real `import
mario.ram.tile_ram` appended to `fly/network/dynamics.py` failed the
fly-guard, a real `import bridge.perception` appended to `sim/episode.py`
failed the Episode-guard, both reverted after confirming the failure
message named the real file and the real forbidden import. Neither guard
needed to change -- `sim/episode.py`/`sim/protocols.py` were never touched
this sprint, and `main()`'s own loop still lives in `run_steering.py`,
not `sim/episode.py`, a stated scoping decision below.

**Scoping decision, stated plainly, not silently under-delivered:**
`main()`'s own `while frame < max_frames and not done:` loop is still
what drives a real run -- not `sim.episode.Episode.run()`. `main()` owns
real test-harness features `Episode`/`MarioEnvironment` don't support
(`frame_skip` action-repeat, `savestate` backup/restore, `inject_frame`/
`inject_gap_frame` synthetic RAM pokes, `force_mario_size`) and extending
`MarioEnvironment` to cover all of them is its own real, riskier change,
not a rename. What phase 5b's own mandate actually asked for --
"`ProjectConfig` drives the whole system, not a subset," and "the
mushroom body updates in exactly one place" -- is satisfied without it:
every decision now runs through one real `Policy` (`FullPolicy`), built
from one `ProjectConfig`, and `main()` is a thin caller of it, the same
relationship `Episode` has to a `Policy` in miniature. `FullPolicy.on_step`
is written for the real `Episode.observers` contract already, so wiring
`main()`'s own loop onto `Episode` later is additive, not a further
rewrite of the decision logic itself.

**The event count, the other half of this sprint's ask.** Per-episode
rewarded-event count on 1-1, baseline (`sigma=0`, `seed=0`, `max_frames=4000`,
689 frames to death, `max_x=1432`) plus a 20-seed `sigma=0.04` sweep,
counting mushrooms collected / damage taken / enemies stomped / `?`
blocks hit (`main()` run unmodified, a read-only monkeypatch on the
stomp proxy only, no code change):

| | mushrooms | damage | stomps | qblock hits | total |
|---|---|---|---|---|---|
| baseline | 0 | 0 | 0 | 7 | 7 |
| 20-seed sweep | 0 (all 20) | 0 (all 20) | 0 (all 20) | 4-7 (median 7, mean 6.45) | 4-7 |

**This is a worse result than docs/TRACE_BIOLOGY.md's own open question
anticipated.** That document asked whether the two discriminable classes
(mushroom appetitive, enemy aversive) occur often enough to learn from --
the answer here is not "rarely," it's "never, in every one of 21 runs
tried." Every single rewarded event on 1-1 under the current baseline is
a `?`-block hit (PAM only). Zero mushrooms are ever collected (odour pulls
toward one, but nothing in this circuit's repertoire executes "hit the
block a mushroom spawns from" as a distinct skill from qblock-hitting
itself -- the mushroom census is a downstream consequence of a block hit
that hasn't happened to spawn one across 21 runs, not an independent
event). Zero stomps and zero damage in every run -- Mario's own vertical
hitbox mechanics for stomping aren't modelled at all, and every death this
circuit has ever produced has been from a Goomba PIT/side collision the
telemetry doesn't distinguish from any other death for reward purposes.
**Phase 6 has one discriminable stimulus class to learn from on 1-1, not
two, and needs a different level or a synthetic/injected discriminator to
test the aversive (PPL1/PPM) side of the plasticity rule at all** -- this
is exactly the kind of finding docs/TRACE_BIOLOGY.md's own closing line
asked to have in hand before building, not after a null.

Goldens byte-identical, twice, separate processes, after every commit.
Both import guards green (and re-verified to fail on a real violation).
Full 47-test suite green, twice, separate processes.

## Refactor phase 5b, correction — the event count above was wrong

**Not an edit of the entry above — per this file's own rule, a correction
gets a new entry, especially when the original one was wrong.** Two
mistakes, both in the measurement script, not in `FullPolicy` or
`main()`: "damage taken" was a shrink proxy (`mario_size` decreasing) on
a Mario who never grows, so it could only ever read zero and told us
nothing about whether an aversive event happens; and the stomp proxy
reused `enemy_thetas`'s own `d_px`, which tracks only the single dominant
enemy per hemisphere, so a stomp on any other slot was invisible to it.

Recounted, same 21 runs (baseline + 20-seed `sigma=0.04` sweep), fixed
both: death (`main()`'s own `died_or_flagged`) as the aversive event, and
a direct RAM scan of all 5 enemy slots' active+type bytes for the stomp
proxy (a slot active and within 20px of Mario one frame, gone the next).
Mushroom spawns (a slot's type/active bytes turning into `POWERUP_ID`)
counted separately from collections (`mario_size` increasing), per this
correction's own instruction: a spawn nobody catches is a live pathway
failure, not an absent reward class.

| | mushroom spawns | mushroom collected | death | stomps | qblock hits | total |
|---|---|---|---|---|---|---|
| across 21 runs | 0 (0 runs) | 0 (0 runs) | 1 (21 of 21 runs) | median 5, sum 87 | median 7 | median 13, mean 11.6, min 6, max 13 |

**Stomps are real, verified against a false-positive concern before being
trusted:** checked one run's stomp frames (245, 412, 535, 546, 681)
against its death frame (689) -- the last stomp lands 8 frames before
death, none cluster at the end, ruling out "the killing collision itself
deactivates the enemy slot" as the source. DNp01/DNp02's escape jumps are
timed to clear an approaching enemy, and SMB's own jump arc frequently
puts Mario's falling hitbox on top of it on the way down -- a stomp this
circuit never aims for, but gets as a side effect of timing the jump
right, most of the time (median 5 of ~9 escape commitments per run).

**Mushrooms never spawn at all in any of the 21 runs, so their absence
is not evidence of a broken 016 odour pathway** -- there is nothing for
that pathway to fail to catch. SMB's own spawn rule (a `?` block flags
"contains a powerup" once per level, at a fixed block, gated on Mario's
size at the moment of the hit) means catching one requires hitting that
specific block while small; 1-1's own qblock geometry relative to where
these runs die (`max_x` 694-1437, deaths and pit encounters between the
first and second block clusters) may simply not put this circuit in
range of the powerup-flagged block before it dies -- untested here, a
level-geometry question, not a circuit question.

**Revises phase 5b's own conclusion.** There is not "one discriminable
stimulus class to learn from" -- there are two, both common (median 13
combined events per run): qblock hits (appetitive, PAM) and death
(aversive, PPL1/PPM), with stomps as a third, currently-unrouted signal
(the mushroom body's punishment path is wired to death only, not to
individual stomps -- whether a stomp should also carry dopamine is a
phase 6 design question, not answered here). The synthetic-discriminator
concern is gone; the real open question is whether 60-120 frames of
`EligibilityTrace` reach back far enough from a mid-episode qblock hit or
stomp to the decision that caused it, not whether events exist to learn
from.

## 027 — the eligibility trace: persistence, provenance, event-proximal dopamine, and the sign test (`projects/legacy/runs/027_event_proximal_dopamine.mp4`)

**Setup.** REFACTOR_PLAN.md phase 6, the only refactor-line phase that
changes behaviour. Four pieces, in the order the sprint's own prompt
gated them: (1) `tests/test_mb_persistence.py` -- KC->MBON weight
persistence, on the open list since sprint 014, never checked before now,
made a hard prerequisite because death is the only aversive event, fires
once, and is terminal, so punishment learning exists only across
episodes. (2) `trace_decay` (60 frames, unchanged) reprovenanced from an
uncited "measured" claim to a real citation, docs/TRACE_BIOLOGY.md's own
literature check (Handler et al. 2019: KC->MBON synaptic-tag plasticity
significant at ISIs of -1.2s/0s/+0.5s, negligible by 6s), range set to
that window (60-120 frames, was `unknown`). (3) `fly/plasticity/
dopamine.py`'s `event_dopamine()`, routing `?`-block-hit/stomp -> PAM and
death -> PPL1/PPM, reusing `dynamics.CLIP` for magnitude on both sides
(no new scalar) -- gated behind `FullPolicy.event_proximal_dopamine`
(default False, a mode flag like `retinotopic`, not a scalar) so goldens
stay frozen against the pre-phase-6 continuous-progress trigger. (4)
`fly/plasticity/three_factor.py` extracts the depression-only update rule
itself (`update_eligibility`, `depress`) out of the inline mushroom-body
block, so `tests/test_mb_sign_test.py` can drive the REAL rule with a
synthetic KC/DAN protocol at controlled ISIs, not a reimplementation.

**What happened.** Persistence: the round trip (`np.save`/`np.load`) was
already exact, but the FIRST real check -- a genuine subprocess restart
reloading a trained matrix and continuing training, compared against an
uninterrupted in-process continuation -- failed on its first run, and not
for the reason it was written to catch. `FullPolicy.__init__` took a
passed-in `mb_weights` by reference, not by copy; `self.W_kc_mbon -=
(...)` (numpy's in-place `__isub__`) was silently mutating the CALLER's
own array, so the test's own "before" snapshot got rewritten out from
under it mid-episode and reported "no learning happened" when what had
actually happened was "the two things being compared were, by then, the
same object." Fixed with one `.copy()`; both checks pass afterward
(exact round trip; subprocess-reload continuation byte-identical to an
in-process one). Pre-existing since sprint 014, not introduced by phase
5b's move -- no golden or existing caller ever passes `mb_weights`, so
this changed zero recorded behaviour (verified, not assumed).

The sign test's result, run before any episode per the prompt's own gate:
forward pairing (KC fires, dopamine arrives ~5 frames later, well inside
the trace window) depresses the synapse. Backward pairing (dopamine
arrives, KC fires 5 frames later) produces **no significant change, not
the opposite sign** -- `depress()` has no branch that can ever add
weight, regardless of order. The rule does not reproduce Handler et al.
2019's bidirectional, order-dependent finding; it implements
SPEC_mushroom_body.md section 4's own earlier, different, also-documented
model instead (valence comes from WHICH MBON gets depressed -- approach-
promoting or avoidance-promoting -- not from a sign flip on one synapse).

Class imbalance, measured two ways. Per docs/RUNS.md's phase 5b
correction: ~12-13 appetitive events per episode (median 7 qblock hits +
median 5 stomps) against exactly 1 aversive event (death, every episode).
An idealized closed-form check (best-case eligibility = 1, using the real
`depress()` function) predicted PAM-reachable synapses would collapse to
<1% of their original weight within 8-10 episodes while PPL1/PPM-
reachable synapses were still at 60%+ -- a dramatic, fast-saturating
picture. **A real 15-episode training run (same savestate, `frame_skip=
1`, `event_proximal_dopamine=True`) measured something much more modest,
and the idealized estimate is flagged here as wrong, not quietly
dropped:** starting from the untrained connectome (overall mean
0.000201, 15.5% of entries nonzero -- a naturally small, sparse matrix,
not the "1.0" the idealized check assumed), the top-10%-by-reach PAM
population moved from 0.000171 to 0.000162 over 15 episodes (-5.3%,
~180 combined qblock+stomp events) while the top-10%-by-reach PPL1/PPM
population moved from 0.000174 to 0.000172 (-1.1%, 15 death events) --
real eligibility values during actual gameplay sit far below the
best-case ceiling the idealized check assumed (KC activity is sparse and
EMA-smoothed, not continuously saturated), so real depression per event
is far gentler than the worst case. The measured **per-episode** decay
rate is ~4.6x faster for the appetitive channel than the aversive one --
directionally exactly what a 12:1 event-count imbalance predicts, but
smaller than 12:1 because punishment turns out to be **~2.6x more potent
per individual event** on its own reachable synapses than reward is on
its (`punish_reach`/`pam_reach` top values are comparable in raw
magnitude, but the two populations aren't identical). At these real
rates, reaching 50% depression by extrapolation is ~140 episodes for the
appetitive channel and ~650 for the aversive one -- gradual on the scale
of a real training run, not an instant floor.

Demonstration run: baseline scenario (1-1, σ=0, seed=0) with
`event_proximal_dopamine=True` -- 689 frames, dies at the identical point
as the legacy-trigger baseline, max_x=1432. Identical on screen to every
other σ=0/seed=0 video in this project, because a single episode's WTA/
escape/steering decisions never read mushroom-body output strongly enough
to diverge visibly -- what changed is invisible on screen and visible
only in which frames actually depressed a synapse (7 qblock hits + 5
stomps, not ~650 frames of forward progress). Goldens (frozen against the
legacy trigger, `event_proximal_dopamine=False`) stayed byte-identical
throughout, checked after every commit, twice, separate processes.

**What we learned.** The persistence prerequisite would have failed
silently in exactly the way the sprint's own prompt warned about, but not
via the mechanism it named -- not "punishment never gets applied," but
"punishment gets applied and then a naive verification of that fact
lies about it" (an aliasing bug that made a real training loop's own
carried-forward weights correct all along, while making THIS TEST's
attempt to double-check that fact wrong). Fixed and verified; the
prerequisite holds.

The sign test is the one negative result this sprint reports as a fact
about the implementation, not a bug: this project's plasticity rule is
depression-only in a way that structurally cannot match Handler et al.'s
bidirectional coincidence-detection finding, and that's an existing,
stated design choice (SPEC_mushroom_body.md section 4) from before this
sprint, not something phase 6 broke. Anyone building further on this
mechanism needs to know it's the "different MBON populations" model, not
the "same synapse flips sign" model, before assuming order-of-events
sensitivity that isn't there.

The class-imbalance finding is real but smaller than the naive 12:1 ratio
suggests, and the FIRST estimate of it in this sprint (idealized,
best-case eligibility) was itself wrong by orders of magnitude --
CLAUDE.md invariant 7's own lesson (measure the actual thing, a
plausible-sounding calculation isn't a substitute) applying here to a
learning-rate question instead of a GPU one. The real, measured
consequence: over any realistic training run, the appetitive channel
will end up several times more depressed than the aversive channel per
unit of wall-clock training, not because reward matters more per event
(punishment is actually more potent per event) but purely because it
fires ~12x more often. Whether that's a problem depends on what the
mushroom body is FOR in this system -- if steering/DNp02 bias is meant to
track "is this a place that's been good," an appetitive-dominated signal
may be exactly the intended shape; if aversive learning (avoiding the
kind of encounter that caused a specific death) matters as much, this
imbalance means it will take roughly an order of magnitude more training
to matter at all.

**Not answered here, and flagged rather than skipped:** whether the new
event-proximal trigger changes Mario's behaviour for the better than the
old continuous-progress trigger over many episodes of real training --
this sprint verified the mechanism runs correctly and characterised what
it does to the weights, not whether it improves anything. That's its own
measurement (a real multi-episode training curve, event-proximal vs
legacy, compared on survival/distance), not attempted here.

Deliverables: goldens green at σ=0 with the new mechanism disabled (3/3,
twice, separate processes), both import guards green, full suite green
(57/57), one video + telemetry (`projects/legacy/runs/
027_event_proximal_dopamine.mp4`), this four-field entry, scalars (one:
`trace_decay`'s reprovenance, value unchanged) counted separately from
scaffolding (`event_dopamine`, `three_factor.py`, `event_proximal_dopamine`
the mode flag, the stomp-detection addition to `FullPolicy`).

## Still open

- **The 009 climb/long-jump livelock is understood, not just patched
  around**: root cause was the injected mushroom contaminating
  `enemy_thetas()` (fixed in 010). `ReflexHabituation`/MDN are real,
  general mechanisms that work as designed and remain in place, but a
  genuine (non-contaminated) livelock to validate them against hasn't been
  found yet — 010's fixed re-run of the same scenario diverges too early
  to reach the original spot. Worth watching whether a real one turns up
  before spending more effort constructing a synthetic one.
- **Long-jump specificity, now confirmed on a real enemy, not just a
  contamination artifact**: 010 verified 1-2's persistent DLMn recruitment
  (22/28 long jumps at `gap_width=0`, post-fix) is driven by an actual
  near-stationary Green Koopa Troopa, not the mushroom. DLMn genuinely
  reads DNp01's general vigor, not `gap_width` specifically. Same open
  design question as before: gate on `gap_width>0` explicitly, or keep it
  as a real property of a shared escape relay.
- **The long jump doesn't clear wide gaps**: 1-3's 8-tile pit beat it
  outright (008). 007's `GAP_GAIN`/`DLMN_RECRUIT_THRESHOLD` calibration only
  covered gaps up to 4 tiles.
- **Mushroom body** (4,554 KC → 104 MBON, dopamine-gated) for learning.
  Reward must be x-progress, not score — score pays for farming the first
  Goomba forever.
- A harder benchmark. If every controller survives, the test measures nothing.
- The long-jump hold duration is a binary switch (25 vs 35 frames), not
  continuously scaled with DLMn's actual activation level — SPEC_terrain.md
  section 2 flagged this as the natural next step, not done this sprint.
- **Refusal has no escape route** (016): the refusal rule stops Mario from
  entering a too-wide gap, but the action space has no "just wait safely"
  option — cornered between a refused pit and an approaching Goomba, he
  died there anyway. Predicted in docs/MECHANISMS.md #6's own caveat before
  this was built; now confirmed. Needs an actual alternative path (the real
  fly doesn't have SMB's moving platforms either, per that same caveat) or
  a way to fight from a standstill, neither of which exists yet.
- **`inject_mushroom`-style RAM pokes are not collidable** (016, found
  while chasing 016's own "eats the mushroom" criterion): Active/ID/X/Y
  alone produces a visible, odour-active object that Mario's hitbox can
  pass straight through with zero effect, while an identical poke using a
  real enemy ID collides normally. Most likely missing: per-object state
  the real spawn routine caches (hitbox dimensions etc.) that a raw poke
  never populates. Undiscovered until now because 006/008/009 only ever
  needed an odour value from it. Worth root-causing if a future sprint
  needs a synthetic OBJECT (not just a synthetic RAM value) to be pickable.
- **The mushroom body cannot express a lateralized learned preference**
  (017): `mbon_agg` blends all 97 MBON bodies into one scalar before
  `mb_bias_l`/`mb_bias_r` split it back out by a FIXED anatomical ratio
  (0.00379 vs 0.00632) -- so whatever KC pattern was actually learned on
  each side individually never reaches the decision as a real left/right
  difference, only as a uniformly-R-biased pull of varying strength. A
  real fix needs an actual per-hemisphere KC->MBON readout, not a
  telemetry change -- bigger than an audit fix, queued here.
- **pC1's real output mostly isn't identifiable** (017): of 793,019 real
  outgoing synapses, 530,215 (66.8%) land on bodies with no `type`
  annotation in this connectome. The characterization here ("dominated by
  other pC1 subtypes and arousal-adjacent neuropil") is necessarily about
  the identified third only.
- **No synapse-level spatial data exists anywhere in this dataset** (018):
  confirmed across all three MaleCNS flat files, not assumed from the
  LC4/LPLC2 case alone. Forecloses any future "does this population order
  along a spatial axis" test (retinotopy, azimuth, receptive fields) --
  those need a different data export (e.g. per-ROI or per-synapse
  coordinates), not a cleverer query against this one.
- **LC4/LPLC2 have real, denser (than LC10a) hex-carrying input, not yet
  used** (019): LC4 16.47% of real input, LPLC2 5.84%, both one hop, both
  reaching 100% of bodies -- but with noisier receptive-field tiling than
  LC10a (58-62%/28-34% "indistinguishable" vs LC10a-L's 5%), consistent
  with these being wide-field detectors rather than narrowly tuned ones.
  Explicitly out of scope for 019; would need its own pre-commit
  thinness check (`lc10a_pursuit_circuit.py`'s own result argues for
  running that check before writing any wiring code, not after).
- ~~The mushroom body's DNa02 bias has the wrong sign (020)~~ **FIXED in
  021** -- `mb_bias_r/l`/`mb_bias_dnp02` now subtract rather than add.
  Re-tested with a live excitatory baseline (021): the corrected,
  inhibitory bias is real and measurably responsive to depression, but
  stays ~0.1% of baseline -- 014's original magnitude estimate was right,
  only its sign was wrong. The still-open lateralisation issue
  (`mbon_agg` blending L+R, 017) is untouched by this fix and remains
  open.
- **HOME_BIAS has a real, modest (~5x) direct-injection advantage over a
  fairly boundary-injected equivalent** (022): not the order-of-magnitude
  effect that would have invalidated 019-021, but real and measured --
  `HOME_BIAS=1.0` direct on DNa01/DNa02 settles DNa02_R to 0.998; the
  same magnitude applied fairly (boundary-injected on the real N>=60
  threshold partners instead) settles it to 0.197. Not fixed here (no
  building was in scope) -- worth considering whether HOME_BIAS should
  eventually enter the same way a real sensory population would, the
  next time the steering circuit's own wiring is touched.
- ~~Phase 6's eligibility trace needs at least two discriminable aversive
  stimuli to have anything to learn a difference between (phase-3 plan
  amendment)~~ **CORRECTED**, docs/REFACTOR_PLAN.md section 7: wrong, and
  stated too strongly. Phase 6's three-factor plasticity rule
  (SPEC_mushroom_body.md, sprint 014) already has a real two-class
  discriminable scenario with DIFFERING outcomes on 1-1 alone -- the
  mushroom (appetitive, real PAM->MBON reward) versus an enemy (aversive,
  real PPL/PPM->MBON punishment) -- no species decoding required.
  Per-species enemy discrimination (phase 4's Goomba/Koopa work,
  docs/ENTITIES.md) is a richer experiment built on top of that, not a
  prerequisite for phase 6 to have something to learn. The phase-4 work
  itself stands on its own (the tool's per-character smell panel needs
  real enemy identity regardless); only the phase-6-necessity claim was
  wrong.


## honest-001 — baseline of the honest-play project (`projects/honest/runs/001_baseline_1-1.mp4`)

**Setup.** New read-only project `honest` = test3's settings with every `config.rules` switch off (jump hold/cooldown, binary long jump, escape and climb habituation, MDN backup, climb stall/reflex, refusal, walk suppression, odour brake), no forced module (`graded_pit_response` off), MotorDirect with `release_on_landing` (decay 0.6, a_threshold 5.0), DNp01 and DNp02 refractory 8 steps, page + gap + wall perception on (wall: looming route gain 1.0, takeoff gain 0, 6 tiles), arousal 0, sigma 0, level 1-1, seed 0. Three new scalars (`WallAheadParams`), 80 in total; defaults of every existing config unchanged.
**What happened.** Died at frame 108, `max_x_abs` 311, enemy contact with the first Goomba (7 px ahead at death; no pit, no wall in range, wall stimulus 0 all run). Last 60 frames: theta rose 0.12 -> 2.56 and d_px fell 192 -> 7 while LC4_R peaked 0.69 and LPLC2_R 5.0; TTMn crossed threshold three times (frames 89, 92, 105, all DNp01; DNp02 never fired) with motor drive 3.68, 2.45 and 6.19 against `a_threshold` 5.0, so A was pressed for one frame only, at d=14 px. DLMn 1.07 max (no pit), DNp09 flat 0.71 (B held all 60 frames), steering flipped R->L for frames 92-97 (aversive odour) then back to R, MDN 0. Save state `001_baseline_1-1_pre_death` at frame 48.
**What we learned.** Without the counters the fly does commit early (65 px, frame 89, just after Mario's x wrapped past a 256 px page boundary, with page perception on) but MotorDirect's threshold discards that commit and the one that passes it is too late for a one-frame hop. The honest failure is at the motor mapping (decay/threshold against a single TTMn rise), not in perception; the next experiment belongs in a duplicate of `honest`. The wall module was not exercised by this death.


## learning-v2-001 — MBON readout strength sweep and power-up sign test (analysis sprint, no video)

**Setup.** `scripts/sweep_mbon_frac.py`: level 1-1, seed 0, sigma 0, 2000-frame cap, `win_attempt`'s config (page + gap perception, MotorDirect, MB spatial inputs) plus the per-MBON readout with all four `_frac` values set equal, learning frozen (rate 0) so only the readout differs; once with fresh KC->MBON weights and once with the trained `real_ep029.npy` checkpoint. Also the reward-vs-punishment sign test (`tests/test_powerup_reward.py`, real `mb_pam_reach`/`mb_punish_reach`, one shared sparse eligibility, one power-up pulse vs one death pulse). No new default behaviour, so no video: everything above is off unless switched on and the goldens are byte-identical. Two scalars added (`QBlockAheadParams`), 82 in total.
**What happened.** Sweep, frac -> (state first differs from frac 0, Mario x first differs, outcome): 0.005 -> frame 55, never, max_x 682 (unchanged, died at 610); 0.02 -> frame 160, never, unchanged; 0.05 -> frame 217, frame 217, max_x 679 (3 px less); 0.2 fresh -> frame 150, never, max_x 682 with one fewer escape jump; 0.2 trained -> frame 218, frame 218, max_x **1520**, survived 1056 frames (vs 610), 2 jumps vs 3. At 0.005-0.05 the fresh and trained runs were identical run for run (same divergence frames). Sign test: 40 of 97 MBONs are PAM-dominated, 57 PPL/PPM-dominated; a power-up pulse changes the PAM group's weights by -0.00784 against -0.00033 for a death pulse (23x more), and the PPL group's by -0.00045 against -0.00673 (15x less). Both depress (the rule cannot potentiate); reward minus punishment is <= 0 on every PAM-dominated MBON and >= 0 on every PPL-dominated one.
**What we learned.** With the shipped default (0.005) the readout moves the fly's internal state within a second but never its behaviour on this seed; position first diverges at about 0.05, and a trained brain only behaves differently from a fresh one at 0.2, the top of the new range (one seed, one checkpoint, so read it as "order 0.05-0.2, not 0.005", not as a threshold). Learning can therefore only change behaviour through this route if the readout is raised roughly 10-40x; the range change (0-0.2) is what makes that testable. Reward and punishment separate by *which MBONs* they depress, not by sign, as the spec says: valence lives in the anatomy, and the sign test now pins that for the power-up event too.


## learning-v3-001 — recovery sign test, TTMn plateau diagnosis, posture neurons (analysis sprint, no video)

**Setup.** Analysis of `projects/learn_1` telemetry (209 runs) and isolated-network probes; the sign test on the real 97 x 4064 KC->MBON matrix with recovery on; one connectome pass (`edges_dn_vis_learning_v3.parquet`: all 1332 descending neurons + LC4/LPLC2/LPLC1/LC6/LC9/LC10a/LC11/LC16/LC17) for the Down/Up neuron choice. Everything new is off by default (goldens byte-identical), so no video: nothing watchable changes unless a switch is turned on. 95 scalars.
**What happened.** Sign test (5 earlier reward pulses depress KC group A; then one pulse with KC group B active; recovery_rate 0.001): reward, depression only: 2323 synapses down, 0 up; with recovery: 2323 down (the active KCs) **and 2538 up** (depressed, silent KCs recovering toward baseline), never above the untrained weight; punishment likewise (2727 down / 2547 up); the PAM-dominated MBONs (40) take -0.0065 under reward vs -0.0003 under punishment, the PPL-dominated ones (57) the reverse (-0.0005 vs -0.0070). TTMn plateau: not a constant 17 but a 3-frame cycle 4.1/8.3/17.0, with looming quiet and the enemy *behind* Mario (d_px -41..-155); the jump network stays at TTMn 3-12 with zero input after one looming pulse at g 2.6, and at g 2.0 any tonic lplc2 >= 0.4 holds it at 5-17; A is held because `learn_1`'s MotorDirect has `dlmn_gain` 1.0 and DLMn sits at 1.5-2.9 (drive 5-14 vs `a_threshold` 4): A held 338 of 450 frames (288 with looming quiet). `adapt_frames` 30 cuts that to 60/450 (seed 0) and 77/450 (seed 1); `ignore_behind` alone does not (289/225). Descending neurons: Down = DNp03/DNp06/DNp11 (LPLC1-dominant), Up = DNg40/DNp05 (LPLC2/LC4-dominant); posture circuit 10 core neurons + 142 inputs (85 LC4, 53 LPLC1, 4 LPLC2 with >= 60 synapses), spectral radius 0.9993 at g=1.
**What we learned.** (1) With recovery the rule is no longer one-directional: dopamine now moves weights up for KCs that were silent and down for KCs that were active, and reward vs punishment still separate by which MBONs. (2) The plateau is a latched jump circuit whose tonic DLMn/TTMn output is integrated by MotorDirect into a permanently held A; the muscle-level adaptation removes the held A but not the latch (only lowering `jump.g` does), and the fly gets less far without the accidental permanent hop (max_x 708 -> 323, seed 0) -- an honest cost of the fix, not a regression. (3) The annotations carry no behavioural labels, so the Down/Up roles are a hypothesis (looming-driven DN pathways other than the escape ones); thresholds are set so nothing presses them until driven, and the neurons' real behaviour is not verified.

## 211 — E1 jump the Goomba, real vs shuffled connectome, seed 9200 (`projects/redesign_e1/runs/211a_e1_real_seed9200.mp4`, `projects/redesign_e1/runs/211b_e1_shuffled_seed9200.mp4`)

**Setup.** Redesign phase 2 brain path (`brain.e1`, recorded through `tool/core/brain_runner.run_brain_one`). Scene `e1_goomba_approach` (hash 15d214a2d20eb35d): 60 frames right+B, 50 frames idle, then the fly (`BrainPolicy`, network 4736dc554136ac98, calibration cddee55ba0a629ee) is in control with the first Goomba 90 px ahead. 211a real connectome, 211b degree-preserving shuffle (shuffle seed 1), same noise seed 9200. Nothing tuned; this is a demonstration run, not part of the 20-seed eval (seeds 3000-3019, see docs/RESULTS_redesign_phase2.md).
**What happened.** Real: GF fired at frame 113, theta 43.6 deg at 20 px, before contact (frame 130); A held 12 frames; Goomba stomped, survived the 60 frame grace. Shuffled: GF never fired, no A press, contact at frame 299, Mario died (308 frames).
**What we learned.** On this seed the single-seed picture matches the aggregate eval: the real wiring produces the jump, the rewired copy does not. One seed shows nothing statistical.

## 212 — E1 GF-lesion control arm, seeds 3000-3019 (no video: control arm, no watchable run beyond 211)

**Setup.** Same E1 scene and calibration as 211 (scene 15d214a2d20eb35d, network 4736dc554136ac98, calibration cddee55ba0a629ee). Real connectome with both Giant Fiber cells silenced (`lesion_gf`), seeds 3000-3019, same noise seeds as the real arm (policy.reset(seed)). Command: `.venv/Scripts/python.exe -m brain.e1 --arms lesion_gf --n 20 --seed0 3000 --workers 8 --out audit/p2_e1_lesion.json`. Run once; real (18/20) and shuffled (0/20) taken from audit/p2_e1_eval.json, not re-run. No parameters changed.
**What happened.** Survived 0/20 (Wilson 95% CI 0-16%), deaths 20, timeouts 0. GF crossed threshold before contact 20/20 (first GF frame 108-113, theta median 40.0 deg, 22 px). GF output max 0.00 Hz, TTMn max 0.011 Hz, A pressed in 0 runs. All runs: contact frame 120, death frame 130. Seeds 3018/3019 behaved like the rest (GF at 110, no A, died).
**What we learned.** Cutting the GF output while it still detects the threat removes survival (18/20 to 0/20) and no jump is issued, so the survival in the real arm comes through the GF output, not threshold crossing alone. Shuffled and lesion both give 0/20 by different routes (GF never fires vs fires with no output). Real-arm Hz fields were not stored in the earlier json, so no Hz comparison with real. No video: control arm.

## 213 — E1 records: shuffled contact spread and the 3018/3019 limitation (no video: records only, no new run)

**Setup.** No model, calibration, encoding or scene change and no new eval; this entry corrects and completes the record of the
3000-3019 E1 eval (entries 211, 212 are untouched).
**What happened.** The shuffled arm's contact frames spread 116-299 (real 120-138) because shuffled Mario retreats Left under
noise-driven steering, not because he stands still; the arm never jumps and still dies (docs/NOTE_e1_shuffled_contact_spread.md).
Real seeds 3018 and 3019 died: the GF fired at frame 110 but A was held only 3-4 frames (survivors 12-26), a short hop, contact at
126/124, death at 130. Recorded as a known limitation; no threshold tuning, no code change.
**What we learned.** The earlier wording "shuffled survival is 0 by passive death" was wrong: shuffled is not stationary. The
real-arm deaths are a property of the circuit plus the fixed motor map and are reported as such. The TTMn-about-3%-of-real figure
is a 2-seed smoke check only (9100-9101); GF-output and TTMn peaks were not stored for the real and shuffled arms of 3000-3019.

## 214 — E0 walk to the goal, real vs shuffled, seed 9200 (`projects/redesign_e1/runs/214a_e0_real_seed9200.mp4`, `214b_e0_shuffled_seed9200.mp4`)

**Setup.** Phase 3 (docs/SPEC_phase3.md), network 3848f3e70b2051ef (adds LC10a), calibration 9cf9317984a0b28c. Scene e0_walk_goal, landmark on (GOAL_CUE_SALIENCE 15), looming on, no enemies. 214a real, 214b degree shuffle (seed 1), noise seed 9200. Eval seeds 4000-4019, once: docs/RESULTS_redesign_phase3.md.
**What happened.** Real reached x 400 at frame 135 (Right and B held, no Left, GF never crossed). Shuffled held Left 600/600 frames, never advanced, timed out, GF crossed. Eval: real 20/20, shuffled 0/20, class-shuffled 0/20 (Left 99%). Real arrives at frame 135 in all 20 seeds.
**What we learned.** The landmark moves "go right" into the senses and the real wiring turns it into walking; random wiring turns the same cue into Left. Passes the plan criterion, but the landmark is an assumption supplied as an input and the real arm is noise-insensitive.

## 215 — E3 pursue the mushroom, real vs shuffled, seed 9200 (`projects/redesign_e1/runs/215a_e3_real_seed9200.mp4`, `215b_e3_shuffled_seed9200.mp4`)

**Setup.** As 214, scene e3_mushroom, landmark off, pursuit on (powerup kind), bound 150 frames. 215a real, 215b degree shuffle (seed 1), seed 9200. Eval seeds 5000-5019, once. Same entry also records the E1 regression on the new network (seeds 3000-3019, previously used): real 13/20 (was 18/20), shuffled 0/20, lesion 0/20.
**What happened.** Real reached the mushroom at frame 105 (Right 43 frames, no Left). Shuffled timed out (Left 112 of 150, GF crossed). Eval: real 20/20 (frames 102-105), shuffled 0/20, class-shuffled 0/20; E1 regression fails the Phase 2 criterion (>= 16) with the same GF angles but shorter A holds (deaths held A 4-9 frames).
**What we learned.** E3 passes, but there is no pursuit-off arm, so it does not prove pursuit is necessary. Adding LC10a changed E1 real survival from 18 to 13/20; reported, not tuned.

## 216 — Phase 3 round 2 on fresh seeds: E1 new-network baseline, E3 with real_no_pursuit, E0 real_no_landmark (`projects/redesign_e1/runs/216a_e3_real_seed9200.mp4`, `216b_e3_real_no_pursuit_seed9200.mp4`)

**Setup.** Network 3848f3e70b2051ef, calibration 9cf9317984a0b28c, PURSUIT_AROUSAL 0.65 (docs/SPEC_phase3.md section 11). Each eval run once, no parameter change: E1 seeds 3100-3119 (arms real, shuffled, shuffled_class, lesion_gf), E3 seeds 5100-5119 (real, shuffled, shuffled_class, real_no_pursuit), E0 seeds 4000-4019 arm real_no_landmark only (the other E0 arms are unaffected by the arousal change and ran earlier). 216a real, 216b real with pursuit_kinds=[] (the real_no_pursuit setting), seed 9200. Raw: audit/p3r2_e1.json, p3r2_e3.json, p3r2_e0_nolandmark.json.
**What happened.** E1 real survived 12/20 (CI 39-78%), below the plan criterion of 16; shuffled 0/20, shuffled_class 13/20, lesion_gf 0/20. E3 real reached 20/20 (median frame 105.5), shuffled 0/20, shuffled_class 3/20, real_no_pursuit 0/20 (all timeouts, no key pressed). E0 real_no_landmark 0/20 (timeouts, no key pressed). Video seed 9200: real reached at frame 106, no-pursuit timed out at 150.
**What we learned.** E3 passes and pursuit is necessary in it; E0's landmark is necessary. E1 does NOT reach 16/20 on fresh seeds (12/20), so the earlier 13/20 on seeds 3000-3019 was not a seed artefact; and the class-preserving shuffle survives 13/20 in E1, so E1 survival does not separate the real wiring from a class-preserving rewiring. Reported, not tuned.

## 217 — Correction and caveats to entries 214-216 (no video: documentation only; 216b is the no-pursuit control, there is no shuffled video for 216 and no E1 video for the 12/20 result)

**Setup.** No code, scalar or eval change; this corrects how 214-216 read (entry 216 text is untouched).
**What happened.** (1) The E3 class-shuffle control FAILED: 3/20 reached against the criterion <= 2 (95% CI 5-36%), so class-preserving wiring also reaches the mushroom sometimes. (2) E1 on fresh seeds: real 12/20 FAILS the Phase 2 criterion >= 16; shuffled_class 13/20, so E1 survival does not separate the real wiring from class-preserving rewiring (12 vs 13/20, overlapping CIs). (3) 214/215 used the old DNp09-arousal rule and are SUPERSEDED for E3 (class-shuffle 0/20 there, 3/20 now); that the E0 real/shuffled arms are unaffected by the arousal change is plausible, not rerun. (4) E0 is one deterministic trajectory (frame 135 on every seed) so the E0 necessity result (real_no_landmark 0/20) is one trajectory, not 20 independent trials; E3 real is near-deterministic (median 105.5, frames 102-106).
**What we learned.** The E3 pass shows the real wiring turns a pursuit cue into walking and that pursuit is needed there, but it does not show the real connectome is uniquely responsible, since a class-preserving rewiring gets 3/20. The E1 cause (shorter A holds) is correlational, brain-only evidence, not a paired closed-loop test; 12/20 on fresh seeds matching 13/20 on replayed seeds supports "not seed luck". The rule-before-run ordering of the arousal value is unverifiable from artefacts (mtimes: calibration.py 13:50:31, senses_arousal_output.txt 13:50:41, SPEC 13:55:17); 0.65 does equal the midpoint of the stated 0.3-1.0 window.

## 218 — E1 on fresh seeds 3200-3219 after the many-seed recalibration (`projects/redesign_e1/runs/218a_e1_real_seed9200.mp4`)

**Setup.** Network 3848f3e70b2051ef, calibration 343d8f60abcdba25 (30-noise-seed derivation, docs/SPEC_phase3.md section 12). No code, config or parameter edits; one eval, no retries: `python -m brain.e1 --n 20 --seed0 3200 --workers 8 --arms real shuffled shuffled_class lesion_gf --out audit/p3r3_e1.json`. Arms: real, degree shuffle (pass/fail null), class shuffle (informative), GF lesion (should fail). Video is real-arm seed 9200 (stomped, GF at frame 111, contact 133, A held 16 frames), one seed, not the result.
**What happened.** real 16/20 (Wilson 58-92%), 4 deaths, GF before contact 20/20, theta at GF median 41.7 (38.4-43.6), GF out max 12 Hz, TTMn max 0.349. Degree shuffle 0/20 (0-16%), GF never fired. Class shuffle 16/20 (58-92%), theta at GF 33.0 (27.3-34.2), GF 18 Hz, TTMn 0.517. Lesion 0/20, TTMn 0.012. Criteria: real >= 16 passes (exactly at the boundary, lower CI 58%); degree shuffle <= 2 passes. All 4 real deaths (seeds 3202, 3203, 3207, 3217) had a first A run of 1 frame (total A frames 1-4); 4 of the 16 survivors also had a 1-frame first run, 9/20 had a first run <= 2 frames. Earlier single-seed calibration on 3100-3119 gave real 12/20, class 13/20. tests/test_e1.py::test_lesion_arm_silences_gf_and_ttmn_but_the_gf_still_crosses_threshold still fails: lesion TTMn 0.00836 vs real 0.0720 at seed 9100 (ratio 0.116, test requires < 0.1).
**What we learned.** The criterion is met at its edge on seeds not used in the calibration, with the degree-shuffle null clean; the margin is one episode (15/20 would fail), so it is a boundary pass, not a comfortable one. Deaths are tied to 1-frame A taps, which is correlation in closed loop outcomes, not a paired test. The class shuffle equals the real arm (16 vs 16), so E1 survival shows type-level, not neuron-level, wiring matters. The lesion unit test is a threshold of 10% on a residual TTMn signal; it is unchanged and failing, nothing was adjusted.

## 219 — Caveats to entry 218: the A-tap failure mode is not fixed (no video: documentation only)

**Setup.** No code or eval change; reviewer round 3 corrections to how 218 reads.
**What happened.** Brain-only tap fraction fell 0.42 -> 0.30 after the many-seed recalibration, but on 3200-3219 all 4 deaths were 1-frame first A runs and 5 survivors were taps too (9/20). 16/20 is a boundary pass (lower CI 58%, 15/20 would fail, real equals class-shuffled 16 vs 16). The lesion-arm test at seed 9100 fails (ratio 0.116 vs bound 0.1), left unedited awaiting Arun; E0/E3 were not re-run under calibration 343d8f60abcdba25.
**What we learned.** The short-hop mode remains; the tap-death link is not a paired test, and the 0.30 is not independent validation (same analysis that motivated the change, non-monotone in the threshold). Entry 218 is not edited.

## 220 — E0 and E3 re-run under the current calibration, fresh seeds (no video: behaviour matches 214/215/216; metrics are in audit/p4_e0.json, audit/p4_e3.json)

**Setup.** One run each, no retries, no edits. Network 3848f3e70b2051ef, calibration 343d8f60abcdba25 (E0/E3 had last been run under 9cf9317984a0b28c). E0 seeds 4100-4119 (600 frames), E3 seeds 5200-5219 (150 frames), arms real, shuffled (degree), shuffled_class, and the necessity arm (real_no_landmark / real_no_pursuit).
**What happened.** E0: real 20/20 (CI 84-100%), shuffled 0/20, class-shuffled 0/20, no_landmark 0/20. E3: real 20/20, shuffled 0/20, class-shuffled 3/20 (CI 5-36%), no_pursuit 0/20. Real median frames 135 (E0) and 105 (E3), identical to the earlier runs; real never touches the GF, A or Left. Degree shuffles fire the GF (E0 20/20, E3 15/20) and walk left.
**What we learned.** The earlier E0/E3 claims hold under the current calibration, and RUNS 214-217 / RESULTS rounds 1-2 are superseded by these as the current-calibration results. E0 real remains one deterministic trajectory, so 20/20 is weaker evidence than its CI suggests. E1 on 3200-3219 stays a boundary pass, not robust (16/20, CI 58-92%, 15/20 would fail, 9/20 A taps, class-shuffled equal). No video: real E0/E3 behaviour (frames, keys) is unchanged from 214/215/216.

## 221 — 1-1 innate baseline, real vs degree shuffle vs class shuffle (`projects/redesign_e1/runs/221a_b11_real_seed9200.mp4`, `221b_b11_shuffled_seed9200.mp4`, `221c_b11_shuffled_class_seed9200.mp4`)

**Setup.** docs/SPEC_baseline_1-1.md: real SMB 1-1 from power-on, no scripted actions, no RAM edits, looming + pursuit + home landmark on, network 3848f3e70b2051ef, calibration 343d8f60abcdba25, seeds 6000-6019, shuffle seed 1+i. One run, no retries, a baseline with no pass/fail and no tuning afterwards. Videos: seed 9200, one per arm.
**What happened.** Real: max_x mean 357 (bootstrap CI 333-380), median 315; 13 died to the first Goomba (frame 106), 7 survived it and stalled at the first pipe (x=434, stuck); 0/20 level complete, 0/20 mushroom, first A runs never taps (0/20). Both shuffled arms: max_x 40 in all 20 (walk left into the edge, stuck). The SPEC "Goombas jumped" metric reports 0/20 but under-counts (a 14 px ground overlap before take-off counts as a hit); the 7 survivors did jump it (docs/RESULTS_baseline_1-1.md spot-check).
**What we learned.** Innately the fly walks right and jumps at the first Goomba, in time about 35% of the time, and then gets no further: it does not jump the pipe, does not use blocks or reach the mushroom or the flag. Real wiring beats both shuffles on distance, but the baseline is two near-identical trajectories, so noise seeds add little. The "jumped" metric has a known false-negative.

## 222 — Goombas-jumped metric correction, replay re-score and Goomba-death diagnostic of the 1-1 baseline (no video: documentation and read-only replay; no code or calibration change in this entry)

**Setup.** Follows 221. The "jumped" tracker was corrected in commit 2794964 (a ground overlap before Mario's first airborne frame in the window is not a hit); the bug was found in a spot check and fixed before any re-score. This entry: a read-only replay (audit/p7_rescore.py, scratch, gitignored) of the already-run real-arm episodes, seeds 6000-6019, same network 3848f3e70b2051ef and calibration 343d8f60abcdba25, corrected tracker. It is a replay, not a new eval. Also records the earlier replay diagnostic (audit/p6_*.py): baseline real arm vs the E1 real arm replayed on seeds 3200-3219.
**What happened.** Real arm: 7 jumped / 20 encountered (the 7 stuck episodes; the 13 died_enemy episodes 0); every episode reproduced its stored outcome, frames and max_x. The stored 0 in 221 is the pre-correction value. Shuffled arms encounter no Goomba (never reach it), so nothing to score and no comparison on jumping. In time = 7/20 = 35% (RESULTS said "about half"; 221 text unedited, correction appended to RESULTS). Diagnostic: E1 replay 16 stomped / 4 died; baseline deaths vs survivors differ by one frame of A timing (survivors A on frame 103, deaths 104; take-off dx 14 vs 11); closing speed is about 3.5 px/frame in the baseline vs about 0.5 in E1 (about 7x), theta rises 8-13 deg/frame vs about 2, so the GF threshold is crossed 22 px away with about 2 frames to act.
**What we learned.** The corrected metric agrees with the spot check (7 survivors jumped it). Limits: the baseline is two trajectories across 20 seeds, so n=20 is effectively 2; the link from the one-frame A difference to GF-to-A muscle delay is post-hoc, untested, Fisher p=0.06 (a trend); the rise-time threshold (take-off at dx >= about 14) is inferred from the two observed trajectories; the 4 E1 deaths are a different mode (1-frame A taps). Nothing was tuned from these numbers.

## 223 — E2a: obstacle expansion at pipe 1, real vs degree shuffle vs class shuffle vs no obstacle cue (`projects/redesign_e1/runs/223a_e2a_real_seed9200.mp4`, `223b_e2a_real_no_obstacle_seed9200.mp4`)

**Setup.** docs/SPEC_e2a.md: scene e2a_pipe1 (first Goomba removed, home landmark on, no pursuit), obstacles seen as looming at LC4/LPLC2 only, no new scalars. Network 3848f3e70b2051ef, calibration 343d8f60abcdba25, seeds 7100-7119, shuffle seed 1+i, 600 frames. One run, no retries, criteria stated beforehand (real >= 14/20, degree shuffle <= 2/20, no-cue <= 2/20). Videos seed 9200 (223b built by calling the episode directly, the launcher cannot select the no-cue arm). Raw: audit/p7_e2a.json.
**What happened.** Real cleared 18/20 (Wilson CI 70-97%); the 2 failures were 1-frame A taps at x 434 (stuck at 436). GF first spike at x 413-422, d about 30 px, theta about 42 deg; first A median frame 52, x 431; 12/20 first A runs are 1-frame taps (10 of those cleared), the rest 9-13 frames. Degree shuffle 0/20 and class shuffle 0/20 (all timeout at the scene start x 321, never walked); no-cue arm 0/20 (stuck at x 436, GF never fired, no A). Criteria: all three met. Root tests: 288 passed, 0 failed.
**What we learned.** The cue is necessary (0/20 without it) and the real wiring carries it (shuffles 0/20), and real clears above the bar. Limits: the shuffled arms do not walk at all, so they do not test the pipe specifically (the degree shuffle's GF fires on frame 1 at theta 13.5 deg); real is not one trajectory but outcome depends on tap timing within a 5-29 px window, so the 2 failures are a timing-margin effect; this is a Mario's-eye-view assumption, not a fly behaviour, and only pipe 1 was tested.

## 224 — 1-1 innate baseline re-run WITH obstacle expansion (`projects/redesign_e1/runs/224a_b11_real_seed9200.mp4`)

**Setup.** B11 as 221 but `expanding_obstacle` on (docs/SPEC_baseline_1-1.md, "Obstacle expansion on"); fresh seeds 6100-6119, same network and calibration, one run, no retries, no pass/fail. Raw: audit/p7_b11.json. Entry 221 (without obstacle expansion: max_x 357, 13 died at the first Goomba, 7 stalled at pipe 1 x=434) is unchanged.
**What happened.** Real: max_x mean 417 (bootstrap CI 356-499), median 315, max 724; 15 died to the first Goomba (all frame 106, x 315), 5 stalled at x 722-724 (pipe 1 cleared 5/20); Goombas jumped 10/25 encountered (5 episodes); 0 A taps in first runs; no mushroom, 0 complete. Shuffles (both): max_x 40 in all 20, stuck.
**What we learned.** Obstacle expansion removes the pipe-1 stall for every Goomba survivor (0 -> 5 of 5), but they all stall again at x 722-724 (cause not diagnosed here) and the Goomba still kills 15/20 (13/20 before; different seeds, not evidence of change). The baseline remains effectively two trajectories, so n=20 is weak evidence; nothing reaches the mushroom or the flag.

## 225 � Walking-speed dose-response on GOAL_CUE_SALIENCE 5/8/11/15 (no video: no qualitatively different behaviour at any value; table in docs/RESULTS_dose_response.md, raw audit/p10_dose.json)

**Setup.** docs/SPEC_dose_response.md: B11 with obstacle expansion, only the right-LC10a landmark salience varies (5, 8, 11, 15), same fresh seeds 6200-6219 per value, real and degree shuffle, one run, 4 workers, no retries. This is a dose-response; no value adopted, registry default stays 15.
**What happened.** Walking speed to frame 100 is flat (2.545 / 2.570 / 2.570 / 2.570 px/frame); first-Goomba contact is frame 103-104 at x 306 for every value. Survivors of the first Goomba (real) 1, 10, 9, 8 of 20; max_x mean 333, 528, 505, 466 (medians 312, 518, 315, 315); pipe 1 cleared 1, 10, 9, 7. Value 5 is the only one with A taps (9/20). Shuffled: 80/80 stuck at x 40, never walked right, never met a Goomba.
**What we learned.** Within 8-15 speed and survival at the first Goomba do not move systematically (10, 9, 8, not distinguishable at n=20); the one large change is between 5 and 8 (1 to 10 survivors) with speed unchanged to about 1%. Speed therefore does not explain survival here; what differs is not diagnosed. Survivors still stall at x about 722.

## 226 — Phase 5c step 2 validation: pursuit azimuth -> 0 (no video: no qualitatively different behaviour; docs/RESULTS_5c_step2.md, raw audit/p14_e3.json, audit/p14_b11.json)

**Setup.** docs/SPEC_geometry_5c.md step 2: pursuit target azimuth fixed at 0, so both LC10a sides get equal drive. Fresh seeds, one run each, 3 workers: E3 5300-5319 (real, degree shuffle, class shuffle, no_pursuit); B11 6300-6319 (real, degree shuffle, class shuffle). Affected tests (phase3, e1, baseline, scalars_doc) 50/50 pass under .venv.
**What happened.** E3: real 20/20 (84-100%), degree shuffle 0/20, class shuffle 2/20, no_pursuit 0/20; median 116 frames, GF never crossed, mean Left frames 0 (shuffles 110 / 76). B11 real: max_x mean 374 (CI 315-451), median 315; 18 died at an enemy (16 at x 315), 2 stalled at x~724; Goombas jumped 5/23; no A taps; shuffles stuck at x 40. Replay seed 9200: azimuth 0.0 in all 85 calls, LC10a left == right at every call; no_pursuit never moves.
**What we learned.** The wrong-sign tilt removal changed nothing in E3 and B11 is within seed noise of the earlier baseline but nominally lower (mean 374 vs 417 / 466; 3 survivors of the first Goomba vs 5-8). So step 2 did not make Mario better. Rightward walking in E3 is not carried by any visual asymmetry now; whether it comes from the symmetric pursuit drive through the real wiring and motor map (shuffles walk Left instead) was not isolated.

## 227 — Phase 5c step 3 validation: obstacle face as an extended object (no video: pipe 3 still stalls; docs/RESULTS_5c_step3.md, raw audit/p15_e2a.json, audit/p15_b11.json)

**Setup.** docs/SPEC_geometry_5c.md section 5: obstacle elevation taken at the nearest point of the face (not the run centre), Mario body 12/24 px. Fresh seeds, one run each, 3 workers: E2a 7200-7219 (4 arms), B11 6400-6419 (real, degree and class shuffle), plus a read-only replay of seeds 6103/6105/6106/6108/6115 (already-used seeds from 6100-6119). No code or config change; tests/test_e2a.py 22 passed.
**What happened.** E2a: real 20/20 (84-100%), degree shuffle 0/20, class 0/20, no obstacle 0/20; GF at d 38-44 px (theta 40-46 deg), first A 15-24 px and take-off 12-21 px before the pipe-1 stall point (inside the 5-29 window); 5/20 taps. The degree shuffle's GF fires at frame 0 and it never walks. B11 real: mean max_x 385 (CI 343-441), median 315; 15 died at the first Goomba (x 315), 5 stalled at x 596 (the base of pipe 2); pipe 1/2/3 cleared 5/0/0. Replay: 6103 and 6105 still stall at pipe 3 (x 722), 6106/6108/6115 now stall at pipe 2 (x 596).
**What we learned.** The step is neutral-to-better for the pipe-1 scene and worse at the margin for the whole level: survivors that previously passed pipe 2 (5/5) now stall there (5/5 in the new seeds, 3/5 in the replay), and pipe 3 is not fixed (2/5 still stall at 722). The cause is not diagnosed. Telemetry rows hold the Goomba-slot d/theta, so the face GF/A numbers at pipes 2-3 were not readable from them. Reported only.

## 228 — Phase 5c step 4 validation: surface-to-surface distance (`projects/redesign_e1/runs/228a_b11_real_seed9200.mp4`)

**Setup.** Step 4 of docs/SPEC_geometry_5c.md: enemy and obstacle distance measured from Mario's front edge to the nearest hitbox face (centre - 10/11 for enemies, face - 13/14 for obstacles), enemy w = 10. Fresh seeds, each run once, nothing tuned: E1 3300-3319, E2a 7300-7319, B11 6500-6519, dose-response 6600-6619. Video is B11 real seed 9200. Detail in docs/RESULTS_5c_step4.md.
**What happened.** E1 real 10/20 (criterion >= 16, previous 16/20), degree 0/20, class 15/20, lesion 0/20; every death was a short A press (2-6 frames), every survivor a long hold. E2a real 20/20 (same), shuffles 0/20, no-obstacle 0/20; GF fires 39-45 px before the stall point, take-off 24-36 px. B11 real mean max_x 698 (was 385): no deaths at the first Goomba, 8 stalled at pipe 2 (596), 9 at pipe 3 (722), 3 died (723, 844, 1128). Dose-response survival 5/19/20/20 of 20 at salience 5/8/11/15, speed 2.55-2.57 (flat). Root tests 295/295, tool brain test 17/17.
**What we learned.** The change helps the long B11 run (first Goomba survived, pipe 2 cleared 12/20) and leaves E2a unchanged, but E1 real fails its own criterion (10/20): the GF now fires about 19 frames before contact yet the press is a short tap in half the episodes and half of those die. Cause not diagnosed here. One seed video is an observation, not a result.
