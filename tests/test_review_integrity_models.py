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


def test_critical_finding_forces_invalid_status():
  report = PassReport(
      integrity_score=97.0,
      findings=[Finding(
          reason_code="fabricated_quote",
          severity=Severity.CRITICAL,
          artifact="claims.json",
          message="quote does not authenticate",
      )],
      dimensions={},
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
      pass_report=PassReport(
          integrity_score=100.0,
          findings=[],
          dimensions={},
          manifest_sha256="b" * 64,
      ),
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
      name="citation_binding", score=80.0, findings=[finding])
  passed = PassReport(
      integrity_score=80.0,
      findings=[finding],
      dimensions={"citation_binding": dimension},
      manifest_sha256="c" * 64,
  )
  repair = RepairRecord(
      attempt=1,
      reason_codes=[ReasonCode.CITATION_AMBIGUOUS],
      action="disambiguate bibliography entry",
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
    DimensionResult(name="citation_binding", score=value, findings=[])
  with pytest.raises(ValueError, match="score"):
    IntegrityRunReport(
        pass_report=PassReport(
            integrity_score=100.0,
            findings=[],
            dimensions={},
            manifest_sha256="d" * 64,
        ),
        quality_score=value,
        repairs=[],
    )


@pytest.mark.parametrize("field, value", [
    ("schema_version", "2.0.0"),
    ("manifest_sha256", "not-a-sha256"),
])
def test_pass_report_rejects_invalid_wire_values(field, value):
  report = PassReport(
      integrity_score=100.0,
      findings=[],
      dimensions={},
      manifest_sha256="e" * 64,
  ).to_dict()
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
      name="citation_binding", score=100.0, findings=[])
  with pytest.raises(ValueError, match="duplicate dimension"):
    PassReport(
        integrity_score=100.0,
        findings=[],
        dimensions=[dimension, dimension],
        manifest_sha256="f" * 64,
    )


def test_dimensions_only_accept_the_six_stable_identifiers():
  with pytest.raises(ValueError, match="dimension"):
    DimensionResult(name="unsupported_dimension", score=100.0, findings=[])


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
