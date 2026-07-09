# Co-Researcher Project Context

Rolling state. Prune entries >3 weeks after each milestone.

## Current Focus

**Branch `feat/literature-search-backends`** (2026-06-04) — replacing the hand-wavy `WebSearch`-based literature-review protocol with three real database backends: OpenAlex, arXiv, Europe PMC. Architecture: `literature-review` owns the scripts; `systematic-review` references them. `http_client.py` + `jats.py` (MIT, in `scripts/`, imported as sibling modules) are the shared HTTP client + JATS extractor. `uv` bootstrap handled by `scripts/setup.sh`, not as a skill.

## Open Threads

- Decision pending on whether to merge `literature-review` and `systematic-review` into one skill with a rigor parameter. Currently kept separate (PRISMA distinction is meaningful).
- Other co-researcher skills (`research-synthesis`, `multi-source-investigation`, `peer-review`) still use `WebSearch` only. May benefit from the same backend integration in a follow-up.
- README / CONTRIBUTING not yet updated to mention `scripts/setup.sh` as a first-run step.
- **PR #19 not yet merged**: public repo — held open until the full paper-reading feature is verified. Phase 2 done; funnel ran live via local plugin install (2026-06-18) and the extraction pipeline was exercised on real papers. Live-run feedback fixed: search_arxiv single-JSON + hit count, workspace anchored to invocation CWD, arXiv relevance default, OpenAlex topic-filter guidance + hit counts, EPMC hit count, PyMuPDF stdout-pollution suppression, table/heading caveats in notes.md. Remaining: Semantic Scholar backend (backlog, new feature). See memory `pr19-merge-gate`, `literature-search-feedback`.

## Recent Decisions

- **2026-06-04**: `uv` is not a skill. It's a CLI binary, set up via `scripts/setup.sh` with an inline fallback documented in `literature-review/SKILL.md`.
- **2026-06-04**: `setup.sh` also prompts (optionally) for `OPENALEX_API_KEY`, writes to `~/.env` mode 600, never echoes the value. Free polite pool still works without a key but throttles after ~1 `--search` per day.
- **2026-06-04**: Backend scripts live inside `literature-review/scripts/` (not as separate top-level skills). User-facing surface area = the two review skills only.
- **2026-06-04**: Kept both `literature-review` (narrative/scoping) and `systematic-review` (PRISMA). Methodological distinction justifies the 60% protocol overlap.
- **2026-06-11**: Made `scripts/setup.sh` robust under non-interactive environments (added `|| true` to key input `read`). Updated `evals/lib/core.py` to use `shutil.which` and check `/opt/homebrew/bin` to fix evaluation CLI discovery on Apple Silicon macOS.
- **2026-06-20**: Backend is now original MIT throughout — all four scripts (`search_arxiv.py`, `europepmc_api.py`, `openalex_cli.py`, `read_paper.py`) plus the `http_client.py`/`jats.py` helpers, reimplemented to a minimal surface (openalex keeps just `filter`). Deleted unused `download_paper.py`/`download_paper_source.py`. Each verified with contract tests + live API calls. Only non-MIT footprint: the optional AGPL `pymupdf4llm` runtime dep. Dropped the `<attribution>` block from literature-review SKILL.md (token savings; credit lives in per-file source headers).
- **2026-06-20**: De-packaged `scienceskillscommon` — moved `http_client.py`/`jats.py` into `scripts/` as plain sibling modules, deleted the package dir + stub `SKILL.md` (was a phantom skill) + `pyproject`/`__init__`/uv.sources. Removes the foreign "science-skills" name, the build machinery, and the stale-wheel `--reinstall` gotcha. 45 tests green.
- **2026-06-17**: Paper-reading + review-funnel workflow complete. Phase 1 (Tasks 1–5): `read_paper.py` resolution chain + backends, EPMC PMCID fallback, 31 unit tests. Phase 2 (Tasks 6–8): both review SKILL.md protocols rewritten around the `review/{slug}/` workspace with `corpus.json` screening state, pilot screening, evidence/background split, `notes.md` as the unit of synthesis, abstract-only/PRISMA "not retrieved" handling. **Deviation from the spec draft (agreed 2026-06-12)**: the arXiv-HTML retrieval route was dropped; `read_paper.py`'s `source` enum has no `arxiv_html`.

## Pitfalls

- `http_client.py` and `jats.py` are plain sibling modules in `scripts/` (no package/build). `uv run script.py` puts the script dir on `sys.path`, so `import http_client` resolves; tests load scripts by path and must `sys.path.insert(0, <scripts dir>)` first. Editing them is live — no `--reinstall` needed.
- OpenAlex `--search` queries cost 10× more than `--filter`. Prefer `--filter` with resolved IDs over name-based `--search` when possible.
- Europe PMC search auto-appends `OPEN_ACCESS:y`. To search closed-access metadata, would need to modify `europepmc_api.py` (don't unless asked).

## Smoke-Test Status

All three backends tested 2026-06-04 on `feat/literature-search-backends`:

- arXiv: `search_arxiv.py --query "ti:attention is all you need" --max_results 1` → JSON returned
- OpenAlex: `openalex_cli.py filter works --search "transformer attention mechanism"` → 261,522 hits, $0.001 cost
- Europe PMC: `europepmc_api.py search "DOI:10.1038/s41586-021-03819-2"` → resolves AlphaFold paper (PMC8371605)
- `scripts/setup.sh` detects existing `uv` (Homebrew 0.10.9) and warms the dep cache successfully
