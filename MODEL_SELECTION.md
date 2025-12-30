# Model Selection Strategy

This document outlines the rationale for selecting specific LLM models for different agents and evaluation tasks within the Co-Researcher suite.

## Rationale for Defaults

### Primary Model: Claude 4.5 Sonnet
- **Why**: Sonnet provides the best balance of reasoning speed, PhD-level accuracy, and tool-use reliability. It consistently outperforms most models on complex logical mapping and citation integrity.
- **Usage**: Default for all research agents and the evaluation judge.

## Model-to-Agent Alignment

| Agent | Recommended Model | Rationale |
|-------|-------------------|-----------|
| **critical-analyzer** | `claude:opus` | Requires maximum logical "depth" for fallacy detection and identifying subtle biases. |
| **hypothesis-explorer** | `gemini:pro` | Benefit from Gemini's lateral thinking and large context window for mapping complex variable relationships. |
| **literature-reviewer** | `claude:sonnet` | High precision in citation handling and low hallucination rate. |
| **quant-analyst** | `gpt-4o` | Stronger statistical reasoning and code-execution accuracy for complex data analysis. |
| **lateral-thinker** | `claude:opus` | Creative leaps require the largest parameter count and most sophisticated reasoning chains. |

## Evaluation Costs vs. Quality

- **Sonnet** is used for evaluation judging to maintain high standards without the extreme latency/cost of Opus.
- **Codex (GPT-5.2)** is used as an execution-focused baseline for rapid, automated testing where creative depth is less critical than protocol adherence.

## Configuration

Models can be overridden in the agent's frontmatter or via the evaluation CLI:
```bash
python run_eval.py --model "codex:gpt-5.2 high"
```
