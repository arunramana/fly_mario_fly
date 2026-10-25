"""Fire flower power-up. Same slot-5 object as the mushroom, told apart by PowerUpType (1)."""
from fly_mario_fly.mario.objects.mushroom import PowerUp
from fly_mario_fly.rules import declare


class FireFlower(PowerUp):
    name = "fire_flower"
    label = "Fire flower"
    note = "The live fire flower in object slot 5 (a power-up block hit by big Mario)."


PLUGIN = FireFlower()


DECLARATION = declare("object", "invented",
    "A game object found by reading the game's RAM (ours, not the fly's). The live fire flower in object slot 5 (a power-up block hit by big Mario).")
