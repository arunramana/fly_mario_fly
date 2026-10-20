"""Runs started over HTTP and played over a WebSocket.

POST /runs only records the request (status "pending"). The run is built and played when a client connects to
/runs/{id}/live: one frame per Run.step(), on a single worker thread per run (the emulator is not thread-safe, but a
single thread is fine). Pause / step / speed are handled here by deciding when to call step() again; the runner needs
no hook for them.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from fly_mario.contracts import FlyConfig, Scene
from fly_mario.runner import Run, new_run_id, save_run
from fly_mario.api import convert as V
from fly_mario.api import schemas as S

FPS = 60.0


@dataclass
class LiveRun:
    id: str
    fly: FlyConfig
    scene: Scene
    status: str = "pending"
    result: object = None                      # RunResult once finished
    error: str = ""


@dataclass
class Control:
    paused: bool = False
    speed: float = 1.0
    steps: int = 0
    closed: bool = False


class Runs:
    def __init__(self, runs_dir: Path):
        self.dir = Path(runs_dir)
        self.live: dict[str, LiveRun] = {}

    def create(self, fly: FlyConfig, scene: Scene) -> LiveRun:
        rid = f"{new_run_id(fly.name, scene.level_id, scene.seed)}_{uuid.uuid4().hex[:6]}"
        self.live[rid] = LiveRun(rid, fly, scene)
        return self.live[rid]

    # ---- reading ----------------------------------------------------------------------------------------------
    def summaries(self) -> list:
        out = {r.id: self._summary(r) for r in self.live.values()}
        for p in sorted(self.dir.glob("*/summary.json")) if self.dir.exists() else ():
            s = self._saved_summary(p)
            if s and s.id not in out:
                out[s.id] = s
        return list(out.values())

    def detail(self, rid: str) -> Optional[S.RunDetail]:
        if rid in self.live:
            r = self.live[rid]
            return S.RunDetail(**self._summary(r).model_dump(), scene=V.scene_to_dto(r.scene),
                               result=V.result_to_dto(r.result) if r.result else None)
        p = self.dir / rid / "summary.json"
        s = self._saved_summary(p) if p.exists() else None
        if s is None:
            return None
        return S.RunDetail(**s.model_dump(), scene=self._saved_scene(rid), result=self._saved_result(rid))

    @staticmethod
    def _summary(r: LiveRun) -> S.RunSummary:
        res = r.result
        return S.RunSummary(id=r.id, fly=r.fly.name, level_id=r.scene.level_id, status=r.status,
                            outcome=res.outcome if res else None, max_x=res.max_x if res else None,
                            score=res.score if res else None)

    @staticmethod
    def _saved_summary(p: Path) -> Optional[S.RunSummary]:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return S.RunSummary(id=d["id"], fly=d["fly"], level_id=d["level"], status="finished",
                                outcome=d["outcome"], max_x=d["max_x"], score=d["score"])
        except (OSError, ValueError, KeyError):
            return None

    def _saved_scene(self, rid: str) -> Optional[S.SceneDTO]:
        try:
            import yaml
            cfg = yaml.safe_load((self.dir / rid / "config.yaml").read_text(encoding="utf-8"))
            return S.SceneDTO(**cfg["scene"])
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _saved_result(self, rid: str) -> Optional[S.RunResultDTO]:
        scene = self._saved_scene(rid)
        try:
            d = json.loads((self.dir / rid / "summary.json").read_text(encoding="utf-8"))
            return S.RunResultDTO(id=d["id"], fly=d["fly"], scene=scene, outcome=d["outcome"], death=d.get("death"),
                                  max_x=d["max_x"], score=d["score"], blocks=d["blocks"], mushroom=d["mushroom"],
                                  counts=d.get("counts", {}), hash=d.get("hash", "")) if scene else None
        except (OSError, ValueError, KeyError):
            return None

    # ---- playing ----------------------------------------------------------------------------------------------
    async def stream(self, ws: WebSocket, live: LiveRun) -> None:
        await ws.accept()
        if live.status in ("finished", "aborted", "failed"):
            await self._finish(ws, live)
            return
        if live.status == "running":
            await ws.send_json(S.ErrorEvent(message="this run is already being streamed").model_dump())
            await ws.close()
            return
        live.status = "running"
        ctl = Control()
        reader = asyncio.create_task(self._read(ws, ctl))
        pool = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_running_loop()
        try:
            run = await loop.run_in_executor(pool, self._build, live)
            total = live.scene.max_frames
            while not run.finished and not ctl.closed:
                if ctl.paused and ctl.steps == 0:
                    await asyncio.sleep(0.02)
                    continue
                ctl.steps = max(0, ctl.steps - 1)
                t0 = time.perf_counter()
                event = await loop.run_in_executor(pool, lambda: V.frame_event(run.step(), total))
                await ws.send_json(event.model_dump())
                if 0 < ctl.speed < 100:
                    await asyncio.sleep(max(0.0, 1.0 / (FPS * ctl.speed) - (time.perf_counter() - t0)))
            if ctl.closed:
                live.status = "aborted"
                return
            live.result = run.result()
            await loop.run_in_executor(pool, lambda: save_run(run, live.result, self.dir / live.id))
            live.status = "finished"
            await self._finish(ws, live)
        except WebSocketDisconnect:
            live.status = "aborted"
        except Exception as e:                      # the run itself failed: tell the client, keep the server up
            live.status, live.error = "failed", f"{type(e).__name__}: {e}"
            try:
                await ws.send_json(S.ErrorEvent(message=live.error).model_dump())
                await ws.close()
            except Exception:
                pass
        finally:
            reader.cancel()
            pool.shutdown(wait=False)

    @staticmethod
    def _build(live: LiveRun) -> Run:
        run = Run(live.fly, live.scene, run_id=live.id)
        run.start()
        return run

    @staticmethod
    async def _finish(ws: WebSocket, live: LiveRun) -> None:
        if live.result is not None:
            await ws.send_json(S.EndEvent(result=V.result_to_dto(live.result)).model_dump())
        else:
            await ws.send_json(S.ErrorEvent(message=live.error or f"run {live.status}").model_dump())
        await ws.close()

    @staticmethod
    async def _read(ws: WebSocket, ctl: Control) -> None:
        try:
            while True:
                try:
                    msg = S.ClientMessage.model_validate(await ws.receive_json())
                except WebSocketDisconnect:
                    raise
                except Exception:
                    await ws.send_json(S.ErrorEvent(message="expected {type: play|pause|step|speed, value?}").model_dump())
                    continue
                if msg.type == "pause":
                    ctl.paused = True
                elif msg.type == "play":
                    ctl.paused = False
                elif msg.type == "step":
                    ctl.paused, ctl.steps = True, ctl.steps + 1
                elif msg.type == "speed" and msg.value is not None:
                    ctl.speed = float(msg.value)
                await ws.send_json(S.StateEvent(paused=ctl.paused, speed=ctl.speed).model_dump())
        except WebSocketDisconnect:
            ctl.closed = True
        except asyncio.CancelledError:
            raise
        except Exception:
            ctl.closed = True
