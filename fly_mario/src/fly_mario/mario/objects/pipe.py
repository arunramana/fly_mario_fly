"""Pipe: a vertical wall face standing on the ground. Terrain, so remove() does nothing."""
from fly_mario.mario import ram as R


class Pipe:
    name = "pipe"
    label = "Pipe"
    note = "Raw column stack of pipe tiles; neighbouring equal-height columns are one pipe."
    kind = "terrain"
    default_loom_shape = "solid_block"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        return [R.instance("pipe", x0, R.face_box(x0, x1, H, facts), ram, facts)
                for x0, x1, H in R.merged_faces(ram, facts, facts["tiles"]["pipe"])]

    def remove(self, env):
        pass


PLUGIN = Pipe()
