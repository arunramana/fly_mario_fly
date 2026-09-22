# SPEC: fly_mario step 5 — habituation and the backward-walking fallback

Fixes the pathology 009's live recording surfaced by accident: a reflex
(escape or climb) that fires repeatedly against an obstacle it never
clears, forever, because nothing about the reflex itself changes when it
keeps failing. Diagnosed, not assumed: `CLIMB_COOLDOWN_FRAMES` 15→40
changed nothing (byte-identical run); `CLIMB_STALL_FRAMES` 20→60 revealed
the true clock was the escape/takeoff pathway's own `LONG_JUMP_HOLD_FRAMES`
(35) + `JUMP_COOLDOWN_FRAMES` (40) = 75-frame hold-then-cooldown cycle, not
climb at all — climb was riding along on top of it.

## 1. Generalised habituation — any reflex, same mechanism

**Real, documented biology, not a timeout**: the Giant Fiber pathway
habituates to repeated stimulation in real flies — repeated activation
without resolution weakens the pathway's own response. Modeled here as a
property of *firing without progress*, applied identically to both
reflexes that share the A button (escape/DLMn and climb), each with its
own independent state:

```
ReflexHabituation:
  on each frame the reflex's trigger condition is true:
    progress = mario_x - last_check_x   (None first time -> no penalty)
    if progress < PROGRESS_THRESHOLD (one tile, 16px):
        hab_level = min(hab_level + 1, GIVE_UP)
    else:
        hab_level = 0                    # it worked -- fully re-sensitise
    last_check_x = mario_x
    fires = hab_level < GIVE_UP
```

`last_check_x` updates every time the condition recurs, whether or not the
reflex actually fires — so a suppressed reflex keeps "listening" for the
progress that would re-sensitise it (e.g. after MDN backs Mario up and a
later attempt actually clears the obstacle). This sits entirely in
`run_steering.py`'s decision layer, gating whether an already-computed
TTMn/DLMn crossing or a blocked-forward stall is acted on — `circuit.py`,
`dynamics.py`, `run_mario.py` are not touched; the real neurons still
compute exactly what they always computed, habituation only gates whether
that computation gets to press the button.

## 2. MDN — the escape-failed fallback

MDN confirmed in the connectome exactly as stated: **4 bodies** (10763 R,
11288 L, 11332 R, 12348 L), `descending_neuron`, subclass `xn`. No direct
synapse from DNp01 or GFC1-4 (checked) — same situation as DNp09 in 007, so
it gets its own small circuit: MDN(4) + N≥60 presynaptic partners (93,
`mdn_circuit.py`, same reused extraction/signs/weight-matrix pipeline as
every prior population).

Driver: since there is no real synaptic path from the escape circuit into
MDN, "escape habituates past threshold → MDN takes over" is implemented the
same way `HOME_BIAS`/`WALK_DRIVE`/`GAP_GAIN` already are — an external
current (`MDN_DRIVE`) injected onto all 4 MDN bodies **only when the escape
reflex's `hab_level` reaches `GIVE_UP`**, i.e. it has already fully given
up. This is not a new category of hand-set input; it is the same thing
gap-width already does for DNp01, aimed at a different population.

When MDN's mean activation crosses `MDN_THRESHOLD`, it **overrides** the
steering WTA's lateral output to "press left" for `MDN_BACKUP_FRAMES` —
a hard override, not one more competing bias, matching "backing up is the
fly's actual escape-failed move" rather than a nudge alongside everything
else. Climb gets habituation (section 1) but no MDN-equivalent fallback —
not asked for, and climb already has its own hop→escalate ladder.

## 3. The demonstration

Three configurations, same exact scenario 009 got stuck in (1-1,
`inject_frame=60`, `force_mario_size=0`): baseline (009's behaviour),
habituation only, habituation+MDN. Report the frame the pin actually
breaks in the third case, and confirm the first two stay pinned (per your
own prediction: habituation alone converts the bounce into a stand-still,
not an escape).
