"""The Luigi skin redraws the player on the game picture and leaves everything else alone."""
import numpy as np

from fly_mario_fly.render import skin

SKY = (92, 148, 252)


def _player(**kw):
    p = dict(x=100.0, y=160.0, w=12.0, h=16.0, big=False, airborne=False, facing=1, moving=False)
    return {**p, **kw}


def test_skin_replaces_player_and_keeps_background():
    game = np.zeros((240, 256, 3), np.uint8)
    game[:] = SKY
    game[200:204, 100:112] = (255, 0, 0)                   # stand-in for the stock player
    out = skin.apply(game, _player(), 0, 0)
    assert not (out[200:204, 100:112] == (255, 0, 0)).all(axis=-1).any()
    assert (out[:150] == SKY).all() and (game[200:204, 100:112] == (255, 0, 0)).all()   # input untouched


def test_every_pose_has_a_sprite():
    for size in ("small", "big"):
        for pose in ("stand", "walk", "jump"):
            assert skin._sprite(f"{size}_{pose}"), f"{size}_{pose}"
