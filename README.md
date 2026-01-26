# Co-Researcher (v1.1.1)

A professional research suite for conducting rigorous academic research using specialized agents and multi-platform CLI commands. Compatible with **Claude Code**, **Gemini CLI**, and **OpenAI Codex**.

## Installation

### Claude Code

**Option 1: From Marketplace (Recommended)**
```bash
claude plugins install poemswe/co-researcher
```

**Option 2: From Local Directory**
```bash
cd /path/to/co-researcher
claude plugins link .
```

**Verification:**
```bash
claude plugins list
Type /research to test
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

**Verification:**
```bash
gemini extension list
Type /research to test
```

### VS Code (via Codex)

**From Local Directory:**
1. Clone the repository:
   ```bash
   git clone https://github.com/poemswe/co-researcher.git
   cd co-researcher
   ```

2. Link to Codex workspace:
   ```bash
   mkdir -p ~/.codex/skills
   ln -s "$(pwd)" ~/.codex/skills/co-researcher
   ```

3. Verify in VS Code:
   - Open Command Palette (Cmd+Shift+P)
   - Type "Codex: List Skills"
   - Look for `$research` in the available skills

**Alternative: Direct Copy**
```bash
cp -r /path/to/co-researcher ~/.codex/skills/
```

## Native Platform Parity

The suite provides native research commands across all supported platforms:

| Feature | Command (Claude) | Slash (Gemini) | Skill (Codex) |
|---------|------------------|----------------|---------------|
| **Research Project** | `/research` | `/research` | `$research` |
| **Methodology** | `/methodology` | `/methodology` | `$methodology` |
| **Critical Analysis** | `/analyze` | `/analyze` | `$analyze` |
| **Bibliography** | `/bibliography` | `/bibliography` | `$bibliography` |
| **Synthesize** | `/synthesize` | `/synthesize` | `$synthesize` |
| **Peer Review** | `/review` | `/review` | `$review` |
| **Ethical Risk** | `/ethics` | `/ethics` | `$ethics` |
| **Grant Proposal** | `/grant` | `/grant` | `$grant` |

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

## Specialized Agents

The suite includes 10 PhD-level agents, each governed by **Systemic Honesty** principles (no fabrication, accuracy over count).

1.  **Methodology Expert**: Research design, methodology selection, and validation.
2.  **Literature Reviewer**: Systematic reviews & citation chain analysis.
3.  **Critical Analyzer**: Fallacy detection & bias identification.
4.  **Hypothesis Explorer**: Variable mapping & experimental design.
5.  **Lateral Thinker**: Cross-domain analogies & first-principles.
6.  **Qualitative Researcher**: Thematic analysis & coding strategies.
7.  **Quantitative Analyst**: Statistical power & effect size interpretation.
8.  **Peer Reviewer**: Academic manuscript & proposal critique.
9.  **Ethics Expert**: IRB compliance, privacy risks, and data ethics.
10. **Grant Writer**: Grant proposal development & funding strategy.

## Evaluation Framework

Verify agent performance with the v2.0 benchmark system:

```bash
cd evals
python run_eval.py all -j 4 --model "codex:gpt-5.2 high"
```

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

**Arena Dashboard**:
```bash
open evals/arena.html
```
View model leaderboards, capability matrices, and score trends with performance ratings (Excellent/Good/Fair/Poor).

## Architecture

- `agents/`: Core agent definitions (Markdown).
- `commands/`: Unified platform commands (.md for Claude, .toml for Gemini).
- `.codex/skills/`: Native repository skills for Codex.
- `evals/`: 22 test cases and Python runner.
- manifests: `gemini-extension.json`, `AGENTS.md`, `GEMINI.md`.

## License
MIT
