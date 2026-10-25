"""Discover plug-ins by folder: every module in a package exposes one object named PLUGIN."""
from __future__ import annotations

import importlib
import importlib.util
import pkgutil
from pathlib import Path

KINDS = {
    "mechanisms": "fly_mario_fly.fly.mechanisms",
    "objects": "fly_mario_fly.mario.objects",
    "scenes": "fly_mario_fly.mario.scenes",
    "senses": "fly_mario_fly.senses",
    "shapes": "fly_mario_fly.senses.shapes",
    "actions": "fly_mario_fly.actions",
}


def load_package(package: str) -> dict:
    """Import every module of an installed package; return {plug-in name: PLUGIN}."""
    pkg = importlib.import_module(package)
    return _collect(pkg.__path__, package + ".", importlib.import_module)


def load_folder(folder: Path) -> dict:
    """Same as load_package for a bare folder of .py files (tests, scratch)."""
    def _load(name: str):
        spec = importlib.util.spec_from_file_location(name, Path(folder) / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return _collect([str(folder)], "", _load)


def list_plugins(kind: str) -> dict:
    """Plug-ins of one kind (a key of KINDS), by name."""
    return load_package(KINDS[kind])


def list_modules(kind: str) -> dict:
    """Like list_plugins, but returns {plug-in name: its module}: the module also holds the plug-in's DECLARATION."""
    package = KINDS[kind]
    pkg = importlib.import_module(package)
    out = {}
    for info in pkgutil.iter_modules(pkg.__path__):
        if not info.ispkg:
            mod = importlib.import_module(package + "." + info.name)
            out[mod.PLUGIN.name] = mod
    return out


def _collect(paths, prefix: str, importer) -> dict:
    found: dict = {}
    for info in pkgutil.iter_modules(paths):
        if info.ispkg:  # sub-folders (e.g. senses/shapes) are their own kind
            continue
        mod = importer(prefix + info.name)
        plugin = getattr(mod, "PLUGIN", None)
        if plugin is None:
            raise ValueError(f"{prefix + info.name}: no PLUGIN")
        if plugin.name in found:
            raise ValueError(f"duplicate plug-in name {plugin.name!r} in {prefix + info.name}")
        found[plugin.name] = plugin
    return found
