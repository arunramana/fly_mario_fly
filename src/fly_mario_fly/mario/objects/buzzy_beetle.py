"""Buzzy Beetle: a hard-shelled walker (fire cannot hurt it). It first appears in World 4-2 and 6-2 among the levels read here."""
from fly_mario_fly.mario import enemies
from fly_mario_fly.rules import declare


class BuzzyBeetle:
    name = "buzzy_beetle"
    label = "Buzzy Beetle"
    note = "16 x 16 walker, RAM type 0x02 (read in 6-2). Only live states are found: a stomped beetle (its shell) is not."
    kind = "enemy"
    default_loom_shape = "own_box"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        return enemies.find_enemies(ram, facts, self.name)

    def remove(self, env):
        enemies.remove_kind(env, self.name)


PLUGIN = BuzzyBeetle()


DECLARATION = declare(
    "character", "invented",
    "A creature found by reading the game's RAM (enemy slots, type byte 0x02; facts in mario/facts/smb1.yaml); its 16 x 16 box is ours, "
    "not the fly's. A sense attaches to it like to any creature: looming rides LC4/LPLC2 -> Giant Fiber -> jump.")
