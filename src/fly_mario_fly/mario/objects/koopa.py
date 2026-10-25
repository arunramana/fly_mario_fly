"""Koopa Troopa (green and red): walks until stomped, then sits in a shell."""
from fly_mario_fly.mario import enemies
from fly_mario_fly.rules import declare


class Koopa:
    name = "koopa"
    label = "Koopa"
    note = "16 x 24 walking; 16 x 16 in its shell (state['shell'])."
    kind = "enemy"
    default_loom_shape = "own_box"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        return enemies.find_enemies(ram, facts, self.name)

    def remove(self, env):
        enemies.remove_kind(env, self.name)


PLUGIN = Koopa()


DECLARATION = declare("object", "invented",
    "A game object found by reading the game's RAM (ours, not the fly's). 16 x 24 walking; 16 x 16 in its shell (state['shell']).")
