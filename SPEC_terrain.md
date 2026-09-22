# SPEC: fly_mario step 3 — terrain (pits, speed, and — if time allows — smell)

Goal: unlock the two things a looming detector structurally cannot see —
absence of ground, and a stationary odour source that must be stood under —
via one tile-RAM decoder. Read `docs/RUNS.md` "Still open" before touching
anything; this sprint closes three of its four bullets.

**Priority order, stated by you: ship 1+2+3, leave 4+5 for next sprint if it
runs long.** Pits kill runs; `?` blocks are optional polish.

---

## 1. Tile RAM decoder

`Block_Buffer_1` at `0x0500`, `Block_Buffer_2` at `0x05D0`, 13 rows × 16
columns each (confirmed against the public disassembly's `BlockBufferColumnPos`
/ `MetatileBuffer` machinery — this matches your `0x0500-0x069F` exactly:
`0x0500 + 0xD0 = 0x05D0`, `0x05D0 + 0xD0 = 0x06A0`).

**Do not trust a tile-ID table off the internet without checking it against
this ROM.** Two sources disagreed with each other during research for this
spec — one gives `0xC0`/`0xC1` as the question-block IDs and `0xC2`/`0xC3` as
plain coin tiles, the other (your own note) says `0xC2`/`0xC3` are the
question blocks. **Resolve this empirically, the way SPEC_jump resolved
LPLC1**: dump the raw buffer bytes under Mario's feet while he is
demonstrably standing on solid ground (not falling), dump the bytes under a
known pit in 1-1 (there are two, both well before the first flagpole — you'll
know because Mario falls through if he doesn't jump), and dump the bytes at
the row of `?` blocks that follows the first pipe in 1-1. Whichever byte value
actually shows up at each of those three known-truth locations *is* the
ground/air/question-block ID for this build — cite the ROM, not the wiki, in
the README. Save a few frames with the decoded grid overlaid as text (or
drawn) next to the real screenshot so this can be eyeballed, per your
instruction — don't ship the decoder unverified.

Column indexing: the buffer is a 32-column ring (2 screens × 16 cols) that
scrolls as Mario advances; there is a RAM value tracking which absolute column
maps to buffer column 0 (candidates near `0x071A`/`0x071C`, already referenced
by `gym_super_mario_bros/smb_env.py`'s `_left_x_position` as the "screen left"
anchor) — derive the exact mapping empirically the same way: place a tile you
know is solid (Mario is standing on it) and confirm which buffer cell it
resolves to at Mario's own screen column.

Deliverable: a small module (`tile_ram.py`) exposing, relative to Mario's
current foot column:
- `ground_ahead(ram, n_tiles)` → bool per offset, or the count of consecutive
  grounded tiles from a given offset (a pit = a run of *not*-ground).
- `solid_ahead(ram)` → whether the tile in front of Mario at chest/head height
  is solid, i.e. an obstacle to walk into (feeds `run_steering.py`'s existing
  contact-based climb — this sprint doesn't need to replace that reflex, just
  can now *tell it apart from a pit*, which the blind stall-detector never
  could).
- `question_blocks_near(ram, x_range)` → level-x positions of `?` tiles
  currently in the tile buffer (used by section 4, if reached).

## 2. Pit → long jump via the Giant Fiber's own graded output

**A pit is invisible to LC4/LPLC2 — it is not a tweak to their input, it's a
separate modality hitting the same escape command neuron**, exactly the way a
real fly's Giant Fiber integrates multiple threat modalities (visual looming,
wind-puff, etc.) onto one decision. Inject `gap_width` (consecutive
non-ground tiles ahead, from `tile_ram.ground_ahead`) as an **extra external
current added onto DNp01's existing per-frame `I`**, both hemispheres
symmetrically (a pit dead ahead isn't lateralised) — same `I` vector
`dynamics.HybridState.step` already takes for looming, just one more term
summed in. New scalar: `GAP_GAIN` (current per non-ground tile ahead).
**The jump circuit itself (`circuit.py`, `dynamics.py`, `run_mario.py`) is
not modified** — this is one more line adding to `I[DNp01_idx]` at the call
site, nothing upstream changes.

**DLMn recruitment is real connectome, not invented.** Queried directly
against the weights file for this spec: DNp01 has **zero direct synapses
onto DLMn** — but real, substantial synapses onto **GFC1-4** (Giant Fiber
Circuit interneurons: 144/112/107/97 synapses respectively from DNp01), and
GFC1-4 synapse onto DLMn with 80 real edges. This is the documented
disynaptic jump→flight relay in the Giant Fiber literature (GF → PSI-class
interneuron → DLMn), not fabricated for this sprint — it's exactly why the
GFC types exist as a named class in this connectome.

New module `takeoff_circuit.py`: core = DNp01 (2, same bodies as the jump
circuit) + GFC1-4 (34 neurons found in this connectome) + DLMn (10: 8 in
`DLMn c-f`, 2 in `DLMn a, b` — matches your stated count exactly). Real
edges via `mcns.body_subgraph`, signs via `circuit.build_signs`, weight
matrix via `circuit.build_weight_matrix` — all reused, nothing new to write
there. Dynamics: plain `dynamics.step` (no spiking fallback needed — DLMn's
job is graded recruitment, not commitment).

**Interface to the existing jump circuit**: read the running
`dynamics.HybridState`'s DNp01 output (its `.h[dnp01_idx]`, post-spike) each
frame and use it as the external drive onto the DNp01 rows of
`takeoff_circuit`'s own `W` — the jump circuit's code and state are
untouched; this is a one-directional read, once per frame. `gap_width`'s
current is injected **once**, into the jump circuit's DNp01, and its
graded effect on DLMn happens because the whole downstream chain is real
recurrent connectivity, not because the signal is injected twice.

Outcome, per your framing (binary, not continuous, to keep this sprint
shippable): `TTMn` alone crossing threshold → the existing `JUMP_HOLD_FRAMES`
(short hop, unchanged). `TTMn` **and** `DLMn` (mean activation over its 10
bodies) crossing its own new threshold `DLMN_RECRUIT_THRESHOLD` in the same
window → `LONG_JUMP_HOLD_FRAMES` (longer A-hold = higher and farther arc,
the mechanism SMB already uses for jump distance). Note in the README that
continuous hold-duration scaling with DLMn's actual activation level is the
natural next step, not done here.

## 3. DNp09 → graded speed

DNp09 (2 neurons, confirmed) has **no direct synapse from DNa01/DNa02**
(checked) — it needs its own small circuit, same recipe as steering:
N≥60 presynaptic partners is **23 neurons** (25 total with DNp09 itself),
`speed_circuit.py`, real edges/signs/weights via the same reused helpers.

Driver: `WALK_DRIVE`, a constant external bias (same structural role as
`HOME_BIAS` on the steering circuit) representing baseline motivation to
walk, **minus a suppression term active while a jump/hop hold or a
blocked-forward stall is in progress** — an escape or a climb attempt
transiently interrupting ongoing locomotion is itself a real, documented
phenomenon, not invented for convenience. Press **B iff** DNp09's mean
activation (after the leaky dynamics settle) is over `DNP09_SPEED_THRESHOLD`.

This is what finally lets Mario stop: `MOVES` drops the permanent `B` hold;
B is now conditional, mirroring how A already was.

Action space grows to cover every {left, right} × {B on/off} × {A on/off}
combination actually reachable (8 entries) rather than hardcoding B in.

## 4. `?` blocks as odour (if 1-3 shipped with room to spare)

Same odour mechanism as the mushroom in `SPEC_steering.md` section 2, source
at each `?` block position found by `tile_ram.question_blocks_near`,
concentration `1/distance` into the same DNa01/DNa02 steering pathway.
**State the limitation up front, in the README, not as a surprise later**:
odour here is a horizontal signal (left/right routing, same as the mushroom)
— it can only get Mario to *stand under* the block. Actually hitting it from
below is the climb reflex's job (an upward A-press against a solid tile
directly overhead), which is a second, separate stage. Don't conflate them
in the writeup: report whichever stage was actually observed working.

## 5. Hunger gates the odour (if 4 shipped)

**This is the fix for run 006's finding, and it is not "shrink HOME_BIAS."**
Shrinking the bias makes Mario permanently distractible, which trades one
failure mode for a worse one. Instead: small Mario (`RAM 0x0756 == 0`) is
hungry, big/fiery Mario is sated. Scale **all** odour gain (mushroom from 006
and `?`-block odour from section 4) by a hunger factor tied to that RAM
byte — full gain when small, reduced (not necessarily zero) when big/fiery.
Re-run 006's synthetic-mushroom test with Mario forced small and report
plainly whether the WTA decision actually flips this time. If it still
doesn't, say so — that's the honest result, not a reason to keep raising the
gain until it does.

## 6. Deliverable

`runs/007_terrain.mp4` (brain panel; add DNp09, DLMn, and the pit signal as
their own traces, same additive pattern `brain_panel.py` already uses for
DNa01/DNa02 — gated on the telemetry columns actually being present so
`compare_controllers.py`'s existing videos keep rendering unmodified).
Append the four-field entry to `docs/RUNS.md` per its own stated format —
Setup / What happened / What we learned, append-only, no editing 001-006.

## 7. Explicitly out of scope

Tile-based rendering changes, learning, the mushroom body / hunger-as-a-real-
circuit (still just a RAM-byte gate here, not a modeled 540-neuron
population — that's still on the "Still open" list for later), anything not
listed above.
