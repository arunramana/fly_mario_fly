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
    return TestClient(create_app(flies_dir=tmp_path / "flies", runs_folder=tmp_path / "runs")), tmp_path


def test_registry_gives_every_object_an_icon_url(client):
    c, _ = client
    objs = c.get("/registry").json()["objects"]
    assert objs and all(o["icon"] == f"/objects/{o['name']}/icon.png" for o in objs)


def test_icon_endpoint_serves_the_cached_png_and_answers_404_at_once_when_it_is_not_ready(client, monkeypatch):
    c, tmp = client
    (tmp / "icons").mkdir()
    ok, buf = cv2.imencode(".png", icons.to_icon(np.full((16, 16, 3), 90, np.uint8)))
    (tmp / "icons" / "goomba.png").write_bytes(buf.tobytes())
    r = c.get("/objects/goomba/icon.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[1:4] == b"PNG"
    monkeypatch.setattr(icons, "make_icons", lambda names: pytest.fail("a request must never run the emulator"))
    assert c.get("/objects/pipe/icon.png").status_code == 404                  # not made yet: the page shows a square
    assert c.get("/objects/nonsense/icon.png").status_code == 404


def test_the_background_colour_is_transparent_and_found_below_the_status_bar():
    screen = np.zeros((240, 256, 3), np.uint8)
    screen[icons.STATUS_BAR:] = (92, 148, 252)
    screen[100:116, 100:116] = (200, 50, 50)                                  # a sprite
    bg = icons.background(screen)
    assert bg == (92, 148, 252)
    out = icons.to_icon(screen[96:120, 96:120], bg)
    assert out[..., 3].min() == 0 and out[..., 3].max() == 255
    assert (out[out[..., 3] > 0][:, :3] == (50, 50, 200)).all()               # only the sprite is opaque (BGR)


def test_a_pipe_crop_covers_both_columns_and_a_sprite_keeps_a_two_pixel_margin():
    x0, y0, x1, y1 = icons.crop_box(Box(100, 100, 32, 48), 0)
    assert x0 <= 100 - icons.PAD and x1 >= 132 + icons.PAD
    x0, y0, x1, y1 = icons.crop_box(Box(100, 100, 16, 16), 0, icons.SPRITE_PAD)
    assert (x0, x1) == (98, 118) and icons.SPRITE_PAD == 2


def test_a_mapped_sprite_is_fitted_keeping_its_aspect_and_a_missing_one_gives_none(tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.setattr(icons, "sprites_dir", lambda: tmp_path)
    monkeypatch.setattr(icons, "MAP", tmp_path / "icons.yaml")
    (tmp_path / "icons.yaml").write_text('wide: "w.png"\nabsent: "nope.png"\n')
    img = np.zeros((10, 20, 4), np.uint8)
    img[..., 0], img[..., 3] = 255, 255                                       # opaque red, 20 x 10
    Image.fromarray(img).save(tmp_path / "w.png")
    out = icons.sprite_icon("wide")
    assert out.shape == (icons.ICON, icons.ICON, 4)
    assert out[icons.ICON // 2, 4, 3] == 255 and out[icons.ICON // 2, 3, 3] == 0   # 20 px x2 = 40: 4 px free each side
    assert out[0, 0, 3] == 0 and out[icons.MARGIN, icons.ICON // 2, 3] == 0   # half height: transparent above
    assert out[icons.ICON // 2, icons.ICON // 2, :3].tolist() == [0, 0, 255]                # BGR
    assert icons.sprite_icon("absent") is None and icons.sprite_icon("unmapped") is None


def test_a_sprite_is_scaled_by_a_whole_factor_with_a_two_pixel_margin():
    for h, w, k in ((16, 16, 2), (24, 16, 1), (20, 20, 2)):                     # 44 px fit: 16 -> x2, 24 -> x1 (x2 = 48 would touch)
        out = icons.to_icon(np.full((h, w, 3), 90, np.uint8))
        ys, xs = np.nonzero(out[..., 3])
        assert (ys.max() - ys.min() + 1, xs.max() - xs.min() + 1) == (h * k, w * k)
        assert min(ys.min(), xs.min(), icons.ICON - 1 - ys.max(), icons.ICON - 1 - xs.max()) >= icons.MARGIN
