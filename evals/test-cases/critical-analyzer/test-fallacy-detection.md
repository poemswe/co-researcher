# Test Case: Logical Fallacy Detection

## Metadata
- **Agent**: critical-analyzer
- **Difficulty**: Medium
- **Focus**: Identifying logical fallacies

## Rubric Profile
- **Primary**: analytical-quality (75%)
- **Secondary**: output-structure (25%)

## Task Prompt

```
Critically analyze this argument:

"Studies show that countries with more ice cream consumption have higher rates of drowning deaths.
Therefore, ice cream consumption causes drowning. We should ban ice cream sales near beaches
to save lives. Anyone who opposes this ban clearly doesn't care about public safety.
Besides, Dr. Smith from the National Ice Cream Council says there's no link,
but he's obviously biased since he works for the ice cream industry."
```

## Expected Behaviors

### Must Identify
- [ ] Correlation/causation fallacy (ice cream → drowning)
- [ ] False dichotomy (ban or don't care about safety)
- [ ] Ad hominem (dismissing Dr. Smith based on affiliation)
- [ ] Confounding variable (summer heat causes both)

### Should Include
- [ ] Clear explanation of each fallacy
- [ ] How the fallacy undermines the argument
- [ ] The valid concern underlying the argument
- [ ] Alternative interpretations of the data
- [ ] What evidence would be needed for valid causal claim

### Should Not Include
- [ ] False positives (labeling valid reasoning as fallacious)
- [ ] Missing the main fallacies
- [ ] Dismissing concerns entirely
- [ ] Confusing types of fallacies

## Evaluation Criteria

### Reasoning Quality (Primary)
- Bias Detection: Are fallacies correctly identified?
- Logical Coherence: Is the analysis itself logical?
- Alternative Explanations: Is the confound identified?

### Research Quality
- Accuracy: Are fallacy types correctly named?

### Output Structure
- Clear enumeration of fallacies
- Evidence for each identification
- Balanced assessment

## Passing Threshold
- Overall Score: ≥ 70/100
- Reasoning Quality: ≥ 80/100
- Must identify at least 3 of 4 main fallacies

## Rubric Weights
- Research Quality: 20%
- Reasoning Quality: 55%
- Output Structure: 25%
