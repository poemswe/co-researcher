---
name: literature-review
description: Conducts systematic literature reviews with academic rigor. Use when you need to understand existing research on a topic, identify research gaps, trace the evolution of ideas, or build a comprehensive bibliography. Triggers on phrases like "literature review", "what does research say", "find papers on", "academic sources for", "systematic review of".
tools:
  - WebSearch
  - WebFetch
  - Read
  - Grep
  - Glob
---

# Systematic Literature Review

This skill guides you through conducting a PhD-level literature review.

## Phase 1: Scope Definition

Before searching, clearly define:

### Research Question
- What specific question are you investigating?
- Is it focused enough to be answerable?
- Is it broad enough to find relevant literature?

### Inclusion Criteria
- **Time range**: How far back to search?
- **Source types**: Peer-reviewed only? Include preprints?
- **Language**: English only or multilingual?
- **Geographic scope**: Any regional focus?
- **Discipline**: Single field or interdisciplinary?

### Exclusion Criteria
- What types of sources to exclude?
- Quality thresholds (e.g., minimum citations)?

**CHECKPOINT**: Confirm scope with user before proceeding.

## Phase 2: Search Strategy

### Search Term Development
1. Identify key concepts from research question
2. List synonyms and related terms for each concept
3. Include both technical and common terms
4. Consider field-specific vocabulary

### Boolean Query Construction
```
(concept1 OR synonym1a OR synonym1b)
AND
(concept2 OR synonym2a OR synonym2b)
AND
(concept3 OR synonym3a)
```

### Database Selection
Execute searches using WebSearch with site filters:
- `site:arxiv.org` - Preprints (CS, physics, math)
- `site:scholar.google.com` - Broad academic
- `site:semanticscholar.org` - AI-powered discovery
- `site:pubmed.gov` - Biomedical
- `site:ssrn.com` - Social sciences, economics
- `site:acm.org` - Computer science

## Phase 3: Source Retrieval and Screening

### Initial Screening
For each result:
1. Check title relevance
2. Read abstract
3. Assess publication quality
4. Decide include/exclude

### Full-Text Retrieval
Use WebFetch to get:
- Full paper content (if available)
- Key sections (methods, results, discussion)
- Reference lists for citation chaining

### Citation Chaining
- **Backward**: Check references of key papers
- **Forward**: Find papers citing key works

## Phase 4: Quality Assessment

Rate each source:

| Criterion | Score (1-5) |
|-----------|-------------|
| Authority (author credentials, institution) | |
| Publication venue (impact, peer review) | |
| Methodology (rigor, validity) | |
| Currency (recency, field relevance) | |
| Relevance (alignment with question) | |

**Minimum threshold**: Average score ≥ 3

## Phase 5: Data Extraction

For each included source, extract:
- Full citation information
- Key findings
- Methodology
- Theoretical framework
- Limitations noted
- Relevance to research question

## Phase 6: Synthesis

### Thematic Organization
Group sources by:
- Theoretical approach
- Methodology
- Findings/conclusions
- Time period

### Pattern Identification
- Where do sources agree?
- Where do they conflict?
- How has thinking evolved?
- What methods dominate?

### Gap Analysis
- What questions remain unanswered?
- What populations/contexts are understudied?
- What methods haven't been applied?
- What theoretical gaps exist?

**CHECKPOINT**: Present synthesis summary for user review.

## Phase 7: Documentation

### Output Structure
```
# Literature Review: [Topic]

## Research Question
[Stated question]

## Search Strategy
- Databases: [List]
- Search terms: [Query]
- Date range: [Range]
- Inclusion criteria: [List]

## Sources Identified
- Total found: [N]
- After screening: [N]
- Included: [N]

## Thematic Analysis

### Theme 1: [Name]
[Summary with citations]

### Theme 2: [Name]
[Summary with citations]

## Research Gaps
1. [Gap with evidence]
2. [Gap with evidence]

## Key Sources
[Annotated bibliography]

## References
[Formatted citations]
```
