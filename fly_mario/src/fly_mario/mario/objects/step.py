"""Step: hard (staircase) blocks standing on the ground. Terrain, so remove() does nothing."""
from fly_mario.mario import ram as R


class Step:
    name = "step"
    label = "Stair step"
    note = "Raw column stack of hard blocks; one box per run of equal-height columns."
    kind = "terrain"
    default_loom_shape = "box"

    def find(self, ram, facts):
        return [R.instance("step", x0, R.face_box(x0, x1, H, facts), ram, facts)
                for x0, x1, H in R.merged_faces(ram, facts, facts["tiles"]["step"])]

    def remove(self, env):
        pass


PLUGIN = Step()
