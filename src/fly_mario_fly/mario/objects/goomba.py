"""Goomba: a walking mushroom enemy. Raw box from the enemy slots."""
from fly_mario_fly.mario import enemies
from fly_mario_fly.rules import declare


class Goomba:
    name = "goomba"
    label = "Goomba"
    note = "Walks toward Mario; a stomp kills it, a touch kills Mario."
    kind = "enemy"
    default_loom_shape = "own_box"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        return enemies.find_enemies(ram, facts, self.name)

    def remove(self, env):
        enemies.remove_kind(env, self.name)


PLUGIN = Goomba()


DECLARATION = declare("object", "invented",
    "A game object found by reading the game's RAM (ours, not the fly's). Walks toward Mario; a stomp kills it, a touch kills Mario.")
