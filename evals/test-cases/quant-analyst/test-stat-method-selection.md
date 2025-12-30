# Test Case: Statistical Method Selection

## Metadata
- **Agent**: quant-analyst
- **Difficulty**: Medium
- **Focus**: Choosing appropriate statistical tests

## Rubric Profile
- **Primary**: quantitative-quality (75%)
- **Secondary**: output-structure (25%)

## Task Prompt

```
I have the following research scenarios. For each, recommend the appropriate statistical test:

1. Comparing average test scores between a control group and treatment group (30 participants each)
2. Examining the relationship between hours studied and exam grades
3. Comparing customer satisfaction across 4 different product versions
4. Testing if gender distribution differs between two departments
5. Predicting house prices based on square footage, bedrooms, and location
```

## Expected Behaviors

### Must Identify
- [ ] Scenario 1: Independent samples t-test (or Mann-Whitney if assumptions violated)
- [ ] Scenario 2: Pearson correlation (or Spearman if non-linear)
- [ ] Scenario 3: One-way ANOVA (or Kruskal-Wallis)
- [ ] Scenario 4: Chi-square test of independence (or Fisher's exact)
- [ ] Scenario 5: Multiple linear regression

### Should Include
- [ ] Assumptions for each test
- [ ] How to check assumptions
- [ ] Alternative tests if assumptions violated
- [ ] Effect size measures to report
- [ ] Sample size considerations

### Should Not Include
- [ ] Wrong test recommendations
- [ ] Missing key assumptions
- [ ] Confusing test types
- [ ] Recommending overly complex methods

## Evaluation Criteria

### Reasoning Quality (Primary)
- Logical Coherence: Are recommendations well-justified?
- Methodology Critique: Are assumptions addressed?

### Research Quality
- Accuracy: Are test recommendations correct?

### Output Structure
- Clear mapping of scenario to test
- Assumptions listed for each
- Alternatives provided

## Passing Threshold
- Overall Score: ≥ 70/100
- Must get at least 4 of 5 correct
