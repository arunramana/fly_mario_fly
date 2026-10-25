"""The MCP tools as plain functions (no MCP dependency): easy to test, and the server is a thin wrapper.

Every function returns a JSON-able dict. A write that would break a rule is REFUSED: {"ok": False, "refused": [{rule, subject,
message}], "nothing_written": True}. Nothing here edits connectome weights or fires neurons, and there is no tool that could:
a client can only add plug-ins made from fixed recipes, attach cues, set dials, and run a fly.

Lane rule: this package goes through runner/, rules/, render/ (to make a video), registry and contracts, and never names a
specific sense, object or action.
"""
from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fly_mario_fly import registry
from fly_mario_fly.contracts import Scene
from fly_mario_fly.mcp_server import codegen as cg
from fly_mario_fly.rules import RULES
from fly_mario_fly.rules import lookup, smoke
from fly_mario_fly.rules import validate as V
from fly_mario_fly.rules.guards import RuleViolation
from fly_mario_fly.runner import (Options, Run, active_actions, active_senses, brain_ready, dump_fly, load_fly, record, validate)
from fly_mario_fly.runner import config as C

COLOUR = {"fly": "teal", "invented": "orange"}
HONESTY = ["The wiring is untouched; a few dials are evolved.",
           "Never say 'nothing is trained'. Say what is invented (orange) and what is real (teal)."]
CANNOT = ["edit connectome weights", "fire neurons directly", "choose an action for the fly", "write code: new plug-ins are made from "
          "fixed recipes with validated numbers and names"]
MAX_FRAMES = 20000


@dataclass
class Workspace:
    """Where writes go. Defaults: the plug-in folders of the installed checkout, and configs/flies (or $FLY_MARIO_FLY_FLIES_DIR)."""
    plugin_dirs: Optional[dict] = None          # registry kind -> folder (tests override this)
    flies_dir: Optional[Path] = None

    def plugin_dir(self, kind: str) -> Path:
        if self.plugin_dirs and kind in self.plugin_dirs:
            return Path(self.plugin_dirs[kind])
        return Path(importlib.import_module(registry.KINDS[kind]).__path__[0])

    def flies(self) -> Path:
        return Path(self.flies_dir or os.environ.get("FLY_MARIO_FLY_FLIES_DIR") or C.FLIES)


def _refused(*items) -> dict:
    out = []
    for it in items:
        out.append({"rule": it.rule, "subject": it.subject, "message": it.message} if isinstance(it, V.Violation)
                   else {"rule": "R-INPUT", "subject": "request", "message": str(it)})
    return {"ok": False, "refused": out, "nothing_written": True}


def _decl(d) -> dict:
    out = {"kind": d.kind, "origin": d.origin, "colour": COLOUR[d.origin], "what": d.what}
    if d.route is not None:
        out["route"] = {"mechanism": d.route.mechanism, "cell_types": list(d.route.cell_types), "wiring": d.route.wiring,
                        "colour": "teal"}
    for k in ("drives", "modulates", "reads_groups", "buttons", "game_reads"):
        if getattr(d, k):
            out[k] = list(getattr(d, k))
    return out


def _knob(k) -> dict:
    return {"key": k.key, "label": k.label, "default": k.default, "min": k.lo, "max": k.hi, "scale": k.scale,
            "origin": k.origin, "colour": COLOUR[k.origin], "evolvable": k.evolvable}


# ---- reading ------------------------------------------------------------------------------------------------------

def list_rules() -> dict:
    return {"rules": [dataclasses.asdict(r) for r in RULES],
            "colour_rule": "teal = real wiring read off the MaleCNS connectome; orange = invented by us.",
            "honesty": HONESTY, "tools_cannot": CANNOT,
            "validate": "python -m fly_mario_fly.rules validate"}


def _kinds() -> list:
    return list(registry.KINDS) + ["characters"]


def _modules(kind: str) -> dict:
    if kind == "characters":
        return {n: m for n, m in registry.list_modules("objects").items() if m.DECLARATION.kind == "character"}
    if kind not in registry.KINDS:
        raise ValueError(f"unknown kind {kind!r}; known: {_kinds()}")
    return registry.list_modules(kind)


def list_plugins(kind: Optional[str] = None) -> dict:
    kinds = [kind] if kind else _kinds()
    try:
        out = []
        for k in kinds:
            for name, mod in _modules(k).items():
                d = mod.DECLARATION
                out.append({"kind": k, "name": name, "label": getattr(mod.PLUGIN, "label", name), "origin": d.origin,
                            "colour": COLOUR[d.origin], "what": d.what})
    except ValueError as e:
        return _refused(e)
    return {"ok": True, "plugins": out}


def explain_plugin(kind: str, name: str) -> dict:
    try:
        mods = _modules(kind)
    except ValueError as e:
        return _refused(e)
    if name not in mods:
        return _refused(f"no {kind} named {name!r}; known: {sorted(mods)}")
    mod = mods[name]
    p = mod.PLUGIN
    out = {"ok": True, "kind": kind, "name": name, "label": getattr(p, "label", name), "declaration": _decl(mod.DECLARATION),
           "source": str(Path(mod.__file__)), "dials": [_knob(k) for k in getattr(p, "knobs", []) or []]}
    for attr in ("effect", "note", "description", "scope", "feeds", "raises", "reads", "button", "source_groups", "priority",
                 "input_groups", "output_groups", "neuron_sets"):
        if hasattr(p, attr):
            out[attr] = getattr(p, attr)
    return out


def list_flies(workspace: Optional[Workspace] = None) -> dict:
    ws = workspace or Workspace()
    names = sorted(f.stem for f in ws.flies().glob("*.yaml"))
    return {"ok": True, "flies": names, "folder": str(ws.flies())}


# ---- writing plug-ins: always validated first ---------------------------------------------------------------------------

def _load_candidate(registry_kind: str, name: str, text: str, tmp: Path):
    folder = tmp / registry_kind
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.py"
    path.write_text(text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"_mcp_candidate_{registry_kind}_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, path


def _taken(registry_kind: str, name: str, ws: Workspace) -> Optional[str]:
    if name in registry.list_plugins(registry_kind):
        return f"a {registry_kind[:-1]} named {name!r} already exists"
    if (ws.plugin_dir(registry_kind) / f"{name}.py").exists():
        return f"{ws.plugin_dir(registry_kind) / (name + '.py')} already exists; nothing is ever overwritten"
    return None


def _add(registry_kind: str, expected_kind: str, name: str, text: str, ws: Workspace, dry_run: bool, smoke_kind: str) -> dict:
    ctx = V.make_context()
    with tempfile.TemporaryDirectory() as td:
        try:
            mod, path = _load_candidate(registry_kind, name, text, Path(td))
        except Exception as e:                       # noqa: BLE001: a bad recipe must come back as a refusal, not a crash
            return _refused(f"the generated plug-in does not load: {type(e).__name__}: {e}")
        plugin, decl = mod.PLUGIN, mod.DECLARATION
        bad = V.check_declaration(expected_kind, name, plugin, decl, ctx) + V.check_knobs(expected_kind, name, plugin)
        bad += V.scan_source([path], root=Path(td))
        existing = {k.key for kind in ("senses", "actions", "shapes") for p in registry.list_plugins(kind).values() for k in p.knobs}
        bad += [V.Violation("R-DIALS", f"{expected_kind} '{name}' dial '{k.key}'", "duplicates an existing dial.")
                for k in getattr(plugin, "knobs", []) or [] if k.key in existing]
        if bad:
            return _refused(*bad)
        problems = smoke.smoke_sense(plugin, decl) if smoke_kind == "sense" else smoke.smoke_object(plugin)
        if problems:
            return _refused(*problems)
    target = ws.plugin_dir(registry_kind) / f"{name}.py"
    out = {"ok": True, "dry_run": dry_run, "would_write" if dry_run else "written": str(target), "kind": expected_kind,
           "name": name, "origin": decl.origin, "colour": COLOUR[decl.origin], "declaration": _decl(decl),
           "dials": [_knob(k) for k in getattr(plugin, "knobs", []) or []],
           "checked": "declaration, dials, static scans and a smoke test passed"}
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "x", encoding="utf-8") as f:       # 'x': never overwrite
            f.write(text)
        importlib.invalidate_caches()                        # a running server must see the new file at once
        lookup._modules.cache_clear()
        out["next"] = ["python -m fly_mario_fly.rules validate", "attach it to a fly with add_cue", "commit the new file"]
    return out


def add_sense(name: str, label: str, effect: str, cue: str, route: str, drives: list, gain: float, colour: str = "green",
              range_px: float = 96.0, split_by_side: bool = False, wiring: str = "", what: str = "", dry_run: bool = False,
              workspace: Optional[Workspace] = None) -> dict:
    """A new sense: an invented cue (a closed list of recipes) driving input neurons of a real circuit (`route`)."""
    ws = workspace or Workspace()
    try:
        name = cg.check_name(name)
        label, effect = cg.check_text(label, "label", 3, 80), cg.check_text(effect, "effect")
        if cue not in cg.CUES:
            raise ValueError(f"cue must be one of {list(cg.CUES)}, got {cue!r}")
        if colour not in cg.COLOURS:
            raise ValueError(f"colour must be one of {sorted(cg.COLOURS)}, got {colour!r}")
        route = cg.check_names([route], "route")[0]
        drives = cg.check_names(drives, "drives")
        gain = cg.check_number(gain, "gain", 0.001, 100000.0)
        range_px = cg.check_number(range_px, "range_px", 8.0, 512.0)
        if not isinstance(split_by_side, bool):
            raise ValueError("split_by_side must be true or false")
        taken = _taken("senses", name, ws)
        if taken:
            raise ValueError(taken)
    except ValueError as e:
        return _refused(e)
    ctx = V.make_context()
    cell_types = sorted(ctx.cell_types(drives))
    wiring = cg.check_text(wiring, "wiring", 3, 200) if wiring else f"{route} circuit: {', '.join(drives)} (input neurons) onward"
    what = cg.check_text(what, "what", 20, 400) if what else (
        f"Invented cue ({cue}): {effect.rstrip('.')}. Only the wiring it drives, from {', '.join(drives)} onward ({route}), is real.")
    text = cg.sense_file(name=name, label=label, effect=effect, cue=cue, route=route, drives=drives, gain=gain, colour=colour,
                         range_px=range_px, split_by_side=split_by_side, wiring=wiring, what=what, cell_types=cell_types)
    return _add("senses", "sense", name, text, ws, dry_run, "sense")


def add_character(name: str, label: str, note: str, type_bytes: list, size: list, live_states: Optional[list] = None,
                  what: str = "", dry_run: bool = False, workspace: Optional[Workspace] = None) -> dict:
    """A new creature in the five enemy slots, found by its RAM type byte(s). Read-only: it only reads the game's memory."""
    ws = workspace or Workspace()
    try:
        name = cg.check_name(name)
        label, note = cg.check_text(label, "label", 3, 80), cg.check_text(note, "note")
        type_bytes = cg.check_int_list(type_bytes, "type_bytes", 0, 255, 8)
        if not isinstance(size, (list, tuple)) or len(size) != 2:
            raise ValueError(f"size must be [width, height], got {size!r}")
        w, h = int(cg.check_number(size[0], "size width", 4, 64)), int(cg.check_number(size[1], "size height", 4, 64))
        live_states = cg.check_int_list(live_states if live_states is not None else [0], "live_states", 0, 255, 8)
        taken = _taken("objects", name, ws)
        if taken:
            raise ValueError(taken)
        for owner, bytes_ in smoke.known_type_bytes().items():
            clash = sorted(set(bytes_) & set(type_bytes))
            if clash:
                raise ValueError(f"type byte(s) {clash} already belong to '{owner}'; one creature per RAM type")
    except (ValueError, TypeError, IndexError) as e:
        return _refused(e)
    what = cg.check_text(what, "what", 20, 400) if what else (
        f"A creature found by reading the game's RAM for type byte(s) {type_bytes}; the box ({w}x{h}) is ours, not the fly's.")
    text = cg.creature_file(name=name, label=label, note=note, type_bytes=type_bytes, size=[w, h], live_states=live_states, what=what)
    return _add("objects", "character", name, text, ws, dry_run, "object")


def add_object(name: str, label: str, note: str, tile_ids: list, what: str = "", dry_run: bool = False,
               workspace: Optional[Workspace] = None) -> dict:
    """New solid terrain made of metatile ids standing on the ground (like a pipe). Read-only: it only reads the game's memory."""
    ws = workspace or Workspace()
    try:
        name = cg.check_name(name)
        label, note = cg.check_text(label, "label", 3, 80), cg.check_text(note, "note")
        tile_ids = cg.check_int_list(tile_ids, "tile_ids", 1, 255, 16)
        taken = _taken("objects", name, ws)
        if taken:
            raise ValueError(taken)
        owners = smoke.known_tile_ids()
        clash = {t: owners[t] for t in tile_ids if t in owners}
        if clash:
            raise ValueError(f"tile id(s) {clash} are already named in the game facts (id: owner); pick ids no object uses")
    except ValueError as e:
        return _refused(e)
    what = cg.check_text(what, "what", 20, 400) if what else (
        f"Terrain found by reading the game's RAM for metatile id(s) {tile_ids}; the boxes are ours, not the fly's.")
    text = cg.terrain_file(name=name, label=label, note=note, tile_ids=tile_ids, what=what)
    return _add("objects", "object", name, text, ws, dry_run, "object")


# ---- writing flies (config) -----------------------------------------------------------------------------------------------

def _fly_path(name: str, ws: Workspace) -> Path:
    if not isinstance(name, str) or not cg.FLY_RE.match(name):
        raise ValueError(f"fly name {name!r} must be letters, digits, - or _ (no paths)")
    p = ws.flies() / f"{name}.yaml"
    if not p.exists() and (C.FLIES / f"{name}.yaml").exists():
        p = C.FLIES / f"{name}.yaml"
    return p


def _save(fly, name: str, ws: Workspace, dry_run: bool, overwrite_ok: bool) -> dict:
    target = ws.flies() / f"{name}.yaml"
    if target.exists() and not overwrite_ok:
        return _refused(f"{target} already exists; use save_as with a new name to keep the original")
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dump_fly(fly), encoding="utf-8")
    return {"ok": True, "dry_run": dry_run, "fly": name, "file": str(target), "senses": sorted(fly.attachments) + sorted(fly.whole_fly),
            "actions": sorted(fly.actions), "dials": {k: v for k, v in sorted(fly.knobs.items())}}


def create_fly(name: str, copy_from: str = "blank", dry_run: bool = False, workspace: Optional[Workspace] = None) -> dict:
    """A new fly (a YAML config) copied from an existing one."""
    ws = workspace or Workspace()
    try:
        src = load_fly(_fly_path(copy_from, ws))
        if not isinstance(name, str) or not cg.FLY_RE.match(name):
            raise ValueError(f"fly name {name!r} must be letters, digits, - or _ (no paths)")
        fly = dataclasses.replace(src, name=name, provenance={"source": f"created by the MCP server as a copy of {copy_from}"})
        return _save(fly, name, ws, dry_run, overwrite_ok=False)
    except (ValueError, FileNotFoundError) as e:
        return _refused(e)


def add_cue(fly: str, sense: str, objects: Optional[list] = None, save_as: str = "", dry_run: bool = False,
            workspace: Optional[Workspace] = None) -> dict:
    """Attach a sense (a cue) to object types in a fly. A whole-fly sense takes no objects."""
    ws = workspace or Workspace()
    try:
        base = load_fly(_fly_path(fly, ws))
        senses = registry.list_plugins("senses")
        if sense not in senses:
            raise ValueError(f"no sense {sense!r}; known: {sorted(senses)}")
        if senses[sense].scope == "whole_fly":
            if objects:
                raise ValueError(f"{sense!r} is a whole-fly sense: it looks at everything and takes no objects")
            new = dataclasses.replace(base, whole_fly=frozenset(base.whole_fly | {sense}))
        else:
            objs = cg.check_names(objects or [], "objects")
            new = dataclasses.replace(base, attachments={**base.attachments, sense: frozenset(set(base.attachments.get(sense, ())) | set(objs))})
        validate(new)
        target = save_as or fly
        if save_as and not cg.FLY_RE.match(save_as):
            raise ValueError(f"save_as {save_as!r} must be letters, digits, - or _")
        new = dataclasses.replace(new, name=target)
        res = _save(new, target, ws, dry_run, overwrite_ok=not save_as)
        if res.get("ok"):
            d = declaration_for("senses", sense)
            res["cue"] = {"sense": sense, "origin": d.origin, "colour": COLOUR[d.origin], "route": d.route.wiring if d.route else ""}
        return res
    except (ValueError, FileNotFoundError) as e:
        return _refused(e)


def declaration_for(kind: str, name: str):
    return registry.list_modules(kind)[name].DECLARATION


def set_dial(fly: str, key: str, value: float, save_as: str = "", dry_run: bool = False,
             workspace: Optional[Workspace] = None) -> dict:
    """Set one dial (a KnobSpec value) of a fly, within its range. Dials scale cues and readouts; they are orange."""
    ws = workspace or Workspace()
    try:
        base = load_fly(_fly_path(fly, ws))
        if not isinstance(key, str) or not cg.KEY_RE.match(key):
            raise ValueError(f"{key!r} is not a dial. Only dials can be set (never weights or neurons)")
        value = cg.check_number(value, "value", -1e9, 1e9)
        specs = {k.key: k for kind in ("senses", "actions", "shapes") for p in registry.list_plugins(kind).values() for k in p.knobs}
        if key not in specs:
            raise ValueError(f"no dial {key!r}. Only dials can be set (never weights or neurons); known: {sorted(specs)}")
        k = specs[key]
        if k.origin != "invented":
            raise ValueError(f"dial {key!r} claims real wiring; dials must be invented")
        if not (k.lo <= value <= k.hi):
            raise ValueError(f"{key} = {value} is outside its range [{k.lo}, {k.hi}]")
        old = base.knobs.get(key, k.default)
        target = save_as or fly
        if save_as and not cg.FLY_RE.match(save_as):
            raise ValueError(f"save_as {save_as!r} must be letters, digits, - or _")
        new = dataclasses.replace(base, name=target, knobs={**base.knobs, key: value})
        validate(new)
        res = _save(new, target, ws, dry_run, overwrite_ok=not save_as)
        if res.get("ok"):
            res["dial"] = {**_knob(k), "old": old, "new": value}
        return res
    except (ValueError, FileNotFoundError) as e:
        return _refused(e)


# ---- running --------------------------------------------------------------------------------------------------------------

def run_fly(fly: str, level: str = "1-1", seed: int = 0, noop: int = 0, sigma: float = 0.0, max_frames: int = 6000,
            video: bool = False, workspace: Optional[Workspace] = None) -> dict:
    """Play one episode headlessly and summarise it. Needs the MaleCNS brain cache ($FLY_MARIO_FLY_DATA); never downloads."""
    ws = workspace or Workspace()
    try:
        cfg = load_fly(_fly_path(fly, ws))
        seed = int(cg.check_number(seed, "seed", 0, 2**31 - 1))
        noop = int(cg.check_number(noop, "noop", 0, 600))
        sigma = cg.check_number(sigma, "sigma", 0.0, 1.0)
        max_frames = int(cg.check_number(max_frames, "max_frames", 60, MAX_FRAMES))
        if not isinstance(level, str) or len(level) > 12:
            raise ValueError("level must be like '1-1'")
    except (ValueError, FileNotFoundError) as e:
        return _refused(e)
    if not brain_ready(cfg):
        return {"ok": False, "error": "the brain for this fly is not built. Set $FLY_MARIO_FLY_DATA and run "
                "`python scripts/download_data.py --build-brains` (about 1.2 GB; this tool never downloads by itself)."}
    rid = record.new_run_id(fly, level, seed)
    try:
        run = Run(cfg, Scene(level, noop=noop, sigma=sigma, seed=seed, max_frames=max_frames), Options(moment_every_s=0), run_id=rid)
        result = run.play()
    except RuleViolation as e:
        return {"ok": False, "rule_violation": str(e)}
    except ValueError as e:
        return _refused(e)
    out = {"ok": True, "fly": fly, "level": level, "seed": seed, "outcome": result.outcome, "max_x": result.max_x,
           "frames": result.counts["frames"], "score": result.score, "blocks": result.blocks, "hash": result.hash[:12],
           "death": result.death, "objects_seen": sorted(run.seen),
           "senses": [{"name": s.name, "origin": "invented", "colour": "orange"} for s in active_senses(cfg)],
           "actions": [a.name for a in active_actions(cfg)],
           "honesty": HONESTY[0]}
    if video:
        out["video"] = _render(run, result, rid)
    return out


def _render(run, result, rid: str) -> dict:
    from fly_mario_fly.render import export, specs
    folder_saved = record.save_run(run, result)
    spec = specs.run_spec(rid, True, True, 1, None, None)
    folder = export.new_job_folder(spec, specs.title(spec))
    code = export.run_job(folder)
    info = export.read_json(folder / "info.json") or {}
    if code != 0 or "file" not in info:
        return {"ok": False, "error": f"the video export failed (code {code}); the run was saved in {folder_saved}"}
    return {"ok": True, "path": str(folder / info["file"]), "seconds": info.get("duration_s"), "run_folder": str(folder_saved)}
