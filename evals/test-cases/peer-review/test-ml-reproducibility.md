# Test Case: Machine-learning Reproducibility (Peer Reviewer)

## Metadata
- **Capability**: peer-review
- **Implementation Skill**: peer-review
- **Difficulty**: Hard
- **Area**: Reproducibility & Evaluation

## Rubric Profile
- **Primary**: analytical-quality (50%)
- **Secondary**: research-quality (30%)
- **Tertiary**: output-structure (20%)

## Task Prompt

```
Review this conference submission summary:

"We propose a new model for medical image classification that beats the state of the art by 1.2 accuracy points. We tuned the learning rate and architecture by checking accuracy on the test set after each training run, then report the best test accuracy. Results are from a single training run with one random seed. Baseline numbers are copied from the original papers, which used different train/test splits. Code and data will be released after acceptance."
```

## Expected Behaviors

### Must Include
- [ ] Identify Test-set Leakage: State that tuning on the test set and reporting the best test score makes the result optimistically biased.
- [ ] Identify Missing Variance: Note that a single seed cannot show whether a 1.2-point gain exceeds run-to-run variation.
- [ ] Identify Unfair Baselines: Note that baselines evaluated on different splits are not comparable.
- [ ] Identify Missing Artifacts: Flag that withholding code and data prevents reviewers from checking the claims.

### Should Include
- [ ] A request for a held-out validation set, or cross-validation, for tuning
- [ ] A request for multiple seeds with mean and spread
- [ ] A request to re-run baselines on the same split
- [ ] A clear recommendation

### Should Not Include
- [ ] Accepting the 1.2-point improvement as established
- [ ] Focusing only on the model architecture
- [ ] Inventing details about the dataset not in the summary

## Evaluation Criteria

### Analytical Quality (Primary)
- Correct identification of each evaluation flaw

### Research Quality
- Knowledge of sound machine-learning evaluation practice

### Output Structure
- Referee-report format with a recommendation

## Passing Threshold
- Overall Score: ≥ 70/100
