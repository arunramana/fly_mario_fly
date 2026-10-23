"""Fire flower power-up. Same slot-5 object as the mushroom, told apart by PowerUpType (1)."""
from fly_mario_fly.mario.objects.mushroom import PowerUp


class FireFlower(PowerUp):
    name = "fire_flower"
    label = "Fire flower"
    note = "The live fire flower in object slot 5 (a power-up block hit by big Mario)."


PLUGIN = FireFlower()
