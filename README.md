# Co-Researcher: Academic Research Plugin for Claude Code

![Version](https://img.shields.io/badge/version-2.8.0-1e3a8a) ![License: MIT](https://img.shields.io/badge/license-MIT-065f46)

Co-Researcher is an academic research plugin for **Claude Code**, **Gemini CLI**, **OpenAI Codex** and **OpenCode**. It runs literature reviews, systematic reviews, peer review and citation checks inside the AI assistant you already use.

Searches run against real scholarly databases (OpenAlex, arXiv, Europe PMC), and every bibliography passes a verification gate that catches fabricated, mismatched, and retracted citations before output.

## Installation

| Platform | Install |
|---|---|
| Claude Code | `/plugin marketplace add poemswe/co-researcher` then `/plugin install co-researcher` |
| Gemini CLI | `gemini extension install https://github.com/poemswe/co-researcher` |
| Codex | Tell Codex: `Fetch and follow instructions from https://raw.githubusercontent.com/poemswe/co-researcher/main/.codex/INSTALL.md` |
| OpenCode | Tell OpenCode: `Fetch and follow instructions from https://raw.githubusercontent.com/poemswe/co-researcher/main/.opencode/INSTALL.md` |

Manual setup for each platform is in [.codex/INSTALL.md](.codex/INSTALL.md) and [.opencode/INSTALL.md](.opencode/INSTALL.md). From a local clone, Gemini users can run `gemini extension link .`, and Claude CLI users `claude plugin marketplace add poemswe/co-researcher && claude plugin install co-researcher`.

## Commands

| Task | Claude / Gemini | Codex |
|---|---|---|
| Research project | `/research` | `$research` |
| Critical analysis | `/analyze` | `$analyze` |
| Peer review | `/review` | `$review` |

Everything else runs when you describe the task in plain language, and the matching skill starts on its own.

`/research "remote work and productivity"` drafts a plan and waits for your approval before running it. Add `--auto` to skip the approval, `--plan-only` to stop at the plan, or `--template=quick|rigorous|comprehensive` for a preset depth.

## Skills

Each skill follows the **Systemic Honesty** principles, which a session-start hook loads automatically.

- **literature-review**: database search, screening and synthesis, with an evidence check before delivery
- **systematic-review**: PRISMA-standard systematic reviews
- **research-synthesis**: narrative synthesis with stated uncertainty
- **multi-source-investigation**: cross-checking claims across sources
- **critical-analysis**: logic checking and fallacy detection
- **peer-review**: manuscript critique and methodological review
- **research-methodology**: design selection and validation, including cross-domain and first-principles reframing
- **hypothesis-testing**: hypotheses, variables, falsification criteria and scorer checks
- **quantitative-analysis**: test selection, power and effect sizes
- **qualitative-research**: coding and thematic analysis
- **ethics-review**: IRB compliance and privacy risk
- **grant-writing**: proposals and specific aims
- **academic-writing**: removing AI-isms from research prose
- **research-manager**: task planning and resumable project state
- **using-co-researcher**: orientation to the suite

## Literature Reviews With Evidence Checks

Ask your agent for a literature review ("review the evidence on remote work and
productivity"), or invoke the `literature-review` skill. The agent searches
OpenAlex, arXiv and Europe PMC, screens what it finds, reads the full texts it
can retrieve through legal open-access routes, and writes everything into a
workspace under your current directory.

| File in `review/{slug}/` | Holds |
|---|---|
| `protocol.md` | the question, inclusion criteria and query log |
| `corpus.json` | every candidate paper and its screening decision |
| `papers/{key}/fulltext.md` | the retrieved text of each included paper |
| `synthesis.md` | the review itself |
| `claims.json` | one entry per cited sentence, with the verbatim quote behind it |
| `refs.json` | the bibliography, checked against OpenAlex, Europe PMC and Crossref |

Before delivering, the agent runs `validate_review.py`, which checks the
workspace without a model. Every quote must occur in its paper, and every
citation must point to exactly one screened paper. Every number in a claim must
appear in its quote, and every cited sentence in the synthesis must agree with a
verified claim in its numbers, negation and direction. A number in an uncited
sentence is flagged. When a check fails, the agent receives the findings and up
to three rounds to repair them.

| The review arrives as | Meaning |
|---|---|
| valid | every check passed |
| valid with warnings | the checks passed, with caveats listed beside the review, such as support from an abstract only or a bibliography that could not be resolved online |
| INVALID EVIDENCE | problems remained after repair; the draft opens with this warning and names what failed, so treat it as unverified and ask the agent to fix those items or check them yourself |

The checks confirm that the review says what its sources say. They do not
confirm that the sources are right, and they cannot judge meaning, so a sentence
that calls a finding "proven" where the paper says "suggested" passes. Read the
review as critically as you would any draft.

To re-check a workspace yourself, run
`python3 /path/to/co-researcher/skills/literature-review/scripts/validate_review.py --workspace review/{slug}`.
Options, output formats and exit codes are in [docs/validate-review.md](docs/validate-review.md).

How the checker was tested, what it catches and what still gets through are in
[the report](https://coresearcher.poemswe.com/paper/), with a
[technical write-up](https://coresearcher.poemswe.com/paper/write-up/) behind it.

## Research Toolchain

The scripts in `skills/literature-review/scripts/` run through `uv`, and the other evidence-handling skills share them. Run `bash scripts/setup.sh` once to install `uv` and, optionally, store an OpenAlex API key.

| Script | What it does |
|--------|--------------|
| `openalex_cli.py` | cross-disciplinary search over about 250M works |
| `search_arxiv.py` | preprint search |
| `europepmc_api.py` | life-science full text and citation chaining |
| `read_paper.py` | DOI, arXiv ID or PMCID to markdown full text through legal open-access routes; warns on retractions |
| `build_corpus.py` | merges search results into a deduplicated `corpus.json`, keeping screening decisions on re-runs |
| `verify_citations.py` | resolves every citation against OpenAlex, Europe PMC and Crossref, and flags `mismatched`, `not_found` or `retracted` |
| `prisma_counts.py` | PRISMA 2020 flow counts from `corpus.json` |
| `check_claims.py` | checks each quote against its paper and each citation against the corpus |
| `validate_review.py` | the offline gate that runs every check and writes an auditable JSON report |

## Evaluations

The repository carries 33 broad quality cases across 10 capabilities, and a
separate 16-case evidence-integrity set. Results are on the
[Evals dashboard](https://coresearcher.poemswe.com/evals/). A broad quality
score is not an integrity result. Running and publishing evals is covered in
[evals/README.md](evals/README.md).

## Development

```bash
PYTHONNOUSERSITE=1 uv run --no-project --with pytest --with pymupdf4llm --with python-dotenv python -m pytest -q tests
```

The suite runs offline on fixture data. `tests/test_research_smoke.py` alone
covers claim checking, PRISMA counts and the resumable research scaffold. An
opt-in Codex smoke needs an authenticated Codex CLI:
`CO_RESEARCHER_CODEX_SMOKE=1 uv run scripts/codex_smoke_research.py`.

| Path | Holds |
|---|---|
| `skills/` | the research skills, one source for every platform |
| `commands/` | platform commands (`.md` for Claude, `.toml` for Gemini) |
| `.codex/`, `.opencode/` | launchers and install instructions |
| `evals/` | quality and integrity cases, the runner and the dashboard |
| `.claude-plugin/`, `gemini-extension.json`, `GEMINI.md` | manifests |

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=poemswe/co-researcher&type=Date)](https://star-history.com/#poemswe/co-researcher&Date)

## License

MIT. One optional runtime dependency, `pymupdf4llm` (with its `PyMuPDF` backend), is **AGPL-3.0**. `read_paper.py` uses it for PDF text extraction, and `uv` pulls it in only when that script runs. If you redistribute a service built on `read_paper.py`, the AGPL terms apply to that dependency. The Europe PMC JATS and OpenAlex abstract routes don't need it.
