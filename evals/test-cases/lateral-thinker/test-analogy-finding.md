# Test Case: Cross-Domain Analogy Finding

## Metadata
- **Agent**: lateral-thinker
- **Difficulty**: Hard
- **Focus**: Finding productive analogies from other domains

## Task Prompt

```
We're trying to reduce customer churn for a subscription service.
We've tried the obvious approaches (discounts, loyalty programs, better onboarding)
but churn remains high.

Find analogies from completely different domains that might give us fresh approaches
to think about customer retention.
```

## Expected Behaviors

### Must Include
- [ ] At least 3 cross-domain analogies
- [ ] Clear mapping from source to target domain
- [ ] Actionable insights from each analogy
- [ ] Acknowledgment of where analogies break down

### Productive Analogy Examples
- Medicine: Prevention vs treatment, immune system
- Ecology: Ecosystem balance, keystone species
- Relationships: Marriage counseling, attachment styles
- Architecture: Foundations, load-bearing elements
- Biology: Symbiosis, host-parasite dynamics
- Physics: Friction, inertia, momentum

### Should Include
- [ ] Abstraction of core problem structure
- [ ] Novel insights not from obvious sources
- [ ] Practical applications suggested
- [ ] Caveats about analogical limits
- [ ] Multiple levels of abstraction

### Should Not Include
- [ ] Surface-level analogies only
- [ ] Analogies from same domain (e.g., other SaaS)
- [ ] Forced analogies that don't map well
- [ ] Missing the insight transfer step

## Evaluation Criteria

### Reasoning Quality (Primary)
- Alternative Explanations: Are novel perspectives offered?
- Logical Coherence: Do analogies map sensibly?

### Research Quality
- Comprehensiveness: Multiple domains explored?

### Output Structure
- Clear analogy presentation
- Mapping explained
- Actionable takeaways

## Passing Threshold
- Overall Score: ≥ 70/100
- Must provide at least 2 genuinely novel analogies

## Rubric Weights
- Research Quality: 25%
- Reasoning Quality: 50%
- Output Structure: 25%
