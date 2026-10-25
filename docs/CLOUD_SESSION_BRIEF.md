# fly_mario_fly — brief for cloud sessions

Put this file in the repo (e.g. `docs/CLOUD_SESSION_BRIEF.md`) and start the session with:
"Read docs/CLOUD_SESSION_BRIEF.md and follow it."

---

## 1. What this project is

`arunramana/fly_mario_fly` plays Super Mario Bros with the **MaleCNS v1.0** fruit-fly connectome (Janelia FlyEM × Google, CC-BY 4.0). Game state is turned into the fly's senses. Those senses drive a small circuit of **real neurons with their real wiring**, and the fly's motor and descending neurons press the buttons.

- **Circuit:** 636 neurons, including LC4, LPLC2, DNp01 (giant fibre), TTMn (jump muscle), DNp09 (forward walking), LC10a and DNa (steering).
- **Behaviours:**
  - **Walk right:** an invented home signal drives LC10a, and the real LC10a → DNp09 wiring turns that into walking.
  - **Jump:** looming (angular size θ and its growth) drives LC4/LPLC2, and the real wiring through the giant fibre and the jump muscle turns that into a jump.
  - **Smells and hearing:** invented cues fed into real routes (JO → giant fibre, ORN → DNa, DC4 → MDN).
- **Dials:** a few scale how strong each sense or cue is. Evolution may tune the dials only, never the wiring.
- **Scope:** level 1-1 is won. Other levels are not tuned yet.

Before changing anything, read `CLAUDE.md`, `README`, `CONTRIBUTING`, `docs/` and the tutorials. Then summarise the architecture back to me in 15 lines or fewer.

## 2. The project's rules (do's and don'ts)

**Do**
1. The fly makes every decision.
2. Read the game's memory to work out what the fly senses.
3. Invent cues the fly can react to.
4. Add dials that set how strong each sense and cue is.

**Don't**
1. Edit the fly's wiring. No neuroevolution: connectome weights are read-only.
2. Fire the fly's neurons directly.
3. Let our code decide an action for the fly.

**Colour rule:** teal means real wiring from the connectome; orange means invented by us.
**Honesty lines:** "The wiring is untouched; a few dials are evolved." Never say "nothing is trained". Say what is invented.

## 3. Decisions already made (don't reopen)

- **Licence:** MIT, holder "Arun Ramana".
- **CODEOWNERS:** `@arunramana`.
- **Nintendo assets:** the sprites and `level_db.json` **stay in the repo**. This is the owner's decision; don't move or remove them.
- **Pins:** `nes-py==8.2.1`, `gym-super-mario-bros==7.4.0` (version 9 breaks the emulator wrapper).
- **Tests:** tests skip when `FLY_MARIO_FLY_DATA` is unset. Never point it at an empty folder in CI (that triggers a 1.1 GB download).
- **Roadmap (future, do not build now):** evolution across all levels, and a lightweight browser version (pick level + fly settings, watch the run; no downloads, no evolution).

## 4. Ground rules for every PR

- One small, reviewable PR per step, each on its own branch off `main`.
- **Stop after each PR** and wait. The owner will paste review comments (Greptile and their own), and you fix them on the same PR.
- **Behaviour must stay identical.** These must stay green: the full test suite, the web lint and build, every tutorial, and the demo (`scripts/demo.py`, seed 101, which reaches the flag with hash `3111e33d1b22`). If a change could alter results, **flag it instead of making it**.
- Never rewrite git history. Never commit data, videos, `.env` files or keys.
- If GitHub push fails (403), stop and say so. Don't upload through the API, because that flattens the commits.

## 5. Work plan

### PR 1: Cleanup
- List the removal candidates: stale, backup or duplicate code; unused scripts; generated files; stock boilerplate (`web/README.md` Vite text); design mockups; old telemetry and checkpoints; the `--legacy` path; `tools/freeze_golden.py`.
- For each, give grep evidence that it's unused (imports, tests, CI, docs, tutorials).
- **Wait for the owner's OK on the list**, then delete. Extend `.gitignore` so they don't come back.

### PR 2: Compliance layer
- Add a `rules` module that encodes section 2:
  - Actions may only come from motor or descending-neuron outputs, never from game logic.
  - Connectome weights are read-only.
  - Senses and cues may only drive input neurons through a **declared, real route**; no direct neuron setting.
  - Every sense, cue, object, character and action declares its origin: `fly` (teal) or `invented` (orange). `fly` items must cite the real route and cell types.
  - Dials may only scale sense and cue strengths, and they are the only thing evolution may tune.
- Add a **plugin schema** (a dataclass or YAML) for senses, cues, objects, characters and actions.
- Add a **validator** with plain-English errors, **runtime guards** that fail loudly on any weight write or direct neuron firing, and a **CI job** that validates every plugin.
- Migrate the existing senses, objects and actions onto the schema with identical behaviour.
- Add tests that deliberately break each rule and check that the validator rejects them.

### PR 3: MCP server
- Tools such as `list_rules`, `list_plugins`, `explain_plugin`, `add_sense`, `add_cue`, `add_object`, `add_character`, `set_dial` and `run_fly` (headless; returns a summary and an optional video path).
- Every write goes through the validator, returns the teal/orange label, and **refuses rule-breaking requests with the reason**. No tool may edit weights or fire neurons.
- Include setup docs (connecting it to Claude or other MCP clients) and tests.

### PR 4: New characters and objects
- Add a few new characters and objects as plugins through the schema, each with origin labels, routes, tests and a short tutorial snippet.

### PR 5: README and documentation
- **README:**
  - a hero GIF slot and a 30-second "what is this"
  - quick start
  - how it works (senses → real neurons → actions, with the teal/orange rule)
  - the do's and don'ts, the compliance layer and the MCP
  - results, tutorials and contributing
  - credits: MaleCNS v1.0 (Janelia/Google, CC-BY 4.0); Ro0oney / The Fly Project; SethBling's MarI/O
  - licence
- **`docs/`:** concepts, "Rules of the fly" (compliance), a plugin authoring guide, an MCP guide, and an architecture overview. Link all of them from the README and CONTRIBUTING.
- **Roadmap section and `ROADMAP.md`, containing only:**
  - Evolution across all levels.
  - A lightweight browser version: pick a level and fly settings, watch the run. No downloads, no evolution.

### PR 6: Repo health
- Confirm these are in place: `SECURITY.md` (GitHub private vulnerability reporting), CODEOWNERS, issue and PR templates, and CI. Make the CI job names stable so they can be required.
- In the PR description, list the GitHub settings for the owner to apply by hand:
  - a ruleset on `main`: PR + 1 approval + required CI + resolved conversations + no force-push or deletion
  - squash-merge only, and auto-delete branches
  - a read-only workflow token, and approval required for workflows on fork PRs
  - Dependabot, plus secret scanning with push protection

## 6. Finish

End with a short summary covering what changed in each PR, the open questions, and anything you flagged instead of changing.
