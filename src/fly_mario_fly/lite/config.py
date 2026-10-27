"""Limits and paths of the lite server. Every value has a default and an env var (FMF_LITE_*)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default, cast=str):
    v = os.environ.get(f"FMF_LITE_{name}")
    return default if v is None else cast(v)


@dataclass(frozen=True)
class LiteConfig:
    bundle_dir: Path = Path("bundle")        # what `python -m fly_mario_fly.lite.bundle` wrote
    cache_dir: Path = Path("cache")          # finished videos
    cache_max_bytes: int = 300 * 2**20       # the cache never grows past this (oldest-used videos go first)
    workers: int = 1                         # runs at the same time (each is one CPU core)
    queue_max: int = 12                      # waiting + running; more is refused with 503
    rate_per_minute: int = 6                 # new (uncached) runs per client per minute
    max_frames: int = 3600                   # game frames of one run (60 s of play); the request's own max is cut to this
    max_start_x: int = 4000
    stride: int = 4                          # every 4th game frame goes in the video: 15 fps
    crf: int = 30                            # H.264 quality (higher = smaller file)
    scale: int = 2                           # NES x2 = 512 x 480
    wall_budget_s: float = 90.0              # a run that takes longer is stopped and reported as a failure
    keep_brains: int = 2                     # brains held in memory per worker
    levels: tuple = ("1-1", "1-2")           # levels this server offers (the bundle must have them)
    modifiers: tuple = ("no_enemies", "whole_level")
    cors_origins: tuple = ("http://localhost:5173", "http://127.0.0.1:5173")
    trust_proxy: bool = False                # read the client address from X-Forwarded-For (behind Fly.io / Cloud Run)
    seed: int = 101
    noop: int = 3
    panels_dir: str = ""                     # worker side only: set from the bundle by worker_json
    version: str = ""                        # set from the bundle at start (see bundle.read_version)

    def worker_json(self) -> str:
        """The few values a worker process needs to play and draw a run (what `engine.render` rebuilds a config from)."""
        import json
        return json.dumps({k: getattr(self, k) for k in ("scale", "stride", "crf", "wall_budget_s", "noop", "seed")} | {"panels_dir": str(self.bundle_dir / "panels")})

    @classmethod
    def from_env(cls) -> "LiteConfig":
        d = cls()
        csv = lambda s: tuple(x.strip() for x in s.split(",") if x.strip())
        return cls(
            bundle_dir=Path(_env("BUNDLE", d.bundle_dir)), cache_dir=Path(_env("CACHE", d.cache_dir)),
            cache_max_bytes=int(_env("CACHE_MB", d.cache_max_bytes // 2**20, float) * 2**20),
            workers=_env("WORKERS", d.workers, int), queue_max=_env("QUEUE", d.queue_max, int),
            rate_per_minute=_env("RATE", d.rate_per_minute, int), max_frames=_env("MAX_FRAMES", d.max_frames, int),
            stride=_env("STRIDE", d.stride, int), crf=_env("CRF", d.crf, int), wall_budget_s=_env("BUDGET_S", d.wall_budget_s, float),
            keep_brains=_env("KEEP_BRAINS", d.keep_brains, int), levels=_env("LEVELS", d.levels, csv),
            cors_origins=_env("CORS", d.cors_origins, csv), trust_proxy=_env("TRUST_PROXY", "0") == "1")
