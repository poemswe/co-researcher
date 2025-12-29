# Test Case: Simpson's Paradox Analysis

## Metadata
- **Agent**: quant-analyst
- **Difficulty**: Hard
- **Focus**: Statistical paradox recognition and correct interpretation

## Task Prompt

```
Analyze this hospital performance data and recommend which hospital is better for surgery:

**Overall Success Rates:**
- Hospital A: 90% success (900/1000 surgeries)
- Hospital B: 85% success (850/1000 surgeries)

**Breakdown by Surgery Type:**
| Surgery Type | Hospital A | Hospital B |
|--------------|------------|------------|
| Easy (routine) | 95.0% (760/800) | 98.0% (196/200) |
| Hard (complex) | 70.0% (140/200) | 81.75% (654/800) |

Based on this data, which hospital would you recommend for:
1. A routine surgery?
2. A complex surgery?
3. Overall?

Explain any paradoxes or counterintuitive findings.
```

## Expected Behaviors

### Must Include
- [ ] Identifies Simpson's Paradox by name or concept
- [ ] Correctly notes Hospital B is better for BOTH surgery types
- [ ] Explains the aggregate reversal mechanism
- [ ] Notes the confounding by surgery type distribution
- [ ] Recommends Hospital B for both routine and complex

### Should Include
- [ ] Calculates weighted averages to show mechanism
- [ ] Discusses why aggregate data is misleading
- [ ] Mentions selection bias in patient allocation
- [ ] Suggests Hospital A takes more hard cases

### Should Not Include
- [ ] Recommending Hospital A based on aggregate only
- [ ] Ignoring the stratified breakdown
- [ ] Failing to recognize the paradox
- [ ] Incorrect arithmetic

## Evaluation Criteria

### Research Quality
- Accurate interpretation of provided data
- Correct statistical reasoning

### Reasoning Quality (Primary)
- Recognition of Simpson's Paradox
- Correct causal reasoning about confounding
- Appropriate recommendations

### Output Structure
- Clear presentation of analysis
- Separate answers for each question

## Passing Threshold
- Overall Score: ≥ 80/100
- Reasoning Quality: ≥ 85/100 (must identify paradox)

## Rubric Weights
- Research Quality: 25%
- Reasoning Quality: 55%
- Output Structure: 20%
