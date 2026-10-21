"""The FastAPI app. create_app() takes the folders it writes to so tests can point them at a scratch dir."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import TypeAdapter

from fly_mario import registry
from fly_mario.runner import dump_fly, load_fly, validate
from fly_mario.runner.config import FLIES
from fly_mario.runner.levels import level_thumbnail
from fly_mario.runner.record import runs_dir
from fly_mario.api import convert as V
from fly_mario.api import layers
from fly_mario.api import ports
from fly_mario.api import schemas as S
from fly_mario.api.jobs import Jobs
from fly_mario.api.live import Runs
from fly_mario.api.videos import Videos

OPENAPI_PATH = Path(__file__).with_name("openapi.json")
NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def create_app(flies_dir: Optional[Path] = None, runs_folder: Optional[Path] = None) -> FastAPI:
    flies = Path(flies_dir) if flies_dir else FLIES
    runs = Runs(Path(runs_folder) if runs_folder else runs_dir())
    jobs = Jobs(runs.dir, flies)
    videos = Videos(runs.dir)
    app = FastAPI(title="fly_mario", version="0.0.1")
    app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(KeyError)
    async def _unknown(_: Request, e: KeyError):                 # an unknown moment (or level) id from the runner
        return JSONResponse({"detail": e.args[0] if e.args else "not found"}, status_code=404)

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

    def write_fly(dto: S.FlyDTO) -> S.FlyView:
        if not NAME.match(dto.name):
            raise HTTPException(422, "fly name: letters, digits, _ and - only")
        fly = check_fly(dto)
        flies.mkdir(parents=True, exist_ok=True)
        (flies / f"{dto.name}.yaml").write_text(dump_fly(fly), encoding="utf-8")
        return V.fly_to_view(load_fly(flies / f"{dto.name}.yaml"))

    # ---- registry and levels ----------------------------------------------------------------------------------
    @app.get("/registry", response_model=S.RegistryInfo)
    def get_registry():
        return V.registry_info(ports.level_catalogue(runs.dir), fly_names())

    @app.get("/levels", response_model=list[S.LevelInfo])
    def get_levels():
        return ports.level_catalogue(runs.dir)

    @app.get("/levels/{level_id}", response_model=S.LevelInfo)
    def get_level(level_id: str):
        return ports.level_info(level_id, runs.dir)

    @app.get("/levels/{level_id}/thumbnail.png", responses={200: {"content": {"image/png": {}}}})
    def get_level_thumbnail(level_id: str):
        """The level's opening screen (256 x 208 PNG); made with the emulator the first time, then cached."""
        return Response(level_thumbnail(level_id), media_type="image/png", headers={"Cache-Control": "max-age=86400"})

    # ---- flies ------------------------------------------------------------------------------------------------
    @app.get("/flies", response_model=list[S.FlySummary])
    def list_flies():
        return [V.fly_summary(read_fly(n)) for n in fly_names()]

    @app.get("/flies/presets", response_model=list[S.FlyView])
    def fly_presets():
        return [V.fly_to_view(read_fly(n)) for n in fly_names()]

    @app.post("/brain-map.png", responses={200: {"content": {"image/png": {}}}})
    def brain_map(dto: S.FlyDTO):
        """The brain and nerve cord with the neuron groups this fly uses lit: the Fly page's mini map."""
        return Response(layers.brain_map_png(check_fly(dto)), media_type="image/png")

    @app.get("/flies/{name}", response_model=S.FlyView)
    def get_fly(name: str):
        return V.fly_to_view(read_fly(name))

    @app.post("/flies", response_model=S.FlyView, status_code=201)
    def create_fly(dto: S.FlyDTO):
        if NAME.match(dto.name) and (flies / f"{dto.name}.yaml").exists():
            raise HTTPException(409, f"a fly named {dto.name!r} already exists; PUT to replace it")
        return write_fly(dto)

    @app.put("/flies/{name}", response_model=S.FlyView)
    def put_fly(name: str, dto: S.FlyDTO):
        if dto.name != name:
            raise HTTPException(422, "the name in the body must match the name in the path")
        read_fly(name)
        return write_fly(dto)

    # ---- runs -------------------------------------------------------------------------------------------------
    @app.post("/runs", response_model=S.RunSummary, status_code=201)
    def start_run(req: S.RunRequestDTO):
        fly = check_fly(req.fly)
        if req.scene.level_id not in {lv.id for lv in ports.level_catalogue(runs.dir)}:
            raise HTTPException(422, f"unknown level {req.scene.level_id!r}")
        known = registry.list_plugins("scenes")
        bad = [n for n, _ in req.scene.modifiers if n not in known]
        if bad:
            raise HTTPException(422, f"unknown scene modifier(s) {bad}")
        if req.from_moment is not None:
            moment = ports.get_moment(req.from_moment)             # unknown id -> 404
            if (moment.scene.level_id, moment.scene.rom) != (req.scene.level_id, req.scene.rom):
                raise HTTPException(422, f"moment {req.from_moment!r} is on {moment.scene.level_id}, "
                                         f"not {req.scene.level_id}")
        live = runs.create(V.with_dials(fly, req.dials), V.dto_to_scene(req.scene), req.from_moment)
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
        if run_id not in runs.live and not (runs.dir / run_id).exists() and not ports.list_moments(run_id):
            raise HTTPException(404, f"no run {run_id!r}")
        return ports.list_moments(run_id)

    @app.post("/runs/{run_id}/moments", response_model=S.MomentSummary, status_code=201)
    async def save_moment(run_id: str, body: S.MomentSave = S.MomentSave()):
        live = runs.live.get(run_id)
        if live is None:
            raise HTTPException(404, f"no run {run_id!r} on this server")
        try:
            return await runs.save_moment(live, body.name, body.frame)
        except LookupError as e:
            raise HTTPException(409, str(e))
        except ValueError as e:
            raise HTTPException(422, str(e))

    # ---- moments ----------------------------------------------------------------------------------------------
    @app.get("/moments/{moment_id}", response_model=S.MomentSummary)
    def get_moment(moment_id: str):
        return ports.get_moment(moment_id)

    @app.patch("/moments/{moment_id}", response_model=S.MomentSummary)
    def rename_moment(moment_id: str, body: S.MomentRename):
        return ports.rename_moment(moment_id, body.name)

    @app.delete("/moments/{moment_id}", status_code=204)
    def delete_moment(moment_id: str):
        ports.delete_moment(moment_id)

    @app.get("/moments/{moment_id}/tries", response_model=list[S.TryDTO])
    def moment_tries(moment_id: str):
        return ports.tries_from(moment_id)

    # ---- background jobs: evolution and "test this fly" -------------------------------------------------------
    def start_job(kind: str, req, **kw) -> S.JobCreated:
        fly = check_fly(req.fly)
        try:
            return S.JobCreated(id=jobs.create(kind, fly, req.level, req.dials, workers=req.workers, **kw))
        except ValueError as e:
            raise HTTPException(422, str(e))

    @app.post("/jobs/evolve", response_model=S.JobCreated, status_code=201)
    def start_evolve(req: S.EvolveRequest):
        if req.start != "level_start":
            moment = ports.get_moment(req.start)                       # unknown id -> 404
            if moment.scene.level_id != req.level:
                raise HTTPException(422, f"moment {req.start!r} is on {moment.scene.level_id}, not {req.level}")
        return start_job("evolve", req, generations=req.generations, start=req.start, seed=req.seed, pop=req.population,
                         train_n=req.train_n, flag_x=req.flag_x)

    @app.post("/jobs/test", response_model=S.JobCreated, status_code=201)
    def start_test(req: S.TestJobRequest):
        return start_job("test", req)

    @app.get("/jobs", response_model=list[S.JobSummary])
    def list_jobs():
        return jobs.list()

    @app.get("/jobs/{job_id}", response_model=S.JobDetail)
    def get_job(job_id: str):
        d = jobs.detail(job_id)
        if d is None:
            raise HTTPException(404, f"no job {job_id!r}")
        return d

    @app.post("/jobs/{job_id}/cancel", response_model=S.JobDetail)
    def cancel_job(job_id: str):
        if not jobs.cancel(job_id):
            raise HTTPException(404, f"no job {job_id!r}")
        return jobs.detail(job_id)

    @app.get("/jobs/{job_id}/generations/{gen}/fly", response_model=S.FlyDTO)
    def generation_fly(job_id: str, gen: int):
        """The best fly of one generation (-1 = the fly evolution started from): start a run with it to watch it."""
        fly = jobs.generation_fly(job_id, gen)
        if fly is None:
            raise HTTPException(404, f"job {job_id!r} has no generation {gen}")
        return fly

    @app.post("/jobs/{job_id}/use", response_model=S.FlyView, status_code=201)
    def use_evolved_fly(job_id: str, body: S.UseFly = S.UseFly()):
        """"Use this fly": save the evolution's best fly as a new fly yaml, with where it came from."""
        if body.name and not NAME.match(body.name):
            raise HTTPException(422, "fly name: letters, digits, _ and - only")
        try:
            name = jobs.use(job_id, body.name)
        except FileExistsError as e:
            raise HTTPException(409, str(e))
        if name is None:
            raise HTTPException(404, f"job {job_id!r} has no evolved fly (yet)")
        return V.fly_to_view(read_fly(name))

    # ---- video exports: clips for editing (stills first, the mp4 only when asked for) ------------------------------
    @app.post("/videos", response_model=S.VideoSummary, status_code=201)
    def start_video(req: S.VideoRequest):
        """Ask for an export: its 2-3 preview stills are made in the background; render the mp4 with /render."""
        try:
            return videos.detail(videos.create(req))
        except ValueError as e:
            raise HTTPException(422, str(e))

    @app.get("/videos", response_model=list[S.VideoSummary])
    def list_videos():
        return videos.list()

    @app.get("/videos/{video_id}", response_model=S.VideoSummary)
    def get_video(video_id: str):
        d = videos.detail(video_id)
        if d is None:
            raise HTTPException(404, f"no video export {video_id!r}")
        return d

    @app.post("/videos/{video_id}/render", response_model=S.VideoSummary)
    def render_video(video_id: str):
        """The user looked at the stills and wants the mp4."""
        try:
            if not videos.render(video_id):
                raise HTTPException(404, f"no video export {video_id!r}")
        except RuntimeError as e:
            raise HTTPException(409, str(e))
        return videos.detail(video_id)

    @app.post("/videos/{video_id}/cancel", response_model=S.VideoSummary)
    def cancel_video(video_id: str):
        if not videos.cancel(video_id):
            raise HTTPException(404, f"no video export {video_id!r}")
        return videos.detail(video_id)

    @app.get("/videos/{video_id}/stills/{n}.png", responses={200: {"content": {"image/png": {}}}})
    def video_still(video_id: str, n: int):
        p = videos.still_path(video_id, n)
        if p is None:
            raise HTTPException(404, "no such still")
        return FileResponse(p, media_type="image/png")

    @app.get("/videos/{video_id}/video.mp4", responses={200: {"content": {"video/mp4": {}}}})
    def video_file(video_id: str, download: bool = False):
        p = videos.video_path(video_id)
        if p is None:
            raise HTTPException(404, "this export has no mp4 yet")
        return FileResponse(p, media_type="video/mp4", filename=f"{video_id}.mp4",
                            content_disposition_type="attachment" if download else "inline")

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
