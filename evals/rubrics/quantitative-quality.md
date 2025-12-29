# Quantitative Quality Rubric

Evaluates statistical reasoning, method selection, and numerical analysis accuracy.

## Overview

This rubric assesses an agent's ability to select appropriate statistical methods, perform correct calculations, verify assumptions, and interpret results properly. Focus is on **quantitative correctness**, not literature review.

**Use for**: Statistical analysis, method selection, data interpretation, hypothesis testing, effect size calculation.

**Do NOT use for**: Qualitative analysis, logical argumentation, literature reviews.

## Dimensions

### 1. Method Selection (0-30 points)

Evaluates appropriateness of statistical test/method for the research question and data type.

| Score | Criteria |
|-------|----------|
| 28-30 | Perfect method selection; accounts for all data characteristics (distribution, scale, independence); justifies choice with references to assumptions; suggests alternatives if assumptions borderline |
| 22-27 | Appropriate method selected; considers most data characteristics; brief justification provided; minor oversights acceptable |
| 16-21 | Generally appropriate method but doesn't fully account for data characteristics; weak or missing justification; may overfit |
| 9-15 | Questionable method selection; ignores key data characteristics; no justification; serious assumption violations likely |
| 0-8 | Inappropriate method; fundamental misunderstanding of when to use certain tests; would lead to invalid conclusions |

**Scoring Guidance**:
- t-test: Check for normality requirement, independence, equal variances (or Welch's correction)
- ANOVA: Check for normality, homogeneity of variance, independence
- Regression: Check for linearity, independence, homoscedasticity, normality of residuals
- Non-parametric: Appropriate when parametric assumptions violated
- Sample size: Method appropriate for n (e.g., not chi-square with expected counts <5)

### 2. Calculation Accuracy (0-30 points)

Evaluates correctness of mathematical operations and statistical computations.

| Score | Criteria |
|-------|----------|
| 28-30 | All calculations correct; formulas properly applied; degrees of freedom correct; p-values accurate; effect sizes computed correctly |
| 22-27 | Calculations mostly correct; minor arithmetic errors acceptable; formulas generally correct; minor rounding acceptable |
| 16-21 | Some calculation errors; occasional formula misapplication; degrees of freedom sometimes wrong; p-values approximately correct |
| 9-15 | Frequent calculation errors; wrong formulas used; degrees of freedom incorrect; p-values wrong |
| 0-8 | Serious calculation errors; fundamental misunderstanding of formulas; computations nonsensical |

**Scoring Guidance**:
- Verify key calculations (test statistic, p-value, confidence intervals)
- Check degrees of freedom (critical for determining significance)
- Verify effect size calculations (Cohen's d, η², R², etc.)
- Allow minor rounding differences (0.051 vs 0.05 acceptable)
- Penalize formula misapplication heavily (e.g., using wrong denominator)

### 3. Assumption Verification (0-20 points)

Evaluates checking of statistical assumptions and consideration of violations.

| Score | Criteria |
|-------|----------|
| 19-20 | All relevant assumptions checked; appropriate tests used (Shapiro-Wilk, Levene's, etc.); violations addressed with alternatives or transformations; limitations clearly stated |
| 15-18 | Most assumptions checked; violations noted; some mitigation attempted; limitations mentioned |
| 11-14 | Some assumptions checked but key ones missed; violations noted but not addressed; limited discussion of limitations |
| 6-10 | Few assumptions checked; violations ignored or unnoticed; no discussion of limitations |
| 0-5 | No assumption checking; proceeds as if all assumptions met; ignores obvious violations |

**Scoring Guidance**:
- Normality: Shapiro-Wilk, Q-Q plot, or mention of CLT with large n
- Homogeneity of variance: Levene's test or visual inspection
- Independence: Study design discussion
- Linearity (regression): Residual plots
- Outliers: Identification and impact assessment
- Multicollinearity (regression): VIF or correlation matrix

### 4. Interpretation Validity (0-20 points)

Evaluates correctness of statistical interpretation and practical significance.

| Score | Criteria |
|-------|----------|
| 19-20 | Distinguishes statistical from practical significance; correct interpretation of p-values; effect sizes reported and interpreted; confidence intervals properly understood; causation vs correlation clear |
| 15-18 | Generally correct interpretation; effect sizes mentioned; p-values not over-interpreted; minor conceptual errors acceptable |
| 11-14 | Interpretation mostly correct but some conflation of statistical/practical significance; effect sizes missing or misinterpreted; p-value misunderstandings |
| 6-10 | Frequent interpretation errors; confuses significance with importance; effect sizes ignored; causation implied from correlation |
| 0-5 | Fundamental interpretation errors; p-value misunderstood; effect size not reported; causation falsely claimed |

**Scoring Guidance**:
- p < 0.05 doesn't mean "important" or "large effect"
- Effect size should determine practical significance
- Confidence intervals should be interpreted, not just reported
- Correlation ≠ causation (unless experimental design supports)
- Non-significance ≠ "no effect" (could be underpowered)
- Multiple comparisons should be addressed

## Overall Quantitative Quality Score

| Total Score | Rating | Interpretation |
|-------------|--------|----------------|
| 90-100 | Excellent | Publishable statistical analysis |
| 75-89 | Good | Solid analysis with minor issues |
| 60-74 | Acceptable | Correct approach but execution flaws |
| 40-59 | Below Standard | Significant statistical errors |
| 0-39 | Unacceptable | Fundamentally flawed analysis |

## Quick Evaluation Checklist

- [ ] Is the statistical test appropriate for the data type?
- [ ] Are calculations accurate?
- [ ] Are assumptions checked and violations addressed?
- [ ] Are effect sizes reported and interpreted?
- [ ] Is statistical significance distinguished from practical significance?
- [ ] Are p-values correctly interpreted?
- [ ] Is causation vs correlation properly handled?
- [ ] Are confidence intervals reported and interpreted?

## Examples

### High Score (94/100)
*Task: Which test for comparing blood pressure between 3 diet groups?*

**Agent Output**:
- **Method (29/30)**: Recommends one-way ANOVA; notes need for normality, homogeneity of variance, independence; suggests Kruskal-Wallis if assumptions violated
- **Calculation (29/30)**: Shows correct F-statistic formula,correct df (2, 57), p-value calculation accurate
- **Assumptions (19/20)**: Mentions Shapiro-Wilk for normality, Levene's for variance, discusses random assignment for independence
- **Interpretation (17/20)**: Reports η² = 0.15 (medium effect); notes statistical significance (p=0.03) but small practical difference (3 mmHg); doesn't claim causation

### Low Score (38/100)
*Same task*

**Agent Output**:
- **Method (12/30)**: Suggests multiple t-tests without mentioning multiple comparison problem
- **Calculation (8/30)**: Uses wrong formula for pooled variance; df calculations incorrect
- **Assumptions (5/20)**: No mention of normality or variance homogeneity
- **Interpretation (13/20)**: Claims p=0.04 means "strong effect"; no effect size; implies causation without justification

## Special Cases

### Simpson's Paradox Validation
- **Required**: Must verify Case Mix disparity before diagnosing paradox
- **Method (0 pts)**: If claims paradox without checking group distributions
- **Interpretation (+10 pts)**: If correctly identifies when reversal is impossible due to equal distributions

### Power Analysis
- **Required**: Sample size justification or post-hoc power for null results
- **Method (+5 pts)**: Provides power calculation with justification
- **Method (0 pts)**: Proceeds with underpowered study without acknowledgment

### Bayesian Analysis
- **Method**: Judge prior selection and justification
- **Interpretation**: Evaluate credible interval interpretation vs frequentist CI
