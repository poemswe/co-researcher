# Co-Researcher Project Context

Rolling state. Prune entries >3 weeks after each milestone.

## Current Focus

**Branch `feat/literature-search-backends`** (2026-06-04) — replacing the hand-wavy `WebSearch`-based literature-review protocol with three real database backends: OpenAlex, arXiv, Europe PMC. Architecture: `literature-review` owns the scripts; `systematic-review` references them. `scienceskillscommon` (Apache-2.0, vendored from google-deepmind/science-skills) is the shared HTTP client. `uv` bootstrap handled by `scripts/setup.sh`, not as a skill.

## Open Threads

- Decision pending on whether to merge `literature-review` and `systematic-review` into one skill with a rigor parameter. Currently kept separate (PRISMA distinction is meaningful).
- Other co-researcher skills (`research-synthesis`, `multi-source-investigation`, `peer-review`) still use `WebSearch` only. May benefit from the same backend integration in a follow-up.
- README / CONTRIBUTING not yet updated to mention `scripts/setup.sh` as a first-run step.

## Recent Decisions

- **2026-06-04**: `uv` is not a skill. It's a CLI binary, set up via `scripts/setup.sh` with an inline fallback documented in `literature-review/SKILL.md`.
- **2026-06-04**: `setup.sh` also prompts (optionally) for `OPENALEX_API_KEY`, writes to `~/.env` mode 600, never echoes the value. Free polite pool still works without a key but throttles after ~1 `--search` per day.
- **2026-06-04**: Backend scripts live inside `literature-review/scripts/` (not as separate top-level skills). User-facing surface area = the two review skills only.
- **2026-06-04**: Kept both `literature-review` (narrative/scoping) and `systematic-review` (PRISMA). Methodological distinction justifies the 60% protocol overlap.
- **2026-06-11**: Made `scripts/setup.sh` robust under non-interactive environments (added `|| true` to key input `read`). Updated `evals/lib/core.py` to use `shutil.which` and check `/opt/homebrew/bin` to fix evaluation CLI discovery on Apple Silicon macOS.

## Pitfalls

- `[tool.uv.sources]` paths in script PEP 723 headers are resolved **relative to the script file's directory**, not CWD. Path is `../../scienceskillscommon` from `skills/literature-review/scripts/X.py` → `skills/scienceskillscommon/`. If scripts move, paths must be re-counted.
- `scienceskillscommon/` directory name must stay verbatim (no kebab-case rename) — the wheel build maps `.` → `science_skills/scienceskillscommon` and scripts import `from science_skills.scienceskillscommon import http_client`.
- OpenAlex `--search` queries cost 10× more than `--filter`. Prefer `--filter` with resolved IDs over name-based `--search` when possible.
- Europe PMC search auto-appends `OPEN_ACCESS:y`. To search closed-access metadata, would need to modify `europepmc_api.py` (don't unless asked).

## Smoke-Test Status

All three backends tested 2026-06-04 on `feat/literature-search-backends`:

- arXiv: `search_arxiv.py --query "ti:attention is all you need" --max_results 1` → JSON returned
- OpenAlex: `openalex_cli.py filter works --search "transformer attention mechanism"` → 261,522 hits, $0.001 cost
- Europe PMC: `europepmc_api.py search "DOI:10.1038/s41586-021-03819-2"` → resolves AlphaFold paper (PMC8371605)
- `scripts/setup.sh` detects existing `uv` (Homebrew 0.10.9) and warms the dep cache successfully
