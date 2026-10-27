"""One run -> one mp4. This is what a worker process does; it has no web code and keeps no state but the loaded brains.

The run is the full tool's `runner.Run`, step for step, so the buttons (and the run hash) are exactly those of the full tool.
Only every `stride`-th frame is drawn and encoded. The emulator, the senses and the brain still run every frame.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from fly_mario_fly.lite.config import LiteConfig

FPS = 60


class OverBudget(RuntimeError):
    """The run took more wall-clock time than the server allows."""


def init_worker(bundle_dir: str, keep_brains: int) -> None:
    """Run once per worker process: make the runner load brains from the bundle (never build them), at most `keep_brains` at a time."""
    from fly_mario_fly.runner import brainstore
    brainstore.install(Path(bundle_dir) / "brains", keep=keep_brains)


def render(settings_json: str, out_path: str, progress_path: str, cfg_json: str) -> dict:
    """Play the settings, write the mp4 to `out_path`, return the summary. `progress_path` gets the frame count now and then."""
    from fly_mario_fly.api import convert as V
    from fly_mario_fly.api import schemas as S
    from fly_mario_fly.lite import drawing
    from fly_mario_fly.lite.encode import Encoder
    from fly_mario_fly.lite.settings import Settings
    from fly_mario_fly.runner import Run, Options

    cfg = LiteConfig(**json.loads(cfg_json))
    raw = json.loads(settings_json)
    st = Settings(fly=raw["fly"], dials=raw["dials"], level_id=raw["level"], modifiers=tuple((n, dict(p)) for n, p in raw["mods"]),
                  max_frames=raw["max_frames"])
    fly = V.with_dials(V.dto_to_fly(S.FlyDTO(**st.fly)), st.dials)
    t0 = time.perf_counter()
    run = Run(fly, st.scene(cfg), Options())
    enc = None
    try:
        groups = sorted({g for a in run.actions for g in a.source_groups})
        enc = Encoder(out_path, drawing.frame_size(cfg.scale), FPS // cfg.stride, cfg.crf)
        while not run.finished:
            rec = run.step()
            if rec.frame % cfg.stride == 0 or rec.done:
                enc.write(drawing.draw(rec, cfg.scale, groups))
            if rec.frame % 120 == 0:
                Path(progress_path).write_text(str(rec.frame), encoding="utf-8")
                if time.perf_counter() - t0 > cfg.wall_budget_s:
                    raise OverBudget(f"the run took longer than {cfg.wall_budget_s:.0f} s")
        res = V.result_to_dto(run.result()).model_dump()
    finally:
        if enc is not None:
            enc.close()
        run.close()
    wall = time.perf_counter() - t0
    return {"result": res, "video_frames": enc.frames, "fps": FPS // cfg.stride, "wall_s": round(wall, 2),
            "video_bytes": Path(out_path).stat().st_size, "settings": raw}


class ProcessEngine:
    """The production engine: runs `render` in a worker process (spawned, so the emulator's state never leaks between runs and a crash
    in it cannot take the web server down). Brains stay loaded in the worker between runs. Call it from a thread."""

    def __init__(self, cfg: LiteConfig):
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor
        self.pool = ProcessPoolExecutor(max_workers=cfg.workers, mp_context=mp.get_context("spawn"),
                                        initializer=init_worker, initargs=(str(cfg.bundle_dir), cfg.keep_brains))

    def __call__(self, settings_json: str, out_path: str, progress_path: str, cfg_json: str) -> dict:
        return self.pool.submit(render, settings_json, out_path, progress_path, cfg_json).result()

    def shutdown(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)
