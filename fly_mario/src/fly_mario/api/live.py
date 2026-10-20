"""Runs started over HTTP and played over a WebSocket.

POST /runs only records the request (status "pending"). The run is built and played when a client connects to
/runs/{id}/live: one frame per Run.step(), on a single worker thread per run (the emulator is not thread-safe, but a
single thread is fine). Pause / step / speed are handled here by deciding when to call step() again; the runner needs
no hook for them.
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from fly_mario.contracts import FlyConfig, Scene
from fly_mario.runner import Run, new_run_id, save_moment, save_run
from fly_mario.api import convert as V
from fly_mario.api import layers as Lay
from fly_mario.api import schemas as S

FPS = 60.0
# A paced run (speed < 100) sends a picture whenever the previous one has gone out, so a slow client or machine drops
# pictures instead of falling behind; the emulator still runs every frame, at the pace the speed asks for.


def _dials_of(provenance: dict) -> str:
    return "original" if (provenance or {}).get("dials") == "original" else "tuned"


@dataclass
class LiveRun:
    id: str
    fly: FlyConfig
    scene: Scene
    parent_moment: Optional[str] = None        # resumed from this saved moment
    status: str = "pending"
    result: object = None                      # RunResult once finished
    error: str = ""
    run: Optional[Run] = None                  # the Run while it is being streamed
    pool: Optional[ThreadPoolExecutor] = None  # its one worker thread: everything that touches the emulator goes here
    brain: Optional[Lay.BrainLayer] = None     # the brain panel, rendered on its own thread
    brain_sent: int = -1                       # frame number of the newest brain picture already sent
    prev_screen: object = None                 # the screen before the latest step: what the senses of that step were looking at


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
        self.render_pool = ThreadPoolExecutor(max_workers=2)       # builds frame pictures (OpenCV / zlib let go of the GIL)

    def create(self, fly: FlyConfig, scene: Scene, from_moment: Optional[str] = None) -> LiveRun:
        rid = f"{new_run_id(fly.name, scene.level_id, scene.seed)}_{uuid.uuid4().hex[:6]}"
        self.live[rid] = LiveRun(rid, fly, scene, from_moment)
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
                               result=self._live_result(r) if r.result else None)
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
                            score=res.score if res else None, parent_moment=r.parent_moment,
                            dials=_dials_of(r.fly.provenance))

    @staticmethod
    def _saved_summary(p: Path) -> Optional[S.RunSummary]:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return S.RunSummary(id=d["id"], fly=d["fly"], level_id=d["level"], status="finished",
                                outcome=d["outcome"], max_x=d["max_x"], score=d["score"],
                                parent_moment=d.get("parent_moment"),
                                dials=Runs._saved_dials(p.parent))
        except (OSError, ValueError, KeyError):
            return None

    @staticmethod
    def _live_result(r: LiveRun) -> S.RunResultDTO:
        return V.result_to_dto(r.result).model_copy(update={"dials": _dials_of(r.fly.provenance)})

    @staticmethod
    def _saved_dials(folder: Path) -> str:
        try:
            import yaml
            cfg = yaml.safe_load((folder / "config.yaml").read_text(encoding="utf-8"))
            return _dials_of(cfg["fly"].get("provenance"))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return "tuned"

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
            return S.RunResultDTO(id=d["id"], fly=d["fly"], scene=scene, outcome=d["outcome"], death=V.death_to_dto(d.get("death")),
                                  max_x=d["max_x"], score=d["score"], blocks=d["blocks"], mushroom=d["mushroom"],
                                  counts=d.get("counts", {}), hash=d.get("hash", ""),
                                  dials=self._saved_dials(self.dir / rid)) if scene else None
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
        pool = live.pool = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_running_loop()
        try:
            run = live.run = await loop.run_in_executor(pool, self._build, live)
            total = live.scene.max_frames
            sender, deadline = None, time.perf_counter()                 # sender: the task building and sending the newest picture
            while not run.finished and not ctl.closed:
                if ctl.paused and ctl.steps == 0:
                    await asyncio.sleep(0.02)
                    deadline = time.perf_counter()
                    continue
                single = ctl.paused                     # a single step while paused is always shown
                ctl.steps = max(0, ctl.steps - 1)
                t0 = time.perf_counter()
                rec = await loop.run_in_executor(pool, run.step)
                shown, live.prev_screen = (rec.screen if live.prev_screen is None else live.prev_screen), rec.screen
                if live.brain:
                    live.brain.submit(rec.rates, rec.frame)         # every frame: the smoothing needs them all
                paced = 0 < ctl.speed < 100
                busy = sender is not None and not sender.done()
                due = single or run.finished or not paced or not busy
                if due or rec.moments:
                    if sender is not None:
                        await sender                    # pictures go out in order, and a moment never overtakes its frame
                    if due:
                        sender = asyncio.create_task(self._send_frame(ws, loop, live, rec, total, shown))
                for info in rec.moments:                # auto moments, and "3 s before death" on the last frame
                    if sender is not None:
                        await sender
                    await ws.send_json(S.MomentEvent(moment=V.moment_to_dto(info)).model_dump())
                if paced:                               # an absolute schedule, so timer granularity averages out
                    now = time.perf_counter()
                    deadline = max(deadline + 1.0 / (FPS * ctl.speed), now - 0.25)     # (a stall is not caught up on)
                    await asyncio.sleep(max(0.0, deadline - now))
                else:
                    deadline = time.perf_counter()
            if sender is not None:
                await sender
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
            if live.brain:
                live.brain.close()
            live.run = live.pool = live.brain = None
            pool.shutdown(wait=False)

    async def save_moment(self, live: LiveRun, name: str, frame: Optional[int]) -> S.MomentSummary:
        """Save a moment by hand. The emulator belongs to the run's worker thread, so the save is queued behind the
        frame being played. Raises LookupError if the run is not being played right now, ValueError for a bad frame."""
        run, pool = live.run, live.pool
        if run is None or pool is None or not run.started:
            raise LookupError("the run is not being played right now; moments can only be saved while it runs")
        info = await asyncio.get_running_loop().run_in_executor(pool, lambda: save_moment(run, frame, name))
        return V.moment_to_dto(info)

    async def _send_frame(self, ws: WebSocket, loop, live: LiveRun, rec, total: int, screen) -> None:
        """Build the frame's pictures and send it. Runs beside the emulator's thread so the two overlap."""
        text = await loop.run_in_executor(self.render_pool, lambda: self._event(live, rec, total, screen).model_dump_json())
        await ws.send_text(text)

    @staticmethod
    def _build(live: LiveRun) -> Run:
        run = Run(live.fly, live.scene, run_id=live.id, from_moment=live.parent_moment, moments=True)
        run.start()
        live.brain = Lay.BrainLayer(run)
        return run

    @staticmethod
    def _event(live: LiveRun, rec, total: int, screen) -> S.FrameEvent:
        """One frame with its picture layers: game screen, transparent overlay and, when a newer one is ready, the brain."""
        items = [it for out in rec.outputs.values() for it in out.overlay]
        ov = Lay.overlay_rgba(items, rec.scroll_x)
        b64 = lambda b: base64.b64encode(b).decode("ascii")
        brain = live.brain.latest(live.brain_sent) if live.brain else None
        if brain:
            live.brain_sent = brain[0]
        return V.frame_event(rec, total, overlay_png=None if ov is None else b64(Lay.png_bytes(ov[0])),
                             overlay_at=None if ov is None else [ov[1], ov[2]],
                             brain_jpg=None if brain is None else b64(brain[1]), screen=screen)

    @staticmethod
    async def _finish(ws: WebSocket, live: LiveRun) -> None:
        if live.result is not None:
            await ws.send_json(S.EndEvent(result=Runs._live_result(live)).model_dump())
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
