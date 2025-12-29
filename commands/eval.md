---
description: Run evaluation tests against co-researcher agents and generate quality reports
argument-hint: [agent] [test-name] | all | list
---

# /eval - Run Agent Evaluations

Run evaluation tests against co-researcher agents and generate quality assessment reports using rubrics and LLM judges.

## Usage

```
/eval [agent] [test-name]
/eval all
/eval list
```

## Examples

{% if $ARGUMENTS == "all" %}
### Running All Tests
Running comprehensive evaluation of all 13 test cases across all 6 agents.

{% elsif $ARGUMENTS == "list" %}
### Available Tests

#### Literature Reviewer (3 tests)
- `basic-search` - Easy: Search strategy and source retrieval
- `gap-analysis` - Medium: Research gap identification
- `citation-chain` - Hard: Citation tracing and influence mapping

#### Critical Analyzer (3 tests)
- `fallacy-detection` - Medium: Identifying logical fallacies
- `bias-identification` - Hard: Cognitive and research bias detection
- `methodology-critique` - Medium: Evaluating research methods

#### Hypothesis Explorer (2 tests)
- `hypothesis-formulation` - Medium: Creating testable hypotheses
- `variable-mapping` - Hard: Identifying variables and confounds

#### Quantitative Analyst (2 tests)
- `stat-method-selection` - Medium: Choosing appropriate statistical tests
- `effect-size-interpretation` - Medium: Understanding practical significance

#### Qualitative Researcher (2 tests)
- `thematic-analysis` - Medium: Identifying themes in text data
- `coding-strategy` - Medium: Developing coding schemes

#### Lateral Thinker (2 tests)
- `analogy-finding` - Hard: Cross-domain analogy discovery
- `first-principles` - Hard: Fundamental decomposition and rebuilding

{% elsif $1 and not $2 %}
### Running All Tests for $1
Running all test cases for the $1 agent.

{% elsif $1 and $2 %}
### Running Specific Test
Running test '$2' for agent '$1'.

{% else %}
### Usage

**Run all tests**:
```
/eval all
```

**Run all tests for an agent**:
```
/eval literature-reviewer
/eval critical-analyzer
/eval hypothesis-explorer
/eval qual-researcher
/eval quant-analyst
/eval lateral-thinker
```

**Run specific test**:
```
/eval literature-reviewer basic-search
/eval critical-analyzer fallacy-detection
/eval hypothesis-explorer hypothesis-formulation
```

**List available tests**:
```
/eval list
```

{% endif %}

## Evaluation Process

For each test:

1. **Load Test Case** → Read test prompt, expected behaviors, evaluation criteria
2. **Execute Agent** → Run agent with test prompt
3. **Apply Rubrics** → Eval-judge scores against research quality, reasoning quality, output structure
4. **Generate Report** → Produces scored evaluation with feedback

## Scoring Dimensions

Each test evaluated across 3 dimensions (0-100 scale):

### Research Quality
- **Source Credibility** (0-25): Are sources academic and authoritative?
- **Comprehensiveness** (0-25): Are key perspectives covered?
- **Accuracy** (0-25): Are sources correctly represented?
- **Citation Quality** (0-25): Are citations complete and traceable?

### Reasoning Quality
- **Logical Coherence** (0-25): Are arguments valid and sound?
- **Bias Detection** (0-25): Are biases correctly identified?
- **Methodology Critique** (0-25): Is methodology appropriately assessed?
- **Alternative Explanations** (0-25): Are competing hypotheses generated?

### Output Structure
- **Organization** (0-25): Is content logically organized?
- **Completeness** (0-25): Are all required elements present?
- **Clarity** (0-25): Is writing clear and accessible?
- **Visual Communication** (0-25): Are tables/lists used effectively?

## Passing Criteria

| Criterion | Threshold |
|-----------|-----------|
| Overall Score | ≥ 70/100 |
| Primary Dimension | Test-specific threshold |
| Must-Include Items | All required behaviors |

## Available Tests

### Literature Reviewer (3 tests)
| Test | Difficulty | Focus |
|------|------------|-------|
| `basic-search` | Easy | Search strategy and source retrieval |
| `gap-analysis` | Medium | Research gap identification |
| `citation-chain` | Hard | Citation tracing and influence mapping |

**Example**: `/eval literature-reviewer citation-chain`

### Critical Analyzer (3 tests)
| Test | Difficulty | Focus |
|------|------------|-------|
| `fallacy-detection` | Medium | Identifying logical fallacies |
| `bias-identification` | Hard | Cognitive and research bias detection |
| `methodology-critique` | Medium | Evaluating research methods |

**Example**: `/eval critical-analyzer bias-identification`

### Hypothesis Explorer (2 tests)
| Test | Difficulty | Focus |
|------|------------|-------|
| `hypothesis-formulation` | Medium | Creating testable hypotheses |
| `variable-mapping` | Hard | Identifying variables and confounds |

**Example**: `/eval hypothesis-explorer variable-mapping`

### Quantitative Analyst (2 tests)
| Test | Difficulty | Focus |
|------|------------|-------|
| `stat-method-selection` | Medium | Choosing appropriate statistical tests |
| `effect-size-interpretation` | Medium | Understanding practical significance |

**Example**: `/eval quant-analyst stat-method-selection`

### Qualitative Researcher (2 tests)
| Test | Difficulty | Focus |
|------|------------|-------|
| `thematic-analysis` | Medium | Identifying themes in text data |
| `coding-strategy` | Medium | Developing coding schemes |

**Example**: `/eval qual-researcher thematic-analysis`

### Lateral Thinker (2 tests)
| Test | Difficulty | Focus |
|------|------------|-------|
| `analogy-finding` | Hard | Cross-domain analogy discovery |
| `first-principles` | Hard | Fundamental decomposition and rebuilding |

**Example**: `/eval lateral-thinker first-principles`

## Output Report

Each evaluation produces:

1. **Test Information** - Agent, test name, difficulty level
2. **Dimension Scores** - Research, reasoning, and structure quality with justifications
3. **Strengths** - What the agent did well
4. **Weaknesses** - Areas for improvement
5. **Overall Score** - Weighted aggregate (0-100)
6. **Rating** - Excellent/Good/Acceptable/Below Standard/Unacceptable
7. **Pass/Fail** - PASS if ≥70, FAIL if <70

### Example Output

```markdown
# Evaluation Report

## Test Information
- Test Case: Basic Literature Search
- Agent: literature-reviewer
- Difficulty: Easy

## Research Quality Assessment
### Source Credibility: 22/25
Justification: Used multiple peer-reviewed sources; mostly current publications

### Comprehensiveness: 20/25
Justification: Identified 7 relevant sources; minor gaps in grey literature

### Accuracy: 23/25
Justification: Sources accurately represented; preserved nuance and caveats

### Citation Quality: 24/25
Justification: Complete citations with DOIs; consistent formatting

**Research Quality Total: 89/100**

## Reasoning Quality Assessment
[Similar breakdown...]

## Output Structure Assessment
[Similar breakdown...]

## Overall Score
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Research Quality | 89 | 50% | 44.5 |
| Reasoning Quality | 82 | 25% | 20.5 |
| Output Structure | 85 | 25% | 21.25 |
| **Total** | | 100% | **86.25** |

## Rating: Good

## Key Findings
- **Top Strength**: Excellent source credibility and curation
- **Top Weakness**: Could include more grey literature
- **Improvement Priority**: Expand source scope to include more diverse perspectives

## Pass/Fail Determination
- Threshold: 70/100
- Result: **PASS** ✓
```

## Batch Evaluation

### Evaluate All Tests
```
/eval all
```

Produces summary report with:
- Per-agent average scores
- Per-test scores
- Overall plugin quality assessment
- Comparative analysis
- Recommendations for improvement

### Example Summary

```markdown
# Co-Researcher Plugin - Comprehensive Evaluation Report

## Per-Agent Results
| Agent | Tests | Avg Score | Status |
|-------|-------|-----------|--------|
| literature-reviewer | 3 | 82 | ✓ PASS |
| critical-analyzer | 3 | 78 | ✓ PASS |
| hypothesis-explorer | 2 | 75 | ✓ PASS |
| quant-analyst | 2 | 80 | ✓ PASS |
| qual-researcher | 2 | 77 | ✓ PASS |
| lateral-thinker | 2 | 72 | ✓ PASS |

**Overall Plugin Score: 77/100** → GOOD

## Test Results Summary
- Total Tests Run: 13
- Passed: 13 (100%)
- Failed: 0
- Average Score: 77/100
```

## Tips for Best Evaluations

1. **Start Simple** - Run easy tests first to establish baseline
2. **Check Specific Areas** - If an agent struggles, run related tests to isolate issues
3. **Compare Performance** - Run `/eval all` periodically to track improvements
4. **Review Feedback** - Pay attention to weakness recommendations
5. **Iterate** - Update agents based on evaluation results and re-test

## Evaluation Rubrics

Full rubrics are documented in:
- `evals/rubrics/research-quality.md` - Source credibility, comprehensiveness, accuracy, citations
- `evals/rubrics/reasoning-quality.md` - Logic, bias, methodology, alternatives
- `evals/rubrics/output-structure.md` - Organization, completeness, clarity, visuals

## Test Cases

All test cases located in `evals/test-cases/[agent]/test-[name].md` with:
- Task prompt
- Expected behaviors (must/should/should-not include)
- Evaluation criteria
- Passing threshold
- Rubric weights
