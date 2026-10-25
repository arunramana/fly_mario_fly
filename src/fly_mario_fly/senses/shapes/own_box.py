"""The object's own box: what you would see if you looked at it. The default for anything that moves (enemies, pickups)."""
from fly_mario_fly.contracts import Box
from fly_mario_fly.rules import declare


class OwnBox:
    name = "own_box"
    label = "Its own box"
    description = "The object's own silhouette. A Goomba looms as a 16 x 16 box."
    knobs = []
    family = "free"          # how a looming sense treats it: a free-standing box that Mario can get past

    def shape(self, obj, facts, knobs):
        b = obj.box
        return Box(b.x, b.y, b.w, b.h)


PLUGIN = OwnBox()


DECLARATION = declare("shape", "invented",
    "How an object's box is turned into the box the looming cue measures (our choice). The object's own silhouette. A Goomba looms as a 16 x 16 box.")
