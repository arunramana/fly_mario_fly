"""Smoke tests for a plug-in that has not been registered yet: does it run at all, and does it stay inside its declaration?

Used by the MCP server before it writes a new plug-in file. Imports the game and senses lazily (this package is neutral: it is
neither fly/ nor mario/).
"""
from __future__ import annotations

import math

from fly_mario_fly.rules.guards import check_sense_output


def smoke_sense(plugin, declaration) -> list:
    """Call a sense's cue() on hand-made frames (a creature ahead, a creature behind, nothing). Returns a list of problems."""
    import numpy as np

    from fly_mario_fly.contracts import Box, MarioState, ObjectInstance, SenseOutput
    from fly_mario_fly.mario.facts import load_facts
    from fly_mario_fly.senses.kit.memory import SenseMemory

    facts, problems = load_facts("1-1"), []
    knobs = {k.key: k.default for k in plugin.knobs}
    mario = MarioState(x=100.0, y=160.0, w=12.0, h=16.0, airborne=False, power="small", facing=1)
    frames = {"object ahead": [ObjectInstance("probe", 0, Box(160, 160, 16, 16), "ahead", {"slot": 0, "shell": False})],
              "object behind": [ObjectInstance("probe", 1, Box(20, 160, 16, 16), "behind", {"slot": 1, "shell": False})],
              "nothing": []}
    for label, objs in frames.items():
        mem = SenseMemory()
        mem.rng, mem.sigma, mem.world, mem.mods = np.random.default_rng(0), 0.0, list(objs), {}
        try:
            out = plugin.cue(list(objs), mario, facts, knobs, mem)
        except Exception as e:                       # noqa: BLE001: report anything a broken plug-in raises
            problems.append(f"cue() raised {type(e).__name__} on '{label}': {e}")
            continue
        if not isinstance(out, SenseOutput):
            problems.append(f"cue() must return a SenseOutput, got {type(out).__name__}")
            continue
        try:
            check_sense_output(plugin.name, out.inputs, declaration.drives)
        except ValueError as e:
            problems.append(str(e))
        for g, v in out.inputs.items():
            if not (isinstance(v, (int, float)) and math.isfinite(v) and v >= 0):
                problems.append(f"cue() gave {v!r} for {g} on '{label}': levels must be finite and not negative")
    return problems


def smoke_object(plugin) -> list:
    """Reset the game, walk a few frames, call find() (and remove()); the instances must have a Box and a valid side."""
    from fly_mario_fly.contracts import Box, ObjectInstance
    from fly_mario_fly.mario.env import MarioEnv

    env, problems = MarioEnv(), []
    try:
        env.reset("1-1", noop=3)
        for _ in range(120):
            env.step(["right"])
        found = plugin.find(env.ram, env.facts)
        if not isinstance(found, list):
            problems.append(f"find() must return a list, got {type(found).__name__}")
        else:
            for o in found:
                if not isinstance(o, ObjectInstance) or not isinstance(o.box, Box) or o.side not in ("ahead", "behind", "above", "below"):
                    problems.append(f"find() returned something that is not a valid ObjectInstance: {o!r}")
                    break
        plugin.remove(env)
    except Exception as e:                           # noqa: BLE001
        problems.append(f"find()/remove() raised {type(e).__name__}: {e}")
    finally:
        env.close()
    return problems


def known_type_bytes() -> dict:
    """{creature name: [RAM type bytes]} for every creature already described in the facts."""
    from fly_mario_fly.mario.facts import load_facts
    objs = load_facts("1-1")["objects"]
    return {n: list(v["types"]) for n, v in objs.items() if isinstance(v, dict) and "types" in v}


def known_tile_ids() -> dict:
    """{tile id: facts key} for every metatile id the facts already name (empty tile excluded)."""
    from fly_mario_fly.mario.facts import load_facts
    out = {}
    for key, val in load_facts("1-1")["tiles"].items():
        for t in (val if isinstance(val, list) else [val]):
            if isinstance(t, int) and t != 0:
                out.setdefault(t, key)
    return out
