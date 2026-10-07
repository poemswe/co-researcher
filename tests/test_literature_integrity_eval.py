import json
import pathlib
import subprocess
import sys
from dataclasses import fields, is_dataclass
from types import SimpleNamespace

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

from lib.literature_integrity import (  # noqa: E402
    CaseDefinition,
    IntegrityEvalResult,
    LiteratureIntegrityRunner,
    ModelUsage,
    ProductionModelExecutor,
    ProductionQualityJudge,
    QualityResult,
    RepairCost,
    RobustnessResult,
    SnapshotEvaluation,
    load_cases,
)
from lib import literature_integrity  # noqa: E402
from lib.run_reports import (  # noqa: E402
    CombinedRunResult, load_dashboard_data, write_run_report)
from review_integrity.models import IntegrityRunReport  # noqa: E402
from review_integrity.repair import safe_repair_feedback  # noqa: E402


def _write_workspace(workspace: pathlib.Path, state: int) -> None:
  """Write deterministic passes that improve twice but stay invalid."""
  payloads = {
      "protocol.md": "" if state == 0 else "# Synthetic protocol\n",
      "corpus.json": [],
      "claims.json": [],
      "synthesis.md": "" if state < 2 else f"final synthesis {state}\n",
      "refs.json": [],
      "project.json": {"project": "synthetic-eval"},
  }
  for relative_path, payload in payloads.items():
    destination = workspace / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
      destination.write_text(payload, encoding="utf-8")
    else:
      destination.write_text(json.dumps(payload), encoding="utf-8")


class FakeExecutor:
  def __init__(self):
    self.workspaces = []
    self.initial_contents = []
    self.feedback = []
    self.state_by_workspace = {}

  @staticmethod
  def _usage(*, cost: float) -> ModelUsage:
    return ModelUsage(
        duration_seconds=0.25,
        input_tokens=10,
        output_tokens=20,
        estimated_cost_usd=cost,
        executor_version="fake-1",
        prompt_version="fake-prompt-1",
        prompt_sha256="a" * 64,
    )

  def first_pass(self, case, workspace):
    self.workspaces.append(workspace)
    self.initial_contents.append(tuple(workspace.iterdir()))
    self.state_by_workspace[workspace] = 0
    _write_workspace(workspace, 0)
    return self._usage(cost=0.4)

  def repair(self, feedback, workspace):
    self.feedback.append(feedback)
    assert set(feedback) == {
        "reason_codes", "affected_artifacts", "findings"}
    state = self.state_by_workspace[workspace] + 1
    self.state_by_workspace[workspace] = state
    _write_workspace(workspace, state)
    return self._usage(cost=0.1)


class RecordingJudge:
  def __init__(self, *, fail_on=None):
    self.syntheses = []
    self.fail_on = fail_on

  def score(self, case, synthesis):
    self.syntheses.append(synthesis)
    if synthesis == self.fail_on:
      raise RuntimeError("synthetic judge failure")
    score = 11.0 if not synthesis else 89.0
    return QualityResult(
        quality_score=score,
        scores={
            "research-quality": score,
            "analytical-quality": score,
            "output-structure": score,
        },
        error=None,
    )


def _case(tmp_path, case_id="synthetic-case", expected_status="invalid"):
  case_dir = tmp_path / "cases" / case_id
  case_dir.mkdir(parents=True)
  fixture = case_dir / "fixture.txt"
  fixture.write_text("synthetic public input\n", encoding="utf-8")
  (case_dir / "case.json").write_text(json.dumps({
      "schema_version": "1.0.0",
      "capability": "literature-review-integrity",
      "case_id": case_id,
      "prompt": "Create a synthetic review workspace.",
      "domain": "testing",
      "fixture_paths": ["fixture.txt"],
      "quality_rubric_id": "literature-review-v1",
  }), encoding="utf-8")
  (case_dir / "expected.json").write_text(json.dumps({
      "schema_version": "1.0.0",
      "final_status": expected_status,
      "minimum_repair_rounds": 0,
      "maximum_repair_rounds": 3,
  }), encoding="utf-8")
  return next(
      case for case in load_cases(case_dir.parent) if case.case_id == case_id)


def _runner(tmp_path, executor=None, judge=None):
  return LiteratureIntegrityRunner(
      executor or FakeExecutor(), judge or RecordingJudge(),
      workspace_parent=tmp_path / "workspaces",
      scorecard_directory=tmp_path / "cases")


def _reachable_strings(value, seen=None):
  seen = set() if seen is None else seen
  if id(value) in seen:
    return []
  seen.add(id(value))
  if isinstance(value, pathlib.PurePath):
    return [str(value)]
  if isinstance(value, str):
    return [value]
  if isinstance(value, dict):
    return [
        item
        for key, nested in value.items()
        for item in (*_reachable_strings(key, seen),
                     *_reachable_strings(nested, seen))
    ]
  if isinstance(value, (tuple, list, set)):
    return [item for nested in value
            for item in _reachable_strings(nested, seen)]
  if is_dataclass(value):
    return [item for definition in fields(value)
            for item in _reachable_strings(
                getattr(value, definition.name), seen)]
  return []


def test_integrity_mode_is_listed_by_cli():
  result = subprocess.run(
      [sys.executable, str(ROOT / "evals/run_eval.py"), "list"],
      check=False, capture_output=True, text=True, timeout=10)

  assert result.returncode == 0
  assert "literature-review-integrity" in result.stdout
  help_result = subprocess.run(
      [sys.executable, str(ROOT / "evals/run_eval.py"), "--help"],
      check=False, capture_output=True, text=True, timeout=10)
  assert "literature-review-integrity" in help_result.stdout


def test_cli_list_recursively_reports_all_integrity_cases_in_sorted_order():
  command = [sys.executable, str(ROOT / "evals/run_eval.py"), "list"]
  first = subprocess.run(
      command, check=False, capture_output=True, text=True, timeout=10)
  second = subprocess.run(
      command, check=False, capture_output=True, text=True, timeout=10)

  assert first.returncode == second.returncode == 0
  assert first.stdout == second.stdout
  section = first.stdout.split("  literature-review-integrity\n", 1)[1]
  entries = []
  for line in section.splitlines():
    if line.startswith("    - "):
      entries.append(line.removeprefix("    - "))
    elif entries:
      break
  assert len(entries) == 15
  assert entries == sorted(entries)
  assert entries[:2] == ["integrity-case-001", "integrity-case-002"]
  assert entries[-2:] == ["synthetic-invalid-number", "synthetic-valid"]
  assert "expected.json" not in first.stdout


def test_eval_uses_isolated_workspace_per_case(tmp_path):
  executor = FakeExecutor()
  first = _case(tmp_path, "one")
  second = _case(tmp_path, "two")
  runner = _runner(tmp_path, executor=executor)

  runner.run_case(first)
  runner.run_case(second)

  assert len(set(executor.workspaces)) == 2
  assert executor.initial_contents == [(), ()]
  assert all("cases" not in workspace.parts for workspace in executor.workspaces)


def test_first_pass_is_immutable_after_repairs(tmp_path):
  executor = FakeExecutor()
  judge = RecordingJudge()
  case = _case(tmp_path)

  result = _runner(tmp_path, executor, judge).run_case(case)

  assert result.model_first_pass.quality.quality_score == 11.0
  assert result.model_first_pass.integrity.manifest_sha256 == (
      result.model_first_pass.workspace_manifest_sha256)
  assert result.system_final.workspace_manifest_sha256 != (
      result.model_first_pass.workspace_manifest_sha256)
  assert result.model_first_pass.integrity.to_dict() == (
      result.repair_rounds[0].previous_integrity.to_dict())
  with pytest.raises(TypeError):
    result.model_first_pass.quality.scores["research-quality"] = 100.0


def test_quality_judge_receives_first_and_final_synthesis_from_matching_snapshots(
    tmp_path,
):
  judge = RecordingJudge()
  case = _case(tmp_path)

  result = _runner(tmp_path, judge=judge).run_case(case)

  assert judge.syntheses == ["", "final synthesis 3\n"]
  assert result.model_first_pass.quality.quality_score == 11.0
  assert result.system_final.quality.quality_score == 89.0
  assert result.system_final.workspace_manifest_sha256 == (
      result.system_final.integrity.manifest_sha256)


def test_eval_stops_after_three_repairs(tmp_path):
  executor = FakeExecutor()
  case = _case(tmp_path)

  result = _runner(tmp_path, executor=executor).run_case(case)

  assert len(result.repair_rounds) == 3
  assert len(executor.feedback) == 3
  assert result.repair_rounds[-1].action == "stop_invalid"
  assert result.repair_cost.rounds == 3
  assert result.repair_cost.estimated_cost_usd == pytest.approx(0.3)


def test_eval_marks_unresolved_critical_case_invalid(tmp_path):
  case = _case(tmp_path)
  result = _runner(tmp_path).run_case(case)

  assert result.system_final.integrity.status.value == "invalid"
  assert result.robustness.observed_final_status == "invalid"
  assert result.robustness.expectation_met is True


def test_quality_and_integrity_scores_are_not_blended(tmp_path):
  case = _case(tmp_path)
  result = _runner(tmp_path).run_case(case)
  serialized = result.to_dict()

  assert serialized["model_first_pass"]["quality"]["quality_score"] == 11.0
  assert serialized["model_first_pass"]["integrity"]["integrity_score"] != 11.0
  assert "overall_score" not in serialized
  assert set(serialized) == {
      "schema_version", "model_first_pass", "repair_rounds",
      "system_final", "repair_cost", "robustness",
  }


def test_eval_result_round_trips_with_a_closed_schema(tmp_path):
  case = _case(tmp_path)
  result = _runner(tmp_path).run_case(case)

  assert IntegrityEvalResult.from_dict(result.to_dict()) == result
  with pytest.raises(ValueError, match="unknown fields"):
    IntegrityEvalResult.from_dict({**result.to_dict(), "overall_score": 50})


def test_eval_result_rejects_rewritten_first_pass_chain(tmp_path):
  case = _case(tmp_path)
  serialized = _runner(tmp_path).run_case(case).to_dict()
  serialized["repair_rounds"][0]["previous_integrity"] = (
      serialized["system_final"]["integrity"])

  with pytest.raises(ValueError, match="previous integrity"):
    IntegrityEvalResult.from_dict(serialized)


def test_eval_result_rejects_repair_cost_that_does_not_match_usage(tmp_path):
  case = _case(tmp_path)
  serialized = _runner(tmp_path).run_case(case).to_dict()
  serialized["repair_cost"]["estimated_cost_usd"] = 99.0

  with pytest.raises(ValueError, match="repair_cost"):
    IntegrityEvalResult.from_dict(serialized)


def test_repair_round_retains_and_validates_reason_chain(tmp_path):
  case = _case(tmp_path)
  serialized = _runner(tmp_path).run_case(case).to_dict()
  expected = list(dict.fromkeys(
      finding["reason_code"]
      for finding in serialized["repair_rounds"][0]["integrity"]["findings"]))

  assert serialized["repair_rounds"][0]["reason_codes"] == expected
  serialized["repair_rounds"][0]["reason_codes"] = []
  with pytest.raises(ValueError, match="reason_codes"):
    IntegrityEvalResult.from_dict(serialized)


def test_quality_failure_is_explicit_and_does_not_change_integrity(tmp_path):
  judge = RecordingJudge(fail_on="final synthesis 3\n")
  case = _case(tmp_path)

  result = _runner(tmp_path, judge=judge).run_case(case)

  assert result.system_final.quality.quality_score is None
  assert result.system_final.quality.error == "synthetic judge failure"
  assert result.system_final.integrity.status.value == "invalid"
  with pytest.raises(TypeError):
    result.system_final.quality.scores["research-quality"] = 0.0


def test_case_loader_rejects_unknown_or_secret_fields(tmp_path):
  case_dir = tmp_path / "bad"
  case_dir.mkdir()
  payload = {
      "schema_version": "1.0.0",
      "capability": "literature-review-integrity",
      "case_id": "bad",
      "prompt": "prompt",
      "domain": "testing",
      "fixture_paths": [],
      "quality_rubric_id": "literature-review-v1",
      "answer_key": "must not be accepted",
  }
  (case_dir / "case.json").write_text(json.dumps(payload), encoding="utf-8")

  with pytest.raises(ValueError, match="unknown fields"):
    load_cases(tmp_path)


def test_case_sidecars_never_enter_workspace_or_quality_input(tmp_path):
  executor = FakeExecutor()
  judge = RecordingJudge()
  case = _case(tmp_path)

  _runner(tmp_path, executor, judge).run_case(case)

  assert executor.initial_contents == [()]
  assert all("expected" not in synthesis for synthesis in judge.syntheses)
  assert all("final_status" not in json.dumps(item)
             for item in executor.feedback)


def test_case_scoring_material_is_not_reachable_by_executor_or_judge(tmp_path):
  observed = []

  class IntrospectionExecutor(FakeExecutor):
    def first_pass(self, case, workspace):
      observed.extend(_reachable_strings((case, workspace)))
      observed.extend(str(path) for path in workspace.rglob("*"))
      return super().first_pass(case, workspace)

    def repair(self, feedback, workspace):
      observed.extend(_reachable_strings((feedback, workspace)))
      observed.extend(str(path) for path in workspace.rglob("*"))
      return super().repair(feedback, workspace)

  class IntrospectionJudge(RecordingJudge):
    def score(self, case, synthesis):
      observed.extend(_reachable_strings((case, synthesis)))
      return super().score(case, synthesis)

  case = _case(
      tmp_path, case_id="integrity-case-800",
      expected_status="valid_with_warnings")
  scorecard = tmp_path / "cases" / case.case_id / "expected.json"
  scorecard.write_text(json.dumps({
      "schema_version": "1.0.0", "final_status": "valid_with_warnings",
      "minimum_repair_rounds": 0, "maximum_repair_rounds": 3,
      "attack_family": "unicode-substitution",
      "reason_expectations": [{
          "reason_code": "fabricated_quote", "present": True,
          "unit": {"artifact": "claims.json", "context_key": "result_index",
                   "context_value": 0},
      }],
  }))
  executor = IntrospectionExecutor()
  result = _runner(
      tmp_path, executor, IntrospectionJudge()).run_case(case)
  reachable = "\n".join(observed)

  assert "expected.json" not in reachable
  assert "valid_with_warnings" not in reachable
  assert "unicode-substitution" not in reachable
  assert str(tmp_path / "cases") not in reachable
  assert not any("score" in definition.name.lower()
                 for definition in fields(case))
  assert executor.feedback[0] == safe_repair_feedback(
      result.model_first_pass.integrity)


def test_scorecards_preload_in_memory_without_temp_artifacts(
    monkeypatch, tmp_path,
):
  case = _case(
      tmp_path, case_id="integrity-case-807",
      expected_status="valid_with_warnings")
  scorecard = tmp_path / "cases" / case.case_id / "expected.json"
  scorecard.write_text(json.dumps({
      "schema_version": "1.0.0", "final_status": "invalid",
      "minimum_repair_rounds": 3, "maximum_repair_rounds": 3,
      "attack_family": "memory-only-family",
      "reason_expectations": [{
          "reason_code": "fabricated_quote", "present": False,
          "unit": {"artifact": "claims.json", "context_key": None,
                   "context_value": None},
      }],
  }))
  safe_temp = tmp_path / "scorecard-temp"
  safe_temp.mkdir()
  monkeypatch.setattr(literature_integrity, "_SAFE_TEMP_ROOT", safe_temp)

  runner = _runner(tmp_path)
  assert not tuple(safe_temp.rglob("*"))
  scorecard.unlink()
  result = runner.run_case(case)

  assert result.robustness.expected_final_status == "invalid"
  assert result.robustness.minimum_repair_rounds == 3
  assert not tuple(safe_temp.rglob("*"))


def test_runner_records_unsafe_case_and_continues_to_next_case(tmp_path):
  first = _case(tmp_path, case_id="integrity-case-801")
  second = _case(tmp_path, case_id="integrity-case-802")

  class SequenceExecutor(FakeExecutor):
    def first_pass(self, case, workspace):
      usage = super().first_pass(case, workspace)
      if len(self.workspaces) == 1:
        (workspace / "refs.json").unlink()
      return usage

  runner = _runner(tmp_path, executor=SequenceExecutor())
  results = runner.run_cases((first, second), tmp_path / "run")

  assert len(results) == 2
  first_wire = results[0].to_dict()
  assert first_wire["operational_failure"]["reason_code"] == "artifact_missing"
  assert first_wire["operational_failure"]["status"] == "invalid"
  assert results[1].model_first_pass.workspace_manifest_sha256
  assert (tmp_path / "run" / "integrity-case-801.json").is_file()
  assert (tmp_path / "run" / "integrity-case-802.json").is_file()


def test_repair_load_failure_counts_failed_submitted_attempt_in_cost_and_bounds(
    tmp_path,
):
  case = _case(tmp_path, case_id="integrity-case-805")
  scorecard = tmp_path / "cases" / case.case_id / "expected.json"
  scorecard.write_text(json.dumps({
      "schema_version": "1.0.0", "final_status": "invalid",
      "minimum_repair_rounds": 1, "maximum_repair_rounds": 1,
  }))

  class SymlinkRepairExecutor(FakeExecutor):
    def repair(self, feedback, workspace):
      usage = super().repair(feedback, workspace)
      outside = workspace.parent / "outside-refs.json"
      outside.write_text("[]")
      (workspace / "refs.json").unlink()
      (workspace / "refs.json").symlink_to(outside)
      return usage

  result = _runner(
      tmp_path, executor=SymlinkRepairExecutor()).run_case(case)

  assert result.operational_failure.phase == "repair_load"
  assert result.operational_failure.attempt == 1
  assert result.repair_rounds == ()
  assert result.repair_cost.rounds == 1
  assert result.repair_cost.input_tokens == 10
  assert result.repair_cost.output_tokens == 20
  assert result.repair_cost.estimated_cost_usd == 0.1
  assert result.robustness.expectation_met is True


def test_operational_result_rejects_forged_attempt_cost_and_expectation(tmp_path):
  case = _case(tmp_path, case_id="integrity-case-806")

  class MissingRepairExecutor(FakeExecutor):
    def repair(self, feedback, workspace):
      usage = super().repair(feedback, workspace)
      (workspace / "refs.json").unlink()
      return usage

  result = _runner(tmp_path, executor=MissingRepairExecutor()).run_case(case)
  serialized = result.to_dict()

  forged_cost = json.loads(json.dumps(serialized))
  forged_cost["repair_cost"]["rounds"] = 0
  with pytest.raises(ValueError, match="cost|attempt"):
    literature_integrity.decode_integrity_result(forged_cost)

  forged_expectation = json.loads(json.dumps(serialized))
  forged_expectation["robustness"]["expectation_met"] = not (
      serialized["robustness"]["expectation_met"])
  with pytest.raises(ValueError, match="robustness|expectation"):
    literature_integrity.decode_integrity_result(forged_expectation)

  forged_bounds = json.loads(json.dumps(serialized))
  forged_bounds["robustness"]["minimum_repair_rounds"] = 2
  with pytest.raises(ValueError, match="robustness|expectation"):
    literature_integrity.decode_integrity_result(forged_bounds)

  forged_status = json.loads(json.dumps(serialized))
  forged_status["robustness"]["observed_final_status"] = "valid"
  with pytest.raises(ValueError, match="robustness|invalid"):
    literature_integrity.decode_integrity_result(forged_status)

  forged_error = json.loads(json.dumps(serialized))
  forged_error["robustness"]["error"] = "forged scorer error"
  with pytest.raises(ValueError, match="error|robustness"):
    literature_integrity.decode_integrity_result(forged_error)


def _repair_failure_after_two_trusted_rounds(tmp_path):
  class ThirdRepairFailsToLoad(FakeExecutor):
    def repair(self, feedback, workspace):
      usage = super().repair(feedback, workspace)
      if len(self.feedback) == 3:
        (workspace / "refs.json").unlink()
      return usage

  case = _case(tmp_path, case_id="integrity-case-809")
  result = _runner(
      tmp_path, executor=ThirdRepairFailsToLoad()).run_case(case)
  assert len(result.repair_rounds) == 2
  assert result.operational_failure.attempt == 3
  return result.to_dict()


@pytest.mark.parametrize("mutation", [
    lambda value: value["repair_rounds"][0].update(
        previous_integrity=value["repair_rounds"][0]["integrity"]),
    lambda value: value["repair_rounds"][1].update(attempt=3),
    lambda value: value["repair_rounds"][1].update(attempt=1),
    lambda value: value["repair_rounds"][0].update(action="pass"),
    lambda value: value["repair_rounds"][-1].update(action="stop_invalid"),
    lambda value: value["repair_rounds"][0].update(
        workspace_manifest_sha256="f" * 64),
    lambda value: value["repair_rounds"][0]["model_usage"].update(
        duration_seconds=99.0),
])
def test_operational_result_rejects_forged_repair_chain(tmp_path, mutation):
  serialized = _repair_failure_after_two_trusted_rounds(tmp_path)
  mutation(serialized)

  with pytest.raises(ValueError):
    literature_integrity.decode_integrity_result(serialized)


def test_operational_result_rejects_successful_history_followed_by_failure(
    tmp_path,
):
  serialized = _repair_failure_after_two_trusted_rounds(tmp_path)
  valid = IntegrityRunReport.example_valid().pass_report.to_dict()
  first_round = serialized["repair_rounds"][0]
  first_round.update({
      "integrity": valid,
      "workspace_manifest_sha256": valid["manifest_sha256"],
      "reason_codes": [],
      "action": "pass",
  })
  serialized["repair_rounds"][1]["previous_integrity"] = valid

  with pytest.raises(ValueError, match="terminal|policy|repair"):
    literature_integrity.decode_integrity_result(serialized)


@pytest.mark.parametrize("bad_attack", [
    {"attack_family": "", "reason_expectations": []},
    {"attack_family": "unicode-substitution", "reason_expectations": [{
        "reason_code": "not-a-reason", "present": True,
        "unit": {"artifact": "claims.json", "context_key": None,
                 "context_value": None}}]},
])
def test_invalid_adversarial_scorecard_is_an_explicit_scorer_error(
    tmp_path, bad_attack,
):
  case = _case(tmp_path, case_id="integrity-case-803")
  scorecard = tmp_path / "cases" / case.case_id / "expected.json"
  payload = json.loads(scorecard.read_text())
  payload.update(bad_attack)
  scorecard.write_text(json.dumps(payload))

  result = _runner(tmp_path).run_case(case)

  assert result.robustness.expectation_met is None
  assert result.robustness.error


def test_scorecard_preload_is_immutable_during_model_and_judge_phases(tmp_path):
  case = _case(tmp_path, expected_status="valid_with_warnings")
  scorecard = tmp_path / "cases" / case.case_id / "expected.json"

  class FinalJudge(RecordingJudge):
    def score(self, case, synthesis):
      result = super().score(case, synthesis)
      if len(self.syntheses) == 2:
        scorecard.write_text(json.dumps({
            "schema_version": "1.0.0",
            "final_status": "invalid",
            "minimum_repair_rounds": 3,
            "maximum_repair_rounds": 3,
        }), encoding="utf-8")
      return result

  result = _runner(tmp_path, judge=FinalJudge()).run_case(case)

  assert result.robustness.expected_final_status == "valid_with_warnings"
  assert result.robustness.expectation_met is False


def _capture_executor_calls(monkeypatch):
  calls = []
  monkeypatch.setattr(
      literature_integrity, "find_cli",
      lambda provider: pathlib.Path(f"/fake/{provider}"))

  def fake_run(command, **kwargs):
    calls.append((command, kwargs))
    return SimpleNamespace(returncode=0, stdout="", stderr="")

  monkeypatch.setattr(literature_integrity.subprocess, "run", fake_run)
  return calls


def test_claude_executor_can_create_and_repair_workspace(
    monkeypatch, tmp_path,
):
  calls = _capture_executor_calls(monkeypatch)
  case = _case(tmp_path)
  executor = ProductionModelExecutor("claude", ROOT)
  workspace = tmp_path / "model-workspace"
  workspace.mkdir()

  executor.first_pass(case, workspace)
  executor.repair({
      "reason_codes": [], "affected_artifacts": [], "findings": [],
  }, workspace)

  for index, (command, _kwargs) in enumerate(calls):
    tools = command[command.index("--tools") + 1].split(",")
    assert {"Read", "Write", "Edit", "Bash"} <= set(tools)
    assert command[command.index("--permission-mode") + 1] == "acceptEdits"
    if index == 0:
      assert {"WebSearch", "WebFetch"} <= set(tools)
    else:
      assert not {"WebSearch", "WebFetch"} & set(tools)
    prompt = command[command.index("-p") + 1]
    assert "expected.json" not in prompt
    assert "final_status" not in prompt
    assert str(tmp_path / "cases") not in prompt
    assert str(ROOT) not in prompt
    assert "unicode-substitution" not in prompt
    if index == 0:
      assert str(tmp_path / "cases") not in prompt
      skill_line = next(
          line for line in prompt.splitlines() if line.startswith("Skill path:"))
      fixture_line = next(
          line for line in prompt.splitlines() if line.startswith("- /"))
      staged_paths = [
          pathlib.Path(skill_line.split(": ", 1)[1]),
          pathlib.Path(fixture_line.removeprefix("- ")),
      ]
      assert all("synthetic-attacks" not in str(path) for path in staged_paths)
      assert all(not path.exists() for path in staged_paths)


def test_capture_prompt_anchors_the_workspace_at_the_current_directory(
    monkeypatch, tmp_path,
):
  calls = _capture_executor_calls(monkeypatch)
  workspace = tmp_path / "model-workspace"
  workspace.mkdir()

  ProductionModelExecutor("claude", ROOT).first_pass(_case(tmp_path), workspace)

  prompt = calls[0][0][calls[0][0].index("-p") + 1]
  assert 'WS="$(pwd)"' in prompt
  assert "Do not create review/{slug}" in prompt
  assert "$WS/project.json" in prompt
  assert literature_integrity.CAPTURE_PROMPT_VERSION == (
      "literature-integrity-capture-v2")


@pytest.mark.parametrize("returncode", [0, 17])
def test_first_pass_stages_only_public_bytes_and_cleans_immediately(
    monkeypatch, tmp_path, returncode,
):
  safe_temp = tmp_path / "executor-temp"
  safe_temp.mkdir()
  monkeypatch.setattr(literature_integrity, "_SAFE_TEMP_ROOT", safe_temp)
  monkeypatch.setattr(
      literature_integrity, "find_cli", lambda _provider: pathlib.Path(
          "/fake/claude"))
  case = _case(tmp_path, case_id="integrity-case-808")
  scorecard = tmp_path / "cases" / case.case_id / "expected.json"
  scorecard.write_text('{"attack_family":"must-never-stage"}')
  active_snapshots = []
  active_roots = []

  def inspect_active_staging(command, **kwargs):
    prompt = command[command.index("-p") + 1]
    skill_path = pathlib.Path(next(
        line.split(": ", 1)[1] for line in prompt.splitlines()
        if line.startswith("Skill path:")))
    staging = skill_path.parent.parent
    active_roots.append(staging)
    files = tuple(
        (path.relative_to(staging).as_posix(), path.read_bytes())
        for path in sorted(staging.rglob("*")) if path.is_file())
    active_snapshots.append(files)
    return SimpleNamespace(
        returncode=returncode, stdout="", stderr="synthetic failure")

  monkeypatch.setattr(
      literature_integrity.subprocess, "run", inspect_active_staging)
  workspace = tmp_path / "workspace"
  workspace.mkdir()

  if returncode:
    with pytest.raises(
        literature_integrity.ModelExecutionError, match="exited 17"):
      ProductionModelExecutor("claude", ROOT).first_pass(case, workspace)
  else:
    ProductionModelExecutor("claude", ROOT).first_pass(case, workspace)

  assert len(active_snapshots) == 1
  staged = active_snapshots[0]
  fixture_files = [item for item in staged if item[0].startswith("fixture-")]
  assert fixture_files == [("fixture-001.txt", b"synthetic public input\n")]
  serialized = b"\n".join(
      name.encode() + b"\n" + content for name, content in staged)
  assert b"expected.json" not in serialized
  assert b"must-never-stage" not in serialized
  assert not active_roots[0].name.startswith("literature-")
  assert not tuple(safe_temp.rglob("*"))


@pytest.mark.parametrize("provider", ["codex", "gemini"])
def test_non_claude_executor_commands_keep_provider_write_mode(
    monkeypatch, tmp_path, provider,
):
  calls = _capture_executor_calls(monkeypatch)
  case = _case(tmp_path)
  workspace = tmp_path / f"{provider}-workspace"
  workspace.mkdir()

  ProductionModelExecutor(provider, ROOT).first_pass(case, workspace)

  command, kwargs = calls[0]
  assert command[-1] == "-"
  assert kwargs["input"]
  if provider == "codex":
    assert "--full-auto" not in command
    sandbox = command.index("--sandbox")
    assert command[sandbox + 1] == "workspace-write"
    assert "--skip-git-repo-check" in command
  else:
    assert "--yolo" in command


@pytest.mark.parametrize(("provider", "credential", "config_home"), [
    ("claude", "ANTHROPIC_API_KEY", "CLAUDE_CONFIG_DIR"),
    ("codex", "OPENAI_API_KEY", "CODEX_HOME"),
    ("gemini", "GEMINI_API_KEY", "GEMINI_CLI_HOME"),
])
def test_production_executor_uses_closed_gold_isolated_child_environment(
    monkeypatch, tmp_path, provider, credential, config_home,
):
  calls = _capture_executor_calls(monkeypatch)
  case = _case(tmp_path, case_id="integrity-case-804")
  case_root = tmp_path / "cases"
  monkeypatch.setenv(credential, "credential-value")
  monkeypatch.setenv(config_home, str(ROOT / ".private-model-config"))
  monkeypatch.setenv("PYTHONPATH", str(ROOT))
  monkeypatch.setenv("VIRTUAL_ENV", str(ROOT / ".venv"))
  monkeypatch.setenv("OLDPWD", str(case_root))
  monkeypatch.setenv("TASK10_CASE_ROOT", str(case_root))
  monkeypatch.setenv("TASK10_FAMILY", "unicode-substitution")
  monkeypatch.setenv("TASK10_EXPECTED", str(case_root / "expected.json"))
  monkeypatch.setenv("UNRELATED_SECRET", "must-not-be-inherited")
  workspace = tmp_path / f"{provider}-workspace"
  workspace.mkdir()

  ProductionModelExecutor(provider, ROOT).first_pass(case, workspace)

  child = calls[0][1]["env"]
  serialized = "\n".join(f"{key}={value}" for key, value in child.items())
  assert child["PWD"] == str(workspace.resolve())
  assert child[credential] == "credential-value"
  assert child["PATH"] == (
      "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
  assert not ({
      "OLDPWD", "PYTHONPATH", "VIRTUAL_ENV", "TASK10_CASE_ROOT",
      "TASK10_FAMILY", "TASK10_EXPECTED", "UNRELATED_SECRET",
      config_home,
  } & set(child))
  assert str(ROOT) not in serialized
  assert str(case_root) not in serialized
  assert "unicode-substitution" not in serialized
  assert "expected.json" not in serialized


def _legacy_quality_report(output):
  return SimpleNamespace(
      judge_output=output,
      overall_score=0.0,
      scores={name: 0 for name in (
          "research-quality", "analytical-quality", "output-structure")},
  )


@pytest.mark.parametrize("output", [
    "unparseable response",
    "RESEARCH_QUALITY: 10\nANALYTICAL_QUALITY: 20\nOVERALL_SCORE: 15",
    "Judge error: unavailable",
])
def test_production_quality_judge_fails_closed_on_incomplete_output(
    monkeypatch, tmp_path, output,
):
  monkeypatch.setattr(
      literature_integrity, "evaluate_output",
      lambda *args: _legacy_quality_report(output))

  result = ProductionQualityJudge("claude").score(_case(tmp_path), "text")

  assert result.quality_score is None
  assert result.scores == {}
  assert result.error


def test_production_quality_judge_accepts_explicit_zero_scores(
    monkeypatch, tmp_path,
):
  output = (
      "RESEARCH_QUALITY: 0\n"
      "ANALYTICAL_QUALITY: 0\n"
      "OUTPUT_STRUCTURE: 0\n"
      "OVERALL_SCORE: 0\n")
  monkeypatch.setattr(
      literature_integrity, "evaluate_output",
      lambda *args: _legacy_quality_report(output))

  result = ProductionQualityJudge("claude").score(_case(tmp_path), "text")

  assert result.quality_score == 0.0
  assert result.scores == {
      "research-quality": 0.0,
      "analytical-quality": 0.0,
      "output-structure": 0.0,
  }
  assert result.error is None


@pytest.mark.parametrize("mutation", [
    lambda value: value["repair_rounds"][0].update(action="pass"),
    lambda value: value["repair_rounds"].pop(),
    lambda value: value["repair_rounds"][-1].update(action="repair"),
    lambda value: value["robustness"].update(expectation_met=False),
    lambda value: value["system_final"]["model_usage"].update(
        prompt_version="forged-final-usage"),
    lambda value: value["repair_rounds"][1].update(
        workspace_manifest_sha256="f" * 64),
])
def test_eval_result_rejects_policy_and_commitment_tampering(
    tmp_path, mutation,
):
  case = _case(tmp_path)
  serialized = _runner(tmp_path).run_case(case).to_dict()
  mutation(serialized)

  with pytest.raises(ValueError):
    IntegrityEvalResult.from_dict(serialized)


def test_eval_result_rejects_nonterminal_first_pass_without_repairs():
  report = IntegrityRunReport.example_valid().pass_report
  usage = FakeExecutor._usage(cost=0.0)
  quality = QualityResult(
      quality_score=0.0,
      scores={name: 0.0 for name in (
          "research-quality", "analytical-quality", "output-structure")},
      error=None,
  )
  first = SnapshotEvaluation(
      workspace_manifest_sha256=report.manifest_sha256,
      quality=quality, integrity=report, model_usage=usage)
  forged_usage = ModelUsage(
      duration_seconds=usage.duration_seconds,
      input_tokens=usage.input_tokens,
      output_tokens=usage.output_tokens,
      estimated_cost_usd=usage.estimated_cost_usd,
      executor_version=usage.executor_version,
      prompt_version="forged-final-usage",
      prompt_sha256=usage.prompt_sha256,
  )
  forged_final = SnapshotEvaluation(
      workspace_manifest_sha256=report.manifest_sha256,
      quality=quality, integrity=report, model_usage=forged_usage)

  with pytest.raises(ValueError, match="usage"):
    IntegrityEvalResult(
        model_first_pass=first,
        repair_rounds=(),
        system_final=forged_final,
        repair_cost=RepairCost.from_rounds(()),
        robustness=RobustnessResult(
            expected_final_status="valid",
            observed_final_status="valid",
            minimum_repair_rounds=0,
            maximum_repair_rounds=0,
            expectation_met=True,
            error=None,
        ),
    )


def test_replay_requires_repair_for_repairable_warning_first_pass():
  from review_integrity.models import (
      DimensionResult, Finding, PassReport, ReasonCode, Severity)
  finding = Finding(
      reason_code=ReasonCode.CLAIM_NEEDS_REVIEW, severity=Severity.WARNING,
      artifact="claims.json", message="claim support requires review")
  dimension = DimensionResult(
      name="quote_authenticity", score=0.0, applicable=True,
      evaluated_units=1, passed_units=0, nominal_weight=25.0,
      effective_weight=100.0, findings=[finding])
  report = PassReport(
      integrity_score=0.0, findings=[finding],
      dimensions={"quote_authenticity": dimension},
      manifest_sha256="c" * 64)
  quality = QualityResult(
      quality_score=0.0,
      scores={name: 0.0 for name in (
          "research-quality", "analytical-quality", "output-structure")},
      error=None,
  )
  first = SnapshotEvaluation(
      workspace_manifest_sha256=report.manifest_sha256, quality=quality,
      integrity=report, model_usage=FakeExecutor._usage(cost=0.0))

  assert literature_integrity._replay_repair_chain(first, ()) == "repair"


def test_executor_error_keeps_only_the_last_output_line(monkeypatch, tmp_path):
  monkeypatch.setattr(
      literature_integrity, "find_cli",
      lambda provider: pathlib.Path(f"/fake/{provider}"))
  monkeypatch.setattr(
      literature_integrity.subprocess, "run",
      lambda command, **kwargs: SimpleNamespace(
          returncode=1, stdout="",
          stderr="banner\nprompt echo\nERROR: You've hit your usage limit.\n"))
  workspace = tmp_path / "workspace"
  workspace.mkdir()

  with pytest.raises(literature_integrity.ModelExecutionError) as error:
    ProductionModelExecutor("codex", ROOT).first_pass(_case(tmp_path), workspace)

  assert str(error.value) == (
      "model executor exited 1: ERROR: You've hit your usage limit.")


def test_executor_timeout_is_a_model_execution_error(monkeypatch, tmp_path):
  monkeypatch.setattr(
      literature_integrity, "find_cli",
      lambda provider: pathlib.Path(f"/fake/{provider}"))

  def timeout(command, **kwargs):
    raise literature_integrity.subprocess.TimeoutExpired(command, 5)

  monkeypatch.setattr(literature_integrity.subprocess, "run", timeout)
  workspace = tmp_path / "workspace"
  workspace.mkdir()

  with pytest.raises(literature_integrity.ModelExecutionError, match="timed out"):
    ProductionModelExecutor("claude", ROOT).first_pass(_case(tmp_path), workspace)


_SNAPSHOT_PROVENANCE = {
    "target_commit": None, "target_dirty": None, "engine_version": "1.0.0",
    "validator_versions": {"claims": "1.0.0"},
}


def _snapshot_run(tmp_path):
  case = _case(tmp_path)
  runner = _runner(tmp_path)
  result = runner.run_case(case)
  run = CombinedRunResult.from_results(
      run_id="run-snapshots", timestamp="2026-10-06T12:00:00Z",
      model="fake", results=((case.case_id, result),),
      provenance=_SNAPSHOT_PROVENANCE)
  return case, runner, result, run


def test_runner_keeps_one_snapshot_per_loaded_pass(tmp_path):
  case, runner, result, _run = _snapshot_run(tmp_path)

  assert [snapshot.manifest_sha256
          for snapshot in runner.snapshots[case.case_id]] == [
      result.model_first_pass.workspace_manifest_sha256,
      *(item.workspace_manifest_sha256 for item in result.repair_rounds)]


def test_run_report_retains_verifiable_workspace_snapshots(tmp_path):
  case, runner, _result, run = _snapshot_run(tmp_path)
  root = tmp_path / "results"

  run_path = write_run_report(run, root, snapshots=runner.snapshots)
  selected = load_dashboard_data(root, "run-snapshots")

  references = selected["cases"][0]["snapshots"]
  assert [item["label"] for item in references] == [
      "first-pass", "round-01", "round-02", "round-03"]
  final = json.loads((run_path / references[-1]["path"]).read_text())
  files = {item["path"]: item["content"] for item in final["files"]}
  assert files["synthesis.md"] == "final synthesis 3\n"


def test_tampered_snapshot_is_rejected_on_load(tmp_path):
  _case, runner, _result, run = _snapshot_run(tmp_path)
  root = tmp_path / "results"
  run_path = write_run_report(run, root, snapshots=runner.snapshots)
  first = run_path / "snapshots" / "synthetic-case-first-pass.json"
  first.write_text(first.read_text().replace('"claims.json"', '"claimz.json"'))

  with pytest.raises(ValueError, match="snapshot"):
    load_dashboard_data(root, "run-snapshots")


def test_snapshots_must_match_the_recorded_manifests(tmp_path):
  case, runner, _result, run = _snapshot_run(tmp_path)
  reordered = {case.case_id: tuple(reversed(runner.snapshots[case.case_id]))}

  with pytest.raises(ValueError, match="snapshot"):
    write_run_report(run, tmp_path / "results", snapshots=reordered)


def test_unloadable_workspace_has_no_snapshot(tmp_path):
  class EmptyExecutor(FakeExecutor):
    def first_pass(self, case, workspace):
      return self._usage(cost=0.0)

  case = _case(tmp_path)
  runner = _runner(tmp_path, executor=EmptyExecutor())

  runner.run_case(case)

  assert runner.snapshots[case.case_id] == ()


def test_claude_first_pass_can_read_the_staged_skill(monkeypatch, tmp_path):
  calls = _capture_executor_calls(monkeypatch)
  workspace = tmp_path / "model-workspace"
  workspace.mkdir()

  ProductionModelExecutor("claude", ROOT).first_pass(_case(tmp_path), workspace)

  command = calls[0][0]
  prompt = command[command.index("-p") + 1]
  skill_path = pathlib.Path(next(
      line for line in prompt.splitlines()
      if line.startswith("Skill path:")).split(": ", 1)[1])
  added = command[command.index("--add-dir") + 1]
  assert skill_path.is_relative_to(added)


def _fake_cli(monkeypatch, *, stdout="", stderr=""):
  calls = []
  monkeypatch.setattr(
      literature_integrity, "find_cli",
      lambda provider: pathlib.Path(f"/fake/{provider}"))

  def fake_run(command, **kwargs):
    calls.append(command)
    return SimpleNamespace(returncode=0, stdout=stdout, stderr=stderr)

  monkeypatch.setattr(literature_integrity.subprocess, "run", fake_run)
  return calls


def test_claude_executor_records_the_resolved_model(monkeypatch, tmp_path):
  events = [
      {"type": "system", "subtype": "init", "model": "claude-opus-5-5"},
      {"type": "result", "subtype": "success", "result": "done"},
  ]
  calls = _fake_cli(monkeypatch, stdout=json.dumps(events))
  workspace = tmp_path / "workspace"
  workspace.mkdir()
  executor = ProductionModelExecutor("claude", ROOT)

  executor.first_pass(_case(tmp_path), workspace)

  assert calls[0][calls[0].index("--output-format") + 1] == "json"
  assert executor.resolved_models == {"claude-opus-5-5"}


def test_codex_executor_records_the_resolved_model(monkeypatch, tmp_path):
  _fake_cli(monkeypatch, stderr=(
      "OpenAI Codex v0.154.0\n--------\nmodel: gpt-6-astra\n"
      "provider: openai\n--------\n"))
  workspace = tmp_path / "workspace"
  workspace.mkdir()
  executor = ProductionModelExecutor("codex", ROOT)

  executor.first_pass(_case(tmp_path), workspace)

  assert executor.resolved_models == {"gpt-6-astra"}


def test_unrecognized_cli_output_records_no_model(monkeypatch, tmp_path):
  _fake_cli(monkeypatch, stdout="plain text output")
  workspace = tmp_path / "workspace"
  workspace.mkdir()
  executor = ProductionModelExecutor("claude", ROOT)

  executor.first_pass(_case(tmp_path), workspace)

  assert executor.resolved_models == set()


def test_executor_error_prefers_the_error_line_over_trailing_counts(
    monkeypatch, tmp_path,
):
  monkeypatch.setattr(
      literature_integrity, "find_cli",
      lambda provider: pathlib.Path(f"/fake/{provider}"))
  monkeypatch.setattr(
      literature_integrity.subprocess, "run",
      lambda command, **kwargs: SimpleNamespace(
          returncode=1, stdout="",
          stderr="ERROR: You've hit your usage limit.\ntokens used\n6,745\n"))
  workspace = tmp_path / "workspace"
  workspace.mkdir()

  with pytest.raises(literature_integrity.ModelExecutionError) as error:
    ProductionModelExecutor("codex", ROOT).first_pass(_case(tmp_path), workspace)

  assert str(error.value) == (
      "model executor exited 1: ERROR: You've hit your usage limit.")


def test_completed_cases_can_be_reloaded_with_their_snapshots(tmp_path):
  from lib.run_reports import load_completed_cases
  case, runner, result, run = _snapshot_run(tmp_path)
  root = tmp_path / "results"
  write_run_report(run, root, snapshots=runner.snapshots)

  report, completed = load_completed_cases(root, "run-snapshots")

  assert report["run_id"] == "run-snapshots"
  [(case_id, evaluation, adversarial_score, snapshots)] = completed
  assert case_id == case.case_id
  assert evaluation == result
  assert adversarial_score is None
  assert [snapshot.manifest_sha256 for snapshot in snapshots] == [
      snapshot.manifest_sha256 for snapshot in runner.snapshots[case.case_id]]
