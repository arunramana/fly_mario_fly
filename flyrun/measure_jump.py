"""Part S2c: measure MAX_JUMP_HEIGHT = apex above take-off of a full walking jump (A held 40 frames, Right held, flat ground).
python -m flyrun.measure_jump"""
from . import env as E


def measure(hold=40, walk=60):
    env = E.make_env()
    env.reset()
    ram = env.ram
    for _ in range(walk):                       # walk right on flat ground first (walking speed, before pipe 1 at x~447)
        env.step(E.RIGHT)
    y0, x0 = int(ram[0x00CE]), E.mario_x(ram)
    ys, f = [], 0
    while True:
        a = E.RIGHT_A if f < hold else E.RIGHT
        env.step(a)
        f += 1
        ys.append(int(ram[0x00CE]))
        if f > 3 and int(ram[0x001D]) == 0:
            break
        if f > 200:
            break
    return y0, x0, y0 - min(ys), f, E.mario_x(ram)


if __name__ == "__main__":
    for hold in (30, 40, 50):
        print("hold", hold, "(ground y, x0, apex height, frames, x_land)", measure(hold))
