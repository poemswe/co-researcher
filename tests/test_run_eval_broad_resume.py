import json
import pathlib
import sys
import types

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

import run_eval  # noqa: E402


def _case(agent, name):
  return types.SimpleNamespace(
      agent=agent, implementation_skill=agent, name=name, file_path=None,
      task_prompt="prompt", timeout=10)


def _report(case, score=90.0):
  return types.SimpleNamespace(
      test_case=case, overall_score=score, passed=score >= 70,
      rubric_breakdown={}, agent_output="output", judge_output="REASONING: ok",
      must_include_met=[], must_include_missed=[], execution_metadata={})


@pytest.fixture
def broad(tmp_path, monkeypatch):
  cases = [_case("peer-review", "Statistical Flaws"),
           _case("peer-review", "Manuscript Critique"),
           _case("ethics-review", "Privacy Risk")]
  calls = []

  def execute(case, model, verbose):
    calls.append(case.name)
    return _report(case)

  monkeypatch.setattr(run_eval, "EVALS_DIR", tmp_path)
  monkeypatch.setattr(run_eval, "discover_tests", lambda _directory: cases)
  monkeypatch.setattr(run_eval, "_execute_single_test", execute)
  monkeypatch.setattr(run_eval, "generate_summary", lambda _directory: run_eval.RESULTS_DIR / "s.md")
  return types.SimpleNamespace(cases=cases, calls=calls, root=tmp_path)


def _overview(root):
  return json.loads((root / "benchmark_overview.json").read_text())


def test_resume_runs_only_missing_cases_into_one_run(broad):
  run_id = "run_20261008_000000_000001"
  run_eval.save_benchmark_v2([_report(broad.cases[0], 80.0)], "codex:x low", run_id)

  run_eval.main(["all", "-m", "codex:x low", "--resume", run_id])

  assert broad.calls == ["Manuscript Critique", "Privacy Risk"]
  detail = json.loads((broad.root / f"test_results_detail/{run_id}.json").read_text())
  assert sorted(r["test_name"] for r in detail["test_results"]) == [
      "Manuscript Critique", "Privacy Risk", "Statistical Flaws"]
  entries = [r for r in _overview(broad.root)["runs"] if r["run_id"] == run_id]
  assert len(entries) == 1
  assert entries[0]["tests_run"] == 3
  assert entries[0]["average_score"] == round((80 + 90 + 90) / 3, 1)


def test_resume_refuses_a_different_model(broad, capsys):
  run_id = "run_20261008_000000_000002"
  run_eval.save_benchmark_v2([_report(broad.cases[0])], "codex:x low", run_id)

  with pytest.raises(SystemExit) as exit_info:
    run_eval.main(["all", "-m", "claude:y", "--resume", run_id])

  assert exit_info.value.code == 2
  assert broad.calls == []
  assert "same model" in capsys.readouterr().err


def test_unknown_resume_run_exits_before_running(broad):
  with pytest.raises(SystemExit) as exit_info:
    run_eval.main(["all", "--resume", "run_20991231_000000_000000"])

  assert exit_info.value.code == 2
  assert broad.calls == []


def test_incomplete_broad_run_prints_the_resume_command(broad, monkeypatch, capsys):
  def execute(case, model, verbose):
    broad.calls.append(case.name)
    return None if case.name == "Privacy Risk" else _report(case)

  monkeypatch.setattr(run_eval, "_execute_single_test", execute)
  monkeypatch.setattr(run_eval, "generate_run_id", lambda: "run_20261008_000000_000003")

  run_eval.main(["all", "-m", "codex:x low"])

  out = capsys.readouterr().out
  assert "1 of 3 tests did not run" in out
  assert "--resume run_20261008_000000_000003" in out


def test_a_judge_error_is_an_execution_error_not_a_zero_score(monkeypatch):
  case = _case("ethics-review", "Privacy Risk")
  monkeypatch.setattr(run_eval, "execute_agent", lambda *a: types.SimpleNamespace(
      success=True, output="answer", duration=1.0, error=None))
  failed = _report(case, 0.0)
  failed.judge_output = "Judge error: You've hit your usage limit."
  monkeypatch.setattr(run_eval, "evaluate_output", lambda *a: failed)
  monkeypatch.setattr(
      run_eval, "generate_report", lambda *a: run_eval.RESULTS_DIR / "report.md")
  ok = _report(case, 0.0)
  monkeypatch.setattr(run_eval, "evaluate_output", lambda *a: ok)
  ok.scores = {}
  assert run_eval._execute_single_test(case, "codex:x low", False) is ok

  failed.scores = {}
  monkeypatch.setattr(run_eval, "evaluate_output", lambda *a: failed)
  assert run_eval._execute_single_test(case, "codex:x low", False) is None
