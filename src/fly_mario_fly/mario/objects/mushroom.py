"""Super Mushroom power-up. Lives in the power-up slot (5), not the enemy slots. Also the base of the other power-ups
(fire_flower, star, one_up): one object id (0x2E), told apart by PowerUpType."""
from fly_mario_fly.contracts import Box
from fly_mario_fly.mario import ram as R


class PowerUp:
    name = "mushroom"
    label = "Mushroom"
    note = "The live super mushroom in object slot 5."
    kind = "pickup"
    default_loom_shape = "own_box"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        r, g, spec = facts["ram"], facts["grid"], facts["objects"][self.name]
        s = g["powerup_slot"]
        if not int(ram[r["enemy_active"] + s]) or int(ram[r["enemy_type"] + s]) not in spec["types"]:
            return []
        if int(ram[r["powerup_type"]]) not in spec["powerup_types"]:
            return []
        x = int(ram[r["enemy_page"] + s]) * 256 + int(ram[r["enemy_x"] + s])
        w, h = spec["size"]
        top = int(ram[r["enemy_y"] + s]) - g["enemy_feet_offset"] - h
        return [R.instance(self.name, s, Box(x, top, w, h), ram, facts, slot=s)]

    def remove(self, env):
        r, s = env.facts["ram"], env.facts["grid"]["powerup_slot"]
        if int(env.ram[r["enemy_active"] + s]) and int(env.ram[r["powerup_type"]]) in env.facts["objects"][self.name]["powerup_types"]:
            env.poke(r["enemy_active"] + s, 0)


class Mushroom(PowerUp):
    pass


PLUGIN = Mushroom()
