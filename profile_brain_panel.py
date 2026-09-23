"""
profile_brain_panel.py -- sprint 026 step 1: where does one brain_panel
frame actually spend its time? Budget is 16.7ms (60fps real-time).

brain_panel.py is PIL, not matplotlib (the sprint brief's "matplotlib
overhead" is generalised here to "text/overlay drawing", the actual
PIL-equivalent phase -- stated plainly rather than silently assumed).
Three phases, timed separately, using a real frame's act/norm pulled
from 017's own telemetry (near its DNp01 commit, frame 148, so
population glow is non-trivial, not an all-zero warm-up frame):

    1. static background copy      (c["bg"].copy())
    2. active-neuron ellipse draw  (the per-soma glow + dot loop)
    3. text/label overlay          (captions, legend, bars -- PIL's
                                     ImageDraw.text, the "matplotlib
                                     overhead" analogue)
"""
import time

import numpy as np
import pandas as pd
from PIL import ImageDraw

import brain_panel as bp

N = 100  # iterations per phase, median reported


def build_frame_inputs():
    tel = pd.read_csv("runs/017_step1_fixes_telemetry.csv")
    row = tel[tel["frame"] == 148].iloc[0]  # the DNp01 commit frame -- real glow, not idle
    act = {"LC4": row.lc4, "LPLC2": row.lplc2, "DNp01": 1.0, "TTMn": row.ttmn,
           "DNa01": row.dna01, "DNa02": row.dna02, "DNp09": row.dnp09, "DLMn": row.dlmn}
    norm = {"LC4": max(tel["lc4"].max(), 1e-9), "LPLC2": max(tel["lplc2"].max(), 1e-9),
            "DNp01": 1.0, "TTMn": max(tel["ttmn"].max(), 1e-9),
            "DNa01": max(tel["dna01"].max(), 1e-9), "DNa02": max(tel["dna02"].max(), 1e-9),
            "DNp09": max(tel["dnp09"].max(), 1e-9), "DLMn": max(tel["dlmn"].max(), 1e-9)}
    pops = bp.ORDER + bp.STEERING_ORDER + bp.TERRAIN_ORDER
    return act, norm, pops, row


def time_phase(fn, n=N):
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000.0)
    return np.median(times), np.percentile(times, 90)


def main():
    act, norm, pops, row = build_frame_inputs()
    c = bp._build()  # warm the cache once, same as production (memoized)

    # phase 1: static background copy alone
    med, p90 = time_phase(lambda: c["bg"].copy())
    print(f"1. background copy        : median={med:.3f}ms  p90={p90:.3f}ms")

    # phase 2: active-neuron ellipse draw (population glow + soma dots),
    # same logic as panel()'s draw loop, isolated
    def draw_neurons():
        im = c["bg"].copy()
        d = ImageDraw.Draw(im, "RGBA")
        draw_order = [t for t in pops if t != "DNp01"] + (["DNp01"] if "DNp01" in pops else [])
        for t in draw_order:
            u, v = c["pop"][t]
            a = float(np.clip(act.get(t, 0.0) / max(norm.get(t, 1.0), 1e-9), 0, 1))
            r, g, b = bp.COL[t]
            alpha = int(45 + 210 * a)
            rad = 1.6 + 4.2 * a + (2.5 if t in ("DNp01", "TTMn") else 0)
            if a > 0.35:
                for uu, vv in zip(u, v):
                    d.ellipse([uu - rad * 2.4, vv - rad * 2.4,
                               uu + rad * 2.4, vv + rad * 2.4], fill=(r, g, b, int(30 * a)))
            for uu, vv in zip(u, v):
                d.ellipse([uu - rad, vv - rad, uu + rad, vv + rad], fill=(r, g, b, alpha))
        return im
    med, p90 = time_phase(draw_neurons)
    print(f"2. active-neuron draw      : median={med:.3f}ms  p90={p90:.3f}ms")

    # phase 3: full panel() call minus phases 1+2 isolated above -- i.e.
    # text/label/legend overlay only, applied on top of an already-drawn
    # neuron image (same image draw_neurons() produces)
    im = draw_neurons()

    def draw_text_overlay():
        im2 = im.copy()
        d = ImageDraw.Draw(im2, "RGBA")
        f, fs, fb = bp._font(13), bp._font(11), bp._font(15, True)
        d.text((18, 16), "LIVE BRAIN", font=fb, fill=(255, 255, 255))
        d.text((18, 38), f"{c['n']:,} neurons at their real somas", font=fs, fill=(137, 135, 129))
        d.text((18, 54), "MaleCNS v1.0  ·  brightness = population mean", font=fs, fill=(137, 135, 129))
        d.text((18, 88), f"odour  L={row.odor_l:.3f}  R={row.odor_r:.3f}", font=fs, fill=(195, 194, 183))
        d.text((18, 136), f"steer  R_team={row.r_team:.3f}  L_team={row.l_team:.3f}", font=fs, fill=(120, 200, 160))
        y = bp.H - (22 * len(pops) + 44)
        for t in pops:
            r, g, b = bp.COL[t]
            a = float(np.clip(act.get(t, 0) / max(norm.get(t, 1.0), 1e-9), 0, 1))
            d.ellipse([18, y + 3, 26, y + 11], fill=(r, g, b))
            d.text((34, y), bp.LABEL[t], font=fs, fill=(195, 194, 183))
            d.rectangle([210, y + 3, 330, y + 11], outline=(44, 44, 42))
            if a > 0:
                d.rectangle([210, y + 3, 210 + int(120 * a), y + 11], fill=(r, g, b))
            d.text((342, y), f"{act.get(t, 0):7.3f}", font=fs, fill=(195, 194, 183))
            y += 22
        return im2
    med, p90 = time_phase(draw_text_overlay)
    print(f"3. text/label overlay      : median={med:.3f}ms  p90={p90:.3f}ms")

    # phase 4: the REAL panel() call, end to end, for a sanity total
    def full_panel():
        return bp.panel(act, norm, spike=False, caption="", populations=pops,
                         odor_l=float(row.odor_l), odor_r=float(row.odor_r),
                         r_team=float(row.r_team), l_team=float(row.l_team))
    med, p90 = time_phase(full_panel)
    print(f"4. full panel() (sanity)   : median={med:.3f}ms  p90={p90:.3f}ms")
    print(f"\nbudget: 16.7ms for real-time (60fps)")


if __name__ == "__main__":
    main()
