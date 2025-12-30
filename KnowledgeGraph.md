# Co-Researcher Knowledge Graph

## Core Concepts

### Specialized Research Agents
- **Literature Reviewer**: Expert in systematic literature reviews and hallucination detection.
- **Critical Analyzer**: Specialist in bias identification and logical fallacy detection.
- **Hypothesis Explorer**: Expert in formulating testable hypotheses and variable mapping.
- **Lateral Thinker**: Expert in cross-domain analogy and first-principles reasoning.
- **Qualitative Researcher**: Specialist in thematic analysis and coding strategies.
- **Quantitative Analyst**: Expert in statistical method selection and interpretation.
- **Peer Reviewer**: Rigorous academic manuscript and proposal evaluator.
- **Ethics Expert**: Specialist in research ethics, IRB compliance, and privacy risks.

### Platform Manifests & Extensions
- **Claude Code**: Native commands and agent definitions in `commands/` and `agents/`.
- **Gemini CLI**: Official extension format with `gemini-extension.json` and centralized `commands/`.
- **OpenAI Codex**: Manifested via `AGENTS.md` and `.codex/skills/`.

### Truthfulness & Honesty
- **Systemic Honesty**: Core Research Principles use ethics-first placement immediately after identity statement (v3.3).
- **Hallucination Detection**: Explicit evaluation against fabricated sources and research gaps.
- **Credibility Triage**: Structured pre-output hooks for source validation (ACCEPT/FLAG/REJECT).

### Evaluation Framework
- **Dynamic Rubric System**: 6 task-specific rubrics mapped to agent capabilities.
- **Persistent Indexing**: Rebuildable `index.md` that scans all existing reports in `results/latest/`.
- **Parallel Testing**: Thread-safe execution runner (`run_eval.py`).
- **Extended Model Support**: Targeting specific versions and reasoning levels (e.g., `--model "codex:gpt-5.2 high"`).
- **Adversarial Judging**: Judge-prompt hardening with anti-gaming measures and peer-review simulation.
- **Benchmark Tracking v2.0**: Two-file architecture for scalability:
  - `benchmark_overview.json`: Lightweight dashboard data (~900B) with run metadata and summary stats
  - `test_results_detail/{run_id}.json`: Full test details (~500KB per run) with agent outputs, judge evaluations, and rubric breakdowns
  - Enables fast dashboard load while preserving full transparency for deep analysis
- **Arena of Agents Dashboard**: A "Battle Royale" themed HTML/JS visualization (`arena.html`) for score trends and leaderboards, now optimized for v2.0 schema.
- **Provider-Specific Tool-Enablement**: Targeted CLI flags for web tools (e.g., `--search` and `--enable web_search_request` for Codex) to ensure platform parity.
- **Stdin Prompt Handling**: Proper `-` argument passing for Codex exec mode to enable programmatic evaluation.

### Prompt Engineering (v1.0.0)
- **Anthropic Best Practices**: XML tags for section delineation (`<principles>`, `<competencies>`, `<protocol>`).
- **52% Size Reduction**: Condensed from 1458 to 695 total lines across 8 agents.
- **PreToolUse Hook**: Credibility pre-filter runs before web fetch, not after.
- **Versioning**: All agents start at v1.0.0 in YAML frontmatter.

### Research Orchestration Engine
- **Intelligent Coordinator**: Injected into `/research` to automate multi-agent workflows.
- **Modes**: Interactive (default), Auto (`--auto`), Plan-Only (`--plan-only`), Manual (`--manual`).
- **Templates**: Predefined DAGs for common scenarios (`quick`, `rigorous`, `comprehensive`).
- **Adaptive Planning**: Dynamic agent selection based on query classification.

## Workflows
- **Discovery**: Agents are discovered by platform-specific manifests at the repository level.
- **Evaluation**: CLI-driven testing using `run_eval.py` with multi-model targeting.
- **Distribution**: Universal "Repository-as-a-Plugin" model.
