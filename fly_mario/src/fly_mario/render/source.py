"""Turn a recorded run (a folder under $FLY_MARIO_DATA/runs/) into the plain data the renderer draws.

A run folder keeps no frames and no per-neuron rates, so the run is replayed through the runner's public API (the
emulator and the brain are deterministic, so the replay is the recorded run; the hash in summary.json says so).
Per-group run maxima come from the saved rates.npz.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from fly_mario.contracts import Scene
from fly_mario.render import palette as P
from fly_mario.render import somata
from fly_mario.render.data import BrainData, FrameData
from fly_mario.runner import Options, Run, fly_from_dict

SMOOTH = 3          # the glow and the index use a 3-frame mean of the rates


def _smooth(series: np.ndarray) -> np.ndarray:
    cs = np.concatenate([[0.0], np.cumsum(series)])
    k = np.arange(len(series))
    lo = np.maximum(k - SMOOTH + 1, 0)
    return (cs[k + 1] - cs[lo]) / (k + 1 - lo)


def load_run(run_dir) -> Run:
    """A fresh Run (not yet played) rebuilt from the folder's config.yaml."""
    run_dir = Path(run_dir)
    cfg = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
    sc = dict(cfg["scene"])
    sc["modifiers"] = tuple((n, dict(p)) for n, p in sc.get("modifiers", ()))
    return Run(fly_from_dict(cfg["fly"]), Scene(**sc), Options(**cfg.get("options", {})), run_id=run_dir.name)


def brain_data(run: Run, run_dir) -> BrainData:
    """Soma positions, group membership, colours and run maxima for the brain this run uses."""
    brain = run.brain
    sid, sxyz = somata.all_somata()
    ids = brain.body_ids
    j = np.clip(np.searchsorted(sid, ids), 0, len(sid) - 1)
    has = sid[j] == ids
    xyz = np.full((len(ids), 3), np.nan)
    xyz[has] = sxyz[j[has]]
    if (~has).any():
        xyz[~has] = somata.terminal_positions(ids[~has])
    grouped = np.zeros(len(ids), bool)
    for m in brain.masks.values():
        grouped |= m
    rates_file = Path(run_dir) / "rates.npz"
    rmax = {}
    if rates_file.exists():
        z = np.load(rates_file)
        rmax = {g: float(_smooth(z[g]).max()) for g in z.files}
    return BrainData(
        all_xyz=sxyz, xyz={g: xyz[m] for g, m in brain.masks.items()},
        colours={g: P.COLOURS.get(g, P.OTHER) for g in brain.masks},
        other_xyz=xyz[~grouped], index=P.INDEX, rate_max=rmax, counts=brain.counts(), big=P.BIG,
        n_neurons=len(ids))


def _overlay(outputs: dict) -> list:
    return [it for out in outputs.values() for it in out.overlay]


def _scroll(run: Run) -> float:
    r = run.env.facts["ram"]
    return float(int(run.env.ram[r["screen_page"]]) * 256 + int(run.env.ram[r["screen_x"]]))


def frames(run: Run, upto: int | None = None):
    """Play the run, yielding one FrameData per frame (frame numbers count idle frames, like the recorder's).

    The game picture is the screen the senses were looking at: the one BEFORE the frame's action, so the overlay
    (computed from that screen's RAM) sits on the picture it describes."""
    run.start()
    history: dict = {g: [] for g in run.brain.masks}
    prev = None
    while not run.finished:
        scroll = _scroll(run)
        rec = run.step()
        for g, v in rec.rates.items():
            history[g].append(v)
        rates = {g: float(np.mean(h[-SMOOTH:])) for g, h in history.items()}
        yield FrameData(game=prev if prev is not None else rec.screen, overlay=_overlay(rec.outputs), rates=rates,
                        scroll_x=scroll, frame=rec.frame)
        prev = rec.screen
        if upto is not None and rec.frame >= upto:
            return


def still_frame(run: Run, frame: int) -> FrameData:
    fd = None
    for fd in frames(run, upto=frame):
        pass
    assert fd is not None and fd.frame == frame, f"the run ends at frame {fd.frame if fd else 0}, before frame {frame}"
    return fd


def check_hash(run: Run, run_dir) -> bool:
    """True if the replay reproduced the recorded trajectory."""
    want = json.loads((Path(run_dir) / "summary.json").read_text(encoding="utf-8"))["hash"]
    return run.result().hash == want
