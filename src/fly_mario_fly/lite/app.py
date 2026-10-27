"""The lite HTTP API. Same shapes as the full tool's for what they share (registry, levels, flies, the run request), so the same web
app talks to either. A run is `POST /runs` -> poll `GET /runs/{id}` -> `GET /videos/{id}.mp4`.

The ids are cache keys: asking for the same settings again gives the same id, and the video is served with
`Cache-Control: immutable`, so a CDN in front of this server answers repeated views without touching it.
"""
from __future__ import annotations

import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from fly_mario_fly.api import schemas as S
from fly_mario_fly.lite import bundle
from fly_mario_fly.lite.cache import DiskCache
from fly_mario_fly.lite.config import LiteConfig
from fly_mario_fly.lite.jobs import Jobs, QueueFull, RateLimited
from fly_mario_fly.lite.settings import Refused, canonicalize

IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}
DAY = {"Cache-Control": "public, max-age=86400"}
SAFE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def create_lite_app(cfg: LiteConfig, engine=None, pool=None) -> FastAPI:
    """`engine` and `pool` are injectable so tests can run the whole API with a fake engine and no data."""
    from concurrent.futures import ThreadPoolExecutor
    cfg = bundle.with_version(cfg)
    cache = DiskCache(cfg.cache_dir, cfg.cache_max_bytes)
    own_engine = engine is None
    if own_engine:
        from fly_mario_fly.lite.engine import ProcessEngine
        engine = ProcessEngine(cfg)
    pool = pool or ThreadPoolExecutor(max_workers=cfg.workers, thread_name_prefix="lite-run")
    jobs = Jobs(cfg, cache, pool, engine)
    files = bundle.Files(cfg.bundle_dir)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        pool.shutdown(wait=False, cancel_futures=True)
        if own_engine:
            engine.shutdown()

    app = FastAPI(title="fly_mario_fly lite", version=cfg.version, docs_url=None, redoc_url=None, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(cfg.cors_origins), allow_methods=["GET", "POST"], allow_headers=["*"])
    app.state.jobs, app.state.cache, app.state.cfg = jobs, cache, cfg

    def client_of(request: Request) -> str:
        if cfg.trust_proxy:
            fwd = request.headers.get("x-forwarded-for", "")
            if fwd:
                return fwd.split(",")[0].strip()
        return request.client.host if request.client else ""

    @app.get("/health")
    def health():
        return {"ok": True, "version": cfg.version, "queue": jobs.queue_depth(), "cache_bytes": cache.size(), "cache_entries": len(cache.keys())}

    # ---- what the page needs to draw its screens (static, from the bundle) -------------------------------------
    @app.get("/registry")
    def registry():
        return Response(files.read("registry.json"), media_type="application/json", headers=DAY)

    @app.get("/levels")
    def levels():
        return Response(files.read("levels.json"), media_type="application/json", headers=DAY)

    @app.get("/levels/{level_id}/thumbnail.png")
    def thumbnail(level_id: str):
        return _png(files.path("thumbs", f"{level_id}.png"))

    @app.get("/objects/{object_type}/icon.png")
    def icon(object_type: str):
        return _png(files.path("icons", f"{object_type}.png"))

    @app.get("/flies")
    def flies():
        return Response(files.read("flies.json"), media_type="application/json", headers=DAY)

    @app.get("/flies/{name}")
    def fly(name: str):
        if name != "blank":
            raise HTTPException(404, f"no fly named {name!r} on the lite server")
        return Response(files.read("fly_blank.json"), media_type="application/json", headers=DAY)

    def _png(path: Optional[Path]):
        if path is None or not path.exists():
            raise HTTPException(404, "not found")
        return FileResponse(path, media_type="image/png", headers=DAY)

    # ---- runs ---------------------------------------------------------------------------------------------------
    @app.post("/runs", status_code=202)
    def start_run(req: S.RunRequestDTO, request: Request):
        try:
            st = canonicalize(req, cfg)
        except (Refused, ValueError) as e:
            raise HTTPException(422, str(e))
        try:
            t = jobs.submit(st, client_of(request))
        except RateLimited as e:
            raise HTTPException(429, str(e), headers={"Retry-After": str(e.retry_after)})
        except QueueFull as e:
            raise HTTPException(503, str(e), headers={"Retry-After": "30"})
        return {"run_id": t.key, "status": t.status, "cached": t.cached}

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        if not SAFE.match(run_id):
            raise HTTPException(404, "no such run")
        s = jobs.status(run_id)
        if s is None:
            raise HTTPException(404, f"no run {run_id!r} (the server may have restarted: start it again)")
        out = {"run_id": run_id, **s}
        if s["status"] == "done":
            out["video_url"] = f"/videos/{run_id}.mp4"
            out["max_frames"] = s["summary"]["settings"]["max_frames"]
        return JSONResponse(out, headers={"Cache-Control": "no-store"})

    @app.get("/videos/{name}")
    def video(name: str):
        key = name.removesuffix(".mp4")
        if not name.endswith(".mp4") or not SAFE.match(key) or cache.get(key) is None:
            raise HTTPException(404, "no such video")
        return FileResponse(cache.mp4(key), media_type="video/mp4", headers=IMMUTABLE)

    return app
