import json
import pathlib
import sys

import pytest


SCRIPTS = (pathlib.Path(__file__).resolve().parents[1]
           / "skills/literature-review/scripts")
sys.path.insert(0, str(SCRIPTS))

import check_claims  # noqa: E402
from review_integrity.models import (  # noqa: E402
    Finding,
    IntegrityStatus,
    PassReport,
    ReasonCode,
    Severity,
)
from review_integrity.scoring import score_integrity  # noqa: E402
from review_integrity.workspace import load_workspace  # noqa: E402


def _claim(*, claim=None, paper_id="p1", citation="Patel, 2022",
           quote=None):
  text = claim or "Readmissions fell 18% in the treatment arm."
  return {
      "claim": text,
      "paper_id": paper_id,
      "citation": citation,
      "supporting_quote": quote or (
          "Thirty-day readmissions fell 18% in the treatment arm relative "
          "to usual care across all enrolled regional hospitals."),
  }


def _record(*, key="paper-one", paper_id="p1", author="Priya Patel",
            year=2022, status="included", role="evidence", reason=None):
  screening = {"status": status}
  if reason is not None:
    screening["reason"] = reason
  return {
      "key": key,
      "ids": {"pmcid": paper_id},
      "authors": [author],
      "year": year,
      "role": role,
      "found_via": "openalex",
      "fulltext": "fulltext",
      "screening": screening,
  }


def _snapshot(tmp_path, *, claims=None, corpus=None, synthesis=None,
              refs=None, reverse_creation=False):
  claims = claims or [_claim()]
  corpus = corpus or [_record()]
  synthesis = synthesis or (
      "Readmissions fell 18% in the treatment arm (Patel, 2022).")
  refs = refs if refs is not None else [{
      "doi": "10.1/example", "title": "Example Study"}]
  payloads = {
      "protocol.md": "# Protocol\n",
      "corpus.json": json.dumps(corpus),
      "claims.json": json.dumps(claims),
      "synthesis.md": synthesis,
      "refs.json": json.dumps(refs),
      "project.json": json.dumps({"project": "review"}),
  }
  for record in corpus:
    if (record.get("screening") or {}).get("status") != "included":
      continue
    if record.get("role") not in {"evidence", "background"}:
      continue
    paper_id = record["ids"]["pmcid"]
    payloads[f"papers/{paper_id}/fulltext.md"] = (
        "Thirty-day readmissions fell 18% in the treatment arm relative "
        "to usual care across all enrolled regional hospitals.")
  paths = list(payloads)
  if reverse_creation:
    paths.reverse()
  root = tmp_path / ("reverse" if reverse_creation else "review")
  for relative_path in paths:
    destination = root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(payloads[relative_path], encoding="utf-8")
  return load_workspace(root)


def _finding(reason, *, severity=Severity.WARNING, artifact="claims.json",
             context=None):
  return Finding(
      reason_code=reason,
      severity=severity,
      artifact=artifact,
      message="stable test finding",
      context=context or {},
  )


def test_valid_workspace_scores_100(tmp_path):
  report = score_integrity(_snapshot(tmp_path), ())

  assert report.integrity_score == 100.0
  assert report.status is IntegrityStatus.VALID
  assert list(report.dimensions) == [
      "quote_authenticity", "citation_binding", "quantitative_grounding",
      "synthesis_coverage", "bibliography_verification",
      "prisma_artifact_completeness",
  ]
  assert [(dimension.nominal_weight, dimension.effective_weight)
          for dimension in report.dimensions.values()] == [
      (25.0, 25.0), (20.0, 20.0), (20.0, 20.0),
      (15.0, 15.0), (10.0, 10.0), (10.0, 10.0),
  ]
  assert {name: dimension.evaluated_units
          for name, dimension in report.dimensions.items()} == {
      "quote_authenticity": 1,
      "citation_binding": 1,
      "quantitative_grounding": 1,
      "synthesis_coverage": 1,
      "bibliography_verification": 1,
      "prisma_artifact_completeness": 8,
  }


def test_dimension_failure_deducts_only_its_weight(tmp_path):
  finding = _finding(
      ReasonCode.ABSTRACT_ONLY_SUPPORT,
      context={"result_index": 0, "claim_text": "Readmissions fell 18%.",
               "numbers_missing": []},
  )

  report = score_integrity(_snapshot(tmp_path), (finding,))

  assert report.integrity_score == 75.0
  assert report.dimensions["quote_authenticity"].score == 0.0
  assert all(dimension.score == 100.0 for name, dimension
             in report.dimensions.items() if name != "quote_authenticity")


def test_duplicate_findings_do_not_double_deduct_one_unit(tmp_path):
  claims = [_claim(), _claim(paper_id="p1")]
  first = _finding(
      ReasonCode.FABRICATED_QUOTE,
      severity=Severity.CRITICAL,
      context={"result_index": 0, "claim_text": claims[0]["claim"],
               "numbers_missing": ["18"]},
  )
  duplicate_unit = _finding(
      ReasonCode.CLAIM_NEEDS_REVIEW,
      context={"result_index": 0, "claim_text": claims[0]["claim"],
               "numbers_missing": ["18"]},
  )

  report = score_integrity(
      _snapshot(tmp_path, claims=claims), (first, duplicate_unit))

  assert report.dimensions["quote_authenticity"].evaluated_units == 2
  assert report.dimensions["quote_authenticity"].passed_units == 1
  assert report.dimensions["quote_authenticity"].score == 50.0
  assert report.dimensions["quantitative_grounding"].passed_units == 1
  assert len(report.dimensions["quantitative_grounding"].findings) == 2


def test_quantitative_units_use_all_non_citation_numbers(tmp_path):
  claim_text = (
      "In 2022, readmissions fell 18%, then settled at 12.5% (Patel, 2024).")
  assert check_claims.extract_numbers(claim_text) == [
      "2022", "18", "12.5", "2024"]
  finding = _finding(
      ReasonCode.CLAIM_NEEDS_REVIEW,
      context={"result_index": 0, "claim_text": claim_text,
               "numbers_missing": ["12.5"]},
  )

  report = score_integrity(
      _snapshot(tmp_path, claims=[_claim(claim=claim_text)]), (finding,))

  dimension = report.dimensions["quantitative_grounding"]
  assert (dimension.evaluated_units, dimension.passed_units) == (3, 2)
  assert dimension.score == pytest.approx(200 / 3)
  assert report.integrity_score == pytest.approx(205 / 3)


def test_quantitative_units_count_repeated_number_occurrences(tmp_path):
  claim_text = "In 2020, the trial enrolled 2020 participants."
  finding = _finding(
      ReasonCode.CLAIM_NEEDS_REVIEW,
      context={"result_index": 0, "claim_text": claim_text,
               "numbers_missing": ["2020"]},
  )

  report = score_integrity(
      _snapshot(tmp_path, claims=[_claim(claim=claim_text)]), (finding,))

  dimension = report.dimensions["quantitative_grounding"]
  assert (dimension.evaluated_units, dimension.passed_units) == (2, 1)
  assert dimension.score == 50.0


def test_binding_and_coverage_enumerate_each_claim_and_sentence_identity(
    tmp_path,
):
  claims = [
      _claim(),
      _claim(paper_id="p2", citation="Lee, 2021",
             claim="Mortality fell 12% in the intervention arm."),
  ]
  corpus = [
      _record(),
      _record(key="paper-two", paper_id="p2", author="Ana Lee", year=2021),
  ]
  synthesis = (
      "Readmissions fell 18% (Patel, 2022; Lee, 2021). "
      "Mortality fell 12% (Lee, 2021).")

  report = score_integrity(_snapshot(
      tmp_path, claims=claims, corpus=corpus, synthesis=synthesis), ())

  assert report.dimensions["citation_binding"].evaluated_units == 2
  assert report.dimensions["synthesis_coverage"].evaluated_units == 3


def _coverage_finding(sentence, index):
  return _finding(
      ReasonCode.COVERAGE_CLAIM_MISSING,
      severity=Severity.CRITICAL,
      context={
          "synthesis_sentence": sentence,
          "synthesis_sentence_index": index,
          "citation_identity": "author:lee:2021",
      },
  )


def test_repeated_identical_coverage_occurrences_fail_independently(tmp_path):
  sentence = "An unsupported finding appears here (Lee, 2021)."
  synthesis = f"{sentence} {sentence}"
  snapshot = _snapshot(tmp_path, synthesis=synthesis)

  one = score_integrity(snapshot, (_coverage_finding(sentence, 0),))
  both = score_integrity(snapshot, (
      _coverage_finding(sentence, 1), _coverage_finding(sentence, 0)))

  one_dimension = one.dimensions["synthesis_coverage"]
  both_dimension = both.dimensions["synthesis_coverage"]
  assert (one_dimension.evaluated_units, one_dimension.passed_units) == (2, 1)
  assert one_dimension.score == 50.0
  assert (both_dimension.evaluated_units, both_dimension.passed_units) == (2, 0)
  assert both_dimension.score == 0.0


def test_repeated_coverage_findings_are_order_independent(tmp_path):
  sentence = "An unsupported finding appears here (Lee, 2021)."
  snapshot = _snapshot(tmp_path, synthesis=f"{sentence} {sentence}")
  first = _coverage_finding(sentence, 0)
  second = _coverage_finding(sentence, 1)

  assert score_integrity(snapshot, (first, second)).to_dict() == (
      score_integrity(snapshot, (second, first)).to_dict())


@pytest.mark.parametrize("index", [True, False, -1, 2, "0", None])
def test_malformed_coverage_occurrence_fails_dimension_closed(tmp_path, index):
  sentence = "An unsupported finding appears here (Lee, 2021)."
  snapshot = _snapshot(tmp_path, synthesis=f"{sentence} {sentence}")

  report = score_integrity(snapshot, (_coverage_finding(sentence, index),))

  assert report.dimensions["synthesis_coverage"].score == 0.0


def test_mismatched_coverage_occurrence_context_fails_dimension_closed(tmp_path):
  sentence = "An unsupported finding appears here (Lee, 2021)."
  snapshot = _snapshot(tmp_path, synthesis=f"{sentence} {sentence}")
  finding = _coverage_finding("Different sentence (Lee, 2021).", 0)

  report = score_integrity(snapshot, (finding,))

  assert report.dimensions["synthesis_coverage"].score == 0.0


def test_mismatched_coverage_identity_context_fails_dimension_closed(tmp_path):
  sentence = "An unsupported finding appears here (Lee, 2021)."
  snapshot = _snapshot(tmp_path, synthesis=f"{sentence} {sentence}")
  finding = _finding(
      ReasonCode.COVERAGE_CLAIM_MISSING,
      severity=Severity.CRITICAL,
      context={
          "synthesis_sentence": sentence,
          "synthesis_sentence_index": 0,
          "citation_identity": "author:patel:2022",
      },
  )

  report = score_integrity(snapshot, (finding,))

  assert report.dimensions["synthesis_coverage"].score == 0.0


def test_zero_numeric_claims_are_not_applicable_and_weights_renormalize(
    tmp_path,
):
  snapshot = _snapshot(tmp_path, claims=[_claim(
      claim="Readmissions improved in the treatment arm.")], synthesis=(
          "Readmissions improved in the treatment arm (Patel, 2022)."))

  report = score_integrity(snapshot, ())

  numeric = report.dimensions["quantitative_grounding"]
  assert (numeric.applicable, numeric.score, numeric.effective_weight) == (
      False, None, 0.0)
  assert (numeric.evaluated_units, numeric.passed_units) == (0, 0)
  assert [dimension.effective_weight for dimension in
          report.dimensions.values()] == [31.25, 25.0, 0.0, 18.75, 12.5, 12.5]
  assert report.integrity_score == 100.0
  assert report.to_dict()["dimensions"]["quote_authenticity"][
      "effective_weight"] == 31.2


def test_global_claim_incomplete_scores_all_dependent_dimensions_zero(
    tmp_path,
):
  incomplete = _finding(
      ReasonCode.VALIDATOR_INCOMPLETE,
      severity=Severity.CRITICAL,
      context={"validator": "claim"},
  )

  report = score_integrity(_snapshot(tmp_path), (incomplete,))

  for name in (
      "quote_authenticity", "citation_binding", "quantitative_grounding",
      "synthesis_coverage",
  ):
    dimension = report.dimensions[name]
    assert dimension.applicable is True
    assert dimension.score == 0.0
  assert report.dimensions["bibliography_verification"].score == 100.0


@pytest.mark.parametrize("index", [True, False, -1, 2, "0", None])
def test_malformed_claim_index_uses_dependent_dimension_fail_safe(
    tmp_path, index,
):
  incomplete = _finding(
      ReasonCode.VALIDATOR_INCOMPLETE,
      severity=Severity.CRITICAL,
      context={"validator": "claim", "result_index": index},
  )
  snapshot = _snapshot(tmp_path, claims=[_claim(), _claim()])

  report = score_integrity(snapshot, (incomplete,))

  for name in (
      "quote_authenticity", "citation_binding", "quantitative_grounding",
      "synthesis_coverage",
  ):
    assert report.dimensions[name].score == 0.0


def test_malformed_claim_level_incomplete_index_cannot_partially_target(tmp_path):
  incomplete = _finding(
      ReasonCode.VALIDATOR_INCOMPLETE,
      severity=Severity.CRITICAL,
      context={"result_index": True},
  )
  snapshot = _snapshot(tmp_path, claims=[_claim(), _claim()])

  report = score_integrity(snapshot, (incomplete,))

  for name in (
      "quote_authenticity", "citation_binding", "quantitative_grounding",
      "synthesis_coverage",
  ):
    assert report.dimensions[name].score == 0.0


def test_unknown_critical_finding_fails_all_applicable_dimensions(tmp_path):
  unknown = _finding(
      ReasonCode.ARTIFACT_TYPE_INVALID,
      severity=Severity.CRITICAL,
      artifact="unknown-artifact",
  )

  report = score_integrity(_snapshot(tmp_path), (unknown,))

  assert all(dimension.score == 0.0
             for dimension in report.dimensions.values())
  assert report.integrity_score == 0.0
  assert report.status is IntegrityStatus.INVALID


def test_high_score_cannot_override_critical_invalid_status(tmp_path):
  refs = [
      {"doi": "10.1/example", "title": "Example Study"},
      {"doi": "10.1/other", "title": "Other Study"},
  ]
  retracted = _finding(
      ReasonCode.CITATION_RETRACTED,
      severity=Severity.CRITICAL,
      artifact="refs.json",
      context={"result_index": 1},
  )

  report = score_integrity(_snapshot(tmp_path, refs=refs), (retracted,))

  assert report.integrity_score == 95.0
  assert report.status is IntegrityStatus.INVALID


@pytest.mark.parametrize("index", [True, False, -1, 2, "0", None])
def test_malformed_bibliography_index_fails_dimension_closed(tmp_path, index):
  refs = [
      {"doi": "10.1/example", "title": "Example Study"},
      {"doi": "10.1/other", "title": "Other Study"},
  ]
  retracted = _finding(
      ReasonCode.CITATION_RETRACTED,
      severity=Severity.CRITICAL,
      artifact="refs.json",
      context={"result_index": index},
  )

  report = score_integrity(_snapshot(tmp_path, refs=refs), (retracted,))

  assert report.dimensions["bibliography_verification"].score == 0.0


def test_unscreened_record_fails_artifact_prisma_dimension_closed(tmp_path):
  corpus = [_record(), _record(
      key="paper-two", paper_id="p2", status=None, role="other")]
  incomplete = _finding(
      ReasonCode.VALIDATOR_INCOMPLETE,
      severity=Severity.CRITICAL,
      artifact="corpus.json",
      context={"validator": "prisma", "unscreened_indices": [1]},
  )

  report = score_integrity(_snapshot(tmp_path, corpus=corpus), (incomplete,))

  dimension = report.dimensions["prisma_artifact_completeness"]
  assert dimension.applicable is True
  assert dimension.score == 0.0


@pytest.mark.parametrize("index", [True, False, -1, 2, "0"])
def test_malformed_prisma_decision_index_fails_dimension_closed(
    tmp_path, index,
):
  corpus = [
      _record(),
      _record(key="excluded", paper_id="p2", status="excluded",
              role="other"),
  ]
  missing_reason = _finding(
      ReasonCode.PRISMA_EXCLUSION_REASON_MISSING,
      artifact="corpus.json",
      context={"decision_indices": [index], "count": 1},
  )

  report = score_integrity(
      _snapshot(tmp_path, corpus=corpus), (missing_reason,))

  assert report.dimensions["prisma_artifact_completeness"].score == 0.0


def test_report_round_trip_is_strict_and_recomputes_unrounded_values(tmp_path):
  report = score_integrity(
      _snapshot(tmp_path, claims=[_claim(), _claim(), _claim()]), (
      _finding(
          ReasonCode.CLAIM_NEEDS_REVIEW,
          context={"result_index": 0, "claim_text": "claim",
                   "numbers_missing": []},
      ),
  ))

  serialized = report.to_dict()
  assert serialized["dimensions"]["quote_authenticity"]["score"] == 66.7
  assert report.dimensions["quote_authenticity"].unrounded_score == (
      100.0 * 2 / 3)
  assert PassReport.from_dict(serialized) == report
  serialized["dimensions"]["quote_authenticity"]["passed_units"] = 3
  try:
    PassReport.from_dict(serialized)
  except ValueError as exc:
    assert "score" in str(exc) or "units" in str(exc)
  else:
    raise AssertionError("inconsistent dimension counts were accepted")


def test_output_order_is_independent_of_input_and_creation_order(tmp_path):
  first = _finding(
      ReasonCode.CLAIM_NEEDS_REVIEW,
      context={"result_index": 0, "claim_text": "claim",
               "numbers_missing": []},
  )
  second = _finding(
      ReasonCode.CITATION_RESOLUTION_UNAVAILABLE,
      artifact="refs.json", context={"result_index": 0},
  )

  report_a = score_integrity(
      _snapshot(tmp_path / "a"), (second, first))
  report_b = score_integrity(
      _snapshot(tmp_path / "b", reverse_creation=True), (first, second))

  assert report_a.to_dict() == report_b.to_dict()
