# Analytical Quality Rubric

Evaluates logical reasoning, argument analysis, and critical thinking without requiring external research.

## Overview

This rubric assesses an agent's ability to analyze arguments, identify flaws, and construct counterarguments using **logical reasoning alone**. It does NOT penalize for lack of external citations when the task is to analyze provided content.

**Use for**: Critical analysis of arguments, fallacy detection, bias identification, methodological critique of described studies.

**Do NOT use for**: Literature reviews, research requiring external sources, tasks explicitly asking for citations.

## Dimensions

### 1. Logical Rigor (0-40 points)

Evaluates the validity and soundness of reasoning chains.

| Score | Criteria |
|-------|----------|
| 37-40 | Flawless logical reasoning; all inferences valid; no logical leaps; conclusions necessarily follow from premises; formal logic correctly applied when relevant |
| 30-36 | Strong reasoning with minor gaps; mostly valid inferences; conclusions well-supported; occasional minor logical imprecision acceptable |
| 23-29 | Generally sound reasoning but some weak inferences; conclusions adequately supported; some logical connections unclear or assumed |
| 15-22 | Noticeable logical errors; weak inferences; conclusions sometimes unsupported; confusion between correlation and causation or similar |
| 0-14 | Serious logical errors; invalid reasoning chains; circular logic; conclusions don't follow from premises |

**Scoring Guidance**:
- Check if conclusions logically follow from evidence presented
- Verify no logical fallacies in the agent's own reasoning
- Assess clarity of reasoning chains (A→B→C should be explicit)
- Look for unwarranted assumptions or logical leaps

### 2. Fallacy/Flaw Detection (0-30 points)

Evaluates ability to identify logical fallacies, biases, or methodological flaws in analyzed content.

| Score | Criteria |
|-------|----------|
| 28-30 | Identifies all major fallacies/flaws; correctly classifies each; provides clear explanations; no false positives |
| 22-27 | Identifies most major fallacies/flaws; classifications mostly correct; explanations adequate; minimal false positives |
| 16-21 | Identifies some fallacies/flaws but misses key issues; some misclassifications; explanations sometimes unclear |
| 9-15 | Misses major fallacies/flaws; frequent misclassifications; weak explanations; significant false positives |
| 0-8 | Fails to identify obvious fallacies/flaws; serious misidentifications; no understanding of fallacy types |

**Scoring Guidance**:
- For critical-analyzer: Check against common fallacies (ad hominem, straw man, false dichotomy, post hoc, etc.)
- For hypothesis-explorer: Check identification of confounds, unfalsifiable claims, circular definitions
- For quant-analyst: Check identification of statistical errors, p-hacking, Simpson's Paradox, etc.
- Penalize false positives (labeling valid reasoning as fallacious)

### 3. Counterargument Strength (0-20 points)

Evaluates quality and diversity of alternative explanations or opposing viewpoints.

| Score | Criteria |
|-------|----------|
| 19-20 | Multiple strong counterarguments; diverse perspectives; each plausible and well-reasoned; addresses strongest form of opponent's position |
| 15-18 | Good counterarguments; reasonable diversity; mostly plausible; adequate engagement with opposing views |
| 11-14 | Some counterarguments but limited diversity; plausibility varies; may engage with weak versions of opposing views |
| 6-10 | Weak counterarguments; little diversity; often implausible; strawman versions of opposing views |
| 0-5 | No meaningful counterarguments; fails to engage with opposing perspectives |

**Scoring Guidance**:
- Check for Steel Man approach (strongest version of opposing view)
- Assess diversity of alternatives (not just 1-2 similar counterarguments)
- Verify counterarguments are plausible, not absurd
- Look for acknowledgment of valid points in opposing position

### 4. Assumption Analysis (0-10 points)

Evaluates identification of hidden premises, unspoken assumptions, and dependencies.

| Score | Criteria |
|-------|----------|
| 9-10 | Identifies all major hidden assumptions; explains their role in argument; assesses their validity; notes dependencies |
| 7-8 | Identifies most major assumptions; explains their importance; some assessment of validity |
| 5-6 | Identifies some assumptions but misses key ones; explanations superficial |
| 3-4 | Misses obvious assumptions; minimal explanation of those identified |
| 0-2 | Fails to identify assumptions or confuses assumptions with explicit premises |

**Scoring Guidance**:
- Look for identification of implicit premises needed to make argument work
- Check if agent explains why assumptions matter
- Assess whether agent questions validity of assumptions
- Verify no confusion between explicit statements and underlying assumptions

## Overall Analytical Quality Score

| Total Score | Rating | Interpretation |
|-------------|--------|----------------|
| 90-100 | Excellent | PhD-level analytical reasoning |
| 75-89 | Good | Strong analysis with minor gaps |
| 60-74 | Acceptable | Adequate but room for improvement |
| 40-59 | Below Standard | Significant analytical weaknesses |
| 0-39 | Unacceptable | Fails to demonstrate analytical rigor |

## Quick Evaluation Checklist

- [ ] Are all reasoning chains logically valid?
- [ ] Are major fallacies/flaws correctly identified?
- [ ] Are fallacy classifications accurate?
- [ ] Are counterarguments strong and diverse?
- [ ] Are hidden assumptions surfaced?
- [ ] Is the agent's own reasoning free of fallacies?
- [ ] Does analysis address the strongest version of arguments?

## Examples

### High Score (95/100)
*Task: Analyze argument that "vaccines cause autism because autism diagnoses increased after vaccine schedules expanded"*

**Agent Output**:
- **Logical Rigor (40/40)**: Correctly identifies post hoc fallacy; notes correlation ≠ causation; explains multiple alternative explanations
- **Fallacy Detection (29/30)**: Identifies post hoc, hasty generalization, ignoring confounds; no false positives
- **Counterarguments (19/20)**: Offers diagnostic awareness hypothesis, genetic understanding improvements, broadened diagnostic criteria
- **Assumptions (7/10)**: Identifies assumption that temporal relationship implies causation; notes assumption that no other factors changed

### Low Score (35/100)
*Same task*

**Agent Output**:
- **Logical Rigor (10/40)**: Vague statement that "correlation doesn't prove causation" without explaining why
- **Fallacy Detection (12/30)**: Identifies post hoc but misses confounding; incorrectly labels argument as "ad hominem"
- **Counterarguments (8/20)**: Only offers "people are more aware now" without elaboration; no other alternatives
- **Assumptions (5/10)**: Doesn't identify the causation assumption; confuses explicit claims with hidden premises
