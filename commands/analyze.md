---
description: Critically analyze content, claims, or arguments with rigorous evaluation
argument-hint: [claim] | [url] | [topic-to-analyze]
---

# /analyze - Critical Analysis

{% if $ARGUMENTS %}
I'll conduct a rigorous critical analysis of: **$ARGUMENTS**
{% else %}
I'll conduct a rigorous critical analysis of content you provide.
{% endif %}

## What I'll evaluate:

### Evidence Quality
- Source credibility and authority
- Evidence type and strength
- Support for claims made

### Logical Validity
- Argument structure
- Logical fallacies
- Hidden assumptions

### Bias Detection
- Cognitive biases
- Research biases
- Conflicts of interest

### Methodology
- Research design appropriateness
- Internal/external validity
- Statistical rigor (if applicable)

### Alternative Explanations
- Competing hypotheses
- Confounding factors
- Simpler explanations

## What I need:

{% if not $ARGUMENTS %}
Provide one of:
- URL to content
- Text to analyze
- Paper/document reference
- Claim or argument
{% else %}
Ready to analyze. Provide the full content, URL, or additional context if needed.
{% endif %}

## Output:

You'll receive:
- Claim extraction and mapping
- Evidence assessment table
- List of logical issues
- Bias concerns
- Methodology critique
- Alternative explanations
- Overall strength rating
- Key concerns and recommendations

What would you like me to analyze?
