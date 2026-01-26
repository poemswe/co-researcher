# Co-Researcher Skills

PhD-level research capabilities for coding agents. Powered by the [Research Orchestration Engine](README.md#research-orchestration-engine).

## Available Skills

### research-methodology
Expert in research methodology and design. Guides methodology selection, research design, mixed methods approaches, and methodological validation.

### literature-review
Expert in systematic literature reviews. Searches academic databases, evaluates source credibility, traces citation chains, identifies research gaps.

### critical-analysis
Specialist in rigorous critical analysis. Identifies logical fallacies, methodological weaknesses, cognitive biases, alternative explanations.

### hypothesis-testing  
Specialist in scientific hypothesis development. Formulates testable hypotheses, maps variables, identifies confounds, assesses falsifiability.

### lateral-thinking
Expert in creative and lateral thinking. Finds cross-domain analogies, applies first principles reasoning, explores adjacent possibilities.

### qualitative-research
Expert in qualitative research methods. Conducts thematic analysis, develops coding schemes, applies grounded theory.

### quantitative-analysis
Expert in quantitative research methods. Selects appropriate statistical tests, interprets effect sizes, assesses statistical power.

### peer-review
Rigorous academic manuscript/proposal review. Evaluates contribution, methodology, and rigor.

### ethics-review
Research ethics, IRB compliance, and data privacy specialist.

### grant-proposal
Expert grant proposal writer. Transforms research ideas into compelling, fundable proposals for NSF, NIH, ERC.

### research-synthesis
Synthesizes research findings into coherent narratives with uncertainty quantification.

### multi-source-investigation
Conducts systematic investigations across diverse information sources with cross-validation.

### systematic-review
Guidance for conducting PhD-level systematic literature reviews according to PRISMA standards.

## Usage

Reference skills from `skills/` directory:
- `skills/research-methodology/SKILL.md`
- `skills/literature-review/SKILL.md`
- `skills/critical-analysis/SKILL.md`
- `skills/hypothesis-testing/SKILL.md`
- `skills/lateral-thinking/SKILL.md`
- `skills/qualitative-research/SKILL.md`
- `skills/quantitative-analysis/SKILL.md`
- `skills/peer-review/SKILL.md`
- `skills/ethics-review/SKILL.md`
- `skills/grant-proposal/SKILL.md`

## Evaluation

Run tests with:
```bash
cd evals
python run_eval.py all --model codex
```
