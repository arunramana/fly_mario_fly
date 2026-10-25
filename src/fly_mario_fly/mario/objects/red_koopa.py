"""Red Koopa Troopa: the Koopa that turns around at ledges. The existing `koopa` is the green one (type 0x00)."""
from fly_mario_fly.mario import enemies
from fly_mario_fly.rules import declare


class RedKoopa:
    name = "red_koopa"
    label = "Red Koopa"
    note = "16 x 24 walker, RAM type 0x03 (read in 3-3); the green Koopa is `koopa`. Its shell is not tracked."
    kind = "enemy"
    default_loom_shape = "own_box"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        return enemies.find_enemies(ram, facts, self.name)

    def remove(self, env):
        enemies.remove_kind(env, self.name)


PLUGIN = RedKoopa()


DECLARATION = declare(
    "character", "invented",
    "A creature found by reading the game's RAM (enemy slots, type byte 0x03; facts in mario/facts/smb1.yaml); its 16 x 24 box is ours, "
    "not the fly's. A sense attaches to it like to any creature: looming rides LC4/LPLC2 -> Giant Fiber -> jump.")
