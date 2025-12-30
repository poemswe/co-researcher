# Evaluation Framework

Run evaluation tests against co-researcher agents to assess quality and performance.

## Quick Start

```bash
python run_eval.py list           # List all available tests
python run_eval.py all            # Run all tests (default model: claude)
python run_eval.py all -j 4       # Run with 4 parallel jobs
python run_eval.py all --benchmark  # Track scores in benchmark_history.json
python run_eval.py literature-reviewer  # Run all tests for an agent
python run_eval.py literature-reviewer zero-results  # Run specific test
```

## CLI Usage

```bash
python run_eval.py [args] [-m MODEL] [-j JOBS] [-v]

# Examples
python run_eval.py list                              # List available tests
python run_eval.py all -j 8                # Run all tests with 8 jobs
python run_eval.py critical-analyzer -j 4            # Run all analyst tests
python run_eval.py all --model "codex:gpt-5.2 high" # Use GPT-5.2 with high reasoning
python run_eval.py critical-analyzer fallacy-detection  # Run specific test
python run_eval.py literature-reviewer -v            # Verbose output
```

## Model Options

| Provider | Syntax | Example |
|----------|--------|---------|
| `claude` | `claude[:version]` | `claude:sonnet`, `claude:opus` |
| `gemini` | `gemini[:version]` | `gemini:gemini-3-flash-preview` |
| `codex`  | `codex[:version [extra]]` | `codex:gpt-5.2-codex high` |

> [!TIP]
> Use quotes for model strings with spaces: `--model "codex:gpt-5.2-codex high"`

## Available Tests (22 total)

| Agent | Test | Difficulty |
|-------|------|------------|
| **critical-analyzer** | bias-identification | Hard |
| | contradictory-evidence | Hard |
| | fallacy-detection | Medium |
| | methodology-critique | Medium |
| **hypothesis-explorer** | hypothesis-formulation | Medium |
| | unfalsifiable-claim | Hard |
| | variable-mapping | Hard |
| **lateral-thinker** | analogy-finding | Hard |
| | constraint-satisfaction | Hard |
| | first-principles | Hard |
| **literature-reviewer** | basic-search | Easy |
| | citation-chain | Hard |
| | gap-analysis | Medium |
| | hallucination-detection | Hard |
| **qual-researcher** | coding-strategy | Medium |
| | leading-questions | Hard |
| | thematic-analysis | Medium |
| **quant-analyst** | effect-size-interpretation | Medium |
| | simpson-paradox | Hard |
| | stat-method-selection | Medium |

## Scoring (Task-Specific)

The framework uses specialized rubrics based on the agent's task domain:

| Rubric | Agents | Key Focus |
|--------|--------|-----------|
| `analytical-quality` | Critical Analyzer, Lateral Thinker | Logical rigor, fallacy detection |
| `quantitative-quality` | Quantitative Analyst | Statistical accuracy, method choice |
| `qualitative-quality` | Qualitative Researcher | Coding strategy, thematic depth |
| `design-quality` | Hypothesis Explorer, Ethics Expert | Feasibility, ethics, variables |
| `research-quality` | Literature Reviewer, Peer Reviewer | Citation chain, gap analysis |
| `output-structure` | All | Organization, clarity (Fixed 25%) |

**Passing**: ≥70/100 overall (Hard tests: ≥80)

Results saved to `evals/results/`:
- `results/latest/index.md` — Persistent summary (auto-rebuilds)
- `results/latest/*.md` — Individual markdown reports
- `results/history/` — Timestamped archives

## Structure

```
evals/
├── run_eval.py          # CLI entry point
├── lib/core.py          # Core logic
├── prompts/             # Prompt templates
├── rubrics/             # Scoring rubrics
├── test-cases/          # Test definitions
└── results/             # Generated reports
```
