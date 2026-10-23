"""Solid tiles that no other object claims but that still stop a rising head: the ground-coloured blocks that make up
an underground ceiling (84), the solid blocks of 1-1 (87, 88) and 1-2's sideways exit pipe (28-33). Terrain."""
from fly_mario_fly.contracts import Box
from fly_mario_fly.mario import ram as R


class CeilingBlock:
    name = "ceiling_block"
    label = "Ceiling block"
    note = "One 16 x 16 box per solid tile above the ground that is not a brick, pipe, step or ? block; it only matters overhead."
    kind = "terrain"
    default_loom_shape = "solid_block"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        t = facts["grid"]["tile"]
        return [R.instance("ceiling_block", wx, Box(wx, row * t, t, t), ram, facts, tile=tid, row=row)
                for wx, row, tid in R.tile_boxes(ram, facts, facts["tiles"]["ceiling_block"])]

    def remove(self, env):
        pass


PLUGIN = CeilingBlock()
