# Co-Researcher Project Context

Rolling state. Prune entries >3 weeks after each milestone.

## Current Focus

**v2.7.1 in PR #42 (`fix/resolver-false-alarms`, version bumped on the branch).** It fixes resolver false alarms found by running the resolver on the paper's own references, where it verified 19 of 23 real works and now verifies 22. Merge needs the user's explicit go-ahead; after it, tag `v2.7.1` and publish the release.

**v2.7.0 released (2026-10-10).** PR #34 merged `release/2.7.0` into `main` as merge commit `6c6036b`, so the benchmark pin `905a482` is on `main`. Tag `v2.7.0` and the GitHub release are published; Tests and the Pages deploy passed, and the live site serves 2.7.0 (Evals, 32 cases, seven rubrics, published integrity runs). 2.7.0 adds the evidence-integrity engine and gate, live integrity evals with resume, published integrity runs on the dashboard, broad-run resume and release filtering, six new broad cases (32), an overstated-finding integrity case recorded as a known gap, path redaction, honest model and effort labels, and the site renamed from Arena to Evals.

Published 2.7.0 runs: integrity on `5802823` (before the multi-quote skill fix `2329249`), Opus `claude-opus-5-5` and Codex `gpt-6-astra` (low effort), both 15/16, missing only the known gap. Broad: Opus 32/32, average 84.8. Codex broad `codex:gpt-6-astra low`: 32/32, average 89.7, added by #37. Post-release on `main`: #36 (`cb54321`) stops numbered list markers being read as uncited numbers.

Write-ups (private, not shared): the pilot protocol is a Claude Doc (`b84e270a-cf38-4882-a568-659a5bb799f1`); every decision is made (units, domains, cases per paper as the affine plane of order 3, models and runs, uncertainty, agreement bar, NIST beacon at a fixed time T, OSF registry), with Codex's review folded in. The freeze command, paper selection and reviewer handoff are a separate feature after 2.7.0. The workshop paper "Every Claim Traced" (https://claude.ai/artifact/FQUH5LQGXszNXnHhPhHDg1) is at version 15 (2026-10-13) after three Codex reviews, which narrowed its claims to what the gate checks. The third scored it 2/5, mainly for lacking an independently annotated evaluation on real papers, which is the planned benchmark. Version 13 added Nam et al. (arXiv:2606.09500, deterministic gates for clinical manuscripts), the closest prior work, to related work. All 27 references were checked to exist (19 by the resolver, the rest at arXiv, NIST, Unicode and Crossref). Versions 14 and 15 report that resolver result in the Table 1 caption: two arXiv titles with `?` not found, one DOI OpenAlex attaches to another record, and NISTIR 8213, whose DOI registration carries a shorter title. Its evidence package is in `evals/published/paper/` (earlier runs, judge re-scores with `table6.py`, §7 counterexamples). Next: the user's read-through, then LaTeX with static figures for arXiv, then a `/paper/` page on the site. The user posts it herself. arXiv policy to respect: since 14 May 2026, incontrovertible evidence of unchecked LLM output (fabricated references, leftover model text) earns a one-year ban, after which submissions must first be accepted at a peer-reviewed venue. The CS section has refused review, survey and position papers since 2025-10-31, so the paper must read as a systems and evaluation paper.

PR #29 (icaromol, Windows rate-limiter lock) has changes requested: a stale lock directory left by a killed process hangs every later call. It is planned for the next minor or major release.

Next open item is the Semantic Scholar backend (see Open Threads).

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

965 tests pass on `fix/resolver-false-alarms` (2.7.1, 2026-10-13).
