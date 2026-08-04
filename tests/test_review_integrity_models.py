import pathlib
import sys

import pytest


SCRIPTS = (pathlib.Path(__file__).resolve().parents[1]
           / "skills/literature-review/scripts")
sys.path.insert(0, str(SCRIPTS))

from review_integrity.models import (  # noqa: E402
    DimensionResult,
    Finding,
    IntegrityRunReport,
    IntegrityStatus,
    PassReport,
    ReasonCode,
    RepairRecord,
    Severity,
)


def _complete_dimension():
  return DimensionResult(
      name="citation_binding", score=100.0, applicable=True,
      evaluated_units=1, passed_units=1, nominal_weight=20.0,
      effective_weight=100.0, findings=[])


def test_critical_finding_forces_invalid_status():
  finding = Finding(
      reason_code="fabricated_quote",
      severity=Severity.CRITICAL,
      artifact="claims.json",
      message="quote does not authenticate",
  )
  dimension = _complete_dimension()
  dimension = DimensionResult(
      name=dimension.name, score=dimension.score,
      applicable=dimension.applicable,
      evaluated_units=dimension.evaluated_units,
      passed_units=dimension.passed_units,
      nominal_weight=dimension.nominal_weight,
      effective_weight=dimension.effective_weight,
      findings=[finding],
  )
  report = PassReport(
      integrity_score=100.0,
      findings=[finding],
      dimensions={"citation_binding": dimension},
      manifest_sha256="a" * 64,
  )
  assert report.status is IntegrityStatus.INVALID


def test_run_report_round_trips_without_unknown_fields():
  report = IntegrityRunReport.example_valid()
  assert IntegrityRunReport.from_dict(report.to_dict()) == report
  with pytest.raises(ValueError, match="unknown fields"):
    IntegrityRunReport.from_dict({**report.to_dict(), "gold_label": True})


def test_quality_score_is_none_without_a_quality_judge():
  report = IntegrityRunReport(
      pass_report=IntegrityRunReport.example_valid().pass_report,
      workspace_manifest_sha256="a" * 64,
      action="pass",
      quality_score=None,
      repairs=[],
  )
  assert report.to_dict()["quality_score"] is None
  assert IntegrityRunReport.from_dict(report.to_dict()).quality_score is None


def test_independent_models_round_trip_with_schema_versions():
  finding = Finding(
      reason_code=ReasonCode.CITATION_AMBIGUOUS,
      severity=Severity.WARNING,
      artifact="refs.json",
      message="citation resolves to multiple records",
  )
  dimension = DimensionResult(
      name="citation_binding", score=80.0, applicable=True,
      evaluated_units=5, passed_units=4, nominal_weight=20.0,
      effective_weight=100.0, findings=[finding])
  passed = PassReport(
      integrity_score=80.0,
      findings=[finding],
      dimensions={"citation_binding": dimension},
      manifest_sha256="c" * 64,
  )
  repair = RepairRecord(
      attempt=1,
      pass_report=passed,
      workspace_manifest_sha256="d" * 64,
      reason_codes=[ReasonCode.CITATION_AMBIGUOUS],
      action="pass",
      resolved=True,
  )
  for model_type, value in (
      (Finding, finding),
      (DimensionResult, dimension),
      (PassReport, passed),
      (RepairRecord, repair),
  ):
    serialized = value.to_dict()
    assert serialized["schema_version"] == "1.0.0"
    assert model_type.from_dict(serialized) == value


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, 100.1])
def test_scores_must_be_finite_and_within_0_to_100(value):
  with pytest.raises(ValueError, match="score"):
    DimensionResult(
        name="citation_binding", score=value, applicable=True,
        evaluated_units=1, passed_units=1, nominal_weight=20.0,
        effective_weight=100.0, findings=[])
  with pytest.raises(ValueError, match="score"):
    IntegrityRunReport(
        pass_report=IntegrityRunReport.example_valid().pass_report,
        workspace_manifest_sha256="a" * 64,
        action="pass",
        quality_score=value,
        repairs=[],
    )


@pytest.mark.parametrize("field, value", [
    ("schema_version", "2.0.0"),
    ("manifest_sha256", "not-a-sha256"),
])
def test_pass_report_rejects_invalid_wire_values(field, value):
  report = IntegrityRunReport.example_valid().pass_report.to_dict()
  report[field] = value
  with pytest.raises(ValueError):
    PassReport.from_dict(report)


def test_rejects_unknown_reason_codes_and_duplicate_dimension_names():
  with pytest.raises(ValueError, match="reason_code"):
    Finding(
        reason_code="invented_reason",
        severity=Severity.WARNING,
        artifact="claims.json",
        message="not in the public allowlist",
    )
  dimension = DimensionResult(
      name="citation_binding", score=100.0, applicable=True,
      evaluated_units=1, passed_units=1, nominal_weight=20.0,
      effective_weight=100.0, findings=[])
  with pytest.raises(ValueError, match="duplicate dimension"):
    PassReport(
        integrity_score=100.0,
        findings=[],
        dimensions=[dimension, dimension],
        manifest_sha256="f" * 64,
    )


def test_dimensions_only_accept_the_six_stable_identifiers():
  with pytest.raises(ValueError, match="dimension"):
    DimensionResult(
        name="unsupported_dimension", score=100.0, applicable=True,
        evaluated_units=1, passed_units=1, nominal_weight=20.0,
        effective_weight=100.0, findings=[])


@pytest.mark.parametrize("overrides", [
    {"score": None, "applicable": True},
    {"score": 0.0, "applicable": False},
    {"score": None, "applicable": False, "evaluated_units": 1},
    {"score": 50.0, "evaluated_units": 3, "passed_units": 1},
    {"score": 100.0, "passed_units": 2},
    {"nominal_weight": 25.0},
])
def test_dimension_rejects_inconsistent_counts_applicability_and_weights(
    overrides,
):
  values = {
      "name": "citation_binding", "score": 100.0, "applicable": True,
      "evaluated_units": 1, "passed_units": 1, "nominal_weight": 20.0,
      "effective_weight": 100.0, "findings": [],
  }
  values.update(overrides)
  with pytest.raises(ValueError):
    DimensionResult(**values)


def test_not_applicable_dimension_round_trips_with_null_score():
  dimension = DimensionResult(
      name="quantitative_grounding", score=None, applicable=False,
      evaluated_units=0, passed_units=0, nominal_weight=20.0,
      effective_weight=0.0, findings=[])

  assert dimension.to_dict()["score"] is None
  assert DimensionResult.from_dict(dimension.to_dict()) == dimension


def test_finding_context_is_recursively_immutable_and_round_trips():
  finding = Finding(
      reason_code=ReasonCode.CLAIM_NEEDS_REVIEW,
      severity=Severity.WARNING,
      artifact="claims.json",
      message="claim requires review",
      context={"claim_index": 2, "anchors": {"missing": ["18"]}},
  )

  assert finding.to_dict()["context"] == {
      "claim_index": 2, "anchors": {"missing": ["18"]}}
  assert Finding.from_dict(finding.to_dict()) == finding
  with pytest.raises(TypeError):
    finding.context["claim_index"] = 3
  with pytest.raises(TypeError):
    finding.context["anchors"]["missing"] = ()


@pytest.mark.parametrize("context", [
    {1: "non-string key"},
    {"value": float("nan")},
    {"value": float("inf")},
    {"value": {"unsupported"}},
])
def test_finding_context_rejects_non_json_safe_values(context):
  with pytest.raises(ValueError, match="context"):
    Finding(
        reason_code=ReasonCode.CLAIM_NEEDS_REVIEW,
        severity=Severity.WARNING,
        artifact="claims.json",
        message="claim requires review",
        context=context,
    )


def test_pass_report_rejects_zero_applicable_dimensions():
  with pytest.raises(ValueError, match="applicable|denominator"):
    PassReport(
        integrity_score=100.0,
        findings=[],
        dimensions={},
        manifest_sha256="9" * 64,
    )


def test_pass_report_rejects_forged_wire_with_no_applicable_dimension():
  report = IntegrityRunReport.example_valid().pass_report.to_dict()
  for dimension in report["dimensions"].values():
    dimension.update({
        "score": None,
        "applicable": False,
        "evaluated_units": 0,
        "passed_units": 0,
        "effective_weight": 0.0,
    })
  report["integrity_score"] = 100.0

  with pytest.raises(ValueError, match="applicable|denominator"):
    PassReport.from_dict(report)
