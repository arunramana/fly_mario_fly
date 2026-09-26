"""MotorDirectModule and MbonReadoutModule (bridge/controller_modules.py)."""
import numpy as np

from bridge.controller_modules import MbonReadoutModule, MotorDirectModule, build_modules
from config.params import MbonReadoutParams, ModulesConfig, MotorDirectParams
from config.project_config import ProjectConfig
import dataclasses


def test_motor_drive_follows_ttmn_onset_and_releases():
    m = MotorDirectModule(MotorDirectParams())
    pressed = [m.update(ratio, 0.0) for ratio in [0, 0, 5, 10, 16, 16, 16, 16] + [16] * 40]
    assert not pressed[0] and not pressed[1]
    assert pressed[3]                       # onset drives A
    assert not pressed[-1]                  # a saturated (latched) TTMn does not hold A forever


def test_motor_rising_edge_and_suppression():
    m = MotorDirectModule(MotorDirectParams())
    assert m.rising(True) and not m.rising(True)     # only the first frame is a commit
    m.suppressed = True
    assert m.update(20.0, 0.0) is False              # a habituated (suppressed) commit drives nothing
    m.rising(False)
    assert m.suppressed is False                      # re-armed once the motor output drops


def test_dlmn_lengthens_the_hold():
    short, long_ = MotorDirectModule(MotorDirectParams()), MotorDirectModule(MotorDirectParams())

    def hold(m, dlmn):
        m.update(10.0, dlmn)
        n = 0
        while m.update(0.0, dlmn) and n < 500:
            n += 1
        return n
    assert hold(long_, 8.0) > hold(short, 0.0)


def test_readout_is_per_pathway_and_negative():
    m = MbonReadoutModule(MbonReadoutParams())
    m.weights = {g: np.array([1.0, 0.0]) for g in m.PATHWAYS}
    m.weights["mdn"] = np.array([0.0, 1.0])
    out = m.readout(np.array([2.0, 0.5]))
    assert out["dnp01"][0] == 2.0 and out["mdn"][0] == 0.5
    assert out["dnp01"][1] < 0 and out["mdn"][1] < 0


def test_modules_are_off_by_default_and_built_from_config():
    cfg = ProjectConfig()
    assert cfg.modules.motor_direct is None and cfg.modules.mbon_readout is None
    on = dataclasses.replace(cfg, modules=ModulesConfig(motor_direct=MotorDirectParams(),
                                                        mbon_readout=MbonReadoutParams()))
    assert {m.kind for m in build_modules(on)} == {"motor", "readout"}


def test_pathway_weights_are_normalised_and_cached():
    from fly.circuits.mbon_pathway_weights import CACHE
    if not CACHE.exists():
        return  # computed on first readout run (needs the 3.6 GB weights stream)
    z = np.load(CACHE)
    for g in ("dnp01", "dlmn", "dnp09", "mdn"):
        assert abs(z[g].sum() - 1.0) < 1e-6 and (z[g] >= 0).all()
    assert len(z["mid_ids"]) > 0


def test_brain_panel_shows_mbon_readout_only_when_columns_exist():
    import setuptools  # noqa: F401
    from config.params import MbonReadoutParams
    from config.project_config import load
    from render.brain_panel import _panel_context, panel_for_row
    from sim.project_runner import run_from_config
    cfg = load("projects/win_attempt/config.json")
    cfg = dataclasses.replace(cfg, scenario=dataclasses.replace(cfg.scenario, max_frames=80),
                              modules=dataclasses.replace(cfg.modules, mbon_readout=MbonReadoutParams()))
    tel, _ = run_from_config(cfg, "zz_readout_test.mp4", write_telemetry=False)
    tel = tel.fillna(0).reset_index(drop=True)
    ctx = _panel_context(tel)
    assert ctx["has_mbon"] and "MBONmid" in ctx["populations"]
    assert panel_for_row(tel, 40, ctx).size[0] > 0
    plain = tel.drop(columns=[c for c in tel.columns if c.startswith("mbon_")])
    assert not _panel_context(plain)["has_mbon"]


def test_mb_spatial_inputs_off_keeps_seven_kc_features_and_on_adds_two():
    import setuptools  # noqa: F401
    from bridge.full_policy import FullPolicy
    from config.params import MbSpatialInputParams
    off = FullPolicy(config=ProjectConfig())
    assert off.mb_proj.shape[1] == 7 and not off.mb_spatial
    cfg = dataclasses.replace(ProjectConfig(), modules=ModulesConfig(mb_spatial_inputs=MbSpatialInputParams()))
    on = FullPolicy(config=cfg)
    assert on.mb_proj.shape[1] == 9 and on.mb_spatial


def test_mb_spatial_perception_values():
    from bridge.controller_modules import MbSpatialInputModule, PerceptionContext, Stimulus
    from config.params import MbSpatialInputParams

    class NoEnemies:
        def enemy_records(self, ram):
            return []
    m = MbSpatialInputModule(MbSpatialInputParams())
    cfg = ProjectConfig()
    look = cfg.takeoff.gap_lookahead_tiles

    def edge_at(d):
        s = Stimulus()
        m.perceive(PerceptionContext(ram=None, mario_x=0, gap_w=0, distance_to_edge=d,
                                     config=cfg, registry=NoEnemies()), s)
        return s.mb_extra
    assert edge_at(None) == (0.0, 0.0)
    assert edge_at(1)[0] == 1.0                      # at the edge: full strength
    assert 0 < edge_at(look)[0] < edge_at(1)[0]      # weaker farther away


def test_motor_direct_releases_a_for_a_frame_on_landing_and_starts_fresh():
    m = MotorDirectModule(MotorDirectParams())
    assert m.params.release_on_landing is True                       # default on
    m.update(0.0, 0.0, player_state=0)
    for _ in range(3):
        m.update(10.0, 0.0, player_state=1)                          # airborne, drive high
    assert m.update(0.0, 0.0, player_state=1) is True
    assert m.update(5.0, 0.0, player_state=0) is False               # landed: A released this frame
    assert m.drive == 0.0                                            # so the next jump is a new press
    off = MotorDirectModule(MotorDirectParams(release_on_landing=False))
    for _ in range(3):
        off.update(10.0, 0.0, player_state=1)
    assert off.update(0.0, 0.0, player_state=0) is True              # off: unchanged behaviour
