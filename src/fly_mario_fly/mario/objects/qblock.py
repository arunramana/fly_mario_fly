"""? block that has not been hit yet. Terrain."""
from fly_mario_fly.contracts import Box
from fly_mario_fly.mario import ram as R
from fly_mario_fly.rules import declare


class QBlock:
    name = "qblock"
    label = "? block"
    note = "Unused ? block; state['tile'] is the tile id (192 or 193)."
    kind = "terrain"
    default_loom_shape = "solid_block"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        t = facts["grid"]["tile"]
        return [R.instance("qblock", wx, Box(wx, row * t, t, t), ram, facts, tile=tid, row=row)
                for wx, row, tid in R.tile_boxes(ram, facts, facts["tiles"]["qblock"])]

    def remove(self, env):
        pass


PLUGIN = QBlock()


DECLARATION = declare("object", "invented",
    "A game object found by reading the game's RAM (ours, not the fly's). Unused ? block; state['tile'] is the tile id (192 or 193).")
