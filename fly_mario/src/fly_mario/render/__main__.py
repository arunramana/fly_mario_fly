"""Draw runs.

Old form (one saved run, straight to a file):
    python -m fly_mario.render <run_dir> --still FRAME | --video [--no-senses] [--no-brain] [--out PATH]

Video exports (a job folder under $FLY_MARIO_DATA/videos/<id>/; --stills first, then --video on the same job):
    python -m fly_mario.render run <run> [--no-senses] [--no-brain] [--speed 2] [--from F] [--to F]  (--stills | --video [--job ID])
    python -m fly_mario.render side-by-side <runA> <runB> | --test JOB --start N   [--label-a T] [--label-b T] [--brain] [--speed 2]
    python -m fly_mario.render montage <evolution id> [--gens 0,3,5] [--clip-seconds 6] [--speed 2] [--with-start]
    python -m fly_mario.render job <folder>          (what the API starts)

<run> is a folder under $FLY_MARIO_DATA/runs/ (or just its name).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import cv2

from fly_mario.render import source
from fly_mario.render.draw import H, W, Renderer

EXPORT_CMDS = ("run", "side-by-side", "montage", "job")


def _suffix(a) -> str:
    return ("_nosenses" if a.no_senses else "") + ("_nobrain" if a.no_brain else "")


def legacy(argv) -> int:
    ap = argparse.ArgumentParser(prog="python -m fly_mario.render")
    ap.add_argument("run_dir")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--still", type=int, metavar="FRAME", help="one PNG of this frame (idle frames counted)")
    g.add_argument("--video", action="store_true", help="the whole run as an mp4")
    ap.add_argument("--no-senses", action="store_true", help="leave the game pixels untouched (no overlay)")
    ap.add_argument("--no-brain", action="store_true", help="game only, centred")
    ap.add_argument("--out", default=None)
    ap.add_argument("--fps", type=int, default=60)
    a = ap.parse_args(argv)

    run_dir = Path(a.run_dir)
    if not run_dir.exists():
        run_dir = Path(os.environ["FLY_MARIO_DATA"]) / "runs" / a.run_dir
    run = source.load_run(run_dir)
    brain = None if a.no_brain else source.brain_data(run, run_dir)
    rd = Renderer(brain, show_senses=not a.no_senses, show_brain=not a.no_brain)

    if a.still is not None:
        out = Path(a.out) if a.out else run_dir / "render" / f"still_{a.still:05d}{_suffix(a)}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        img = rd.frame(source.still_frame(run, a.still))
        cv2.imwrite(str(out), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        print(out)
        return 0

    out = Path(a.out) if a.out else run_dir / "render" / f"run{_suffix(a)}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    vw = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), a.fps, (W, H))
    n = 0
    for fd in source.frames(run):
        vw.write(cv2.cvtColor(rd.frame(fd), cv2.COLOR_RGB2BGR))
        n += 1
        if n % 300 == 0:
            print("frame", n, flush=True)
    vw.release()
    print(out, n, "frames", "(replay matches the recorded hash)" if source.check_hash(run, run_dir) else "(WARNING: replay hash differs from the recording)")
    return 0


def exports(argv) -> int:
    from fly_mario.render import export, specs
    ap = argparse.ArgumentParser(prog="python -m fly_mario.render")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def stage(p):
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--stills", action="store_true", help="2-3 PNGs to look at first")
        g.add_argument("--video", action="store_true", help="the mp4")
        p.add_argument("--job", default="", help="with --video: the job made by --stills (its folder or id)")

    r = sub.add_parser("run")
    r.add_argument("run")
    r.add_argument("--no-senses", action="store_true")
    r.add_argument("--no-brain", action="store_true")
    r.add_argument("--speed", type=int, default=1)
    r.add_argument("--from", dest="frame_from", type=int, default=None)
    r.add_argument("--to", dest="frame_to", type=int, default=None)
    stage(r)
    s = sub.add_parser("side-by-side")
    s.add_argument("runs", nargs="*", help="two saved runs")
    s.add_argument("--test", default="", help="a finished test job: Original vs Tuned of one of its starts")
    s.add_argument("--start", type=int, default=1, help="with --test: which start (1-based)")
    s.add_argument("--label-a", default="")
    s.add_argument("--label-b", default="")
    s.add_argument("--brain", action="store_true")
    s.add_argument("--no-senses", action="store_true")
    s.add_argument("--speed", type=int, default=1)
    stage(s)
    m = sub.add_parser("montage")
    m.add_argument("evolution")
    m.add_argument("--gens", default="", help="comma list of generations (default: every one)")
    m.add_argument("--clip-seconds", type=float, default=6.0)
    m.add_argument("--speed", type=int, default=2)
    m.add_argument("--with-start", action="store_true", help="also a clip of the fly the evolution started from")
    m.add_argument("--no-senses", action="store_true")
    stage(m)
    j = sub.add_parser("job")
    j.add_argument("folder")
    a = ap.parse_args(argv)

    if a.cmd == "job":
        return export.run_job(a.folder)
    if a.job:                                         # the video stage of a job whose stills were made earlier
        folder = Path(a.job)
        folder = folder if folder.exists() else export.videos_dir() / a.job
        if export.read_json(folder / "job.json") is None:
            print(f"error: no job {a.job!r}", file=sys.stderr)
            return 2
    else:
        try:
            if a.cmd == "run":
                spec = specs.run_spec(a.run, not a.no_senses, not a.no_brain, a.speed, a.frame_from, a.frame_to)
            elif a.cmd == "side-by-side":
                if a.test:
                    sa, sb = specs.test_side(a.test, a.start, "original"), specs.test_side(a.test, a.start, "tuned")
                elif len(a.runs) == 2:
                    sa, sb = specs.saved_side(a.runs[0]), specs.saved_side(a.runs[1])
                else:
                    ap.error("side-by-side needs two runs, or --test JOB --start N")
                spec = specs.side_by_side_spec(sa, sb, a.label_a, a.label_b, a.brain, not a.no_senses, a.speed)
            else:
                spec = specs.montage_spec(a.evolution, [int(g) for g in a.gens.split(",") if g] or None, a.clip_seconds,
                                          a.speed, a.with_start, not a.no_senses)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        folder = export.new_job_folder(spec, specs.title(spec))
    job = export.read_json(folder / "job.json")
    job.update(stage="stills" if a.stills else "video", status="queued")
    export._write_json(folder / "job.json", job)
    code = export.run_job(folder)
    if a.stills:
        for f in export.read_json(folder / "stills.json")["stills"]:
            print(folder / "stills" / f)
    else:
        info = export.read_json(folder / "info.json")
        print(folder / info["file"], f"{info['duration_s']} s", f"rendered in {info['render_s']} s", info["replay_checks"])
    return code


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    return exports(argv) if argv and argv[0] in EXPORT_CMDS else legacy(argv)


if __name__ == "__main__":
    raise SystemExit(main())
