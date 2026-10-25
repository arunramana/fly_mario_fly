"""Piranha plant: lives in a pipe and only the part above the rim exists."""
from fly_mario_fly.mario import enemies
from fly_mario_fly.rules import declare


class Piranha:
    name = "piranha"
    label = "Piranha plant"
    note = "Rises out of a pipe; clipped at the pipe rim."
    kind = "enemy"
    default_loom_shape = "own_box"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        return enemies.find_enemies(ram, facts, self.name)

    def remove(self, env):
        enemies.remove_kind(env, self.name)


PLUGIN = Piranha()


DECLARATION = declare("object", "invented",
    "A game object found by reading the game's RAM (ours, not the fly's). Rises out of a pipe; clipped at the pipe rim.")
