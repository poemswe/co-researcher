---
name: research-synthesis
description: Synthesizes research findings into coherent narratives with uncertainty quantification. Use when integrating findings from multiple sources, creating research summaries, drawing conclusions from evidence, or communicating research results. Triggers on phrases like "synthesize", "integrate findings", "what's the conclusion", "summarize research", "overall picture", "bring together".
tools:
  - WebSearch
  - WebFetch
  - Read
  - Grep
  - Glob
---

# Research Synthesis

This skill guides the integration of diverse research findings into coherent, actionable conclusions.

## Phase 1: Synthesis Preparation

### Input Assessment
- What sources/findings need synthesis?
- What is the overarching research question?
- Who is the audience for this synthesis?
- What decisions will this inform?

### Source Inventory
| Source | Type | Quality | Key Contribution |
|--------|------|---------|------------------|
| [Source] | [Type] | [Rating] | [Main finding] |

### Compatibility Check
- Do sources address the same question?
- Are methodologies compatible?
- Can findings be meaningfully compared?
- Are there definitional inconsistencies?

**CHECKPOINT**: Confirm synthesis scope and purpose with user.

## Phase 2: Pattern Recognition

### Finding Categorization
Group findings by:

**By Conclusion**:
- Consistent findings (agree)
- Inconsistent findings (disagree)
- Complementary findings (different aspects)
- Unique findings (only one source)

**By Evidence Strength**:
- Strong evidence (multiple high-quality sources)
- Moderate evidence (some quality sources)
- Weak evidence (limited or low-quality sources)
- Contested (conflicting strong sources)

### Convergence Analysis
For each major finding:
1. How many sources support it?
2. What is their combined quality?
3. Are there methodological differences?
4. Do any sources contradict?

## Phase 3: Weight Assignment

### Evidence Weighting Factors
| Factor | Weight Modifier |
|--------|-----------------|
| Sample size | Larger = higher weight |
| Study design | RCT > observational |
| Peer review | Reviewed > not reviewed |
| Replication | Replicated > single study |
| Recency | More recent = higher (usually) |
| Relevance | Direct > indirect evidence |

### Confidence Levels
- **High confidence**: Multiple high-quality sources agree, no major contradictions
- **Moderate confidence**: Good evidence but some limitations or gaps
- **Low confidence**: Limited evidence, quality concerns, or contradictions
- **Very low confidence**: Minimal evidence, major limitations
- **Insufficient**: Cannot draw conclusions

## Phase 4: Contradiction Resolution

### When Sources Disagree

**Step 1**: Verify actual disagreement
- Are they measuring the same thing?
- Are conditions comparable?
- Could both be true in different contexts?

**Step 2**: Assess relative quality
- Which has stronger methodology?
- Which has larger sample?
- Which is more recent?

**Step 3**: Identify explanatory factors
- Population differences
- Methodological differences
- Context differences
- Time period differences

**Step 4**: Synthesis approach
| Situation | Approach |
|-----------|----------|
| Quality difference | Favor higher quality |
| Context difference | Specify conditions |
| Genuine debate | Present both positions |
| Unexplained | Acknowledge uncertainty |

**CHECKPOINT**: Present contradictions and proposed resolution for user input.

## Phase 5: Narrative Construction

### Synthesis Structure Options

**Conceptual Framework**:
Organize around theoretical concepts
```
Concept 1 → Concept 2 → Concept 3
    ↓           ↓           ↓
[Findings]  [Findings]  [Findings]
```

**Chronological**:
Trace evolution of understanding
```
Early understanding → Key developments → Current state
```

**Problem-Solution**:
Frame around practical questions
```
Problem → Evidence → Solutions → Remaining gaps
```

**Argument-Based**:
Build toward conclusions
```
Claim → Evidence → Counterclaim → Resolution → Conclusion
```

### Narrative Elements
1. **Opening**: Context and importance
2. **Body**: Organized evidence presentation
3. **Integration**: How pieces connect
4. **Limitations**: What we don't know
5. **Conclusion**: Key takeaways

## Phase 6: Uncertainty Quantification

### Uncertainty Sources
| Source | Description | Handling |
|--------|-------------|----------|
| Measurement | Data collection errors | Acknowledge precision limits |
| Sampling | Non-representative samples | Note generalizability limits |
| Model | Theoretical assumptions | Test sensitivity |
| Conflict | Disagreeing sources | Present range of views |
| Gap | Missing information | Explicitly note unknowns |

### Uncertainty Communication
Use calibrated language:

| Confidence | Language |
|------------|----------|
| Very high (>95%) | "The evidence clearly shows..." |
| High (80-95%) | "The evidence strongly suggests..." |
| Moderate (60-80%) | "The evidence suggests..." |
| Low (40-60%) | "Some evidence indicates..." |
| Very low (<40%) | "Limited evidence hints at..." |

## Phase 7: Actionable Conclusions

### Conclusion Formulation
For each key conclusion:
- State the finding clearly
- Specify confidence level
- Note key supporting evidence
- Acknowledge limitations
- Identify implications

### Recommendation Framework
| Evidence Strength | Recommendation Type |
|-------------------|---------------------|
| Strong | Direct recommendation |
| Moderate | Conditional recommendation |
| Weak | Suggestion for consideration |
| Insufficient | No recommendation (need more research) |

## Phase 8: Documentation

### Output Structure
```
# Research Synthesis: [Topic]

## Executive Summary
[2-3 paragraph overview of key findings]

## Purpose
[Research question and synthesis goals]

## Sources Synthesized
[Brief description of evidence base]

## Key Findings

### Finding 1: [Statement]
**Confidence**: [Level]
**Evidence**: [Summary of supporting sources]
**Caveats**: [Limitations or conditions]

### Finding 2: [Statement]
[Same structure]

## Areas of Uncertainty
- [Uncertainty 1]: [Description and implications]
- [Uncertainty 2]: [Description and implications]

## Contradictions and Debates
- [Topic]: [Summary of disagreement and interpretation]

## Conclusions
[Integrated conclusions with confidence levels]

## Implications
- For [audience 1]: [Implications]
- For [audience 2]: [Implications]

## Research Gaps
[What remains unknown and needs investigation]

## References
[Formatted citations]
```

**CHECKPOINT**: Review synthesis for accuracy and completeness with user.
