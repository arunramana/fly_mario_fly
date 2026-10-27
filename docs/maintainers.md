# Maintainers: GitHub settings and how work flows

What is already in the repository, and the settings that only the owner can switch on (they cannot be committed).

## In the repo (checked by `tests/test_repo_health.py`)

| file | job |
|---|---|
| `SECURITY.md` | how to report a vulnerability (GitHub private vulnerability reporting) and what the tool does and does not protect |
| `.github/CODEOWNERS` | the owner reviews everything; `contracts.py`, `registry.py`, `CLAUDE.md`, `pyproject.toml`, `tests/golden/` and `.github/` are listed explicitly |
| `.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md` | bug and feature forms (blank issues off, security reports go to the private form), PR checklist (does it change run results?) |
| `.github/workflows/ci.yml` | three jobs with stable names: **`python`** (pinned install, full suite without data), **`web`** (lint and build), **`rules`** (validate every plug-in). Read-only token, timeouts, one run per ref |
| `.github/dependabot.yml` | weekly grouped updates for pip, npm and Actions; the pinned emulator and numpy stack are protected from breaking bumps |

## Settings to apply by hand (Settings tab of the repository)

**1. A ruleset on `main`** (Rules -> Rulesets -> New branch ruleset, target: default branch, enforcement: active)
- Restrict deletions; block force pushes.
- Require a pull request before merging: **1 approval**, dismiss stale approvals when new commits are pushed, require conversation resolution, allowed merge method: **squash**.
- Require status checks to pass: **`python`**, **`web`**, **`rules`** (they appear in the list once they have run on a PR). `GitGuardian Security Checks` can be added too.
- Bypass list: add yourself (repository admin) so you can merge your own PRs. A sole maintainer cannot approve their own PR, so do **not** tick "Require review from Code Owners" unless there is a second code owner; it would block every PR.

**2. Merging** (General -> Pull Requests): allow **squash merging only** (untick merge commits and rebase), and tick **Automatically delete head branches**.

**3. Actions** (Actions -> General)
- Workflow permissions: **Read repository contents and packages permissions** (the workflow also declares `contents: read` itself).
- Fork pull request workflows: **Require approval for all outside collaborators** (or "first-time contributors" at the least), so a fork cannot run code in your Actions before you look.

**4. Security** (Code security)
- Dependency graph, **Dependabot alerts**, **Dependabot security updates** and (with `.github/dependabot.yml`) **version updates**: on.
- **Secret scanning** and **push protection**: on.
- **Private vulnerability reporting**: on (SECURITY.md relies on it).

**5. Optional**
- A tag ruleset protecting `pre-cleanup` (the tag that keeps the old code) from deletion or moving.
- Require approval of workflow runs from Dependabot only if you do not want its PRs to start CI by themselves.

## How a change flows

1. A branch off `main`, small commits, a PR from the template (what changed, how it was checked, **could it change run results?**).
2. CI must be green: `python`, `web`, `rules`. For anything that touches `src/`, also run the suite with the real data and `python scripts/demo.py` (hash `3111e33d1b22`); CI cannot, because it never downloads the 1 GB data.
3. One approval, resolved conversations, squash merge, the branch is deleted.
4. Anything that could change results is flagged in the PR instead of being slipped in.

## When Dependabot opens a PR

CI runs the tests without data. For a bump of `numpy`, `pyarrow`, `scipy`, `pydantic`, `fastapi` or the MCP SDK, also run the data-backed suite and the demo before merging: a numerical library can change results that CI cannot see.
Some updates are **ignored on purpose** in `.github/dependabot.yml` because the project stays on numpy 1.26 (the emulator wrapper breaks under numpy 2): `scipy` 1.18+ and `contourpy` 1.4+ need numpy 2 (pip cannot resolve them), `pyarrow` 24+ installs but then refuses to import without numpy 2 (so CI's install step would pass and every run would break), `pyglet` 2.x is outside `nes-py`'s requirement, and `nes-py`, `gym-super-mario-bros`, `gym`, `numpy` and `opencv-python-headless` are pinned. Moving the project to numpy 2 is a decision for its own PR (the emulator stack first), after which these ignores go.

`requirements.txt` holds the exact pins (Python 3.12); Dependabot edits one line at a time, so after a bump make sure `pip install -r requirements.txt && pip check` is still clean.
