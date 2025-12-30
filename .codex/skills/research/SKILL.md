---
name: research
description: Start a research project with intelligent agent orchestration
metadata:
  short-description: Intelligent Research Orchestration
---

# /research - Intelligent Research Orchestration

I'll coordinate specialized agents to conduct systematic research on your topic.

## Research Topic
**Query**: $ARGUMENTS

## 🤖 Orchestration Mode

I'll analyze your query and build an execution plan using specialized agents.

**Agent Registry**:
- `literature-reviewer`: Academic source search, citation chains
- `critical-analyzer`: Fallacy detection, bias identification
- `hypothesis-explorer`: Hypothesis formulation, variable mapping
- `lateral-thinker`: Cross-domain analogies, creative thinking
- `qual-researcher`: Thematic analysis, coding strategies
- `quant-analyst`: Statistical methods, effect sizes
- `peer-reviewer`: Manuscript evaluation
- `ethics-expert`: IRB compliance, privacy risks

**Orchestration Process**:
1. **Classify Query**: Determine research type
2. **Select Agents**: Choose optimal agent sequence
3. **Generate Plan**: Build execution DAG
4. **Present Plan**: Show workflow to user
5. **Execute**: Run agents sequentially
6. **Synthesize**: Integrate outputs

I'm analyzing your research topic to determine the optimal workflow...

**Proposed Plan**:
[I will generate this based on your query]

**Proceed?** (yes/no/modify)

---

**Modes Supported**:
- Default: Interactive
- `--auto`: Automatic execution
- `--plan-only`: Show plan only
- `--manual`: Traditional guided mode

**Templates**: `--template=quick|rigorous|comprehensive`
