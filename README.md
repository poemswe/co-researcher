# Co-Researcher Plugin

A PhD-level research capabilities plugin for Claude Code that provides specialized agents, skills, and commands for conducting rigorous academic research across multiple methodologies.

## Features

- **8 Specialized Research Agents** - Expert agents for different research approaches
- **7 Research Skills** - Focused skill modules for specific research tasks
- **6 Research Commands** - Quick-access commands for common research operations
- **22 Test Cases** - Comprehensive evaluation suite with automated scoring
- **Python Eval Framework** - CLI-based testing with multi-model support (Claude, Gemini, Codex)
- **Multi-Platform Support** - Works with Claude Code, Gemini CLI, and OpenAI Codex CLI
- **Academic Rigor** - PhD-level methodologies for research tasks
- **Universal Distribution** - Simple "Repository-as-a-Plugin" model

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

### 5. Peer Reviewer
Rigorous academic manuscript/proposal review. Evaluates contribution, methodology, and rigor.

**Use when:** Seeking critical feedback on research drafts or evaluating others' work.

### 6. Ethics Expert
Research ethics, IRB compliance, and data privacy specialist.

**Use when:** Planning studies involving human subjects, sensitive data, or high-impact technologies.

### 5. Qualitative Researcher
Expert in qualitative research methods. Conducts thematic analysis, develops coding schemes, applies grounded theory, performs discourse analysis, and ensures rigor through triangulation.

**Use when:** Analyzing text, interviews, observations, or other non-numerical data

### 8. Quantitative Analyst
Expert in quantitative research methods. Selects appropriate statistical tests, interprets effect sizes, assesses statistical power, identifies common pitfalls, and recommends data visualization.

**Use when:** Analyzing numerical data, planning statistical analyses, interpreting quantitative results

## Core Research Principles

All 8 agents in this suite are governed by these fundamental research principles to ensure PhD-level integrity:

### 1. Factual Integrity
- **No Fabrication**: Agents are strictly forbidden from inventing sources, data, citations, or participant quotes.
- **Evidence-Based**: Every claim must be traceable to a retrieved source or a logical first-principle derivation.

### 2. Honesty Above Fulfillment
- **Quality over Quantity**: If a task asks for a specific count (e.g., "5 papers") but only fewer exist, agents provide ONLY the legitimate items.
- **Reporting Limitations**: If evidence is missing or insufficient to answer a query, reporting the "research gap" is prioritized over "simulating success."

### 3. Uncertainty Calibration
- **Objectivity**: Agents maintain a neutral, PhD-level tone.
- **Probabilistic Language**: Agents use appropriate descriptors (e.g., "highly likely," "preliminary evidence suggests") when data is incomplete or conflicting.

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

All commands support optional arguments for streamlined workflows:

### /research
Start a new research project with scope definition, question formulation, and methodology planning.

**Usage:**
```
/research                          # Interactive: asks for topic
/research machine learning         # Pre-fill topic, skip initial prompt
```

**Argument hint:** `[topic] | [research-question]`

### /analyze
Begin critical analysis of claims, evidence, or research. Evaluate evidence quality, identify logical fallacies, and assess methodological soundness.

**Usage:**
```
/analyze                           # Interactive: asks what to analyze
/analyze AI bias in hiring         # Pre-fill subject, skip initial prompt
```

**Argument hint:** `[claim] | [url] | [topic-to-analyze]`

### /bibliography
Generate and manage research bibliographies. Extract citations, organize sources, and format references in various academic styles.

**Usage:**
```
/bibliography                      # Interactive: asks for style and sources
/bibliography apa                  # Pre-fill style, ready for sources
```

**Argument hint:** `[style] | apa | mla | chicago | ieee | harvard | vancouver`

### /synthesize
Integrate findings from multiple research sources into a coherent summary. Combines evidence, identifies patterns, and draws evidence-based conclusions.

**Usage:**
```
/synthesize                        # Interactive: asks for topic
/synthesize pandemic response      # Pre-fill topic, skip initial prompt
```

**Argument hint:** `[topic] | [research-question]`

### /review
Start a PhD-level academic peer review of a manuscript, research proposal, or draft report.

**Usage:**
```
/review                           # Interactive: asks for content
/review draft.pdf                 # Pre-fill content/file
```

**Argument hint:** `[manuscript-text] | [url] | [draft-file-path]`

### /ethics
Conduct a PhD-level ethical analysis of a research design, study protocol, or data management plan.

**Usage:**
```
/ethics                           # Interactive: asks for protocol
/ethics study_design.md           # Pre-fill protocol
```

**Argument hint:** `[study-design] | [url] | [protocol-file-path]`

## Evaluation Framework

Run tests using the Python CLI:

```bash
cd evals
python run_eval.py list                    # List all tests
python run_eval.py all                     # Run all with Claude
python run_eval.py all --model gemini      # Run with Gemini
python run_eval.py all --model codex       # Run with Codex
python run_eval.py all --model claude:sonnet  # Specific model version
python run_eval.py critical-analyzer       # Test one agent
```

**Full documentation:** See [evals/runner.md](evals/runner.md)

## How It Works

1. **Start with a research goal** - Use `/research` command or directly ask a specialized agent
2. **Choose your methodology** - Each agent handles a different research approach
3. **Get credibility feedback** - Web sources are automatically assessed for reliability
4. **Access specialized skills** - Each skill provides detailed guidance for specific research tasks
5. **Synthesize findings** - Use the synthesis agent or command to integrate your results

## Architecture

```
co-researcher/
├── agents/              # 8 specialized research agents
├── skills/              # 7 focused research skill modules
├── commands/            # Unified hub for Claude (.md) and Gemini (.toml) commands
├── hooks/               # Credibility assessment hook
├── AGENTS.md            # Codex CLI agent manifest
├── GEMINI.md            # Gemini CLI agent manifest
├── gemini-extension.json # Gemini CLI official extension manifest
├── .codex/skills/       # Codex CLI native repository skills
├── evals/               # Python evaluation framework
│   ├── run_eval.py      # CLI entry point
│   ├── lib/core.py      # Core evaluation logic
│   ├── prompts/         # Judge and agent prompt templates
│   ├── rubrics/         # Research, reasoning, structure rubrics
│   └── test-cases/      # 22 tests across 8 agents
└── .claude-plugin/      # Plugin manifest
```

## Quick Start

### Start Research Project
```bash
/research climate change impacts
# → Opens with topic pre-filled
# → Refines research question
# → Suggests appropriate methodology
# → Deploys specialized agents
```

### Analyze a Claim
```bash
/analyze correlation vs causation
# → Begins critical analysis
# → Identifies logical fallacies
# → Evaluates evidence quality
# → Suggests alternatives
```

### Generate Bibliography
```bash
/bibliography apa
# → Ready with APA format selected
# → Provide sources (URLs or text)
# → Returns formatted citations
```

### Synthesize Findings
```bash
/synthesize remote work effectiveness
# → Integrates multiple sources
# → Identifies patterns
# → Quantifies uncertainty
# → Draws conclusions
```

### Evaluate Agent Quality
```bash
cd evals
python run_eval.py all --model gemini
# → Runs all 22 tests across 8 agents
# → Multi-model support (Claude, Gemini, Codex)
# → Generates reports in results/
```

## Publishing & Distribution

For detailed instructions on how to publish this suite for all three platforms, see the [Publishing Guide](PUBLISHING.md).

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
- Markdown-based frontmatter for configuration with `argument-hint` support
- Modular design with independent agents and skills
- Comprehensive test cases in `evals/` directory
- Multi-dimensional evaluation rubrics with automated scoring

### Evaluation Framework

**Test Suite:** 22 test cases across 8 agents (including 6 hard adversarial tests)

| Agent | Tests | Coverage |
|-------|-------|---------|
| Literature Reviewer | 4 | basic-search, gap-analysis, citation-chain, hallucination-detection |
| Critical Analyzer | 4 | fallacy-detection, bias-identification, methodology-critique, contradictory-evidence |
| Hypothesis Explorer | 3 | hypothesis-formulation, variable-mapping, unfalsifiable-claim |
| Quantitative Analyst | 3 | stat-method-selection, effect-size-interpretation, simpson-paradox |
| Qualitative Researcher | 3 | thematic-analysis, coding-strategy, leading-questions |
| Lateral Thinker | 3 | analogy-finding, first-principles, constraint-satisfaction |
| Peer Reviewer | 1 | test-manuscript-critique |
| Ethics Expert | 1 | test-privacy-risk |

**Evaluation Dimensions:**
- **Research Quality** (100 points): Source credibility, comprehensiveness, accuracy, citations
- **Reasoning Quality** (100 points): Logic, bias detection, methodology critique, alternatives
- **Output Structure** (100 points): Organization, completeness, clarity, visual communication

**Passing Criteria:** ≥ 70/100 overall (Hard tests: ≥80)

Run evaluations with:
```bash
cd evals
python run_eval.py all                     # Full suite with Claude
python run_eval.py all --model gemini      # With Gemini
python run_eval.py critical-analyzer       # Agent-specific
```

### Native CLI Usage (Gemini & Codex)

You can also use the agents and commands directly in your preferred CLI:

**Gemini CLI:**
Supports native slash commands!
```bash
gemini /research "Climate Change"
gemini /analyze "https://example.com/paper.pdf"
gemini /review "Provide paper draft"
gemini /ethics "Propose study design"
```

**Codex CLI:**
Supports repository skills!
```bash
codex "$research Climate Change"
codex "$analyze Evidence analysis"
codex "$review Draft manuscript"
codex "$ethics Study design"
```

### Command Argument Support

All commands support optional arguments using `argument-hint` in frontmatter:

```yaml
---
argument-hint: [arg1] [arg2] | option1 | option2
---
```

Arguments are accessible in command content via:
- `$ARGUMENTS` - entire argument string
- `$1`, `$2` - individual positional arguments
- `{% if $ARGUMENTS %}` - conditional rendering

## License

MIT

## Author

poemswe
