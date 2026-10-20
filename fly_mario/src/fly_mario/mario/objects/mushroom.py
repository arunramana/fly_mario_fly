"""Super Mushroom power-up. Lives in the power-up slot (5), not the enemy slots."""
from fly_mario.contracts import Box
from fly_mario.mario import ram as R


class Mushroom:
    name = "mushroom"
    label = "Mushroom"
    note = "The live power-up in object slot 5."
    kind = "pickup"
    default_loom_shape = "own_box"
    block_hit_tile = None
    causes_fall_death = False

    def find(self, ram, facts):
        r, g, spec = facts["ram"], facts["grid"], facts["objects"]["mushroom"]
        s = g["powerup_slot"]
        if not int(ram[r["enemy_active"] + s]) or int(ram[r["enemy_type"] + s]) not in spec["types"]:
            return []
        x = int(ram[r["enemy_page"] + s]) * 256 + int(ram[r["enemy_x"] + s])
        w, h = spec["size"]
        top = int(ram[r["enemy_y"] + s]) - g["enemy_feet_offset"] - h
        return [R.instance("mushroom", s, Box(x, top, w, h), ram, facts, slot=s)]

    def remove(self, env):
        r, s = env.facts["ram"], env.facts["grid"]["powerup_slot"]
        if int(env.ram[r["enemy_active"] + s]):
            env.poke(r["enemy_active"] + s, 0)


PLUGIN = Mushroom()
