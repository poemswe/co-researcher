# Test Case: Checking the Study Exercises the Mechanism

## Metadata
- **Capability**: hypothesis-testing
- **Implementation Skill**: hypothesis-testing
- **Difficulty**: Medium
- **Focus**: Confirming the manipulation triggers the hypothesised mechanism before pre-registration

## Rubric Profile
- **Primary**: design-quality (60%)
- **Secondary**: analytical-quality (30%)
- **Tertiary**: output-structure (10%)
- **Timeout**: 900

## Task Prompt

```
Users of our coding assistant report that it keeps repeating the same mistake
within a long session, even after being corrected. We added a memory feature
that stores each correction, and we think it fixes this because the assistant
can look up past corrections before it acts again.

To test it, I wrote 40 short tasks with exact expected answers, each run in a
fresh session: 20 with memory on, 20 with memory off. Most are solved in one
step. I'll compare accuracy between the arms.

Write the hypothesis and a pre-registration plan I can freeze before running.
```

## Expected Behaviors

### Must Include
- [ ] H0 and H1 with the stated mechanism (looking up past corrections)
- [ ] A measurable per-run proxy for the mechanism
- [ ] A pilot with floors stated before the plan is frozen: corrections followed by a chance to repeat the mistake occur in both arms, and stored corrections are retrieved in the memory-on arm
- [ ] A rule that a null result counts against H1 only if both pilot checks passed

### Should Include
- [ ] Noticing that one-step tasks in fresh sessions leave no correction to remember
- [ ] Building tasks from real sessions where the repeated mistake occurred
- [ ] Keeping pilot runs out of the confirmatory sample
- [ ] A Manipulation Check line in the output

### Should Not Include
- [ ] Treating a null accuracy difference as disconfirming the memory mechanism without evidence the mechanism was exercised
- [ ] Freezing the plan with the original task set and no pilot

## Evaluation Criteria

### Design Quality (Primary)
- Manipulation Validity: Does the design show the treatment can act through the stated mechanism?
- Pre-registration: Are the proxy, both floors and the null-result rule fixed in advance?

### Analytical Quality
- Does the response explain why a null result from this task set says nothing about the hypothesis?

### Output Structure
- Hypotheses, variable matrix, manipulation check, falsification criteria

## Passing Threshold
- Overall Score: ≥ 70/100
- Must state a pilot floor for the mechanism proxy
