import json
import pathlib
import sys
from types import SimpleNamespace

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
_PROVENANCE = {
    "target_commit": None, "target_dirty": None, "engine_version": "1.0.0",
    "validator_versions": {"claims": "1.0.0"},
}
ATTACKS = (
    EVALS / "test-cases/literature-review-integrity/synthetic-attacks")
SCRIPTS = ROOT / "skills/literature-review/scripts"
sys.path.insert(0, str(EVALS))
sys.path.insert(0, str(SCRIPTS))

from lib import literature_integrity  # noqa: E402
from lib.literature_integrity import load_cases  # noqa: E402
from lib.literature_integrity import (  # noqa: E402
    AdversarialCaseScore,
    IntegrityEvalResult,
    ModelUsage,
    QualityResult,
    ReasonMetric,
    RepairCost,
    RobustnessResult,
    SnapshotEvaluation,
)
from lib.run_reports import (  # noqa: E402
    CombinedCaseResult,
    CombinedRunResult,
    load_dashboard_data,
    write_run_report,
)
from review_integrity.models import IntegrityRunReport  # noqa: E402
from review_integrity.models import ReasonCode  # noqa: E402
from review_integrity.validators import validate_snapshot  # noqa: E402
from review_integrity.workspace import (  # noqa: E402
    WorkspaceError,
    load_workspace,
)


ATTACK_EXPECTATIONS = (
    ("integrity-case-001", "unicode-substitution",
     ReasonCode.FABRICATED_QUOTE, None),
    ("integrity-case-002", "negation-deletion",
     ReasonCode.FABRICATED_QUOTE, None),
    ("integrity-case-003", "stitched-quote",
     ReasonCode.FABRICATED_QUOTE, None),
    ("integrity-case-004", "wrong-source",
     ReasonCode.CITATION_IDENTITY_MISMATCH, None),
    ("integrity-case-005", "ambiguous-title",
     ReasonCode.CITATION_AMBIGUOUS, None),
    ("integrity-case-006", "compound-name",
     ReasonCode.CITATION_IDENTITY_MISMATCH, None),
    ("integrity-case-007", "added-number",
     ReasonCode.COVERAGE_NUMBER_MISSING, None),
    ("integrity-case-008", "altered-number",
     ReasonCode.COVERAGE_NUMBER_MISSING, None),
    ("integrity-case-009", "background-role",
     ReasonCode.COVERAGE_ROLE_INVALID, None),
    ("integrity-case-010", "missing-artifact",
     ReasonCode.ARTIFACT_MISSING, "missing"),
    ("integrity-case-011", "malformed-artifact",
     ReasonCode.ARTIFACT_MALFORMED, "malformed"),
    ("integrity-case-012", "symlink",
     ReasonCode.ARTIFACT_SYMLINK, "symlink"),
    ("integrity-case-013", "traversal",
     ReasonCode.ARTIFACT_TRAVERSAL, "traversal"),
)

FAMILY_NAMES = {family for _case, family, _reason, _mutation
                in ATTACK_EXPECTATIONS}


def _scenario(case_id):
  return json.loads((ATTACKS / case_id / "input.json").read_text())


def _write_workspace(root, scenario):
  payloads = {
      "project.json": {"project": "invented-integrity-attack"},
      "protocol.md": "# Synthetic protocol\n",
      "corpus.json": scenario["corpus"],
      "claims.json": scenario["claims"],
      "synthesis.md": scenario["synthesis"],
      "refs.json": scenario["references"],
  }
  for paper_id, source in scenario["sources"].items():
    payloads[f"papers/{paper_id}/fulltext.md"] = source
  for relative, value in payloads.items():
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
      path.write_text(value, encoding="utf-8")
    else:
      path.write_text(json.dumps(value), encoding="utf-8")


def test_public_attack_case_definitions_cover_every_family_once():
  cases = load_cases(ATTACKS)

  assert {case.case_id for case in cases} == {
      case for case, _family, _reason, _mutation in ATTACK_EXPECTATIONS}
  for case in cases:
    public = json.loads((ATTACKS / case.case_id / "case.json").read_text())
    assert set(public) - {"workspace_tamper"} == {
        "schema_version", "capability", "case_id", "prompt", "domain",
        "fixture_paths", "quality_rubric_id",
    }
    assert public["fixture_paths"] == ["input.json"]
    public_reachable = "\n".join((
        case.case_id, case.prompt, case.domain,
        *(fixture.relative_path.as_posix()
          for fixture in case.fixture_files))).casefold()
    assert not FAMILY_NAMES & {
        family for family in FAMILY_NAMES if family in public_reachable}

  all_cases = load_cases(ATTACKS.parent)
  assert {case for case, _family, _reason, _mutation in ATTACK_EXPECTATIONS} < {
      case.case_id for case in all_cases}


class _ScenarioExecutor:
  def __init__(self):
    self.feedback = []

  @staticmethod
  def _usage():
    return ModelUsage(
        duration_seconds=0.0, input_tokens=0, output_tokens=0,
        estimated_cost_usd=0.0, executor_version="scenario-v1",
        prompt_version="scenario-v1", prompt_sha256="b" * 64)

  def first_pass(self, case, workspace):
    scenario = json.loads(case.fixture_files[0].content.decode("utf-8"))
    _write_workspace(workspace, scenario)
    return self._usage()

  def repair(self, feedback, workspace):
    self.feedback.append(feedback)
    return self._usage()


class _ScenarioJudge:
  def __init__(self):
    self.calls = []

  def score(self, case, synthesis):
    self.calls.append((case, synthesis))
    return QualityResult(
        quality_score=50.0,
        scores={name: 50.0 for name in (
            "research-quality", "analytical-quality", "output-structure")},
        error=None)


@pytest.mark.parametrize(
    ("case_id", "family", "reason_code", "mutation"), ATTACK_EXPECTATIONS)
def test_critical_attack_is_detected_at_its_expected_unit(
    tmp_path, case_id, family, reason_code, mutation,
):
  case = next(item for item in load_cases(ATTACKS) if item.case_id == case_id)
  executor = _ScenarioExecutor()
  judge = _ScenarioJudge()
  runner = literature_integrity.LiteratureIntegrityRunner(
      executor, judge, workspace_parent=tmp_path / "workspaces",
      scorecard_directory=ATTACKS)

  result = runner.run_case(case)
  expectation = json.loads(
      (ATTACKS / case_id / "expected.json").read_text())["reason_expectations"][0]
  if mutation in {"missing", "symlink", "traversal"}:
    serialized = result.to_dict()
    failure = serialized["operational_failure"]
    assert failure["reason_code"] == reason_code.value
    assert failure["artifact"] == expectation["unit"]["artifact"]
    assert failure["status"] == "invalid"
    assert failure["workspace_manifest_sha256"] is None
    assert failure["quality"] is None
    assert judge.calls == []
    assert executor.feedback == []
    return

  findings = result.model_first_pass.integrity.findings
  matches = [
      finding for finding in findings
      if finding.reason_code is reason_code
      and finding.artifact == expectation["unit"]["artifact"]
      and (
          expectation["unit"]["context_key"] is None
          or finding.context.get(expectation["unit"]["context_key"])
          == expectation["unit"]["context_value"])
  ]
  assert len(matches) == 1


def test_repair_operational_failure_keeps_latest_trusted_findings(tmp_path):
  case = next(
      item for item in load_cases(ATTACKS)
      if item.case_id == "integrity-case-001")

  class SymlinkRepairExecutor(_ScenarioExecutor):
    def repair(self, feedback, workspace):
      self.feedback.append(feedback)
      literature_integrity.apply_workspace_tamper("symlink", workspace)
      return self._usage()

  result = literature_integrity.LiteratureIntegrityRunner(
      SymlinkRepairExecutor(), _ScenarioJudge(),
      workspace_parent=tmp_path / "workspaces",
      scorecard_directory=ATTACKS).run_case(case)
  score = literature_integrity.load_adversarial_scores(
      ATTACKS, {case.case_id: result}, domains={case.case_id: "synthetic"})[case.case_id]

  assert result.operational_failure.phase == "repair_load"
  assert dict(score.confusion) == {
      "true_positive": 1, "false_positive": 2,
      "true_negative": 1, "false_negative": 0}
  assert score.reason_metrics["fabricated_quote"].true_positive == 1
  assert score.reason_metrics["artifact_symlink"].false_positive == 1


@pytest.mark.parametrize(
    "case_id", [case for case, _family, _reason, _mutation
                in ATTACK_EXPECTATIONS[:9]])
def test_authentic_control_matches_attack_length_and_structure(case_id):
  scenario = _scenario(case_id)
  attacked, control = scenario["claims"][:2]
  attacked_source = scenario["sources"][attacked["paper_id"]]
  control_source = scenario["sources"][control["paper_id"]]

  assert abs(len(attacked_source) - len(control_source)) <= 4
  assert abs(len(attacked["supporting_quote"])
             - len(control["supporting_quote"])) <= 4
  assert attacked_source.count(".") == control_source.count(".")
  assert attacked["supporting_quote"].count(".") == (
      control["supporting_quote"].count("."))
  assert type(attacked["citation"]) is type(control["citation"])


@pytest.mark.parametrize(
    ("case_id", "mutation", "control_artifact"), [
        ("integrity-case-010", "missing", "claims.json"),
        ("integrity-case-011", "malformed", "refs.json"),
        ("integrity-case-012", "symlink", "refs.json"),
        ("integrity-case-013", "traversal", "refs.json"),
    ])
def test_operational_attack_has_a_matched_valid_artifact_control(
    tmp_path, case_id, mutation, control_artifact,
):
  scenario = _scenario(case_id)
  workspace = tmp_path / case_id
  _write_workspace(workspace, scenario)
  literature_integrity.apply_workspace_tamper(mutation, workspace)

  control = workspace / control_artifact
  assert control.is_file() and not control.is_symlink()
  json.loads(control.read_text(encoding="utf-8"))
  expected = json.loads((ATTACKS / case_id / "expected.json").read_text())
  negative = [item for item in expected["reason_expectations"]
              if item["present"] is False]
  assert len(negative) == 1
  assert negative[0]["unit"] == {
      "artifact": control_artifact,
      "context_key": None,
      "context_value": None,
  }


@pytest.mark.parametrize(
    ("case_id", "mutation", "false_positives"), [
        ("integrity-case-010", "missing", 0),
        ("integrity-case-011", "malformed", 1),
        ("integrity-case-012", "symlink", 0),
        ("integrity-case-013", "traversal", 0),
    ])
def test_operational_controls_contribute_true_negatives(
    tmp_path, case_id, mutation, false_positives,
):
  case = next(item for item in load_cases(ATTACKS) if item.case_id == case_id)
  result = literature_integrity.LiteratureIntegrityRunner(
      _ScenarioExecutor(), _ScenarioJudge(),
      workspace_parent=tmp_path / "workspaces",
      scorecard_directory=ATTACKS).run_case(case)

  score = literature_integrity.load_adversarial_scores(
      ATTACKS, {case_id: result}, domains={case_id: "synthetic"})[case_id]
  assert dict(score.confusion) == {
      "true_positive": 1, "false_positive": false_positives,
      "true_negative": 1, "false_negative": 0,
  }


def test_ambiguous_title_control_matches_reference_binding_structure():
  scenario = _scenario("integrity-case-005")

  assert [set(reference) for reference in scenario["references"]] == [
      {"title"}, {"title"}]
  assert [claim["citation"] for claim in scenario["claims"]] == ["[1]", "[2]"]


def test_scorer_produces_per_family_confusion_and_reason_metrics(tmp_path):
  load_adversarial_scores = getattr(
      literature_integrity, "load_adversarial_scores", None)
  assert callable(load_adversarial_scores), (
      "the scorer must expose post-run adversarial scoring")
  scorecards = tmp_path / "scorecards"
  scorecards.mkdir()
  expected = {
      "schema_version": "1.0.0",
      "final_status": "invalid",
      "minimum_repair_rounds": 0,
      "maximum_repair_rounds": 3,
      "attack_family": "unicode-substitution",
      "reason_expectations": [
          {
              "reason_code": "fabricated_quote", "present": True,
              "unit": {"artifact": "claims.json",
                       "context_key": "result_index", "context_value": 0},
          },
          {
              "reason_code": "fabricated_quote", "present": False,
              "unit": {"artifact": "claims.json",
                       "context_key": "result_index", "context_value": 1},
          },
      ],
  }
  case_dir = scorecards / "unicode-substitution"
  case_dir.mkdir()
  (case_dir / "expected.json").write_text(json.dumps(expected))
  observed = [{
      "schema_version": "1.0.0", "reason_code": "fabricated_quote",
      "severity": "critical", "artifact": "claims.json", "message": "x",
      "context": {"result_index": 0},
  }]

  scores = load_adversarial_scores(
      scorecards, {"unicode-substitution": observed}, domains={"unicode-substitution": "synthetic"})
  score = scores["unicode-substitution"]

  assert score.attack_family == "unicode-substitution"
  assert dict(score.confusion) == {
      "true_positive": 1, "false_positive": 0,
      "true_negative": 1, "false_negative": 0,
  }
  assert score.reason_metrics["fabricated_quote"].precision == 1.0
  assert score.reason_metrics["fabricated_quote"].recall == 1.0
  assert score.reason_metrics["fabricated_quote"].true_negative == 1


def _write_adversarial_scorecard(root, expectations):
  case_dir = root / "integrity-case-900"
  case_dir.mkdir(parents=True)
  (case_dir / "expected.json").write_text(json.dumps({
      "schema_version": "1.0.0", "final_status": "invalid",
      "minimum_repair_rounds": 0, "maximum_repair_rounds": 3,
      "attack_family": "unicode-substitution",
      "reason_expectations": expectations,
  }))


def _finding(reason, artifact, **context):
  return {
      "schema_version": "1.0.0", "reason_code": reason,
      "severity": "critical", "artifact": artifact, "message": "observed",
      "context": context,
  }


def test_scorer_matches_one_to_one_and_counts_duplicates_and_extras(tmp_path):
  _write_adversarial_scorecard(tmp_path, [
      {"reason_code": "fabricated_quote", "present": True,
       "unit": {"artifact": "claims.json", "context_key": "result_index",
                "context_value": 0}},
      {"reason_code": "fabricated_quote", "present": False,
       "unit": {"artifact": "claims.json", "context_key": "result_index",
                "context_value": 1}},
  ])
  observed = [
      _finding("fabricated_quote", "claims.json", result_index=0),
      _finding("fabricated_quote", "claims.json", result_index=0),
      _finding("fabricated_quote", "claims.json", result_index=1),
      _finding("citation_ambiguous", "claims.json", result_index=7),
  ]

  score = literature_integrity.load_adversarial_scores(
      tmp_path, {"integrity-case-900": observed}, domains={"integrity-case-900": "synthetic"})["integrity-case-900"]

  assert dict(score.confusion) == {
      "true_positive": 1, "false_positive": 3,
      "true_negative": 0, "false_negative": 0}
  assert score.reason_metrics["fabricated_quote"] == ReasonMetric(1, 2, 0, 0)
  assert score.reason_metrics["citation_ambiguous"] == ReasonMetric(0, 1, 0, 0)


def test_scorer_rejects_contradictory_expectations_for_the_same_unit(tmp_path):
  unit = {"artifact": "claims.json", "context_key": "result_index",
          "context_value": 0}
  _write_adversarial_scorecard(tmp_path, [
      {"reason_code": "fabricated_quote", "present": True, "unit": unit},
      {"reason_code": "fabricated_quote", "present": False, "unit": unit},
  ])

  with pytest.raises(ValueError, match="duplicate|contradictory"):
    literature_integrity.load_adversarial_scores(
        tmp_path, {"integrity-case-900": []}, domains={"integrity-case-900": "synthetic"})


@pytest.mark.parametrize(("expectations", "confusion", "precision", "recall"), [
    ([{"reason_code": "fabricated_quote", "present": True,
       "unit": {"artifact": "claims.json", "context_key": "result_index",
                "context_value": 0}}],
     {"true_positive": 0, "false_positive": 0,
      "true_negative": 0, "false_negative": 1}, None, 0.0),
    ([{"reason_code": "fabricated_quote", "present": False,
       "unit": {"artifact": "claims.json", "context_key": "result_index",
                "context_value": 1}}],
     {"true_positive": 0, "false_positive": 0,
      "true_negative": 1, "false_negative": 0}, None, None),
])
def test_scorer_has_explicit_zero_denominator_behavior(
    tmp_path, expectations, confusion, precision, recall,
):
  _write_adversarial_scorecard(tmp_path, expectations)

  score = literature_integrity.load_adversarial_scores(
      tmp_path, {"integrity-case-900": []}, domains={"integrity-case-900": "synthetic"})["integrity-case-900"]
  metric = score.reason_metrics["fabricated_quote"]

  assert dict(score.confusion) == confusion
  assert metric.precision is precision
  assert metric.recall == recall
  assert metric.true_negative == confusion["true_negative"]


def _valid_evaluation():
  integrity = IntegrityRunReport.example_valid().pass_report
  usage = ModelUsage(
      duration_seconds=1.0, input_tokens=10, output_tokens=20,
      estimated_cost_usd=0.01, executor_version="test-v1",
      prompt_version="test-v1", prompt_sha256="a" * 64)
  snapshot = SnapshotEvaluation(
      workspace_manifest_sha256=integrity.manifest_sha256,
      quality=QualityResult(
          quality_score=80.0,
          scores={name: 80.0 for name in (
              "research-quality", "analytical-quality", "output-structure")},
          error=None),
      integrity=integrity, model_usage=usage)
  return IntegrityEvalResult(
      model_first_pass=snapshot, repair_rounds=(), system_final=snapshot,
      repair_cost=RepairCost.from_rounds(()),
      robustness=RobustnessResult(
          expected_final_status="valid", observed_final_status="valid",
          minimum_repair_rounds=0, maximum_repair_rounds=0,
          expectation_met=True, error=None))


def test_task9_aggregates_count_only_attack_and_reason_metrics(tmp_path):
  first = AdversarialCaseScore(
      attack_family="unicode-substitution",
      domain="synthetic",
      confusion={
          "true_positive": 1, "false_positive": 0,
          "true_negative": 1, "false_negative": 0},
      reason_metrics={
          "fabricated_quote": ReasonMetric(1, 0, 1, 0)},
  )
  second = AdversarialCaseScore(
      attack_family="unicode-substitution",
      domain="synthetic",
      confusion={
          "true_positive": 0, "false_positive": 1,
          "true_negative": 0, "false_negative": 1},
      reason_metrics={
          "fabricated_quote": ReasonMetric(0, 1, 0, 1)},
  )
  run = CombinedRunResult(
      run_id="run-attack-metrics", timestamp="2026-08-04T12:00:00Z",
      model="codex:test",
      provenance=_PROVENANCE, cases=(
          CombinedCaseResult(
              case_id="attack-one", evaluation=_valid_evaluation(),
              adversarial_score=first),
          CombinedCaseResult(
              case_id="attack-two", evaluation=_valid_evaluation(),
              adversarial_score=second),
      ))

  write_run_report(run, tmp_path)
  report = load_dashboard_data(tmp_path, "run-attack-metrics")

  assert report["summary"]["attack_family_confusion"] == {
      "unicode-substitution": ReasonMetric(1, 1, 1, 1).to_dict()}
  assert report["summary"]["reason_code_metrics"] == {
      "fabricated_quote": {
          "true_positive": 1, "false_positive": 1, "true_negative": 1,
          "false_negative": 1,
          "precision": 0.5, "recall": 0.5, "specificity": 0.5}}
  serialized = json.dumps(report)
  assert "reason_expectations" not in serialized
  assert "context_value" not in serialized


def test_count_only_adversarial_schema_rejects_unknown_and_forged_metrics():
  score = AdversarialCaseScore(
      attack_family="unicode-substitution",
      domain="synthetic",
      confusion={
          "true_positive": 1, "false_positive": 0,
          "true_negative": 1, "false_negative": 0},
      reason_metrics={
          "fabricated_quote": ReasonMetric(1, 0, 1, 0)},
  ).to_dict()
  with_unknown = {**score, "gold": "must not enter count output"}

  with pytest.raises(ValueError, match="unknown fields"):
    AdversarialCaseScore.from_dict(with_unknown)

  score["reason_metrics"]["fabricated_quote"]["precision"] = 0.0
  with pytest.raises(ValueError, match="rates"):
    AdversarialCaseScore.from_dict(score)


def test_adversarial_schema_rejects_confusion_that_disagrees_with_reasons():
  with pytest.raises(ValueError, match="reconcile|confusion"):
    AdversarialCaseScore(
        attack_family="unicode-substitution",
        domain="synthetic",
        confusion={
            "true_positive": 2, "false_positive": 0,
            "true_negative": 0, "false_negative": 0},
        reason_metrics={"fabricated_quote": ReasonMetric(1, 0, 0, 0)})


def test_adversarial_schema_rejects_forged_true_negative_count():
  with pytest.raises(ValueError, match="reconcile|confusion"):
    AdversarialCaseScore(
        attack_family="unicode-substitution",
        domain="synthetic",
        confusion={
            "true_positive": 1, "false_positive": 0,
            "true_negative": 1, "false_negative": 0},
        reason_metrics={"fabricated_quote": {
            "true_positive": 1, "false_positive": 0,
            "true_negative": 0, "false_negative": 0,
            "precision": 1.0, "recall": 1.0, "specificity": None}})


def test_adversarial_v1_wire_artifact_is_explicitly_rejected():
  with pytest.raises(ValueError, match="schema_version"):
    AdversarialCaseScore.from_dict({
        "schema_version": "1.0.0",
        "attack_family": "unicode-substitution",
        "domain": "synthetic",
        "confusion": {
            "true_positive": 1, "false_positive": 0,
            "true_negative": 0, "false_negative": 0},
        "reason_metrics": {"fabricated_quote": {
            "true_positive": 1, "false_positive": 0,
            "true_negative": 0, "false_negative": 0,
            "precision": 1.0, "recall": 1.0}},
    })


@pytest.mark.parametrize(("counts", "specificity"), [
    ((1, 1, 3, 0), 0.75),
    ((1, 0, 0, 0), None),
])
def test_reason_metric_reports_specificity(counts, specificity):
  metric = ReasonMetric(*counts)

  assert metric.specificity == specificity
  assert metric.to_dict()["specificity"] == specificity
  assert ReasonMetric.from_dict(metric.to_dict()) == metric


def test_reason_metric_rejects_forged_specificity():
  forged = {**ReasonMetric(1, 1, 3, 0).to_dict(), "specificity": 1.0}

  with pytest.raises(ValueError, match="rates"):
    ReasonMetric.from_dict(forged)


def test_scorer_records_case_domain(tmp_path):
  _write_adversarial_scorecard(tmp_path, [
      {"reason_code": "fabricated_quote", "present": True,
       "unit": {"artifact": "claims.json", "context_key": "result_index",
                "context_value": 0}}])

  score = literature_integrity.load_adversarial_scores(
      tmp_path, {"integrity-case-900": []},
      domains={"integrity-case-900": "clinical"})["integrity-case-900"]

  assert score.domain == "clinical"
  assert AdversarialCaseScore.from_dict(score.to_dict()) == score


def test_scorer_requires_a_domain_for_every_scored_case(tmp_path):
  _write_adversarial_scorecard(tmp_path, [
      {"reason_code": "fabricated_quote", "present": True,
       "unit": {"artifact": "claims.json", "context_key": "result_index",
                "context_value": 0}}])

  with pytest.raises(ValueError, match="domain"):
    literature_integrity.load_adversarial_scores(
        tmp_path, {"integrity-case-900": []}, domains={})


_OPERATIONAL_TAMPERS = {
    "integrity-case-010": "missing", "integrity-case-011": "malformed",
    "integrity-case-012": "symlink", "integrity-case-013": "traversal",
}


def test_operational_cases_declare_a_public_workspace_tamper():
  cases = {case.case_id: case for case in load_cases(ATTACKS)}

  assert {case_id: case.workspace_tamper
          for case_id, case in cases.items()
          if case.workspace_tamper is not None} == _OPERATIONAL_TAMPERS


@pytest.mark.parametrize("case_id", [
    "integrity-case-010", "integrity-case-012", "integrity-case-013"])
def test_unloadable_tamper_cases_expect_fail_closed_invalid(case_id):
  expected = json.loads((ATTACKS / case_id / "expected.json").read_text())

  assert expected["final_status"] == "invalid"
  assert expected["minimum_repair_rounds"] == 0
  assert expected["maximum_repair_rounds"] == 0


def test_case_loader_rejects_unknown_workspace_tamper(tmp_path):
  case_dir = tmp_path / "integrity-case-900"
  case_dir.mkdir()
  (case_dir / "input.json").write_text("{}")
  (case_dir / "case.json").write_text(json.dumps({
      "schema_version": "1.0.0", "capability": "literature-review-integrity",
      "case_id": "integrity-case-900", "prompt": "Build it.",
      "domain": "synthetic", "fixture_paths": ["input.json"],
      "quality_rubric_id": "literature-review-v1",
      "workspace_tamper": "delete-everything",
  }))

  with pytest.raises(ValueError, match="workspace_tamper"):
    load_cases(tmp_path)


@pytest.mark.parametrize("tamper", sorted(set(_OPERATIONAL_TAMPERS.values())))
def test_capture_prompt_never_reveals_the_workspace_tamper(
    monkeypatch, tmp_path, tamper,
):
  case_id = next(key for key, value in _OPERATIONAL_TAMPERS.items()
                 if value == tamper)
  case = next(item for item in load_cases(ATTACKS) if item.case_id == case_id)
  calls = []
  monkeypatch.setattr(
      literature_integrity, "find_cli",
      lambda provider: pathlib.Path(f"/fake/{provider}"))
  monkeypatch.setattr(
      literature_integrity.subprocess, "run",
      lambda command, **kwargs: calls.append(command) or SimpleNamespace(
          returncode=0, stdout="", stderr=""))
  workspace = tmp_path / "workspace"
  workspace.mkdir()

  literature_integrity.ProductionModelExecutor("claude", ROOT).first_pass(
      case, workspace)

  prompt = calls[0][calls[0].index("-p") + 1]
  assert "workspace_tamper" not in prompt
  assert tamper not in prompt
