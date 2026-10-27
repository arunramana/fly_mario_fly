"""python -m fly_mario_fly.lite [--host 0.0.0.0] [--port 8080]   (settings from FMF_LITE_* env vars, see config.py)"""
import argparse

import uvicorn

from fly_mario_fly.lite.app import create_lite_app
from fly_mario_fly.lite.config import LiteConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args()
    uvicorn.run(create_lite_app(LiteConfig.from_env()), host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
