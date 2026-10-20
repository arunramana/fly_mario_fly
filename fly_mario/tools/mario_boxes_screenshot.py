"""Throwaway: draw the object finders' boxes on four frames of 1-1 and save a PNG (not part of the test suite).

    python tools/mario_boxes_screenshot.py            -> tools/_out/mario_boxes.png
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fly_mario import registry                    # noqa: E402
from fly_mario.mario import ram as R               # noqa: E402
from fly_mario.mario.env import MarioEnv           # noqa: E402
from fly_mario.mario.walker import Walker          # noqa: E402

HUD = 32          # the status bar: tile-buffer y 0 is screen y 32
COLOURS = {"goomba": "#ff3030", "koopa": "#30c030", "piranha": "#ff30ff", "pipe": "#00e0e0", "step": "#e0a000",
           "pit": "#ffffff", "qblock": "#ffff00", "usedblock": "#a0a0a0", "brick": "#ff8040", "mushroom": "#ff60c0"}
SCALE = 2


def grab(env, step, objs):
    f = env.facts
    left = int(env.ram[f["ram"]["screen_page"]]) * 256 + int(env.ram[f["ram"]["screen_x"]])
    img = Image.fromarray(step.frame).convert("RGB").resize((256 * SCALE, 240 * SCALE), Image.NEAREST)
    d = ImageDraw.Draw(img)
    for name, plug in objs.items():
        for o in plug.find(env.ram, f):
            b = o.box
            x0, y0 = (b.x - left) * SCALE, (b.y + HUD) * SCALE
            d.rectangle([x0, y0, x0 + b.w * SCALE - 1, y0 + b.h * SCALE - 1], outline=COLOURS[name], width=2)
            d.text((x0 + 2, y0 + 2), name, fill=COLOURS[name])
    m = R.read_mario(env.ram, f)
    x0, y0 = (m.x - left) * SCALE, (m.y + HUD) * SCALE
    d.rectangle([x0, y0, x0 + m.w * SCALE - 1, y0 + m.h * SCALE - 1], outline="#00a0ff", width=2)
    d.text((x0 + 2, y0 - 12), "mario", fill="#00a0ff")
    return img


def in_view(env, objs):
    """Object types with at least one box well inside the screen (not on its right edge)."""
    f = env.facts
    left = int(env.ram[f["ram"]["screen_page"]]) * 256 + int(env.ram[f["ram"]["screen_x"]])
    return {n for n, p in objs.items() for o in p.find(env.ram, f) if left + 24 <= o.box.x and o.box.x + o.box.w <= left + 232}


def first_frame(env, objs, steps, want, sweep):
    """Step until a frame has every object type in `want` in view; return that step."""
    out = None
    for i in range(steps):
        if sweep:
            R.sweep_enemies(env, env.facts)
        out = env.step(env_walker(env))
        if want <= in_view(env, objs):
            return out
        if out.done:
            break
    raise RuntimeError(f"never saw {want}")


def env_walker(env):
    if not hasattr(env, "_w"):
        env._w = Walker()
    return env._w.act(env)


def main():
    objs = registry.list_plugins("objects")
    shots = []
    # 1: a Goomba with ? blocks and bricks (enemies left on, so this stops at the first frame that has them)
    # 2-4: a pipe, a pit and stair steps (enemies off so the walker lives that long)
    for want, sweep in (({"goomba", "qblock"}, False), ({"pipe"}, True), ({"pit"}, True), ({"step"}, True)):
        env = MarioEnv(); env.reset("1-1")
        out = first_frame(env, objs, 4000, want, sweep)
        shots.append(grab(env, out, objs))
    w, h = shots[0].size
    sheet = Image.new("RGB", (2 * w, 2 * h))
    for k, im in enumerate(shots):
        sheet.paste(im, ((k % 2) * w, (k // 2) * h))
    dest = Path(__file__).parent / "_out"
    dest.mkdir(exist_ok=True)
    sheet.save(dest / "mario_boxes.png")
    print(dest / "mario_boxes.png")


if __name__ == "__main__":
    main()
