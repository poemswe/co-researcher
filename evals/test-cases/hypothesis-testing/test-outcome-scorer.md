# Test Case: Testing the Outcome Scorer Before Pre-registration

## Metadata
- **Capability**: hypothesis-testing
- **Implementation Skill**: hypothesis-testing
- **Difficulty**: Medium
- **Focus**: Treating the scoring instrument as part of the pre-registered design

## Rubric Profile
- **Primary**: design-quality (60%)
- **Secondary**: analytical-quality (30%)
- **Tertiary**: output-structure (10%)
- **Timeout**: 900

## Task Prompt

```
I want to test whether giving a coding assistant a planning tool makes its
answers more accurate. I'll run 60 tasks, 30 with the tool and 30 without.
Each answer is free text, and I'll score it by extracting the JSON array from
the answer and comparing it to the expected array.

Write the hypothesis and a pre-registration plan I can freeze before running.
```

## Expected Behaviors

### Must Include
- [ ] H0 and H1 with a stated mechanism
- [ ] Running the JSON extractor on real outputs before the plan is frozen
- [ ] A pre-registered tie-break rule for answers with more than one array
- [ ] Reporting both scores if the scorer changes after data is seen

### Should Include
- [ ] Awkward formats to test (draft then corrected array, fenced blocks, trailing prose)
- [ ] Reading individual misses before attributing a difference to the treatment
- [ ] A Scorer Check line in the output

### Should Not Include
- [ ] Treating the extraction rule as fixed by its operational definition alone
- [ ] Allowing silent scorer changes after seeing results

## Evaluation Criteria

### Design Quality (Primary)
- Measurement Validity: Is the scorer tested before the plan is frozen?
- Pre-registration: Are the tie-break rule and change-reporting rule fixed in advance?

### Analytical Quality
- Does the response explain how a scoring error in one arm can look like a treatment effect?

### Output Structure
- Hypotheses, variable matrix, falsification criteria, scorer check

## Passing Threshold
- Overall Score: ≥ 70/100
- Must include a pre-registered tie-break rule
