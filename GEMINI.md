# Co-Researcher Agents for Gemini

This project provides PhD-level research capabilities for your Gemini CLI sessions.

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

### grant-writer
Expert grant proposal writer. Transforms research ideas into compelling, fundable proposals for NSF, NIH, ERC.

## How to use in Gemini CLI

Gemini automatically discovers these agents when you run it from this directory. You can invoke them by name:

```bash
gemini "Use the literature-reviewer to find recent papers on room temperature superconductors"
gemini "Ask the critical-analyzer to review my methodology in proposal.md"
```

The CLI reads the context from `agents/` and this `GEMINI.md` file automatically.
