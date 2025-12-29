# Test Case: Manuscript Critique (Peer Reviewer)

## Metadata
- **Agent**: peer-reviewer
- **Difficulty**: Medium
- **Area**: Methodological Rigor

## Task Prompt
Please peer review the following abstract and methodology summary:

**Title**: "The Impact of Morning Coffee on Long-Term Cognitive Decline"
**Abstract**: We investigate the relationship between daily coffee consumption and cognitive health over 50 years. We find that participants who drank 3+ cups of coffee showed 80% less cognitive decline.
**Methodology**: We surveyed 25 retired professors from our local university department across two weekends. Participants self-reported their current coffee habits and their perceived memory strength from 50 years ago. No control group was used as the effect was considered obvious.

## Expected Behaviors
1. **Identify Selection Bias**: Note that 25 professors from one university is not a representative sample.
2. **Identify Recall Bias**: Note that self-reporting memory from 50 years ago is highly unreliable.
3. **Identify Lack of Control**: Highlight that the "obvious" effect does not justify skipping a control group.
4. **Scoring**: Should assign low scores for Methodology and Rigor (1/5 or 2/5).

## Evaluation Criteria
- Did the agent identify the recall bias?
- Did the agent identify the selection bias?
- Did the agent criticize the lack of a control group?
- Is the tone professional and academic?

## Passing Threshold
Passing: Score >= 7/10

## Rubric Weights
- Recall Bias Identification: 0.3
- Selection Bias Identification: 0.3
- Control Group Critique: 0.2
- Professional Tone: 0.2
