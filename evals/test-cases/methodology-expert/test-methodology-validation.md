# Test Case: Methodology Validation & Design Critique

## Metadata
- **Agent**: methodology-expert
- **Difficulty**: Medium
- **Focus**: Evaluating whether a proposed research design fits the research question and identifying design flaws

## Rubric Profile
- **Primary**: analytical-quality (70%)
- **Secondary**: design-quality (30%)
- **Timeout**: 900

## Task Prompt

```
Here's a research question I'm planning to investigate:
"What personality traits predict success in remote work environments?"

My proposed design:
- Distribute a validated personality assessment (Big Five) to 500 remote workers
- Measure their performance with a single question: "Rate your job performance 1-10"
- Use linear regression to identify which Big Five traits predict performance
- Survey will take 30 minutes and we'll have 3 months to recruit

Is this methodology sound? What are the problems?
```

## Expected Behaviors

### Must Include
- [ ] Identify that the question is correlational/predictive (appropriate for quantitative)
- [ ] Identify at least 2 major methodology problems
- [ ] Explain why each problem is problematic for the research question
- [ ] Propose specific improvements

### Should Include
- [ ] Issue #1: Single-item performance measure (low validity, unreliable)
- [ ] Issue #2: Unmeasured confounds (tenure, team support, technical skills)
- [ ] Issue #3: Self-report bias (both personality and performance)
- [ ] Issue #4: Sample composition unclear (all remote? all companies?)
- [ ] Issue #5: Temporal ordering unclear (cross-sectional can't establish prediction)
- [ ] Suggestions for improvement (multi-item performance scale, control variables, longitudinal)
- [ ] Discussion of statistical power (N=500 reasonable, but depends on effect size)

### Should Not Include
- [ ] Endorsement of the design as-is
- [ ] Missing the validity threats
- [ ] Suggesting qualitative methods when quantitative is appropriate
- [ ] Vague critique (e.g., "it has problems" without specifics)

## Evaluation Criteria

### Analytical Quality (Primary)
- **Flaw Identification**: Are major design issues found and clearly stated?
- **Problem Depth**: Is the impact of each flaw explained?
- **Rigor**: Are validity concepts applied correctly?
- **Alternative Solutions**: Are specific improvements proposed?

### Design Quality (Secondary)
- **Methodology Coherence**: Does proposed fix maintain methodological soundness?
- **Feasibility**: Are suggestions realistic?

### Critical Problems to Identify
1. **Measurement Validity**: Single-item performance measure is unreliable and invalid
   - Should use multi-item scale or objective performance metrics

2. **Confounding Variables**: Multiple plausible alternative explanations
   - Need to measure and control: Years of remote work experience, technical proficiency, manager support, team size, job role

3. **Self-Report Bias**: Both predictors and outcome are self-reported
   - Should include objective performance measures if possible

4. **Sample Specification**: "Remote workers" is too broad
   - Need to specify: Same company? Different companies? Job roles?

5. **Cross-sectional Limitation**: Cannot claim "predicts" with cross-sectional data
   - Should acknowledge as correlational or collect longitudinal data

### Optimal Design Fix
- Use validated multi-item job performance scale (e.g., task performance, contextual performance)
- OR use objective metrics (productivity data, error rates, manager ratings on standardized scale)
- Measure and control confounds (experience, skills, resources)
- Specify sample clearly (e.g., all software engineers in tech companies)
- Consider longitudinal design for true prediction
- Assess measurement model before regression

## Passing Threshold
- Overall Score: ≥ 70/100
- Analytical Quality: ≥ 75/100
- Must identify 2+ major validity threats
- Must explain why each is problematic
- Must propose specific improvements
