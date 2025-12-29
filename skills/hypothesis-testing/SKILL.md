---
name: hypothesis-testing
description: Guides scientific hypothesis development and testing methodology. Use when formulating research questions, developing testable hypotheses, designing experiments, or evaluating research approaches. Triggers on phrases like "hypothesis", "test if", "experiment design", "research question", "how would I test", "is it true that".
tools:
  - WebSearch
  - WebFetch
  - Read
  - Grep
  - Glob
---

# Hypothesis Testing Workflow

This skill guides you through rigorous hypothesis development and testing methodology.

## Phase 1: Observation and Question

### Starting Point Analysis
- What observation or phenomenon prompted this inquiry?
- What patterns or anomalies are you seeing?
- What existing knowledge is relevant?

### Research Question Formulation
Good research questions are:
- **Focused**: Specific enough to answer
- **Researchable**: Can be investigated empirically
- **Complex**: Requires analysis, not just facts
- **Arguable**: Has multiple possible answers

### Question Types
| Type | Example | Hypothesis Style |
|------|---------|------------------|
| Descriptive | "What is X?" | Not hypothesis-driven |
| Relational | "Is X related to Y?" | Correlation hypothesis |
| Causal | "Does X cause Y?" | Causal hypothesis |
| Comparative | "Is X different from Y?" | Difference hypothesis |

**CHECKPOINT**: Confirm research question with user.

## Phase 2: Hypothesis Construction

### Hypothesis Components
```
If [independent variable/condition]
Then [dependent variable/outcome]
Because [theoretical mechanism]
```

### Null vs Alternative Hypothesis
- **H₀ (Null)**: No effect/relationship exists
- **H₁ (Alternative)**: Effect/relationship exists

Example:
- H₀: Training method has no effect on performance
- H₁: Training method improves performance

### Hypothesis Quality Check
- [ ] Is it testable with available methods?
- [ ] Is it falsifiable (can be proven wrong)?
- [ ] Does it make specific predictions?
- [ ] Is it parsimonious (simplest explanation)?
- [ ] Is it consistent with existing knowledge?
- [ ] Does it specify the mechanism?

## Phase 3: Variable Mapping

### Variable Identification
| Variable | Type | Operationalization |
|----------|------|-------------------|
| [Name] | Independent (IV) | [How measured/manipulated] |
| [Name] | Dependent (DV) | [How measured] |
| [Name] | Control | [How held constant] |
| [Name] | Confound | [Potential interference] |
| [Name] | Mediator | [Explains mechanism] |
| [Name] | Moderator | [Affects strength] |

### Operationalization Criteria
For each variable:
- Concrete, observable indicators
- Reliable measurement method
- Valid representation of construct
- Appropriate scale (nominal, ordinal, interval, ratio)

## Phase 4: Prediction Generation

### Specific Predictions
From your hypothesis, derive:
1. **If H₁ true**: [Specific observable outcome]
2. **If H₀ true**: [Expected null result]
3. **Effect direction**: [Increase/decrease/differ]
4. **Effect magnitude**: [Expected size]

### Boundary Conditions
- Under what conditions should hypothesis hold?
- Where might it not apply?
- What would moderate the effect?

**CHECKPOINT**: Validate predictions align with user's research goals.

## Phase 5: Design Selection

### Experimental vs Observational
```
Can you manipulate the IV?
├── Yes → Experimental design
│   ├── Random assignment possible? → True experiment
│   └── No random assignment? → Quasi-experiment
└── No → Observational design
    ├── Over time? → Longitudinal
    └── Single point? → Cross-sectional
```

### Design Options
| Design | Strengths | Limitations |
|--------|-----------|-------------|
| RCT | Causal inference | Artificial, expensive |
| Quasi-experiment | More feasible | Weaker causal claims |
| Cohort | Temporal sequence | Attrition, time |
| Case-control | Efficient for rare outcomes | Recall bias |
| Cross-sectional | Quick, inexpensive | No causation |

### Control Strategies
| Threat | Control Method |
|--------|---------------|
| Selection bias | Random assignment, matching |
| History | Control group, isolation |
| Maturation | Control group, short duration |
| Testing effects | Control group, alternate forms |
| Instrumentation | Standardization, calibration |

## Phase 6: Confound Mitigation

### Confound Analysis
For each potential confound:
1. How could it affect the DV?
2. How might it correlate with the IV?
3. What's the mitigation strategy?

### Mitigation Strategies
| Strategy | How It Works |
|----------|--------------|
| Random assignment | Distributes confounds equally |
| Matching | Pairs similar participants |
| Statistical control | Adjust in analysis |
| Counterbalancing | Vary order of conditions |
| Blinding | Remove bias from knowledge |
| Standardization | Same procedures for all |

## Phase 7: Falsifiability Statement

### Define Falsification Criteria
Specify exactly what results would falsify H₁:
- What outcome pattern rejects the hypothesis?
- What effect size is too small to matter?
- What statistical threshold applies?

### Pre-registration Elements
- Hypothesis (before seeing data)
- Analysis plan (before seeing data)
- Sample size justification
- Exclusion criteria
- Success/failure criteria

## Phase 8: Documentation

### Output Structure
```
# Hypothesis Development: [Topic]

## Research Question
[Clearly stated question]

## Hypotheses
- H₀: [Null hypothesis]
- H₁: [Alternative hypothesis]
- Mechanism: [Why we expect this]

## Variables
| Variable | Type | Operationalization |
|----------|------|-------------------|
| [Name] | [Type] | [Definition] |

## Predictions
1. If H₁: [Expected outcome]
2. If H₀: [Expected outcome]
3. Effect size: [Expected magnitude]

## Design
- Type: [Design name]
- Justification: [Why this design]

## Confounds and Controls
| Confound | Risk | Mitigation |
|----------|------|------------|
| [Name] | [Level] | [Strategy] |

## Falsification Criteria
[Specific conditions that would reject H₁]

## Feasibility Notes
- Resources needed: [List]
- Ethical considerations: [List]
- Timeline estimate: [Estimate]
```
