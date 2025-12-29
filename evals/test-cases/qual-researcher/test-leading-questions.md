# Test Case: Leading Questions Detection

## Metadata
- **Agent**: qual-researcher
- **Difficulty**: Hard
- **Focus**: Methodological bias identification in interview protocols

## Task Prompt

```
Review this interview protocol designed to study "Public Attitudes Toward Climate Change":

**Interview Questions:**
1. "Don't you agree that climate change is the most pressing issue of our time?"
2. "How worried are you about the future of your children due to environmental collapse?"
3. "What sacrifices are you personally willing to make to fight climate change?"
4. "Many scientists say we have less than 10 years to act. How does that make you feel?"
5. "Who do you blame for the current environmental crisis?"

Evaluate the methodological quality of this protocol and provide recommendations for improvement.
```

## Expected Behaviors

### Must Include
- [ ] Identifies leading question bias in Q1 ("Don't you agree...")
- [ ] Notes presupposition of concern in Q2 ("environmental collapse")
- [ ] Flags loaded language throughout
- [ ] Provides neutral reformulations of at least 3 questions
- [ ] Critiques lack of opposing viewpoint exploration

### Should Include
- [ ] Notes acquiescence bias risk
- [ ] Identifies false urgency framing in Q4
- [ ] Suggests adding neutral or skeptical perspectives
- [ ] Recommends balanced question ordering
- [ ] Mentions interviewer effect considerations

### Should Not Include
- [ ] Approving the protocol without critique
- [ ] Only surface-level criticism
- [ ] Failing to provide constructive alternatives
- [ ] Missing the leading question patterns

## Evaluation Criteria

### Research Quality
- Understanding of qualitative methodology standards
- Recognition of bias types

### Reasoning Quality (Primary)
- Systematic identification of methodological flaws
- Quality of suggested improvements

### Output Structure
- Question-by-question analysis
- Clear improvement recommendations

## Passing Threshold
- Overall Score: ≥ 80/100
- Reasoning Quality: ≥ 80/100

## Rubric Weights
- Research Quality: 30%
- Reasoning Quality: 45%
- Output Structure: 25%
