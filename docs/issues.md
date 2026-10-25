# Good first issue drafts

Copy each block into a GitHub issue (label `good first issue`). Each is small, has a clear "done", and avoids the maintainer-owned files.

---

## 1. Add the README demo GIF
**Where:** `docs/media/demo.gif`, README (the commented-out image line near the top).
**Task:** Run `python scripts/demo.py --video`, turn the mp4 into a GIF (under ~5 MB, 10-15 s, e.g. with `ffmpeg`), commit it as `docs/media/demo.gif` and un-comment the image line in the README.
**Done when:** the README shows the fly clearing World 1-1.

## 2. Add a linter and formatter config (ruff)
**Where:** a `[tool.ruff]` section, CI step.
**Task:** Propose a minimal ruff config that passes on the current code with few or no source changes (start with `E`, `F`, `I` and a generous line length, ~140), and add it as a CI step. Do not reformat the whole tree in the same PR.
**Done when:** `ruff check src tests scripts` is green locally and in CI. (`pyproject.toml` is maintainer-owned: open the PR and the maintainer will merge the config part.)

## 3. Write "How to add a sense" in docs
**Where:** `docs/add_a_sense.md`, link from CONTRIBUTING.
**Task:** Walk through creating a tiny sense plug-in: copy `senses/home.py`, change the `PLUGIN` object, declare its `KnobSpec` with a truthful `origin`, attach it in a copy of `configs/flies/blank.yaml`, and see it in `registry.list_plugins("senses")`. Use hand-built frames like `tests/test_senses_behaviour.py` to show how to test it.
**Done when:** someone who has not read the code can follow it end to end.

## 4. Run the tests on macOS and Windows in CI
**Where:** `.github/workflows/ci.yml`.
**Task:** Turn the `python` job into an OS matrix (`ubuntu-latest`, `macos-latest`, `windows-latest`) with Python 3.12. `nes-py` compiles C++ so expect to fix or document build requirements; if one OS cannot work, document why in the README instead.
**Done when:** CI is green on the OSes that can work, and the README says which are supported.

## 5. Make `scripts/download_data.py` verify its download
**Where:** `scripts/download_data.py` (and, if you want, `fly/connectome.py`'s `_download`).
**Task:** After downloading, check each file against the size the server reports (already done) and print its SHA-256 so users can compare. Add `--check` that only verifies files that are already there, without downloading. Add a unit test that uses a tiny local HTTP server or a monkeypatched `_download`, never the real 1 GB file.
**Done when:** `--check` reports OK/missing/truncated for each file.

## 6. Document the CLI flags in one place
**Where:** `docs/cli.md`.
**Task:** The runner (`python -m fly_mario_fly.runner run --help`), evolve and render CLIs are documented only in module docstrings. Collect the flags with one example each (`--scene keep_only:pit`, `--from-moment`, `--legacy`, `--record-ram`, `evolve run ... --gens`). Explain what `--legacy` is for (parity with the old tool) and that it is not for normal use.
**Done when:** every flag printed by `--help` appears in the doc.

## 7. Replace stale "old code" wording in comments and configs
**Where:** `configs/flies/*.yaml` provenance notes, `mario/facts/*.yaml` headers, `mario/env.py`.
**Task:** Several comments point at files from the old repository (`runs/E1s.md`, `runs/L2b_tiles.json`) that contributors cannot see. Rewrite each to say what the number is and how to re-derive it (or mark it "recorded from the pre-cleanup code, git tag `pre-cleanup`"). Comments and YAML comments/provenance text only; **no value changes**.
**Done when:** `pytest tests -q` gives the same result and `git diff` shows only comment/provenance text.

## 8. Test the web app's mock mode in CI
**Where:** `web/`, `.github/workflows/ci.yml`.
**Task:** `npm run dev:mock` runs the front end on canned data. Add a small Playwright (or Vitest) smoke test that starts mock mode and checks the Fly tab renders the sense grid, and run it in the `web` CI job.
**Done when:** the smoke test fails if the Fly screen crashes on load.
