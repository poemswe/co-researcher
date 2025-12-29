# Co-Researcher Plugin

A PhD-level research capabilities plugin for Claude Code that provides specialized agents, skills, and commands for conducting rigorous academic research across multiple methodologies.

## Features

- **6 Specialized Research Agents** - Expert agents for different research approaches
- **5 Research Skills** - Focused skill modules for specific research tasks
- **4 Research Commands** - Quick-access commands for common research operations
- **Credibility Assessment** - Automatic evaluation of web sources for reliability
- **Academic Rigor** - PhD-level methodologies for literature reviews, hypothesis testing, and critical analysis

## Agents

### 1. Literature Reviewer
Expert in systematic literature reviews. Searches academic databases (arXiv, Google Scholar, Semantic Scholar), evaluates source credibility, traces citation chains, identifies research gaps, and synthesizes findings.

**Use when:** Understanding existing research on any topic, building comprehensive bibliographies, identifying research opportunities

### 2. Critical Analyzer
Specialist in rigorous critical analysis. Identifies logical fallacies, methodological weaknesses, cognitive biases, alternative explanations, and evidence quality issues.

**Use when:** Evaluating claims, reviewing research methodology, peer reviewing content, assessing argument validity

### 3. Hypothesis Explorer
Specialist in scientific hypothesis development. Formulates testable hypotheses, maps variables, identifies confounds, designs experiments, and assesses falsifiability.

**Use when:** Developing research questions, designing studies, validating research approaches

### 4. Lateral Thinker
Expert in creative and lateral thinking for research. Finds cross-domain analogies, applies first principles reasoning, uses inversion thinking, explores adjacent possibilities, and generates novel hypotheses.

**Use when:** Stuck on a problem, seeking innovation, exploring unconventional approaches

### 5. Qualitative Researcher
Expert in qualitative research methods. Conducts thematic analysis, develops coding schemes, applies grounded theory, performs discourse analysis, and ensures rigor through triangulation.

**Use when:** Analyzing text, interviews, observations, or other non-numerical data

### 6. Quantitative Analyst
Expert in quantitative research methods. Selects appropriate statistical tests, interprets effect sizes, assesses statistical power, identifies common pitfalls, and recommends data visualization.

**Use when:** Analyzing numerical data, planning statistical analyses, interpreting quantitative results

## Skills

### Literature Review
Conducts systematic literature reviews with academic rigor. Guides you through scope definition, search strategy, source retrieval and screening, quality assessment, data extraction, synthesis, and documentation.

### Hypothesis Testing
Guides scientific hypothesis development and testing methodology. Covers hypothesis formulation, variable mapping, confound identification, research design selection, and falsifiability assessment.

### Critical Analysis
Applies rigorous critical analysis to evaluate claims, arguments, and research. Covers logical analysis, methodological critique, bias identification, evidence strength assessment, and alternative explanation generation.

### Multi-Source Investigation
Conducts systematic investigations across diverse information sources with cross-validation and credibility assessment. Useful for fact-checking, understanding different perspectives, and building comprehensive understanding.

### Research Synthesis
Synthesizes research findings into coherent narratives with uncertainty quantification. Integrates findings from multiple sources into actionable conclusions.

## Commands

### /research
Start a new research project with scope definition, question formulation, and methodology planning. Sets up a research plan with clear phases and deploys appropriate specialized agents.

### /analyze
Begin critical analysis of claims, evidence, or research. Evaluate evidence quality, identify logical fallacies, and assess methodological soundness.

### /bibliography
Generate and manage research bibliographies. Extract citations, organize sources, and format references.

### /synthesize
Integrate findings from multiple research sources into a coherent summary. Combines evidence, identifies patterns, and draws evidence-based conclusions.

## How It Works

1. **Start with a research goal** - Use `/research` command or directly ask a specialized agent
2. **Choose your methodology** - Each agent handles a different research approach
3. **Get credibility feedback** - Web sources are automatically assessed for reliability
4. **Access specialized skills** - Each skill provides detailed guidance for specific research tasks
5. **Synthesize findings** - Use the synthesis agent or command to integrate your results

## Architecture

```
co-researcher/
├── agents/              # 6 specialized research agents
├── skills/             # 5 focused research skill modules
├── commands/           # 4 quick-access research commands
├── hooks/              # Credibility assessment hook
├── evals/              # Test cases and evaluation rubrics
└── .claude-plugin/     # Plugin manifest
```

## Quick Start

### Basic Literature Review
```
Start with: "I need to understand what research says about [topic]"
Triggers: literature-reviewer agent
Output: Systematic review with sources and research gaps
```

### Evaluate a Research Paper
```
Start with: "Please evaluate the methodology of this paper"
Triggers: critical-analyzer agent
Output: Detailed critique of validity, biases, and limitations
```

### Design a Study
```
Start with: "Help me develop a testable hypothesis for my research"
Triggers: hypothesis-explorer agent
Output: Hypothesis framework with variables and design recommendations
```

### Fact-Check Claims
```
Start with: "Investigate whether this claim is true"
Triggers: multi-source-investigation skill
Output: Evidence-based assessment with source verification
```

## Features in Detail

### Academic Database Access
- arXiv (preprints in CS, physics, math)
- Google Scholar (broad academic coverage)
- Semantic Scholar (AI-powered discovery)
- PubMed (biomedical literature)
- SSRN (social sciences, economics)
- ACM Digital Library (computer science)

### Methodological Rigor
- PICO framework for intervention research
- GRADE framework for evidence certainty
- Braun & Clarke's 6-phase thematic analysis
- Grounded theory coding strategies
- Statistical power analysis
- Confound identification and mitigation

### Quality Assurance
- Lincoln & Guba trustworthiness criteria
- Triangulation strategies
- Reflexivity assessment
- Citation chain analysis (backward/forward)
- Source credibility evaluation

### Credibility Assessment Hook
Automatic evaluation of web sources retrieved during research:
- Checks source authority (domain reputation, credentials)
- Flags unreliable sources
- Notes if extraordinary claims need extra verification
- Rates overall source quality (High/Medium/Low)

## Best Practices

1. **Start broad, then narrow** - Begin with literature review to understand the landscape
2. **Use hypothesis-explorer before designing** - Ensure your question is testable and feasible
3. **Combine methodologies** - Use both qualitative and quantitative agents for comprehensive analysis
4. **Check for biases** - Always run critical analysis on your own work
5. **Think laterally** - When stuck, use lateral-thinker for novel perspectives
6. **Assess source credibility** - The plugin provides automatic credibility feedback
7. **Document your process** - Keep track of methodological decisions and rationales

## For Developers

This plugin follows Claude Code plugin architecture:
- Auto-discovered components in `agents/`, `skills/`, `commands/` directories
- Markdown-based frontmatter for configuration
- Modular design with independent agents and skills
- Comprehensive test cases in `evals/` directory
- Evaluation rubrics for quality assessment

### Test Coverage
Comprehensive test cases included for all agents:
- Literature Reviewer: basic search, citation chains, gap analysis
- Critical Analyzer: bias identification, fallacy detection, methodology critique
- Hypothesis Explorer: hypothesis formulation, variable mapping
- Lateral Thinker: analogy finding, first principles reasoning
- Qual Researcher: coding strategy, thematic analysis
- Quant Analyst: statistical method selection, effect size interpretation

### Evaluation Rubrics
- Research quality assessment
- Reasoning quality evaluation
- Output structure validation

## License

MIT

## Author

poemswe
