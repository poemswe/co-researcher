# Co-Researcher Technical Reference

This document provides a technical overview of the co-researcher system architecture, components, and design decisions.

## Core Components

### Specialized Research Skills

Nine domain-expert skills provide PhD-level research capabilities:

- **literature-review**: Systematic literature reviews, citation analysis, and hallucination detection
- **critical-analysis**: Bias identification and logical fallacy detection
- **hypothesis-testing**: Testable hypothesis formulation and variable mapping
- **lateral-thinking**: Cross-domain analogy and first-principles reasoning
- **qualitative-research**: Thematic analysis and coding strategies
- **quantitative-analysis**: Statistical method selection and interpretation
- **peer-review**: Academic manuscript and proposal evaluation
- **ethics-review**: Research ethics, IRB compliance, and privacy risk assessment
- **grant-proposal**: Grant proposal development, specific aims, and funding strategy

### Platform Integration

**Current Version: v2.0.0**

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
