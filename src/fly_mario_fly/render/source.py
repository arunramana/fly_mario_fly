"""Turn a recorded run (a folder under $FLY_MARIO_FLY_DATA/runs/) into the plain data the renderer draws.

A run folder keeps no frames and no per-neuron rates, so the run is replayed through the runner's public API (the
emulator and the brain are deterministic, so the replay is the recorded run; the hash in summary.json says so).
Per-group run maxima come from the saved rates.npz.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from fly_mario_fly.render import palette as P
from fly_mario_fly.render import skin
from fly_mario_fly.render.data import BrainData, FrameData
from fly_mario_fly.runner import Options, Run, brain_display, fly_from_dict

SMOOTH = 3          # the glow and the index use a 3-frame mean of the rates


def _smooth(series: np.ndarray) -> np.ndarray:
    cs = np.concatenate([[0.0], np.cumsum(series)])
    k = np.arange(len(series))
    lo = np.maximum(k - SMOOTH + 1, 0)
    return (cs[k + 1] - cs[lo]) / (k + 1 - lo)


def run_from_side(side: dict) -> Run:
    """A fresh Run from an export spec's side: {fly, scene, options, from_moment?} (plain dicts, as job.json keeps them)."""
    from fly_mario_fly.runner.record import scene_from_dict
    return Run(fly_from_dict(side["fly"]), scene_from_dict(side["scene"]), Options(**side.get("options", {})),
               run_id=side.get("run_id") or "", from_moment=side.get("from_moment"))


def rate_max_of(run: Run, steps: int | None = None) -> dict:
    """The per-group run maxima of a run that has no rates.npz: play it once (its first `steps` frames), nothing drawn."""
    run.start()
    hist: dict = {g: [] for g in run.brain.masks}
    while not run.finished and (steps is None or len(hist[next(iter(hist))]) < steps):
        for g, v in run.step().rates.items():
            hist[g].append(v)
    return {g: float(_smooth(np.asarray(v)).max()) for g, v in hist.items() if v}


def brain_data(run: Run, run_dir=None, rate_max: dict | None = None) -> BrainData:
    """Soma positions, group membership, colours and run maxima for the brain this run uses (all from brain_display).

    The maxima come from `rate_max`, else the run folder's rates.npz."""
    bd = brain_display(run.fly)
    disp = bd.display
    rmax = dict(rate_max or {})
    rates_file = Path(run_dir) / "rates.npz" if run_dir is not None else None
    if not rmax and rates_file is not None and rates_file.exists():
        z = np.load(rates_file)
        rmax = {g: float(_smooth(z[g]).max()) for g in z.files}
    return BrainData(
        all_xyz=bd.all_xyz, xyz={g: d.xyz for g, d in bd.groups.items()}, colours={g: d.rgb for g, d in bd.groups.items()},
        other_xyz=bd.other_xyz, other_colour=tuple(int(bd.other_colour[i:i + 2], 16) for i in (1, 3, 5)),
        index=[(r["label"], r["role"], list(r["groups"])) for r in disp["index"]], rate_max=rmax,
        counts={g: d.count for g, d in bd.groups.items()}, big=frozenset(disp["big"]), n_neurons=bd.n_neurons,
        placed_by_terminal=frozenset(bd.placed_by_terminal))


def _overlay(outputs: dict) -> list:
    return [it for out in outputs.values() for it in out.overlay]


def frames(run: Run):
    """Play the run, yielding one FrameData per frame (frame numbers count idle frames, like the recorder's).

    The game picture is the screen the senses were looking at: the one BEFORE the frame's action, so the overlay
    (computed from that screen's RAM) sits on the picture it describes."""
    run.start()
    history: dict = {g: [] for g in run.brain.masks}
    prev = None
    last_x = None
    use_skin = skin.enabled()
    while not run.finished:
        rec = run.step()
        for g, v in rec.rates.items():
            history[g].append(v)
        rates = {g: float(np.mean(h[-SMOOTH:])) for g, h in history.items()}
        first = prev is None                         # no earlier picture: use this frame's, with its own scroll
        m = rec.mario
        player = dict(x=m.x, y=m.y, w=m.w, h=m.h, big=m.power != "small", airborne=m.airborne, facing=m.facing,
                      moving=last_x is not None and int(m.x) != last_x)
        last_x = int(m.x)
        game = rec.screen if first else prev
        if use_skin and not first:
            game = skin.apply(game, player, rec.scroll_x, rec.frame)
        yield FrameData(game=game, player=player, overlay=_overlay(rec.outputs), rates=rates,
                        scroll_x=float(rec.scroll_x_after if first else rec.scroll_x), frame=rec.frame)
        prev = rec.screen
