"""A request, cut down to what the lite server runs, and the cache key that names that run.

Two requests that would play the same game must get the same key (that is what makes the cache work), so the settings are
canonical: names sorted, knob positions rounded, noise off, a fixed seed, the frame cap applied. The run is made from the
canonical settings, not from the request, so the key and the video always agree.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from fly_mario_fly import registry
from fly_mario_fly.api import convert as V
from fly_mario_fly.api import schemas as S
from fly_mario_fly.lite.config import LiteConfig
from fly_mario_fly.runner import validate

POSITION_DIGITS = 3                  # knob sliders are 0..1; three decimals is finer than anyone can set by hand


class Refused(ValueError):
    """The request asks for something the lite server does not do (HTTP 422)."""


@dataclass(frozen=True)
class Settings:
    fly: dict                        # canonical FlyDTO as a dict
    dials: str
    level_id: str
    modifiers: tuple                 # ((name, params), ...)
    max_frames: int

    def to_json(self) -> str:
        return json.dumps({"fly": self.fly, "dials": self.dials, "level": self.level_id,
                           "mods": [list(m) for m in self.modifiers], "max_frames": self.max_frames}, sort_keys=True, separators=(",", ":"))

    def key(self, version: str) -> str:
        return hashlib.sha256(f"{version}|{self.to_json()}".encode()).hexdigest()[:20]

    def fly_dto(self) -> S.FlyDTO:
        return S.FlyDTO(**self.fly)

    def scene(self, cfg: LiteConfig):
        from fly_mario_fly.contracts import Scene
        return Scene(level_id=self.level_id, modifiers=tuple((n, dict(p)) for n, p in self.modifiers), start="level_start",
                     noop=cfg.noop, sigma=0.0, seed=cfg.seed, max_frames=self.max_frames, stuck_frames=300)


def canonicalize(req: S.RunRequestDTO, cfg: LiteConfig) -> Settings:
    """Raises Refused (or ValueError from validate) for a request outside the lite limits."""
    if req.from_moment is not None:
        raise Refused("saved moments are not available on the lite server")
    sc = req.scene
    if sc.level_id not in cfg.levels:
        raise Refused(f"level {sc.level_id!r} is not offered here (offered: {', '.join(cfg.levels)})")
    if sc.start != "level_start":
        raise Refused("only the level start is available here")
    known = registry.list_plugins("scenes")
    mods = []
    for name, params in sc.modifiers:
        if name not in known:
            raise Refused(f"unknown scene modifier {name!r}")
        if name not in cfg.modifiers:
            raise Refused(f"scene modifier {name!r} is not available here")
        mods.append((name, tuple(sorted(dict(params).items()))))
    mods = tuple(sorted(set(mods)))

    f = req.fly
    fly_check = V.dto_to_fly(f)                      # unknown knob keys -> ValueError
    validate(fly_check)                              # unknown senses / objects / actions -> ValueError
    attachments = {s: sorted(set(t)) for s, t in sorted(f.attachments.items()) if t}
    canon = S.FlyDTO(
        name="lite", attachments=attachments,
        loom_shapes={s: sh for s, sh in sorted(f.loom_shapes.items()) if s in attachments},
        whole_fly=sorted(set(f.whole_fly)), actions=sorted(set(f.actions)),
        knobs={k: round(float(p), POSITION_DIGITS) for k, p in sorted(f.knobs.items())}, provenance={})
    cap = min(int(sc.max_frames), cfg.max_frames)
    if cap < 60:
        raise Refused("max_frames must be at least 60")
    return Settings(fly=canon.model_dump(), dials="original" if req.dials == "original" else "tuned", level_id=sc.level_id,
                    modifiers=mods, max_frames=cap)
