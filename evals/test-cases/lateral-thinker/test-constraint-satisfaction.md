# Test Case: Constraint Satisfaction Puzzle

## Metadata
- **Agent**: lateral-thinker
- **Difficulty**: Hard
- **Focus**: Creative problem-solving with hidden constraints

## Rubric Profile
- **Primary**: analytical-quality (70%)
- **Secondary**: output-structure (30%)

## Task Prompt

```
Classic Logic Puzzle:

You have 8 balls that look identical. One ball is slightly heavier than the others.

Using a balance scale with only TWO weighings, identify which ball is the heavy one.

Provide:
1. Your complete algorithm
2. Show how it works for ALL possible cases
3. Prove that 2 weighings are sufficient
```

## Expected Behaviors

### Must Include
- [ ] Correct algorithm: divide into groups of 3, 3, and 2
- [ ] First weighing: compare two groups of 3
- [ ] Handles all 3 first-weighing outcomes (left heavy, right heavy, balanced)
- [ ] Second weighing correctly identifies among remaining candidates
- [ ] Proves solution works in exactly 2 weighings

### Should Include
- [ ] Explains information-theoretic reasoning (3^2 = 9 > 8)
- [ ] Shows systematic case analysis
- [ ] Notes this is optimal (can't do with 1 weighing)
- [ ] Clear step-by-step walkthrough

### Should Not Include
- [ ] Algorithms requiring more than 2 weighings
- [ ] Missing edge cases
- [ ] Incorrect logic that fails for some balls
- [ ] Giving up or claiming impossible

## Evaluation Criteria

### Research Quality
- N/A (pure logic puzzle)

### Reasoning Quality (Primary)
- Correct algorithm
- Complete case coverage
- Sound logical proof

### Output Structure
- Clear algorithm presentation
- Systematic case enumeration
- Easy to follow logic

## Passing Threshold
- Overall Score: ≥ 80/100
- Reasoning Quality: ≥ 90/100 (correctness required)
