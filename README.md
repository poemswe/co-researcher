# Co-Researcher (v2.7.0)

A professional research suite for conducting rigorous academic research using specialized agents and multi-platform CLI commands. Compatible with **Claude Code**, **Gemini CLI**, **OpenAI Codex**, and **OpenCode**.

Searches run against real scholarly databases (OpenAlex, arXiv, Europe PMC), and every bibliography passes a verification gate that catches fabricated, mismatched, and retracted citations before output.

## Installation

### Claude Code

**Option 1: Slash commands**
```
/plugin marketplace add poemswe/co-researcher
/plugin install co-researcher
```

**Option 2: Claude CLI**
```bash
claude plugin marketplace add poemswe/co-researcher
claude plugin install co-researcher
```

### Gemini CLI

**Option 1: From GitHub**
```bash
gemini extension install https://github.com/poemswe/co-researcher
```

**Option 2: From Local Directory**
```bash
cd /path/to/co-researcher
gemini extension link .
```

### Codex

**Option 1: Ask Codex (Agentic)**
Tell Codex:
```text
Fetch and follow instructions from https://raw.githubusercontent.com/poemswe/co-researcher/main/.codex/INSTALL.md
```

**Option 2: Manual Setup**
```bash
# 1. Clone this repo to ~/.codex/skills/co-researcher
# 2. Add hook to ~/.codex/AGENTS.md
# 3. Run:
~/.codex/skills/co-researcher/.codex/co-researcher-codex bootstrap
```
See [.codex/INSTALL.md](.codex/INSTALL.md) for details.

### OpenCode

**Option 1: Ask OpenCode (Agentic)**
Tell OpenCode:
```text
Fetch and follow instructions from https://raw.githubusercontent.com/poemswe/co-researcher/main/.opencode/INSTALL.md
```

**Option 2: Manual Setup**
```bash
# 1. Clone this repo
# 2. Run the installer:
./.opencode/install.sh
```
See [.opencode/INSTALL.md](.opencode/INSTALL.md) for details.

## Native Platform Parity

The suite provides native research commands across all supported platforms:

| Feature | Command (Claude) | Slash (Gemini) | Skill (Codex) |
|---------|------------------|----------------|---------------|
| **Research Project** | `/research` | `/research` | `$research` |
| **Critical Analysis** | `/analyze` | `/analyze` | `$analyze` |
| **Peer Review** | `/review` | `/review` | `$review` |

Every other capability (methodology, synthesis, ethics review, grant writing, bibliography) is invoked by describing the task in natural language — the matching skill self-triggers via its description. Commands exist only for the three entry points people type habitually.

## Research Orchestration Engine

The `/research` command features intelligent agent orchestration that automatically:
- Analyzes your research question
- Selects optimal agents for your specific needs
- Creates an execution plan with clear phases
- Coordinates multi-agent workflows

### Usage Modes

**Interactive Mode** (default - recommended):
```bash
/research "impact of social media on teenage mental health"
```
Review and approve the execution plan before agents run.

**Auto Mode** (for trusted workflows):
```bash
/research "climate change mitigation strategies" --auto
```
Executes the plan automatically without confirmation.

**Plan-Only Mode** (for review):
```bash
/research "AI ethics frameworks" --plan-only
```
Generates execution plan but doesn't run it.

### Example Workflow

```bash
# 1. Start research with orchestration
/research "effectiveness of remote work on productivity"

# The engine will:
# - literature-reviewer: Find recent studies on remote work outcomes
# - critical-analyzer: Evaluate methodology and bias in key studies  
# - quant-analyst: Interpret effect sizes and statistical significance
# - hypothesis-explorer: Map variables (work location, productivity metrics, confounds)

# 2. Review generated plan and approve execution
# 3. Agents run in coordinated sequence
# 4. Receive integrated findings
```

### Templates

Pre-configured agent combinations for common scenarios:
```bash
/research "topic" --template=quick        # Fast literature scan
/research "topic" --template=rigorous     # Full systematic review
/research "topic" --template=comprehensive # Deep multi-method analysis
```

## Specialized Skills

The suite includes PhD-level research skills, each governed by **Systemic Honesty** principles.

- **critical-analysis**: Rigorous logic checking and fallacy detection
- **ethics-review**: IRB compliance and privacy risk assessment
- **grant-writing**: Funding strategy and proposal development
- **hypothesis-testing**: Variable mapping and experimental design
- **academic-writing**: Eliminating AI-isms from research prose
- **literature-review**: Systematic search and citation analysis
- **multi-source-investigation**: Cross-validation across diverse sources
- **peer-review**: Manuscript critique and methodological review
- **qualitative-research**: Thematic analysis and coding
- **quantitative-analysis**: Statistical power and effect size interpretation
- **research-manager**: Dynamic task scaffolding and polyglot session persistence
- **research-methodology**: Design selection, validation, and creative reframing (cross-domain analogies, first-principles)
- **research-synthesis**: Narrative synthesis with uncertainty quantification
- **systematic-review**: PRISMA-standard systematic review guidance
- **using-co-researcher**: Orientation to the suite — how skills are invoked and the rules that govern them. Activation is automatic: a session-start hook injects the Systemic Honesty principles, and each skill self-triggers from its description.

## Research Toolchain

The `literature-review` skill ships CLI backends (`skills/literature-review/scripts/`, run via `uv`) that the other evidence-handling skills share:

| Script | What it does |
|--------|--------------|
| `openalex_cli.py` | Cross-disciplinary search over ~250M works (OpenAlex) |
| `search_arxiv.py` | Preprint search (CS, physics, math, quant-bio) |
| `europepmc_api.py` | Life-science full text + forward/backward citation chaining |
| `read_paper.py` | Any DOI/arXiv ID/PMCID → markdown full text via legal open-access routes; warns on retracted papers |
| `build_corpus.py` | Merges raw backend results into a deduplicated `corpus.json`; retains trusted author metadata and preserves screening decisions on re-runs |
| `verify_citations.py` | Bibliography gate — resolves every citation (JSON, BibTeX, or plain text) against OpenAlex, Europe PMC, and Crossref/Retraction Watch; reports `verified` / `mismatched` / `not_found` / `retracted` with a nonzero exit on any failure |
| `prisma_counts.py` | PRISMA 2020 flow counts computed from the review workspace's `corpus.json` |
| `check_claims.py` | Claim-to-source gate — verifies evidence/background quotes and binds author-year or ordered numeric citations to trusted corpus records; catches invented evidence, wrong-source attribution, and omissions |
| `validate_review.py` | Deterministic offline one-pass integrity gate — snapshots a submitted review, runs the shared validators, scores explicit evidence units, and emits an auditable JSON report |

One-time setup: `bash scripts/setup.sh` (installs `uv`, optionally stores an OpenAlex API key).

### Plugin validation (offline)

Run the shared validation engine directly from any working directory (Python
3.10 or newer; no package installation is required):

```bash
python3 /path/to/co-researcher/skills/literature-review/scripts/validate_review.py \
  --workspace /path/to/review/example
```

This command is always offline. It never resolves citations over the network.
When a nonempty bibliography has no explicit `--citation-report`, the report
records `citation_resolution_unavailable` as a warning; it does not claim that
the bibliography is verified. An empty bibliography makes that dimension not
applicable. To score a prior offline resolver result, supply its immutable JSON
report explicitly:

```bash
python3 /path/to/co-researcher/skills/literature-review/scripts/validate_review.py \
  --workspace /path/to/review/example \
  --citation-report /path/to/citation-report.json \
  --output /path/outside/review/integrity-report.md
```

Standard output is always the complete compact JSON validation report. An
optional `.json` output is byte-for-byte identical to stdout; `.md` produces a
human-readable audit report. The output must be a new file outside the entire
submitted workspace. Other suffixes, existing files, symlinks, and unsafe path
traversal are refused.

The report identifies engine and validator versions, the target Git commit and
tracked dirty state when available, and both the workspace-manifest hash and
the supplied citation-report hash. Its combined manifest hash commits to both
inputs (or to an explicit null citation-report marker), so provenance can be
audited without network access. Ignored and untracked files do not affect the
Git dirty marker.

Exit codes are `0` for `valid` or `valid_with_warnings`, `1` for `invalid`, and
`2` when usage or an input/output safety problem prevents construction of a
validation report. Exit `2` means the review was not validated and must be
treated as an invalid delivery by an enclosing workflow.

## Research Smoke Tests

Run the deterministic smoke locally or in CI:

```bash
uv run pytest tests/test_research_smoke.py
```

It uses fixture data only, runs offline, and exercises claim verification,
PRISMA counting, and the resumable research scaffold contract. It is separate
from the scored evaluation suite.

For the canonical, self-contained full-root verification, use the cached
isolated environment below. It requires that the cache has already been
populated with these public packages; it does not use ambient Python packages
or network access:

```bash
UV_CACHE_DIR=/private/tmp/co-researcher-uv-cache \
  uv run --offline --with pytest --with pymupdf4llm --with python-dotenv \
  python -B -m pytest -q -p no:cacheprovider tests
```

The real Codex integration smoke is opt-in and requires an authenticated Codex
CLI. It performs no live literature retrieval:

```bash
CO_RESEARCHER_CODEX_SMOKE=1 uv run scripts/codex_smoke_research.py
```

Use `--keep-workdir` to retain its temporary project for debugging. The Codex
smoke is slower and environment-dependent; it does not replace scored evals.

## Evaluation Framework

### Broad quality evaluation (32 cases)

Run the 32-case broad quality benchmark from the repository root:

```bash
python3 evals/run_eval.py all -j 4 --model "codex:gpt-5.2 high"
```

This command requires an authenticated model provider and network access. It
uses the repository's public quality cases; it does not require a private
official-case directory. A case that fails to execute, for example on a usage
limit, is left out instead of scored as zero, and the run prints how to finish
it with the same model:

```bash
python3 evals/run_eval.py all -j 4 --model "codex:gpt-5.2 high" --resume RUN_ID
```

Each run records the plugin release it ran under, and the dashboard compares
runs within one release, on the same case set. Runs from before 2.7.0 were
backfilled with the plugin version in effect at their timestamp.

Historical broad-quality scores are
**Quality-only historical run — not integrity evaluated**: a quality score is
not an integrity result.

### Dedicated literature integrity evaluation

Run the integrity workflow separately; it keeps quality and integrity results
separate:

```bash
python3 evals/run_eval.py literature-review-integrity \
  --model "codex:gpt-5.2 high"
```

This command requires an authenticated model provider and network access. Its
checked-in cases are public synthetic fixtures. Any private official-case
directory is supplied separately by its owner and must not be added to the
repository or CI. Each integrity run writes its auditable result bundle to
`evals/results/runs/<run_id>/`, which Git ignores. To show runs on the
dashboard, publish them by ID:

```bash
python3 evals/publish_integrity_runs.py RUN_ID [RUN_ID ...]
```

The command validates each run, refuses one that contains your home directory
path, copies it to `evals/published/runs/`, and adds it to the published index
that the dashboard reads.

Before a prospective pilot, its owner can verify the runtime-supplied manifest
commitments without executing or scoring any case:

```bash
python3 evals/run_eval.py literature-review-integrity \
  --official-cases-dir PATH \
  --dry-run-manifest-audit
```

This read-only dry run traverses every supplied-root and manifest-path component
with descriptor-relative nofollow opens. It reads file bytes only from
`commitment-index.json` and the manifests it lists, verifies stable file
metadata around each bounded read, and requires NFC Unicode paths. Before it
returns, a completion barrier checks all retained index/manifest descriptors,
reopens and rehashes every complete committed path from the held root, checks
all retained descriptors again, and finally reopens the complete supplied-root
chain from the filesystem anchor. Any observed component, content, or identity
change fails the audit. It does not open committed inputs, scan the directory,
load annotations, construct a model executor or judge, use the network, or
write evaluation results. Supplying the directory without the dry-run flag is
rejected because prospective-case execution is not implemented by this
interface.

### Features
- **Parallel Runner**: Multi-threaded execution with `-j` (jobs) flag
- **Dynamic Rubrics**: 6 specialized rubrics matched to agent skills
- **Extended Targeting**: Support for specific versions and reasoning levels
- **Persistent Indexing**: Rebuildable `latest/index.md` summary

### Benchmark v2.0
Two-file architecture for scalability and transparency:

**Dashboard Data** (`benchmark_overview.json` ~900B):
- Lightweight run metadata and summary stats
- Fast dashboard load times (10-50x improvement)

**Test Details** (`test_results_detail/{run_id}.json` ~500KB):
- Full agent outputs and judge evaluations
- Rubric-by-rubric scoring breakdowns
- Must-include analysis and justifications

### Dashboard server and view

Serve the dashboard locally, then open the displayed URL (normally
`http://localhost:8000`):

```bash
python3 -m http.server 8000 --directory evals
```

The dashboard reads local public result artifacts. It needs neither a model,
network service, nor a private official-case directory after the files are on
disk. A hosted view is also available at **[coresearcher.poemswe.com](https://coresearcher.poemswe.com)**.

Features: Model leaderboards, capability matrices, score trends, and detailed test breakdowns with performance ratings (Excellent/Good/Fair/Poor).

## Architecture

- `skills/`: Specialized research skills (Markdown). Single source of truth for every platform.
- `commands/`: Unified platform commands (.md for Claude, .toml for Gemini).
- `.codex/`: Codex launcher (`co-researcher-codex`) and `bootstrap.md`; it reads `skills/` directly.
- `evals/`: 32 broad quality cases, a separate literature-integrity mode, and
  the Python runner.
- manifests: `.claude-plugin/plugin.json`, `gemini-extension.json`, `GEMINI.md`.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=poemswe/co-researcher&type=Date)](https://star-history.com/#poemswe/co-researcher&Date)

## License
MIT

The project itself is MIT-licensed. One optional runtime dependency carries a stronger license: `pymupdf4llm` (and its `PyMuPDF` backend), used by `skills/literature-review/scripts/read_paper.py` for PDF text extraction, is **AGPL-3.0**. It is pulled in only when that script runs via `uv`, not bundled with the skills. If you redistribute a service built on `read_paper.py`, the AGPL terms apply to that dependency. The Europe PMC JATS and OpenAlex abstract routes do not require it.
