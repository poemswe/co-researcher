# Test Case: Statistical Flaws (Peer Reviewer)

## Metadata
- **Capability**: peer-review
- **Implementation Skill**: peer-review
- **Difficulty**: Medium
- **Area**: Statistical Rigor

## Rubric Profile
- **Primary**: analytical-quality (50%)
- **Secondary**: research-quality (30%)
- **Tertiary**: output-structure (20%)

## Task Prompt

```
Review this manuscript summary as a journal referee:

Title: "Morning Coffee Causes Higher Exam Performance"
Methods: We surveyed 24 university students about their coffee habits and their grades. We measured 15 outcomes (grades in each of 12 courses, overall GPA, attendance, and self-rated focus).
Results: Coffee drinkers had a higher grade in organic chemistry (p = 0.04). Other outcomes are not reported.
Conclusion: Drinking coffee every morning causes better exam performance, and universities should provide free coffee.
```

## Expected Behaviors

### Must Include
- [ ] Identify the Causal Overclaim: State that an observational survey cannot support "causes".
- [ ] Identify Multiple Comparisons: Note that one p = 0.04 result among 15 outcomes is expected by chance without correction.
- [ ] Identify Selective Reporting: Flag that the other 14 outcomes are not reported.
- [ ] Identify the Small Sample: Note that n = 24 gives little power and unstable estimates.

### Should Include
- [ ] Likely confounders, such as sleep or socioeconomic status
- [ ] A request for all outcomes, effect sizes and confidence intervals
- [ ] A clear recommendation, such as major revision or rejection
- [ ] Note that the policy recommendation goes far beyond the evidence

### Should Not Include
- [ ] Accepting the causal conclusion
- [ ] Treating p = 0.04 as convincing on its own
- [ ] Reviewing only writing style

## Evaluation Criteria

### Analytical Quality (Primary)
- Correct identification of each statistical flaw

### Research Quality
- Accuracy of the statistical reasoning

### Output Structure
- Referee-report format with a recommendation

## Passing Threshold
- Overall Score: ≥ 70/100
