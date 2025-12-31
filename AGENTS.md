# Co-Researcher Agents

PhD-level research capabilities for coding agents. Powered by the [Research Orchestration Engine](README.md#research-orchestration-engine).

## Available Agents

### literature-reviewer
Expert in systematic literature reviews. Searches academic databases, evaluates source credibility, traces citation chains, identifies research gaps.

### critical-analyzer
Specialist in rigorous critical analysis. Identifies logical fallacies, methodological weaknesses, cognitive biases, alternative explanations.

### hypothesis-explorer  
Specialist in scientific hypothesis development. Formulates testable hypotheses, maps variables, identifies confounds, assesses falsifiability.

### lateral-thinker
Expert in creative and lateral thinking. Finds cross-domain analogies, applies first principles reasoning, explores adjacent possibilities.

### qual-researcher
Expert in qualitative research methods. Conducts thematic analysis, develops coding schemes, applies grounded theory.

### quant-analyst
Expert in quantitative research methods. Selects appropriate statistical tests, interprets effect sizes, assesses statistical power.

### peer-reviewer
Rigorous academic manuscript/proposal review. Evaluates contribution, methodology, and rigor.

### ethics-expert
Research ethics, IRB compliance, and data privacy specialist.

## Usage

Reference agents from `agents/` directory:
- `agents/literature-reviewer.md`
- `agents/critical-analyzer.md`
- `agents/hypothesis-explorer.md`
- `agents/lateral-thinker.md`
- `agents/qual-researcher.md`
- `agents/quant-analyst.md`
- `agents/peer-reviewer.md`
- `agents/ethics-expert.md`

## Evaluation

Run tests with:
```bash
cd evals
python run_eval.py all --model codex
```
