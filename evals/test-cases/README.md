# Test Cases & Rubrics Reference

Quick lookup guide for all 34 test cases, their specifications, and evaluation rubrics.

## Metadata Schema

Each test case declares two separate identifiers:

```markdown
- **Capability**: lateral-thinking
- **Implementation Skill**: research-methodology
```

`Capability` is the stable benchmark category used for scores and cross-model
comparisons. It must match the canonical form of the test-case directory name.
`Implementation Skill` names the skill that executes the case and may change
without rewriting benchmark history. The parser accepts the former `Agent`
field only for compatibility with external legacy cases.

---

## Critical-Analyzer (4 tests)

### 1. Bias Identification
- **Difficulty**: Hard
- **Focus**: Detecting research and cognitive biases
- **Rubric Profile**: Analytical Quality (75%), Output Structure (25%)
- **Task**: Identify 6+ types of bias in a pharmaceutical study
- **Must Identify**: Funding bias, Conflict of interest, Selection bias, Attrition bias, Detection bias, HARKing
- **Timeout**: 900s
- **Key Skill**: Recognize systematic bias types and their validity impact

### 2. Fallacy Detection
- **Difficulty**: Medium
- **Focus**: Identifying logical fallacies in arguments
- **Rubric Profile**: Analytical Quality (75%), Output Structure (25%)
- **Task**: Detect fallacies in a vaccine-autism argument
- **Must Identify**: Post hoc, Hasty generalization, Confounding
- **Timeout**: 600s
- **Key Skill**: Distinguish correlation from causation, recognize formal fallacies

### 3. Methodology Critique
- **Difficulty**: Medium
- **Focus**: Assessing research design validity
- **Rubric Profile**: Analytical Quality (75%), Output Structure (25%)
- **Task**: Critique the methodology of a described study
- **Must Identify**: Design flaws, validity threats, missing controls
- **Timeout**: 900s
- **Key Skill**: Evaluate internal/external validity threats

### 4. Contradictory Evidence
- **Difficulty**: Hard
- **Focus**: Reconciling conflicting research findings
- **Rubric Profile**: Analytical Quality (75%), Output Structure (25%)
- **Task**: Analyze why two studies reached opposite conclusions
- **Must Identify**: Methodological differences, confounding factors, population differences
- **Timeout**: 900s
- **Key Skill**: Explain empirical contradiction through systematic analysis

---

## Hypothesis-Explorer (5 tests)

### 1. Hypothesis Formulation
- **Difficulty**: Medium
- **Focus**: Formulating testable, specific hypotheses
- **Rubric Profile**: Design Quality (60%), Analytical Quality (30%), Output Structure (10%)
- **Task**: Generate 3+ testable hypotheses from a research question
- **Must Identify**: Clear prediction, specific variables, falsifiable statement
- **Timeout**: 600s
- **Key Skill**: Operationalize variables and create testable predictions

### 2. Unfalsifiable Claim
- **Difficulty**: Hard
- **Focus**: Detecting unfalsifiable or circular claims
- **Rubric Profile**: Design Quality (60%), Analytical Quality (30%), Output Structure (10%)
- **Task**: Identify why a claim is unfalsifiable and suggest fix
- **Must Identify**: Circular reasoning, non-falsifiable statement, how to make testable
- **Timeout**: 600s
- **Key Skill**: Understand falsifiability as core principle of science

### 3. Variable Mapping
- **Difficulty**: Hard
- **Focus**: Identifying and operationalizing research variables
- **Rubric Profile**: Design Quality (60%), Analytical Quality (30%), Output Structure (10%)
- **Task**: Map conceptual variables to measurable constructs
- **Must Identify**: IV/DV distinction, confounds, operationalization quality
- **Timeout**: 600s
- **Key Skill**: Define measurement strategies for abstract concepts

### 4. Outcome Scorer
- **Difficulty**: Medium
- **Focus**: Treating the scoring instrument as part of the pre-registered design
- **Rubric Profile**: Design Quality (60%), Analytical Quality (30%), Output Structure (10%)
- **Task**: Write a pre-registration plan for a study scored by extracting JSON from free-text answers
- **Must Identify**: Scorer tested on real outputs before freezing, tie-break rule, both scores reported after a post-hoc change
- **Timeout**: 900s
- **Key Skill**: Validate the measurement instrument before the plan is frozen

### 5. Manipulation Check
- **Difficulty**: Medium
- **Focus**: Confirming the manipulation triggers the hypothesised mechanism before pre-registration
- **Rubric Profile**: Design Quality (60%), Analytical Quality (30%), Output Structure (10%)
- **Task**: Write a pre-registration plan for a memory feature tested on one-step tasks in fresh sessions
- **Must Identify**: Per-run mechanism proxy, pilot floor fixed before freezing, null result counts only if the floor was met
- **Timeout**: 900s
- **Key Skill**: Show the study exercises the mechanism before a null result can count

---

## Lateral-Thinker (3 tests)

### 1. Analogy Finding
- **Difficulty**: Hard
- **Focus**: Finding novel analogies to explain concepts
- **Rubric Profile**: Analytical Quality (70%), Output Structure (30%)
- **Task**: Generate 3+ apt analogies explaining a technical concept
- **Must Identify**: Appropriate mappings, clarity of explanation, novel connections
- **Timeout**: 600s
- **Key Skill**: Transfer knowledge across domains, find structural similarities

### 2. Constraint Satisfaction
- **Difficulty**: Hard
- **Focus**: Finding solutions within competing constraints
- **Rubric Profile**: Analytical Quality (70%), Output Structure (30%)
- **Task**: Design a research study satisfying 5+ competing constraints
- **Must Identify**: All constraints satisfied, trade-offs explained, feasibility
- **Timeout**: 900s
- **Key Skill**: Optimize across multiple objectives, understand design trade-offs

### 3. First Principles
- **Difficulty**: Hard
- **Focus**: Breaking down complex problems to first principles
- **Rubric Profile**: Analytical Quality (70%), Output Structure (30%)
- **Task**: Build up explanation of phenomenon from atomic principles
- **Must Identify**: Core assumptions, logical steps, emergence of complexity
- **Timeout**: 900s
- **Key Skill**: Reductionist thinking, rebuild from basics

---

## Literature-Reviewer (4 tests)

### 1. Basic Search
- **Difficulty**: Easy
- **Focus**: Conducting literature searches
- **Rubric Profile**: Research Quality (70%), Analytical Quality (20%), Output Structure (10%)
- **Task**: Outline search strategy for a research question
- **Must Identify**: Relevant keywords, search terms, databases, scope
- **Timeout**: 600s
- **Key Skill**: Systematic information retrieval, Boolean search operators

### 2. Citation Chain
- **Difficulty**: Hard
- **Focus**: Tracing connections between cited papers
- **Rubric Profile**: Research Quality (70%), Analytical Quality (20%), Output Structure (10%)
- **Task**: Follow citations back 3+ steps, identify foundational work
- **Must Identify**: Key citations, seminal papers, research lineage
- **Timeout**: 900s
- **Key Skill**: Understand research genealogy, trace intellectual development

### 3. Gap Analysis
- **Difficulty**: Medium
- **Focus**: Identifying gaps in existing literature
- **Rubric Profile**: Research Quality (70%), Analytical Quality (20%), Output Structure (10%)
- **Task**: Synthesize literature and identify research gaps
- **Must Identify**: Covered areas, gaps, future directions, unanswered questions
- **Timeout**: 900s
- **Key Skill**: Meta-analysis of literature, identify unexplored areas

### 4. Hallucination Detection
- **Difficulty**: Hard
- **Focus**: Detecting fabricated or misrepresented citations
- **Rubric Profile**: Research Quality (70%), Analytical Quality (20%), Output Structure (10%)
- **Task**: Identify fabricated citations or misquotations
- **Must Identify**: Which citations are suspicious, why, verification strategy
- **Timeout**: 900s
- **Key Skill**: Source verification, identify inconsistencies

---

## Qual-Researcher (3 tests)

### 1. Coding Strategy
- **Difficulty**: Medium
- **Focus**: Qualitative data analysis coding approach
- **Rubric Profile**: Qualitative Quality (75%), Output Structure (25%)
- **Task**: Design coding scheme for interview data
- **Must Identify**: Code categories, hierarchy, codebook, application examples
- **Timeout**: 900s
- **Key Skill**: Create systematic categorization, ensure inter-rater reliability

### 2. Leading Questions
- **Difficulty**: Hard
- **Focus**: Recognizing biased interview techniques
- **Rubric Profile**: Qualitative Quality (75%), Output Structure (25%)
- **Task**: Identify leading/biased questions, propose neutral alternatives
- **Must Identify**: Bias in phrasing, impact on responses, neutral rewording
- **Timeout**: 600s
- **Key Skill**: Researcher reflexivity, eliminate interviewer bias

### 3. Thematic Analysis
- **Difficulty**: Medium
- **Focus**: Identifying themes in qualitative data
- **Rubric Profile**: Qualitative Quality (75%), Output Structure (25%)
- **Task**: Extract themes from transcribed interview text
- **Must Identify**: Key themes, supporting quotes, theme hierarchy, saturation
- **Timeout**: 900s
- **Key Skill**: Pattern recognition in unstructured data

---

## Quant-Analyst (3 tests)

### 1. Effect Size Interpretation
- **Difficulty**: Medium
- **Focus**: Interpreting statistical effect sizes
- **Rubric Profile**: Quantitative Quality (75%), Output Structure (25%)
- **Task**: Interpret effect sizes and practical significance
- **Must Identify**: Statistical vs practical significance, magnitude assessment, context
- **Timeout**: 600s
- **Key Skill**: Move beyond p-values to effect magnitude

### 2. Simpson's Paradox
- **Difficulty**: Hard
- **Focus**: Understanding statistical paradoxes
- **Rubric Profile**: Quantitative Quality (75%), Output Structure (25%)
- **Task**: Explain how aggregated data can reverse direction of simple relationships
- **Must Identify**: Paradox mechanism, Simpson's paradox concept, resolution
- **Timeout**: 600s
- **Key Skill**: Understand confounding and stratification in data

### 3. Stat Method Selection
- **Difficulty**: Medium
- **Focus**: Choosing appropriate statistical tests
- **Rubric Profile**: Quantitative Quality (75%), Output Structure (25%)
- **Task**: Select appropriate statistical test for research question/data
- **Must Identify**: Test assumptions, rationale, alternatives, effect size metric
- **Timeout**: 600s
- **Key Skill**: Match methods to data characteristics

---

## Ethics-Expert (3 tests)

### 1. Privacy Risk
- **Difficulty**: Hard
- **Focus**: Identifying privacy and ethical risks in research
- **Rubric Profile**: Design Quality (70%), Analytical Quality (20%), Output Structure (10%)
- **Task**: Identify privacy risks in a data collection protocol
- **Must Identify**: De-identification risks, consent issues, data protection, regulatory compliance
- **Timeout**: 900s
- **Key Skill**: Anticipate privacy threats, regulatory knowledge

### 2. Deception Without Debriefing
- **Difficulty**: Medium
- **Focus**: Deception, debriefing and participant welfare in an online experiment
- **Rubric Profile**: Design Quality (70%), Analytical Quality (20%), Output Structure (10%)
- **Task**: Assess an online study that gives fabricated negative feedback with no debriefing
- **Must Identify**: Missing debriefing, psychological harm, unfair pay, an invalid exemption claim
- **Timeout**: 900s
- **Key Skill**: Apply deception and debriefing standards

### 3. Re-identification Risk
- **Difficulty**: Hard
- **Focus**: Re-identification risk in a "de-identified" health dataset
- **Rubric Profile**: Design Quality (70%), Analytical Quality (20%), Output Structure (10%)
- **Task**: Assess a public release of rare-disease records that keeps birth date, ZIP code and sex
- **Must Identify**: Quasi-identifiers, small-population risk, HIPAA Safe Harbor not met, review required
- **Timeout**: 900s
- **Key Skill**: Recognize identifying combinations of fields

---

## Methodology-Expert (3 tests)

### 1. Methodology Selection
- **Difficulty**: Medium
- **Focus**: Matching research questions to optimal methodology
- **Rubric Profile**: Design Quality (70%), Analytical Quality (30%)
- **Task**: Recommend methodology for understanding remote work well-being
- **Must Identify**: Question classification, 2+ candidate methodologies, design specification, quality standards
- **Timeout**: 900s
- **Key Skill**: Map research question to appropriate method family

### 2. Mixed Methods Design
- **Difficulty**: Hard
- **Focus**: Designing integrated mixed-methods studies
- **Rubric Profile**: Design Quality (75%), Analytical Quality (25%)
- **Task**: Design mixed-methods study evaluating workplace wellness program
- **Must Identify**: Mixed methods design type, qual/quant components, integration point, timeline
- **Timeout**: 900s
- **Key Skill**: Integrate qualitative and quantitative approaches coherently

### 3. Methodology Validation
- **Difficulty**: Medium
- **Focus**: Evaluating whether proposed design fits research question
- **Rubric Profile**: Analytical Quality (70%), Design Quality (30%)
- **Task**: Critique a proposed correlational study design and identify flaws
- **Must Identify**: 2+ validity threats, explain impact, propose improvements
- **Timeout**: 900s
- **Key Skill**: Assess design-question fit and measurement validity

---

## Peer-Reviewer (3 tests)

### 1. Manuscript Critique
- **Difficulty**: Medium
- **Focus**: Comprehensive peer review of research manuscript
- **Rubric Profile**: Analytical Quality (50%), Research Quality (30%), Output Structure (20%)
- **Task**: Provide peer review of manuscript with critical assessment
- **Must Identify**: Major flaws, methodological issues, significance, clarity
- **Timeout**: 900s
- **Key Skill**: Holistic research evaluation, constructive feedback

### 2. Statistical Flaws
- **Difficulty**: Medium
- **Focus**: Statistical errors in a manuscript summary
- **Rubric Profile**: Analytical Quality (50%), Research Quality (30%), Output Structure (20%)
- **Task**: Referee a small observational study that claims causation from one of 15 outcomes
- **Must Identify**: Causal overclaim, multiple comparisons, selective reporting, small sample
- **Timeout**: 900s
- **Key Skill**: Detect statistical overreach

### 3. ML Reproducibility
- **Difficulty**: Hard
- **Focus**: Evaluation and reproducibility flaws in a machine-learning submission
- **Rubric Profile**: Analytical Quality (50%), Research Quality (30%), Output Structure (20%)
- **Task**: Referee a paper that tuned on the test set with one seed and mismatched baselines
- **Must Identify**: Test-set leakage, missing variance, unfair baselines, missing code and data
- **Timeout**: 900s
- **Key Skill**: Apply sound machine-learning evaluation practice

---

## Grant-Writer (3 tests)

### 1. Grant Proposal Structure
- **Difficulty**: Medium
- **Focus**: Structuring a funding proposal from a research concept
- **Rubric Profile**: Design Quality (50%), Analytical Quality (30%), Output Structure (20%)
- **Task**: Structure an NSF grant proposal for an AI wildfire prediction project
- **Must Identify**: Significance, independent specific aims, feasibility/limitations, NSF alignment
- **Timeout**: 900s
- **Key Skill**: Transform technical idea into fundable narrative arc

### 2. Specific Aims Revision
- **Difficulty**: Medium
- **Focus**: Critiquing and rewriting a weak Specific Aims page
- **Rubric Profile**: Design Quality (50%), Analytical Quality (30%), Output Structure (20%)
- **Task**: Revise R01 aims that depend on each other and lack a hypothesis
- **Must Identify**: Dependent aims, missing hypothesis, missing outcomes, independent rewritten aims
- **Timeout**: 900s
- **Key Skill**: Turn exploratory aims into testable ones

### 3. Resubmission Introduction
- **Difficulty**: Hard
- **Focus**: Responding to reviewer critiques in a resubmission
- **Rubric Profile**: Design Quality (50%), Analytical Quality (30%), Output Structure (20%)
- **Task**: Write a one-page Introduction answering four reviewer critiques
- **Must Identify**: Every critique addressed, valid points conceded with changes, no argument with reviewers
- **Timeout**: 900s
- **Key Skill**: Persuade the same panel on resubmission

---

## Rubric Reference

### 1. Analytical Quality (125 lines)
**Dimensions**: Logical Rigor, Fallacy/Flaw Detection, Counterargument Strength, Assumption Analysis

**Point Scale**: 40 + 30 + 20 + 10 = 100 points max

**Used For**:
- Critical-Analyzer (all 4 tests)
- Hypothesis-Explorer (all 5 tests)
- Lateral-Thinker (all 3 tests)
- Literature-Reviewer (all 4 tests)
- Ethics-Expert (all 3 tests)
- Methodology-Expert (all 3 tests)
- Grant-Writer (all 3 tests)
- Peer-Reviewer (all 3 tests)

**Key Criteria**:
- Logical validity and soundness
- Flaw/fallacy identification accuracy
- Quality and diversity of counterarguments
- Hidden assumption surfacing

### 2. Research Quality (102 lines)
**Dimensions**: Source Credibility, Citation Accuracy, Evidence Evaluation, Literature Synthesis

**Point Scale**: 40 + 30 + 20 + 10 = 100 points max

**Used For**:
- Literature-Reviewer (all 4 tests)
- Peer-Reviewer (all 3 tests)

**Key Criteria**:
- Citation accuracy and relevance
- Source evaluation rigor
- Evidence quality assessment
- Synthesis coherence

### 3. Quantitative Quality (148 lines)
**Dimensions**: Statistical Rigor, Assumption Checking, Effect Size Understanding, Interpretation Accuracy

**Point Scale**: 35 + 30 + 20 + 10 + 5 = 100 points max

**Used For**:
- Quant-Analyst (all 3 tests)

**Key Criteria**:
- Correct test selection
- Assumption verification
- Proper effect size calculation
- Contextual interpretation

### 4. Qualitative Quality (144 lines)
**Dimensions**: Coding Strategy, Data Saturation, Reflexivity, Theme Validity

**Point Scale**: 30 + 30 + 20 + 10 + 10 = 100 points max

**Used For**:
- Qual-Researcher (all 3 tests)

**Key Criteria**:
- Systematic coding approach
- Saturation achievement
- Researcher bias awareness
- Theme grounding in data

### 5. Design Quality (142 lines)
**Dimensions**: Hypothesis Clarity, Operationalization, Control Adequacy, Feasibility

**Point Scale**: 30 + 25 + 20 + 15 + 10 = 100 points max

**Used For**:
- Hypothesis-Explorer (all 5 tests)
- Ethics-Expert (all 3 tests)
- Methodology-Expert (all 3 tests)
- Grant-Writer (all 3 tests)

**Key Criteria**:
- Testable hypothesis formulation
- Variable operationalization quality
- Control/confound management
- Practical feasibility

### 6. Output Structure (138 lines)
**Dimensions**: Organization, Completeness, Clarity, Visual Communication

**Point Scale**: 25 + 20 + 20 + 20 + 15 = 100 points max

**Used For**:
- Critical-Analyzer (all 4 tests)
- Hypothesis-Explorer (all 5 tests)
- Lateral-Thinker (all 3 tests)
- Literature-Reviewer (all 4 tests)
- Qual-Researcher (all 3 tests)
- Quant-Analyst (all 3 tests)
- Ethics-Expert (all 3 tests)
- Grant-Writer (all 3 tests)
- Peer-Reviewer (all 3 tests)

**Key Criteria**:
- Logical flow and hierarchy
- All required elements present
- Technical clarity
- Visual presentation quality

### 7. Reasoning Quality (129 lines)
**Dimensions**: Logic Transparency, Evidence Integration, Conclusion Justification, Uncertainty Expression

**Point Scale**: 30 + 25 + 20 + 15 + 10 = 100 points max

**Used For**: No current test case

**Key Criteria**:
- Explicit reasoning chains
- Evidence-based argumentation
- Well-justified conclusions
- Appropriate confidence expression

---

## Scoring Scale (All Rubrics)

| Score Range | Rating | Interpretation |
|---|---|---|
| 90-100 | Excellent | PhD-level quality, exceeds professional standards |
| 75-89 | Good | Strong performance with minor issues |
| 60-74 | Acceptable | Meets requirements with room for improvement |
| 40-59 | Below Standard | Significant issues, needs work |
| 0-39 | Unacceptable | Fails to meet basic requirements |

---

## Default Test Weights

**Standard Configuration**:
- Primary Rubric: 50-75%
- Secondary Rubric: 20-40%
- Tertiary/Output: 10-25%

**Example**:
- Bias Identification: 75% Analytical + 25% Output = 100%
- Manuscript Critique: 75% Analytical + 25% Output = 100%

**Overall Score Calculation**:
```
Score = (Primary_Score × Primary_Weight) + (Secondary_Score × Secondary_Weight) + (Tertiary_Score × Tertiary_Weight)
```

---

## Test Difficulty Rationale

**Hard (47%, 16 tests)**:
- Require high-level reasoning
- Designed to differentiate frontier models
- Examples: Analogy Finding, Simpson's Paradox, First Principles

**Medium (50%, 17 tests)**:
- Balanced cognitive load
- Test practical competencies
- Examples: Fallacy Detection, Effect Size Interpretation

**Easy (3%, 1 test)**:
- Foundation-level validation
- Example: Basic Search

This distribution is intentional - PhD-level agents should struggle with hard tests.

---

## Test-Rubric Mapping Matrix

| Test | Primary Rubric | Secondary | Agent Category |
|---|---|---|---|
| [Bias Identification](critical-analysis/test-bias-identification.md) | Analytical (75%) | Output (25%) | Critical-Analyzer |
| [Fallacy Detection](critical-analysis/test-fallacy-detection.md) | Analytical (75%) | Output (25%) | Critical-Analyzer |
| [Methodology Critique](critical-analysis/test-methodology-critique.md) | Analytical (75%) | Output (25%) | Critical-Analyzer |
| [Contradictory Evidence](critical-analysis/test-contradictory-evidence.md) | Analytical (75%) | Output (25%) | Critical-Analyzer |
| [Hypothesis Formulation](hypothesis-testing/test-hypothesis-formulation.md) | Design (60%) | Analytical (30%) | Hypothesis-Explorer |
| [Unfalsifiable Claim](hypothesis-testing/test-unfalsifiable-claim.md) | Design (60%) | Analytical (30%) | Hypothesis-Explorer |
| [Variable Mapping](hypothesis-testing/test-variable-mapping.md) | Design (60%) | Analytical (30%) | Hypothesis-Explorer |
| [Outcome Scorer](hypothesis-testing/test-outcome-scorer.md) | Design (60%) | Analytical (30%) | Hypothesis-Explorer |
| [Manipulation Check](hypothesis-testing/test-manipulation-check.md) | Design (60%) | Analytical (30%) | Hypothesis-Explorer |
| [Analogy Finding](lateral-thinking/test-analogy-finding.md) | Analytical (70%) | Output (30%) | Lateral-Thinker |
| [Constraint Satisfaction](lateral-thinking/test-constraint-satisfaction.md) | Analytical (70%) | Output (30%) | Lateral-Thinker |
| [First Principles](lateral-thinking/test-first-principles.md) | Analytical (70%) | Output (30%) | Lateral-Thinker |
| [Basic Search](literature-review/test-basic-search.md) | Research (70%) | Analytical (20%) | Literature-Reviewer |
| [Citation Chain](literature-review/test-citation-chain.md) | Research (70%) | Analytical (20%) | Literature-Reviewer |
| [Gap Analysis](literature-review/test-gap-analysis.md) | Research (70%) | Analytical (20%) | Literature-Reviewer |
| [Hallucination Detection](literature-review/test-hallucination-detection.md) | Research (70%) | Analytical (20%) | Literature-Reviewer |
| [Coding Strategy](qualitative-research/test-coding-strategy.md) | Qualitative (75%) | Output (25%) | Qual-Researcher |
| [Leading Questions](qualitative-research/test-leading-questions.md) | Qualitative (75%) | Output (25%) | Qual-Researcher |
| [Thematic Analysis](qualitative-research/test-thematic-analysis.md) | Qualitative (75%) | Output (25%) | Qual-Researcher |
| [Effect Size Interpretation](quantitative-analysis/test-effect-size-interpretation.md) | Quantitative (75%) | Output (25%) | Quant-Analyst |
| [Simpson's Paradox](quantitative-analysis/test-simpson-paradox.md) | Quantitative (75%) | Output (25%) | Quant-Analyst |
| [Stat Method Selection](quantitative-analysis/test-stat-method-selection.md) | Quantitative (75%) | Output (25%) | Quant-Analyst |
| [Privacy Risk](ethics-review/test-privacy-risk.md) | Design (70%) | Analytical (20%) | Ethics-Expert |
| [Deception Without Debriefing](ethics-review/test-deception-debriefing.md) | Design (70%) | Analytical (20%) | Ethics-Expert |
| [Re-identification Risk](ethics-review/test-reidentification-risk.md) | Design (70%) | Analytical (20%) | Ethics-Expert |
| [Methodology Selection](research-methodology/test-methodology-selection.md) | Design (70%) | Analytical (30%) | Methodology-Expert |
| [Mixed Methods Design](research-methodology/test-mixed-methods-design.md) | Design (75%) | Analytical (25%) | Methodology-Expert |
| [Methodology Validation](research-methodology/test-methodology-validation.md) | Analytical (70%) | Design (30%) | Methodology-Expert |
| [Grant Proposal Structure](grant-writing/test-grant-proposal.md) | Design (50%) | Analytical (30%) | Grant-Writer |
| [Specific Aims Revision](grant-writing/test-specific-aims-revision.md) | Design (50%) | Analytical (30%) | Grant-Writer |
| [Resubmission Introduction](grant-writing/test-resubmission-response.md) | Design (50%) | Analytical (30%) | Grant-Writer |
| [Manuscript Critique](peer-review/test-manuscript-critique.md) | Analytical (50%) | Research (30%) | Peer-Reviewer |
| [Statistical Flaws](peer-review/test-statistical-flaws.md) | Analytical (50%) | Research (30%) | Peer-Reviewer |
| [ML Reproducibility](peer-review/test-ml-reproducibility.md) | Analytical (50%) | Research (30%) | Peer-Reviewer |

---

## Current Performance by Test

See benchmark_history.json for latest scores per test case.

**Top Performers** (across all models):
1. Bias Identification: 92.2 avg (Gemini)
2. Fallacy Detection: 97.3 avg (Gemini)
3. Quant-Analyst tests: 96.7 avg (Gemini)

**Challenging Tests** (where models struggle):
1. Lateral-Thinker (Analogy, Constraint, First Principles): 31-98 range
2. Literature-Reviewer (Hallucination): 60-98 range
3. Peer-Reviewer (Manuscript): 73-98 range

---

## How to Use This Reference

**For Dashboard Development**:
- Use test metadata to populate difficulty badges, rubric profiles
- Extract must-include behaviors for compliance checking
- Reference timeouts for evaluation settings

**For Improvement Planning**:
- Identify which rubric dimensions cause failures
- Target rubric-specific training/fine-tuning
- Understand test difficulty distribution

**For Benchmarking**:
- Know expected score ranges by difficulty
- Understand rubric weighting for fair comparison
- Reference agent specialization by test focus
