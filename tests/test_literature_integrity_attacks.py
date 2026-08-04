import json
import pathlib
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
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
    ("unicode-substitution", ReasonCode.FABRICATED_QUOTE),
    ("negation-deletion", ReasonCode.FABRICATED_QUOTE),
    ("stitched-quote", ReasonCode.FABRICATED_QUOTE),
    ("wrong-source", ReasonCode.CITATION_IDENTITY_MISMATCH),
    ("ambiguous-title", ReasonCode.CITATION_AMBIGUOUS),
    ("compound-name", ReasonCode.CITATION_IDENTITY_MISMATCH),
    ("added-number", ReasonCode.COVERAGE_NUMBER_MISSING),
    ("altered-number", ReasonCode.COVERAGE_NUMBER_MISSING),
    ("background-role", ReasonCode.COVERAGE_ROLE_INVALID),
    ("missing-artifact", ReasonCode.ARTIFACT_MISSING),
    ("malformed-artifact", ReasonCode.ARTIFACT_MALFORMED),
    ("symlink", ReasonCode.ARTIFACT_SYMLINK),
    ("traversal", ReasonCode.ARTIFACT_TRAVERSAL),
)


def _scenario(case_id):
  return json.loads((ATTACKS / case_id / "scenario.json").read_text())


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


def _artifact_failure(case_id, root):
  if case_id == "missing-artifact":
    (root / "refs.json").unlink()
  elif case_id == "malformed-artifact":
    (root / "claims.json").write_text("{not-json", encoding="utf-8")
  elif case_id == "symlink":
    outside = root.parent / "outside-claims.json"
    outside.write_text("[]", encoding="utf-8")
    (root / "claims.json").unlink()
    (root / "claims.json").symlink_to(outside)
  elif case_id == "traversal":
    (root / "project.json").unlink()
    artifacts = [
        "protocol.md", "corpus.json", "claims.json", "synthesis.md",
        "refs.json", *(
            f"papers/{paper_id}/fulltext.md"
            for paper_id in _scenario(case_id)["sources"]),
        "../outside.json",
    ]
    (root / "run-manifest.json").write_text(json.dumps({
        "schema_version": "1.0.0", "artifacts": artifacts,
    }), encoding="utf-8")


def test_public_attack_case_definitions_cover_every_family_once():
  cases = load_cases(ATTACKS)

  assert {case.case_id for case in cases} == {
      case for case, _reason in ATTACK_EXPECTATIONS}
  for case in cases:
    public = json.loads((ATTACKS / case.case_id / "case.json").read_text())
    assert set(public) == {
        "schema_version", "capability", "case_id", "prompt", "domain",
        "fixture_paths", "quality_rubric_id",
    }

  all_cases = load_cases(ATTACKS.parent)
  assert {case for case, _reason in ATTACK_EXPECTATIONS} < {
      case.case_id for case in all_cases}


@pytest.mark.parametrize(("case_id", "reason_code"), ATTACK_EXPECTATIONS)
def test_critical_attack_is_detected_at_its_expected_unit(
    tmp_path, case_id, reason_code,
):
  root = tmp_path / case_id
  _write_workspace(root, _scenario(case_id))

  if case_id in {"missing-artifact", "symlink", "traversal"}:
    authentic = load_workspace(root)
    assert authentic.manifest_sha256
    _artifact_failure(case_id, root)
    with pytest.raises(WorkspaceError) as captured:
      load_workspace(root)
    assert captured.value.reason_code is reason_code
    return

  if case_id == "malformed-artifact":
    authentic = load_workspace(root)
    assert authentic.manifest_sha256
    _artifact_failure(case_id, root)
    findings = validate_snapshot(load_workspace(root))
    matches = [
        finding for finding in findings
        if finding.reason_code is reason_code
        and finding.artifact == "claims.json"]
    assert len(matches) == 1
    return

  findings = validate_snapshot(load_workspace(root))
  expectation = json.loads(
      (ATTACKS / case_id / "expected.json").read_text())["reason_expectations"][0]
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


@pytest.mark.parametrize(
    "case_id", [case for case, _reason in ATTACK_EXPECTATIONS[:9]])
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
      scorecards, {"unicode-substitution": observed})
  score = scores["unicode-substitution"]

  assert score.attack_family == "unicode-substitution"
  assert dict(score.confusion) == {
      "true_positive": 1, "false_positive": 0,
      "true_negative": 1, "false_negative": 0,
  }
  assert score.reason_metrics["fabricated_quote"].precision == 1.0
  assert score.reason_metrics["fabricated_quote"].recall == 1.0


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
      confusion={
          "true_positive": 1, "false_positive": 0,
          "true_negative": 1, "false_negative": 0},
      reason_metrics={
          "fabricated_quote": ReasonMetric(1, 0, 0)},
  )
  second = AdversarialCaseScore(
      attack_family="unicode-substitution",
      confusion={
          "true_positive": 0, "false_positive": 1,
          "true_negative": 0, "false_negative": 1},
      reason_metrics={
          "fabricated_quote": ReasonMetric(0, 1, 1)},
  )
  run = CombinedRunResult(
      run_id="run-attack-metrics", timestamp="2026-08-04T12:00:00Z",
      model="codex:test", cases=(
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
      "unicode-substitution": {
          "true_positive": 1, "false_positive": 1,
          "true_negative": 1, "false_negative": 1}}
  assert report["summary"]["reason_code_metrics"] == {
      "fabricated_quote": {
          "true_positive": 1, "false_positive": 1, "false_negative": 1,
          "precision": 0.5, "recall": 0.5}}
  serialized = json.dumps(report)
  assert "reason_expectations" not in serialized
  assert "context_value" not in serialized


def test_count_only_adversarial_schema_rejects_unknown_and_forged_metrics():
  score = AdversarialCaseScore(
      attack_family="unicode-substitution",
      confusion={
          "true_positive": 1, "false_positive": 0,
          "true_negative": 1, "false_negative": 0},
      reason_metrics={
          "fabricated_quote": ReasonMetric(1, 0, 0)},
  ).to_dict()
  with_unknown = {**score, "gold": "must not enter count output"}

  with pytest.raises(ValueError, match="unknown fields"):
    AdversarialCaseScore.from_dict(with_unknown)

  score["reason_metrics"]["fabricated_quote"]["precision"] = 0.0
  with pytest.raises(ValueError, match="rates"):
    AdversarialCaseScore.from_dict(score)
