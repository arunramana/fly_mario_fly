"""Lite settings: two requests that play the same game get the same key, and anything the lite server does not do is refused."""
import pytest
from lite_support import config, request

from fly_mario_fly.api import schemas as S
from fly_mario_fly.lite.settings import Refused, canonicalize


@pytest.fixture
def cfg(tmp_path):
    return config(tmp_path)


def key(req, cfg, version="v"):
    return canonicalize(req, cfg).key(version)


def test_same_game_same_key_whatever_the_order(cfg):
    a = request(attachments={"looming": ["goomba", "koopa"]}, actions=("walk", "steer"))
    b = request(attachments={"looming": ["koopa", "goomba"]}, actions=("steer", "walk"))
    assert key(a, cfg) == key(b, cfg)


def test_the_fly_name_and_provenance_do_not_matter(cfg):
    a, b = request(), request()
    b.fly.name, b.fly.provenance = "something else", {"source": "me"}
    assert key(a, cfg) == key(b, cfg)


def test_knobs_are_rounded_so_nearly_equal_sliders_share_a_run(cfg):
    from fly_mario_fly.api import knobs as K
    k = next(iter(sorted(K.specs_by_key())))
    a, b = request(knobs={k: 0.50012}), request(knobs={k: 0.50049})
    assert key(a, cfg) == key(b, cfg)
    assert key(a, cfg) != key(request(knobs={k: 0.52}), cfg)
    assert canonicalize(a, cfg).fly["knobs"][k] == 0.5


def test_different_games_get_different_keys(cfg):
    base = key(request(), cfg)
    assert key(request(level="1-2"), cfg) != base
    assert key(request(mods=("no_enemies",)), cfg) != base
    assert key(request(actions=("walk",)), cfg) != base
    assert key(request(dials="original"), cfg) != base
    assert key(request(max_frames=300), cfg) != base


def test_the_version_is_part_of_the_key(cfg):
    s = canonicalize(request(), cfg)
    assert s.key("a") != s.key("b")


def test_frame_cap_is_applied_and_shared(cfg):
    big = canonicalize(request(max_frames=99999), cfg)
    assert big.max_frames == cfg.max_frames
    assert key(request(max_frames=99999), cfg) == key(request(max_frames=cfg.max_frames), cfg)


def test_noise_and_seed_are_fixed_by_the_server(cfg):
    req = request()
    req.scene.sigma, req.scene.seed, req.scene.noop = 0.7, 12345, 99
    sc = canonicalize(req, cfg).scene(cfg)
    assert (sc.sigma, sc.seed, sc.noop, sc.start) == (0.0, cfg.seed, cfg.noop, "level_start")
    assert key(req, cfg) == key(request(), cfg)


@pytest.mark.parametrize("bad, why", [
    (dict(level="8-4"), "not offered"),
    (dict(level="nope"), "not offered"),
    (dict(mods=("keep_only",)), "not available"),
    (dict(mods=("no_such_modifier",)), "unknown scene modifier"),
    (dict(from_moment="abc"), "moments"),
])
def test_refused(cfg, bad, why):
    with pytest.raises(Refused, match=why):
        canonicalize(request(**bad), cfg)


def test_a_moment_start_is_refused(cfg):
    req = request()
    req.scene.start = "some-moment-id"
    with pytest.raises(Refused, match="level start"):
        canonicalize(req, cfg)
    req.scene.start = 1500
    with pytest.raises(Refused, match="level start"):
        canonicalize(req, cfg)


def test_unknown_sense_or_action_or_knob_is_an_error(cfg):
    with pytest.raises(ValueError):
        canonicalize(request(attachments={"no_such_sense": ["goomba"]}), cfg)
    with pytest.raises(ValueError):
        canonicalize(request(actions=("no_such_action",)), cfg)
    with pytest.raises(ValueError):
        canonicalize(request(knobs={"no.such.knob": 0.5}), cfg)


def test_the_canonical_fly_is_a_valid_dto(cfg):
    s = canonicalize(request(attachments={"looming": ["goomba"]}), cfg)
    assert isinstance(s.fly_dto(), S.FlyDTO)
    assert s.fly_dto().name == "lite"
