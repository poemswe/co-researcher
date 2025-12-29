# Test Case: Methodology Critique

## Metadata
- **Agent**: critical-analyzer
- **Difficulty**: Medium
- **Focus**: Evaluating research methodology

## Rubric Profile
- **Primary**: analytical-quality (75%)
- **Secondary**: output-structure (25%)

## Task Prompt

```
Evaluate this research methodology:

Study: Effect of classical music on plant growth
Method: 20 plants divided into two groups. Group A exposed to Mozart 8 hours daily,
Group B in silence. Growth measured after 30 days. Group A grew 15% more on average.
Researchers concluded classical music helps plants grow.

Critique this methodology and assess the validity of the conclusion.
```

## Expected Behaviors

### Must Identify
- [ ] Small sample size (n=10 per group)
- [ ] Lack of randomization details
- [ ] No control for other variables (light, water, temperature)
- [ ] Single measurement point
- [ ] Potential confounds (speaker heat, vibration)
- [ ] Overgeneralization (Mozart → all classical music)

### Should Include
- [ ] Internal validity assessment
- [ ] External validity assessment
- [ ] Suggestions for improved design
- [ ] What conclusions are supported vs. claimed
- [ ] Effect size interpretation

### Should Not Include
- [ ] Dismissing the research entirely
- [ ] Missing major methodological issues
- [ ] Accepting conclusions uncritically
- [ ] Ignoring what the study did well

## Evaluation Criteria

### Reasoning Quality (Primary)
- Methodology Critique: Are validity threats identified?
- Logical Coherence: Is the critique well-reasoned?
- Alternative Explanations: Are confounds proposed?

### Research Quality
- Accuracy: Are methodological terms used correctly?

### Output Structure
- Systematic critique
- Constructive improvements suggested
- Balanced assessment

## Passing Threshold
- Overall Score: ≥ 70/100
- Reasoning Quality: ≥ 75/100

## Rubric Weights
- Research Quality: 20%
- Reasoning Quality: 55%
- Output Structure: 25%
