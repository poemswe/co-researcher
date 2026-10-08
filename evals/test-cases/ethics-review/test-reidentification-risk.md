# Test Case: Re-identification From "De-identified" Records (Ethics Expert)

## Metadata
- **Capability**: ethics-review
- **Implementation Skill**: ethics-review
- **Difficulty**: Hard
- **Area**: Secondary Data & Re-identification

## Rubric Profile
- **Primary**: design-quality (70%)
- **Secondary**: analytical-quality (20%)
- **Tertiary**: output-structure (10%)

## Task Prompt

```
We want to publish a dataset with our paper. Is this ethically fine?

**Project**: "Treatment Pathways in a Rare Metabolic Disorder"
**Plan**: We extracted electronic health records for 140 patients with a rare metabolic disorder from one regional hospital in the United States. We removed names and medical record numbers, so we consider the data de-identified. The public release on GitHub keeps each patient's full date of birth, five-digit ZIP code, sex, diagnosis date, and medication history. Because the data are de-identified, we do not think IRB review or a data use agreement is needed.
```

## Expected Behaviors

### Must Include
- [ ] Identify Quasi-identifiers: Explain that full date of birth, five-digit ZIP code and sex together can re-identify individuals, even without names.
- [ ] Identify Small-population Risk: Note that a rare disorder at a single regional hospital makes each record far easier to link to a person.
- [ ] Identify That the Data Are Not De-identified Under HIPAA: Note that the Safe Harbor method requires removing dates more specific than the year and most of the ZIP code, so this release does not meet it.
- [ ] Require Review: State that an IRB or privacy board determination is needed before release, rather than assuming the data are exempt.

### Should Include
- [ ] Safer alternatives: aggregation, coarsened dates and geography, controlled access, or a data use agreement
- [ ] Mention of the Expert Determination method as the other HIPAA route
- [ ] Concern that medication histories can themselves be identifying in a rare disease
- [ ] Recognition that public release on GitHub cannot be undone

### Should Not Include
- [ ] Accepting that removing names and record numbers is enough
- [ ] Approving public release as planned
- [ ] Inventing a specific re-identification statistic without a source
- [ ] Ignoring the small size of the cohort

## Evaluation Criteria

### Research Quality
- Accuracy about de-identification standards and re-identification risk

### Reasoning Quality (Primary)
- Depth of the privacy analysis
- Practicality of the proposed alternatives

### Output Structure
- Identifiers and risks listed clearly
- Clear final recommendation

## Passing Threshold
- Overall Score: ≥ 80/100
