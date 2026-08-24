"""Deterministic unit scoring for immutable literature-review snapshots."""

from __future__ import annotations

import json
from typing import Iterable

import check_claims
import verify_citations

from .models import (
    DIMENSION_ORDER,
    DIMENSION_WEIGHTS,
    DimensionResult,
    Finding,
    PassReport,
    ReasonCode,
    Severity,
)
from .workspace import WorkspaceSnapshot


_CLAIM_DIMENSIONS = (
    "quote_authenticity", "citation_binding", "quantitative_grounding",
    "synthesis_coverage",
)
_ARTIFACT_REASONS = frozenset({
    ReasonCode.ARTIFACT_MISSING,
    ReasonCode.ARTIFACT_MALFORMED,
    ReasonCode.ARTIFACT_SYMLINK,
    ReasonCode.ARTIFACT_TRAVERSAL,
    ReasonCode.ARTIFACT_TYPE_INVALID,
    ReasonCode.ARTIFACT_SIZE_LIMIT,
    ReasonCode.MANIFEST_MISMATCH,
})
_QUOTE_REASONS = frozenset({
    ReasonCode.FABRICATED_QUOTE,
    ReasonCode.CLAIM_NEEDS_REVIEW,
    ReasonCode.ABSTRACT_ONLY_SUPPORT,
})
_BINDING_REASONS = frozenset({
    ReasonCode.CITATION_IDENTITY_MISMATCH,
    ReasonCode.CITATION_AMBIGUOUS,
})
_COVERAGE_REASONS = frozenset({
    ReasonCode.COVERAGE_NUMBER_MISSING,
    ReasonCode.COVERAGE_CLAIM_MISSING,
    ReasonCode.COVERAGE_ROLE_INVALID,
})
_FIXED_ARTIFACTS = (
    "protocol.md", "corpus.json", "claims.json", "synthesis.md", "refs.json",
)


def _finding_key(finding: Finding) -> str:
  return json.dumps(
      finding.to_dict(), ensure_ascii=False, sort_keys=True,
      separators=(",", ":"))


def _ordered_findings(findings: Iterable[Finding]) -> tuple[Finding, ...]:
  return tuple(sorted(findings, key=_finding_key))


def _incomplete(validator: str, artifact: str, **context: object) -> Finding:
  return Finding(
      reason_code=ReasonCode.VALIDATOR_INCOMPLETE,
      severity=Severity.CRITICAL,
      artifact=artifact,
      message=f"{validator} validator did not produce an interpretable result",
      context={"validator": validator, **context},
  )


def _malformed(artifact: str) -> Finding:
  return Finding(
      reason_code=ReasonCode.ARTIFACT_MALFORMED,
      severity=Severity.CRITICAL,
      artifact=artifact,
      message="submitted artifact is not semantically valid",
      context={"artifact": artifact},
  )


def _claim_entries(value: object) -> list[dict] | None:
  if not isinstance(value, list) or not value:
    return None
  required = ("claim", "paper_id", "citation", "supporting_quote")
  for entry in value:
    if not isinstance(entry, dict):
      return None
    if any(not isinstance(entry.get(field), str) or not entry[field].strip()
           for field in required):
      return None
    if entry.get("role", "evidence") not in {"evidence", "background"}:
      return None
  return value


def _read_json(snapshot: WorkspaceSnapshot, relative_path: str) -> object:
  return snapshot.read_json(relative_path)


def _append_once(findings: list[Finding], finding: Finding) -> None:
  key = _finding_key(finding)
  if all(_finding_key(existing) != key for existing in findings):
    findings.append(finding)


def _ensure_incomplete(
    findings: list[Finding], validator: str, artifact: str, **context: object,
) -> None:
  if any(
      finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE
      and finding.context.get("validator") == validator
      for finding in findings
  ):
    return
  _append_once(findings, _incomplete(validator, artifact, **context))


def _ensure_malformed(findings: list[Finding], artifact: str) -> None:
  if any(finding.reason_code is ReasonCode.ARTIFACT_MALFORMED
         and finding.artifact == artifact for finding in findings):
    return
  _append_once(findings, _malformed(artifact))


def _artifact_dependencies(relative_path: str) -> tuple[str, ...]:
  dependencies = {
      "claims.json": _CLAIM_DIMENSIONS,
      "corpus.json": (*_CLAIM_DIMENSIONS, "prisma_artifact_completeness"),
      "synthesis.md": ("synthesis_coverage",),
      "refs.json": (
          "citation_binding", "synthesis_coverage",
          "bibliography_verification"),
  }
  return dependencies.get(relative_path, ())


def _strict_index(value: object, upper_bound: int) -> int | None:
  """Return an in-range unit index; booleans are never integer indices."""
  if type(value) is not int or not 0 <= value < upper_bound:
    return None
  return value


def score_integrity(
    snapshot: WorkspaceSnapshot, findings: tuple[Finding, ...],
) -> PassReport:
  """Score explicit units using only retained bytes and stable findings."""
  if not isinstance(snapshot, WorkspaceSnapshot):
    raise ValueError("snapshot must be a WorkspaceSnapshot")
  if not isinstance(findings, tuple) or not all(
      isinstance(finding, Finding) for finding in findings):
    raise ValueError("findings must be a tuple of Finding values")
  all_findings = list(findings)

  claims: list[dict] = []
  claims_valid = False
  try:
    parsed_claims = _claim_entries(_read_json(snapshot, "claims.json"))
    if parsed_claims is None:
      raise ValueError("malformed claims")
    claims = parsed_claims
    claims_valid = True
  except Exception:
    _ensure_malformed(all_findings, "claims.json")
    _ensure_incomplete(all_findings, "claim", "claims.json")

  refs: list = []
  refs_valid = False
  try:
    parsed_refs = _read_json(snapshot, "refs.json")
    if not isinstance(parsed_refs, list):
      raise ValueError("malformed references")
    verify_citations.normalize_citation_entries(parsed_refs)
    refs = parsed_refs
    refs_valid = True
  except Exception:
    _ensure_malformed(all_findings, "refs.json")
    _ensure_incomplete(all_findings, "citation", "refs.json")

  corpus: list[dict] = []
  corpus_valid = False
  try:
    parsed_corpus = _read_json(snapshot, "corpus.json")
    if not isinstance(parsed_corpus, list) or not all(
        isinstance(record, dict) for record in parsed_corpus):
      raise ValueError("malformed corpus")
    corpus = parsed_corpus
    corpus_valid = True
  except Exception:
    _ensure_malformed(all_findings, "corpus.json")
    _ensure_incomplete(all_findings, "prisma", "corpus.json")
    _ensure_incomplete(all_findings, "claim", "claims.json")

  synthesis = ""
  coverage_sentences: list[tuple[str, frozenset[str]]] = []
  coverage_units: set[tuple[int, str]] = set()
  synthesis_valid = False
  try:
    synthesis = snapshot.read_text("synthesis.md")
    if not synthesis.strip():
      raise ValueError("empty synthesis")
    for sentence_index, sentence in enumerate(
        check_claims._split_sentences(synthesis)):
      stripped = sentence.strip()
      identities = frozenset({
          record["key"] for record in check_claims._citation_records(sentence)
      })
      coverage_sentences.append((stripped, identities))
      for identity in identities:
        coverage_units.add((sentence_index, identity))
    if not coverage_units:
      raise ValueError("synthesis has no supported citations")
    synthesis_valid = True
  except Exception:
    _ensure_malformed(all_findings, "synthesis.md")
    _ensure_incomplete(all_findings, "claim", "claims.json")

  try:
    if not snapshot.read_text("protocol.md").strip():
      raise ValueError("empty protocol")
  except Exception:
    _ensure_malformed(all_findings, "protocol.md")
    _ensure_incomplete(all_findings, "artifact", "workspace")

  quote_units = {index for index in range(len(claims))}
  binding_units = set(quote_units)
  numeric_units = {
      (index, occurrence, number)
      for index, claim in enumerate(claims)
      for occurrence, number in enumerate(check_claims.extract_numbers(
          check_claims._strip_citations(
              claim["claim"], check_claims._citation_records(claim["claim"]))))
  }
  bibliography_units = set(range(len(refs)))

  artifact_units: set[tuple[str, object]] = {
      ("artifact", relative_path) for relative_path in _FIXED_ARTIFACTS}
  snapshot_paths = {artifact.relative_path for artifact in snapshot.files}
  project_links = snapshot_paths & {"project.json", "run-manifest.json"}
  if len(project_links) == 1:
    artifact_units.add(("artifact", next(iter(project_links))))
  else:
    _ensure_incomplete(all_findings, "artifact", "workspace")
  for artifact in snapshot.files:
    if artifact.preferred_for_claims:
      artifact_units.add(("artifact", artifact.relative_path))

  if corpus_valid:
    unscreened = []
    for index, record in enumerate(corpus):
      screening = record.get("screening")
      if not isinstance(screening, dict):
        unscreened.append(index)
        continue
      status = screening.get("status")
      if status in {"included", "excluded"}:
        artifact_units.add(("decision", index))
      else:
        unscreened.append(index)
    if unscreened:
      _ensure_incomplete(
          all_findings, "prisma", "corpus.json",
          unscreened_indices=unscreened)

  units: dict[str, set] = {
      "quote_authenticity": quote_units,
      "citation_binding": binding_units,
      "quantitative_grounding": numeric_units,
      "synthesis_coverage": coverage_units,
      "bibliography_verification": bibliography_units,
      "prisma_artifact_completeness": artifact_units,
  }
  failed: dict[str, set] = {name: set() for name in DIMENSION_ORDER}
  zeroed: set[str] = set()
  relevant: dict[str, list[Finding]] = {
      name: [] for name in DIMENSION_ORDER}

  def attach(name: str, finding: Finding) -> None:
    if all(_finding_key(existing) != _finding_key(finding)
           for existing in relevant[name]):
      relevant[name].append(finding)

  def fail_unit(name: str, unit: object, finding: Finding) -> bool:
    attach(name, finding)
    if unit not in units[name]:
      return False
    failed[name].add(unit)
    return True

  def zero(name: str, finding: Finding) -> None:
    attach(name, finding)
    zeroed.add(name)

  for finding in _ordered_findings(all_findings):
    reason = finding.reason_code
    context = finding.context
    mapped = False

    if reason is ReasonCode.VALIDATOR_INCOMPLETE:
      validator = context.get("validator")
      has_result_index = "result_index" in context
      result_index = _strict_index(
          context.get("result_index"), len(claims))
      if validator == "claim" and has_result_index and result_index is not None:
        mapped |= fail_unit("quote_authenticity", result_index, finding)
        for unit in numeric_units:
          if unit[0] == result_index:
            mapped |= fail_unit("quantitative_grounding", unit, finding)
      elif validator == "claim":
        for name in _CLAIM_DIMENSIONS:
          zero(name, finding)
        mapped = True
      elif validator == "citation":
        zero("bibliography_verification", finding)
        mapped = True
      elif validator in {"prisma", "artifact"}:
        zero("prisma_artifact_completeness", finding)
        mapped = True
      elif validator is not None:
        dependencies = _artifact_dependencies(finding.artifact)
        if dependencies:
          for name in dependencies:
            zero(name, finding)
          mapped = True

    has_result_index = "result_index" in context
    result_index = _strict_index(context.get("result_index"), len(claims))
    if (finding.artifact == "claims.json"
        and result_index is not None):
      if reason in _QUOTE_REASONS | {ReasonCode.VALIDATOR_INCOMPLETE}:
        mapped |= fail_unit("quote_authenticity", result_index, finding)
      if reason in _BINDING_REASONS:
        mapped |= fail_unit("citation_binding", result_index, finding)
      missing = context.get("numbers_missing")
      if isinstance(missing, (list, tuple)):
        missing_occurrences: dict[object, int] = {}
        for number in missing:
          ordinal = missing_occurrences.get(number, 0)
          candidates = sorted(
              (unit for unit in numeric_units
               if unit[0] == result_index and unit[2] == number),
              key=lambda unit: unit[1])
          if ordinal < len(candidates):
            mapped |= fail_unit(
                "quantitative_grounding", candidates[ordinal], finding)
          missing_occurrences[number] = ordinal + 1
      if reason is ReasonCode.FABRICATED_QUOTE:
        for unit in numeric_units:
          if unit[0] == result_index:
            mapped |= fail_unit("quantitative_grounding", unit, finding)
      if reason is ReasonCode.VALIDATOR_INCOMPLETE:
        for unit in numeric_units:
          if unit[0] == result_index:
            mapped |= fail_unit("quantitative_grounding", unit, finding)

    if (reason in _QUOTE_REASONS
        and finding.artifact == "claims.json" and not mapped):
      zero("quote_authenticity", finding)
      if reason is ReasonCode.FABRICATED_QUOTE:
        zero("quantitative_grounding", finding)
      mapped = True

    if (reason in _BINDING_REASONS
        and finding.artifact == "claims.json" and not mapped):
      zero("citation_binding", finding)
      mapped = True

    if (reason is ReasonCode.VALIDATOR_INCOMPLETE
        and finding.artifact == "claims.json" and has_result_index
        and result_index is None and not mapped):
      for name in _CLAIM_DIMENSIONS:
        zero(name, finding)
      mapped = True

    if reason in _COVERAGE_REASONS:
      sentence = context.get("synthesis_sentence")
      identity = context.get("citation_identity")
      sentence_index = _strict_index(
          context.get("synthesis_sentence_index"), len(coverage_sentences))
      context_matches = (
          sentence_index is not None
          and isinstance(sentence, str)
          and isinstance(identity, str)
          and coverage_sentences[sentence_index][0] == sentence
          and identity in coverage_sentences[sentence_index][1]
      )
      if context_matches:
        mapped |= fail_unit(
            "synthesis_coverage", (sentence_index, identity), finding)
      if not mapped:
        zero("synthesis_coverage", finding)
        mapped = True

    if finding.artifact == "refs.json":
      bibliography_index = _strict_index(
          context.get("result_index"), len(bibliography_units))
      if bibliography_index is not None:
        mapped |= fail_unit(
            "bibliography_verification", bibliography_index, finding)
      elif "result_index" in context:
        zero("bibliography_verification", finding)
        mapped = True
      elif reason is ReasonCode.CITATION_RESOLUTION_UNAVAILABLE:
        zero("bibliography_verification", finding)
        mapped = True
      elif finding.severity is Severity.CRITICAL:
        zero("bibliography_verification", finding)
        mapped = True
      else:
        attach("bibliography_verification", finding)
        mapped = True

    if reason is ReasonCode.PRISMA_EXCLUSION_REASON_MISSING:
      indices = context.get("decision_indices")
      if not isinstance(indices, (list, tuple)):
        indices = [
            index for index, record in enumerate(corpus)
            if isinstance(record.get("screening"), dict)
            and record["screening"].get("status") == "excluded"
            and not record["screening"].get("reason")
        ]
      valid_decisions = {
          unit[1] for unit in artifact_units if unit[0] == "decision"}
      parsed_indices = [
          _strict_index(index, len(corpus)) for index in indices]
      if (any(index is None for index in parsed_indices)
          or any(index not in valid_decisions for index in parsed_indices)):
        zero("prisma_artifact_completeness", finding)
        mapped = True
      else:
        for index in parsed_indices:
          mapped |= fail_unit(
              "prisma_artifact_completeness", ("decision", index), finding)
      if not mapped:
        zero("prisma_artifact_completeness", finding)
        mapped = True

    if reason in _ARTIFACT_REASONS:
      relative_path = context.get("artifact", finding.artifact)
      if isinstance(relative_path, str):
        mapped |= fail_unit(
            "prisma_artifact_completeness",
            ("artifact", relative_path), finding)
        for name in _artifact_dependencies(relative_path):
          zero(name, finding)
          mapped = True
      if reason is ReasonCode.MANIFEST_MISMATCH:
        zero("prisma_artifact_completeness", finding)
        mapped = True

    if not mapped and finding.severity is Severity.CRITICAL:
      for name in DIMENSION_ORDER:
        zero(name, finding)

  claim_incomplete = any(
      finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE
      and finding.context.get("validator") == "claim"
      for finding in all_findings)
  citation_incomplete = any(
      finding.reason_code is ReasonCode.VALIDATOR_INCOMPLETE
      and finding.context.get("validator") == "citation"
      for finding in all_findings)

  applicable = {name: True for name in DIMENSION_ORDER}
  if claims_valid and not numeric_units and not claim_incomplete:
    applicable["quantitative_grounding"] = False
  if refs_valid and not bibliography_units and not citation_incomplete:
    applicable["bibliography_verification"] = False
  if not synthesis_valid:
    applicable["synthesis_coverage"] = True

  nominal_total = sum(
      DIMENSION_WEIGHTS[name] for name in DIMENSION_ORDER if applicable[name])
  dimensions = {}
  for name in DIMENSION_ORDER:
    if not applicable[name]:
      dimensions[name] = DimensionResult(
          name=name, score=None, applicable=False,
          evaluated_units=0, passed_units=0,
          nominal_weight=DIMENSION_WEIGHTS[name], effective_weight=0.0,
          findings=_ordered_findings(relevant[name]),
      )
      continue
    evaluated = len(units[name])
    passed = 0 if name in zeroed else evaluated - len(failed[name])
    score = 0.0 if evaluated == 0 else 100.0 * passed / evaluated
    dimensions[name] = DimensionResult(
        name=name, score=score, applicable=True,
        evaluated_units=evaluated, passed_units=passed,
        nominal_weight=DIMENSION_WEIGHTS[name],
        effective_weight=DIMENSION_WEIGHTS[name] * 100.0 / nominal_total,
        findings=_ordered_findings(relevant[name]),
    )

  integrity_score = sum(
      dimension.nominal_weight * (dimension.unrounded_score or 0.0)
      for dimension in dimensions.values() if dimension.applicable
  ) / nominal_total
  ordered = _ordered_findings(all_findings)
  return PassReport(
      integrity_score=integrity_score,
      findings=ordered,
      dimensions=dimensions,
      manifest_sha256=snapshot.manifest_sha256,
  )


__all__ = ["score_integrity"]
