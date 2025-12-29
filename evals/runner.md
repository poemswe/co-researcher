---
description: Run evaluation suite for co-researcher agents
---

# /eval - Evaluation Runner

Run evaluation tests against co-researcher agents to assess quality and performance.

## Usage

```
/eval [agent] [test]
```

### Examples
```
/eval all                           # Run all tests for all agents
/eval literature-reviewer           # Run all tests for literature-reviewer
/eval critical-analyzer fallacy     # Run specific test
```

## Available Tests

### literature-reviewer
| Test | Difficulty | Focus |
|------|------------|-------|
| basic-search | Easy | Search strategy and source retrieval |
| gap-analysis | Medium | Research gap identification |
| citation-chain | Hard | Citation tracing and influence mapping |

### critical-analyzer
| Test | Difficulty | Focus |
|------|------------|-------|
| fallacy-detection | Medium | Identifying logical fallacies |
| bias-identification | Hard | Research and cognitive bias detection |
| methodology-critique | Medium | Evaluating research methods |

### hypothesis-explorer
| Test | Difficulty | Focus |
|------|------------|-------|
| hypothesis-formulation | Medium | Creating testable hypotheses |
| variable-mapping | Hard | Identifying variables and confounds |

### quant-analyst
| Test | Difficulty | Focus |
|------|------------|-------|
| stat-method-selection | Medium | Choosing statistical tests |
| effect-size-interpretation | Medium | Understanding practical significance |

### qual-researcher
| Test | Difficulty | Focus |
|------|------------|-------|
| thematic-analysis | Medium | Identifying themes in text data |
| coding-strategy | Medium | Developing coding schemes |

### lateral-thinker
| Test | Difficulty | Focus |
|------|------------|-------|
| analogy-finding | Hard | Cross-domain analogy discovery |
| first-principles | Hard | Fundamental decomposition |

## Evaluation Process

1. **Load Test Case**: Read test prompt and expected behaviors
2. **Execute Agent**: Run agent with test prompt
3. **Apply Rubrics**: Use LLM-judge with appropriate rubrics
4. **Generate Report**: Produce scored evaluation report

## Rubrics Applied

| Dimension | Max Score | Description |
|-----------|-----------|-------------|
| Research Quality | 100 | Source credibility, comprehensiveness, accuracy, citations |
| Reasoning Quality | 100 | Logic, bias detection, methodology critique, alternatives |
| Output Structure | 100 | Organization, completeness, clarity, visual elements |

## Passing Criteria

- **Overall**: ≥ 70/100 weighted average
- **Primary dimension**: Must meet test-specific threshold
- **Critical items**: Must include all "Must Include" behaviors

## Output

Evaluation produces:
1. Score breakdown by dimension
2. Pass/fail determination
3. Strengths and weaknesses
4. Improvement recommendations

## Batch Evaluation

To evaluate all agents:
```
/eval all
```

This generates a summary report with:
- Per-agent scores
- Per-test scores
- Overall plugin quality assessment
- Comparative analysis across agents
