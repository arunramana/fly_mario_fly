# What this file does, in plain English:
# Reads the per-frame log (telemetry) of a finished run_steering.py game and
# finds every pit (a gap in the ground) Mario came up to. For each one it
# reports the gap's width, how often the jump-trigger neuron fired on the
# approach, whether a hop or the long jump was used, and whether Mario got
# across or died. Used by run_steering.py's run 008; it changes no game.
"""
pit_report.py -- SPEC_odour.md section 3: does the long jump generalise?

007 cleared one real 2-tile pit, once, on 1-1. This post-processes a
run_steering.py telemetry DataFrame (which already logs `gap` -- SPEC_
terrain.md's `tile_ram.gap_width(ram)` every frame) to find every pit
actually encountered and report, per pit: gap width, DNp01 spike rate
during the approach, whether DLMn crossed threshold, hop vs long jump,
cleared vs died. Pure telemetry analysis -- no simulation changes.

    from sim.pit_report import find_pit_events, summarize
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CLEAR_MARGIN_PX = 16          # extra px of forward progress beyond the gap's
                               # far edge required to call it "cleared"
CLEAR_WINDOW_FRAMES = 90      # how long after a pit ends to look for that
                               # progress (or a death) before giving up


def find_pit_events(tel: pd.DataFrame) -> list[dict]:
    """A pit event is a maximal run of consecutive frames with gap > 0.
    Returns one dict per event with the raw frame range and peak gap width;
    `summarize` fills in the rest."""
    gap = tel["gap"].to_numpy()
    in_pit = gap > 0
    events = []
    i = 0
    n = len(gap)
    while i < n:
        if in_pit[i]:
            start = i
            while i < n and in_pit[i]:
                i += 1
            end = i - 1  # inclusive
            events.append({
                "start_frame": int(tel["frame"].iloc[start]),
                "end_frame": int(tel["frame"].iloc[end]),
                "start_idx": start,
                "end_idx": end,
                "gap_width_tiles": int(gap[start:end + 1].max()),
            })
        else:
            i += 1
    return events


def summarize(tel: pd.DataFrame, events: list[dict], died_or_flagged: bool,
              final_frame: int) -> list[dict]:
    """Fill in DNp01 spike rate, DLMn recruitment, hop-vs-long-jump, and
    cleared-vs-died for each event found by `find_pit_events`."""
    mario_x = tel["mario_x"].to_numpy()
    spike = tel["spike"].to_numpy()
    dlmn = tel["dlmn"].to_numpy() if "dlmn" in tel.columns else None
    long_jump = tel["long_jump"].to_numpy() if "long_jump" in tel.columns else None
    n = len(tel)

    out = []
    for ev in events:
        s, e = ev["start_idx"], ev["end_idx"]
        approach_lo = max(0, s - 20)  # a short look-back window before the
                                       # gap itself, since the escape/takeoff
                                       # trigger fires from GAP_GAIN current
                                       # that starts as soon as gap_width>0,
                                       # i.e. essentially at s -- the
                                       # look-back just catches a jump that
                                       # started a frame or two early.
        spike_rate = float(spike[approach_lo:e + 1].mean())
        dlmn_peak = float(dlmn[approach_lo:min(e + 30, n)].max()) if dlmn is not None else float("nan")
        dlmn_crossed = bool(dlmn_peak >= 1.0) if dlmn is not None else None
        window_hi = min(e + CLEAR_WINDOW_FRAMES, n)
        did_long_jump = bool(long_jump[s:window_hi].any()) if long_jump is not None else None
        did_hop = bool(spike[approach_lo:e + 1].any()) and not did_long_jump

        far_edge_x = mario_x[e] + ev["gap_width_tiles"] * 16
        cleared = bool(np.any(mario_x[e:window_hi] >= far_edge_x + CLEAR_MARGIN_PX))
        # died specifically near this pit: episode ended within the look-ahead
        # window and no clearance was seen
        died_here = (not cleared) and died_or_flagged and (window_hi >= final_frame)

        out.append({
            **ev,
            "spike_rate": spike_rate,
            "dlmn_peak": dlmn_peak,
            "dlmn_crossed": dlmn_crossed,
            "used_long_jump": did_long_jump,
            "used_hop": did_hop,
            "cleared": cleared,
            "died_here": died_here,
        })
    return out


def print_table(level: str, rows: list[dict]):
    if not rows:
        print(f"  {level}: no pits encountered this run.")
        return
    print(f"  {level}: {len(rows)} pit(s) encountered")
    for i, r in enumerate(rows):
        outcome = "CLEARED" if r["cleared"] else ("DIED" if r["died_here"] else "UNRESOLVED (ran out of frames)")
        jump_kind = "long jump" if r["used_long_jump"] else ("hop" if r["used_hop"] else "no jump seen")
        print(f"    #{i+1} frame {r['start_frame']}-{r['end_frame']}  "
              f"gap_width={r['gap_width_tiles']} tiles  "
              f"spike_rate={r['spike_rate']:.2f}  "
              f"DLMn_peak={r['dlmn_peak']:.2f} (crossed={r['dlmn_crossed']})  "
              f"{jump_kind}  -> {outcome}")
