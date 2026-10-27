"""The lite image's files: its pins are the tested pins, and it leaves out what the lite server must not need."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pins(path):
    out = {}
    for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            name, version = line.strip().split("==")
            out[name.lower().replace("_", "-")] = version
    return out


def test_lite_pins_are_the_tested_pins():
    full, lite = pins("requirements.txt"), pins("deploy/lite/requirements.txt")
    assert lite and set(lite) <= set(full)
    assert {n: v for n, v in lite.items() if full[n] != v} == {}


def test_lite_leaves_out_the_data_and_search_stack():
    lite = pins("deploy/lite/requirements.txt")
    for heavy in ("pandas", "pyarrow", "cma", "httpx", "websockets", "mcp", "pytest", "jupyter"):
        assert heavy not in lite


def test_the_lite_image_runs_the_lite_module_with_a_bundle_and_no_data():
    d = (ROOT / "deploy/lite/Dockerfile").read_text(encoding="utf-8")
    assert "fly_mario_fly.lite" in d and "FMF_LITE_BUNDLE" in d
    assert "FLY_MARIO_FLY_DATA" not in d
    assert "USER app" in d                                  # not root


def test_the_bundle_is_not_committed():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"^deploy/lite/bundle/$", ignore, re.M)


def test_every_setting_is_documented():
    code = (ROOT / "src/fly_mario_fly/lite/config.py").read_text(encoding="utf-8")
    names = set(re.findall(r'_env\("([A-Z_]+)"', code))
    doc = (ROOT / "docs/lite.md").read_text(encoding="utf-8")
    assert names and all(f"`{n}`" in doc for n in names), [n for n in names if f"`{n}`" not in doc]
