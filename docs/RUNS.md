# Run log

One entry per run, newest at the bottom. Four fields, always the same four.
Append after every behaviour-changing sprint — never edit an old entry to make
it look better, including the ones that failed. The failures are why the later
runs work.

Videos and per-run notes live in `runs/`.

---

## 001 — first jump (`runs/mario_jump.mp4`)

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

## 002 — the brain overlay (`runs/mario_with_brain.mp4`)

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

## 004 — three controllers, g = 1.5 (`runs/004a,b,c`)

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

## 005 — the 2×2 and the rerun at g = 2.0 (`runs/005a,b,c`)

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

## 006 — steering (`runs/006_steering.mp4`)

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

## 007 — terrain: pits, graded takeoff, and speed (`runs/007_terrain.mp4`)

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

## 008 — odour that can win, and does the long jump generalise (`runs/008a,b,c`)

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

## 009 — the used-block bug and ORN adaptation (`runs/009_orn_adapt.mp4`)

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

## 010 — habituation, MDN, and the bug that was driving the whole investigation (`runs/010_enemy_thetas_fix.mp4`)

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
`runs/008a_1-1.mp4` before being caught and killed. The original bytes are
gone; there was no backup. `runs/008b_1-2.mp4` and `runs/008c_1-3.mp4` are
untouched. The accidentally-created content was moved to
`runs/_recovered_postfix_1-1_accidental_overwrite.mp4` rather than
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

## 011 — the first uncontaminated baseline (`runs/011a,b,c`)

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

## 012 — the second escape pathway, and a null result that survived widening (`runs/012a,b,c`)

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

## 014 — the mushroom body: it learns, and it doesn't matter, and both are real (`runs/014a,b`)

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

## 016 — make it a smell problem (`runs/016_smell.mp4`)

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
