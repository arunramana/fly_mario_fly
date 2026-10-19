"""Goomba: a walking mushroom enemy. Raw box from the enemy slots."""
from fly_mario.mario import enemies


class Goomba:
    name = "goomba"
    label = "Goomba"
    note = "Walks toward Mario; a stomp kills it, a touch kills Mario."
    kind = "enemy"
    default_loom_shape = "box"

    def find(self, ram, facts):
        return enemies.find_enemies(ram, facts, self.name)

    def remove(self, env):
        enemies.remove_kind(env, self.name)


PLUGIN = Goomba()
