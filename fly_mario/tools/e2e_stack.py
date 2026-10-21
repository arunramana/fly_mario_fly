"""Run the web e2e scripts against a private stack: python tools/e2e_stack.py [flow.mjs video.mjs]  (from fly_mario/).

The API gets a temp flies folder (FLY_MARIO_FLIES_DIR, a copy of the preset flies), so "Use this fly" never writes into
configs/flies/. It starts its own API (8010) and vite (5180), stops exactly those two process trees, and removes exactly
the temp folder it made; nothing else is touched.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
API_PORT, WEB_PORT = 8010, 5180
SHELL = sys.platform == "win32"


def kill_tree(proc):
    if SHELL:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.terminate()


def wait_for(url, seconds=60):
    for _ in range(seconds):
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except OSError:
            time.sleep(1)
    raise SystemExit(f"{url} did not come up")


def main(scripts):
    flies = Path(tempfile.mkdtemp(prefix="fly_mario_e2e_flies_"))
    procs = []
    try:
        shutil.copytree(ROOT / "configs" / "flies", flies, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*_evo_*"))
        env = {**os.environ, "FLY_MARIO_FLIES_DIR": str(flies)}
        procs.append(subprocess.Popen([sys.executable, "-m", "fly_mario.api", "--port", str(API_PORT)], cwd=ROOT, env=env))
        procs.append(subprocess.Popen(["npx", "vite", "--port", str(WEB_PORT), "--strictPort"], cwd=WEB, shell=SHELL,
                                      env={**os.environ, "VITE_API_URL": f"http://127.0.0.1:{API_PORT}"}))
        wait_for(f"http://127.0.0.1:{API_PORT}/levels")
        wait_for(f"http://localhost:{WEB_PORT}/")
        (WEB / "screenshots").mkdir(exist_ok=True)
        code = 0
        for s in scripts or ["e2e/flow.mjs", "e2e/video.mjs"]:
            code |= subprocess.run(["node", s], cwd=WEB, env={**os.environ, "BASE": f"http://localhost:{WEB_PORT}"}).returncode
        return code
    finally:
        for p in procs:
            kill_tree(p)
        shutil.rmtree(flies)          # the exact temp folder made above


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
