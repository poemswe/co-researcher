# Test Case: Citation Chain Analysis

## Metadata
- **Agent**: literature-reviewer
- **Difficulty**: Hard
- **Focus**: Citation chaining and influence mapping

## Rubric Profile
- **Primary**: research-quality (70%)
- **Secondary**: analytical-quality (20%)
- **Tertiary**: output-structure (10%)

## Task Prompt

```
I found a key paper on transformer architectures in NLP: "Attention Is All You Need" (Vaswani et al., 2017).
Trace its influence: what papers built on it, and what foundational works did it build upon?
Map the citation chain to understand how this work fits into the field's evolution.
```

## Expected Behaviors

### Must Include
- [ ] Identifies papers citing the target (forward citations)
- [ ] Identifies papers cited by the target (backward citations)
- [ ] Maps influence/evolution of ideas
- [ ] Distinguishes foundational vs. derivative works
- [ ] Shows how field evolved before and after

### Should Include
- [ ] Co-citation analysis (papers frequently cited together)
- [ ] Key derivative works identified (BERT, GPT, etc.)
- [ ] Foundational works identified (sequence models, attention mechanisms)
- [ ] Impact metrics discussed
- [ ] Research lineages traced

### Should Not Include
- [ ] Surface-level citation counts only
- [ ] Citations without context/relevance
- [ ] Missing major derivative works
- [ ] Incorrect attribution of ideas

## Evaluation Criteria

### Research Quality (Primary)
- Comprehensiveness: Are major citations captured?
- Accuracy: Are influence relationships correct?
- Source Credibility: Are cited works verified?

### Reasoning Quality
- Logical Coherence: Is the influence map coherent?
- Alternative Explanations: Are parallel developments noted?

### Output Structure
- Visual or narrative flow of influence
- Clear timeline or hierarchy
- Key works highlighted

## Passing Threshold
- Overall Score: ≥ 70/100
- Research Quality: ≥ 80/100 (high bar for accuracy)

## Rubric Weights
- Research Quality: 50%
- Reasoning Quality: 25%
- Output Structure: 25%
