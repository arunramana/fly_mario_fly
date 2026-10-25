"""1-up mushroom power-up. Same slot-5 object as the mushroom, told apart by PowerUpType (3)."""
from fly_mario_fly.mario.objects.mushroom import PowerUp
from fly_mario_fly.rules import declare


class OneUp(PowerUp):
    name = "one_up"
    label = "1-up mushroom"
    note = "The live 1-up mushroom in object slot 5."


PLUGIN = OneUp()


DECLARATION = declare("object", "invented",
    "A game object found by reading the game's RAM (ours, not the fly's). The live 1-up mushroom in object slot 5.")
