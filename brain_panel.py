"""
brain_panel.py — render the MaleCNS soma cloud as a live-brain panel and
composite it beside the emulator frames.

The silhouette is not drawn: it is 141,781 real soma coordinates from
`somaLocation` in the MaleCNS annotations, projected x (left-right) against
z (brain -> nerve cord). Brain with both optic lobes on top, VNC below. LC4 and
LPLC2 light up where they actually live in the optic lobes; TTMn sits in VNC
segment T2 where the jump muscle is driven.

Usage as a module:

    import brain_panel
    brain_panel.render_run(telemetry_df, frames_dir, "runs/006_shuffle_n20.mp4")

Usage from the command line:

    python brain_panel.py telemetry.csv frames/ runs/006_whatever.mp4

`telemetry_df` needs one row per emulator frame with columns:
    lc4, lplc2, mem, spike, ttmn      (population means + Giant Fiber state)
Optionally `theta`, `d_px`, `frame` for the caption.

NOTE: brightness is currently a POPULATION MEAN, not per-neuron activity — all
126 LC4 somas glow together. To upgrade, dump the full state vector from the
dynamics step and pass `per_neuron={'LC4': array, ...}`; the drawing code
already accepts per-soma alpha.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.feather as feather
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
ANN = ROOT / ".." / "data" / "malecns_v1.0" / \
    "body-annotations-male-cns-v1.0-minconf-0.5.feather"

W, H = 620, 910
SURFACE = (13, 13, 13)

# Dark-mode categorical slots. Four populations, but they occupy clearly
# separate anatomy and each is directly labelled, so identity never rests on
# hue alone.
COL = {"LC4": (57, 135, 229), "LPLC2": (25, 158, 112),
       "DNp01": (217, 89, 38), "TTMn": (230, 103, 103),
       "DNa01": (168, 121, 224), "DNa02": (222, 178, 60),
       "DNp09": (99, 200, 226), "DLMn": (240, 140, 200)}
LABEL = {"LC4": "LC4  looming", "LPLC2": "LPLC2  looming",
         "DNp01": "DNp01  Giant Fiber", "TTMn": "TTMn  jump muscle",
         "DNa01": "DNa01  steering", "DNa02": "DNa02  steering",
         "DNp09": "DNp09  forward walking", "DLMn": "DLMn  wing downstroke"}
ORDER = ["LC4", "LPLC2", "DNp01", "TTMn"]
# DNa01/DNa02/DNp09/DLMn are drawn only when a run's telemetry actually
# carries them (run_steering.py) -- see render_run's `populations` handling
# below. Their real somas are VNC/central-complex-adjacent, not optic lobe,
# but they come from the same _build() soma-position cache since it's keyed
# off COL. DLMn spans two connectome type strings ("DLMn c-f", "DLMn a, b")
# -- POP_TYPES maps the single panel key to both.
STEERING_ORDER = ["DNa01", "DNa02"]
TERRAIN_ORDER = ["DNp09", "DLMn"]
POP_TYPES = {"DLMn": ["DLMn c-f", "DLMn a, b"]}

_cache = {}


def _font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)
    except OSError:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except OSError:
            return ImageFont.load_default()


def _build():
    """Project every soma once and bake the faint whole-CNS background."""
    if _cache:
        return _cache
    if not ANN.exists():
        sys.exit(f"Annotations not found at {ANN}")

    df = feather.read_table(ANN, columns=["bodyId", "type", "somaLocation"]).to_pandas()
    df = df[df.somaLocation.notna()].copy()
    L = np.array([list(v) for v in df.somaLocation], dtype=float)
    px, pz = L[:, 0], L[:, 2]

    x0, x1, z0, z1 = px.min(), px.max(), pz.min(), pz.max()
    pad = 26
    s = min((W - 2 * pad) / (x1 - x0), (H - 2 * pad) / (z1 - z0))
    U = np.clip(((px - x0) * s + (W - (x1 - x0) * s) / 2).astype(int), 0, W - 1)
    V = np.clip(((pz - z0) * s + (H - (z1 - z0) * s) / 2).astype(int), 0, H - 1)

    dens = np.zeros((H, W), dtype=np.float32)
    np.add.at(dens, (V, U), 1.0)
    tone = np.log1p(dens) / np.log1p(dens.max())
    bg = np.zeros((H, W, 3), dtype=np.uint8)
    for c, base in enumerate((70, 78, 74)):
        bg[..., c] = np.maximum(np.clip(tone * base * 2.6, 0, base), SURFACE[c])

    _cache["bg"] = Image.fromarray(bg)
    _cache["pop"] = {t: (U[df.type.isin(POP_TYPES.get(t, [t])).values],
                         V[df.type.isin(POP_TYPES.get(t, [t])).values])
                     for t in COL}
    _cache["n"] = len(df)
    return _cache


def panel(act: dict, norm: dict, spike: bool = False, caption: str = "",
          populations: list | None = None, climb: bool = False,
          conflict: bool = False, pit: bool = False,
          long_jump: bool = False, odor_l: float | None = None,
          odor_r: float | None = None, hungry: bool | None = None,
          steer_left: bool = False, orn_a_l: float | None = None,
          orn_a_r: float | None = None, avers_l: float | None = None,
          avers_r: float | None = None, refusing: bool = False,
          r_team: float | None = None, l_team: float | None = None) -> Image.Image:
    """One frame of the brain panel. act/norm are {population: value}.
    `populations` defaults to the original jump-circuit four; pass ORDER +
    STEERING_ORDER to also draw DNa01/DNa02 (run_steering.py)."""
    pops = populations if populations is not None else ORDER
    c = _build()
    im = c["bg"].copy()
    d = ImageDraw.Draw(im, "RGBA")

    draw_order = [t for t in pops if t != "DNp01"] + (["DNp01"] if "DNp01" in pops else [])
    for t in draw_order:      # DNp01 last so it sits on top
        u, v = c["pop"][t]
        a = float(np.clip(act.get(t, 0.0) / max(norm.get(t, 1.0), 1e-9), 0, 1))
        r, g, b = COL[t]
        alpha = int(45 + 210 * a)
        rad = 1.6 + 4.2 * a + (2.5 if t in ("DNp01", "TTMn") else 0)
        if a > 0.35:
            for uu, vv in zip(u, v):
                d.ellipse([uu - rad * 2.4, vv - rad * 2.4,
                           uu + rad * 2.4, vv + rad * 2.4], fill=(r, g, b, int(30 * a)))
        for uu, vv in zip(u, v):
            d.ellipse([uu - rad, vv - rad, uu + rad, vv + rad], fill=(r, g, b, alpha))

    f, fs, fb = _font(13), _font(11), _font(15, True)
    d.text((18, 16), "LIVE BRAIN", font=fb, fill=(255, 255, 255))
    d.text((18, 38), f"{c['n']:,} neurons at their real somas", font=fs,
           fill=(137, 135, 129))
    d.text((18, 54), "MaleCNS v1.0  ·  brightness = population mean", font=fs,
           fill=(137, 135, 129))
    if caption:
        d.text((18, 70), caption, font=fs, fill=(137, 135, 129))
    if spike:
        d.text((430, 16), "GIANT FIBER SPIKE", font=fb, fill=(230, 103, 103))
    if climb:
        d.text((430, 36), "CLIMB", font=fb, fill=COL["DNa02"])
    if conflict:
        d.text((430, 56), "CONFLICT", font=fb, fill=(255, 255, 255))
    if pit:
        d.text((430, 76), "PIT AHEAD", font=fb, fill=COL["DNp01"])
    if long_jump:
        d.text((430, 96), "LONG JUMP (DLMn)", font=fb, fill=COL["DLMn"])
    if odor_l is not None and odor_r is not None:
        # Not a neuron population -- odour is an external RAM-derived signal,
        # not a soma, so it gets a text readout rather than a spot on the
        # brain (SPEC_odour.md: don't invent a fictitious neuron for it).
        d.text((18, 88), f"odour  L={odor_l:.3f}  R={odor_r:.3f}"
               + (f"   Mario: {'HUNGRY' if hungry else 'sated'}" if hungry is not None else ""),
               font=fs, fill=(195, 194, 183))
    if orn_a_l is not None and orn_a_r is not None:
        # ORN adaptation state -- also not a soma, a receptor property, same
        # text-readout treatment as odour itself, right below it.
        d.text((18, 104), f"ORN adapt  a_L={orn_a_l:.3f}  a_R={orn_a_r:.3f}",
               font=fs, fill=(137, 135, 129))
    if r_team is not None and l_team is not None:
        # sprint 017: the "DNa01" / "DNa02" bars below are means BY TYPE
        # (each already averaging its own L+R bodies together) -- they are
        # NOT what the WTA decides on, and will read as nearly identical to
        # EACH OTHER almost every frame by construction (DNa01/DNa02 receive
        # the same per-side current). r_team/l_team, by HEMISPHERE, is the
        # actual decision signal and the one place a steering asymmetry is
        # visible -- diagnosed the hard way in 017 after 016's own video had
        # to be read back via OCR with no r_team/l_team column to check.
        d.text((18, 136), f"steer  R_team={r_team:.3f}  L_team={l_team:.3f}",
               font=fs, fill=(120, 200, 160))
    if avers_l is not None and avers_r is not None:
        # Aversive odour (sprint 016) -- same text-readout treatment, not a
        # soma: it's a second RAM-derived channel through the same steering
        # circuit, not a distinct neuron population.
        d.text((18, 120), f"aversive odour  L={avers_l:.3f}  R={avers_r:.3f}",
               font=fs, fill=(214, 120, 100))
    if refusing:
        d.text((430, 136), "REFUSING (gap too wide)", font=fb, fill=(214, 120, 100))
    if steer_left:
        # HOME_BIAS only ever adds to the R team (run_steering.py) -- so the
        # WTA ever picking L is proof odour actually overcame it, not a
        # tie-break or noise. Worth flagging distinctly from the ordinary
        # per-frame direction readout.
        d.text((430, 116), "ODOUR OVERRIDE (steering L)", font=fb, fill=(230, 200, 60))

    y = H - (22 * len(pops) + 44)
    for t in pops:
        r, g, b = COL[t]
        a = float(np.clip(act.get(t, 0) / max(norm.get(t, 1.0), 1e-9), 0, 1))
        d.ellipse([18, y + 3, 26, y + 11], fill=(r, g, b))
        d.text((34, y), LABEL[t], font=fs, fill=(195, 194, 183))
        d.rectangle([210, y + 3, 330, y + 11], outline=(44, 44, 42))
        if a > 0:
            d.rectangle([210, y + 3, 210 + int(120 * a), y + 11], fill=(r, g, b))
        d.text((342, y), f"{act.get(t, 0):7.3f}", font=fs, fill=(195, 194, 183))
        y += 22
    return im


def render_run(tel: pd.DataFrame, frames_dir, out_path, fps: int = 60,
               caption: str = "") -> Path:
    """Composite the brain panel beside each emulator frame and encode an mp4."""
    frames = sorted(Path(frames_dir).glob("*.png"))
    if not frames:
        sys.exit(f"No frames in {frames_dir}")
    tel = tel.fillna(0).reset_index(drop=True)
    n = min(len(tel), len(frames))

    # The Giant Fiber's membrane resets to zero the instant it spikes, so mem
    # alone makes it go dark exactly when it fires. Hold the spike for a few
    # frames so the flash is visible at 60fps.
    gf = np.maximum(tel["mem"].to_numpy() / 0.5, 0.0)
    sp = tel["spike"].to_numpy().astype(float)
    hold = sp.copy()
    for k in (1, 2, 3):
        hold[k:] = np.maximum(hold[k:], sp[:-k] * (1 - 0.22 * k))
    gf = np.clip(np.maximum(gf, hold), 0, 1)

    norm = {"LC4": max(tel["lc4"].max(), 1e-9),
            "LPLC2": max(tel["lplc2"].max(), 1e-9),
            "DNp01": 1.0,
            "TTMn": max(tel["ttmn"].max(), 1e-9)}

    has_steer = "dna01" in tel.columns and "dna02" in tel.columns
    has_terrain = "dnp09" in tel.columns and "dlmn" in tel.columns
    populations = ORDER + (STEERING_ORDER if has_steer else []) + (TERRAIN_ORDER if has_terrain else [])
    if has_steer:
        norm["DNa01"] = max(tel["dna01"].max(), 1e-9)
        norm["DNa02"] = max(tel["dna02"].max(), 1e-9)
    if has_terrain:
        norm["DNp09"] = max(tel["dnp09"].max(), 1e-9)
        norm["DLMn"] = max(tel["dlmn"].max(), 1e-9)
    has_climb = "climb" in tel.columns
    has_conflict = "conflict" in tel.columns
    has_gap = "gap" in tel.columns
    has_long_jump = "long_jump" in tel.columns
    has_odor = "odor_l" in tel.columns and "odor_r" in tel.columns
    has_hunger = "hungry" in tel.columns
    has_direction = "direction" in tel.columns
    has_orn_adapt = "orn_a_l" in tel.columns and "orn_a_r" in tel.columns
    has_aversive = "avers_l" in tel.columns and "avers_r" in tel.columns
    has_refuse = "refusing" in tel.columns
    has_teams = "r_team" in tel.columns and "l_team" in tel.columns

    tmp = Path(out_path).parent / "_composite_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        row = tel.iloc[i]
        act = {"LC4": row.lc4, "LPLC2": row.lplc2, "DNp01": gf[i], "TTMn": row.ttmn}
        if has_steer:
            act["DNa01"] = row.dna01
            act["DNa02"] = row.dna02
        if has_terrain:
            act["DNp09"] = row.dnp09
            act["DLMn"] = row.dlmn
        p = panel(act, norm, spike=bool(row.spike), caption=caption,
                  populations=populations,
                  climb=bool(row.climb) if has_climb else False,
                  conflict=bool(row.conflict) if has_conflict else False,
                  pit=bool(row.gap > 0) if has_gap else False,
                  long_jump=bool(row.long_jump) if has_long_jump else False,
                  odor_l=float(row.odor_l) if has_odor else None,
                  odor_r=float(row.odor_r) if has_odor else None,
                  hungry=bool(row.hungry) if has_hunger else None,
                  steer_left=bool(row.direction == "L") if has_direction else False,
                  orn_a_l=float(row.orn_a_l) if has_orn_adapt else None,
                  orn_a_r=float(row.orn_a_r) if has_orn_adapt else None,
                  avers_l=float(row.avers_l) if has_aversive else None,
                  avers_r=float(row.avers_r) if has_aversive else None,
                  refusing=bool(row.refusing) if has_refuse else False,
                  r_team=float(row.r_team) if has_teams else None,
                  l_team=float(row.l_team) if has_teams else None)
        # show the real membrane value in the readout, not the held flash
        game = Image.open(frames[i])
        out = Image.new("RGB", (p.width + game.width, max(p.height, game.height)),
                        SURFACE)
        out.paste(p, (0, 0))
        out.paste(game, (p.width, 0))
        out.save(tmp / f"{i:05d}.png")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-framerate", str(fps),
         "-i", str(tmp / "%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "20", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", str(out_path)],
        check=True)
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    print(f"wrote {out_path}")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    render_run(pd.read_csv(sys.argv[1]), sys.argv[2], sys.argv[3])
