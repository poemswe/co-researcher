import pathlib
import sys
from types import SimpleNamespace

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

from lib.core import parse_test_case  # noqa: E402
import run_eval  # noqa: E402


@pytest.mark.parametrize(("relative_path", "expected", "expected_skill"), [
    ("grant-writing/test-grant-proposal.md", "grant-proposal", "grant-writing"),
    ("lateral-thinking/test-analogy-finding.md", "lateral-thinking",
     "research-methodology"),
    ("research-methodology/test-methodology-selection.md",
     "research-methodology", "research-methodology"),
])
def test_test_case_directory_defines_stable_benchmark_capability(
    relative_path, expected, expected_skill,
):
  path = ROOT / "evals/test-cases" / relative_path
  test_case = parse_test_case(path)
  assert test_case.agent == expected
  assert test_case.implementation_skill == expected_skill


def test_explicit_capability_must_match_test_directory(tmp_path):
  path = tmp_path / "lateral-thinking" / "test-example.md"
  path.parent.mkdir()
  path.write_text("""# Test Case: Example

## Metadata
- **Capability**: research-methodology
- **Implementation Skill**: research-methodology

## Rubric Profile
- **Primary**: analytical-quality (100%)

## Task Prompt
```
Example task.
```
""", encoding="utf-8")

  with pytest.raises(ValueError, match="Capability.*does not match"):
    parse_test_case(path)


def test_runner_executes_implementation_skill_not_capability(
    tmp_path, monkeypatch,
):
  test_case = parse_test_case(
      ROOT / "evals/test-cases/lateral-thinking/test-analogy-finding.md")
  called = []

  def fake_execute(skill, prompt, timeout, model):
    called.append(skill)
    return SimpleNamespace(success=True, duration=0.1, output="result")

  report = SimpleNamespace(
      passed=True, overall_score=100.0, scores={"analytical-quality": 100})
  monkeypatch.setattr(run_eval, "execute_agent", fake_execute)
  monkeypatch.setattr(run_eval, "evaluate_output", lambda *args: report)
  monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
  monkeypatch.setattr(
      run_eval, "generate_report", lambda *args: tmp_path / "report.md")

  assert run_eval._execute_single_test(test_case, "codex", False) is report
  assert called == ["research-methodology"]
