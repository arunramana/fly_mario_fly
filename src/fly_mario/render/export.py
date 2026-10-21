"""Video exports: replay runs through the runner and draw them as clips (1920 x 1080, 60 fps, H.264).

Two kinds, one job folder each under $FLY_MARIO_DATA/videos/<id>/ (the spec is in job.json, see specs.py):

    run       one saved run in the approved brain | game look; speed, an optional frame range
    montage   one clip per generation of an evolution (that generation's best fly), each played from the start to its
              end (flag, death or stuck), with the fitness of every generation along the bottom and the current one
              highlighted; speed 1x / 2x / 4x

An export is one process, `python -m fly_mario.render job <folder>`: it writes video.mp4 as video.part.mp4 and renames
it when it is complete. Only factual labels are drawn: dials, fly or generation names, how a run ended. No claims.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from fly_mario import registry
from fly_mario.render import palette as P
from fly_mario.render import source
from fly_mario.render.draw import H, LEFT_W, W, BrainPanel, Renderer, font, game_panel
from fly_mario.runner.record import runs_dir

FPS = 60
SCALE = 3                                   # NES x3 in the montage frames
PW, PH = 256 * SCALE, 240 * SCALE           # 768 x 720
GOLD, GREY = (232, 176, 40), (120, 120, 118)
OK_COL, BAD_COL = (96, 200, 120), (230, 100, 90)
ALIVE_EVERY = 5.0
HOLD = 30                                   # output frames the last picture of a montage clip stays, so its caption can be read


def videos_dir() -> Path:
    return runs_dir().parent / "videos"


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class HashMismatch(RuntimeError):
    pass


# ---- encoder ------------------------------------------------------------------------------------------------------
class Writer:
    """H.264 mp4 through the ffmpeg that imageio-ffmpeg bundles (yuv420p, plays everywhere and edits well);
    without imageio-ffmpeg, OpenCV's mp4v."""

    def __init__(self, path: Path, fps: int = FPS):
        self.path = path
        try:
            import imageio_ffmpeg
        except ImportError:
            imageio_ffmpeg = None
        if imageio_ffmpeg is not None:
            self.gen = imageio_ffmpeg.write_frames(str(path), (W, H), fps=fps, codec="libx264", pix_fmt_in="rgb24",
                                                   pix_fmt_out="yuv420p", quality=None, macro_block_size=1,
                                                   output_params=["-crf", "16", "-preset", "medium", "-movflags", "+faststart"])
            self.gen.send(None)
            self.cv = None
        else:
            self.gen = None
            self.cv = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))

    def write(self, img: np.ndarray) -> None:
        if self.gen is not None:
            self.gen.send(np.ascontiguousarray(img).tobytes())
        else:
            self.cv.write(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

    def close(self) -> None:
        if self.gen is not None:
            self.gen.close()
        else:
            self.cv.release()


class Progress:
    """progress.json: how far the job is, at most once a second."""

    def __init__(self, folder: Path, phase: str, total: int):
        self.path, self.phase, self.total = folder / "progress.json", phase, max(1, total)
        self.t0, self.last = time.time(), 0.0

    def tick(self, done: int, force: bool = False) -> None:
        now = time.time()
        if not force and now - self.last < 1.0:
            return
        self.last = now
        el = now - self.t0
        done = min(done, self.total)
        eta = round(el / done * (self.total - done)) if done else None
        _write_json(self.path, {"phase": self.phase, "done": done, "total": self.total, "elapsed_s": round(el),
                                "eta_s": eta, "updated": now})


# ---- one run being replayed ---------------------------------------------------------------------------------------
def outcome_text(run) -> str:
    """How a finished run ended, in words: "Reached the flag", "Died at x 891 · Koopa", ..."""
    if run.outcome == "flag":
        return "Reached the flag"
    x = int(run.max_x)
    if run.outcome == "died":
        cause = str((run.death or {}).get("cause", "other"))
        otype = cause[len("enemy:"):] if cause.startswith("enemy:") else (cause if cause != "other" else None)
        obj = registry.list_plugins("objects").get(otype) if otype else None
        name = getattr(obj, "label", otype)
        return f"Died at x {int((run.death or {}).get('x', x))}" + (f" · {name}" if name else "")
    return f"{'Got stuck' if run.outcome == 'stuck' else 'Ran out of time'} at x {x}"


class Lane:
    """One run played a frame at a time. After the run's last frame `ended` is set and `fd` stays the last frame."""

    def __init__(self, side: dict):
        self.side = side
        self.run = source.run_from_side(side)
        self.it = source.frames(self.run)
        self.fd = None
        self.ended = False
        self.caption = ""
        self.index = -1

    def advance(self) -> bool:
        """Step one frame; True if there was one."""
        if self.ended:
            return False
        self.fd = next(self.it, None) or self.fd
        self.index += 1
        if self.run.finished:
            self.ended = True
            self.caption = outcome_text(self.run)
        return True

    def drain(self) -> None:
        """Play the rest unseen (the replay hash needs the whole run)."""
        while self.advance():
            pass

    def check(self) -> dict:
        """What the replay did, against what was recorded. hash_ok is None when no hash was recorded."""
        res, exp = self.run.result(), self.side.get("expect", {})
        want = exp.get("hash") or ""
        return {"label": self.side.get("label", ""), "run_id": self.side.get("run_id", ""), "outcome": res.outcome,
                "max_x": res.max_x, "frames": res.counts["frames"], "hash": res.hash,
                "hash_ok": (res.hash == want) if want else None,
                "matches_test": None if "outcome" not in exp else (res.outcome == exp["outcome"] and res.max_x == exp["max_x"])}


def verify(lanes: list) -> list:
    checks = [ln.check() for ln in lanes]
    for c in checks:
        if c["hash_ok"] is False or c["matches_test"] is False:
            raise HashMismatch(f"the replay of {c['label'] or c['run_id']!r} does not match the recorded run "
                               f"(recorded hash vs replayed {c['hash'][:12]}): the code or the data changed since it was recorded")
    return checks


def _brain(side: dict, run, steps: int | None = None) -> "source.BrainData":
    if side.get("rates"):
        return source.brain_data(run, Path(side["rates"]).parent)
    return source.brain_data(run, rate_max=source.rate_max_of(source.run_from_side(side), steps))


# ---- compositing helpers ------------------------------------------------------------------------------------------
def _canvas() -> Image.Image:
    return Image.new("RGB", (W, H), P.BG)


def _centred(dr, cx: int, y: int, text: str, sz: int, fill, bold=True, maxw: int = PW) -> None:
    f = font(sz, bold)
    while dr.textlength(text, font=f) > maxw and sz > 18:
        sz -= 2
        f = font(sz, bold)
    dr.text((cx, y), text, font=f, fill=fill, anchor="ma")


def _caption(img: np.ndarray, cx: int, y: int, text: str, good: bool) -> None:
    pil = Image.fromarray(img)
    _centred(ImageDraw.Draw(pil), cx, y, text, 34, OK_COL if good else BAD_COL, maxw=PW + 80)
    img[:] = np.asarray(pil)


# ---- the two layouts --------------------------------------------------------------------------------------------
class RunExport:
    """One saved run, the approved brain | game frame."""

    def __init__(self, spec: dict):
        self.spec, self.side = spec, spec["sides"][0]
        self.noop = int(self.side["scene"].get("noop", 0))
        self.f0, self.f1 = spec["frame_from"], spec["frame_to"]

    def total(self) -> int:
        return int(self.side["expect"]["frames"])

    def frames(self):
        """(key, image) for every frame to be drawn."""
        s = self.spec
        lane = Lane(self.side)
        probe = source.run_from_side(self.side)
        rd = Renderer(_brain(self.side, probe) if s["show_brain"] else None, show_senses=s["show_senses"], show_brain=s["show_brain"])
        while lane.advance():
            f = lane.fd.frame
            if self.f0 <= f <= self.f1 and (f - self.f0) % s["speed"] == 0:
                yield lane.index, rd.frame(lane.fd)
        lane.drain()
        self.report = verify([lane])


class MontageExport:
    """One clip per generation's best fly, played to its end, with the fitness of every generation along the bottom.
    A clip is about frames / speed output frames (every speed-th one, and the last) plus HOLD frames of the last picture."""

    GAME_Y, LABEL_Y, CAP_Y = 84, 16, 808
    BAR_Y0, BAR_Y1 = 920, 1030

    def __init__(self, spec: dict):
        self.spec = spec
        if spec["show_brain"]:                      # the R3 brain panel on the left, the game and the chart on the right
            self.GAME_X, self.BAR_X0, self.BAR_X1 = LEFT_W + (W - LEFT_W - PW) // 2, LEFT_W + 32, W - 32
        else:
            self.GAME_X, self.BAR_X0, self.BAR_X1 = (W - PW) // 2, 160, 1760

    def total(self) -> int:
        return len(self.spec["sides"])              # progress counts clips: how long each is is only known once it has played

    def _base(self, side: dict) -> np.ndarray:
        pil = _canvas()
        dr = ImageDraw.Draw(pil)
        _centred(dr, self.GAME_X + PW // 2, self.LABEL_Y, side["label"], 46, (255, 255, 255), maxw=1200)
        bars = self.spec["bars"]
        cur = side.get("gen", -1)
        dr.text((self.BAR_X0, self.BAR_Y0 - 44), "Fitness of each generation's fly", font=font(20, True), fill=P.TXT)
        dr.rectangle([self.BAR_X1 - 200, self.BAR_Y0 - 38, self.BAR_X1 - 184, self.BAR_Y0 - 24], fill=GOLD)
        dr.text((self.BAR_X1 - 176, self.BAR_Y0 - 44), "best", font=font(18), fill=P.TXT)
        dr.rectangle([self.BAR_X1 - 120, self.BAR_Y0 - 38, self.BAR_X1 - 104, self.BAR_Y0 - 24], fill=GREY)
        dr.text((self.BAR_X1 - 96, self.BAR_Y0 - 44), "average", font=font(18), fill=P.TXT)
        top = max(1e-9, *(b["best"] for b in bars), *(b["mean"] for b in bars))
        slot = min((self.BAR_X1 - self.BAR_X0) / len(bars), 90)                   # few generations: bars stay close, centred
        x0 = (self.BAR_X0 + self.BAR_X1) / 2 - slot * len(bars) / 2
        bw = int(min(40, slot * 0.34))
        hh = self.BAR_Y1 - self.BAR_Y0
        for k, b in enumerate(bars):
            cx = x0 + slot * (k + 0.5)
            on = b["gen"] == cur
            if on:
                dr.rectangle([cx - slot / 2 + 2, self.BAR_Y0 - 6, cx + slot / 2 - 2, self.BAR_Y1 + 30], fill=(30, 30, 36), outline=(110, 110, 120))
            for dx, v, col in ((-bw / 2 - 1, b["mean"], GREY), (bw / 2 + 1, b["best"], GOLD)):
                h = max(2, int(max(v, 0) / top * hh))
                c = col if on else tuple(int(c * 0.55) for c in col)
                dr.rectangle([cx + dx - bw / 2, self.BAR_Y1 - h, cx + dx + bw / 2, self.BAR_Y1], fill=c)
            if len(bars) <= 40 or b["gen"] % 5 == 0:
                dr.text((cx, self.BAR_Y1 + 6), str(b["gen"]), font=font(16, on), fill=(255, 255, 255) if on else P.DIM, anchor="ma")
        row = next((b for b in bars if b["gen"] == cur), None)
        if row:
            dr.text((self.BAR_X0 + 380, self.BAR_Y0 - 44), f"gen {cur}:  best {row['best']:.2f} · average {row['mean']:.2f}",
                    font=font(20), fill=(255, 255, 255))
        return np.asarray(pil).copy()

    def _panel(self, run) -> BrainPanel:
        """One brain panel for every clip, brightness scaled to the maximum over ALL the clips (as the run video scales to
        its whole run), so a bright neuron means the same activity in every generation."""
        if getattr(self, "_shared", None) is None:
            rmax: dict = {}
            for side in self.spec["sides"]:
                for g, v in source.rate_max_of(source.run_from_side(side)).items():
                    rmax[g] = max(rmax.get(g, 0.0), v)
            self._shared = BrainPanel(source.brain_data(run, rate_max=rmax))
        return self._shared

    def frames(self):
        s = self.spec
        self.clips = []                             # per clip: its label, its game frames and the output frames it took
        for k, side in enumerate(s["sides"]):
            lane, base = Lane(side), self._base(side)
            panel = self._panel(lane.run) if s["show_brain"] else None
            out_frames = 0
            while lane.advance():
                if lane.index % s["speed"] and not lane.ended:
                    continue
                out = self._compose(base, lane, panel)
                for _ in range(1 + (HOLD if lane.ended else 0)):
                    out_frames += 1
                    yield k, out
            self.clips.append({"label": side["label"], "outcome": lane.run.outcome, "game_frames": lane.index + 1, "output_frames": out_frames})
        self.report = []

    def _compose(self, base: np.ndarray, lane, panel) -> np.ndarray:
        s, fd = self.spec, lane.fd
        out = base.copy()
        if panel:
            out[:, :LEFT_W] = panel.draw(fd.rates, fd.frame)
        out[self.GAME_Y:self.GAME_Y + PH, self.GAME_X:self.GAME_X + PW] = game_panel(fd.game, fd.overlay, fd.scroll_x, s["show_senses"], SCALE)
        if lane.ended:
            _caption(out[self.CAP_Y:self.CAP_Y + 48, self.GAME_X - 40:self.GAME_X + PW + 40], PW // 2 + 40, 2, lane.caption, lane.run.outcome == "flag")
        return out


EXPORTS = {"run": RunExport, "montage": MontageExport}


# ---- the video -----------------------------------------------------------------------------------------------------
def make_video(folder: Path, spec: dict) -> dict:
    ex = EXPORTS[spec["export"]](spec)
    part, final = folder / "video.part.mp4", folder / "video.mp4"
    prog = Progress(folder, "rendering", ex.total())
    t0, n, key = time.time(), 0, 0
    w = Writer(part)
    try:
        for key, img in ex.frames():
            w.write(img)
            n += 1
            prog.tick(key if spec["export"] == "montage" else n * spec.get("speed", 1))
    finally:
        w.close()
    try:
        checks = ex.report
    except AttributeError:
        checks = []
    part.replace(final)
    info = {"export": spec["export"], "file": "video.mp4", "width": W, "height": H, "fps": FPS, "frames": n,
            "duration_s": round(n / FPS, 2), "bytes": final.stat().st_size, "render_s": round(time.time() - t0, 1),
            "replay_checks": checks, "speed": spec.get("speed", 1)}
    if hasattr(ex, "clips"):
        info["clips"] = ex.clips
    prog.tick(prog.total, force=True)
    return info


# ---- the job process ----------------------------------------------------------------------------------------------
def _heartbeat(folder: Path, stop: threading.Event) -> None:
    while not stop.is_set():
        (folder / "alive").write_text(str(time.time()))
        stop.wait(ALIVE_EVERY)


def run_job(folder) -> int:
    """Render the export job.json asks for and record how it went."""
    folder = Path(folder)
    job = read_json(folder / "job.json")
    stop = threading.Event()
    threading.Thread(target=_heartbeat, args=(folder, stop), daemon=True).start()
    job.update(status="running", pid=os.getpid(), started=time.time())
    _write_json(folder / "job.json", job)
    try:
        _write_json(folder / "info.json", make_video(folder, job["spec"]))
        job = read_json(folder / "job.json") or job
        if job["status"] != "cancelled":
            job.update(status="finished", finished=time.time())
            _write_json(folder / "job.json", job)
        return 0
    except BaseException as e:                                # noqa: BLE001 - the job's last word, whatever went wrong
        job = read_json(folder / "job.json") or job
        job.update(status="failed", error=f"{type(e).__name__}: {e}", finished=time.time())
        _write_json(folder / "job.json", job)
        raise
    finally:
        stop.set()


def new_job_folder(spec: dict, title: str, root: Path | None = None) -> Path:
    """Create videos/<id>/ with a job.json (not started). `of` is what it shows: the run id, or the evolution's."""
    import uuid
    jid = f"vid_{time.strftime('%Y%m%d-%H%M%S')}_{spec['export']}_{uuid.uuid4().hex[:4]}"
    folder = (root or videos_dir()) / jid
    folder.mkdir(parents=True, exist_ok=True)
    _write_json(folder / "job.json", {"id": jid, "kind": "video", "export": spec["export"], "title": title,
                                       "of": spec["sides"][0]["run_id"] if spec["export"] == "run" else spec["evo"], "status": "queued", "spec": spec, "created": time.time(), "pid": None, "error": ""})
    return folder
