# Research Smoke Tests Design

## Goal

Co-Researcher needs a smoke test that proves the research workflow still runs after changes. The test suite needs one stable gate for CI and one optional Codex-level check for the installed agent path.

## Scope

The required smoke test runs without a Codex login, model call, or network access. It creates a small temporary research fixture, runs the local evidence scripts, and checks the expected files and statuses. CI can run it on every change.

The optional Codex smoke test shells out to the Codex CLI. It checks that Codex can load the repository bootstrap, activate the research path, and initialize a plan-only research workspace. Developers run it explicitly when they want to verify the real integration.

## Required Deterministic Smoke

Add `tests/test_research_smoke.py`.

The test creates a temporary workspace with a minimal paper source and claim file:

- `papers/p1/fulltext.md` with one short, real passage.
- `claims.json` with one claim whose number appears in the supporting quote.
- `synthesis.md` with one cited sentence covered by `claims.json`.
- `corpus.json` with one included full-text record and one excluded record with a reason.

The test then runs the local scripts as subprocesses:

- `check_claims.py` must exit `0` and report one verified claim.
- `prisma_counts.py` must exit `0`, report two records after deduplication, and report one record in synthesis.
- A scaffold assertion must create `research/<slug>/project.json` and `research/<slug>/research-tasks.md`, then parse the JSON and confirm `question`, `phase`, `decisions`, and `next_action`.

This test must not call OpenAlex, Europe PMC, Crossref, arXiv, Codex, or any model.

## Optional Codex Smoke

Add `scripts/codex_smoke_research.py`.

The script exits with a clear skip message unless `CO_RESEARCHER_CODEX_SMOKE=1` is set. When enabled, it locates the `codex` binary and runs a constrained prompt in a temporary directory:

```text
Use the Co-Researcher repository at {repo_path}.
Run `.codex/co-researcher-codex bootstrap` and follow the bootstrap rules.
Run a plan-only research smoke test for:
"Does structured exercise reduce hospital readmissions?"
Do not perform live literature retrieval. Initialize the research project scaffold only.
```

The script passes only if Codex exits `0` and the temporary directory contains a `research/<slug>/project.json` file with:

- `question`
- `phase`
- `next_action`
- `decisions`

The script should print the Codex output path and any captured stderr on failure. It should clean up by default, with an escape hatch such as `--keep-workdir` for debugging.

## Commands

Required CI gate:

```bash
uv run pytest tests/test_research_smoke.py
```

Optional local integration check:

```bash
CO_RESEARCHER_CODEX_SMOKE=1 uv run scripts/codex_smoke_research.py
```

## Documentation

Document the split in `README.md` under the Codex or Evaluation section:

- deterministic smoke: fast, offline, CI-safe
- Codex smoke: real CLI integration, opt-in, slower, requires authenticated Codex

The docs should name the exact commands and explain that the optional smoke does not replace scored evals.

## Acceptance Criteria

- The deterministic smoke test passes offline.
- The deterministic smoke test fails if claim verification, PRISMA counting, or project scaffold parsing breaks.
- The optional Codex smoke skips by default with exit `0`.
- The optional Codex smoke fails loudly when enabled and Codex cannot create `project.json`.
- Existing evals remain unchanged.
- Existing unit tests keep passing.

## Out of Scope

- Judging research quality.
- Running live literature retrieval.
- Creating a new benchmark rubric.
- Requiring Codex auth in CI.
- Testing every supported platform in this smoke pass.
