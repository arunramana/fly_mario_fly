"""Starman power-up. Same slot-5 object as the mushroom, told apart by PowerUpType (2)."""
from fly_mario_fly.mario.objects.mushroom import PowerUp


class Star(PowerUp):
    name = "star"
    label = "Star"
    note = "The live starman in object slot 5."


PLUGIN = Star()
