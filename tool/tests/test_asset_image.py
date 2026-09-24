"""tool/SPEC_ui_retro.md section 9: load_asset(asset_id) -> QPixmap always
returns something displayable -- a real image, or the placeholder, never
a crash -- whether the id is unknown, the manifest names a missing file,
or (implicitly, same code path) a corrupt one.
"""
from __future__ import annotations

from tool.ui.widgets.asset_image import PLACEHOLDER_PATH, load_asset


def test_unknown_asset_id_falls_back_to_placeholder(qapp):
    pixmap = load_asset("no_such_card")
    assert not pixmap.isNull()
    placeholder = load_asset("__also_unknown__")
    assert pixmap.toImage() == placeholder.toImage()


def test_manifest_entry_naming_a_missing_file_falls_back_to_placeholder(qapp, monkeypatch):
    import tool.ui.widgets.asset_image as asset_image
    monkeypatch.setattr(asset_image, "_manifest_cache", {"ghost_card": "nowhere/ghost.png"})
    pixmap = asset_image.load_asset("ghost_card")
    placeholder = asset_image.load_asset("__unknown__")
    assert pixmap.toImage() == placeholder.toImage()


def test_placeholder_file_exists_on_disk():
    assert PLACEHOLDER_PATH.exists()


def test_a_real_manifest_entry_loads_its_own_file_when_present(qapp, monkeypatch, tmp_path):
    import tool.ui.widgets.asset_image as asset_image
    real_file = tmp_path / "real.png"
    from PIL import Image
    Image.new("RGB", (8, 8), (255, 0, 0)).save(real_file)
    monkeypatch.setattr(asset_image, "ASSETS_ROOT", tmp_path)
    monkeypatch.setattr(asset_image, "_manifest_cache", {"real_card": "real.png"})
    pixmap = asset_image.load_asset("real_card")
    placeholder = asset_image.load_asset("__unknown__")
    assert pixmap.toImage() != placeholder.toImage()
