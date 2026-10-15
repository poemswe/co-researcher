# Co-Researcher Project Context

Rolling state. Prune entries >3 weeks after each milestone.

## Current Focus

**v2.8.1 (2026-10-14, `fix/non-latin-titles`, fixes #54).** `verify_citations._normalize_title` kept only `[a-z0-9 ]`, so a title in Japanese, Chinese, Korean or Cyrillic normalized to an empty string and a real paper was reported as mismatched. It now casefolds, drops accents and punctuation, and keeps letters and digits in every script. The unused `check_claims._normalize_bib_title` had the same flaw and is removed; reference matching there already uses the Unicode-aware `_normalized_tokens`.

**Roadmap from community feedback (2026-10-14).** A scan of 31 Reddit threads, 2 HN threads and ARS issues produced issues #54-#61: #55 Zotero or a PDF folder as the corpus (most-asked uncovered need, next to design), #56 checking citations in the user's own manuscript, #57 Semantic Scholar, #58 corpus diff between runs, #59 dual screening with kappa, #60 the five known gate gaps (polarity first), #61 partial resolution when a registry is unreachable. The common stance across threads is that AI should help find, triage and verify while the reading and judgement stay with the researcher.

**v2.8.0 released (2026-10-14).** #51 (`33fbaa4`) bumped the version; the user pushed tag `v2.8.0` and published the GitHub release. It ships #50 (`10950d6`, closes #48): hypothesis-testing step 6 runs every outcome scorer on at least 5 real outputs and pre-registers a tie-break rule before the plan is frozen, the output gains a Scorer Check line, quantitative-analysis Data Inspection reads raw outputs against their scores, and a 33rd broad case `hypothesis-testing/test-outcome-scorer` is added. The site and llms files still say 32 cases, because the published runs used 32; change that after the next broad run. Also since 2.7.1: #49 (actions/checkout 7.0.1).

**#47 (davdittrich, manipulation check between protocol steps 4 and 5) is accepted.** The reporter offered a PR with an eval case; we said yes and asked him to rebase after #50. Ship it as 2.8.1 or in 2.9.0.

**Report on the site.** `/paper/` is the plain-language summary and `/paper/write-up/` the technical write-up, both built by a scratchpad script from the artifact source (https://claude.ai/artifact/FQUH5LQGXszNXnHhPhHDg1, v18). Merged: #43 (`6bf15c6`) the pages, #44 (`bcc2937`) the SEO pass (keyword-led descriptions, 18 GitHub topics, no "PhD-level" outside the eval rubric, `bump-version.sh` covers the README badge and site), #45 (`8b3361e`) og:image, #46 (`495b0ac`) Academic Research Skills cited as reference 16 (CC BY-NC, so cite only and reuse nothing), #52 (`5e3a68f`) "How the checker works" as four steps with the why of each. arXiv waits for an evaluation on real papers; its one-year ban for unchecked LLM output and the CS ban on review and position papers both apply. Search Console had not fetched the subdomain sitemap on 2026-10-13 and queries were brand-only; watch for non-brand queries.

**README thinned (2026-10-14, `docs/thin-readme`).** It now covers install, commands, skills, the evidence check, the toolchain and a short development section. The offline validator reference moved to `docs/validate-review.md`, and publishing integrity runs and serving the dashboard moved to `evals/README.md`, whose case table now lists all 33.

PR #29 (icaromol, Windows rate-limiter lock) has changes requested: a stale lock directory left by a killed process hangs every later call.

## Open Threads

- **Gate gaps for 2.7.1.** Codex's paper review found, and we reproduced, five things the gate passes as valid/100: a claim that reverses its quote (claim–quote compared on numbers only), an uncited sentence with no number, a background role on a qualitative finding, swapped numbers (multiset comparison), and duplicate author–year citations (checked against the declared record only). A missing citation report is only a warning, and an empty bibliography raises nothing. The harness's assessability check (`fixture_preserved`) uses containment, so text appended to a source could let a corrupted quote count as assessable. Claim–quote polarity is the first fix planned. Resolver false alarms are fixed in PR #42: OpenAlex's phrase search returned nothing for titles with `?` or `*` and treated `|` as OR, and a DOI that OpenAlex attaches to the wrong work now verifies when the DOI's own Crossref or DataCite record carries the cited title. Registry lookups retry once, and DataCite is skipped after a Crossref match.
- **Resolver follow-ups (not started).** A mismatch reached while Crossref or DataCite was unreachable is still reported as fully resolved; it should mark resolution as partial. The registry check could move into `resolve_doi` as a step that returns candidate titles.
- **Semantic Scholar backend** (backlog, new feature, not started) — feedback from a live-run session flagged this as a gap; no scope/design decided yet.
- Decision pending on whether to merge `literature-review` and `systematic-review` into one skill with a rigor parameter. Currently kept separate (PRISMA distinction is meaningful).
- **No multi-reviewer screening.** Covidence and Rayyan support two independent screeners with conflict adjudication, which real systematic reviews require. We have nothing there. Biggest honest capability gap vs incumbents.
- **Retraction recall is unmeasurable with current method.** Every sample is drawn from one source's own positives, so that source scores 100% by construction. To measure true recall we'd need a source-independent ground-truth set (e.g. the Retraction Watch CSV joined against a random paper sample).

## Recent Decisions

- **2026-10-12**: A title mismatch on a DOI is checked against the DOI's registration (Crossref `works/{doi}`, DataCite `dois/{doi}`) before it is reported. This looks up a known DOI and is not a Crossref bibliographic title search, which returns a top hit for any string (see Pitfalls). When the registration itself carries another title, as NISTIR 8213's draft does ("Randomness Beacon Format 2.0"), the mismatch stands.
- **2026-10-12**: No claude.ai session links or `Claude-Session` trailers in this public repo's commits, PRs or releases. Four squashed commits on `main` (905a482, 3e78832, 465e3ea, b4034cb) keep theirs, by the user's choice.
- **2026-10-06**: Coverage strictness: every synthesis number, years included, must be grounded, and an uncited number is critical. Warnings that edits can fix (`claim_needs_review`, `bibliography_incomplete`, `prisma_exclusion_reason_missing`) trigger repair. `abstract_only_support` and `citation_resolution_unavailable` do not.

## Pitfalls

- A `&&` chain does not stop on pytest failures reported in output you don't read. Run the tests, check the counts, then commit in a separate step. Locally, run tests with `PYTHONNOUSERSITE=1 uv run --no-project --with pytest --with pymupdf4llm --with python-dotenv python -m pytest -q tests`; plain `uv run` picks up an x86_64 pymupdf from user site-packages.
- Never squash or rebase-merge a release branch into `main`. Both rewrite commit IDs and break the claim-verifier benchmark pin `TARGET_COMMIT`; use a merge commit.
- `http_client.py` and `jats.py` are plain sibling modules in `scripts/` (no package/build). `uv run script.py` puts the script dir on `sys.path`, so `import http_client` resolves; tests load scripts by path and must `sys.path.insert(0, <scripts dir>)` first. Editing them is live — no `--reinstall` needed.
- OpenAlex `--search` queries cost 10x more than `--filter`. Prefer `--filter` with resolved IDs over name-based `--search` when possible.
- Europe PMC search auto-appends `OPEN_ACCESS:y`. To search closed-access metadata, would need to modify `europepmc_api.py` (don't unless asked).
- `http_client._resolve_url` matches on hostname, not string prefix — don't regress this back to `startswith(base_url)`, it reopens the host-prefix SSRF bypass.
- `fulltext.md` structure depends on the retrieval route, not the paper. `source: "epmc"` (JATS) yields real `#` headings; every PDF route (`arxiv_pdf`, `oa_pdf`, `user_pdf`, `cached`) goes through `pymupdf4llm` and yields bold-only section lines with zero `#`. Grep `^\*\*` there, not `^#`.
- `corpus.json`'s `fulltext` field is what `prisma_counts.py` reads. Leaving it `null` after retrieving a paper makes the PRISMA flow under-report silently.
- Never pair OpenAlex `--search` with `--sort cited_by_count:desc` — it ranks by citation fame, not relevance, and floods the pool with landmark papers that merely contain the keywords.
- No retraction source is complete. OpenAlex misses some (3/40 sampled); Crossref/Retraction Watch lags on recent retractions (19/50 sampled). Never let one clean answer end a retraction check.
- Crossref's filter language is comma-delimited, so a DOI containing a comma silently splits the expression and returns HTTP 400. `retracted_via_crossref` returns `None` (unknown), never `False` — do not "simplify" that back to a bool.
- A paper with no DOI cannot appear in Crossref at all; its PubMed record is the only retraction route.
- Crossref's `query.bibliographic` always returns a top hit, even for a fabricated title. Never use it to resolve identity.
- Europe PMC marks a retracted paper with pubType `Retracted Publication`; the retraction *notice* is a different document (`Retraction Notice`). "retracted" vs "retraction" is what separates them — don't loosen that substring test.
- Benchmarking retraction recall by sampling one source's positives scores that source at 100% by construction. Any such number is a lower bound on the *others*, not a recall figure.

## Test Status

981 tests pass on `fix/non-latin-titles` (2.8.1, 2026-10-14).
