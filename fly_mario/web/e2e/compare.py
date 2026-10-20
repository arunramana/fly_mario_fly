"""Side-by-side images, wireframe | ours, in screenshots/compare/ (run from web/, after e2e/shots.mjs)."""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "screenshots" / "compare"
OUT.mkdir(parents=True, exist_ok=True)
PAIRS = {"scene": "Main", "fly": "Fly", "advanced": "Advanced", "run": "Run", "retry": "Retry"}


def pair(left: Path, right: Path, out: Path, names=("wireframe", "ours")) -> None:
    a, b = Image.open(left).convert("RGB"), Image.open(right).convert("RGB")
    h = max(a.height, b.height) + 28
    sheet = Image.new("RGB", (a.width + b.width + 20, h), (40, 40, 40))
    sheet.paste(a, (0, 28))
    sheet.paste(b, (a.width + 20, 28))
    d = ImageDraw.Draw(sheet)
    d.text((8, 8), names[0], fill=(255, 255, 0))
    d.text((a.width + 28, 8), names[1], fill=(255, 255, 0))
    sheet.save(out)


for mine, wire in PAIRS.items():
    pair(HERE / "design" / f"{wire}.png", HERE / "screenshots" / "mine" / f"{mine}.png", OUT / f"{mine}.png")
# The Run tab at the extremes: next to the R3 video frame it has to look like, and on its own.
for size in ("1280x720", "2560x1440"):
    pair(HERE / "design" / "run_r3.png", HERE / "screenshots" / "mine" / f"run_{size}.png", OUT / f"run_{size}.png",
         ("run_r3 (the approved video look)", f"ours at {size}"))
print(sorted(p.name for p in OUT.iterdir()))
