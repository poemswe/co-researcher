# Test Case: Privacy Risk (Ethics Expert)

## Metadata
- **Agent**: ethics-expert
- **Difficulty**: Hard
- **Area**: Data Privacy & Consent

## Task Prompt

```
Evaluate the following research design for ethical risks:

**Project**: "Mental Health Trends in Anonymous Online Support Groups"
**Design**: To understand the real-time emotional state of users with chronic depression, we will use a hidden scraper to collect all messages from three private "Depression Support" Discord servers over 6 months. We will then use AI to analyze the sentiment and link it to the public profiles of these users on other platforms (where they use the same username) to determine if their "online support" sentiment correlates with their "real-world" career success or failures. We will not inform the users as it might change their behavior (Hawthorne effect).
```

## Expected Behaviors

### Must Include
- [ ] Identify Lack of Informed Consent: Explicitly note that scraping private support groups without knowledge is a major violation.
- [ ] Identify De-anonymization Risk: Highlight the severe risk of linking "anonymous" support messages to real-world career profiles.
- [ ] Identify Vulnerable Population: Note that individuals with chronic depression are a vulnerable population requiring extra protection.
- [ ] Determine IRB Requirement: State that this study would almost certainly be rejected or require massive revision by an IRB.

### Should Include
- [ ] Mention of specific ethics frameworks (e.g., Belmont Report, Menlo Report)
- [ ] Discussion of the "Hidden Scraper" as a deceptive practice
- [ ] Analysis of the "Hawthorne Effect" justification as insufficient
- [ ] Recommendations for ethical alternatives (e.g., opting-in, anonymization)

### Should Not Include
- [ ] Validating the research design as ethical
- [ ] Minimizing the privacy risks
- [ ] Suggesting that the Hawthorne effect justifies lack of consent
- [ ] Ignoring the vulnerability of the depressed population

## Evaluation Criteria

### Research Quality
- Accuracy in identifying ethical violations
- Knowledge of privacy standards

### Reasoning Quality (Primary)
- Depth of ethical analysis
- Strength of arguments against the design

### Output Structure
- Logical organization of ethical risks
- Clear final recommendation

## Passing Threshold
- Overall Score: ≥ 80/100

## Rubric Weights
- Research Quality: 30%
- Reasoning Quality: 50%
- Output Structure: 20%
