"""Part 4 pre-step: stair faces. (Evolution checks live in evolve.py / runs/003_evolution.md.)"""
from flyrun import env as E
from flyrun import level, scripted
from flyrun.run import _get_env


def test_stairs_each_step_is_a_face():
    """Scripted driver up the first staircase (x 2144..2192): a new 16 px face per step."""
    env = _get_env()
    env.reset()
    drv = scripted.Driver()
    seen = []   # (x of face, H) in order of first appearance while Mario is on/near the stairs
    pipe1 = None
    for f in range(4000):
        ram = env.unwrapped.ram
        mx = E.mario_x(ram)
        face, _ = level.obstacles_ahead(ram)
        if pipe1 is None and face is not None and face.x == 448:
            pipe1 = face.h
        if 2100 <= mx <= 2200 and face is not None and 2144 <= face.x <= 2192:
            if not seen or seen[-1] != (face.x, face.h):
                seen.append((face.x, face.h))
        if mx > 2200:
            break
        env.step(drv.act(ram))
    print("pipe1 H", pipe1, "stairs faces", seen)
    assert pipe1 == 32
    xs = [x for x, _ in seen]
    assert xs == sorted(set(xs)) and len(xs) >= 3          # a face per step, in order
    assert all(h == 16 for x, h in seen if x > 2144), seen   # each later step is 16 above the one below
