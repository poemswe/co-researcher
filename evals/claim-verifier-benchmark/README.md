# Claim-Verifier Benchmark

This project implements the deterministic benchmark described by the private
prospective protocol. It is separate from `evals/run_eval.py` and
`tests/eval_check_claims.py`.

The current phase contains protocol-core tooling only:

- RFC 8785 manifests and commitments;
- the canonical paper split;
- target-independent coverage-unit enumeration; and
- synthetic known-answer fixtures.

It does not contain official papers, official cases, annotations, system
outputs, or performance results. Do not run the frozen verifier, a comparator,
or an ablation on a prospective benchmark paper before the registered test
freeze.

## Verify

```bash
uv sync --project evals/claim-verifier-benchmark --locked
uv run --project evals/claim-verifier-benchmark pytest \
  evals/claim-verifier-benchmark/tests -q
uv run --project evals/claim-verifier-benchmark claim-benchmark-core \
  check-split-vector \
  evals/claim-verifier-benchmark/fixtures/split-vector.json
```
