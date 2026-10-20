"""The moment store: saved moments on disk, and the story of what was tried from them.

    $FLY_MARIO_DATA/runs/<run id>/moments/<moment id>/
        moment.pkl   the SavedMoment: emulator state (mario's save_state blob), brain state by MaleCNS body id,
                     sense memory, RNG state, scene, fly (and the button replay so far, so a resumed run keeps its hash)
        meta.json    MomentInfo as json: enough to list a moment without opening the heavy file

Three kinds: "manual" (save_moment), "auto" (every N seconds of play; only the newest `keep_auto` are kept) and
"death" (the moment 3 s before a death; never rotated away).
Ids are "<run id>@<frame>" (+ "a" auto, "d" death; "-2" ... if that name is taken).
"""
from __future__ import annotations

import json
import pickle
import shutil
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

from fly_mario.contracts import FlyConfig, SavedMoment, Scene
from fly_mario.runner import config as C
from fly_mario.runner import record

KINDS = ("manual", "auto", "death")
SUFFIX = {"manual": "", "auto": "a", "death": "d"}


@dataclass(frozen=True)
class MomentInfo:
    """A saved moment without its heavy bytes."""
    id: str
    run_id: str
    name: str
    frame: int
    x: float
    auto: bool                       # not saved by hand (auto or death)
    kind: str                        # manual | auto | death
    scene: Scene
    fly: FlyConfig
    on_screen: tuple = ()            # object types visible at this moment
    created: float = 0.0


@dataclass(frozen=True)
class Try:
    """One run resumed from a moment."""
    run_id: str
    change: str                      # the fly's change against the moment's fly, in words ("" = same fly)
    outcome: str
    max_x: float


# ---- paths and (de)serialising ------------------------------------------------------------------------------
def run_of(moment_id: str) -> str:
    return moment_id.rsplit("@", 1)[0]


def moments_dir(run_id: str) -> Path:
    return record.runs_dir() / run_id / "moments"


def _folder(moment_id: str) -> Path:
    return moments_dir(run_of(moment_id)) / moment_id


def _info_to_dict(i: MomentInfo) -> dict:
    return {"id": i.id, "run_id": i.run_id, "name": i.name, "frame": i.frame, "x": i.x, "auto": i.auto, "kind": i.kind,
            "scene": record.scene_to_dict(i.scene), "fly": C.fly_to_dict(i.fly), "on_screen": list(i.on_screen),
            "created": i.created}


def _info_from_dict(d: dict) -> MomentInfo:
    return MomentInfo(id=d["id"], run_id=d["run_id"], name=d["name"], frame=int(d["frame"]), x=float(d["x"]),
                      auto=bool(d["auto"]), kind=d["kind"], scene=record.scene_from_dict(d["scene"]),
                      fly=C.fly_from_dict(d["fly"]), on_screen=tuple(d.get("on_screen", ())), created=float(d.get("created", 0)))


# ---- the store ----------------------------------------------------------------------------------------------
def put_moment(m: SavedMoment, kind: str, name: str = "", on_screen=()) -> MomentInfo:
    """Write a captured moment to its run's folder under a fresh id."""
    assert kind in KINDS, kind
    base = f"{m.run_id}@{m.frame}{SUFFIX[kind]}"
    mid, n = base, 1
    while _folder(mid).exists():
        n += 1
        mid = f"{base}-{n}"
    m = replace(m, id=mid, name=name or m.name)
    info = MomentInfo(mid, m.run_id, m.name, m.frame, float(m.x), kind != "manual", kind, m.scene, m.fly,
                      tuple(on_screen), time.time())
    f = _folder(mid)
    f.mkdir(parents=True)
    (f / "moment.pkl").write_bytes(pickle.dumps(m))
    (f / "meta.json").write_text(json.dumps(_info_to_dict(info), indent=1), encoding="utf-8")
    return info


def save_moment(run, frame: int | None = None, name: str = "") -> MomentInfo:
    """Save a moment of a running Run by hand: its current frame, or one of the last few in-memory snapshots."""
    if not run.run_id:
        raise ValueError("a run needs a run_id before it can keep moments")
    m, on_screen = run.capture_at(frame)
    info = put_moment(m, "manual", name or f"frame {m.frame}", on_screen)
    run.moments.append(info.id)
    return info


def get_moment(moment_id: str) -> SavedMoment:
    f = _folder(moment_id) / "moment.pkl"
    if not f.exists():
        raise KeyError(f"no saved moment {moment_id!r}")
    return pickle.loads(f.read_bytes())


def moment_info(moment_id: str) -> MomentInfo:
    f = _folder(moment_id) / "meta.json"
    if not f.exists():
        raise KeyError(f"no saved moment {moment_id!r}")
    return _info_from_dict(json.loads(f.read_text(encoding="utf-8")))


def list_moments(run_id: str) -> list:
    """Every moment of a run, by frame."""
    out = []
    for f in moments_dir(run_id).glob("*/meta.json") if moments_dir(run_id).exists() else ():
        try:
            out.append(_info_from_dict(json.loads(f.read_text(encoding="utf-8"))))
        except (OSError, ValueError, KeyError):
            continue
    return sorted(out, key=lambda i: (i.frame, i.created))


def rename_moment(moment_id: str, name: str) -> MomentInfo:
    info = replace(moment_info(moment_id), name=name)
    (_folder(moment_id) / "meta.json").write_text(json.dumps(_info_to_dict(info), indent=1), encoding="utf-8")
    return info


def delete_moment(moment_id: str) -> None:
    f = _folder(moment_id)
    if not f.exists():
        raise KeyError(f"no saved moment {moment_id!r}")
    shutil.rmtree(f)


def rotate_auto(run_id: str, keep: int) -> list:
    """Delete all but the newest `keep` auto moments of a run (manual and death moments are never touched)."""
    old = [i for i in list_moments(run_id) if i.kind == "auto"][:-keep or None] if keep > 0 else \
        [i for i in list_moments(run_id) if i.kind == "auto"]
    for i in old:
        delete_moment(i.id)
    return [i.id for i in old]


# ---- what was tried from a moment ---------------------------------------------------------------------------
def describe_change(old: FlyConfig, new: FlyConfig) -> str:
    """The difference between two flies in words: senses and actions switched on/off, knobs as directions."""
    from fly_mario import registry
    parts = []
    senses = registry.list_plugins("senses")
    for s in sorted(set(old.attachments) | set(new.attachments)):
        a, b = old.attachments.get(s, frozenset()), new.attachments.get(s, frozenset())
        label = senses[s].label if s in senses else s
        if not a and b:
            parts.append(f"{label} on, attached to {', '.join(sorted(b))}")
        elif a and not b:
            parts.append(f"{label} off")
        elif a != b:
            if b - a:
                parts.append(f"{label} now also on {', '.join(sorted(b - a))}")
            if a - b:
                parts.append(f"{label} no longer on {', '.join(sorted(a - b))}")
    for s in sorted(old.whole_fly ^ new.whole_fly):
        parts.append(f"{senses[s].label if s in senses else s} {'on' if s in new.whole_fly else 'off'}")
    for a in sorted(old.actions ^ new.actions):
        parts.append(f"action {a} {'on' if a in new.actions else 'off'}")
    for t in sorted(set(old.loom_shapes) | set(new.loom_shapes)):
        if old.loom_shapes.get(t) != new.loom_shapes.get(t):
            parts.append(f"{t} looms as {new.loom_shapes.get(t, 'its default shape')}")
    ko, kn = C.resolve_knobs(old) if _valid(old) else dict(old.knobs), C.resolve_knobs(new) if _valid(new) else dict(new.knobs)
    specs = {k.key: k for k in C.knob_specs(new)} if _valid(new) else {}
    specs.update({k.key: k for k in C.knob_specs(old)} if _valid(old) else {})
    for key in sorted(set(ko) | set(kn)):
        a, b = ko.get(key), kn.get(key)
        if a is None or b is None or abs(a - b) <= 1e-12 * max(1.0, abs(a)):
            continue
        sp = specs.get(key)
        parts.append(f"{sp.label if sp else key}: toward {sp.hi_label if b > a else sp.lo_label}" if sp
                     else f"{key}: {'higher' if b > a else 'lower'}")
    return "; ".join(parts)


def _valid(fly: FlyConfig) -> bool:
    try:
        C.validate(fly, strict_range=False)
        return True
    except ValueError:
        return False


def tries_from(moment_id: str) -> list:
    """Every saved run that was resumed from this moment: its change in words and its outcome."""
    info = moment_info(moment_id)
    out = []
    root = record.runs_dir()
    for f in sorted(root.glob("*/summary.json")) if root.exists() else ():
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            if s.get("parent_moment") != moment_id:
                continue
            fly = C.fly_from_dict(yaml.safe_load((f.parent / "config.yaml").read_text(encoding="utf-8"))["fly"])
        except (OSError, ValueError, KeyError):
            continue
        out.append(Try(s["id"], describe_change(info.fly, fly), s["outcome"], float(s["max_x"])))
    return out
