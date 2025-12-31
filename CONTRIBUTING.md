# Contributing to Co-Researcher

We welcome contributions from the research community! Whether you are fixing bugs, improving documentation, or adding new research agents, your help is appreciated.

## Technical Requirements
- Models: Most agents prefer `claude-4-5-sonnet` or similar PhD-level reasoning models.
- Environment: Python 3.10+, and a CLI environment capable of executing agent prompts.

## How to Contribute

1. **Bug Reports & Feature Requests**: Please use the GitHub issues tracker.
2. **Improving Agents**:
    - Modify the `.md` templates in `agents/`.
    - Validate changes using the evaluation framework in `evals/`.
    - Ensure principles and protocols are based on established research methodologies.
3. **Developing New Agents**:
    - Follow the existing pattern in `agents/`.
    - Create a test case in `evals/test-cases/[agent-name]/`.
    - Run benchmarks to verify performance.

## Evaluation Protocol

All changes affecting agent behavior must be validated against the **Co-Researcher Benchmark (v2.0)**.
```bash
cd evals
python run_eval.py [agent-name]
```
Ensuring the agent maintains its reasoning integrity and rubric scores is paramount.

## Style Guide
- **Language**: Use objective, academic, yet accessible English.
- **Documentation**: All new features must be documented in `KnowledgeGraph.md` and `README.md`.
- **Formatting**: Adhere to the existing Markdown structures.

## License
By contributing, you agree that your contributions will be licensed under the MIT License found in the LICENSE file.
