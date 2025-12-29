---
name: critical-analysis
description: Applies rigorous critical analysis to evaluate claims, arguments, and research. Use when evaluating evidence quality, peer reviewing content, assessing argument validity, or identifying weaknesses in reasoning. Triggers on phrases like "critically analyze", "evaluate this", "review this paper", "check the logic", "assess the evidence", "find flaws", "peer review".
tools:
  - WebSearch
  - WebFetch
  - Read
  - Grep
  - Glob
---

# Critical Analysis Framework

This skill guides rigorous critical evaluation of claims, arguments, and research.

## Phase 1: Content Mapping

### Claim Extraction
Identify all claims in the material:
1. **Central claim**: The main argument or thesis
2. **Supporting claims**: Claims used to support the central claim
3. **Implicit claims**: Unstated assumptions
4. **Hedged claims**: Qualified or conditional statements

### Argument Structure Mapping
```
Conclusion (Central Claim)
     ↑
Premise 1 + Premise 2 + Premise 3
     ↑           ↑           ↑
[Evidence]  [Evidence]  [Evidence]
```

### Stakeholder Context
- Who created this content?
- What are their credentials?
- What are potential motivations/interests?
- Who funded the work?

**CHECKPOINT**: Confirm scope of analysis with user.

## Phase 2: Evidence Assessment

### Evidence Inventory
| Claim | Evidence Provided | Evidence Type | Quality |
|-------|-------------------|---------------|---------|
| [Claim] | [What evidence] | [Type] | [Rating] |

### Evidence Types Hierarchy
(Strongest to weakest)
1. Systematic reviews/meta-analyses
2. Randomized controlled trials
3. Cohort studies
4. Case-control studies
5. Cross-sectional studies
6. Case reports
7. Expert opinion
8. Anecdote

### Evidence Quality Markers
**Strong evidence**:
- Peer-reviewed
- Replicable methodology
- Adequate sample size
- Appropriate controls
- Transparent reporting

**Weak evidence**:
- Not peer-reviewed
- Vague methodology
- Small sample
- No controls
- Selective reporting

## Phase 3: Logical Analysis

### Deductive Validity Check
For deductive arguments:
- Are premises true?
- Does conclusion follow necessarily from premises?
- Is the logical form valid?

### Inductive Strength Check
For inductive arguments:
- Is the sample representative?
- Is the sample large enough?
- Are there counterexamples?
- How strong is the correlation?

### Common Fallacy Scan

**Relevance Fallacies**:
- [ ] Ad hominem (attacking person, not argument)
- [ ] Appeal to authority (authority as only evidence)
- [ ] Appeal to emotion (emotions instead of logic)
- [ ] Red herring (irrelevant distraction)

**Presumption Fallacies**:
- [ ] Begging the question (conclusion in premise)
- [ ] False dichotomy (only two options presented)
- [ ] Hasty generalization (insufficient sample)
- [ ] Slippery slope (unsupported chain)

**Ambiguity Fallacies**:
- [ ] Equivocation (shifting word meaning)
- [ ] Amphiboly (grammatical ambiguity)
- [ ] Composition (part → whole error)
- [ ] Division (whole → part error)

**Causal Fallacies**:
- [ ] Post hoc (sequence ≠ causation)
- [ ] Correlation/causation confusion
- [ ] Single cause (ignoring multiple factors)
- [ ] Wrong direction (reversed causality)

## Phase 4: Bias Detection

### Cognitive Bias Scan
- [ ] **Confirmation bias**: Only supporting evidence cited
- [ ] **Anchoring**: Over-reliance on initial information
- [ ] **Availability**: Overweighting recent/memorable
- [ ] **Hindsight**: "Knew it all along" framing
- [ ] **Survivorship**: Ignoring failures

### Research Bias Scan
- [ ] **Selection bias**: Non-representative sampling
- [ ] **Publication bias**: Missing negative results
- [ ] **Funding bias**: Results favor funder
- [ ] **Allegiance bias**: Theory commitment
- [ ] **Spin**: Misleading presentation

### Conflict of Interest Check
- Financial relationships?
- Ideological commitments?
- Career incentives?
- Institutional pressures?

**CHECKPOINT**: Present initial concerns for user input.

## Phase 5: Methodology Critique

### For Empirical Research

**Design Assessment**:
- Appropriate for research question?
- Adequate controls?
- Randomization where possible?
- Blinding implemented?

**Internal Validity Threats**:
- [ ] Selection: Non-equivalent groups
- [ ] History: External events
- [ ] Maturation: Natural changes
- [ ] Testing: Prior test effects
- [ ] Instrumentation: Measurement changes
- [ ] Regression: Extreme scores normalizing
- [ ] Attrition: Differential dropout

**External Validity Threats**:
- [ ] Population: Sample ≠ target population
- [ ] Setting: Lab ≠ real world
- [ ] Time: Results time-bound
- [ ] Treatment variation: Inconsistent implementation

**Statistical Issues**:
- [ ] Appropriate tests used?
- [ ] Assumptions checked?
- [ ] Multiple comparison corrections?
- [ ] Effect sizes reported?
- [ ] Power adequate?

## Phase 6: Alternative Explanations

### Alternative Hypothesis Generation
For each major finding, consider:
1. Could confounds explain this?
2. Could reverse causation explain this?
3. Could third variables explain this?
4. Could measurement artifacts explain this?
5. Could chance explain this?

### Parsimony Assessment
- Are simpler explanations available?
- Does the complexity of the explanation match the evidence?
- Are extraordinary claims supported by extraordinary evidence?

## Phase 7: Strength Assessment

### Overall Quality Rating

| Dimension | Score (1-5) | Notes |
|-----------|-------------|-------|
| Evidence quality | | |
| Logical validity | | |
| Methodology rigor | | |
| Bias control | | |
| Alternative consideration | | |
| **Overall** | | |

### Confidence Classification
- **Strong**: High-quality evidence, valid logic, minimal bias
- **Moderate**: Good evidence with some limitations
- **Weak**: Significant issues but some merit
- **Very weak**: Major flaws, unreliable conclusions
- **Invalid**: Fundamental errors, reject conclusions

## Phase 8: Documentation

### Output Structure
```
# Critical Analysis: [Title/Topic]

## Summary
[Brief overview of what was analyzed]

## Central Claims
1. [Main claim]
2. [Supporting claims]

## Evidence Assessment
| Claim | Evidence | Type | Quality |
|-------|----------|------|---------|
| [Claim] | [Evidence] | [Type] | [Rating] |

## Logical Issues
1. [Issue]: [Explanation]
2. [Issue]: [Explanation]

## Bias Concerns
- [Bias type]: [How it manifests]

## Methodology Critique
- [Issue]: [Impact on validity]

## Alternative Explanations
1. [Alternative]: [Why plausible]
2. [Alternative]: [Why plausible]

## Strengths
- [Strength 1]
- [Strength 2]

## Weaknesses
- [Weakness 1]
- [Weakness 2]

## Overall Assessment
**Rating**: [Strong/Moderate/Weak/Very Weak]
**Key Concern**: [Most significant issue]
**Recommendation**: [Accept/Accept with caveats/Reject/Need more information]
```

**CHECKPOINT**: Review analysis completeness with user.
