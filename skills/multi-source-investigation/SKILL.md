---
name: multi-source-investigation
description: Conducts systematic investigations across diverse information sources with cross-validation and credibility assessment. Use when researching complex topics, fact-checking claims, understanding different perspectives, or building comprehensive understanding. Triggers on phrases like "investigate", "verify", "fact check", "cross-reference", "multiple sources", "different perspectives on".
tools:
  - WebSearch
  - WebFetch
  - Read
  - Grep
  - Glob
---

# Multi-Source Investigation

This skill guides systematic investigation across diverse sources with rigorous validation.

## Phase 1: Investigation Scope

### Central Question
- What exactly are you investigating?
- What would a complete answer look like?
- What level of certainty is needed?

### Stakeholder Mapping
Identify who has knowledge or interests:
- Domain experts
- Practitioners
- Affected parties
- Critics/skeptics
- Regulators/authorities

### Known Perspectives
- What positions already exist on this topic?
- Who holds each position?
- What evidence supports each?

**CHECKPOINT**: Confirm investigation scope with user.

## Phase 2: Source Diversification

### Source Type Matrix

| Type | Strengths | Limitations | Examples |
|------|-----------|-------------|----------|
| Academic | Peer-reviewed, rigorous | May lag current events | Journals, conferences |
| Official | Authoritative | May have political bias | Government, institutions |
| Industry | Practical, current | Commercial interests | White papers, reports |
| Journalism | Accessible, current | Variable quality | News outlets |
| Expert | Deep knowledge | Individual perspective | Interviews, blogs |
| Primary | Direct evidence | Needs interpretation | Data, documents |

### Minimum Source Diversity
Aim for at least:
- 2+ academic sources
- 2+ credible news/journalism sources
- 1+ official/institutional source
- 1+ expert commentary
- Primary data when available

## Phase 3: Systematic Retrieval

### Search Execution
For each source type:

**Academic**:
```
site:arxiv.org OR site:scholar.google.com [topic]
```

**News/Journalism**:
```
site:reuters.com OR site:apnews.com [topic]
```

**Official**:
```
site:gov OR site:edu [topic]
```

### Information Extraction
For each source, document:
- Source metadata (author, date, outlet)
- Key claims made
- Evidence provided
- Methodology (if applicable)
- Potential biases
- Links to other sources

## Phase 4: Credibility Assessment

### CRAAP Test
| Criterion | Questions |
|-----------|-----------|
| **C**urrency | When published? Updated? Still relevant? |
| **R**elevance | Relates to question? Appropriate depth? |
| **A**uthority | Author credentials? Publisher reputation? |
| **A**ccuracy | Supported by evidence? Verifiable? Reviewed? |
| **P**urpose | Inform, persuade, sell? Biases disclosed? |

### Credibility Scoring
Rate each source 1-5:
- 5: Highly credible (peer-reviewed, authoritative, transparent)
- 4: Credible (reputable source, clear methodology)
- 3: Moderately credible (some concerns but usable)
- 2: Questionable (significant issues, use cautiously)
- 1: Not credible (exclude from analysis)

**Threshold**: Only include sources scoring ≥ 3

## Phase 5: Cross-Validation

### Claim Validation Matrix

| Claim | Source A | Source B | Source C | Consensus | Confidence |
|-------|----------|----------|----------|-----------|------------|
| [Claim 1] | ✓ | ✓ | ✓ | Strong | High |
| [Claim 2] | ✓ | ~ | ✗ | Mixed | Low |
| [Claim 3] | ✓ | ✓ | ? | Partial | Medium |

Legend: ✓=supports, ✗=contradicts, ~=nuanced, ?=no data

### Handling Disagreements
When sources conflict:
1. Assess relative credibility
2. Check for newer evidence
3. Identify reasons for disagreement
4. Note the uncertainty

**CHECKPOINT**: Present conflicting findings for user input.

## Phase 6: Perspective Synthesis

### Perspective Map
```
                    Position A
                        |
    Position D ----[Topic]---- Position B
                        |
                    Position C
```

For each position:
- Who holds it?
- What evidence supports it?
- What are its limitations?
- How does it relate to others?

### Certainty Classification
- **Well-established**: High consensus, strong evidence
- **Likely**: Preponderance of evidence
- **Uncertain**: Conflicting evidence
- **Unknown**: Insufficient data
- **Contested**: Active debate, valid arguments on multiple sides

## Phase 7: Investigation Report

### Output Structure
```
# Investigation: [Topic]

## Question
[Central question investigated]

## Methodology
- Sources searched: [List]
- Time period: [Range]
- Inclusion criteria: [Criteria]

## Source Summary
| Source | Type | Credibility | Key Claims |
|--------|------|-------------|------------|
| [Source] | [Type] | [Score] | [Claims] |

## Key Findings

### Finding 1: [Statement]
- Evidence: [Summary]
- Sources: [Citations]
- Certainty: [Level]

### Finding 2: [Statement]
[Same structure]

## Contested Points
- [Point]: [Summary of disagreement]

## Perspective Map
[Visual or narrative of different positions]

## Limitations
- [Limitation 1]
- [Limitation 2]

## Conclusions
[What can be confidently concluded]
[What remains uncertain]

## References
[Formatted citations]
```
