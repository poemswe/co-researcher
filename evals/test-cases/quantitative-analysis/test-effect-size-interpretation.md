# Test Case: Effect Size Interpretation

## Metadata
- **Agent**: quantitative-analysis
- **Difficulty**: Medium
- **Focus**: Interpreting effect sizes and practical significance

## Rubric Profile
- **Primary**: quantitative-quality (75%)
- **Secondary**: output-structure (25%)

## Task Prompt

```
A study reports the following results from a training intervention:
- Treatment group (n=500) vs Control group (n=500)
- Mean difference: 2.3 points on a 100-point scale
- Cohen's d = 0.15
- p < 0.001 (highly significant)
- 95% CI for difference: [1.8, 2.8]

The researchers conclude the training was "highly effective" because p < 0.001.
Evaluate this interpretation.
```

## Expected Behaviors

### Must Include
- [ ] Distinction between statistical and practical significance
- [ ] Interpretation of Cohen's d = 0.15 as "small" effect
- [ ] Note that large sample inflates statistical significance
- [ ] Assessment of whether 2.3 points matters practically
- [ ] Critique of "highly effective" conclusion

### Should Include
- [ ] Effect size benchmarks (0.2 small, 0.5 medium, 0.8 large)
- [ ] Confidence interval interpretation
- [ ] Discussion of what practical significance means in context
- [ ] Minimum meaningful difference concept
- [ ] Recommendation for how to report findings accurately

### Should Not Include
- [ ] Accepting conclusion based on p-value alone
- [ ] Dismissing statistically significant results entirely
- [ ] Ignoring the confidence interval
- [ ] Missing the core insight about effect size

## Evaluation Criteria

### Reasoning Quality (Primary)
- Logical Coherence: Is the analysis well-reasoned?
- Methodology Critique: Is the interpretation error identified?

### Research Quality
- Accuracy: Are effect size benchmarks correct?

### Output Structure
- Clear explanation of the issue
- Appropriate nuance
- Actionable recommendation

## Passing Threshold
- Overall Score: ≥ 70/100
- Must identify practical vs statistical significance distinction
