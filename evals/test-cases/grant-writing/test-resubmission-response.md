# Test Case: Resubmission Introduction (Grant Writer)

## Metadata
- **Capability**: grant-proposal
- **Implementation Skill**: grant-writing
- **Difficulty**: Hard
- **Area**: Resubmission Strategy

## Rubric Profile
- **Primary**: design-quality (50%)
- **Secondary**: analytical-quality (30%)
- **Tertiary**: output-structure (20%)

## Task Prompt

```
My NIH proposal was not funded. Reviewers wrote:
1. "The sample size of 40 is too small to detect the proposed effect."
2. "The applicant has no experience with the proposed imaging method."
3. "Aim 3 is overly ambitious for the timeline."
4. "The reviewer was unclear why the control condition was chosen."

I think reviewer 2 is wrong because my co-investigator is an expert. Help me write the one-page Introduction to the resubmission.
```

## Expected Behaviors

### Must Include
- [ ] Address Every Critique: Respond to all four points, one by one.
- [ ] Concede Valid Points With Changes: For the sample size and timeline critiques, describe concrete revisions such as a power analysis or a narrowed Aim 3.
- [ ] Handle Critique 2 Without Arguing: Address the expertise concern by documenting the co-investigator's role and experience, rather than saying the reviewer was wrong.
- [ ] Respect the Format: Keep the response to roughly one page and tell the user to mark changes in the revised application.

### Should Include
- [ ] A brief opening that thanks reviewers and summarizes the main changes
- [ ] Clarification of the control condition's rationale for critique 4
- [ ] Advice to check the current NIH resubmission instructions for exact limits

### Should Not Include
- [ ] A defensive or dismissive tone toward reviewers
- [ ] Ignoring any of the four critiques
- [ ] Inventing power-analysis numbers or results the user did not give

## Evaluation Criteria

### Design Quality (Primary)
- Whether each response would persuade the same review panel

### Analytical Quality
- Judgment about which critiques to concede

### Output Structure
- A usable one-page draft

## Passing Threshold
- Overall Score: >= 70/100
