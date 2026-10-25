"""The reproducibility files agree with each other: pyproject pins vs requirements.txt, and the demo/download scripts import."""
import importlib.util
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _requirements():
    pins = {}
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+)==(\S+)$", line.strip())
        if m:
            pins[m.group(1).lower().replace("_", "-")] = m.group(2)
    return pins


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_exact_pin_in_pyproject_is_the_same_in_requirements_txt():
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    pins = _requirements()
    for d in deps:
        m = re.match(r"^([A-Za-z0-9_.-]+)==(\S+)$", d)
        if m:
            assert pins.get(m.group(1).lower().replace("_", "-")) == m.group(2), d


def test_requirements_txt_keeps_the_emulator_and_numpy_pins():
    pins = _requirements()
    assert pins["nes-py"] == "8.2.1" and pins["gym-super-mario-bros"] == "7.4.0" and pins["gym"] == "0.23.1"
    assert pins["numpy"].startswith("1.26.")


def test_demo_script_uses_a_fixed_seed_and_a_flies_config_that_exists():
    demo = _load("demo")
    assert demo.ARGS[demo.ARGS.index("--seed") + 1] == "101"
    assert (ROOT / "configs" / "flies" / f"{demo.ARGS[1]}.yaml").exists()


def test_download_script_imports_and_has_a_help():
    dl = _load("download_data")
    assert callable(dl.main)


def test_the_optional_mcp_extra_is_pinned_like_requirements_txt():
    extras = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["optional-dependencies"]
    assert extras["mcp"] == [f"mcp=={_requirements()['mcp']}"]


def test_evaluate_script_imports_and_needs_flies():
    ev = _load("evaluate")
    assert callable(ev.main)
    with pytest.raises(SystemExit):
        ev.main([])                                   # argparse: at least one fly name is required
