"""A ? block that has been hit (or is bumping). Terrain."""
from fly_mario.contracts import Box
from fly_mario.mario import ram as R


class UsedBlock:
    name = "usedblock"
    label = "Used block"
    note = "Empty block after a hit; the bump animation is its own tile id (state['tile'])."
    kind = "terrain"
    default_loom_shape = "solid_block"
    block_hit_tile = "block_hit"        # key in facts["tiles"]: an instance in this tile id counts as a block the run hit

    def find(self, ram, facts):
        t = facts["grid"]["tile"]
        return [R.instance("usedblock", wx, Box(wx, row * t, t, t), ram, facts, tile=tid, row=row)
                for wx, row, tid in R.tile_boxes(ram, facts, facts["tiles"]["used_block"])]

    def remove(self, env):
        pass


PLUGIN = UsedBlock()
