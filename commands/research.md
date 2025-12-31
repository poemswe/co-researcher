---
description: Start a research project with intelligent agent orchestration
argument-hint: [topic] | [research-question] | --auto | --plan-only | --manual | --template=quick|rigorous|comprehensive
---

# /research - Intelligent Research Orchestration

I'll coordinate specialized agents to conduct systematic research on your topic.

{% if $ARGUMENTS contains "--help" %}
## Usage Modes

**Interactive Mode** (default):
```
/research "impact of social media on teens"
```
I'll propose an execution plan and wait for your approval.

**Auto Mode**:
```
/research "climate change mitigation" --auto
```
I'll execute the plan automatically without confirmation.

**Plan-Only Mode**:
```
/research "AI ethics" --plan-only
```
I'll generate the execution plan but not run it. 

**Manual Mode**:
```
/research "topic" --manual
```
Original behavior - I guide you but you invoke agents manually.

{% elsif $ARGUMENTS %}

## Research Topic
**Query**: {{ $ARGUMENTS | remove: "--auto" | remove: "--plan-only" | remove: "--manual" | remove: "--template=quick" | remove: "--template=rigorous" | remove: "--template=comprehensive" | strip }}

{% if $ARGUMENTS contains "--manual" %}
Now let me help refine your question and create a research plan.

## What I'll do:
1. Help refine your research question
2. Identify appropriate methodology
3. Create a research plan with clear phases
4. **You manually invoke** specialized agents: 
   - Literature Reviewer for academic sources
   - Critical Analyzer for evidence evaluation
   - Hypothesis Explorer for testable questions
   - Quant/Qual Analysts for methodology
   - Lateral Thinker for creative approaches

{% else %}

## 🤖 Orchestration Mode Active

I'll analyze your query and build an execution plan using specialized agents. 

<research_orchestration>

**STEP 1: Query Analysis**
- Extract: Research question, scope, methodology type
- Classify: Literature review | Investigation | Hypothesis generation | Critical analysis | Mixed

**STEP 2: Agent Selection**
Based on query classification, select from:
- `literature-reviewer`: Academic search, citation chains, gap analysis
- `critical-analyzer`: Fallacy detection, bias identification, critique
- `hypothesis-explorer`: Hypothesis formulation, variable mapping
- `lateral-thinker`: Cross-domain analogies, first-principles
- `qual-researcher`: Thematic analysis, grounded theory
- `quant-analyst`: Statistical methods, power analysis
- `peer-reviewer`: Manuscript evaluation, rigor assessment
- `ethics-expert`: IRB compliance, privacy, bias detection
- `grant-writer`: Grant proposal development, specific aims, funding strategy

**STEP 3: Execution Plan Generation**
Create a DAG of agent tasks with clear I/O.

**STEP 4: Plan Presentation**
Present plan and handle mode-specific flow (auto/plan-only/interactive).

**STEP 5: Sequential Execution**
Execute each agent, capture output, and handle transitions or failures.

**STEP 6: Integration**
Synthesize all outputs into a coherent final report.

</research_orchestration>

## Execution Plan

{% if $ARGUMENTS contains "--template=quick" %}
**Template**: Quick Literature Review
1. **literature-reviewer**: Thematic search and summaries
2. **synthesize**: Executive summary of findings

{% elsif $ARGUMENTS contains "--template=rigorous" %}
**Template**: Rigorous Evaluation
1. **literature-reviewer**: Comprehensive search (15-20 sources)
2. **critical-analyzer**: Methodological rigor and bias assessment
3. **peer-reviewer**: Overall evidence quality and critique
4. **synthesize**: Integrated evidence hierarchy

{% elsif $ARGUMENTS contains "--template=comprehensive" %}
**Template**: Comprehensive Research
1. **literature-reviewer** (Search) → **critical-analyzer** (Evaluate) → **hypothesis-explorer** (Gaps) → **lateral-thinker** (Reframing) → **synthesize** (Report)

{% else %}
I'm analyzing your query to determine the optimal workflow...

**Proposed Plan**:
1. **[Agent 1]**: [Task]
2. **[Agent 2]**: [Task using Agent 1 output]
3. **Final Synthesis**: Integrate all results
{% endif %}

---

{% if $ARGUMENTS contains "--auto" %}
**Auto-execution enabled. Starting workflow...**
{% elsif $ARGUMENTS contains "--plan-only" %}
**Plan-only mode. Execution halted.**
{% else %}
**Proceed with this plan?** (yes/no/modify)
{% endif %}

{% endif %}

{% else %}

## What I need from you: 

1. **Topic**: What are you researching?
2. **Question**: Specific question to answer?
3. **Mode**: flags like `--auto`, `--plan-only`, `--manual`
4. **Template**: `--template=quick|rigorous|comprehensive`

**Example**:
```
/research "Does intermittent fasting improve cognitive function?" --auto
```

{% endif %}
