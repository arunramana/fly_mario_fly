"""The validator: checks every plug-in against the rules, with plain-English messages.

    python -m fly_mario_fly.rules validate        # exit 1 and print each violation if any rule is broken

`check_declaration`, `check_knobs` and `scan_source` are pure: they take plain objects, so tests (and the MCP server later) can
feed them a deliberately broken plug-in. `validate_all` runs them over the real repository.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from fly_mario_fly.rules.schema import BUTTONS, GAME_READS, KINDS, ORIGINS, Declaration

# registry kind -> declaration kind
DECL_KIND = {"mechanisms": "mechanism", "objects": "object", "scenes": "scene", "senses": "sense", "shapes": "shape",
             "actions": "action"}
# Only a real circuit is "fly" (teal). Everything that reads the game, decides, or draws is ours (orange).
ALLOWED_ORIGIN = {"mechanism": "fly", "sense": "invented", "action": "invented", "object": "invented", "character": "invented",
                  "shape": "invented", "scene": "invented"}
EVOLVABLE_IN = ("sense", "action", "shape")           # kinds whose dials evolution may tune
SRC = Path(__file__).resolve().parents[1]
WEIGHT_NAMES = {"W", "_W", "_Ws"}


@dataclass(frozen=True)
class Violation:
    rule: str
    subject: str
    message: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.subject}: {self.message}"


class Context:
    """What the checks need to know about the fly: its mechanisms and neuron groups."""

    def __init__(self, mechanisms: dict, groups: dict):
        self.mechanisms, self.groups = mechanisms, groups

    def cell_types(self, group_names) -> set:
        out = set()
        for n in group_names:
            g = self.groups.get(n)
            if g is not None:
                out |= set(g.types)
                if g.type_prefix:
                    out.add(g.type_prefix + "*")
        return out


def make_context() -> Context:
    from fly_mario_fly import registry
    from fly_mario_fly.fly.groups import load_groups
    return Context(registry.list_plugins("mechanisms"), load_groups())


def _mech_groups(mech) -> list:
    return list(mech.neuron_sets) + list(mech.input_groups) + list(mech.output_groups)


def check_declaration(expected_kind: str, name: str, plugin, decl, ctx: Context) -> list:
    """Every rule that looks at one plug-in and its declaration."""
    who = f"{expected_kind} '{name}'"
    v = lambda rule, msg: Violation(rule, who, msg)
    if not isinstance(decl, Declaration):
        return [v("R-DECLARED", "has no DECLARATION. Add `DECLARATION = declare(...)` next to PLUGIN saying what is real "
                                "(teal) and what is invented (orange).")]
    out = []
    if decl.kind != expected_kind:
        out.append(v("R-DECLARED", f"declares kind '{decl.kind}' but lives with the {expected_kind}s."))
    if decl.origin not in ORIGINS:
        out.append(v("R-DECLARED", f"origin must be 'fly' (teal) or 'invented' (orange), not '{decl.origin}'."))
    elif decl.kind in ALLOWED_ORIGIN and decl.origin != ALLOWED_ORIGIN[decl.kind]:
        why = "only a circuit read off the connectome is 'fly'" if ALLOWED_ORIGIN[decl.kind] == "invented" else \
              "a mechanism is real wiring, so it must be 'fly'"
        out.append(v("R-ORIGIN-KIND", f"a {decl.kind} must be '{ALLOWED_ORIGIN[decl.kind]}' (orange/teal rule): {why}."))
    if not decl.what.strip():
        out.append(v("R-DECLARED", "`what` is empty: say in one sentence what is real and what is invented."))

    needs_route = decl.origin == "fly" or decl.kind in ("sense", "action")
    route = decl.route
    if needs_route and route is None:
        out.append(v("R-FLY-ROUTE", "must cite the real route it rides on (Route(mechanism, cell_types, wiring))."))
    mech = None
    if route is not None:
        mech = ctx.mechanisms.get(route.mechanism)
        if mech is None:
            out.append(v("R-FLY-ROUTE", f"cites mechanism '{route.mechanism}', which does not exist "
                                        f"(known: {sorted(ctx.mechanisms)})."))
        elif not route.cell_types:
            out.append(v("R-FLY-ROUTE", "cites no cell types."))
        else:
            known = ctx.cell_types(_mech_groups(mech))
            unknown = sorted(set(route.cell_types) - known)
            if unknown:
                out.append(v("R-FLY-ROUTE", f"cites cell types {unknown} that mechanism '{route.mechanism}' does not use "
                                            f"(its cell types: {sorted(known)})."))

    if decl.kind == "sense":
        out += _check_sense(who, plugin, decl, mech, ctx)
    elif decl.kind == "action":
        out += _check_action(who, plugin, decl, mech)
    return out


def _check_sense(who, plugin, decl, mech, ctx) -> list:
    v = lambda rule, msg: Violation(rule, who, msg)
    out = []
    feeds = list(getattr(plugin, "feeds", []))
    if decl.route is not None and decl.route.mechanism not in feeds:
        out.append(v("R-SENSE-ROUTE", f"its route is '{decl.route.mechanism}' but the sense feeds {feeds}: a sense may only "
                                      f"ride the circuit it feeds."))
    if decl.drives:
        if mech is not None:
            bad = sorted(set(decl.drives) - set(mech.input_groups))
            if bad:
                out.append(v("R-SENSE-ROUTE", f"drives {bad}, which are not input groups of '{mech.name}' (input groups: "
                                              f"{list(mech.input_groups)}). Senses may only drive sensory input neurons; "
                                              f"descending and motor neurons cannot be driven."))
            missing = sorted(ctx.cell_types(decl.drives) - set(decl.route.cell_types))
            if missing:
                out.append(v("R-FLY-ROUTE", f"drives groups made of {missing} but its route does not cite those cell types."))
    elif sorted(decl.modulates) != sorted(getattr(plugin, "raises", [])) or not decl.modulates:
        out.append(v("R-SENSE-ROUTE", "drives no neuron group, so it must declare `modulates` = the modifiers it raises "
                                      f"({list(getattr(plugin, 'raises', []))}); a sense that does neither does nothing."))
    return out


def _check_action(who, plugin, decl, mech) -> list:
    v = lambda rule, msg: Violation(rule, who, msg)
    out = []
    src = list(getattr(plugin, "source_groups", []))
    if not decl.reads_groups or sorted(decl.reads_groups) != sorted(src):
        out.append(v("R-ACTION-SOURCE", f"declares reads_groups {list(decl.reads_groups)} but its source_groups are {src}. An "
                                        f"action decides only from the motor/descending neurons it declares."))
    if mech is not None:
        bad = sorted(set(decl.reads_groups) - set(mech.output_groups))
        if bad:
            out.append(v("R-ACTION-SOURCE", f"reads {bad}, which are not output (motor/descending) groups of '{mech.name}' "
                                            f"(outputs: {list(mech.output_groups)}). Actions may not read sensory neurons, game "
                                            f"state or anything else to decide."))
    if not decl.buttons or set(decl.buttons) - set(BUTTONS):
        out.append(v("R-ACTION-SOURCE", f"buttons {list(decl.buttons)} must be a non-empty subset of {list(BUTTONS)}."))
    if set(decl.game_reads) - set(GAME_READS):
        out.append(v("R-ACTION-SOURCE", f"game_reads {list(decl.game_reads)} not allowed; only {list(GAME_READS)}, each "
                                        f"justified in `what`."))
    if decl.game_reads and len(decl.what) < 40:
        out.append(v("R-ACTION-SOURCE", "uses game state, so `what` must explain why it is a mechanical constraint and not a decision."))
    return out


def check_knobs(expected_kind: str, name: str, plugin) -> list:
    """Dials: always invented (a dial can never claim to tune real wiring); evolvable only where evolution may tune."""
    out = []
    for k in getattr(plugin, "knobs", []) or []:
        who = f"{expected_kind} '{name}' dial '{k.key}'"
        if k.origin != "invented":
            out.append(Violation("R-DIALS", who, f"has origin '{k.origin}'. A dial scales a sense, cue or readout that we made "
                                                 f"up; tuning real wiring is not allowed, so a dial must be 'invented'."))
        if k.evolvable and expected_kind not in EVOLVABLE_IN:
            out.append(Violation("R-DIALS", who, f"is evolvable but belongs to a {expected_kind}. Evolution may tune only "
                                                 f"dials of {list(EVOLVABLE_IN)}."))
    return out


def _target_attrs(node):
    """Attribute names written by an assignment target (a.b = .., a.b[i] = .., del a.b[i])."""
    for t in ast.walk(node):
        if isinstance(t, ast.Attribute) and isinstance(t.ctx, (ast.Store, ast.Del)):
            yield t.attr, t
        if isinstance(t, ast.Subscript) and isinstance(t.ctx, (ast.Store, ast.Del)):
            for u in ast.walk(t.value):
                if isinstance(u, ast.Attribute):
                    yield u.attr, u


def scan_source(files, root: Path = SRC) -> list:
    """Static rules over source files (an iterable of Paths under `root`):

    R-NO-WEIGHT-WRITES  nothing assigns to a weight matrix (.W/._W/._Ws) except Brain.__init__ in fly/brain.py.
    R-NO-DIRECT-DRIVE   drive(...) / advance(h, I, ...) are called only from fly/ and runner/; senses/ and actions/ never
                        import the brain or the connectome."""
    out = []
    for path in files:
        rel = path.relative_to(root)
        area = rel.parts[0]
        tree = ast.parse(path.read_text(encoding="utf-8"))
        in_init = _functions_named(tree, "__init__") if rel.as_posix() == "fly/brain.py" else set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete)):
                targets = node.targets if isinstance(node, (ast.Assign, ast.Delete)) else [node.target]
                for tg in targets:
                    for attr, at in _target_attrs(tg):
                        if attr in WEIGHT_NAMES and id(at) not in in_init:
                            out.append(Violation("R-NO-WEIGHT-WRITES", f"{rel}:{node.lineno}",
                                                 f"writes to '{attr}'. Connectome weights are read-only: the wiring is untouched "
                                                 f"and only dials are tuned."))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                name, nargs = node.func.attr, len(node.args)
                if (name == "drive" or (name == "advance" and nargs >= 2)) and area not in ("fly", "runner"):
                    out.append(Violation("R-NO-DIRECT-DRIVE", f"{rel}:{node.lineno}",
                                         f"calls .{name}(...) outside fly/ and runner/. Only the runner moves the brain, and only "
                                         f"through declared senses."))
            if area in ("senses", "actions") and isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                       [node.module or ""] + [f"{node.module}.{a.name}" for a in node.names]
                for m in mods:
                    if m.startswith(("fly_mario_fly.fly.brain", "fly_mario_fly.fly.connectome")):
                        out.append(Violation("R-NO-DIRECT-DRIVE", f"{rel}:{node.lineno}",
                                             f"imports {m}. Senses and actions never touch the brain or the connectome; they only "
                                             f"return inputs or read rates."))
    return out


def _functions_named(tree, fname: str) -> set:
    """ids of every Attribute node inside any function called `fname` (so Brain.__init__ may set its own weights)."""
    ids = set()
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name == fname:
            ids |= {id(n) for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    return ids


def validate_all() -> list:
    """Run every check over the real repository. Returns a list of Violations (empty = all good)."""
    from fly_mario_fly import registry
    ctx = make_context()
    out, seen = [], {}
    for kind in registry.KINDS:
        for name, mod in registry.list_modules(kind).items():
            plugin = mod.PLUGIN
            ek = DECL_KIND[kind]
            declared = getattr(getattr(mod, "DECLARATION", None), "kind", None)
            if kind == "objects" and declared == "character":      # a creature plug-in lives with the objects
                ek = "character"
            out += check_declaration(ek, name, plugin, getattr(mod, "DECLARATION", None), ctx)
            out += check_knobs(ek, name, plugin)
            for k in getattr(plugin, "knobs", []) or []:
                if k.key in seen:
                    out.append(Violation("R-DIALS", f"{ek} '{name}' dial '{k.key}'", f"duplicates the dial of {seen[k.key]}."))
                seen[k.key] = f"{ek} '{name}'"
    out += scan_source(sorted(SRC.rglob("*.py")))
    return out
