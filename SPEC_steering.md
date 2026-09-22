# SPEC: fly_mario step 2 — steering

Goal: one video showing Mario **steering** — choosing left/right, not holding
right unconditionally — plus a second, contact-based pathway for climbing
obstacles. Both ride on top of the untouched jump circuit from
`SPEC_jump.md`; nothing there changes.

Scope of this step: replace the hardcoded right-hold with a real decision
made by DNa01/DNa02 under a constant "go home" bias, competing with a
mushroom-odour signal, plus a separate contact-triggered climbing reflex.
**No EPG ring, no ? blocks, no learning, no tile RAM.**

---

## 1. The circuit

**DNa01** (2, one per hemisphere: L=10442, R=10760) and **DNa02** (2:
R=10360, L=523769) — descending neurons implicated in steering control in
walking *Drosophila* (Rayshubskiy et al. 2020: DNa01/DNa02 drive ipsilateral
turning downstream of the central complex). That literature role is exactly
why they were picked for this step, and it maps directly onto
`CLAUDE.md` invariant 5 (keep hemispheres separate): **R-hemisphere activity
→ press Right, L-hemisphere activity → press Left.**

Expansion, same rule as SPEC_jump section 1b but scoped to these 4 bodies:
every presynaptic partner with **≥60 synapses onto DNa01 ∪ DNa02** (checked
by `query_input_pools.full_presynaptic_population`, live against the
connectome):

| N | new (non-core) partners |
|---|---|
| 60 | 325 |

**325 + 4 core = 329 neurons** — comparable in size to the original 313/315
jump circuit, "small" as required. Top partners by synapse weight are
premotor/central-complex-adjacent types (AN03A008, PS049, LAL124, VES007,
LAL018, DNae005, DNa03, ...), a mix of excitatory (ACh) and inhibitory
(GABA/Glu) — no name-based curation, same sign-agnostic threshold rule as
section 1b.

Extraction reuses `mcns.body_subgraph` + `circuit.build_signs` /
`build_weight_matrix` exactly, in a new module `steering_circuit.py` (mirrors
`circuit.py`, does not touch it).

**Dynamics: plain leaky-integrator rate model, no spiking fallback.**
`dynamics.step` (the un-hybridized ReLU leaky integrator) is reused as-is.
DNp01's spiking fallback existed because the jump circuit needed a *sharp,
committed* event; steering only needs a *continuous relative bias* between
two teams, which a rate model expresses natively. No third circuit-side
hand-set scalar is introduced here beyond gain.

**Gain.** Full Diagnostic-4-style sweep is out of scope this sprint ("cut for
speed"). Instead: compute the spectral radius of `W_steer` at g=1 (same
`circuit.spectral_radius` helper), and pick `G_STEER` the same way the first
jump-circuit pass did before the sweep existed — comfortably under the
runaway boundary, checked against a short constant-bias trace for silent
decay to a stable non-zero fixed point (not zero, not clipped). Documented
in the README as a deliberately lighter check than section 3's, not skipped
outright.

## 2. Input

### Home bias — a constant, not sensory

"Skip the EPG ring... a scalar bias is enough." `HOME_BIAS` is added directly
to the R-hemisphere DNa01+DNa02 units every frame, 0 to the L-hemisphere
ones — a constant external current, structurally identical to how
`I_sensory` already enters the jump circuit's leaky integrator
(`dynamics.step`'s `I` argument), just time-invariant. This is a genuine
fourth-and-up hand-set scalar and is flagged as such, per CLAUDE.md
invariant 3.

### Mushroom odour — real RAM, not a hardcoded event

Powerups occupy the **same 5 enemy object slots** as enemies (confirmed
against a public SMB disassembly, not guessed): `Enemy_Flag` (active)
`0x000F-0x0013`, `Enemy_ID` (type) `0x0016-0x001A`, `Enemy_X` `0x0087-0x008B`
— identical arrays `run_mario.py` already reads for Goombas. A power-up
(mushroom, fire flower, star, or 1-up — SMB's RAM does not distinguish the
subtype in this array, only a separate flag we don't read) is `Enemy_ID ==
0x2E`, `PowerUpObject`.

For each active slot with type `0x2E`: `d = enemy_x - mario_x` (same
convention as `enemy_thetas`), `concentration = 1 / max(|d|, 1)` — no extra
scaling constant, matching the precedent in `sensory.py` that θ/dθ need
none. Route by sign of `d` exactly like enemy routing: `d ≥ 0` excites the
R-hemisphere DNa01/DNa02, `d < 0` excites the L-hemisphere ones — so a
mushroom **behind** Mario pulls the L-team up, directly competing with
`HOME_BIAS`'s R-ward pull. That competition, not a scripted outcome, is the
thing to observe and report honestly in `runs/005_steering.md` — SPEC_jump's
own precedent ("the hypothesis... may not [hold]. Either result is worth
having.") applies here too.

**Demo scenario needs a real powerup in play, deterministically, without
touching `?` blocks (out of scope) or tile RAM.** SMB has no RNG; getting a
mushroom out of a `?` block requires precisely timed pixel-perfect
platforming that is not this sprint's job to script. Instead, inject one
synthetically by writing directly into an inactive enemy slot at a chosen
frame (`active=1`, `type=0x2E`, `x` = mario_x ± offset, `y` on the ground
plane) — the exact same move as `tune.py` driving the jump circuit with a
synthetic θ(t) ramp before ever touching the emulator (SPEC_jump section 3).
Not a `?`-block mechanic, not tile RAM, just a controlled test stimulus.
State this plainly in the run's `.md` writeup.

### Winner-take-all

`R_team = mean(h[DNa01_R], h[DNa02_R])`, `L_team` symmetric. Steering
direction = `argmax(L_team, R_team)`. Ties, or both under a floor, keep the
previous frame's direction (one bit of hysteresis state) rather than
flicker — a mechanical debounce, not a neural one, same spirit as the
existing jump-hold/cooldown state machine.

## 3. Terrain / climbing — contact-based, not visual

**No tile RAM this sprint** rules out reading obstacle height directly. The
real fly doesn't have that information either — legs sense load, not
distance. So: **blocked-forward** = `mario_x` unchanged for
`CLIMB_STALL_FRAMES` while steering says "go right" and no jump/unstick is
already in progress — the proprioceptive signal. On trigger, **try a short
hop first**; only if still blocked afterward does it escalate to a full
jump. This is the contact-based substitute for a priori height knowledge:
the fly's own rule ("step up something small, stop at a face taller") is
realised as *try small, escalate on failure* rather than *measure then
choose*, which is arguably more faithful to "proprioceptors sense leg load"
than pixel-counting a tile height would have been. Stated here as a judgment
call, same as SPEC_jump's LPi pooling exception.

Mario's own size (`0x0756`: 0=small, 1=big, ≥2=fiery) still gates the hop,
per your "same pipe is a different obstacle depending on state": small and
big Mario get different hop-hold durations (`CLIMB_HOP_SMALL_FRAMES` /
`CLIMB_HOP_BIG_FRAMES`), reflecting that the game's own collision box for
each size interacts differently with the same physical obstacle.

**Separate pathway from DNp01.** The escape jump and the climb
hop/jump are two independent triggers that happen to share the one A
button. Track them independently; when both want to press A in the same
frame, log it as a conflict (telemetry column + printed line) rather than
silently merging them — pressing A is idempotent either way, so nothing
mechanical needs resolving, but which circuit "wanted" it is worth knowing.

## 4. Output / overlay

New action space (was: hold right unconditionally):
`["right","B"], ["right","A","B"], ["left","B"], ["left","A","B"]` — lateral
button follows the WTA winner every frame; A follows OR(escape-jump,
climb-hop-or-jump), held for whichever trigger's own hold-duration fired.

`brain_panel.py` gains DNa01/DNa02 as two more populations in the live-brain
panel (real somas, same pipeline — VNC/central-complex adjacent, not optic
lobe), added conditionally on the telemetry actually carrying `dna01`/
`dna02` columns so the existing 4-population jump-only videos
(`compare_controllers.py`) render exactly as before. A `climb` flash (own
color, own label) is added next to the existing spike flash, plus a
`conflict` flash for the rare frame both triggers fire.

## 5. Deliverable

`runs/005_steering.mp4` (or `005a/005b` if this becomes a hero-run
comparison) with the brain panel, DNa01/DNa02 traces, and the climb-trigger
trace, on SMB 1-1, run from the start (no random warm-up — the synthetic
mushroom injection needs a known frame). `runs/005_steering.md` states: the
hand-set scalars added this sprint (`G_STEER`, `HOME_BIAS`,
`CLIMB_STALL_FRAMES`, `CLIMB_HOP_SMALL_FRAMES`, `CLIMB_HOP_BIG_FRAMES`), what
was observed when the mushroom competed with the home bias, and whether/how
often the two jump pathways conflicted.

## 6. Explicitly out of scope

`?` blocks, tile RAM, learning, retinotopic EPG ring, anything beyond the
jump + steering + contact-climb circuits above.
