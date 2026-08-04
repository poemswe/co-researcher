import importlib
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest


SCRIPTS = (pathlib.Path(__file__).resolve().parents[1]
           / "skills/literature-review/scripts")
sys.path.insert(0, str(SCRIPTS))

from review_integrity.models import ReasonCode, Severity  # noqa: E402
from review_integrity.workspace import load_workspace  # noqa: E402


def _validators():
  return importlib.import_module("review_integrity.validators")


def _citation_report(entries, resolver):
  verify_citations = importlib.import_module("verify_citations")
  return verify_citations.verify_citation_entries(
      entries, resolver, datetime(2026, 8, 4, tzinfo=timezone.utc))


class _StaticResolver:
  identity = "static-test"

  def __init__(self, **overrides):
    self.overrides = overrides

  def resolve(self, entry):
    result = {
        "input": entry["raw"], "status": "verified", "doi": entry["doi"],
        "matched_title": "Title", "source": "test",
        "retraction_checked": True, "retraction_source": "test",
        "retraction_status": "complete", "resolution_status": "complete",
    }
    result.update(self.overrides)
    return result


_CLAIM_STATUSES = (
    "verified", "needs_review", "background", "fabricated_quote",
    "uncovered_claim", "source_missing", "no_quote", "quote_too_short",
    "invalid_binding",
)


def _claim_result(status, **overrides):
  result = {
      "claim": "submitted claim", "paper_id": "p1",
      "citation": "Patel, 2022", "supporting_quote": "submitted quote",
      "status": status,
      "source_scope": "fulltext" if status in {
          "verified", "background", "needs_review", "fabricated_quote",
      } else None,
      "quote_match_ratio": None, "matched": None, "best_window": None,
      "quote_is_title": False, "context_risks": [], "anchors": None,
  }
  result.update(overrides)
  return result


def _claim_report(results):
  counts = {status: sum(result.get("status") == status for result in results)
            for status in _CLAIM_STATUSES}
  return {"total": len(results), **counts, "coverage_checked": False,
          "results": results}


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
  result = _claim_result(status)
  if status == "uncovered_claim":
    result["reason_code"] = "coverage_number_missing"
  elif status == "invalid_binding":
    result["reason_code"] = "citation_identity_mismatch"

  findings = validators.claim_findings(_claim_report([result]))

  assert [(finding.reason_code, finding.severity)
          for finding in findings] == [(reason, severity)]
  if status == "uncovered_claim":
    assert findings[0].context["synthesis_sentence"] == "submitted claim"
    assert findings[0].context["citation_identity"] == "Patel, 2022"
    assert "result_index" not in findings[0].context
  else:
    assert findings[0].context["result_index"] == 0
    assert findings[0].context["claim_text"] == "submitted claim"
    assert findings[0].context["numbers_missing"] is None


def test_claim_finding_context_retains_numeric_anchor_failures():
  finding = _validators().claim_findings(_claim_report([_claim_result(
      "needs_review", claim="Rates fell 18%.",
      anchors={"numbers_found": [], "numbers_missing": ["18"],
               "words_found": [], "words_missing": []},
  )]))[0]

  assert finding.context["claim_text"] == "Rates fell 18%."
  assert finding.context["numbers_missing"] == ("18",)


def test_ambiguous_binding_maps_to_distinct_stable_reason():
  validators = _validators()
  report = _claim_report([_claim_result(
      "invalid_binding", reason_code="reference_ambiguous")])

  finding = validators.claim_findings(report)[0]

  assert finding.reason_code is ReasonCode.CITATION_AMBIGUOUS
  assert finding.context["validator_reason"] == "reference_ambiguous"


@pytest.mark.parametrize(("validator_reason", "stable_reason"), [
    ("coverage_role_invalid", ReasonCode.COVERAGE_ROLE_INVALID),
    ("coverage_identity_missing", ReasonCode.COVERAGE_CLAIM_MISSING),
])
def test_other_coverage_reasons_map_stably(validator_reason, stable_reason):
  validators = _validators()
  finding = validators.claim_findings(_claim_report([_claim_result(
      "uncovered_claim", reason_code=validator_reason)]))[0]
  assert finding.reason_code is stable_reason
  assert finding.severity is Severity.CRITICAL


def test_verified_abstract_support_is_warning_but_fulltext_is_clean():
  validators = _validators()
  findings = validators.claim_findings(_claim_report([
      _claim_result("verified", source_scope="abstract", paper_id="a"),
      _claim_result("verified", source_scope="fulltext", paper_id="b"),
      _claim_result("background", source_scope="fulltext", paper_id="c"),
  ]))
  assert [finding.reason_code for finding in findings] == [
      ReasonCode.ABSTRACT_ONLY_SUPPORT]


@pytest.mark.parametrize("status", [
    "source_missing", "no_quote", "quote_too_short", None,
])
def test_incomplete_claim_results_fail_closed(status):
  validators = _validators()
  report = ({"results": [{"status": status}]} if status is None
            else _claim_report([_claim_result(status)]))
  findings = validators.claim_findings(report)
  assert findings[0].reason_code is ReasonCode.VALIDATOR_INCOMPLETE
  assert findings[0].severity is Severity.CRITICAL


def test_missing_exclusion_reason_is_warning():
  validators = _validators()
  findings = validators.prisma_findings({
      "records_by_source": {"openalex": 1}, "after_dedup": 1,
      "screened": 1, "excluded": {"unspecified": 1}, "included": 0,
      "not_retrieved": 0, "in_synthesis": 0,
  })
  assert findings[0].reason_code is ReasonCode.PRISMA_EXCLUSION_REASON_MISSING
  assert findings[0].severity is Severity.WARNING
  assert findings[0].context["count"] == 1


def test_prisma_findings_retain_exact_missing_reason_decision_indices():
  records = [
      {"screening": {"status": "excluded"}},
      {"screening": {"status": "excluded", "reason": "out of scope"}},
  ]
  finding = _validators().prisma_findings({
      "records_by_source": {"unknown": 2}, "after_dedup": 2,
      "screened": 2,
      "excluded": {"unspecified": 1, "out of scope": 1},
      "included": 0, "not_retrieved": 0, "in_synthesis": 0,
  }, records)[0]

  assert finding.context["decision_indices"] == (0,)


def test_unscreened_prisma_records_emit_global_incomplete_context():
  records = [
      {"screening": {"status": "included"}},
      {"screening": {}},
  ]
  finding = _validators().prisma_findings({
      "records_by_source": {"unknown": 2}, "after_dedup": 2,
      "screened": 1, "excluded": {}, "included": 1,
      "not_retrieved": 0, "in_synthesis": 1,
  }, records)[0]

  assert finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE
  assert finding.severity is Severity.CRITICAL
  assert finding.context["validator"] == "prisma"
  assert finding.context["unscreened_indices"] == (1,)


def test_retracted_citation_is_critical():
  validators = _validators()
  entries = [{"doi": "10.1/retracted", "title": None,
              "raw": "10.1/retracted"}]
  report = _citation_report(entries, _StaticResolver(status="retracted"))
  finding = validators.citation_findings(report, entries)[0]
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
  entries = [{"doi": "10.1/x", "title": None, "raw": "10.1/x"}]
  finding = _validators().citation_findings(report, entries)[0]
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
          "retraction_source": None, "retraction_status": "not_applicable",
          "resolution_status": "complete",
      }

  report = verify_citations.verify_citation_entries(
      [{"doi": "10.1/missing", "title": None, "raw": "missing"}],
      EmptyResolver(), datetime(2026, 8, 4, tzinfo=timezone.utc))
  assert report["not_found"] == 1
  assert report["response_status"] == "complete"
  entries = [{"doi": "10.1/missing", "title": None, "raw": "missing"}]
  finding = _validators().citation_findings(report, entries)[0]
  assert finding.reason_code is ReasonCode.CITATION_IDENTITY_MISMATCH
  assert finding.severity is Severity.CRITICAL


def test_verified_without_retraction_check_is_resolution_warning():
  validators = _validators()
  entries = [{"doi": "10.1/x", "title": None, "raw": "citation"}]
  report = _citation_report(entries, _StaticResolver(
      retraction_checked=False, retraction_source=None,
      retraction_status="partial"))
  findings = validators.citation_findings(report, entries)
  assert findings[0].reason_code is ReasonCode.CITATION_RESOLUTION_UNAVAILABLE
  assert findings[0].severity is Severity.WARNING


def test_incomplete_verified_bibliography_metadata_is_warning():
  validators = _validators()
  entries = [{"doi": None, "title": "Unique Title", "raw": "citation"}]
  report = _citation_report(entries, _StaticResolver(
      doi=None, matched_title="Unique Title"))
  findings = validators.citation_findings(report, entries)
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


def test_fallback_hit_after_primary_resolution_outage_is_partial(monkeypatch):
  verify_citations = importlib.import_module("verify_citations")

  def openalex_outage(url):
    raise verify_citations.http_client.HttpError("down", status_code=503)

  monkeypatch.setattr(verify_citations._OPENALEX, "fetch_json",
                      openalex_outage)
  monkeypatch.setattr(verify_citations._EPMC, "fetch_json", lambda url: {
      "resultList": {"result": [{
          "title": "Fallback Title", "doi": "10.1/x", "pmid": None,
      }]}})
  monkeypatch.setattr(verify_citations._CROSSREF, "fetch_json",
                      lambda url: {"message": {"total-results": 0}})
  report = verify_citations.verify_citation_entries(
      [{"doi": "10.1/x", "title": None, "raw": "x"}],
      verify_citations.NetworkCitationResolver(),
      datetime(2026, 8, 4, tzinfo=timezone.utc))
  assert report["results"][0]["resolution_status"] == "partial"
  assert report["response_status"] == "partial"


def _write_snapshot(root, *, source_name="fulltext.md", excluded=False,
                    claims_override=None, refs_override=None):
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
      "refs.json": [] if refs_override is None else refs_override,
      f"papers/p1/{source_name}": source,
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

  findings = _validators().validate_snapshot(
      snapshot, citation_report=_citation_report([], _EmptyResolver()))

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
  findings = validators.validate_snapshot(
      snapshot, citation_report=_citation_report([], _EmptyResolver()))
  assert findings[0].reason_code is ReasonCode.VALIDATOR_INCOMPLETE
  assert findings[0].context["validator"] == "artifact"


def test_validate_snapshot_returns_stable_adapter_order(tmp_path):
  refs = [{"doi": "10.1/retracted"}]
  snapshot = _write_snapshot(
      tmp_path / "review", source_name="abstract.md", excluded=True,
      refs_override=refs)
  entries = importlib.import_module(
      "verify_citations").normalize_citation_entries(refs)
  report = _citation_report(entries, _StaticResolver(status="retracted"))
  findings = _validators().validate_snapshot(snapshot, citation_report=report)
  assert [finding.reason_code for finding in findings] == [
      ReasonCode.ABSTRACT_ONLY_SUPPORT,
      ReasonCode.ABSTRACT_ONLY_SUPPORT,
      ReasonCode.CITATION_RETRACTED,
      ReasonCode.PRISMA_EXCLUSION_REASON_MISSING,
  ]


def test_empty_unprovenanced_citation_report_fails_closed():
  finding = _validators().citation_findings({"results": []})[0]
  assert finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE
  assert finding.severity is Severity.CRITICAL


@pytest.mark.parametrize("missing", [
    "bibliography_sha256", "resolver", "checked_at", "response_status",
])
def test_citation_report_requires_provenance_fields(missing):
  report = {
      "total": 0, "verified": 0, "mismatched": 0, "not_found": 0,
      "retracted": 0, "unavailable": 0,
      "bibliography_sha256": "0" * 64,
      "resolver": "test", "checked_at": "2026-08-04T00:00:00Z",
      "response_status": "complete", "results": [],
  }
  report.pop(missing)
  finding = _validators().citation_findings(report, [])[0]
  assert finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE


def test_citation_verification_requires_utc_checked_at():
  verify_citations = importlib.import_module("verify_citations")
  non_utc = timezone(timedelta(hours=2))
  with pytest.raises(ValueError, match="UTC"):
    verify_citations.verify_citation_entries(
        [], _EmptyResolver(), datetime(2026, 8, 4, tzinfo=non_utc))


@pytest.mark.parametrize(("field", "value"), [
    ("total", True), ("verified", True), ("mismatched", 1),
    ("not_found", 1), ("retracted", 1), ("unavailable", 1),
])
def test_citation_report_rejects_boolean_or_mismatched_counters(field, value):
  verify_citations = importlib.import_module("verify_citations")
  report = verify_citations.verify_citation_entries(
      [], _EmptyResolver(), datetime(2026, 8, 4, tzinfo=timezone.utc))
  report[field] = value
  finding = _validators().citation_findings(report, [])[0]
  assert finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE


def test_validate_snapshot_rejects_citation_report_for_empty_bibliography(
    tmp_path,
):
  verify_citations = importlib.import_module("verify_citations")
  snapshot = _write_snapshot(tmp_path / "review")
  report = verify_citations.verify_citation_entries(
      [{"doi": "10.1/other", "title": None, "raw": "10.1/other"}],
      _NotFoundResolver(), datetime(2026, 8, 4, tzinfo=timezone.utc))
  findings = _validators().validate_snapshot(snapshot, report)
  citation_findings = [finding for finding in findings
                       if finding.context.get("validator") == "citation"]
  assert len(citation_findings) == 1
  assert citation_findings[0].reason_code is ReasonCode.VALIDATOR_INCOMPLETE


def test_citation_report_commitment_rejects_reference_order_mismatch():
  verify_citations = importlib.import_module("verify_citations")
  first = {"doi": "10.1/first", "title": "First", "raw": "first"}
  second = {"doi": "10.1/second", "title": "Second", "raw": "second"}
  report = verify_citations.verify_citation_entries(
      [first, second], _NotFoundResolver(),
      datetime(2026, 8, 4, tzinfo=timezone.utc))
  finding = _validators().citation_findings(report, [second, first])[0]
  assert finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE


def test_citation_report_rejects_malformed_verified_fields():
  verify_citations = importlib.import_module("verify_citations")
  entry = {"doi": "10.1/x", "title": None, "raw": "x"}
  report = verify_citations.verify_citation_entries(
      [entry], _VerifiedResolver(),
      datetime(2026, 8, 4, tzinfo=timezone.utc))
  report["results"][0]["doi"] = True
  finding = _validators().citation_findings(report, [entry])[0]
  assert finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE


class _EmptyResolver:
  identity = "empty-test"

  def resolve(self, entry):
    raise AssertionError("empty bibliography must not invoke resolver")


class _NotFoundResolver:
  identity = "not-found-test"

  def resolve(self, entry):
    return {
        "input": entry["raw"], "status": "not_found", "doi": entry["doi"],
        "matched_title": None, "source": "test", "retraction_checked": False,
        "retraction_source": None, "retraction_status": "not_applicable",
        "resolution_status": "complete",
    }


class _VerifiedResolver:
  identity = "verified-test"

  def resolve(self, entry):
    return {
        "input": entry["raw"], "status": "verified", "doi": entry["doi"],
        "matched_title": "Title", "source": "test",
        "retraction_checked": True, "retraction_source": "test",
        "retraction_status": "complete", "resolution_status": "complete",
    }


def test_crossref_outage_and_clean_epmc_is_partial(monkeypatch):
  verify_citations = importlib.import_module("verify_citations")
  work = {
      "title": "Title", "doi": "https://doi.org/10.1/x",
      "is_retracted": False,
      "ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/1"},
  }
  monkeypatch.setattr(verify_citations._OPENALEX, "fetch_json",
                      lambda url: work)

  def crossref_outage(url):
    raise verify_citations.http_client.HttpError("down", status_code=503)

  monkeypatch.setattr(verify_citations._CROSSREF, "fetch_json",
                      crossref_outage)
  monkeypatch.setattr(verify_citations._EPMC, "fetch_json", lambda url: {
      "resultList": {"result": [{
          "pubTypeList": {"pubType": ["Journal Article"]},
          "commentCorrectionList": {"commentCorrection": []},
      }]}})
  report = verify_citations.verify_citation_entries(
      [{"doi": "10.1/x", "title": None, "raw": "x"}],
      verify_citations.NetworkCitationResolver(),
      datetime(2026, 8, 4, tzinfo=timezone.utc))
  assert report["response_status"] == "partial"
  assert report["results"][0]["retraction_status"] == "partial"
  findings = _validators().citation_findings(
      report, [{"doi": "10.1/x", "title": None, "raw": "x"}])
  assert any(finding.reason_code is ReasonCode.CITATION_RESOLUTION_UNAVAILABLE
             for finding in findings)


def test_verify_entries_rejects_malformed_resolver_result():
  verify_citations = importlib.import_module("verify_citations")

  class MalformedResolver:
    identity = "malformed-test"

    def resolve(self, entry):
      return {"status": "verified", "doi": True}

  with pytest.raises(ValueError, match="resolver result"):
    verify_citations.verify_citation_entries(
        [{"doi": "10.1/x", "title": None, "raw": "x"}],
        MalformedResolver(), datetime(2026, 8, 4, tzinfo=timezone.utc))


@pytest.mark.parametrize(("crossref_clean", "has_pmid", "expected"), [
    (True, True, "partial"),
    (False, False, "unavailable"),
])
def test_other_retraction_outage_combinations_are_not_complete(
    monkeypatch, crossref_clean, has_pmid, expected,
):
  verify_citations = importlib.import_module("verify_citations")
  hit = {"title": "Title", "doi": "10.1/x", "retracted": False,
         "pmid": "1" if has_pmid else None, "source": "openalex"}
  if crossref_clean:
    monkeypatch.setattr(verify_citations, "retracted_via_crossref",
                        lambda doi: False)
    monkeypatch.setattr(verify_citations, "retracted_via_epmc",
                        lambda pmid: None)
  else:
    monkeypatch.setattr(verify_citations, "retracted_via_crossref",
                        lambda doi: None)
  retracted, status, source = verify_citations._retraction_audit(hit)
  assert retracted is False
  assert status == expected


def test_claim_report_rejects_counter_result_mismatch():
  report = {
      "total": 1, "verified": 1, "needs_review": 0, "background": 0,
      "fabricated_quote": 0, "uncovered_claim": 0, "source_missing": 0,
      "no_quote": 0, "quote_too_short": 0, "invalid_binding": 0,
      "coverage_checked": False,
      "results": [{
          "claim": "claim", "paper_id": "p1", "citation": "Patel, 2022",
          "supporting_quote": "quote", "status": "fabricated_quote",
          "source_scope": "fulltext", "quote_match_ratio": 0.0,
          "matched": None, "best_window": "window", "quote_is_title": False,
          "context_risks": [], "anchors": None,
      }],
  }
  finding = _validators().claim_findings(report)[0]
  assert finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE


@pytest.mark.parametrize("mutation", [
    {"after_dedup": True},
    {"after_dedup": 2},
    {"screened": 0, "included": 1},
    {"included": 1, "not_retrieved": 0, "in_synthesis": 0},
])
def test_prisma_report_rejects_malformed_or_inconsistent_counts(mutation):
  report = {
      "records_by_source": {"openalex": 1}, "after_dedup": 1,
      "screened": 1, "excluded": {}, "included": 1,
      "not_retrieved": 0, "in_synthesis": 1,
  }
  report.update(mutation)
  finding = _validators().prisma_findings(report)[0]
  assert finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE


def _pure_claim_inputs(scope_marker):
  source = ("Thirty-day readmissions fell 18% in the treatment arm relative "
            "to usual care across all enrolled regional hospitals.")
  entries = [{
      "claim": "Readmissions fell 18% in the treatment arm.",
      "paper_id": "p1", "citation": "Patel, 2022",
      "supporting_quote": source,
  }]
  corpus = [{
      "key": "paper-one", "ids": {"pmcid": "p1"},
      "authors": ["Priya Patel"], "year": 2022, "role": "evidence",
      **({} if scope_marker is None else {"fulltext": scope_marker}),
  }]
  return entries, corpus, {"p1": source}


def test_ordinary_source_dict_uses_explicit_abstract_scope():
  check_claims = importlib.import_module("check_claims")
  entries, corpus, sources = _pure_claim_inputs("abstract-only")
  report = check_claims.check_claims_document(
      entries, corpus, sources, None, [])
  assert report["results"][0]["source_scope"] == "abstract"


@pytest.mark.parametrize("scope_marker", [None, "unknown", True])
def test_pure_claim_validation_fails_closed_without_exact_source_scope(
    scope_marker,
):
  check_claims = importlib.import_module("check_claims")
  entries, corpus, sources = _pure_claim_inputs(scope_marker)
  with pytest.raises(ValueError, match="scope|fulltext"):
    check_claims.check_claims_document(entries, corpus, sources, None, [])


def test_citation_commitment_includes_raw_and_rejects_replay_collision():
  verify_citations = importlib.import_module("verify_citations")
  first = {"doi": "10.1/x", "title": "Title", "raw": "first rendering"}
  second = {"doi": "10.1/x", "title": "Title", "raw": "second rendering"}
  assert verify_citations.citation_input_identity(first) != (
      verify_citations.citation_input_identity(second))
  assert verify_citations.bibliography_sha256([first]) != (
      verify_citations.bibliography_sha256([second]))


@pytest.mark.parametrize("entry", [
    {"doi": "10.1/x", "title": None},
    {"doi": "10.1/x", "title": None, "raw": "x", "extra": True},
])
def test_pure_citation_verifier_requires_exact_normalized_entry_schema(entry):
  verify_citations = importlib.import_module("verify_citations")
  with pytest.raises(ValueError, match="citation entry|fields|schema"):
    verify_citations.verify_citation_entries(
        [entry], _StaticResolver(),
        datetime(2026, 8, 4, tzinfo=timezone.utc))


def test_json_bibliography_raw_is_deterministic_complete_original_object():
  verify_citations = importlib.import_module("verify_citations")
  original = {"title": "Title", "doi": "10.1/x", "raw": "spoof",
              "note": "submitted metadata"}
  changed = {**original, "note": "changed metadata"}
  first = verify_citations.normalize_citation_entries([original])[0]
  second = verify_citations.normalize_citation_entries([changed])[0]
  assert first["raw"] == json.dumps(
      original, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
  assert first["raw"] != second["raw"]
  assert verify_citations.bibliography_sha256([first]) != (
      verify_citations.bibliography_sha256([second]))


@pytest.mark.parametrize(("status", "audit", "checked"), [
    ("verified", "not_applicable", False),
    ("mismatched", "not_applicable", False),
    ("verified", "complete", False),
    ("verified", "partial", True),
    ("verified", "unavailable", True),
])
def test_citation_adapter_rejects_contradictory_retraction_audits(
    status, audit, checked,
):
  entries = [{"doi": "10.1/x", "title": None, "raw": "x"}]
  report = _citation_report(entries, _StaticResolver(status=status))
  result = report["results"][0]
  result["retraction_status"] = audit
  result["retraction_checked"] = checked
  report["response_status"] = "complete"
  finding = _validators().citation_findings(report, entries)[0]
  assert finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE


def test_prisma_adapter_rejects_unaccounted_screened_records():
  report = {
      "records_by_source": {"openalex": 2}, "after_dedup": 2,
      "screened": 2, "excluded": {}, "included": 1,
      "not_retrieved": 0, "in_synthesis": 1,
  }
  finding = _validators().prisma_findings(report)[0]
  assert finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE


def test_prisma_report_rejects_unknown_screening_status():
  prisma_counts = importlib.import_module("prisma_counts")
  with pytest.raises(ValueError, match="status"):
    prisma_counts.prisma_report([{
        "found_via": "openalex", "screening": {"status": "pending"}}])


@pytest.mark.parametrize(("scope", "expected"), [
    ("abstract", "abstract-only"), ("fulltext", "fulltext"),
])
def test_source_scope_enrichment_accepts_exact_loader_scopes(scope, expected):
  check_claims = importlib.import_module("check_claims")
  records = [{"key": "paper", "ids": {"pmcid": "p1"},
              "fulltext": "stale"}]
  enriched = check_claims.corpus_with_source_scopes(records, {"p1": scope})
  assert enriched[0]["fulltext"] == expected
  assert records[0]["fulltext"] == "stale"


def test_source_scope_enrichment_accepts_same_scope_for_multiple_aliases():
  check_claims = importlib.import_module("check_claims")
  records = [{"key": "paper", "ids": {"pmcid": "p1"},
              "fulltext": "stale"}]
  enriched = check_claims.corpus_with_source_scopes(
      records, {"paper": "abstract", "p1": "abstract"})
  assert enriched[0]["fulltext"] == "abstract-only"


@pytest.mark.parametrize("scopes", [
    {"p1": "invalid"},
    {"paper": "abstract", "p1": "fulltext"},
])
def test_source_scope_enrichment_rejects_invalid_or_conflicting_aliases(scopes):
  check_claims = importlib.import_module("check_claims")
  records = [{"key": "paper", "ids": {"pmcid": "p1"},
              "fulltext": "stale"}]
  with pytest.raises(ValueError, match="scope|conflict"):
    check_claims.corpus_with_source_scopes(records, scopes)
