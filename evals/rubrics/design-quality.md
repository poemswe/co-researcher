# Design Quality Rubric

Evaluates research/study design, feasibility, and ethical considerations.

## Overview

This rubric assesses an agent's ability to design rigorous, feasible, and ethical research studies. Focus is on **design soundness**, not implementation or data collection.

**Use for**: Study design, experimental protocols, IRB preparations, hypothesis formulation, methodology planning.

**Do NOT use for**: Data analysis, literature reviews, results interpretation.

## Dimensions

### 1. Feasibility (0-25 points)

Evaluates practical constraints, resource requirements, and timeline realism.

| Score | Criteria |
|-------|----------|
| 23-25 | Realistic timeline; resource requirements clearly specified and obtainable; practical constraints identified and addressed; recruitment strategy viable; budget considerations evident |
| 18-22 | Generally feasible; most resources identified; constraints mostly addressed; recruitment plausible; minor optimism acceptable |
| 13-17 | Somewhat feasible but challenges underestimated; resource gaps; constraints inadequately addressed; recruitment strategy weak |
| 7-12 | Questionable feasibility; unrealistic timeline; resources underspecified; major constraints ignored |
| 0-6 | Unfeasible design; impossible timeline; resources unavailable; ignores practical realities |

**Scoring Guidance**:
- Timeline: Check against typical project durations (longitudinal studies need years, not months)
- Resources: Personnel, equipment, funding, facilities
- Recruitment: Is target sample size achievable in timeframe? Are inclusion criteria too restrictive?
- Attrition: Is dropout anticipated and accounted for?

### 2. Control Variables (0-25 points)

Evaluates identification and management of confounding variables.

| Score | Criteria |
|-------|----------|
| 23-25 | All major confounds identified; control strategies specified (randomization, matching, statistical control); potential unmeasured confounds acknowledged; mediation/moderation considered |
| 18-22 | Most confounds identified; control strategies mostly appropriate; some unmeasured confounds noted |
| 13-17 | Some confounds identified but key ones missed; control strategies basic; limited awareness of unmeasured confounds |
| 7-12 | Few confounds identified; weak or no control strategies; confounds likely undermine validity |
| 0-6 | No confound identification; no control strategies; will produce spurious findings |

**Scoring Guidance**:
- **Random assignment**: Best control but not always feasible
- **Matching**: Appropriate for quasi-experimental
- **Statistical control**: Regression, ANCOVA (requires measurement)
- **Restriction**: Limiting sample (e.g., same age group)
- Common confounds: SES, age, gender, education, time of measurement

### 3. Ethical Considerations (0-25 points)

Evaluates IRB readiness, consent procedures, and participant protection.

| Score | Criteria |
|-------|----------|
| 23-25 | IRB-ready protocol; informed consent detailed; risks/benefits balanced; vulnerable populations appropriately protected; data privacy/security specified; deception justified if used; debriefing planned |
| 18-22 | Strong ethical framework; consent procedures adequate; risks addressed; privacy considered; minor gaps acceptable |
| 13-17 | Basic ethical considerations; consent mentioned but not detailed; risks underestimated; privacy gaps |
| 7-12 | Inadequate ethics; consent unclear; risks ignored or minimized; no privacy plan; vulnerable populations at risk |
| 0-6 | Unethical design; no consent; serious risks; privacy violations; would be rejected by IRB |

**Scoring Guidance**:
- **Informed consent**: Must include purpose, procedures, risks/benefits, voluntary nature, right to withdraw
- **Risk/benefit**: Minimal risk preferred; benefits should outweigh risks
- **Vulnerable populations**: Children, prisoners, cognitively impaired need extra protection
- **Privacy**: Anonymization vs pseudonymization; secure storage; data sharing plans
- **Deception**: Only if necessary and debriefing planned

### 4. Validity Optimization (0-25 points)

Evaluates internal and external validity of the design.

| Score | Criteria |
|-------|----------|
| 23-25 | High internal validity (causal inferences supported); threats systematically addressed; external validity optimized within constraints; trade-offs explicitly discussed; construct validity strong |
| 18-22 | Good internal validity; major threats addressed; reasonable external validity; trade-offs acknowledged |
| 13-17 | Adequate internal validity but threats remain; external validity limited; trade-offs not fully considered |
| 7-12 | Poor internal validity; threats not addressed; questionable external validity; no awareness of trade-offs |
| 0-6 | Minimal validity; design cannot answer research question; threats overwhelming |

**Scoring Guidance**:
- **Internal validity threats**: Selection, maturation, history, testing, instrumentation, regression to mean, attrition
- **External validity**: Population, ecological, temporal, treatment validity
- **Construct validity**: Operational definitions match theoretical constructs
- **Trade-offs**: Lab vs field (internal vs external validity)

## Overall Design Quality Score

| Total Score | Rating | Interpretation |
|-------------|--------|----------------|
| 90-100 | Excellent | IRB-ready, rigorous design |
| 75-89 | Good | Strong design with minor issues |
| 60-74 | Acceptable | Workable but needs refinement |
| 40-59 | Below Standard | Major design flaws |
| 0-39 | Unacceptable | Fundamentally flawed or unethical |

## Quick Evaluation Checklist

- [ ] Is the design feasible within realistic constraints?
- [ ] Are confounding variables identified and controlled?
- [ ] Is informed consent procedure detailed?
- [ ] Are risks to participants minimized and justified?
- [ ] Is data privacy adequately protected?
- [ ] Does design support causal inferences (if that's the goal)?
- [ ] Is external validity appropriately balanced with internal validity?
- [ ] Are measurement instruments valid and reliable?

## Examples

### High Score (91/100)
*Task: Design study to test if mindfulness reduces anxiety in college students*

**Agent Output**:
- **Feasibility (24/25)**: 12-week timeline; 100 students (power analysis justifies); recruitment via psychology courses + flyers; $5000 budget (instructor fees, assessment materials); IRB submission month 1, recruitment month 2-3
- **Control (22/25)**: Random assignment to mindfulness vs waitlist control; baseline anxiety controlled statistically; demographics matched; notes can't control for concurrent therapy (measured and adjusted)
- **Ethics (24/25)**: Full consent form drafted; minimal risk (mindfulness non-invasive); waitlist gets intervention after study; data anonymized with codes; secure server storage; no vulnerable populations
- **Validity (21/25)**: Random assignment supports causality; validated anxiety scale (GAD-7); threats addressed (testing effects minimized with alternate forms; attrition plan with completer vs ITT analysis); limited to college students (external validity note)

### Low Score (38/100)
*Same task*

**Agent Output**:
- **Feasibility (8/25)**: "8 weeks"; no power analysis; "recruit students"; no budget; timeline vague
- **Control (10/25)**: Mentions "control group" but doesn't specify how assignment occurs; doesn't identify confounds like baseline anxiety, concurrent treatment
- **Ethics (12/25)**: "Get consent"; no risk/benefit discussion; no privacy plan; doesn't address what control group receives
- **Validity (8/25)**: Weak design (no random assignment mentioned); doesn't specify anxiety measure; no discussion of validity threats

## Special Cases

### Quasi-Experimental Design
- **Control (-5 pts)**: If claims causal inference without random assignment
- **Control (+5 pts)**: If uses propensity score matching or other strong quasi-experimental control

### Longitudinal Design
- **Feasibility**: Must account for multi-year timeline, attrition
- **Control**: Repeated measures require accounting for carryover effects

### Qualitative Design
- **Validity**: Trustworthiness criteria replace traditional validity
- **Control**: Not applicable (score N/A or focus on sampling strategy)
