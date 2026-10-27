"""Helpers for the lite tests: a fake engine (no emulator, no data), a synthetic bundle folder, and request builders.
Import with `from lite_support import ...` (pytest puts this folder on sys.path)."""
import json
import threading
import time
from pathlib import Path

from fly_mario_fly.api import schemas as S
from fly_mario_fly.lite.config import LiteConfig


def request(level="1-1", attachments=None, knobs=None, actions=("walk", "steer", "jump", "back_up"), mods=(), max_frames=600, **kw):
    fly = S.FlyDTO(name="x", attachments=attachments or {}, actions=list(actions), knobs=knobs or {})
    scene = S.SceneDTO(level_id=level, modifiers=[(m, {}) for m in mods], max_frames=max_frames)
    return S.RunRequestDTO(fly=fly, scene=scene, **kw)


class FakeEngine:
    """Writes `size` bytes as the mp4 and returns a summary. `gate` (an Event) holds runs until a test opens it."""

    def __init__(self, size=1000, delay=0.0, fail=None, gate=None):
        self.size, self.delay, self.fail, self.gate = size, delay, fail, gate
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, settings_json, out_path, progress_path, cfg_json):
        with self.lock:
            self.calls.append(settings_json)
        if self.gate is not None:
            assert self.gate.wait(10), "test never opened the gate"
        time.sleep(self.delay)
        if self.fail:
            raise RuntimeError(self.fail)
        Path(out_path).write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * self.size)
        return {"result": {"outcome": "flag", "max_x": 3161.0, "hash": "abc"}, "video_frames": 10, "fps": 15, "wall_s": 0.0,
                "video_bytes": self.size, "settings": json.loads(settings_json) | {"max_frames": json.loads(settings_json)["max_frames"]}}


def make_bundle(root: Path) -> Path:
    """The smallest folder the API can serve: the json files and one picture each; no brains (the fake engine needs none)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "version.txt").write_text("testbundle", encoding="utf-8")
    for name, body in {"registry.json": {"presets": ["blank"], "objects": [], "senses": [], "shapes": [], "actions": [],
                                         "scene_modifiers": [], "test_scenes": []},
                       "levels.json": [{"id": "1-1"}, {"id": "1-2"}], "flies.json": [{"name": "blank"}],
                       "fly_blank.json": {"name": "blank"}}.items():
        (root / name).write_text(json.dumps(body), encoding="utf-8")
    for sub, stem in (("thumbs", "1-1"), ("icons", "goomba")):
        (root / sub).mkdir(exist_ok=True)
        (root / sub / f"{stem}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return root


def config(tmp_path: Path, **kw) -> LiteConfig:
    base = dict(bundle_dir=make_bundle(tmp_path / "bundle"), cache_dir=tmp_path / "cache", workers=2, queue_max=4,
                rate_per_minute=100, version="t1")
    return LiteConfig(**{**base, **kw})
