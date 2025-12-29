# Evaluation Framework

Run evaluation tests against co-researcher agents to assess quality and performance.

## Quick Start

```bash
cd evals
python run_eval.py list                    # List all tests
python run_eval.py all                     # Run all tests
python run_eval.py all --model gemini      # Run with Gemini
```

## CLI Usage

```bash
python run_eval.py [args] [-m MODEL] [-v]

# Examples
python run_eval.py list                              # List available tests
python run_eval.py all                     # Run all with Claude
python run_eval.py all --model gemini      # Run with Gemini
python run_eval.py all --model codex       # Run with Codex
python run_eval.py all --model gemini:2.5-pro        # Run with Gemini 2.5 Pro
python run_eval.py critical-analyzer fallacy-detection  # Run specific test
python run_eval.py literature-reviewer -v            # Verbose output
```

## Model Options

| Model | Version Examples |
|-------|------------------|
| `claude` | `claude`, `claude:sonnet`, `claude:opus` |
| `gemini` | `gemini`, `gemini:2.5-pro`, `gemini:flash` |

## Available Tests (20 total)

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

## Scoring

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| Research Quality | 25-50% | Sources, accuracy, citations |
| Reasoning Quality | 25-55% | Logic, bias detection, methodology |
| Output Structure | 20-33% | Organization, clarity |

**Passing**: ≥70/100 overall (Hard tests: ≥80)

## Output

Results saved to `evals/results/`:
- `results/index.md` — Summary report
- `results/<agent>/<test>.md` — Individual test reports

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
