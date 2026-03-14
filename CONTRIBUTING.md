# Contributing to Co-Researcher

We welcome contributions from the research community — bug fixes, documentation improvements, new skills, or eval test cases.

## How to Contribute

1. **Bug Reports & Feature Requests**: Use the GitHub issues tracker.
2. **Improving Skills**:
    - Modify the `SKILL.md` files in `skills/`.
    - Validate changes using the evaluation framework in `evals/`.
    - Keep protocols grounded in established research methodologies.
3. **Developing New Skills**:
    - Follow the existing pattern in `skills/`.
    - Create a test case in `evals/test-cases/[skill-name]/`.
    - Run benchmarks to verify performance.

## Evaluation Protocol

All changes affecting skill behavior must be validated against the **Co-Researcher Benchmark (v2.0)**.
```bash
cd evals
python run_eval.py [skill-name]
```
Maintaining reasoning integrity and rubric scores is required before merging.

## Style Guide

- **Language**: Objective, academic, and accessible English.
- **Documentation**: New skills must be listed in `README.md`.
- **Formatting**: Follow existing Markdown structure in `skills/`.

## License

By contributing, you agree that your contributions will be licensed under the MIT License found in the LICENSE file.
