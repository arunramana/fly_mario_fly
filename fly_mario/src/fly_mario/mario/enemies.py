"""Shared reading of the enemy slots (not a plug-in: the objects/ folder holds only plug-ins)."""
from __future__ import annotations

from fly_mario.contracts import Box, ObjectInstance
from fly_mario.mario import ram as R


def find_enemies(ram, facts, name: str) -> list:
    """Live enemies of one kind (goomba / koopa / piranha) as raw boxes. World px, y = top of the box.

    A dead or stomped enemy (state not in live_states) is not an object any more. A Koopa in its shell
    is still a koopa, 16 x 16, with state['shell'] set."""
    spec = facts["objects"][name]
    off = facts["grid"]["enemy_feet_offset"]
    out = []
    pipe_cols = None
    for slot, typ, state, ex, ey in R.active_slots(ram, facts):
        if typ not in spec["types"]:
            continue
        shell = name == "koopa" and state in spec["shell_states"]
        if not shell and state not in spec["live_states"]:
            continue
        w, h = spec["shell_size"] if shell else spec["size"]
        feet = ey - off
        if name == "piranha":
            # The plant lives inside its pipe, drawn behind it: only the part above the rim exists. A plant whose
            # pipe has not scrolled into the tile buffer yet is not there at all.
            if pipe_cols is None:
                ids = facts["tiles"]["pipe"] + facts["tiles"]["step"]
                pipe_cols = {x: H for x0, x1, H in R.merged_faces(ram, facts, ids)
                             for x in range(x0, x1, facts["grid"]["tile"])}
            t = facts["grid"]["tile"]
            heights = [pipe_cols.get((ex // t) * t), pipe_cols.get(((ex + w - 1) // t) * t)]
            if None in heights:
                continue
            rim = facts["grid"]["ground_row"] * t - max(heights)
            h = max(0, min(feet, rim) - (feet - h))
            if h == 0:
                continue
        out.append(ObjectInstance(name, slot, Box(ex, feet - spec["size"][1] if name == "piranha" else feet - h, w, h),
                                  "ahead", {"slot": slot, "type_byte": typ, "ram_state": state, "shell": shell}))
    return [R.instance(o.type, o.id, o.box, ram, facts, **o.state) for o in out]


def remove_kind(env, name: str) -> None:
    """Switch off every live enemy of one kind in the running game."""
    R.remove_types(env, env.facts, facts_types(env.facts, name))


def facts_types(facts, name: str) -> list:
    return facts["objects"][name]["types"]
