# Test Case: Manuscript Critique (Peer Reviewer)

## Metadata
- **Agent**: peer-reviewer
- **Difficulty**: Medium
- **Area**: Methodological Rigor

## Rubric Profile
- **Primary**: analytical-quality (50%)
- **Secondary**: research-quality (30%)
- **Tertiary**: output-structure (20%)

## Task Prompt

```
Please peer review the following abstract and methodology summary:

**Title**: "The Impact of Morning Coffee on Long-Term Cognitive Decline"
**Abstract**: We investigate the relationship between daily coffee consumption and cognitive health over 50 years. We find that participants who drank 3+ cups of coffee showed 80% less cognitive decline.
**Methodology**: We surveyed 25 retired professors from our local university department across two weekends. Participants self-reported their current coffee habits and their perceived memory strength from 50 years ago. No control group was used as the effect was considered obvious.
```

## Expected Behaviors

### Must Include
- [ ] Identify Selection Bias: Note that 25 professors from one university is not a representative sample.
- [ ] Identify Recall Bias: Note that self-reporting memory from 50 years ago is highly unreliable.
- [ ] Identify Lack of Control: Highlight that the "obvious" effect does not justify skipping a control group.
- [ ] Assign low scores for Methodology and Rigor.

### Should Include
- [ ] Critique of the 80% effect size as likely exaggerated or confounded
- [ ] Recommendation for a prospective longitudinal study instead of retrospective survey
- [ ] Suggestion to include a diverse population
- [ ] Mention of survivor bias (retired professors)

### Should Not Include
- [ ] Accepting the findings as valid
- [ ] Ignoring the recall bias
- [ ] Validating the "obvious effect" reasoning
- [ ] Professionalism lapses

## Evaluation Criteria

### Reasoning Quality (Primary)
- Methodological Critique: Identifying bias and rigor issues
- Logical Coherence: Strength of the critique

### Research Quality
- Accuracy: Correct use of methodological terms

### Output Structure
- Professional tone and academic format
- Clear breakdown of review points

## Passing Threshold
- Overall Score: ≥ 70/100

## Rubric Weights
- Research Quality: 30%
- Reasoning Quality: 50%
- Output Structure: 20%
