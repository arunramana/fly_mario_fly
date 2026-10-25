"""Game objects built from a fixed recipe, so a new one can be declared with numbers instead of code.

The MCP server (`add_character`, `add_object`) writes a plug-in file that only calls these classes with validated literals.
Both read the game's RAM and nothing else; both are ours (orange). Not a plug-in folder: it has no PLUGIN.

  SlotCreature   a creature in the five enemy slots, found by its RAM type byte(s): box = (x, feet - h, w, h).
  TileTerrain    solid terrain made of given metatile ids standing on the ground: one box per wall face (like a pipe).
"""
from __future__ import annotations

from fly_mario_fly.contracts import Box
from fly_mario_fly.mario import ram as R


class SlotCreature:
    kind = "enemy"
    block_hit_tile = None
    causes_fall_death = False

    def __init__(self, *, name, label, note, type_bytes, size, live_states=(0,), default_loom_shape="own_box"):
        self.name, self.label, self.note = name, label, note
        self.type_bytes, self.size, self.live_states = tuple(type_bytes), tuple(size), tuple(live_states)
        self.default_loom_shape = default_loom_shape

    def find(self, ram, facts):
        w, h = self.size
        off = facts["grid"]["enemy_feet_offset"]
        out = []
        for slot, typ, state, ex, ey in R.active_slots(ram, facts):
            if typ in self.type_bytes and state in self.live_states:
                box = Box(ex, ey - off - h, w, h)
                out.append(R.instance(self.name, slot, box, ram, facts, slot=slot, type_byte=typ, ram_state=state))
        return out

    def remove(self, env):
        R.remove_types(env, env.facts, self.type_bytes)


class TileTerrain:
    kind = "terrain"
    block_hit_tile = None
    causes_fall_death = False

    def __init__(self, *, name, label, note, tile_ids, default_loom_shape="solid_block"):
        self.name, self.label, self.note = name, label, note
        self.tile_ids, self.default_loom_shape = tuple(tile_ids), default_loom_shape

    def find(self, ram, facts):
        return [R.instance(self.name, x0, R.face_box(x0, x1, H, facts), ram, facts)
                for x0, x1, H in R.merged_faces(ram, facts, self.tile_ids)]

    def remove(self, env):
        pass
