# Co-Researcher Technical Reference

This document provides a technical overview of the co-researcher system architecture, components, and design decisions.

## Core Components

### Specialized Research Agents

Eight domain-expert agents provide PhD-level research capabilities:

- **Literature Reviewer**: Systematic literature reviews, citation analysis, and hallucination detection
- **Critical Analyzer**: Bias identification and logical fallacy detection
- **Hypothesis Explorer**: Testable hypothesis formulation and variable mapping
- **Lateral Thinker**: Cross-domain analogy and first-principles reasoning
- **Qualitative Researcher**: Thematic analysis and coding strategies
- **Quantitative Analyst**: Statistical method selection and interpretation
- **Peer Reviewer**: Academic manuscript and proposal evaluation
- **Ethics Expert**: Research ethics, IRB compliance, and privacy risk assessment
- **Grant Writer**: Grant proposal development, specific aims, and funding strategy

### Platform Integration

The system supports three CLI platforms through unified agent definitions:

- **Claude Code**: Native commands in `commands/` and agent definitions in `agents/`
- **Gemini CLI**: Official extension format via `gemini-extension.json` and centralized commands
- **OpenAI Codex**: Repository skills in `.codex/skills/` and manifest in `AGENTS.md`

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
- Provider-specific tool enablement for platform parity
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
- Agents discovered via platform-specific manifests
- CLI-driven testing with multi-model support
- Universal compatibility across Claude, Gemini, and Codex platforms
