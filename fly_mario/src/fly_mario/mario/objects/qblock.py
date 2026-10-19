"""? block that has not been hit yet. Terrain."""
from fly_mario.contracts import Box
from fly_mario.mario import ram as R


class QBlock:
    name = "qblock"
    label = "? block"
    note = "Unused ? block; state['tile'] is the tile id (192 or 193)."
    kind = "terrain"
    default_loom_shape = "box"

    def find(self, ram, facts):
        t = facts["grid"]["tile"]
        return [R.instance("qblock", wx, Box(wx, row * t, t, t), ram, facts, tile=tid, row=row)
                for wx, row, tid in R.tile_boxes(ram, facts, facts["tiles"]["qblock"])]

    def remove(self, env):
        pass


PLUGIN = QBlock()
