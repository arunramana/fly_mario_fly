"""The web app lists things in a fixed order (enemies, objects, power-ups); keep that order in step with the registered plug-ins."""
import re
from pathlib import Path

from fly_mario_fly import registry

TS = (Path(__file__).resolve().parents[1] / "web" / "src" / "components" / "senseUtil.ts").read_text(encoding="utf-8")
EXPECTED = {
    "enemies": ["goomba", "koopa", "piranha", "hammer_bro", "buzzy_beetle", "podoboo", "red_koopa"],
    "objects": ["pipe", "step", "pit", "qblock", "usedblock", "brick", "ceiling_block"],
    "powerups": ["mushroom", "fire_flower", "one_up", "star", "coin"],
}
KINDS = {"enemies": {"enemy"}, "objects": {"terrain", "obstacle"}, "powerups": {"pickup"}}


def order_in_ts():
    block = re.search(r"OBJECT_ORDER[^=]*=\s*\{(.*?)\n\}", TS, re.S).group(1)
    return {m.group(1): re.findall(r"'([a-z_0-9]+)'", m.group(2)) for m in re.finditer(r"(\w+):\s*\[(.*?)\]", block, re.S)}


def test_the_display_order_is_the_requested_one():
    assert order_in_ts() == EXPECTED


def test_every_name_is_a_registered_plugin_in_the_tab_its_kind_belongs_to():
    plugins = registry.list_plugins("objects")
    for tab, names in EXPECTED.items():
        for n in names:
            assert plugins[n].kind in KINDS[tab], (tab, n, plugins[n].kind)


def test_every_registered_object_is_listed_so_nothing_falls_to_the_end_unnoticed():
    listed = {n for names in EXPECTED.values() for n in names}
    assert set(registry.list_plugins("objects")) == listed, "add the new plug-in to OBJECT_ORDER in web/src/components/senseUtil.ts"


def test_the_screens_use_the_order():
    root = Path(__file__).resolve().parents[1] / "web" / "src" / "screens"
    assert "byObjectOrder(reg.objects.filter((o) => tabOf(o) === tab))" in (root / "FlyScreen.tsx").read_text(encoding="utf-8")
    assert "byObjectOrder(reg.objects.filter((o) => m.on_screen" in (root / "MomentScreen.tsx").read_text(encoding="utf-8")
    assert "objectRank(a) - objectRank(b)" in (root / "SceneScreen.tsx").read_text(encoding="utf-8")
