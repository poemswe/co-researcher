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
  if isinstance(value, pathlib.Path):
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


def test_eval_uses_isolated_workspace_per_case(tmp_path):
  executor = FakeExecutor()
  runner = _runner(tmp_path, executor=executor)

  runner.run_case(_case(tmp_path, "one"))
  runner.run_case(_case(tmp_path, "two"))

  assert len(set(executor.workspaces)) == 2
  assert executor.initial_contents == [(), ()]
  assert all("cases" not in workspace.parts for workspace in executor.workspaces)


def test_first_pass_is_immutable_after_repairs(tmp_path):
  executor = FakeExecutor()
  judge = RecordingJudge()

  result = _runner(tmp_path, executor, judge).run_case(_case(tmp_path))

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

  result = _runner(tmp_path, judge=judge).run_case(_case(tmp_path))

  assert judge.syntheses == ["", "final synthesis 3\n"]
  assert result.model_first_pass.quality.quality_score == 11.0
  assert result.system_final.quality.quality_score == 89.0
  assert result.system_final.workspace_manifest_sha256 == (
      result.system_final.integrity.manifest_sha256)


def test_eval_stops_after_three_repairs(tmp_path):
  executor = FakeExecutor()

  result = _runner(tmp_path, executor=executor).run_case(_case(tmp_path))

  assert len(result.repair_rounds) == 3
  assert len(executor.feedback) == 3
  assert result.repair_rounds[-1].action == "stop_invalid"
  assert result.repair_cost.rounds == 3
  assert result.repair_cost.estimated_cost_usd == pytest.approx(0.3)


def test_eval_marks_unresolved_critical_case_invalid(tmp_path):
  result = _runner(tmp_path).run_case(_case(tmp_path))

  assert result.system_final.integrity.status.value == "invalid"
  assert result.robustness.observed_final_status == "invalid"
  assert result.robustness.expectation_met is True


def test_quality_and_integrity_scores_are_not_blended(tmp_path):
  result = _runner(tmp_path).run_case(_case(tmp_path))
  serialized = result.to_dict()

  assert serialized["model_first_pass"]["quality"]["quality_score"] == 11.0
  assert serialized["model_first_pass"]["integrity"]["integrity_score"] != 11.0
  assert "overall_score" not in serialized
  assert set(serialized) == {
      "schema_version", "model_first_pass", "repair_rounds",
      "system_final", "repair_cost", "robustness",
  }


def test_eval_result_round_trips_with_a_closed_schema(tmp_path):
  result = _runner(tmp_path).run_case(_case(tmp_path))

  assert IntegrityEvalResult.from_dict(result.to_dict()) == result
  with pytest.raises(ValueError, match="unknown fields"):
    IntegrityEvalResult.from_dict({**result.to_dict(), "overall_score": 50})


def test_eval_result_rejects_rewritten_first_pass_chain(tmp_path):
  serialized = _runner(tmp_path).run_case(_case(tmp_path)).to_dict()
  serialized["repair_rounds"][0]["previous_integrity"] = (
      serialized["system_final"]["integrity"])

  with pytest.raises(ValueError, match="previous integrity"):
    IntegrityEvalResult.from_dict(serialized)


def test_eval_result_rejects_repair_cost_that_does_not_match_usage(tmp_path):
  serialized = _runner(tmp_path).run_case(_case(tmp_path)).to_dict()
  serialized["repair_cost"]["estimated_cost_usd"] = 99.0

  with pytest.raises(ValueError, match="repair_cost"):
    IntegrityEvalResult.from_dict(serialized)


def test_repair_round_retains_and_validates_reason_chain(tmp_path):
  serialized = _runner(tmp_path).run_case(_case(tmp_path)).to_dict()
  expected = list(dict.fromkeys(
      finding["reason_code"]
      for finding in serialized["repair_rounds"][0]["integrity"]["findings"]))

  assert serialized["repair_rounds"][0]["reason_codes"] == expected
  serialized["repair_rounds"][0]["reason_codes"] = []
  with pytest.raises(ValueError, match="reason_codes"):
    IntegrityEvalResult.from_dict(serialized)


def test_quality_failure_is_explicit_and_does_not_change_integrity(tmp_path):
  judge = RecordingJudge(fail_on="final synthesis 3\n")

  result = _runner(tmp_path, judge=judge).run_case(_case(tmp_path))

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


def test_scorecard_is_loaded_after_both_quality_judgments(tmp_path):
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

  assert result.robustness.expected_final_status == "invalid"
  assert result.robustness.expectation_met is True


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
      assert str(case.fixture_paths[0]) not in prompt
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
  assert ("--full-auto" in command) if provider == "codex" else (
      "--yolo" in command)


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
  serialized = _runner(tmp_path).run_case(_case(tmp_path)).to_dict()
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
