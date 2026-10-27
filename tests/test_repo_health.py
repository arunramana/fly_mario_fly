"""The repo-health files are in place and keep the names branch rules depend on."""
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GH = ROOT / ".github"


def ci():
    return yaml.safe_load((GH / "workflows" / "ci.yml").read_text(encoding="utf-8"))


def test_ci_jobs_have_the_stable_names_branch_rules_require():
    jobs = ci()["jobs"]
    assert set(jobs) == {"python", "web", "rules"}
    assert all(job["name"] == key for key, job in jobs.items())          # the check name equals the job id: what a ruleset lists


def test_ci_is_least_privilege_and_bounded():
    wf = ci()
    assert wf["permissions"] == {"contents": "read"}
    assert all("timeout-minutes" in job for job in wf["jobs"].values())
    assert wf["concurrency"]["cancel-in-progress"] is True
    assert "pull_request" in wf[True]                                    # PyYAML reads the key `on` as True


def test_ci_never_points_the_tests_at_the_data_and_never_downloads_it():
    text = (GH / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "FLY_MARIO_FLY_DATA" in text and not re.search(r"^\s*FLY_MARIO_FLY_DATA\s*:", text, re.M)     # only mentioned in a comment
    assert "download_data" not in text and "build-brains" not in text


def test_ci_actions_are_official_and_pinned_to_a_major_version():
    for use in re.findall(r"uses:\s*(\S+)", (GH / "workflows" / "ci.yml").read_text(encoding="utf-8")):
        assert use.startswith("actions/") and re.search(r"@v\d+$", use), use


def test_the_rules_job_runs_the_validator():
    steps = " ".join(s.get("run", "") for s in ci()["jobs"]["rules"]["steps"])
    assert "python -m fly_mario_fly.rules validate" in steps


def test_dependabot_covers_every_ecosystem_and_protects_the_pins():
    cfg = yaml.safe_load((GH / "dependabot.yml").read_text(encoding="utf-8"))
    assert {u["package-ecosystem"] for u in cfg["updates"]} == {"pip", "npm", "github-actions"}
    assert {u["directory"] for u in cfg["updates"]} == {"/", "/web"}
    pip = next(u for u in cfg["updates"] if u["package-ecosystem"] == "pip")
    ignored = {i["dependency-name"] for i in pip["ignore"]}
    assert {"numpy", "gym", "nes-py", "gym-super-mario-bros", "opencv-python-headless", "scipy", "pyarrow", "pyglet", "contourpy"} <= ignored


def test_every_numpy_bound_ignore_matches_a_real_constraint():
    """The ignores exist because numpy stays below 1.27; if that ever changes, these ignores must be revisited."""
    import tomllib
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    assert any(d.replace(" ", "").startswith("numpy") and "<1.27" in d.replace(" ", "") for d in deps)
    cfg = yaml.safe_load((GH / "dependabot.yml").read_text(encoding="utf-8"))
    pip = next(u for u in cfg["updates"] if u["package-ecosystem"] == "pip")
    by_name = {i["dependency-name"]: i.get("versions") for i in pip["ignore"]}
    assert by_name["scipy"] == [">=1.18"] and by_name["pyarrow"] == [">=24"] and by_name["pyglet"] is None


def test_codeowners_covers_everything_and_names_real_paths():
    lines = [ln.split() for ln in (GH / "CODEOWNERS").read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    assert lines[0] == ["*", "@arunramana"]
    for pattern, *owners in lines:
        assert owners and all(o.startswith("@") for o in owners)
        assert pattern == "*" or (ROOT / pattern.lstrip("/")).exists(), pattern


def test_security_policy_uses_private_reporting_and_states_the_limits():
    text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "private" in text.lower() and "Report a vulnerability" in text
    assert "no authentication" in text and "127.0.0.1" in text


@pytest.mark.parametrize("name", ["bug_report.yml", "feature_request.yml"])
def test_issue_forms_are_valid_forms(name):
    form = yaml.safe_load((GH / "ISSUE_TEMPLATE" / name).read_text(encoding="utf-8"))
    assert form["name"] and form["description"] and form["body"]
    assert all("type" in item for item in form["body"])


def test_issue_chooser_sends_security_reports_to_the_private_form():
    cfg = yaml.safe_load((GH / "ISSUE_TEMPLATE" / "config.yml").read_text(encoding="utf-8"))
    assert cfg["blank_issues_enabled"] is False
    assert any("security/advisories/new" in link["url"] for link in cfg["contact_links"])


def test_pr_template_asks_whether_results_change():
    assert "Could this change run results?" in (GH / "pull_request_template.md").read_text(encoding="utf-8")


def test_the_maintainer_guide_names_the_required_checks():
    text = (ROOT / "docs" / "maintainers.md").read_text(encoding="utf-8")
    assert all(f"`{job}`" in text for job in ci()["jobs"])
    assert "squash" in text and "push protection" in text and "Private vulnerability reporting" in text


def test_community_files_exist():
    for f in ("LICENSE", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md", "README.md", "ROADMAP.md"):
        assert (ROOT / f).stat().st_size > 200, f
