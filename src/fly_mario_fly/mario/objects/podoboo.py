"""Podoboo: a fireball that leaps out of the lava in castles."""
from fly_mario_fly.mario import enemies
from fly_mario_fly.rules import declare


class Podoboo:
    name = "podoboo"
    label = "Podoboo"
    note = "16 x 16 lava fireball, RAM type 0x0C (read in 2-4). Its box can be below the screen while it is in the lava."
    kind = "enemy"
    default_loom_shape = "own_box"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        return enemies.find_enemies(ram, facts, self.name)

    def remove(self, env):
        enemies.remove_kind(env, self.name)


PLUGIN = Podoboo()


DECLARATION = declare(
    "character", "invented",
    "A creature found by reading the game's RAM (enemy slots, type byte 0x0C; facts in mario/facts/smb1.yaml); its 16 x 16 box is ours, "
    "not the fly's. A sense attaches to it like to any creature: looming rides LC4/LPLC2 -> Giant Fiber -> jump.")
