# Test Case: Contradictory Evidence Analysis

## Metadata
- **Agent**: critical-analyzer
- **Difficulty**: Hard
- **Focus**: Reasoning under conflicting evidence

## Rubric Profile
- **Primary**: analytical-quality (75%)
- **Secondary**: output-structure (25%)

## Task Prompt

```
Analyze these two studies that reach opposite conclusions about social media's impact on teen mental health:

**Study A** (Johnson et al., 2024, Journal of Youth Studies)
- Design: Longitudinal observational study, n=500
- Finding: Positive correlation (r=0.45) between social media use and self-reported well-being
- Conclusion: "Social media improves mental health in teens"

**Study B** (Smith et al., 2024, Lancet Psychiatry)  
- Design: Randomized controlled trial, n=10,000
- Finding: Significant negative effect (Cohen's d=-0.80) on clinical depression scores
- Conclusion: "Social media use causes harm to teen mental health"

Which study should we trust more? What explains the discrepancy in findings?
```

## Expected Behaviors

### Must Include
- [ ] Identifies methodology difference (correlational vs experimental/RCT)
- [ ] Notes sample size disparity (500 vs 10,000)
- [ ] Discusses effect size interpretation (r=0.45 vs d=-0.80)
- [ ] Explains why RCT provides stronger causal evidence
- [ ] Notes self-report vs clinical measures difference

### Should Include
- [ ] Discusses confounding in observational studies
- [ ] Mentions reverse causation possibility in Study A
- [ ] Notes publication venue credibility difference
- [ ] Suggests meta-analytic approach or additional studies
- [ ] Discusses ecological validity trade-offs

### Should Not Include
- [ ] Concluding "both studies are equally valid" without justification
- [ ] Ignoring the fundamental design differences
- [ ] Cherry-picking one study without methodological reasoning
- [ ] Dismissing either study without analysis

## Evaluation Criteria

### Research Quality
- Understanding of study design hierarchy
- Recognition of effect size magnitudes
- Assessment of internal vs external validity

### Reasoning Quality (Primary)
- Logical analysis of methodology differences
- Identification of confounds and biases
- Weighing evidence appropriately

### Output Structure
- Clear comparison framework
- Organized by analytical dimensions
- Actionable conclusions

## Passing Threshold
- Overall Score: ≥ 80/100
- Reasoning Quality: ≥ 85/100 (primary focus)

## Rubric Weights
- Research Quality: 25%
- Reasoning Quality: 50%
- Output Structure: 25%
