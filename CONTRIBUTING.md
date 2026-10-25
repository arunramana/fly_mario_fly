# Contributing

Thanks for helping. The tool is small on purpose: hard boundaries, one plug-in per file, attachments as config. Please keep it that way.

## Set up

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e . --no-deps    # or: pip install -e ".[test]"
python -m pytest tests -q                                        # no data needed; data-dependent tests skip
```

To run the fly itself you need the MaleCNS data (about 1.2 GB, see the README): set `FLY_MARIO_FLY_DATA` to a folder **outside the repo**, then `python scripts/download_data.py --build-brains`. Web app: `cd web && npm ci && npm run build && npm run lint`.

## Rules that reviewers check

1. **Boundaries.** `fly/` never imports `mario/` and `mario/` never imports `fly/`. Only `senses/`, `actions/`, `runner/` import both. `evolve/`, `api/`, `render/` go through `runner/` and never name a specific object or sense. `tests/test_boundaries.py` enforces this.
2. **One plug-in per file**, exposing one object named `PLUGIN` (a sense in `senses/`, an action in `actions/`, an object in `mario/objects/`, ...). Look at a neighbouring file and copy its shape.
3. **Attachments are config** (`configs/flies/*.yaml`), not code.
4. **Honest dials.** Every `KnobSpec` carries `origin="fly"` (read from the connectome) or `origin="invented"`. Never mark something `fly` that we made up. See the README's "teal vs orange" rule.
5. **Nothing injected past the senses.** A sense turns game state into neuron input; it does not give the fly the answer, and nothing is tuned on game outcomes except through `evolve/` on the training set (the dev set in `configs/dev_sets.yaml` only judges).
6. **Results must not change silently.** The golden tests (`tests/golden/`) compare against answers recorded from the old code. If your change alters a run's `hash`, say so in the PR and explain why; do not edit the golden data to make a test pass.
7. **`contracts.py`, `CLAUDE.md`, `registry.py`, `pyproject.toml` and `tests/golden/` are maintainer-owned.** If you need a change there, open an issue first.
8. **Declare every plug-in.** Next to `PLUGIN`, add `DECLARATION = declare(kind, origin, what, ...)` (see `src/fly_mario_fly/rules/`): `origin` is `"fly"` (teal, real wiring: only mechanisms) or `"invented"` (orange), `what` says in one sentence what is real and what is invented, and a sense or action cites the real route it rides (`Route(mechanism, cell_types, wiring)`). Check it with `python -m fly_mario_fly.rules validate` (CI runs it; `python -m fly_mario_fly.rules list` prints the rules). Nothing may write the weights, fire neurons directly, or let our code choose a button: runtime guards and the validator enforce this.
9. **Never commit** data, caches, videos, or secrets (`.gitignore` covers the usual ones). Don't commit anything from `$FLY_MARIO_FLY_DATA`.

## Tests

- Add `tests/test_<area>_*.py` next to your change. Prefer small hand-built frames and synthetic data (see `tests/test_senses_behaviour.py`) over the real weights.
- A test that needs the real data must skip when `FLY_MARIO_FLY_DATA` is unset.
- Randomness is always seeded (`Scene.seed`, `--seed`); keep it that way so runs are reproducible.

## Pull requests

1. Fork, branch from `main`, keep commits small and focused.
2. Run `python -m pytest tests -q` (and the web build if you touched `web/`).
3. Fill in the PR template. Say what changed, how you checked it, and whether it could change run results.
4. CI must be green. A maintainer reviews; CODEOWNERS are requested automatically.

By contributing you agree your work is released under the repository's MIT licence. Be kind: see the [Code of Conduct](CODE_OF_CONDUCT.md). Starter tasks: [docs/issues.md](docs/issues.md).

## Read first

[concepts](docs/concepts.md) · [rules of the fly](docs/rules-of-the-fly.md) · [writing a plug-in](docs/plugin-authoring.md) · [adding a creature or object](docs/adding_creatures.md) · [MCP server](docs/mcp.md) · [architecture](docs/architecture.md) · [roadmap](ROADMAP.md) · [tutorials](tutorials/README.md) · [maintainers](docs/maintainers.md)
