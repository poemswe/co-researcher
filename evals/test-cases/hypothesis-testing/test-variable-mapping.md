# Test Case: Variable Mapping and Confound Identification

## Metadata
- **Agent**: hypothesis-testing
- **Difficulty**: Hard
- **Focus**: Identifying and mapping all relevant variables

## Rubric Profile
- **Primary**: design-quality (60%)
- **Secondary**: analytical-quality (30%)
- **Tertiary**: output-structure (10%)
- **Timeout**: 900

## Task Prompt

```
I hypothesize that children who play video games have lower academic performance.

Map all the relevant variables I should consider in testing this hypothesis,
including potential confounds that could explain any observed relationship.
```

## Expected Behaviors

### Must Include
- [ ] Independent variable: Video game playing (operationalized)
- [ ] Dependent variable: Academic performance (operationalized)
- [ ] At least 5 potential confounding variables
- [ ] Mediating variables (if applicable)
- [ ] Moderating variables (if applicable)

### Should Include
- [ ] Operationalization for each variable
- [ ] Direction of potential confounding
- [ ] Strategies to control confounds
- [ ] Acknowledgment of reverse causation possibility
- [ ] Distinction between correlation and causation

### Confounds to Consider
- Socioeconomic status
- Parental involvement
- Time spent on homework
- Sleep quality
- Social activities
- Type of games played
- Existing academic ability
- Age/developmental stage

### Should Not Include
- [ ] Missing obvious confounds
- [ ] Assuming causation from hypothesis
- [ ] Ignoring reverse causation
- [ ] Failing to operationalize variables

## Evaluation Criteria

### Reasoning Quality (Primary)
- Alternative Explanations: Are confounds identified?
- Logical Coherence: Is variable mapping logical?

### Research Quality
- Comprehensiveness: Are key variables covered?
- Accuracy: Are variable types correct?

### Output Structure
- Variable table with types
- Confound enumeration
- Mitigation strategies

## Passing Threshold
- Overall Score: ≥ 70/100
- Must identify at least 5 confounds
