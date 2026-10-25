# Writing a plug-in

Everything the fly can sense, do or be attached to is a plug-in: **one file, one object called `PLUGIN`, one `DECLARATION`**. The registry finds them by folder, so adding one means adding a file.
Attachments (which sense is on which object) are config in `configs/flies/*.yaml`, not code.

| you want to add | folder | contract (`contracts.py`) | declaration `kind` |
|---|---|---|---|
| a **sense** (cue -> input neurons) | `senses/` | `cue(objects, mario, facts, knobs, memory) -> SenseOutput` | `sense` |
| an **action** (neuron rates -> button) | `actions/` | `decide(rates, knobs, state) -> ButtonIntent` | `action` |
| a **creature** (enemy slots) | `mario/objects/` | `find(ram, facts)`, `remove(env)` | `character` |
| an **object** (terrain, pickup, pit...) | `mario/objects/` | the same | `object` |
| a **shape** (how an object looms) | `senses/shapes/` | `shape(obj, facts, knobs) -> Box` | `shape` |
| a **scene** edit (no enemies, start at x) | `mario/scenes/` | `on_reset(env, p)`, `on_frame(env, p)` | `scene` |
| a **mechanism** (a real circuit) | `fly/mechanisms/` | a `MechanismSpec` | `mechanism` |

For creatures and objects read [adding_creatures.md](adding_creatures.md) (facts first, plug-in second). To add a sense or creature from an AI client without writing Python, see [mcp.md](mcp.md).

## The steps

1. **Copy a neighbour.** Open the closest existing file (`senses/sweet_smell.py` for a smell, `actions/walk.py` for a button) and change it. Keep its shape.
2. **Declare it** (see [rules-of-the-fly.md](rules-of-the-fly.md)): what is real (teal), what is invented (orange), and for senses and actions the real route.
3. **Dials** are `KnobSpec`s on the plug-in (`knobs = [...]`): `origin="invented"`, a range, `evolvable` only if evolution may tune it, a unique key like `my_sense.gain`.
4. **Validate:** `python -m fly_mario_fly.rules validate`. The messages say what to change.
5. **Test:** `tests/test_<area>_*.py`, on small hand-built frames (see `tests/test_senses_behaviour.py`); never the 1 GB weights.
6. **Attach and run:** add it to a fly's yaml and run it (`python -m fly_mario_fly.runner run <fly> --level 1-1 --seed 101`, or the web app).
7. **Prove nothing else changed:** the full suite, and `python scripts/demo.py` must still print hash `3111e33d1b22`. If a change can alter a run, say so in the PR instead of hiding it.

## A minimal sense

```python
"""Sweet smell for pipes: the nearest pipe drives the attractive-smell antennae (illustration)."""
from fly_mario_fly.contracts import KnobSpec, SenseOutput
from fly_mario_fly.rules import Route, declare
from fly_mario_fly.senses.kit import draw
from fly_mario_fly.senses.kit.geom import eye_of, theta_of


class PipeSmell:
    name = "pipe_smell"
    label = "Pipe smell"
    effect = "The nearest attached object drives the antenna on its side."
    scope = "per_object"                 # attached to object types in a fly's yaml ("whole_fly" = looks at everything)
    colour = draw.GREEN
    line = "solid"
    feeds = ["attraction"]               # the mechanism (real circuit) whose input groups it drives
    order = 45
    raises = []
    reads = []
    knobs = [KnobSpec("pipe_smell.gain", "Smell strength", "faint", "strong", 100.0, 10.0, 1000.0, scale="log",
                      origin="invented", evolvable=True)]

    def cue(self, objects, mario, facts, knobs, memory):
        if not objects:
            return SenseOutput(inputs={"ORN_L": 0.0, "ORN_R": 0.0})
        ex, ey = eye_of(mario, 0.0)
        o = min(objects, key=lambda o: abs(o.box.x + o.box.w / 2 - ex))
        level = knobs["pipe_smell.gain"] * theta_of(abs(o.box.x - ex), o.box.h) * memory.noise()     # noise is seeded
        left = o.box.x + o.box.w / 2 < mario.x + mario.w / 2
        return SenseOutput(inputs={"ORN_L": level if left else 0.0, "ORN_R": 0.0 if left else level},
                           overlay=[draw.box(o.box.x, o.box.y, o.box.w, o.box.h, self.colour)])


PLUGIN = PipeSmell()
DECLARATION = declare(
    "sense", "invented",
    "Invented cue: a smell level that grows with the nearest object's angular size; the ORN -> steering wiring is real.",
    route=Route("attraction", ("ORN*",), "ORN (attractive smell receptors) -> DNa01/02 (steering)"),
    drives=("ORN_L", "ORN_R"))
```

What the validator would refuse: `feeds` and the route naming different circuits, `drives` containing anything but input groups of that circuit (for example `DNp01`), a missing declaration, a dial that says `origin="fly"`.

## Mechanisms are the heavy case

A new circuit means new MaleCNS neurons. It needs: groups in `fly/groups.yaml`, a `MechanismSpec` (input groups, output groups, the extra neurons and the rule that picks them), a verified real route in the data
(cite the cell types and synapse counts), and a test that the brain it builds matches what the data says. It changes brains, so it is always its own reviewed PR; the existing mechanisms (`fly/mechanisms/`) are the templates.
