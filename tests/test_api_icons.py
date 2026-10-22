"""Object icons: the crop rule, the scaling, and the endpoint (the emulator pass itself is stubbed; the e2e checks the real one)."""
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from fly_mario.api import icons
from fly_mario.api.app import create_app
from fly_mario.contracts import Box


def test_crop_is_in_screen_coordinates_with_the_status_bar_and_a_little_padding():
    assert icons.crop_box(Box(100, 160, 16, 16), 40) == (60 - icons.PAD, 192 - icons.PAD, 76 + icons.PAD, 208 + icons.PAD)
    assert icons.crop_box(Box(30, 160, 16, 16), 40) is None                  # starts left of the screen
    assert icons.crop_box(Box(290, 160, 16, 16), 40) is None                 # runs off the right edge
    assert icons.crop_box(Box(100, 200, 16, 16), 0) is None                  # below the picture


def test_a_tall_box_keeps_its_top_and_a_wide_one_its_middle():
    x0, y0, x1, y1 = icons.crop_box(Box(100, 0, 32, 96), 0)
    assert y1 - y0 == icons.MAX_SIDE + 2 * icons.PAD and y0 == icons.STATUS_BAR - icons.PAD
    x0, y0, x1, y1 = icons.crop_box(Box(40, 100, 160, 16), 0)
    assert x1 - x0 == 2 * icons.MAX_SIDE + 2 * icons.PAD and (x0 + x1) / 2 == 120


def test_icon_is_crisp_scaled_and_padded_transparent():
    crop = np.zeros((24, 16, 3), np.uint8)
    crop[:, :8] = (10, 20, 30)
    crop[:, 8:] = (200, 100, 50)
    out = icons.to_icon(crop)
    assert out.shape == (icons.ICON, icons.ICON, 4)
    assert out[icons.ICON // 2, icons.ICON // 2 - 1, :3].tolist() == [30, 20, 10]            # BGR, nearest-neighbour: no blended colours
    assert {tuple(p[:3]) for p in out[out[..., 3] > 0].reshape(-1, 4)} == {(30, 20, 10), (50, 100, 200)}
    assert out[0, 0, 3] == 0 and out[icons.ICON // 2, 0, 3] == 0                              # padding is transparent


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(icons, "icons_dir", lambda: tmp_path / "icons")
    monkeypatch.setattr(icons, "_tried", set())
    return TestClient(create_app(flies_dir=tmp_path / "flies", runs_folder=tmp_path / "runs")), tmp_path


def test_registry_gives_every_object_an_icon_url(client):
    c, _ = client
    objs = c.get("/registry").json()["objects"]
    assert objs and all(o["icon"] == f"/objects/{o['name']}/icon.png" for o in objs)


def test_icon_endpoint_serves_the_cached_png_and_404s_when_it_cannot_make_one(client, monkeypatch):
    c, tmp = client
    (tmp / "icons").mkdir()
    ok, buf = cv2.imencode(".png", icons.to_icon(np.full((16, 16, 3), 90, np.uint8)))
    (tmp / "icons" / "goomba.png").write_bytes(buf.tobytes())
    r = c.get("/objects/goomba/icon.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"
    calls = []
    monkeypatch.setattr(icons, "make_icons", lambda names: calls.append(names) or {})
    assert c.get("/objects/pipe/icon.png").status_code == 404                  # nothing could be made: the page shows a square
    assert c.get("/objects/pipe/icon.png").status_code == 404
    assert len(calls) == 1, "a failed pass is not repeated on every request"
    assert c.get("/objects/nonsense/icon.png").status_code == 404
