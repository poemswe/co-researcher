# Co-Researcher Project Context

Rolling state. Prune entries >3 weeks after each milestone.

## Current Focus

**v2.3.0 released and merged (2026-07-09).** 14 skills, database-backed search across the evidence-handling skills, citation integrity gates (`verify_citations.py`, `prisma_counts.py`, retraction warnings).

**`fix/funnel-protocol-gaps` open as PR #22 (2026-07-10, not merged — user gates merges).** Came out of the first true end-to-end funnel run against live APIs; fixes three protocol defects and adds `build_corpus.py` (the missing step-3 tool). 98 tests across 9 files. No version bump on the branch — release separately after merge.

Next open item after that is the Semantic Scholar backend (see Open Threads).

## Open Threads

- **Semantic Scholar backend** (backlog, new feature, not started) — feedback from a live-run session flagged this as a gap; no scope/design decided yet.
- Decision pending on whether to merge `literature-review` and `systematic-review` into one skill with a rigor parameter. Currently kept separate (PRISMA distinction is meaningful).

## Recent Decisions

- **2026-07-10**: First true end-to-end funnel run against live APIs (search -> corpus -> screening -> full text -> snowball -> PRISMA -> verification), on "LLMs for title/abstract screening". Surfaced three protocol defects and one missing tool, all fixed on `fix/funnel-protocol-gaps` (PR #22): (1) nothing told the agent to write `read_paper`'s status into `corpus.json`'s `fulltext` field, so PRISMA reported `in_synthesis: 0` despite retrieving every paper; (2) heading guidance was vague — it is deterministic and source-dependent; (3) raw `--search` + `--sort cited_by_count:desc` ranks by fame; (4) step 3 had no tool — added `build_corpus.py`.

- **2026-07-09**: `feat/backend-integration-and-skill-consolidation` marked feature-complete and PR opened against `main` (title: `feat: source-resolution integration, citation integrity gates, skill consolidation`, do not merge). Version bumped to 2.3.0 across `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `gemini-extension.json`, `index.html`, and `KnowledgeGraph.md`. Full suite verified green: 79 tests across 8 files.
- **2026-07-09**: PR #19 squash-merged to `main`, tagged `v2.2.0`, GitHub release published. Feature branch deleted (local + remote) after confirming zero tree diff against `main`. All 7 PR review threads resolved (2 were moot — files deleted in the MIT rewrite; 1 was already fixed — `sanitize_id` traversal guard, confirmed via test coverage before closing).
- **2026-07-09**: SSRF hardening — `http_client._resolve_url` now compares hostnames instead of doing a string-prefix match, closing a host-prefix bypass (e.g. `api.openalex.org.evil.com`) that worked when `base_url` had no trailing slash. Coverage backfilled to 57 tests: `_retry_after_secs`/`_backoff_secs` edge cases, `openalex_cli.fetch_with_retry` 429/error branches, `europepmc_api.download_pdf` non-PDF path, `write_output` OSError path.
- **2026-06-20**: Backend is now original MIT throughout — all four scripts (`search_arxiv.py`, `europepmc_api.py`, `openalex_cli.py`, `read_paper.py`) plus the `http_client.py`/`jats.py` helpers, reimplemented to a minimal surface (openalex keeps just `filter`). Deleted unused `download_paper.py`/`download_paper_source.py`. Only non-MIT footprint: the optional AGPL `pymupdf4llm` runtime dep.
- **2026-06-20**: De-packaged `scienceskillscommon` — moved `http_client.py`/`jats.py` into `scripts/` as plain sibling modules, deleted the package dir + stub `SKILL.md` (was a phantom skill) + build machinery. Removes the stale-wheel `--reinstall` gotcha.
- **2026-06-17**: Paper-reading + review-funnel workflow complete. Both review SKILL.md protocols rewritten around the `review/{slug}/` workspace with `corpus.json` screening state, pilot screening, evidence/background split, `notes.md` as the unit of synthesis. **Deviation from the spec draft (agreed 2026-06-12)**: the arXiv-HTML retrieval route was dropped; `read_paper.py`'s `source` enum has no `arxiv_html`.

## Pitfalls

- `http_client.py` and `jats.py` are plain sibling modules in `scripts/` (no package/build). `uv run script.py` puts the script dir on `sys.path`, so `import http_client` resolves; tests load scripts by path and must `sys.path.insert(0, <scripts dir>)` first. Editing them is live — no `--reinstall` needed.
- OpenAlex `--search` queries cost 10x more than `--filter`. Prefer `--filter` with resolved IDs over name-based `--search` when possible.
- Europe PMC search auto-appends `OPEN_ACCESS:y`. To search closed-access metadata, would need to modify `europepmc_api.py` (don't unless asked).
- `http_client._resolve_url` matches on hostname, not string prefix — don't regress this back to `startswith(base_url)`, it reopens the host-prefix SSRF bypass.
- `fulltext.md` structure depends on the retrieval route, not the paper. `source: "epmc"` (JATS) yields real `#` headings; every PDF route (`arxiv_pdf`, `oa_pdf`, `user_pdf`, `cached`) goes through `pymupdf4llm` and yields bold-only section lines with zero `#`. Grep `^\*\*` there, not `^#`.
- `corpus.json`'s `fulltext` field is what `prisma_counts.py` reads. Leaving it `null` after retrieving a paper makes the PRISMA flow under-report silently.
- Never pair OpenAlex `--search` with `--sort cited_by_count:desc` — it ranks by citation fame, not relevance, and floods the pool with landmark papers that merely contain the keywords.

## Smoke-Test Status

All three backends tested live (2026-06-04, re-verified 2026-06-18):

- arXiv: `search_arxiv.py --query "ti:attention is all you need" --max_results 1` → JSON returned
- OpenAlex: `openalex_cli.py filter works --search "transformer attention mechanism"` → 261,522 hits, $0.001 cost
- Europe PMC: `europepmc_api.py search "DOI:10.1038/s41586-021-03819-2"` → resolves AlphaFold paper (PMC8371605)
- `scripts/setup.sh` detects existing `uv` (Homebrew 0.10.9) and warms the dep cache successfully

57/57 unit tests pass as of the `v2.2.0` release.
