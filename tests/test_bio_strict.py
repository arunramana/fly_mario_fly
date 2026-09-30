# What this file does, in plain English:
# Checks the "honest fly" mode (docs/SPEC_bio_strict.md): with it off nothing changes; with
# it on the fly only sees what is on the screen and ahead of it (off-screen, behind and
# far-above enemies give no looming, both eyes get the same frontal looming), nothing
# injects a jump or pit signal, the two self-sustaining loops are gone, a tonic muscle
# level cannot hold the jump button, and walking is a muscle that can be switched off.
"""bio_strict: senses, stripped injections, dynamics, motor model."""
from __future__ import annotations

import dataclasses
import math
from types import SimpleNamespace

import numpy as np
import pytest

from bridge.controller_modules import MotorDirectModule, PerceptionContext, Stimulus
from bridge.full_policy import FullPolicy
from bridge.perception import VisibleRegistry, bio_enemy_thetas
from config.bio_strict import effective
from config.params import (BioStrictParams, ModulesConfig, MotorDirectParams, WallAheadParams)
from config.project_config import ProjectConfig
from fly.network import dynamics
from mario.entities.registry import KindRegistry
from mario.ram import screen, tile_ram
from mario.ram.addresses import (ADDR_ENEMY_ACTIVE, ADDR_ENEMY_PAGE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X, ADDR_ENEMY_Y,
                                 ADDR_MARIO_PAGE, ADDR_MARIO_X)

BIO = BioStrictParams()
GOOMBA = 0x06
PREV = {"L": 0.0, "R": 0.0}


def _ram(mario_x=100, left=0, enemies=(), mario_y=176):
    """A synthetic RAM: screen left edge `left`, Mario at level x `mario_x` (drawn at mario_x - left),
    enemies = [(abs_x, y)] placed in slots 0.."""
    ram = np.zeros(0x800, dtype=np.uint8)
    ram[0x071A], ram[0x071C] = left // 256, left % 256
    ram[ADDR_MARIO_PAGE], ram[ADDR_MARIO_X] = mario_x // 256, mario_x % 256
    ram[0x03AD] = mario_x - left
    ram[0x00CE] = mario_y
    for slot, (x, y) in enumerate(enemies):
        ram[ADDR_ENEMY_ACTIVE + slot] = 1
        ram[ADDR_ENEMY_TYPE + slot] = GOOMBA
        ram[ADDR_ENEMY_PAGE + slot], ram[ADDR_ENEMY_X + slot] = x // 256, x % 256
        ram[ADDR_ENEMY_Y + slot] = y
    return ram


def _theta(ram):
    return bio_enemy_thetas(ram, PREV, KindRegistry(), BIO)


def test_off_by_default_and_effective_is_identity():
    c = ProjectConfig()
    assert c.bio_strict is False and effective(c) is c


def test_only_onscreen_frontal_enemies_loom_equally_in_both_eyes():
    ahead = _theta(_ram(enemies=[(150, 176)]))
    assert ahead[0]["L"] == ahead[0]["R"] > 0 and ahead[2]["L"] == ahead[2]["R"] == 50     # same in both hemispheres
    assert math.isclose(ahead[0]["R"], 2 * math.atan(16 / (2 * 50)))                         # level: full angular size
    assert _theta(_ram(enemies=[(60, 176)]))[0] == {"L": 0.0, "R": 0.0}                     # behind: no looming
    off = _ram(mario_x=400, left=300, enemies=[(400 + 300, 176)])                             # drawn at x=400 > 255
    assert _theta(off)[0] == {"L": 0.0, "R": 0.0}                                            # ahead but off screen
    assert _theta(_ram(enemies=[(150, 176 - 100)]))[0] == {"L": 0.0, "R": 0.0}              # 63 deg above the horizon
    tilted = _theta(_ram(enemies=[(150, 176 - 25)]))[0]["R"]                                # 26.6 deg: reduced, not removed
    assert 0 < tilted < ahead[0]["R"]
    assert _theta(_ram(mario_x=300, left=200, enemies=[(300 + 40, 176)]))[0]["R"] > 0       # page-corrected across 256


def test_visible_registry_hides_offscreen_enemies():
    ram = _ram(mario_x=400, left=300, enemies=[(420, 176), (800, 176)])
    recs = VisibleRegistry(KindRegistry()).enemy_records(ram)
    assert recs[0].active and not recs[1].active


def test_tile_cues_are_limited_to_the_screen():
    ram = np.zeros(0x800, dtype=np.uint8)
    ram[0x03AD] = 192                                   # drawn in column 12
    ram[ADDR_MARIO_X] = 192
    for col in (13, 15):
        ram[tile_ram.BUF1_ADDR + 7 * 16 + col] = tile_ram.QUESTION_COIN_ID
    ram[tile_ram.BUF2_ADDR + 7 * 16 + 2] = tile_ram.QUESTION_COIN_ID       # abs column 18: beyond the right edge
    assert 6 in tile_ram.question_blocks_near(ram)
    assert tile_ram.question_blocks_near(ram, visible_only=True) == [1, 3]
    assert [k for k, _h in tile_ram.question_blocks_ahead(ram, 8, visible_only=True)] == [1, 3]


def test_effective_strips_injected_control_and_scales_the_dynamics():
    md = MotorDirectParams(adapt_frames=0.0, buttons=True)
    cfg = dataclasses.replace(ProjectConfig(), bio_strict=True, modules=ModulesConfig(
        motor_direct=md, wall_ahead=WallAheadParams(looming_gain=1.0, takeoff_gain=0.5)))
    e = effective(cfg)
    assert e.modules.wall_ahead.takeoff_gain == 0.0 and e.modules.wall_ahead.looming_gain == 1.0   # visual route kept
    assert e.takeoff.gap_gain == 0.0 and e.modules.gap_ahead is None
    assert not any(dataclasses.asdict(e.rules).values()) and not e.scenario.graded_pit_response
    assert (e.network.clip, e.jump.spike_amp) == (BIO.clip_hz, BIO.spike_amp_hz) == (200.0, 60.0)
    assert e.modules.motor_direct.adapt_frames == BIO.adapt_frames and e.modules.motor_direct.buttons is False
    assert e.modules.dnp01_refractory.refractory_steps == e.modules.dnp02_refractory.refractory_steps == 3
    assert e.modules.page_perception is not None
    with pytest.raises(ValueError, match="motor_direct"):
        effective(dataclasses.replace(ProjectConfig(), bio_strict=True))


def test_a_tonic_muscle_level_cannot_hold_a_but_a_fresh_rise_presses_it():
    m = MotorDirectModule(dataclasses.replace(effective(dataclasses.replace(
        ProjectConfig(), bio_strict=True, modules=ModulesConfig(motor_direct=MotorDirectParams()))).modules.motor_direct,
        a_threshold=1.0, dlmn_gain=1.0, release_on_landing=False))
    pressed = [m.update(0.0, 2.0) for _ in range(300)]          # tonic DLMn, no rise
    assert pressed[0] and not any(pressed[200:])                  # the onset presses, the tonic level releases
    assert m.update(6.0, 2.0)                                     # a fresh TTMn rise presses again


def _strict_policy(**kw):
    md = MotorDirectParams(a_threshold=4.0, decay=0.7, dlmn_gain=1.0)
    cfg = dataclasses.replace(ProjectConfig(), bio_strict=True, modules=ModulesConfig(motor_direct=md), **kw)
    p = FullPolicy(config=cfg, level="1-1")
    p.reset(0)
    return p


def _noise():
    return dynamics.NoiseConfig(0.0, np.random.default_rng(0))


def test_neither_loop_sustains_itself_at_zero_input():
    """audit D1/D2: the jump network's zero-input latch (TTMn pinned at the clip) and the DNp02<->pIP1 latch are gone."""
    p = _strict_policy()
    net, noise = p.jump_network, _noise()

    def drive(l2, l4):
        I = np.zeros(p.Kj)
        for s in "LR":
            I[p.j_msk[f"LPLC2_{s}"]], I[p.j_msk[f"LC4_{s}"]] = l2, l4
        return I
    for _ in range(10):
        for _ in range(p.substeps):
            net.step(drive(8.0, 1.5), noise=noise)
    tt = []
    for _ in range(150):
        for _ in range(p.substeps):
            h = net.step(drive(0.0, 0.0), noise=noise)
        tt.append(max(h[p.j_msk["TTMn_L"]].mean(), h[p.j_msk["TTMn_R"]].mean()))
    assert max(tt[-30:]) < 1e-6          # decays away (no denormal flush in the jump net, so not exactly 0)
    net2 = p.dnp02_network

    def d2(x):
        I = np.zeros(p.Kdp)
        I[p.dnp02_lc4_l] = I[p.dnp02_lc4_r] = x
        return I
    for _ in range(8):
        for _ in range(p.substeps):
            net2.step(d2(5.0), noise=noise)
    v = []
    for _ in range(120):
        for _ in range(p.substeps):
            h = net2.step(d2(0.0), noise=noise)
        v.append(h[p.dnp02_idx].mean())
    assert max(v[-30:]) < 1e-6


def test_walking_is_a_muscle_that_can_be_switched_off():
    import mario.emulator.env as mario_env
    from mario.actions.actions import buttons_of
    env = mario_env.make_env("1-1")
    env.reset()
    ram = env.unwrapped.ram
    p = _strict_policy()
    b = buttons_of(p.act(SimpleNamespace(ram=ram)))
    assert b["right"] and not b["left"]                          # DNp09 drive walks Mario right
    q = _strict_policy(speed=dataclasses.replace(ProjectConfig().speed, walk_drive=0.0))
    b = buttons_of(q.act(SimpleNamespace(ram=ram)))
    assert not b["right"] and not b["left"]                      # no DNp09 activity: no walking press at all
    env.close()


def test_a_strict_run_builds_and_runs():
    import run_steering
    md = MotorDirectParams(a_threshold=4.0, decay=0.7, dlmn_gain=1.0)
    cfg = dataclasses.replace(ProjectConfig(), bio_strict=True, modules=ModulesConfig(motor_direct=md))
    tel, info = run_steering.main(out_mp4="IGNORED_bio.mp4", record_video=False, write_telemetry=False, level="1-1",
                                  max_frames=120, sigma=0.0, seed=0, config=cfg)
    assert len(tel) == 120 and np.isfinite(tel["ttmn"]).all()
