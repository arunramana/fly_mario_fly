"""The FastAPI app. create_app() takes the folders it writes to so tests can point them at a scratch dir."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter

from fly_mario import registry
from fly_mario.runner import dump_fly, load_fly, validate
from fly_mario.runner.config import FLIES
from fly_mario.runner.record import runs_dir
from fly_mario.api import convert as V
from fly_mario.api import ports
from fly_mario.api import schemas as S
from fly_mario.api.live import Runs

OPENAPI_PATH = Path(__file__).with_name("openapi.json")
NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def create_app(flies_dir: Optional[Path] = None, runs_folder: Optional[Path] = None) -> FastAPI:
    flies = Path(flies_dir) if flies_dir else FLIES
    runs = Runs(Path(runs_folder) if runs_folder else runs_dir())
    app = FastAPI(title="fly_mario", version="0.0.1")
    app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(NotImplementedError)
    async def _not_yet(_: Request, e: NotImplementedError):
        return JSONResponse({"detail": str(e)}, status_code=501)

    def fly_names() -> list:
        return sorted(p.stem for p in flies.glob("*.yaml")) if flies.exists() else []

    def read_fly(name: str):
        if not NAME.match(name) or not (flies / f"{name}.yaml").exists():
            raise HTTPException(404, f"no fly named {name!r}")
        return load_fly(flies / f"{name}.yaml")

    def check_fly(dto: S.FlyDTO):
        try:
            fly = V.dto_to_fly(dto)
            validate(fly)
        except ValueError as e:
            raise HTTPException(422, str(e))
        return fly

    def write_fly(dto: S.FlyDTO) -> S.FlyDTO:
        if not NAME.match(dto.name):
            raise HTTPException(422, "fly name: letters, digits, _ and - only")
        fly = check_fly(dto)
        flies.mkdir(parents=True, exist_ok=True)
        (flies / f"{dto.name}.yaml").write_text(dump_fly(fly), encoding="utf-8")
        return V.fly_to_dto(load_fly(flies / f"{dto.name}.yaml"))

    # ---- registry and levels ----------------------------------------------------------------------------------
    @app.get("/registry", response_model=S.RegistryInfo)
    def get_registry():
        return V.registry_info(ports.level_catalogue(), fly_names())

    @app.get("/levels", response_model=list[S.LevelInfo])
    def get_levels():
        return ports.level_catalogue()

    @app.get("/levels/{level_id}", response_model=S.LevelInfo)
    def get_level(level_id: str):
        for lv in ports.level_catalogue():
            if lv["id"] == level_id:
                return lv
        raise HTTPException(404, f"no level {level_id!r}")

    # ---- flies ------------------------------------------------------------------------------------------------
    @app.get("/flies", response_model=list[S.FlySummary])
    def list_flies():
        return [V.fly_summary(read_fly(n)) for n in fly_names()]

    @app.get("/flies/presets", response_model=list[S.FlyDTO])
    def fly_presets():
        return [V.fly_to_dto(read_fly(n)) for n in fly_names()]

    @app.get("/flies/{name}", response_model=S.FlyDTO)
    def get_fly(name: str):
        return V.fly_to_dto(read_fly(name))

    @app.post("/flies", response_model=S.FlyDTO, status_code=201)
    def create_fly(dto: S.FlyDTO):
        if NAME.match(dto.name) and (flies / f"{dto.name}.yaml").exists():
            raise HTTPException(409, f"a fly named {dto.name!r} already exists; PUT to replace it")
        return write_fly(dto)

    @app.put("/flies/{name}", response_model=S.FlyDTO)
    def put_fly(name: str, dto: S.FlyDTO):
        if dto.name != name:
            raise HTTPException(422, "the name in the body must match the name in the path")
        read_fly(name)
        return write_fly(dto)

    # ---- runs -------------------------------------------------------------------------------------------------
    @app.post("/runs", response_model=S.RunSummary, status_code=201)
    def start_run(req: S.RunRequestDTO):
        fly = check_fly(req.fly)
        if req.scene.level_id not in {lv["id"] for lv in ports.level_catalogue()}:
            raise HTTPException(422, f"unknown level {req.scene.level_id!r}")
        known = registry.list_plugins("scenes")
        bad = [n for n, _ in req.scene.modifiers if n not in known]
        if bad:
            raise HTTPException(422, f"unknown scene modifier(s) {bad}")
        if req.from_moment is not None:
            ports.resume(None, req.from_moment)
        live = runs.create(fly, V.dto_to_scene(req.scene))
        return runs._summary(live)

    @app.get("/runs", response_model=list[S.RunSummary])
    def list_runs():
        return runs.summaries()

    @app.get("/runs/{run_id}", response_model=S.RunDetail)
    def get_run(run_id: str):
        d = runs.detail(run_id)
        if d is None:
            raise HTTPException(404, f"no run {run_id!r}")
        return d

    @app.get("/runs/{run_id}/moments", response_model=list[S.MomentSummary])
    def run_moments(run_id: str):
        return ports.list_moments(run_id)

    @app.websocket("/runs/{run_id}/live")
    async def live(ws: WebSocket, run_id: str):
        run = runs.live.get(run_id)
        if run is None:
            await ws.close(code=4404, reason="no such run")
            return
        await runs.stream(ws, run)

    def openapi():
        """FastAPI's schema plus the WebSocket messages, which it cannot see."""
        if app.openapi_schema is None:
            schema = FastAPI.openapi(app)
            comps = schema.setdefault("components", {}).setdefault("schemas", {})
            for name, model in (("RunEvent", S.RunEvent), ("ClientMessage", S.ClientMessage)):
                js = TypeAdapter(model).json_schema(ref_template="#/components/schemas/{model}")
                comps.update(js.pop("$defs", {}))
                comps[name] = js | {"title": name}
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi
    return app


def export_openapi(path: Path = OPENAPI_PATH) -> Path:
    path.write_text(json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
