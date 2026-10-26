"""Plug-ins, flies and results -> the JSON shapes. Everything is read from the registry; nothing names a sense or object."""
from __future__ import annotations

import base64
import struct
import zlib
from dataclasses import asdict, replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

from fly_mario_fly import registry
from fly_mario_fly.contracts import FlyConfig, Scene
from fly_mario_fly.api import knobs as K
from fly_mario_fly.api import schemas as S


def knob_ui(spec, position: float | None = None) -> S.KnobUI:
    return S.KnobUI(
        key=spec.key, label=spec.label, lo_label=spec.lo_label, hi_label=spec.hi_label,
        position=K.to_position(spec, spec.default) if position is None else position,
        scale=spec.scale, origin=spec.origin, evolvable=spec.evolvable, kind=spec.kind,
        floor_position=None if spec.floor is None else K.to_position(spec, spec.floor))


def _knobs(plugin) -> list:
    return [knob_ui(k) for k in getattr(plugin, "knobs", ())]


ORDER_FILE = Path(__file__).resolve().parents[3] / "configs" / "object_order.yaml"      # the display order of things


@lru_cache(maxsize=1)
def _object_ranks() -> dict:
    """{plug-in name: display rank} from configs/object_order.yaml (every tab's list, one after the other)."""
    lists = yaml.safe_load(ORDER_FILE.read_text(encoding="utf-8"))
    return {n: i for i, n in enumerate(n for names in lists.values() for n in names)}


def registry_info(levels: list, presets: list) -> S.RegistryInfo:
    objs = registry.list_plugins("objects")
    ranks = _object_ranks()
    base = len(ranks)
    senses = registry.list_plugins("senses")
    shapes = registry.list_plugins("shapes")
    actions = registry.list_plugins("actions")
    mods = registry.list_plugins("scenes")
    per_object = {n: any(p.get("type") in ("object_types", "object_type") for p in getattr(m, "params", ()))
                  for n, m in mods.items()}
    return S.RegistryInfo(
        objects=[S.ObjectInfo(name=o.name, label=o.label, note=getattr(o, "note", ""), kind=o.kind,
                              default_loom_shape=o.default_loom_shape,
                              icon=f"/objects/{o.name}/icon.png",
                              order=ranks.get(o.name, base + i)) for i, o in enumerate(objs.values())],
        senses=[S.SenseInfo(name=s.name, label=s.label, effect=s.effect, scope=s.scope, colour=s.colour,
                            line=s.line, feeds=list(getattr(s, "feeds", ())), knobs=_knobs(s),
                            order=int(getattr(s, "order", 0)))
                for s in senses.values()],
        shapes=[S.ShapeInfo(name=s.name, label=s.label, description=s.description,
                            knobs=_knobs(s)) for s in shapes.values()],
        actions=[S.ActionInfo(name=a.name, label=a.label, button=a.button,
                              source_groups=list(a.source_groups), knobs=_knobs(a), priority=a.priority,
                              order=int(getattr(a, "order", i)), status=getattr(a, "status", "ready"))
                 for i, a in enumerate(actions.values())],
        scene_modifiers=[S.SceneModifierInfo(name=m.name, label=m.label, description=m.description,
                                             params=[dict(p) for p in getattr(m, "params", ())],
                                             per_object=per_object[n]) for n, m in mods.items()],
        test_scenes=test_scenes(objs, mods, levels),
        presets=presets)


def test_scenes(objs: dict, mods: dict, levels: list) -> list:
    """One scene per (object-picking scene modifier, object type): that modifier keeping just that object."""
    if not levels:
        return []
    out = []
    for m in mods.values():
        key = next((p["key"] for p in getattr(m, "params", ()) if p.get("type") == "object_types"), None)
        if key is None:
            continue
        for o in objs.values():
            out.append(S.TestScene(name=f"{m.name}:{o.name}", label=f"{m.label}: {o.label}",
                                   scene=S.SceneDTO(level_id=levels[0].id, modifiers=[(m.name, {key: [o.name]})])))
    return out


# ---- flies ------------------------------------------------------------------------------------------------------
def fly_to_dto(fly: FlyConfig) -> S.FlyDTO:
    specs = K.specs_by_key()
    return S.FlyDTO(
        name=fly.name,
        attachments={s: sorted(t) for s, t in sorted(fly.attachments.items())},
        loom_shapes=dict(fly.loom_shapes), whole_fly=sorted(fly.whole_fly), actions=sorted(fly.actions),
        knobs={k: K.to_position(specs[k], v) for k, v in sorted(fly.knobs.items()) if k in specs},
        provenance=dict(fly.provenance))


def fly_to_view(fly: FlyConfig) -> S.FlyView:
    """The FlyDTO plus every knob's dial: position, original (KnobSpec default) position, tuned or not."""
    specs = K.specs_by_key()
    dials = {}
    for key, spec in sorted(specs.items()):
        orig = K.to_position(spec, spec.default)
        pos = K.to_position(spec, fly.knobs[key]) if key in fly.knobs else orig
        dials[key] = S.DialView(position=pos, original_position=orig, tuned=abs(pos - orig) > 1e-9)
    return S.FlyView(**fly_to_dto(fly).model_dump(), dials=dials)


def with_dials(fly: FlyConfig, dials: str) -> FlyConfig:
    """"original": every knob back at its KnobSpec default (the hand-set value before evolution); "tuned": as is."""
    if dials == "tuned":
        return fly
    return replace(fly, knobs={}, provenance={**fly.provenance, "dials": "original"})


def dto_to_fly(dto: S.FlyDTO) -> FlyConfig:
    """Raises ValueError for a knob key no plug-in declares."""
    specs = K.specs_by_key()
    unknown = sorted(set(dto.knobs) - set(specs))
    if unknown:
        raise ValueError(f"{dto.name}: unknown knob(s) {unknown}")
    return FlyConfig(
        name=dto.name, attachments={s: frozenset(t) for s, t in dto.attachments.items()},
        loom_shapes=dict(dto.loom_shapes), whole_fly=frozenset(dto.whole_fly), actions=frozenset(dto.actions),
        knobs={k: K.from_position(specs[k], p) for k, p in dto.knobs.items()}, provenance=dict(dto.provenance))


def fly_summary(fly: FlyConfig) -> S.FlySummary:
    return S.FlySummary(name=fly.name, senses=sorted({s for s, t in fly.attachments.items() if t} | set(fly.whole_fly)),
                        actions=sorted(fly.actions))


# ---- scenes and results -----------------------------------------------------------------------------------------
def scene_to_dto(scene: Scene) -> S.SceneDTO:
    d = asdict(scene)
    d["modifiers"] = [(n, dict(p)) for n, p in scene.modifiers]
    return S.SceneDTO(**d)


def dto_to_scene(dto: S.SceneDTO) -> Scene:
    return Scene(level_id=dto.level_id, rom=dto.rom, modifiers=tuple((n, dict(p)) for n, p in dto.modifiers),
                 start=dto.start, noop=dto.noop, sigma=dto.sigma, seed=dto.seed, max_frames=dto.max_frames,
                 stuck_frames=dto.stuck_frames)


def death_to_dto(death: dict | None) -> S.DeathDTO | None:
    """The runner's death dict ({x, cause}: "enemy:<type>", a fall-death object's name, or "other") -> the structured
    shape, with the object's label from the registry. This is the only place the cause string is read."""
    if not death:
        return None
    cause = str(death.get("cause", "other"))
    kind, otype = "other", None
    if cause.startswith("enemy:"):
        kind, otype = "enemy", cause[len("enemy:"):]
    elif cause != "other":
        kind, otype = "fall", cause
    obj = registry.list_plugins("objects").get(otype) if otype else None
    return S.DeathDTO(x=float(death.get("x", 0)), kind=kind, object_type=otype,
                      object_label=getattr(obj, "label", otype))


def result_to_dto(r) -> S.RunResultDTO:
    return S.RunResultDTO(
        id=r.id, fly=r.fly, scene=scene_to_dto(r.scene), parent_moment=r.parent_moment, outcome=r.outcome,
        death=death_to_dto(r.death), max_x=r.max_x, score=r.score, blocks=r.blocks, mushroom=r.mushroom,
        counts={k: float(v) for k, v in r.counts.items()}, moments=list(r.moments), hash=r.hash)


# ---- frames -----------------------------------------------------------------------------------------------------
def png_b64(screen: np.ndarray) -> str:
    """A 3-channel uint8 image as a base64 PNG (stdlib only; level 1 deflate, this runs every frame)."""
    h, w, _ = screen.shape
    raw = np.hstack([np.zeros((h, 1), np.uint8), np.ascontiguousarray(screen).reshape(h, w * 3)]).tobytes()

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b""))
    return base64.b64encode(png).decode("ascii")


def frame_event(rec, total: int, brain_jpg: str | None = None, screen: np.ndarray | None = None) -> S.FrameEvent:
    m = rec.mario
    overlay = [S.OverlayItem(kind=it.kind, geometry=[float(g) for g in it.geometry], colour=it.colour, line=it.line, anchor=it.anchor)
               for out in rec.outputs.values() for it in out.overlay]
    objects = [S.ObjectOnScreen(type=o.type, id=o.id, box=S.Box(x=o.box.x, y=o.box.y, w=o.box.w, h=o.box.h), side=o.side)
               for o in rec.objects]
    return S.FrameEvent(frame=rec.frame, total=total, frame_png=png_b64(rec.screen if screen is None else screen),
                        mario=S.Box(x=m.x, y=m.y, w=m.w, h=m.h), x=float(rec.x), buttons=sorted(rec.buttons),
                        overlay=overlay, objects=objects, scroll_x=rec.scroll_x, scroll_x_after=rec.scroll_x_after,
                        rates={g: float(v) for g, v in rec.rates.items()}, brain_jpg=brain_jpg)


# ---- levels and moments ---------------------------------------------------------------------------------------------
LEVEL_NAMES = {"full": "Whole game", "lost_levels": "Lost Levels", "random": "Random Stages"}     # the non-stage envs
LEVEL_ORDER = [f"{w}-{s}" for w in range(1, 9) for s in range(1, 5)] + list(LEVEL_NAMES)


def level_to_dto(lv) -> S.LevelInfo:
    return S.LevelInfo(id=lv.id, label=LEVEL_NAMES.get(lv.id, lv.id), kind=lv.kind, status="cleared" if lv.status.wins else "open",
                       status_text=lv.status.text, scanned=lv.scanned, partial=lv.partial,
                       objects=None if lv.objects is None else list(lv.objects))


def moment_to_dto(i) -> S.MomentSummary:
    return S.MomentSummary(id=i.id, run_id=i.run_id, name=i.name, frame=i.frame, x=i.x, auto=i.auto, kind=i.kind,
                           scene=scene_to_dto(i.scene), fly=fly_to_dto(i.fly), on_screen=list(i.on_screen))
