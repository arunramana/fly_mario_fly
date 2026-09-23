# SPEC: fly_mario step 4 — odour that can actually win, and does the long jump hold up

Finishes the two items deferred from `SPEC_terrain.md` (`?`-block odour,
hunger gating), fixes the scaling bug that made 006's mushroom odour a dead
letter, and stress-tests 007's pit-clearing result across all three levels.
Read `docs/RUNS.md` first, including the "Still open" list this sprint
closes two more bullets of.

---

## 0. Fix the units mismatch first — this gates everything else

**Run 006's finding wasn't "odour is too weak," it was "odour and
`HOME_BIAS` were never in the same units."** A mushroom at 40px gives
`concentration = 1/40 = 0.025`; `HOME_BIAS = 1.0`. That's a 40x gap by
construction, not a subtlety a smarter WTA would route around. **Do not
lower `HOME_BIAS`** — that just makes Mario permanently distractible, a
worse failure mode than the one being fixed.

Introduce `ODOUR_GAIN`: scale `concentration` up so that a *close* encounter
(pick a concrete reference — one tile, 16px, is a defensible "Mario is
standing right next to it" distance) lands in the same order of magnitude as
`HOME_BIAS`. Concretely: `effective = ODOUR_GAIN * concentration`, with
`ODOUR_GAIN` chosen so `effective(d=16px) ≈ HOME_BIAS` — i.e. `ODOUR_GAIN ≈
16`. This is a new hand-set scalar; log it plainly like every other one.

**Home stays direction-only; DNp09 already supplies drive.** `HOME_BIAS`'s
job is exactly what it was: a constant sign telling the WTA which way is
"home" when nothing else is competing. It does not need to, and must not,
also encode "how hard to go" — that's `DNp09`/`speed_circuit.py`'s job
already, wired in 007 and entirely independent of the steering WTA. Fixing
the odour/home-bias magnitude mismatch is a scaling fix to two competing
*direction* signals; it does not require any new wiring between the
steering and speed circuits, and none should be added. (This is the same
division real central-complex circuits use — heading/goal direction and
locomotor drive are separate pathways — stated here as the reason *not* to
touch `speed_circuit.py` in this sprint, not as new work to do.)

## 1. `?`-block odour

Source at every `?` block `tile_ram.question_blocks_near` finds (both
`0xC0` coin and `0xC1` power-up variants — SPEC doesn't need to
distinguish them, same as the mushroom not distinguishing power-up
subtype). `question_blocks_near` returns **tile-column offsets**, signed,
relative to Mario — convert to the same pixel-distance units the mushroom
odour uses (`offset_tiles * 16`) before applying the shared `concentration
= 1/max(|d|,1)` formula and the new `ODOUR_GAIN`, so both odour sources are
on identical footing and share one gain constant.

**State the two-stage limitation up front, not as a caveat discovered
later**: odour is horizontal-only (left/right routing into DNa01/DNa02,
same as the mushroom) — it can pull Mario to *stand under* a block. Hitting
it from below is the existing contact-based climb reflex's job (an upward
A-press against a solid-overhead condition), a separate mechanism this
sprint doesn't need to change. Report in the writeup which stage was
actually observed, don't conflate them.

## 2. Hunger gates odour

`RAM 0x0756` (already read in `run_steering.py` as `ADDR_MARIO_SIZE` for
the climb-hop gating): `0` = small = hungry, `≥1` = big/fiery = sated.
Multiply **both** odour sources' `effective` contribution by a hunger
factor — full (or boosted) gain when small, reduced when big/fiery. New
scalar(s): however many you need to express that (a single multiplier
applied when hungry is enough; don't over-parameterize).

**Report a real outcome, not a hoped-for one.** Re-run 006's synthetic
mushroom-behind-Mario scenario with Mario forced small, and state plainly
in the writeup whether the WTA decision actually flips at least once
frame. If it still never does even after the section-0 rescale and hunger
boost, say exactly that — raising gains further until it works by
construction is not a finding, it's curve-fitting the demo.

## 3. Does the long jump generalise?

007 cleared one real 2-tile pit, once. Run all three levels — **1-1, 1-2,
and 1-3** — and for every pit actually encountered, report: gap width
(tiles), DNp01's spike rate during the approach, whether DLMn crossed
`DLMN_RECRUIT_THRESHOLD`, hop vs. long jump, and cleared vs. died. Detect
pit encounters from telemetry (`tile_ram.gap_width(ram) > 0` stretches),
not by eyeballing video.

**1-3 is the correct test now, not an invalid one.** SPEC's own run log
(004) excluded it because every controller — real, shuffled, and the
one-line baseline — died there identically, because all three were blind
to pits. That was true then. Report what actually happens now.

## 4. Deliverable

`runs/008a_1-1.mp4`, `runs/008b_1-2.mp4`, `runs/008c_1-3.mp4` — brain
panel, plus odour and hunger as their own traces (same additive
column-presence-gated pattern already established for every population
added since `SPEC_steering.md`). Append one four-field entry to
`docs/RUNS.md` covering this sprint.

**Also fix the 007 entry's emphasis, explicitly requested — this is a
clarity edit, not the revisionism CLAUDE.md's append-only rule forbids.**
Nothing about the 007 result changes; state its actual strongest finding
(DNp01's spike *amplitude* is fixed at 50.0 always — the graded
jump-vs-flight decision is carried by spike *rate*, which is what the
GFC1-4 relay actually reads) as a clear leading sentence in "What we
learned," not a buried clause. Don't touch 001-006.

## 5. Explicitly out of scope

Any change to `circuit.py`, `dynamics.py`, `run_mario.py`,
`compare_controllers.py`, `speed_circuit.py`'s own wiring, or the climb
reflex's mechanics. Learning, the mushroom body, a harder benchmark — still
on the "Still open" list, still later.
