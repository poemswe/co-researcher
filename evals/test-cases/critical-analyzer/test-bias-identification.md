# Test Case: Research Bias Identification

## Metadata
- **Agent**: critical-analyzer
- **Difficulty**: Hard
- **Focus**: Detecting research and cognitive biases

## Rubric Profile
- **Primary**: analytical-quality (75%)
- **Secondary**: output-structure (25%)

## Task Prompt

```
A pharmaceutical company published a study showing their new drug reduces anxiety by 40%.
The study enrolled 50 participants from company employees, ran for 4 weeks,
used self-reported anxiety scales, and compared to placebo. The company funded the research,
and the lead author holds stock in the company. Participants knew if they were getting
the drug or placebo. Three participants who reported side effects dropped out and
were excluded from analysis. The study was registered after data collection.

Identify all potential biases in this research.
```

## Expected Behaviors

### Must Identify
- [ ] Funding bias (company-funded)
- [ ] Conflict of interest (author holds stock)
- [ ] Selection bias (employees as participants)
- [ ] Attrition bias (excluding dropouts with side effects)
- [ ] Detection bias (no blinding)
- [ ] HARKing/publication bias (post-registration)

### Should Include
- [ ] Impact of each bias on validity
- [ ] Direction of bias (inflating or deflating effect)
- [ ] Severity ranking of biases
- [ ] What controls should have been used
- [ ] Whether any findings can be trusted

### Should Not Include
- [ ] False positives (labeling non-biases as biases)
- [ ] Missing major biases
- [ ] Assuming bias equals wrong results
- [ ] Failing to distinguish bias types

## Evaluation Criteria

### Reasoning Quality (Primary)
- Bias Detection Accuracy: Are biases correctly identified?
- Methodology Critique: Are validity threats understood?
- Alternative Explanations: Are confounds considered?

### Research Quality
- Accuracy: Are bias types correctly named?

### Output Structure
- Systematic bias enumeration
- Impact assessment for each
- Recommendations for interpreting results

## Passing Threshold
- Overall Score: ≥ 70/100
- Reasoning Quality: ≥ 80/100
- Must identify at least 5 of 6 main biases

## Rubric Weights
- Research Quality: 20%
- Reasoning Quality: 55%
- Output Structure: 25%
