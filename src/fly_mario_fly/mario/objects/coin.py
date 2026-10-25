"""Coin: the floating coin tiles (not the coin a block gives when hit). A pickup, not terrain."""
from fly_mario_fly.contracts import Box
from fly_mario_fly.mario import ram as R
from fly_mario_fly.rules import declare


class Coin:
    name = "coin"
    label = "Coin"
    note = "One 16 x 16 box per visible coin tile (metatile ids 0xC2 and 0xC3, read in 4-3). A pickup: not a ceiling and not a wall."
    kind = "pickup"
    default_loom_shape = "own_box"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        t = facts["grid"]["tile"]
        return [R.instance("coin", wx, Box(wx, row * t, t, t), ram, facts, tile=tid, row=row)
                for wx, row, tid in R.tile_boxes(ram, facts, facts["tiles"]["coin"])]

    def remove(self, env):
        pass


PLUGIN = Coin()


DECLARATION = declare(
    "object", "invented",
    "A game object found by reading the game's RAM (the tile grid; ours, not the fly's). One 16 x 16 box per coin tile (ids 0xC2, 0xC3).")
