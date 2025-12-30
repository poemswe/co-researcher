# Test Case: Basic Literature Search

## Metadata
- **Agent**: literature-reviewer
- **Difficulty**: Easy
- **Focus**: Search strategy and source retrieval

## Rubric Profile
- **Primary**: research-quality (70%)
- **Secondary**: analytical-quality (20%)
- **Tertiary**: output-structure (10%)

## Task Prompt

```
Conduct a literature review on the impact of remote work on employee productivity.
Focus on research from the past 5 years.
```

## Expected Behaviors

### Must Include
- [ ] Uses academic search strategies (site:scholar.google.com, site:arxiv.org)
- [ ] Identifies at least 5 relevant academic sources
- [ ] Assesses source credibility for each
- [ ] Provides search terms used
- [ ] Includes publication dates for recency

### Should Include
- [ ] Uses Boolean operators in searches
- [ ] Includes both quantitative and qualitative studies
- [ ] Notes source authority (author credentials, publication venue)
- [ ] Organizes by themes or findings

### Should Not Include
- [ ] Sources older than 5 years (unless seminal)
- [ ] Non-academic sources without justification
- [ ] Unsupported claims
- [ ] Sources without credibility assessment

## Evaluation Criteria

### Research Quality (Primary)
- Source Credibility: Are sources academic and authoritative?
- Comprehensiveness: Are key perspectives covered?
- Accuracy: Are sources correctly represented?
- Citation Quality: Are sources traceable?

### Reasoning Quality (Secondary)
- Logical Coherence: Does search strategy make sense?
- Alternative Explanations: Are different findings acknowledged?

### Output Structure
- Clear organization of findings
- Search methodology documented
- Sources properly listed

## Passing Threshold
- Overall Score: ≥ 70/100
- Research Quality: ≥ 75/100 (primary focus)
