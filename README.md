# Co-Researcher PhD Suite (v1.0.0)

A professional research suite for conducting rigorous academic research using specialized agents and multi-platform CLI commands. Compatible with **Claude Code**, **Gemini CLI**, and **OpenAI Codex**.

## 🚀 Native Platform Parity

The suite provides native research commands across all supported platforms:

| Feature | Command (Claude) | Slash (Gemini) | Skill (Codex) |
|---------|------------------|----------------|---------------|
| **Research Project** | `/research` | `/research` | `$research` |
| **Critical Analysis** | `/analyze` | `/analyze` | `$analyze` |
| **Bibliography** | `/bibliography` | `/bibliography` | `$bibliography` |
| **Synthesize** | `/synthesize` | `/synthesize` | `$synthesize` |
| **Peer Review** | `/review` | `/review` | `$review` |
| **Ethical Risk** | `/ethics` | `/ethics` | `$ethics` |

## 🎓 Specialized Agents

The suite includes 8 PhD-level agents, each governed by **Systemic Honesty** principles (no fabrication, accuracy over count).

1.  **Literature Reviewer**: Systematic reviews & citation chain analysis.
2.  **Critical Analyzer**: Fallacy detection & bias identification.
3.  **Hypothesis Explorer**: Variable mapping & experimental design.
4.  **Lateral Thinker**: Cross-domain analogies & first-principles.
5.  **Qualitative Researcher**: Thematic analysis & coding strategies.
6.  **Quantitative Analyst**: Statistical power & effect size interpretation.
7.  **Peer Reviewer**: Academic manuscript & proposal critique.
8.  **Ethics Expert**: IRB compliance, privacy risks, and data ethics.

## 🧪 Evaluation Framework

Verify agent performance using the multi-model Python CLI:

```bash
cd evals
python run_eval.py all --model claude
# → Runs 22 tests across 8 agents with progress tracking [i/22]
# → Supports: claude, gemini, codex
# → Results saved with timestamps: results/{agent}/{test}_{model}_{time}.md
```

## 🏗️ Architecture

- `agents/`: Core agent definitions (Markdown).
- `commands/`: Unified platform commands (.md for Claude, .toml for Gemini).
- `.codex/skills/`: Native repository skills for Codex.
- `evals/`: 22 test cases and Python runner.
- manifests: `gemini-extension.json`, `AGENTS.md`, `GEMINI.md`.

## 📜 License
MIT
