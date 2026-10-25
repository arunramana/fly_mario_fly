## What and why
<!-- One or two sentences. Link the issue: Fixes owner/repo#123 -->

## How I checked it
<!-- e.g. `python -m pytest tests -q` (N passed), `cd web && npm run build`; a screenshot/clip if visual -->

## Could this change run results?
- [ ] No. Same seeds give the same run `hash`.
- [ ] Yes, and I explain why below (golden data is **not** edited to make tests pass).

## Checklist
- [ ] Import boundaries kept (`fly/` ⟂ `mario/`; `evolve/`, `api/`, `render/` go through `runner/`)
- [ ] Any new dial has a truthful `origin` ("fly" = from the connectome, "invented" = ours)
- [ ] Tests added in `tests/test_<area>_*.py` (small synthetic data, no 1 GB weights)
- [ ] No data, caches, videos or secrets committed
