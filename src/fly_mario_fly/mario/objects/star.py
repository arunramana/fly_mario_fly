"""Starman power-up. Same slot-5 object as the mushroom, told apart by PowerUpType (2)."""
from fly_mario_fly.mario.objects.mushroom import PowerUp
from fly_mario_fly.rules import declare


class Star(PowerUp):
    name = "star"
    label = "Star"
    note = "The live starman in object slot 5."


PLUGIN = Star()


DECLARATION = declare("object", "invented",
    "A game object found by reading the game's RAM (ours, not the fly's). The live starman in object slot 5.")
