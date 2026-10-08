# Test Case: Specific Aims Revision (Grant Writer)

## Metadata
- **Capability**: grant-proposal
- **Implementation Skill**: grant-writing
- **Difficulty**: Medium
- **Area**: Specific Aims

## Rubric Profile
- **Primary**: design-quality (50%)
- **Secondary**: analytical-quality (30%)
- **Tertiary**: output-structure (20%)

## Task Prompt

```
Here is my draft Specific Aims for an NIH R01. Critique it and rewrite it.

"Sleep problems are common in older adults. We will explore the relationship between sleep and memory.
Aim 1: Recruit 300 adults aged 65 and over and collect sleep data with wrist actigraphy.
Aim 2: Using the sleep data from Aim 1, build a model of which sleep features matter.
Aim 3: If Aim 2 finds important features, design an intervention targeting them."
```

## Expected Behaviors

### Must Include
- [ ] Identify Dependent Aims: Point out that Aim 2 depends on Aim 1 and Aim 3 depends on Aim 2's result, so one failure collapses the project.
- [ ] Identify the Missing Hypothesis: Note that "explore the relationship" gives no testable hypothesis.
- [ ] Identify Missing Outcomes: Note that memory is never operationalized and no measurable outcome is named.
- [ ] Rewrite With Hypothesis-driven Aims: Provide revised aims that each test a stated hypothesis and could succeed independently.

### Should Include
- [ ] A gap statement that says what is unknown and why it matters
- [ ] Alternative approaches if a key aim does not work
- [ ] Expected outcomes and impact for each aim
- [ ] Recognition that Aim 1 describes data collection rather than a scientific aim

### Should Not Include
- [ ] Keeping the conditional structure of Aim 3
- [ ] Praising the draft without substantive critique
- [ ] Inventing preliminary data the user did not provide

## Evaluation Criteria

### Design Quality (Primary)
- Independence and testability of the revised aims

### Analytical Quality
- Precision of the critique

### Output Structure
- Critique followed by a usable rewritten page

## Passing Threshold
- Overall Score: >= 70/100
