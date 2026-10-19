"""Part L2b: per-level tile / enemy decoding (1-1 untouched) and the headroom function."""
import json
from pathlib import Path

import numpy as np
import pytest

from flyrun import knobs, level, senses_v2 as S
from flyrun.knobs import MAX_JUMP_HEIGHT

RUNS = Path(__file__).resolve().parents[1] / "runs"


def _ram(tiles=(), left=0):
    ram = np.zeros(0x800, dtype=np.uint8)
    for (x, row), t in dict(tiles).items():
        ram[level.BUF + level.PAGE_BYTES * ((x // 256) % 2) + 16 * row + (x % 256) // 16] = t
    ram[0x071A], ram[0x071C] = left // 256, left % 256
    return ram


def _floor(ram, x0, x1):
    for x in range(x0, x1, 16):
        for r in (11, 12):
            ram[level.BUF + level.PAGE_BYTES * ((x // 256) % 2) + 16 * r + (x % 256) // 16] = 84


def test_level_one_one_tables_are_exactly_the_old_ones(monkeypatch):
    monkeypatch.delenv("FLYRUN_LEVEL", raising=False)
    assert level.wall_tiles(False) == level.SOLID_WALL and level.wall_tiles(True) == level.SOLID_WALL | level.RIM_TILES
    assert knobs.enemy_types() == knobs.ENEMY_TYPES == {0x06: "goomba", 0x00: "koopa"}
    assert 82 not in level.wall_tiles(True)


def test_one_two_decodes_bricks_and_enemies(monkeypatch):
    monkeypatch.setenv("FLYRUN_LEVEL", "1-2")
    assert {82, 90, 92, 93, 94} <= level.wall_tiles(True)
    assert not ({28, 29, 30, 31, 32, 33} & level.wall_tiles(True))       # the exit pipe is a door, not a face ...
    assert {28, 29, 30, 31, 32, 33} <= level.ceiling_tiles()             # ... but it stops a rising head
    assert not ({36, 37, 194, 0} & level.ceiling_tiles())               # flagpole, coin, sky
    assert knobs.enemy_types()[0x03] == "koopa" and knobs.enemy_types()[0x0D] == "piranha"
    ram = _ram({(64, r): 82 for r in (8, 9, 10)})                        # a 3-high brick wall is a 48 px face in 1-2 ...
    assert level.scan_visible(ram, rim=True)[0] == [(64, 48)]
    monkeypatch.setenv("FLYRUN_LEVEL", "1-1")
    assert level.scan_visible(ram, rim=True)[0] == []                    # ... and nothing in 1-1


def test_piranha_is_clipped_at_its_pipe_rim(monkeypatch):
    monkeypatch.setenv("FLYRUN_LEVEL", "1-2")
    walls = [(48, 48), (64, 48)]                                          # a 3-high pipe: rim at y 128
    out = S.enemy_boxes([(0, 0x0D, 0, 56, 136)], walls)                   # fully out: RAM y 136 -> feet 128 = the rim
    assert len(out) == 1 and (out[0].top, out[0].h, out[0].w) == (104, 24, 16)
    half = S.enemy_boxes([(0, 0x0D, 0, 56, 148)], walls)                  # feet 140: 12 px of it are below the rim
    assert half[0].top == 116 and half[0].h == 12
    assert S.enemy_boxes([(0, 0x0D, 0, 56, 160)], walls) == []            # feet 152: head 128 = at the rim, nothing shows
    assert S.enemy_boxes([(0, 0x0D, 0x22, 56, 136)], walls) == []         # defeated
    assert S.enemy_boxes([(0, 0x0D, 0, 56, 136)], []) == []               # its pipe is not on screen yet: not seen
    monkeypatch.setenv("FLYRUN_LEVEL", "1-1")
    assert S.enemy_boxes([(0, 0x0D, 0, 56, 136)], walls) == []            # 1-1 never reads it
    monkeypatch.setenv("FLYRUN_LEVEL", "1-2")
    red = S.enemy_boxes([(0, 0x03, 0, 100, 184)], [])[0]
    assert (red.kind, red.w, red.h, red.top) == ("koopa", 16, 24, 152)


def test_headroom_open_ground_in_one_one(monkeypatch):
    monkeypatch.setenv("FLYRUN_LEVEL", "1-1")
    ram = _ram()
    _floor(ram, 0, 512)
    assert level.headroom(ram, 100, 112, 176, 16) == (0, MAX_JUMP_HEIGHT)          # no ceiling: a full jump
    low = _ram({(96, 7): 81})                                                      # a brick 48 px above his head... its underside is y 128; head 160 -> 32 px
    _floor(low, 0, 512)
    assert level.headroom(low, 100, 112, 176, 16) == (128, 32)
    assert level.headroom(low, 140, 152, 176, 16) == (0, MAX_JUMP_HEIGHT)          # a span next to it is open
    assert level.headroom(low, 90, 130, 176, 16) == (128, 32)                      # any column of the span counts
    big = level.headroom(low, 100, 112, 176, 24)                                   # big Mario: head 152 -> 24 px
    assert big == (128, 24)


def test_headroom_hanging_pillar_in_one_two():
    fx = RUNS / "L2b_fixture_1-2_x832_960.json"
    if not fx.exists():
        pytest.skip("fixture comes from python -m flyrun.l2b_structures")
    cols = json.loads(fx.read_text())
    ram = _ram({(int(x), r): t for x, col in cols.items() for r, t in enumerate(col) if t}, left=800)
    import os
    os.environ["FLYRUN_LEVEL"] = "1-2"
    try:
        # the x ~ 890 pillar of L2 (the death): its underside is at his head height -> no rise at all
        assert level.headroom(ram, 880, 892, 176, 16) == (160, 0)
        assert level.headroom(ram, 864, 896, 176, 16)[1] == 0
        assert level.headroom(ram, 876, 900, 176, 16) == (160, 0)                   # a span that only touches it still counts
        # open ground just after it (x 896-927): only the row-0 ceiling, whose underside is y 16: a full jump
        assert level.headroom(ram, 898, 910, 176, 16) == (16, MAX_JUMP_HEIGHT)
        # the brick platform at x 928-959 (rows 1-2 + row 7) leaves 32 px
        assert level.headroom(ram, 930, 942, 176, 16)[1] == 32
    finally:
        os.environ.pop("FLYRUN_LEVEL", None)
