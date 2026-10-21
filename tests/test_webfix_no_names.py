"""web/src never names a registered sense, object, shape, action or scene modifier: components render whatever the
registry says. Only api/mock.ts (the offline stand-in) may; types.ts is generated from the schema."""
import re
from pathlib import Path

from typing import get_args

from fly_mario import registry
from fly_mario.api.schemas import ClientMessage

SRC = Path(__file__).resolve().parents[1] / "web" / "src"
ALLOWED = {SRC / "api" / "mock.ts", SRC / "api" / "types.ts"}


def _names() -> set:
    """Registered names, minus the words of the live-stream protocol (the ClientMessage `step` is not the `step` object)."""
    protocol = set(get_args(ClientMessage.model_fields["type"].annotation))
    return {n for kind in ("senses", "objects", "actions", "shapes", "scenes") for n in registry.list_plugins(kind)} - protocol


def test_web_src_names_no_registered_plugin():
    names = _names()
    assert {"looming", "goomba", "jump"} <= names, "registry looks empty"
    pat = re.compile(r"""(?<=['"`])(""" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r""")(?=['"`])""")
    hits = []
    for f in sorted(SRC.rglob("*")):
        if f.suffix not in (".ts", ".tsx") or f in ALLOWED:
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            hits += [f"{f.relative_to(SRC)}:{i}: {m.group(1)}" for m in pat.finditer(line)]
    assert not hits, "plug-in names in web/src (put them in api/mock.ts or read them from the registry):\n" + "\n".join(hits)


def test_web_src_does_not_parse_death_strings():
    for f in SRC.rglob("*.tsx"):
        assert "enemy:" not in f.read_text(encoding="utf-8"), f
