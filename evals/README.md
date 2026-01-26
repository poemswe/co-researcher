# Evaluation Framework

Run evaluation tests against co-researcher agents to assess quality and performance.

## Quick Start

```bash
python run_eval.py list           # List all available tests
python run_eval.py all            # Run all tests (default model: claude)
python run_eval.py all -j 4       # Run with 4 parallel jobs
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

## Available Tests (26 total)

| Agent | Test | Difficulty |
|-------|------|------------|
| **critical-analysis** | bias-identification | Hard |
| | contradictory-evidence | Hard |
| | fallacy-detection | Medium |
| | methodology-critique | Medium |
| **ethics-review** | privacy-risk | Hard |
| **grant-proposal** | grant-proposal | Medium |
| **hypothesis-testing** | hypothesis-formulation | Medium |
| | unfalsifiable-claim | Hard |
| | variable-mapping | Hard |
| **lateral-thinking** | analogy-finding | Hard |
| | constraint-satisfaction | Hard |
| | first-principles | Hard |
| **literature-review** | basic-search | Easy |
| | citation-chain | Hard |
| | gap-analysis | Medium |
| | hallucination-detection | Hard |
| **peer-review** | manuscript-critique | Hard |
| **qualitative-research** | coding-strategy | Medium |
| | leading-questions | Hard |
| | thematic-analysis | Medium |
| **quantitative-analysis** | effect-size-interpretation | Medium |
| | simpson-paradox | Hard |
| | stat-method-selection | Medium |
| **research-methodology** | methodology-selection | Medium |
| | methodology-validation | Hard |
| | mixed-methods-design | Hard |

## Scoring (Task-Specific)

The framework uses specialized rubrics based on the agent's task domain:

| Rubric | Agents | Key Focus |
|--------|--------|-----------|
| `analytical-quality` | Critical, Lateral, Methodology | Logical rigor, fallacy detection |
| `quantitative-quality` | Quantitative Analyst | Statistical accuracy, method choice |
| `qualitative-quality` | Qualitative Researcher | Coding strategy, thematic depth |
| `design-quality` | Hypothesis, Ethics, Grant | Feasibility, ethics, variables |
| `research-quality` | Literature, Peer Review | Citation chain, gap analysis |
| `output-structure` | All | Organization, clarity (Fixed 25%) |

**Passing**: ≥70/100 overall (Hard tests: ≥80)

## Results & Benchmarking

### Test Results

Results saved to `evals/results/`:
- `results/latest/index.md` — Persistent summary (auto-rebuilds)
- `results/latest/*.md` — Individual markdown reports
- `results/history/` — Timestamped archives

### Benchmark v2.0 (Automatic)

Every test run automatically generates benchmark data using a two-file architecture:

**`benchmark_overview.json`** (~900B):
- Lightweight run metadata and summary statistics
- Fast dashboard loading (10-50x faster than v1.0)
- Located at `evals/benchmark_overview.json`

**`test_results_detail/{run_id}.json`** (~500KB per run):
- Full test details with agent outputs and judge evaluations
- Rubric-by-rubric scoring breakdowns with reasoning
- Must-include analysis and execution metadata
- Located at `evals/test_results_detail/run_{timestamp}.json`

**View Dashboard**:
```bash
open evals/arena.html
```

**Features:**
- **Model Leaderboards**: Compare performance trends across models.
- **Run ID Filtering**: View specific historic runs (e.g. "Gemini Jan 26") vs "Global Latest".
- **Capability Matrices**: Star-based performance ratings (⭐⭐⭐/⭐⭐/⭐/❌).
- **Deep Inspection**: View full agent outputs with syntax highlighting.

## Structure

```
evals/
├── run_eval.py          # CLI entry point
├── lib/core.py          # Core logic
├── prompts/             # Prompt templates
├── rubrics/             # Scoring rubrics
├── test-cases/          # Test definitions
├── results/             # Generated reports
├── benchmark_overview.json      # Dashboard data (v2.0)
└── test_results_detail/         # Detailed results (v2.0)
```
