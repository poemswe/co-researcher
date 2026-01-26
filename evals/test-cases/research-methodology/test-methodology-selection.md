# Test Case: Methodology Selection & Design Fit

## Metadata
- **Agent**: research-methodology
- **Difficulty**: Medium
- **Focus**: Matching research questions to optimal methodology and providing design guidance

## Rubric Profile
- **Primary**: design-quality (70%)
- **Secondary**: analytical-quality (30%)
- **Timeout**: 900

## Task Prompt

```
I want to understand how remote work affects employee well-being.
I have a small team of 15 people, and I want to capture the lived experience
of working from home—what they enjoy, what challenges them, how it's changed
their work-life balance.

What methodology should I use? I want something practical but rigorous.
```

## Expected Behaviors

### Must Include
- [ ] Question classification (Exploratory, experiential, exploratory)
- [ ] At least 2 candidate methodologies with clear reasoning
- [ ] Recommended approach with justification
- [ ] Specific design specification (sampling, data collection, analysis)
- [ ] Quality standards relevant to chosen methodology

### Should Include
- [ ] Discussion of why qualitative approaches fit this question
- [ ] Consideration of sample size (N=15) and adequacy
- [ ] Data collection methods (interviews, focus groups, observations)
- [ ] Analysis approach and quality criteria (saturation, triangulation)
- [ ] Timeline/feasibility assessment
- [ ] Explicit methodology limitations

### Should Not Include
- [ ] Purely quantitative recommendation for exploratory question
- [ ] Generic "mixed methods" without clear rationale
- [ ] Recommendations ignoring the small team size
- [ ] Missing discussion of rigor/quality criteria
- [ ] Unfeasible designs given constraints

## Evaluation Criteria

### Design Quality (Primary)
- **Methodology Fit**: Does recommended approach match research question?
- **Operationalization**: Are methods clearly specified and actionable?
- **Feasibility**: Is design realistic given 15-person constraint?
- **Rigor Standards**: Are quality criteria discipline-appropriate?

### Analytical Quality (Secondary)
- **Reasoning**: Is the logic transparent for methodology selection?
- **Trade-offs**: Are pros/cons of alternatives discussed?
- **Constraints**: Are limitations and challenges addressed?

### Expected Methodologies
**Primary recommendation**: Phenomenology or Thematic Analysis
**Alternatives**: Case Study, Narrative Analysis

**Why**:
- Small N (15) not suitable for statistical power
- "Lived experience" clearly indicates phenomenological focus
- Exploratory nature suggests qualitative approach
- Team size manageable for intensive interviews

## Passing Threshold
- Overall Score: ≥ 70/100
- Design Quality: ≥ 75/100
- Must recommend qualitative methodology
- Must specify 3+ design elements (sampling, data collection, analysis)
