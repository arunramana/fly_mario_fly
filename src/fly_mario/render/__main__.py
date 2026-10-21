"""Render videos from the command line (each is a job folder under $FLY_MARIO_DATA/videos/<id>/).

    python -m fly_mario.render run <run> [--no-senses] [--no-brain] [--speed 2] [--from F] [--to F]
    python -m fly_mario.render montage <evolution id> [--clip-seconds 6] [--speed 2] [--no-brain] [--no-senses]
    python -m fly_mario.render job <folder>          (what the API starts)

<run> is a folder under $FLY_MARIO_DATA/runs/ (or just its name).
"""
from __future__ import annotations

import argparse
import sys

from fly_mario.render import export, specs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fly_mario.render")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("run")
    r.add_argument("--no-senses", action="store_true")
    r.add_argument("--no-brain", action="store_true", help="game only, centred")
    r.add_argument("--speed", type=int, default=1)
    r.add_argument("--from", dest="frame_from", type=int, default=None)
    r.add_argument("--to", dest="frame_to", type=int, default=None)
    m = sub.add_parser("montage")
    m.add_argument("evolution")
    m.add_argument("--clip-seconds", type=float, default=6.0)
    m.add_argument("--speed", type=int, default=2)
    m.add_argument("--no-brain", action="store_true")
    m.add_argument("--no-senses", action="store_true")
    j = sub.add_parser("job")
    j.add_argument("folder")
    a = ap.parse_args(sys.argv[1:] if argv is None else list(argv))

    if a.cmd == "job":
        return export.run_job(a.folder)
    try:
        if a.cmd == "run":
            spec = specs.run_spec(a.run, not a.no_senses, not a.no_brain, a.speed, a.frame_from, a.frame_to)
        else:
            spec = specs.montage_spec(a.evolution, a.clip_seconds, a.speed, not a.no_senses, not a.no_brain)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    folder = export.new_job_folder(spec, specs.title(spec))
    code = export.run_job(folder)
    info = export.read_json(folder / "info.json")
    if info:
        print(folder / info["file"], f"{info['duration_s']} s", f"rendered in {info['render_s']} s", info["replay_checks"])
    return code


if __name__ == "__main__":
    raise SystemExit(main())
