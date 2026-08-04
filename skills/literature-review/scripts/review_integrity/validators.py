"""Pure adapters from literature validators to stable integrity findings."""

from __future__ import annotations

from typing import Callable

import check_claims
import prisma_counts

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
  context = {"result_index": index}
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


def claim_findings(report: dict) -> tuple[Finding, ...]:
  """Map a claim-checker report into closed, stable findings."""
  if not isinstance(report, dict) or not isinstance(report.get("results"), list):
    return (_incomplete("claim", "claims.json"),)
  results = report["results"]
  if ("total" in report
      and (isinstance(report["total"], bool)
           or not isinstance(report["total"], int)
           or report["total"] != len(results))):
    return (_incomplete("claim", "claims.json"),)
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
              "retraction_source"):
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


def citation_findings(report: dict | None) -> tuple[Finding, ...]:
  """Map an explicit citation report without constructing a resolver."""
  if report is None:
    return (Finding(
        reason_code=ReasonCode.CITATION_RESOLUTION_UNAVAILABLE,
        severity=Severity.WARNING,
        artifact="refs.json",
        message="citation resolution report was not supplied",
        context={"response_status": "unavailable"},
    ),)
  if not isinstance(report, dict) or not isinstance(report.get("results"), list):
    return (_incomplete("citation", "refs.json"),)
  results = report["results"]
  response_status = report.get("response_status", "complete")
  if (not isinstance(response_status, str)
      or response_status not in {"complete", "partial", "unavailable"}):
    return (_incomplete("citation", "refs.json"),)
  if ("total" in report
      and (isinstance(report["total"], bool)
           or not isinstance(report["total"], int)
           or report["total"] != len(results))):
    return (_incomplete("citation", "refs.json"),)
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
      if not isinstance(result.get("retraction_checked"), bool):
        findings.append(_incomplete("citation", "refs.json"))
        continue
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


def prisma_findings(report: dict) -> tuple[Finding, ...]:
  """Map PRISMA output into stable completeness findings."""
  if not isinstance(report, dict) or not isinstance(report.get("excluded"), dict):
    return (_incomplete("prisma", "corpus.json"),)
  excluded = report["excluded"]
  if not all(isinstance(reason, str)
             and not isinstance(count, bool)
             and isinstance(count, int) and count >= 0
             for reason, count in excluded.items()):
    return (_incomplete("prisma", "corpus.json"),)
  count = excluded.get("unspecified", 0)
  if not count:
    return ()
  return (Finding(
      reason_code=ReasonCode.PRISMA_EXCLUSION_REASON_MISSING,
      severity=Severity.WARNING,
      artifact="corpus.json",
      message="excluded review records are missing exclusion reasons",
      context={"count": count},
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


def _source_texts(snapshot: WorkspaceSnapshot) -> check_claims.SourceTexts:
  texts = check_claims.SourceTexts()
  for artifact in snapshot.files:
    if not artifact.preferred_for_claims:
      continue
    parts = artifact.relative_path.split("/")
    if len(parts) != 3 or parts[0] != "papers":
      continue
    paper_id = parts[1]
    texts[paper_id] = snapshot.read_text(artifact.relative_path)
    texts.scopes[paper_id] = (
        "abstract" if parts[2] == "abstract.md" else "fulltext")
  return texts


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
    report = check_claims.check_claims_document(
        entries, corpus, _source_texts(snapshot), synthesis, references)
    return claim_findings(report)

  run("claim", "claims.json", claims)
  run("citation", "refs.json", lambda: citation_findings(citation_report))

  def prisma() -> tuple[Finding, ...]:
    records = snapshot.read_json("corpus.json")
    return prisma_findings(prisma_counts.prisma_report(records))

  run("prisma", "corpus.json", prisma)
  return tuple(findings)


__all__ = [
    "artifact_findings", "citation_findings", "claim_findings",
    "prisma_findings", "validate_snapshot",
]
