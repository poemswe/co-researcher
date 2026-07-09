# Co-Researcher Technical Reference

This document provides a technical overview of the co-researcher system architecture, components, and design decisions.

## Core Components

### Specialized Research Skills

Domain-expert skills provide PhD-level research capabilities:

- **literature-review**: Narrative/scoping reviews with thematic synthesis. **Owns the literature search backend** (`scripts/openalex_cli.py`, `europepmc_api.py`, `search_arxiv.py`, `read_paper.py`) consumed by both review skills and referenced by research-synthesis, multi-source-investigation, and peer-review for source resolution.
- **systematic-review**: PRISMA/Cochrane/JBI reviews with Risk-of-Bias and GRADE. Reuses literature-review's backend scripts.
- **research-methodology**: Design selection and validation; absorbed lateral-thinking's creative-reframing moves (assumption inversion, first-principles deconstruction, cross-domain analogy) as a stuck-problem competency.
- **research-manager**: Project scaffolding and multi-phase orchestration; persists state in research/{slug}/project.json (read-first, write-last)
- **research-synthesis**: Cross-source evidentiary integration with confidence calibration
- **multi-source-investigation**: Claim triangulation and source credibility auditing
- **critical-analysis**: Bias identification and logical fallacy detection
- **hypothesis-testing**: Testable hypothesis formulation and variable mapping
- **qualitative-research**: Thematic analysis and coding strategies
- **quantitative-analysis**: Statistical method selection and interpretation
- **peer-review**: Academic manuscript and proposal evaluation
- **ethics-review**: Research ethics, IRB compliance, and privacy risk assessment
- **grant-writing**: Grant proposal development, specific aims, and funding strategy
- **academic-writing**: Eliminating AI-isms from research prose

### Platform Integration

**Current Version: v2.2.0**

The system supports three CLI platforms through unified skill definitions:

- **Claude Code**: 
  - Installation: `claude plugins install poemswe/co-researcher` or `claude plugins link .`
  - Native commands in `commands/` and skill definitions in `skills/`
  - Plugin manifest: `.claude-plugin/plugin.json`

- **Gemini CLI**: 
  - Installation: `gemini extension add https://github.com/poemswe/co-researcher` or `gemini extension link .`
  - Official extension format via `gemini-extension.json` and centralized commands
  - Context file: `GEMINI.md`

- **OpenAI Codex**: 
  - Installation: Link or copy repository to `~/.codex/skills/co-researcher`
  - Repository skills in `.codex/skills/` and manifest in `AGENTS.md`
  - Skills available via `$` prefix (e.g., `$research`)

All platforms share the same skill definitions in `skills/` but use platform-specific command wrappers.

### Literature Search Backend

Three CLI search scripts ship with the `literature-review` skill, executed via `uv run`:

- **OpenAlex** (`openalex_cli.py`) — cross-disciplinary, ~250M works, citation counts and bibliometrics
- **arXiv** (`search_arxiv.py`) — preprints for CS/physics/math/quant-bio
- **Europe PMC** (`europepmc_api.py`) — life-science open-access full text + forward/backward citation graph
- **Full-text acquisition** (`read_paper.py`) — any identifier (DOI/arXiv/PMCID) → markdown via a fallback chain (cached/user PDF → Europe PMC JATS → arXiv PDF → OpenAlex OA PDF → abstract-only).
- **Citation verification** (`verify_citations.py`) — bibliography file → verified/mismatched/not_found per citation via OpenAlex + Europe PMC; nonzero exit on any failure, used as a pre-output gate by literature-review (protocol step 8) and academic-writing (self-audit).

Both review skills run a persistent funnel in a `review/{slug}/` workspace: `protocol.md` (query log), `corpus.json` (candidate pool + screening decisions, source of truth for PRISMA counts), `papers/{id}/` (full texts + per-paper `notes.md`), `synthesis.md`.

Shared helper modules `http_client.py` (rate limiting/retries/backoff) and `jats.py` (JATS→markdown) live in `scripts/` alongside the backends and are imported as siblings (`import http_client`) — no separate package or build. Stdlib-only; `uv run` puts the script dir on `sys.path`. Everything here is MIT; the only non-MIT footprint is the optional AGPL `pymupdf4llm` runtime dep fetched by uv for `read_paper.py`.

**Prerequisite**: `uv` package manager. One-time setup via `scripts/setup.sh` (detects existing install, falls back to astral.sh installer, warms the dep cache).

### Research Quality Principles

**Systemic Honesty:**
- Ethics-first placement in prompts (immediately after identity statement)
- Explicit hallucination detection against fabricated sources
- Structured credibility triage (ACCEPT/FLAG/REJECT pre-output hooks)

**Pre-fetch Credibility Filtering:**
- Domain validation occurs before web fetch to prevent wasted resources
- Auto-reject list for known misinformation sources
- Flagging system for preprints and blogs

## Evaluation Framework

### Architecture

**Dynamic Rubric System:**
- 6 task-specific rubrics (analytical, quantitative, qualitative, design, reasoning, output)
- Rubrics automatically matched to agent capabilities
- Adversarial judging with anti-gaming measures

**Benchmark v2.0 (Two-File System):**
- `benchmark_overview.json` (~900B): Lightweight run metadata for fast dashboard loading
- `test_results_detail/{run_id}.json` (~500KB): Full test details with agent outputs and judge evaluations
- 10-50x faster dashboard performance while preserving complete transparency

**Testing Infrastructure:**
- Parallel execution via `run_eval.py` with multi-threading (`-j` flag)
- Provider-specific tool enablement for agents; judge runs tool-free for isolation
- Persistent result indexing in `results/latest/index.md`
- Extended model targeting: `--model "provider:version reasoning-level"`
- Robust CLI location via `shutil.which` and `/opt/homebrew/bin` path discovery support for Apple Silicon macOS

### Arena Dashboard

High-performance HTML/JS visualization platform:
- **Editorial Design System**: High-contrast typography, solid colors, and interactive micro-animations
- **Model Leaderboards**: Performance trends with medal-based ranking
- **Capability Matrix**: Star-based capability mapping (⭐⭐⭐/⭐⭐/⭐/❌)
- **Interactive Test Breakdown**:
    - Detailed agent outputs with syntax highlighting and syntax-aware scrolling
    - Dynamic "Must-include" checklist verification (Met/Missed)
    - Overall judge justification and task-specific rubric profiling
- **Historic Run Filtering**: Dropdown selection to view specific past runs (e.g., "Jan 02" vs "Jan 26") alongside model selection
- **Fast Loading**: Optimized for 10-50x faster performance through v2 binary schema

## Research Orchestration Engine

### Intelligent Coordination

The `/research` command automates multi-agent workflows through:
- Query classification and analysis
- Optimal agent selection based on research needs
- Execution plan generation with clear phases
- Coordinated agent sequencing

### Operation Modes

- **Interactive** (default): Generate plan, wait for approval
- **Auto** (`--auto`): Execute plan automatically
- **Plan-Only** (`--plan-only`): Generate plan without execution
- **Manual** (`--manual`): Guided workflow, manual agent invocation

### Templates

Predefined agent combinations for common scenarios:
- `--template=quick`: Fast literature scan
- `--template=rigorous`: Full systematic review
- `--template=comprehensive`: Deep multi-method analysis

## Prompt Engineering

**Design Principles:**
- XML tags for semantic section delineation (`<principles>`, `<competencies>`, `<protocol>`)
- Anthropic best practices for prompt structure
- 52% size reduction (1458 → 695 lines across 8 agents) via efficiency optimizations
- YAML frontmatter versioning (all agents v1.0.0)

**Technical Implementation:**
- Stdin prompt handling with `-` argument for Codex exec mode
- Provider-specific CLI configuration (search flags, tool enablement)

## Distribution Model

Repository-as-a-Plugin architecture:
- Skills discovered via platform-specific manifests
- CLI-driven testing with multi-model support
- Universal compatibility across Claude, Gemini, and Codex platforms

## Commit Message Style

All commits should follow the Conventional Commits format:

```
<type>(<scope>): <subject>

<body>
```

**Format Rules:**
- **Header**: `<type>(<scope>): <subject>` (max 72 characters)
  - `type`: feat, fix, docs, style, refactor, test, chore
  - `scope`: component/area affected (e.g., dashboard, skills, evals)
  - `subject`: imperative mood, lowercase, no period
  
- **Body**: Bullet points explaining the changes
  - Start each point with `-` or `*`
  - Focus on *what* changed and *why*, not *how*
  - Keep lines under 72 characters

**Examples:**
```
feat(dashboard): add normalized capability matrix

- Consolidate duplicate skill names (e.g., "Critical Analysis" only)
- Remove legacy "gemini" from model dropdown
- Default to #1 ranked model on page load
```

```
fix(evals): merge split Gemini test runs into single 26/26 dataset

- Recover 4 missing tests from markdown reports
- Normalize JSON model field to "gemini:gemini-3-flash-preview"
- Update benchmark_overview.json to reference consolidated run
```
