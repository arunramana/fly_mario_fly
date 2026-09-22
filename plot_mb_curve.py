"""Plot the mushroom-body training curve with PIL (not matplotlib -- this
project's venv pins numpy<2 for nes-py, matplotlib is not installed and
adding it risks pulling in a numpy upgrade; PIL is already a project
dependency via brain_panel.py, zero risk)."""
import sys
import csv

from PIL import Image, ImageDraw, ImageFont

csv_path = sys.argv[1] if len(sys.argv) > 1 else "mb_training_curve.csv"
out_path = sys.argv[2] if len(sys.argv) > 2 else "runs/014_mb_learning_curve.png"

rows = []
with open(csv_path) as f:
    for row in csv.DictReader(f):
        rows.append((int(row["episode"]), int(row["max_x_abs"])))

W, H, PAD = 900, 450, 60
im = Image.new("RGB", (W, H), (18, 18, 18))
d = ImageDraw.Draw(im)
try:
    font = ImageFont.truetype("arial.ttf", 14)
    font_b = ImageFont.truetype("arial.ttf", 18)
except OSError:
    font = font_b = ImageFont.load_default()

xs = [r[0] for r in rows]
ys = [r[1] for r in rows]
x_min, x_max = min(xs), max(xs)
y_min, y_max = 0, max(max(ys) * 1.15, 100)


def to_px(x, y):
    px = PAD + (x - x_min) / max(x_max - x_min, 1) * (W - 2 * PAD)
    py = H - PAD - (y - y_min) / (y_max - y_min) * (H - 2 * PAD)
    return px, py


d.line([to_px(x_min, y_min), to_px(x_max, y_min)], fill=(90, 90, 90))
d.line([to_px(x_min, y_min), to_px(x_min, y_max)], fill=(90, 90, 90))

pts = [to_px(x, y) for x, y in rows]
for px, py in pts:
    d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(80, 160, 230))
if len(pts) > 1:
    d.line(pts, fill=(80, 160, 230, 120), width=1)

# rolling mean (window 10)
roll = []
for i in range(len(ys)):
    lo = max(0, i - 9)
    roll.append(sum(ys[lo:i + 1]) / (i - lo + 1))
roll_pts = [to_px(x, y) for x, y in zip(xs, roll)]
d.line(roll_pts, fill=(220, 60, 60), width=3)

n = len(rows)
first_q = ys[:max(1, n // 4)]
last_q = ys[-max(1, n // 4):]
d.text((PAD, 15), f"Mushroom body training -- {n} episodes, level 1-1, identical savestate",
       font=font_b, fill=(230, 230, 230))
d.text((PAD, 38), f"blue = per-episode max x-progress (px)   red = rolling mean (10 ep)",
       font=font, fill=(170, 170, 170))
d.text((W - 340, 15),
       f"1st quarter mean={sum(first_q)/len(first_q):.1f}  "
       f"last quarter mean={sum(last_q)/len(last_q):.1f}",
       font=font, fill=(170, 170, 170))
d.text((10, H // 2), "max x (px)", font=font, fill=(150, 150, 150))
d.text((W // 2, H - 25), "episode", font=font, fill=(150, 150, 150))

im.save(out_path)
print(f"wrote {out_path}")
print(f"first quarter ({len(first_q)} ep): mean={sum(first_q)/len(first_q):.1f}")
print(f"last quarter  ({len(last_q)} ep): mean={sum(last_q)/len(last_q):.1f}")
print(f"overall: mean={sum(ys)/len(ys):.1f} min={min(ys)} max={max(ys)} "
      f"unique values={sorted(set(ys))}")
