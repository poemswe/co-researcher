# Test Case: Unfalsifiable Claim Analysis

## Metadata
- **Agent**: hypothesis-explorer
- **Difficulty**: Hard
- **Focus**: Identifying scientific vs pseudoscientific claims

## Rubric Profile
- **Primary**: design-quality (60%)
- **Secondary**: analytical-quality (30%)
- **Tertiary**: output-structure (10%)

## Task Prompt

```
A researcher presents the following hypothesis:

"Homeopathic remedies are effective, but only when the patient genuinely believes in them. Any clinical trial that fails to show effectiveness simply proves that the test subjects lacked sufficient faith in the treatment."

Your task:
1. Evaluate whether this is a valid scientific hypothesis
2. Identify any logical or methodological problems
3. Propose modifications that would make this testable
4. Generate 3 alternative, falsifiable hypotheses about placebo effects
```

## Expected Behaviors

### Must Include
- [ ] Identifies the unfalsifiability problem explicitly
- [ ] Names or describes the No True Scotsman fallacy
- [ ] Explains why "belief" as escape clause prevents testing
- [ ] Does NOT validate the claim as scientifically sound
- [ ] Proposes genuinely falsifiable alternatives

### Should Include
- [ ] References Popper's demarcation criterion
- [ ] Distinguishes placebo effect from treatment effect
- [ ] Suggests blinding as solution to belief confound
- [ ] Notes circular reasoning in the hypothesis
- [ ] Proposes measurable belief operationalization

### Should Not Include
- [ ] Accepting the hypothesis as valid science
- [ ] Failing to identify the logical fallacy
- [ ] Proposing tests that still allow belief escape clause
- [ ] Confusing unfalsifiable with "difficult to test"

## Evaluation Criteria

### Research Quality
- Accurate understanding of scientific method
- Correct identification of logical fallacies

### Reasoning Quality (Primary)
- Recognition of unfalsifiability
- Clear logical analysis
- Creative but rigorous alternatives

### Output Structure
- Addresses all 4 sub-questions
- Clear structure for each response

## Passing Threshold
- Overall Score: ≥ 80/100
- Reasoning Quality: ≥ 85/100

## Rubric Weights
- Research Quality: 20%
- Reasoning Quality: 55%
- Output Structure: 25%
