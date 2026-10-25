# Adding a creature or an object

A creature (an enemy in the five enemy slots) or an object (tiles on the grid) is **a few lines of facts and one small plug-in file**. It only *reads the game's memory*, so it
is always **orange** (invented): the box is ours, not the fly's. The fly meets it through a sense (for looming that is the real route LC4/LPLC2 → Giant Fiber → jump).

The repo's newer ones are the template: `buzzy_beetle`, `red_koopa`, `hammer_bro`, `podoboo` (creatures) and `coin` (a pickup).

## 1. Read the facts off the emulator (do not guess)

For a creature you need its **RAM type byte**, the **states** it is alive in, and its **box size**. The community disassembly (and `mario/leveldata/enemies.py`) names the type bytes; confirm
them in the level where it first appears by watching the enemy slots:

```python
from fly_mario_fly.mario import ram as R, walker
from fly_mario_fly.mario.env import MarioEnv
env = MarioEnv(); env.reset("6-2", noop=3)
walker.walk_to(env, 864 - 260)                        # scripted walker, enemies off, stops before the beetle spawns
for _ in range(300):
    env.step(["right"])
    hits = [s for s in R.active_slots(env.ram, env.facts) if s[1] == 0x02]    # (slot, type byte, state, x, y)
    if hits:
        print(hits)
        break
```

Then check the box against the sprite by drawing `find()`'s boxes on a frame (see notebook 06, section 8): add the 32-pixel status bar to y.

## 2. Add the facts, then the plug-in

`src/fly_mario_fly/mario/facts/smb1.yaml`, under `objects:` (and `tiles:` for tile objects such as the coin):

```yaml
  buzzy_beetle:
    types: [0x02]
    size: [16, 16]
    live_states: [0, 1]
```

`src/fly_mario_fly/mario/objects/buzzy_beetle.py` (one file, one `PLUGIN`, one `DECLARATION`):

```python
from fly_mario_fly.mario import enemies
from fly_mario_fly.rules import declare


class BuzzyBeetle:
    name = "buzzy_beetle"
    label = "Buzzy Beetle"
    note = "16 x 16 walker, RAM type 0x02 (read in 6-2)."
    kind = "enemy"                     # enemy | obstacle | pickup | terrain
    default_loom_shape = "own_box"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        return enemies.find_enemies(ram, facts, self.name)     # reads facts["objects"][name]

    def remove(self, env):
        enemies.remove_kind(env, self.name)


PLUGIN = BuzzyBeetle()
DECLARATION = declare("character", "invented", "A creature found by reading the game's RAM (type byte 0x02); its box is ours, not the fly's.")
```

Use `kind = "terrain"` **only** for things that really are walls or ceilings: the headroom and wall shapes treat every terrain object in view as one, so a terrain plug-in changes how existing flies behave
(this is why the flagpole is not an object yet). A coin or any pickup is `kind = "pickup"`.

## 3. Check it

```bash
python -m fly_mario_fly.rules validate        # the declaration and the rules (CI runs this too)
python -m pytest tests/test_new_plugins.py -q  # copy a test: poke the RAM, find it in its own level, make sure 1-1 is unchanged
```

World 1-1 must not change: a new creature must not be in `levels.rom_objects("1-1")`, and the demo (`python scripts/demo.py`) must still give hash `3111e33d1b22`.

## 4. Attach a sense

In a fly's yaml (or with the MCP `add_cue` tool, see [mcp.md](mcp.md)):

```yaml
attachments:
  looming: [goomba, koopa, buzzy_beetle]
```

## The fast path: the MCP server

`add_character` (a creature by RAM type byte and size) and `add_object` (terrain by tile ids) write this kind of plug-in for you from a fixed recipe, validate it and smoke-test it in the emulator.
They keep the numbers inside the plug-in file; for a plug-in you intend to keep, moving them into `smb1.yaml` as above is the repo's convention.
