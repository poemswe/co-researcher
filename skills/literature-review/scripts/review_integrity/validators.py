"""Pure adapters from literature validators to stable integrity findings."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Callable

import check_claims
import prisma_counts
import verify_citations

from .models import Finding, ReasonCode, Severity
from .workspace import WorkspaceSnapshot


def _incomplete(validator: str, artifact: str) -> Finding:
  return Finding(
      reason_code=ReasonCode.VALIDATOR_INCOMPLETE,
      severity=Severity.CRITICAL,
      artifact=artifact,
      message=f"{validator} validator did not produce an interpretable result",
      context={"validator": validator},
  )


def _result_context(result: dict, index: int) -> dict:
  if result.get("status") == "uncovered_claim":
    context = {
        "synthesis_sentence": result.get("claim"),
        "synthesis_sentence_index": result.get("synthesis_sentence_index"),
        "citation_identity": result.get("citation"),
    }
  else:
    anchors = result.get("anchors")
    numbers_missing = (anchors.get("numbers_missing")
                       if isinstance(anchors, dict) else None)
    context = {
        "result_index": index,
        "claim_text": result.get("claim"),
        "numbers_missing": numbers_missing,
    }
  for source, target in (
      ("status", "status"), ("reason_code", "validator_reason"),
      ("paper_id", "paper_id"), ("citation", "citation"),
      ("source_scope", "source_scope"),
  ):
    value = result.get(source)
    if isinstance(value, (str, int, bool)) or value is None:
      context[target] = value
  return context


def _claim_finding(
    reason_code: ReasonCode, severity: Severity, message: str,
    result: dict, index: int,
) -> Finding:
  return Finding(
      reason_code=reason_code,
      severity=severity,
      artifact="claims.json",
      message=message,
      context=_result_context(result, index),
  )


_CLAIM_STATUSES = (
    "verified", "needs_review", "background", "fabricated_quote",
    "uncovered_claim", "source_missing", "no_quote", "quote_too_short",
    "invalid_binding",
)


def _count(value) -> bool:
  return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _optional_string(value) -> bool:
  return value is None or isinstance(value, str)


def _valid_claim_result(result: object) -> bool:
  required = {
      "claim", "paper_id", "citation", "supporting_quote", "status",
      "source_scope", "quote_match_ratio", "matched", "best_window",
      "quote_is_title", "context_risks", "anchors",
  }
  if not isinstance(result, dict) or not required <= set(result):
    return False
  if result["status"] not in _CLAIM_STATUSES:
    return False
  if not all(_optional_string(result[field]) for field in (
      "claim", "paper_id", "citation", "supporting_quote", "source_scope",
      "matched", "best_window",
  )):
    return False
  ratio = result["quote_match_ratio"]
  if (ratio is not None and (isinstance(ratio, bool)
      or not isinstance(ratio, (int, float)) or not math.isfinite(ratio)
      or not 0 <= ratio <= 1)):
    return False
  if not isinstance(result["quote_is_title"], bool):
    return False
  if (not isinstance(result["context_risks"], list)
      or not all(isinstance(item, str) for item in result["context_risks"])):
    return False
  if result["anchors"] is not None and not isinstance(result["anchors"], dict):
    return False
  if result["status"] in {"verified", "background"}:
    if result["source_scope"] not in {"abstract", "fulltext"}:
      return False
  if result["status"] in {"invalid_binding", "uncovered_claim"}:
    if not isinstance(result.get("reason_code"), str):
      return False
  if result["status"] == "uncovered_claim":
    sentence_index = result.get("synthesis_sentence_index")
    if (type(sentence_index) is not int or sentence_index < 0):
      return False
  return True


def _valid_claim_report(report: object) -> bool:
  required = {"total", "coverage_checked", "results", *_CLAIM_STATUSES}
  if not isinstance(report, dict) or not required <= set(report):
    return False
  if not isinstance(report["coverage_checked"], bool):
    return False
  if not all(_count(report[status]) for status in _CLAIM_STATUSES):
    return False
  results = report["results"]
  if not isinstance(results, list) or not all(
      _valid_claim_result(result) for result in results):
    return False
  if (not _count(report["total"]) or report["total"] != len(results)
      or sum(report[status] for status in _CLAIM_STATUSES) != len(results)):
    return False
  actual = {status: 0 for status in _CLAIM_STATUSES}
  for result in results:
    actual[result["status"]] += 1
  return all(report[status] == actual[status] for status in _CLAIM_STATUSES)


def claim_findings(report: dict) -> tuple[Finding, ...]:
  """Map a claim-checker report into closed, stable findings."""
  if not _valid_claim_report(report):
    return (_incomplete("claim", "claims.json"),)
  results = report["results"]
  findings = []
  coverage_reasons = {
      "coverage_number_missing": ReasonCode.COVERAGE_NUMBER_MISSING,
      "coverage_role_invalid": ReasonCode.COVERAGE_ROLE_INVALID,
      "coverage_identity_missing": ReasonCode.COVERAGE_CLAIM_MISSING,
  }
  for index, result in enumerate(results):
    if not isinstance(result, dict):
      findings.append(_incomplete("claim", "claims.json"))
      continue
    status = result.get("status")
    if not isinstance(status, str):
      findings.append(_incomplete("claim", "claims.json"))
      continue
    if status == "fabricated_quote":
      findings.append(_claim_finding(
          ReasonCode.FABRICATED_QUOTE, Severity.CRITICAL,
          "supporting quote could not be authenticated", result, index))
    elif status == "invalid_binding":
      validator_reason = result.get("reason_code")
      reason = (ReasonCode.CITATION_AMBIGUOUS
                if isinstance(validator_reason, str)
                and "ambiguous" in validator_reason
                else ReasonCode.CITATION_IDENTITY_MISMATCH)
      findings.append(_claim_finding(
          reason, Severity.CRITICAL,
          "claim citation does not bind uniquely to its trusted source",
          result, index))
    elif status == "uncovered_claim":
      validator_reason = result.get("reason_code")
      reason = (coverage_reasons.get(validator_reason)
                if isinstance(validator_reason, str) else None)
      if reason is None:
        findings.append(_incomplete("claim", "claims.json"))
      else:
        findings.append(_claim_finding(
            reason, Severity.CRITICAL,
            "synthesis statement lacks a complete verified claim trace",
            result, index))
    elif status == "needs_review":
      findings.append(_claim_finding(
          ReasonCode.CLAIM_NEEDS_REVIEW, Severity.WARNING,
          "claim support requires review", result, index))
    elif status in {"source_missing", "no_quote", "quote_too_short"}:
      findings.append(_claim_finding(
          ReasonCode.VALIDATOR_INCOMPLETE, Severity.CRITICAL,
          "claim could not be fully validated", result, index))
    elif status == "verified":
      if result.get("source_scope") not in {"abstract", "fulltext"}:
        findings.append(_incomplete("claim", "claims.json"))
      elif result["source_scope"] == "abstract":
        findings.append(_claim_finding(
            ReasonCode.ABSTRACT_ONLY_SUPPORT, Severity.WARNING,
            "claim support was verified only against an abstract",
            result, index))
    elif status == "background":
      if result.get("source_scope") not in {"abstract", "fulltext"}:
        findings.append(_incomplete("claim", "claims.json"))
    else:
      findings.append(_incomplete("claim", "claims.json"))
  return tuple(findings)


def _citation_context(result: dict, index: int) -> dict:
  context = {"result_index": index}
  for key in ("status", "input", "doi", "matched_title", "source",
              "retraction_source", "resolution_status", "retraction_status"):
    value = result.get(key)
    if isinstance(value, (str, int, bool)) or value is None:
      context[key] = value
  return context


def _citation_finding(
    reason_code: ReasonCode, severity: Severity, message: str,
    result: dict, index: int, extra_context: dict | None = None,
) -> Finding:
  context = _citation_context(result, index)
  if extra_context:
    context.update(extra_context)
  return Finding(
      reason_code=reason_code,
      severity=severity,
      artifact="refs.json",
      message=message,
      context=context,
  )


_CITATION_STATUSES = (
    "verified", "mismatched", "not_found", "retracted", "unavailable",
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def _aware_utc_timestamp(value: object) -> bool:
  if not isinstance(value, str) or not value.endswith("Z"):
    return False
  try:
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
  except ValueError:
    return False
  return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def _valid_citation_result(result: object, entry: dict, index: int) -> bool:
  required = {
      "input", "status", "doi", "matched_title", "source",
      "retraction_checked", "retraction_source", "retraction_status",
      "resolution_status", "entry_index", "input_identity",
  }
  if not isinstance(result, dict) or not required <= set(result):
    return False
  if result["status"] not in _CITATION_STATUSES:
    return False
  if not isinstance(result["input"], str) or result["input"] != entry["raw"]:
    return False
  if not all(_optional_string(result[field]) for field in (
      "doi", "matched_title", "source", "retraction_source",
  )):
    return False
  if not isinstance(result["retraction_checked"], bool):
    return False
  if result["retraction_status"] not in {
      "complete", "partial", "unavailable", "not_applicable",
  }:
    return False
  if result["resolution_status"] not in {"complete", "partial", "unavailable"}:
    return False
  if (isinstance(result["entry_index"], bool)
      or result["entry_index"] != index):
    return False
  identity = result["input_identity"]
  if (not isinstance(identity, str) or not _SHA256_RE.fullmatch(identity)
      or identity != verify_citations.citation_input_identity(entry)):
    return False
  status = result["status"]
  audit = result["retraction_status"]
  if status in {"not_found", "unavailable"}:
    expected_audit = "not_applicable" if status == "not_found" else "unavailable"
    expected_resolution = "complete" if status == "not_found" else "unavailable"
    if (audit != expected_audit or result["retraction_checked"]
        or result["resolution_status"] != expected_resolution):
      return False
  elif status == "retracted":
    if audit != "complete" or not result["retraction_checked"]:
      return False
  else:
    if (audit == "not_applicable"
        or result["retraction_checked"] != (audit == "complete")):
      return False
  return True


def _expected_response_status(results: list[dict]) -> str:
  unavailable = sum(result["status"] == "unavailable" for result in results)
  if results and unavailable == len(results):
    return "unavailable"
  if unavailable or any(
      result["status"] in {"verified", "mismatched"}
      and result["retraction_status"] in {"partial", "unavailable"}
      for result in results
  ) or any(result["resolution_status"] in {"partial", "unavailable"}
           for result in results):
    return "partial"
  return "complete"


def _valid_citation_report(report: object, bibliography: object) -> tuple[bool, list]:
  required = {
      "total", *_CITATION_STATUSES, "resolver", "checked_at",
      "response_status", "bibliography_sha256", "results",
  }
  if not isinstance(report, dict) or not required <= set(report):
    return False, []
  if not isinstance(bibliography, list):
    return False, []
  entries = bibliography
  if not isinstance(report["resolver"], str) or not report["resolver"]:
    return False, entries
  if not _aware_utc_timestamp(report["checked_at"]):
    return False, entries
  if report["response_status"] not in {"complete", "partial", "unavailable"}:
    return False, entries
  digest = report["bibliography_sha256"]
  try:
    expected_digest = verify_citations.bibliography_sha256(entries)
  except (TypeError, ValueError):
    return False, entries
  if (not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest)
      or digest != expected_digest):
    return False, entries
  if not all(_count(report[status]) for status in _CITATION_STATUSES):
    return False, entries
  results = report["results"]
  if (not isinstance(results, list) or len(results) != len(entries)
      or not all(_valid_citation_result(result, entry, index)
                 for index, (result, entry) in enumerate(zip(results, entries)))):
    return False, entries
  if (not _count(report["total"]) or report["total"] != len(results)
      or sum(report[status] for status in _CITATION_STATUSES) != len(results)):
    return False, entries
  for status in _CITATION_STATUSES:
    if report[status] != sum(result["status"] == status for result in results):
      return False, entries
  if report["response_status"] != _expected_response_status(results):
    return False, entries
  return True, entries


def citation_findings(
    report: dict | None, bibliography: list | None = None,
) -> tuple[Finding, ...]:
  """Map an explicit citation report without constructing a resolver."""
  if report is None:
    if bibliography == []:
      return ()
    if isinstance(bibliography, list) and bibliography:
      return (Finding(
          reason_code=ReasonCode.CITATION_RESOLUTION_UNAVAILABLE,
          severity=Severity.WARNING,
          artifact="refs.json",
          message="external citation resolution was not supplied",
          context={"response_status": "unavailable"},
      ),)
    return (_incomplete("citation", "refs.json"),)
  valid, _entries = _valid_citation_report(report, bibliography)
  if not valid:
    return (_incomplete("citation", "refs.json"),)
  results = report["results"]
  response_status = report["response_status"]
  findings = []
  has_resolution_warning = False
  for index, result in enumerate(results):
    if not isinstance(result, dict):
      findings.append(_incomplete("citation", "refs.json"))
      continue
    status = result.get("status")
    if not isinstance(status, str):
      findings.append(_incomplete("citation", "refs.json"))
      continue
    if status == "retracted":
      findings.append(_citation_finding(
          ReasonCode.CITATION_RETRACTED, Severity.CRITICAL,
          "citation resolves to a retracted publication", result, index))
    elif status in {"mismatched", "not_found"}:
      findings.append(_citation_finding(
          ReasonCode.CITATION_IDENTITY_MISMATCH, Severity.CRITICAL,
          "citation does not resolve to the declared publication",
          result, index))
    elif status == "unavailable":
      has_resolution_warning = True
      findings.append(_citation_finding(
          ReasonCode.CITATION_RESOLUTION_UNAVAILABLE, Severity.WARNING,
          "citation resolver could not provide an authoritative answer",
          result, index))
    elif status == "verified":
      if not result["retraction_checked"]:
        has_resolution_warning = True
        findings.append(_citation_finding(
            ReasonCode.CITATION_RESOLUTION_UNAVAILABLE, Severity.WARNING,
            "verified citation was not checked authoritatively for retraction",
            result, index))
      missing = [field for field in ("doi", "matched_title", "source")
                 if not result.get(field)]
      if missing:
        findings.append(_citation_finding(
            ReasonCode.BIBLIOGRAPHY_INCOMPLETE, Severity.WARNING,
            "verified bibliography entry has incomplete metadata",
            result, index, {"missing_fields": missing}))
    else:
      findings.append(_incomplete("citation", "refs.json"))
  if response_status in {"partial", "unavailable"} and not has_resolution_warning:
    findings.append(Finding(
        reason_code=ReasonCode.CITATION_RESOLUTION_UNAVAILABLE,
        severity=Severity.WARNING,
        artifact="refs.json",
        message="citation resolver response was incomplete",
        context={"response_status": response_status},
    ))
  return tuple(findings)


def prisma_findings(
    report: dict, records: list[dict] | None = None,
) -> tuple[Finding, ...]:
  """Map PRISMA output into stable completeness findings."""
  required = {
      "records_by_source", "after_dedup", "screened", "excluded",
      "included", "not_retrieved", "in_synthesis",
  }
  if not isinstance(report, dict) or not required <= set(report):
    return (_incomplete("prisma", "corpus.json"),)
  records_by_source = report["records_by_source"]
  excluded = report["excluded"]
  if (not isinstance(records_by_source, dict) or not isinstance(excluded, dict)
      or not all(isinstance(source, str) and _count(count)
                 for source, count in records_by_source.items())
      or not all(isinstance(reason, str) and _count(count)
                 for reason, count in excluded.items())
      or not all(_count(report[field]) for field in (
          "after_dedup", "screened", "included", "not_retrieved",
          "in_synthesis",
      ))):
    return (_incomplete("prisma", "corpus.json"),)
  if (sum(records_by_source.values()) != report["after_dedup"]
      or report["screened"] > report["after_dedup"]
      or sum(excluded.values()) + report["included"] != report["screened"]
      or report["not_retrieved"] > report["included"]
      or report["in_synthesis"]
      != report["included"] - report["not_retrieved"]):
    return (_incomplete("prisma", "corpus.json"),)
  if report["screened"] != report["after_dedup"]:
    context = {"validator": "prisma"}
    if isinstance(records, list):
      context["unscreened_indices"] = [
          index for index, record in enumerate(records)
          if isinstance(record, dict)
          and (record.get("screening") or {}).get("status") is None
      ]
    return (Finding(
        reason_code=ReasonCode.VALIDATOR_INCOMPLETE,
        severity=Severity.CRITICAL,
        artifact="corpus.json",
        message="prisma validator did not produce an interpretable result",
        context=context,
    ),)
  count = excluded.get("unspecified", 0)
  if not count:
    return ()
  context = {"count": count}
  if isinstance(records, list):
    context["decision_indices"] = [
        index for index, record in enumerate(records)
        if isinstance(record, dict)
        and (record.get("screening") or {}).get("status") == "excluded"
        and not (record.get("screening") or {}).get("reason")
    ]
  return (Finding(
      reason_code=ReasonCode.PRISMA_EXCLUSION_REASON_MISSING,
      severity=Severity.WARNING,
      artifact="corpus.json",
      message="excluded review records are missing exclusion reasons",
      context=context,
  ),)


def artifact_findings(snapshot: WorkspaceSnapshot) -> tuple[Finding, ...]:
  """Report semantic issues and source scope using retained snapshot bytes."""
  if not isinstance(snapshot, WorkspaceSnapshot):
    raise ValueError("snapshot must be a WorkspaceSnapshot")
  findings = []
  expectations = (
      ("protocol.md", "text"), ("corpus.json", "object_list"),
      ("claims.json", "nonempty_object_list"), ("synthesis.md", "text"),
      ("refs.json", "list"),
  )
  for relative_path, kind in expectations:
    malformed = False
    try:
      value = (snapshot.read_text(relative_path) if kind == "text"
               else snapshot.read_json(relative_path))
      if kind == "text":
        malformed = not value.strip()
      elif kind == "list":
        malformed = not isinstance(value, list)
      elif kind == "object_list":
        malformed = (not isinstance(value, list)
                     or not all(isinstance(item, dict) for item in value))
      else:
        malformed = (not isinstance(value, list) or not value
                     or not all(isinstance(item, dict) for item in value))
    except Exception:
      malformed = True
    if malformed:
      findings.append(Finding(
          reason_code=ReasonCode.ARTIFACT_MALFORMED,
          severity=Severity.CRITICAL,
          artifact=relative_path,
          message="submitted artifact is not semantically valid",
          context={"artifact": relative_path},
      ))
  for artifact in snapshot.files:
    if (artifact.preferred_for_claims
        and artifact.relative_path.endswith("/abstract.md")):
      paper_id = artifact.relative_path.split("/", 2)[1]
      findings.append(Finding(
          reason_code=ReasonCode.ABSTRACT_ONLY_SUPPORT,
          severity=Severity.WARNING,
          artifact=artifact.relative_path,
          message="preferred claim source is abstract-only",
          context={"paper_id": paper_id, "source_scope": "abstract"},
      ))
  return tuple(findings)


def _snapshot_sources(snapshot: WorkspaceSnapshot) -> tuple[dict[str, str], dict[str, str]]:
  texts = {}
  scopes = {}
  for artifact in snapshot.files:
    if not artifact.preferred_for_claims:
      continue
    parts = artifact.relative_path.split("/")
    if len(parts) != 3 or parts[0] != "papers":
      continue
    paper_id = parts[1]
    texts[paper_id] = snapshot.read_text(artifact.relative_path)
    scopes[paper_id] = (
        "abstract" if parts[2] == "abstract.md" else "fulltext")
  return texts, scopes


def validate_snapshot(
    snapshot: WorkspaceSnapshot, citation_report: dict | None = None,
) -> tuple[Finding, ...]:
  """Execute all adapters in stable order and fail closed per adapter."""
  findings = []

  def run(name: str, artifact: str, operation: Callable[[], tuple]) -> None:
    try:
      result = operation()
      if not isinstance(result, tuple) or not all(
          isinstance(item, Finding) for item in result):
        raise ValueError("adapter returned malformed findings")
      findings.extend(result)
    except Exception:
      findings.append(_incomplete(name, artifact))

  run("artifact", "workspace", lambda: artifact_findings(snapshot))

  def claims() -> tuple[Finding, ...]:
    entries = snapshot.read_json("claims.json")
    corpus = snapshot.read_json("corpus.json")
    references = snapshot.read_json("refs.json")
    synthesis = snapshot.read_text("synthesis.md")
    source_texts, source_scopes = _snapshot_sources(snapshot)
    corpus = check_claims.corpus_with_source_scopes(corpus, source_scopes)
    report = check_claims.check_claims_document(
        entries, corpus, source_texts, synthesis, references)
    return claim_findings(report)

  run("claim", "claims.json", claims)
  def citations() -> tuple[Finding, ...]:
    references = snapshot.read_json("refs.json")
    entries = verify_citations.normalize_citation_entries(references)
    return citation_findings(citation_report, entries)

  run("citation", "refs.json", citations)

  def prisma() -> tuple[Finding, ...]:
    records = snapshot.read_json("corpus.json")
    return prisma_findings(prisma_counts.prisma_report(records), records)

  run("prisma", "corpus.json", prisma)
  return tuple(findings)


__all__ = [
    "artifact_findings", "citation_findings", "claim_findings",
    "prisma_findings", "validate_snapshot",
]
