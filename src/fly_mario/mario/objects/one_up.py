"""1-up mushroom power-up. Same slot-5 object as the mushroom, told apart by PowerUpType (3)."""
from fly_mario.mario.objects.mushroom import PowerUp


class OneUp(PowerUp):
    name = "one_up"
    label = "1-up mushroom"
    note = "The live 1-up mushroom in object slot 5."


PLUGIN = OneUp()
