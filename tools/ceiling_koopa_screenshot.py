"""Throwaway: two frames of 1-2 near the Koopa (x ~ 850-900) with every terrain box drawn; ceiling_block in magenta.

    python tools/ceiling_koopa_screenshot.py            -> tools/_out/ceiling_koopa.png
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fly_mario_fly import registry                    # noqa: E402
from fly_mario_fly.mario import ram as R               # noqa: E402
from fly_mario_fly.mario.env import MarioEnv           # noqa: E402

HUD, SCALE = 32, 2
COL = {"ceiling_block": "#ff00ff", "brick": "#ffffff", "step": "#e0a000", "pipe": "#00e0e0", "qblock": "#ffff00",
       "usedblock": "#a0a0a0", "koopa": "#30c030", "goomba": "#ff3030", "piranha": "#ff30ff"}


def grab(env, step, plugins):
    f = env.facts
    left = int(env.ram[f["ram"]["screen_page"]]) * 256 + int(env.ram[f["ram"]["screen_x"]])
    img = Image.fromarray(step.frame).convert("RGB").resize((256 * SCALE, 240 * SCALE), Image.NEAREST)
    d = ImageDraw.Draw(img, "RGBA")
    for name, p in plugins.items():
        if name not in COL:
            continue
        for o in p.find(env.ram, f):
            b = o.box
            x0, y0 = (b.x - left) * SCALE, (b.y + HUD) * SCALE
            d.rectangle([x0, y0, x0 + b.w * SCALE - 1, y0 + b.h * SCALE - 1], outline=COL[name], width=2, fill=COL[name] + "70" if p.kind == "terrain" else None)
    m = R.read_mario(env.ram, f)
    x0, y0 = (m.x - left) * SCALE, (m.y + HUD) * SCALE
    d.rectangle([x0, y0, x0 + m.w * SCALE - 1, y0 + m.h * SCALE - 1], outline="#00a0ff", width=2)
    d.text((4, 4), f"1-2  mario x {m.x}   ceiling_block = magenta", fill="#ffffff")
    return img


def main():
    plugins = registry.list_plugins("objects")
    env = MarioEnv()
    env.reset("1-2")
    shots, want = [], [850, 872]
    for i in range(4000):
        out = env.step(("right", "A") if i % 30 < 16 else ("right",))
        if out.done:
            break
        if want and R.mario_x(env.ram, env.facts) >= want[0]:
            shots.append(grab(env, out, plugins))
            want.pop(0)
    if len(shots) < 2:                       # he stopped short of the second mark: show the last frame
        shots.append(grab(env, out, plugins))
    w, h = shots[0].size
    sheet = Image.new("RGB", (2 * w, h))
    for k, im in enumerate(shots):
        sheet.paste(im, (k * w, 0))
    dest = Path(__file__).parent / "_out"
    dest.mkdir(exist_ok=True)
    sheet.save(dest / "ceiling_koopa.png")
    print(dest / "ceiling_koopa.png", len(shots))


if __name__ == "__main__":
    main()
