"""Hammer Bro: hops between ledges and throws hammers (the hammers themselves are not tracked)."""
from fly_mario_fly.mario import enemies
from fly_mario_fly.rules import declare


class HammerBro:
    name = "hammer_bro"
    label = "Hammer Bro"
    note = "16 x 24, RAM type 0x05 (read in 3-1), hops up and down. The thrown hammers are not tracked."
    kind = "enemy"
    default_loom_shape = "own_box"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        return enemies.find_enemies(ram, facts, self.name)

    def remove(self, env):
        enemies.remove_kind(env, self.name)


PLUGIN = HammerBro()


DECLARATION = declare(
    "character", "invented",
    "A creature found by reading the game's RAM (enemy slots, type byte 0x05; facts in mario/facts/smb1.yaml); its 16 x 24 box is ours, "
    "not the fly's. A sense attaches to it like to any creature: looming rides LC4/LPLC2 -> Giant Fiber -> jump.")
