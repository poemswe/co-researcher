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
- **Systemic Honesty**: Core Research Principles are embedded directly into agent definitions (v3.0).
- **Hallucination Detection**: Explicit evaluation against fabricated sources and research gaps.

### Evaluation Framework
- **Dynamic Rubric System**: 6 task-specific rubrics mapped to agent capabilities (analytical, quantitative, qualitative, design, research, structure).
- **Parallel Testing**: Thread-safe evaluation runner (`run_eval.py`) supporting concurrent agent execution.
- **Multi-Model Support**: Standardized testing and benchmarking for Claude, Gemini, and Codex.
- **PhD-Level Rigor**: 22-test suite for PhD-level research and analysis.

## Workflows
- **Discovery**: Agents are discovered by platform-specific manifests at the repository level.
- **Evaluation**: CLI-driven testing using `run_eval.py` with multi-model targeting.
- **Distribution**: Universal "Repository-as-a-Plugin" model.
