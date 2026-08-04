import importlib
import json
import pathlib
import sys
from datetime import datetime, timezone

import pytest


SCRIPTS = (pathlib.Path(__file__).resolve().parents[1]
           / "skills/literature-review/scripts")
sys.path.insert(0, str(SCRIPTS))

from review_integrity.models import ReasonCode, Severity  # noqa: E402
from review_integrity.workspace import load_workspace  # noqa: E402


def _validators():
  return importlib.import_module("review_integrity.validators")


@pytest.mark.parametrize(("status", "reason", "severity"), [
    ("fabricated_quote", ReasonCode.FABRICATED_QUOTE, Severity.CRITICAL),
    ("invalid_binding", ReasonCode.CITATION_IDENTITY_MISMATCH,
     Severity.CRITICAL),
    ("uncovered_claim", ReasonCode.COVERAGE_NUMBER_MISSING,
     Severity.CRITICAL),
    ("needs_review", ReasonCode.CLAIM_NEEDS_REVIEW, Severity.WARNING),
])
def test_claim_statuses_map_to_stable_findings(status, reason, severity):
  validators = _validators()
  result = {"status": status, "claim": "submitted claim", "paper_id": "p1"}
  if status == "uncovered_claim":
    result["reason_code"] = "coverage_number_missing"

  findings = validators.claim_findings({"results": [result]})

  assert [(finding.reason_code, finding.severity)
          for finding in findings] == [(reason, severity)]
  assert findings[0].context["result_index"] == 0


def test_ambiguous_binding_maps_to_distinct_stable_reason():
  validators = _validators()
  report = {"results": [{
      "status": "invalid_binding", "reason_code": "reference_ambiguous",
      "claim": "submitted claim", "paper_id": "p1",
  }]}

  finding = validators.claim_findings(report)[0]

  assert finding.reason_code is ReasonCode.CITATION_AMBIGUOUS
  assert finding.context["validator_reason"] == "reference_ambiguous"


@pytest.mark.parametrize(("validator_reason", "stable_reason"), [
    ("coverage_role_invalid", ReasonCode.COVERAGE_ROLE_INVALID),
    ("coverage_identity_missing", ReasonCode.COVERAGE_CLAIM_MISSING),
])
def test_other_coverage_reasons_map_stably(validator_reason, stable_reason):
  validators = _validators()
  finding = validators.claim_findings({"results": [{
      "status": "uncovered_claim", "reason_code": validator_reason,
  }]})[0]
  assert finding.reason_code is stable_reason
  assert finding.severity is Severity.CRITICAL


def test_verified_abstract_support_is_warning_but_fulltext_is_clean():
  validators = _validators()
  findings = validators.claim_findings({"results": [
      {"status": "verified", "source_scope": "abstract", "paper_id": "a"},
      {"status": "verified", "source_scope": "fulltext", "paper_id": "b"},
      {"status": "background", "source_scope": "fulltext", "paper_id": "c"},
  ]})
  assert [finding.reason_code for finding in findings] == [
      ReasonCode.ABSTRACT_ONLY_SUPPORT]


@pytest.mark.parametrize("status", [
    "source_missing", "no_quote", "quote_too_short", None,
])
def test_incomplete_claim_results_fail_closed(status):
  validators = _validators()
  findings = validators.claim_findings({"results": [{"status": status}]})
  assert findings[0].reason_code is ReasonCode.VALIDATOR_INCOMPLETE
  assert findings[0].severity is Severity.CRITICAL


def test_missing_exclusion_reason_is_warning():
  validators = _validators()
  findings = validators.prisma_findings({
      "after_dedup": 1, "excluded": {"unspecified": 1}})
  assert findings[0].reason_code is ReasonCode.PRISMA_EXCLUSION_REASON_MISSING
  assert findings[0].severity is Severity.WARNING
  assert findings[0].context["count"] == 1


def test_retracted_citation_is_critical():
  validators = _validators()
  finding = validators.citation_findings({
      "total": 1, "verified": 0, "mismatched": 0, "not_found": 0,
      "retracted": 1, "response_status": "complete",
      "results": [{"status": "retracted", "input": "10.1/retracted",
                   "retraction_checked": True}],
  })[0]
  assert finding.reason_code is ReasonCode.CITATION_RETRACTED
  assert finding.severity is Severity.CRITICAL


def test_unavailable_citation_resolver_is_unresolved_not_verified():
  verify_citations = importlib.import_module("verify_citations")

  class UnavailableResolver:
    identity = "offline-test-resolver"

    def resolve(self, entry):
      raise verify_citations.ResolverUnavailable("service unavailable")

  report = verify_citations.verify_citation_entries(
      [{"doi": "10.1/x", "title": None, "raw": "10.1/x"}],
      UnavailableResolver(),
      datetime(2026, 8, 4, 12, 30, tzinfo=timezone.utc),
  )

  assert report["verified"] == 0
  assert report["not_found"] == 0
  assert report["response_status"] == "unavailable"
  assert report["resolver"] == "offline-test-resolver"
  assert report["checked_at"] == "2026-08-04T12:30:00Z"
  assert report["results"][0]["status"] == "unavailable"
  finding = _validators().citation_findings(report)[0]
  assert finding.reason_code is ReasonCode.CITATION_RESOLUTION_UNAVAILABLE
  assert finding.severity is Severity.WARNING


def test_authoritative_empty_citation_lookup_remains_not_found():
  verify_citations = importlib.import_module("verify_citations")

  class EmptyResolver:
    identity = "authoritative-test-resolver"

    def resolve(self, entry):
      return {
          "input": entry["raw"], "status": "not_found", "doi": entry["doi"],
          "matched_title": None, "source": "test", "retraction_checked": False,
          "retraction_source": None,
      }

  report = verify_citations.verify_citation_entries(
      [{"doi": "10.1/missing", "title": None, "raw": "missing"}],
      EmptyResolver(), datetime(2026, 8, 4, tzinfo=timezone.utc))
  assert report["not_found"] == 1
  assert report["response_status"] == "complete"
  finding = _validators().citation_findings(report)[0]
  assert finding.reason_code is ReasonCode.CITATION_IDENTITY_MISMATCH
  assert finding.severity is Severity.CRITICAL


def test_verified_without_retraction_check_is_resolution_warning():
  validators = _validators()
  findings = validators.citation_findings({
      "total": 1, "verified": 1, "mismatched": 0, "not_found": 0,
      "retracted": 0, "response_status": "partial",
      "results": [{"status": "verified", "input": "citation",
                   "doi": "10.1/x", "matched_title": "Title",
                   "source": "test", "retraction_checked": False,
                   "retraction_source": None}],
  })
  assert findings[0].reason_code is ReasonCode.CITATION_RESOLUTION_UNAVAILABLE
  assert findings[0].severity is Severity.WARNING


def test_incomplete_verified_bibliography_metadata_is_warning():
  validators = _validators()
  findings = validators.citation_findings({
      "total": 1, "verified": 1, "mismatched": 0, "not_found": 0,
      "retracted": 0, "response_status": "complete",
      "results": [{"status": "verified", "input": "citation",
                   "doi": None, "matched_title": "Unique Title",
                   "source": "test", "retraction_checked": True,
                   "retraction_source": "test"}],
  })
  assert [finding.reason_code for finding in findings] == [
      ReasonCode.BIBLIOGRAPHY_INCOMPLETE]


def test_malformed_validator_output_is_critical():
  validators = _validators()
  for adapter, value in (
      (validators.claim_findings, {"results": "not-a-list"}),
      (validators.citation_findings, {"results": "not-a-list"}),
      (validators.prisma_findings, {"excluded": []}),
  ):
    finding = adapter(value)[0]
    assert finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE
    assert finding.severity is Severity.CRITICAL


@pytest.mark.parametrize(("adapter_name", "report"), [
    ("claim_findings", {"results": [{"status": ["verified"]}]}),
    ("claim_findings", {"results": [{"status": "verified"}]}),
    ("citation_findings", {
        "response_status": ["complete"], "results": []}),
    ("prisma_findings", {"excluded": {"unspecified": True}}),
])
def test_semantically_malformed_outputs_return_critical_not_exceptions(
    adapter_name, report,
):
  finding = getattr(_validators(), adapter_name)(report)[0]
  assert finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE
  assert finding.severity is Severity.CRITICAL


@pytest.mark.parametrize(("openalex_status", "expected"), [
    (404, "not_found"),
    (503, "unavailable"),
])
def test_network_resolver_distinguishes_empty_lookup_from_outage(
    monkeypatch, openalex_status, expected,
):
  verify_citations = importlib.import_module("verify_citations")

  def openalex_failure(url):
    raise verify_citations.http_client.HttpError(
        "resolver response", status_code=openalex_status)

  monkeypatch.setattr(verify_citations._OPENALEX, "fetch_json",
                      openalex_failure)
  monkeypatch.setattr(verify_citations._EPMC, "fetch_json",
                      lambda url: {"resultList": {"result": []}})
  report = verify_citations.verify_citation_entries(
      [{"doi": "10.1/missing", "title": None, "raw": "missing"}],
      verify_citations.NetworkCitationResolver(),
      datetime(2026, 8, 4, tzinfo=timezone.utc),
  )
  assert report["results"][0]["status"] == expected
  assert report["not_found"] == (expected == "not_found")


def _write_snapshot(root, *, source_name="fulltext.md", excluded=False,
                    claims_override=None):
  source = ("Thirty-day readmissions fell 18% in the treatment arm relative "
            "to usual care across all enrolled regional hospitals.")
  corpus = [{
      "key": "paper-one", "ids": {"pmcid": "p1"}, "title": "A Paper",
      "authors": ["Priya Patel"], "year": 2022, "role": "evidence",
      "fulltext": "fulltext" if source_name == "fulltext.md" else "abstract-only",
      "found_via": "openalex", "screening": {"status": "included"},
  }]
  if excluded:
    corpus.append({
        "key": "excluded-paper", "ids": {"pmcid": "excluded"},
        "role": "evidence", "found_via": "openalex",
        "screening": {"status": "excluded"},
    })
  claims = [{
      "claim": "Readmissions fell 18% in the treatment arm.",
      "paper_id": "p1", "citation": "Patel, 2022",
      "supporting_quote": source,
  }]
  if claims_override is not None:
    claims = claims_override
  payloads = {
      "project.json": {"project": "review"}, "protocol.md": "# Protocol\n",
      "corpus.json": corpus, "claims.json": claims,
      "synthesis.md": ("Readmissions fell 18% in the treatment arm "
                       "(Patel, 2022).\n"),
      "refs.json": [], f"papers/p1/{source_name}": source,
  }
  for relative, value in payloads.items():
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
      path.write_text(value, encoding="utf-8")
    else:
      path.write_text(json.dumps(value), encoding="utf-8")
  return load_workspace(root)


def test_artifact_findings_reports_abstract_only_preferred_source(tmp_path):
  snapshot = _write_snapshot(tmp_path / "review", source_name="abstract.md")
  findings = _validators().artifact_findings(snapshot)
  abstract = [finding for finding in findings
              if finding.reason_code is ReasonCode.ABSTRACT_ONLY_SUPPORT]
  assert len(abstract) == 1
  assert abstract[0].context["paper_id"] == "p1"


def test_artifact_findings_reports_semantically_invalid_claim_entries(tmp_path):
  snapshot = _write_snapshot(
      tmp_path / "review", claims_override=["not-a-claim-object"])
  findings = _validators().artifact_findings(snapshot)
  assert [(finding.reason_code, finding.artifact) for finding in findings] == [
      (ReasonCode.ARTIFACT_MALFORMED, "claims.json")]


def test_validate_snapshot_uses_retained_bytes_not_mutated_paths(tmp_path):
  root = tmp_path / "review"
  snapshot = _write_snapshot(root)
  (root / "claims.json").write_text("{malformed", encoding="utf-8")
  (root / "papers/p1/fulltext.md").write_text(
      "mutated source does not contain the quote", encoding="utf-8")

  findings = _validators().validate_snapshot(snapshot, citation_report={
      "total": 0, "verified": 0, "mismatched": 0, "not_found": 0,
      "retracted": 0, "response_status": "complete", "results": [],
  })

  assert not any(finding.reason_code in {
      ReasonCode.FABRICATED_QUOTE, ReasonCode.ARTIFACT_MALFORMED,
      ReasonCode.VALIDATOR_INCOMPLETE,
  } for finding in findings)


def test_validate_snapshot_catches_adapter_exception(monkeypatch, tmp_path):
  validators = _validators()
  snapshot = _write_snapshot(tmp_path / "review")

  def boom(snapshot):
    raise RuntimeError("adapter failed")

  monkeypatch.setattr(validators, "artifact_findings", boom)
  findings = validators.validate_snapshot(snapshot, citation_report={
      "total": 0, "verified": 0, "mismatched": 0, "not_found": 0,
      "retracted": 0, "response_status": "complete", "results": [],
  })
  assert findings[0].reason_code is ReasonCode.VALIDATOR_INCOMPLETE
  assert findings[0].context["validator"] == "artifact"


def test_validate_snapshot_returns_stable_adapter_order(tmp_path):
  snapshot = _write_snapshot(
      tmp_path / "review", source_name="abstract.md", excluded=True)
  findings = _validators().validate_snapshot(snapshot, citation_report={
      "total": 1, "verified": 0, "mismatched": 0, "not_found": 0,
      "retracted": 1, "response_status": "complete",
      "results": [{"status": "retracted", "input": "10.1/retracted",
                   "retraction_checked": True}],
  })
  assert [finding.reason_code for finding in findings] == [
      ReasonCode.ABSTRACT_ONLY_SUPPORT,
      ReasonCode.ABSTRACT_ONLY_SUPPORT,
      ReasonCode.CITATION_RETRACTED,
      ReasonCode.PRISMA_EXCLUSION_REASON_MISSING,
  ]
