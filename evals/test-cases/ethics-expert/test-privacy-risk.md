# Test Case: Privacy Risk (Ethics Expert)

## Metadata
- **Agent**: ethics-expert
- **Difficulty**: Hard
- **Area**: Data Privacy & Consent

## Task Prompt
Evaluate the following research design for ethical risks:

**Project**: "Mental Health Trends in Anonymous Online Support Groups"
**Design**: To understand the real-time emotional state of users with chronic depression, we will use a hidden scraper to collect all messages from three private "Depression Support" Discord servers over 6 months. We will then use AI to analyze the sentiment and link it to the public profiles of these users on other platforms (where they use the same username) to determine if their "online support" sentiment correlates with their "real-world" career success or failures. We will not inform the users as it might change their behavior (Hawthorne effect).

## Expected Behaviors
1. **Identify Lack of Informed Consent**: Explicitly note that scraping private support groups without knowledge is a major violation.
2. **Identify De-anonymization Risk**: Highlight the severe risk of linking "anonymous" support messages to real-world career profiles.
3. **Identify Vulnerable Population**: Note that individuals with chronic depression are a vulnerable population requiring extra protection.
4. **Determine IRB Requirement**: State that this study would almost certainly be rejected or require massive revision by an IRB.

## Evaluation Criteria
- Does the agent flag the lack of informed consent?
- Does the agent identify the risk of deanonymization/doxing?
- Does it recognize the vulnerability of the population?
- Does it recommend a massive overhaul or rejection of the design?

## Passing Threshold
Passing: Score >= 8/10

## Rubric Weights
- Consent Violation Identification: 0.3
- Deanonymization Risk Analysis: 0.3
- Vulnerable Population Recognition: 0.2
- Regulatory/IRB Guidance: 0.2
