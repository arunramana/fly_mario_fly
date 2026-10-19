"""Breakable brick block (and the underground brick variants). Terrain."""
from fly_mario.contracts import Box
from fly_mario.mario import ram as R


class Brick:
    name = "brick"
    label = "Brick"
    note = "One 16 x 16 box per brick tile above the ground; also the ceiling that stops a jump."
    kind = "terrain"
    default_loom_shape = "solid_block"

    def find(self, ram, facts):
        t = facts["grid"]["tile"]
        return [R.instance("brick", wx, Box(wx, row * t, t, t), ram, facts, tile=tid, row=row)
                for wx, row, tid in R.tile_boxes(ram, facts, facts["tiles"]["brick"])]

    def remove(self, env):
        pass


PLUGIN = Brick()
