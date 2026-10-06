# What this file does, in plain English:
# Reads the shadow-mode logs (a human played, the fly only watched) and answers the
# four questions written down in docs/SPEC_shadow.md before any play: were the
# fly's jump signals there when the human pressed jump, did the fly's Giant Fiber
# spikes line up with human jump presses, was the walking signal on when the human
# held Right, and was the fly early or late. It then applies the pre-registered
# yes/no rule (signals present -> the gap is in the motor rule, absent -> the gap is
# in the brain) and writes a markdown summary, with one block for each pipe and the
# first pit showing what the fly saw while the human crossed it. It changes nothing.
"""brain/shadow_analysis.py -- docs/SPEC_shadow.md ("Pre-registered questions", "Segments").

    .venv/Scripts/python.exe -m brain.shadow_analysis a.csv b.csv --out docs/RESULTS_shadow.md

Pure functions on a DataFrame with the shadow CSV columns (brain/shadow.py COLUMNS) plus a `run` column from `load_runs`.
Press = rising edge of human A. Spike frame = `gf_spike` == 1. Offsets are spike frame minus press frame (negative = fly early).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# ---- pre-registered constants (docs/SPEC_shadow.md; fixed before any data, not tuned) ---------------------------------
Q2_WINDOW = 5                    # frames either side
Q4_WINDOW = 30                   # frames either side: beyond this a press has "no GF spike"
Q4_BIN = 3                       # histogram bin width in frames
PRESENT_FRACTION = 0.5           # Q1 muscle-drive fraction and Q2 must reach this
PRESENT_MEDIAN_ABS_OFFSET = 3    # Q4 median |offset| (absent = infinite) must not exceed this
SEGMENTS = {"pipe 1": 448, "pipe 2": 608, "pipe 3": 736, "gap 1 (pit, 32 px)": 1104}   # world x of the feature's left edge (1-1 tile columns 28, 38, 46, 69)
SEG_BEFORE, SEG_AFTER, SEG_TRACE_STEP = 90, 30, 6


def thresholds() -> tuple[float, float]:
    """(a_threshold, walk_threshold) from brain/calibration.json. Read, never set here."""
    from brain.calibration import Calibration
    m = Calibration.load().motor
    return m.a_threshold, m.walk_threshold


def load_runs(paths) -> pd.DataFrame:
    """Concatenate shadow CSVs; `run` numbers the files so frame offsets are only ever computed inside one run."""
    frames = []
    for i, p in enumerate(paths):
        d = pd.read_csv(p)
        d.insert(0, "run", i)
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def rising_edges(held) -> np.ndarray:
    """Indices where `held` goes from 0 to 1 (a frame 0 that is already held counts as a press)."""
    h = np.asarray(held).astype(bool)
    prev = np.concatenate([[False], h[:-1]])
    return np.flatnonzero(h & ~prev)


def nearest_offsets(events: np.ndarray, spikes: np.ndarray, window: int) -> np.ndarray:
    """Per event, spike - event for the nearest spike (ties go to the earlier spike); NaN when none within +-window."""
    out = np.full(len(events), np.nan)
    if len(spikes) == 0:
        return out
    for i, e in enumerate(events):
        off = spikes - e
        k = np.argmin(np.abs(off) * 2 + (off > 0))        # |off| first, the earlier (negative) one on a tie
        if abs(off[k]) <= window:
            out[i] = off[k]
    return out


def _runs(df: pd.DataFrame):
    for _, d in df.groupby("run", sort=True):
        yield d.reset_index(drop=True)


# ---- the four questions -------------------------------------------------------------------------------------------
def q1(df: pd.DataFrame, a_threshold: float, rest_max: float | None = None) -> dict:
    a = df[df["human_a"] == 1]
    n = len(a)
    rest = float(df["ttmn_rest_max"].iloc[0]) if rest_max is None else rest_max
    over = int((a["muscle_drive"] >= a_threshold).sum())
    above = int((a["ttmn_hz"] > rest).sum())
    return {"a_frames": n, "muscle_over": over, "muscle_over_fraction": over / n if n else float("nan"),
            "ttmn_above_rest": above, "ttmn_above_rest_fraction": above / n if n else float("nan"),
            "a_threshold": a_threshold, "ttmn_rest_max": rest}


def q2(df: pd.DataFrame) -> dict:
    spikes_n = hit_press = hit_held = 0
    for d in _runs(df):
        spikes = np.flatnonzero(d["gf_spike"].to_numpy() == 1)
        held = d["human_a"].to_numpy() == 1
        presses = rising_edges(held)
        for s in spikes:
            spikes_n += 1
            hit_press += bool(len(presses) and np.abs(presses - s).min() <= Q2_WINDOW)
            lo, hi = max(0, s - Q2_WINDOW), s + Q2_WINDOW + 1
            hit_held += bool(held[lo:hi].any())
    f = lambda k: k / spikes_n if spikes_n else float("nan")
    return {"gf_spike_frames": spikes_n, "with_press": hit_press, "with_press_fraction": f(hit_press),
            "with_a_held": hit_held, "with_a_held_fraction": f(hit_held), "window": Q2_WINDOW}


def q3(df: pd.DataFrame, walk_threshold: float) -> dict:
    r = df[df["human_right"] == 1]
    n = len(r)
    over = int((r["dnp09_hz"] > walk_threshold).sum())
    return {"right_frames": n, "dnp09_over": over, "dnp09_over_fraction": over / n if n else float("nan"),
            "walk_threshold": walk_threshold}


def _histogram(offsets: np.ndarray) -> list[tuple[str, int]]:
    edges = list(range(-Q4_WINDOW, Q4_WINDOW + 1, Q4_BIN))
    present = offsets[~np.isnan(offsets)]
    rows = []
    for lo in edges[:-1]:
        hi = lo + Q4_BIN
        last = hi == edges[-1]
        rows.append((f"[{lo:+d},{hi:+d}{']' if last else ')'}", int(((present >= lo) & ((present <= hi) if last else (present < hi))).sum())))
    return rows


def _offset_summary(offsets: np.ndarray) -> dict:
    n = len(offsets)
    present = offsets[~np.isnan(offsets)]
    absent = n - len(present)
    abs_all = np.where(np.isnan(offsets), np.inf, np.abs(offsets))
    return {"n": n, "absent": int(absent), "absent_fraction": absent / n if n else float("nan"),
            "early": int((present < 0).sum()), "coincident": int((present == 0).sum()), "late": int((present > 0).sum()),
            "median_offset_present": float(np.median(present)) if len(present) else float("nan"),
            "median_abs_offset": float(np.median(abs_all)) if n else float("nan"),     # absent = infinite
            "histogram": _histogram(offsets)}


def q4(df: pd.DataFrame) -> dict:
    press_off, frame_off = [], []
    for d in _runs(df):
        spikes = np.flatnonzero(d["gf_spike"].to_numpy() == 1)
        held = d["human_a"].to_numpy() == 1
        press_off.append(nearest_offsets(rising_edges(held), spikes, Q4_WINDOW))
        frame_off.append(nearest_offsets(np.flatnonzero(held), spikes, Q4_WINDOW))
    cat = lambda xs: np.concatenate(xs) if xs else np.array([])
    return {"per_press": _offset_summary(cat(press_off)), "per_frame": _offset_summary(cat(frame_off)), "window": Q4_WINDOW}


def decision(r1: dict, r2: dict, r4: dict) -> dict:
    """The pre-registered one read. Undefined fractions (no A presses, no spikes) are not 'present'."""
    c1 = r1["muscle_over_fraction"] >= PRESENT_FRACTION
    c2 = r2["with_press_fraction"] >= PRESENT_FRACTION
    c3 = r4["per_press"]["median_abs_offset"] <= PRESENT_MEDIAN_ABS_OFFSET
    present = bool(c1 and c2 and c3)
    return {"q1_ok": bool(c1), "q2_ok": bool(c2), "q4_ok": bool(c3), "present": present,
            "gap_in": "the motor rule (signals present at the human's decision moments)" if present
            else "the brain (signals absent at the human's decision moments)"}


# ---- segments -----------------------------------------------------------------------------------------------------
def segment_summaries(df: pd.DataFrame) -> list[dict]:
    out = []
    for name, x in SEGMENTS.items():
        for d in _runs(df):
            hit = np.flatnonzero(d["mario_x"].to_numpy() >= x)
            label = str(d["label"].iloc[0])
            if len(hit) == 0:
                out.append({"segment": name, "label": label, "reached": False})
                continue
            c = int(hit[0])
            lo, hi = max(0, c - SEG_BEFORE), min(len(d), c + SEG_AFTER + 1)
            w = d.iloc[lo:hi].reset_index(drop=True)
            presses = rising_edges(w["human_a"].to_numpy() == 1) + lo - c
            fly_a = rising_edges(w["fly_a"].to_numpy() == 1) + lo - c
            spikes = np.flatnonzero(w["gf_spike"].to_numpy() == 1) + lo - c
            nan_min = lambda s: float(s.min()) if s.notna().any() else float("nan")
            out.append({"segment": name, "label": label, "reached": True, "cross_frame": int(d["frame"].iloc[c]),
                        "window": [lo - c, hi - 1 - c], "max_theta_deg": float(np.degrees(w["theta"].max())),
                        "max_obst_theta_deg": float(np.degrees(w["obst_theta"].max())), "min_obst_d_px": nan_min(w["obst_d_px"]),
                        "max_gf_hz": float(max(w["gf_l_hz"].max(), w["gf_r_hz"].max())), "gf_spike_frames": [int(s) for s in spikes],
                        "max_muscle_drive": float(w["muscle_drive"].max()), "human_a_presses": [int(p) for p in presses],
                        "fly_a_rising_edges": [int(p) for p in fly_a], "max_dnp09_hz": float(w["dnp09_hz"].max()),
                        "trace": w.iloc[::SEG_TRACE_STEP].assign(off=lambda t: t.index + lo - c)[
                            ["off", "mario_x", "theta", "obst_theta", "obst_d_px", "gf_l_hz", "gf_r_hz", "muscle_drive", "human_a",
                             "human_right", "fly_a"]]})
    return out


# ---- markdown -----------------------------------------------------------------------------------------------------
def _pct(x: float) -> str:
    return "n/a" if x != x else f"{100 * x:.1f}%"


def analyse(df: pd.DataFrame, a_threshold: float | None = None, walk_threshold: float | None = None, rest_max: float | None = None) -> dict:
    a_thr, walk_thr = thresholds() if a_threshold is None or walk_threshold is None else (a_threshold, walk_threshold)
    r1, r2, r3, r4 = q1(df, a_thr, rest_max), q2(df), q3(df, walk_thr), q4(df)
    return {"q1": r1, "q2": r2, "q3": r3, "q4": r4, "decision": decision(r1, r2, r4), "segments": segment_summaries(df)}


def format_markdown(res: dict, labels: list[str]) -> str:
    q1_, q2_, q3_, q4_, dec = res["q1"], res["q2"], res["q3"], res["q4"], res["decision"]
    pp, pf = q4_["per_press"], q4_["per_frame"]
    L = ["# RESULTS: shadow mode (human play vs the fly's signals)", "",
         f"Runs: {', '.join(labels)}. Pre-registered in docs/SPEC_shadow.md; the fly controlled nothing. Open loop, one human.", "",
         "## Q1. Human A frames: was the fly's jump drive there?",
         f"- A-held frames: {q1_['a_frames']}",
         f"- muscle drive >= a_threshold ({q1_['a_threshold']:.4f}): {q1_['muscle_over']} ({_pct(q1_['muscle_over_fraction'])})",
         f"- TTMn above its resting range (max over the rest run {q1_['ttmn_rest_max']:.5f}): {q1_['ttmn_above_rest']} ({_pct(q1_['ttmn_above_rest_fraction'])})", "",
         "## Q2. GF spike frames: was a human A press near?",
         f"- GF spike frames: {q2_['gf_spike_frames']}",
         f"- with an A press (rising edge) within +-{q2_['window']} frames: {q2_['with_press']} ({_pct(q2_['with_press_fraction'])})",
         f"- (secondary) with A held on any frame within +-{q2_['window']}: {q2_['with_a_held']} ({_pct(q2_['with_a_held_fraction'])})", "",
         "## Q3. Human Right frames: was the walk drive on?",
         f"- Right-held frames: {q3_['right_frames']}",
         f"- DNp09 > walk_threshold ({q3_['walk_threshold']:.5f}): {q3_['dnp09_over']} ({_pct(q3_['dnp09_over_fraction'])})", "",
         "## Q4. Offset from each human A press to the nearest GF spike (negative = fly early)",
         f"- presses: {pp['n']}; early {pp['early']}, coincident {pp['coincident']}, late {pp['late']}, "
         f"no spike within +-{q4_['window']}: {pp['absent']} ({_pct(pp['absent_fraction'])})",
         f"- median offset (presses with a spike): {pp['median_offset_present']:.1f}; median |offset| (absent = infinite): {pp['median_abs_offset']:.1f}",
         f"- per A frame: n {pf['n']}, early {pf['early']}, coincident {pf['coincident']}, late {pf['late']}, absent {pf['absent']} ({_pct(pf['absent_fraction'])}), "
         f"median offset {pf['median_offset_present']:.1f}", "", "| offset (frames) | presses |", "|---|---|"]
    L += [f"| {b} | {n} |" for b, n in pp["histogram"]]
    L += ["", "## The one read (criterion fixed in the SPEC)",
          f"present = Q1 muscle-drive >= {PRESENT_FRACTION:.0%} [{'yes' if dec['q1_ok'] else 'no'}] AND Q2 >= {PRESENT_FRACTION:.0%} "
          f"[{'yes' if dec['q2_ok'] else 'no'}] AND Q4 median |offset| <= {PRESENT_MEDIAN_ABS_OFFSET} [{'yes' if dec['q4_ok'] else 'no'}].",
          f"**Signals present: {'YES' if dec['present'] else 'NO'}. The gap is in {dec['gap_in']}.** No fixes follow from this document.", "",
          "## Segments (what the fly saw while the human crossed)"]
    for s in res["segments"]:
        if not s["reached"]:
            L.append(f"- {s['segment']} ({s['label']}): not reached")
            continue
        L += ["", f"### {s['segment']} ({s['label']}), crossing at frame {s['cross_frame']}, window {s['window'][0]:+d}..{s['window'][1]:+d}",
              f"- max enemy theta {s['max_theta_deg']:.1f} deg, max obstacle theta {s['max_obst_theta_deg']:.1f} deg, min obstacle d {s['min_obst_d_px']:.1f} px",
              f"- max GF {s['max_gf_hz']:.2f} Hz; GF spike frames (offset from crossing): {s['gf_spike_frames']}; max muscle drive {s['max_muscle_drive']:.3f}; max DNp09 {s['max_dnp09_hz']:.4f} Hz",
              f"- human A presses (offset): {s['human_a_presses']}; fly would-be A rising edges: {s['fly_a_rising_edges']}", "",
              "| off | x | theta | obst theta | obst d | GF L | GF R | drive | human A | human R | fly A |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for _, t in s["trace"].iterrows():
            L.append(f"| {int(t.off)} | {int(t.mario_x)} | {np.degrees(t.theta):.1f} | {np.degrees(t.obst_theta):.1f} | {t.obst_d_px:.0f} | "
                     f"{t.gf_l_hz:.2f} | {t.gf_r_hz:.2f} | {t.muscle_drive:.3f} | {int(t.human_a)} | {int(t.human_right)} | {int(t.fly_a)} |")
    return "\n".join(L) + "\n"


def write_results(csv_paths, out_path, a_threshold: float | None = None, walk_threshold: float | None = None) -> dict:
    """Analyse the CSVs and write the markdown to `out_path`. Returns the result dict."""
    df = load_runs(csv_paths)
    res = analyse(df, a_threshold, walk_threshold)
    labels = [f"{df[df['run'] == i]['label'].iloc[0]} ({Path(p).name}, {int((df['run'] == i).sum())} frames)" for i, p in enumerate(csv_paths)]
    Path(out_path).write_text(format_markdown(res, labels), encoding="utf-8")
    return res


def main(argv=None) -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Q1-Q4 and the decision read from shadow-mode CSVs (docs/SPEC_shadow.md)")
    ap.add_argument("csv", nargs="+")
    ap.add_argument("--out", default="docs/RESULTS_shadow.md")
    args = ap.parse_args(argv)
    res = write_results(args.csv, args.out)
    print(json.dumps({k: res[k] for k in ("q1", "q2", "q3", "decision")}, indent=1, default=str))


if __name__ == "__main__":
    main()
