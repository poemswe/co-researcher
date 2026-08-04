"""Pure deterministic rendering for one-pass integrity validation reports."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Mapping

from .models import DIMENSION_ORDER, PassReport


SCHEMA_VERSION = "1.0.0"
ENGINE_VERSION = "1.0.0"
CLAIMS_VALIDATOR_VERSION = "1.0.0"
CITATION_VALIDATOR_VERSION = "1.0.0"
PRISMA_VALIDATOR_VERSION = "1.0.0"
ARTIFACT_SCORING_VERSION = "1.0.0"
VALIDATOR_VERSIONS = {
    "claims": CLAIMS_VALIDATOR_VERSION,
    "citation": CITATION_VALIDATOR_VERSION,
    "prisma": PRISMA_VALIDATOR_VERSION,
    "artifact_scoring": ARTIFACT_SCORING_VERSION,
}

_TOP_LEVEL_ORDER = (
    "schema_version", "engine_version", "quality_score", "target_commit",
    "target_dirty", "validator_versions", "manifest_sha256",
    "workspace_manifest_sha256", "citation_report_sha256", "dimensions",
    "findings", "integrity_score", "status", "citation_resolution",
)
_TOP_LEVEL_FIELDS = frozenset(_TOP_LEVEL_ORDER)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
_INVALID_WARNING = (
    "INVALID EVIDENCE — This draft contains unresolved evidence-integrity "
    "failures\nand must not be treated as verified research."
)
_SYNTHESIS_EXCERPT_LIMIT = 2000
_FINDING_ORDER = (
    "schema_version", "reason_code", "severity", "artifact", "message",
    "context",
)
_DIMENSION_FIELD_ORDER = (
    "schema_version", "name", "score", "applicable", "evaluated_units",
    "passed_units", "nominal_weight", "effective_weight", "findings",
)


def _require_hash(value: object, field: str, *, nullable: bool = False) -> None:
  if nullable and value is None:
    return
  if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
    raise ValueError(f"{field} must be a lowercase SHA-256 hash")


def combined_manifest_sha256(
    workspace_manifest_sha256: str,
    citation_report_sha256: str | None,
) -> str:
  """Hash the two fixed validation-input records in canonical JSON."""
  _require_hash(workspace_manifest_sha256, "workspace_manifest_sha256")
  _require_hash(
      citation_report_sha256, "citation_report_sha256", nullable=True)
  records = [{"workspace_manifest_sha256": workspace_manifest_sha256}]
  if citation_report_sha256 is None:
    records.append({"citation_report": None})
  else:
    records.append({"citation_report_sha256": citation_report_sha256})
  canonical = json.dumps(
      records, ensure_ascii=False, sort_keys=True,
      separators=(",", ":")).encode("utf-8")
  return hashlib.sha256(canonical).hexdigest()


def validate_report(report: object) -> dict:
  """Validate the closed top-level wire schema without changing it."""
  if type(report) is not dict or set(report) != _TOP_LEVEL_FIELDS:
    raise ValueError("validation report has unknown or missing fields")
  if report["schema_version"] != SCHEMA_VERSION:
    raise ValueError("unsupported validation report schema version")
  if report["engine_version"] != ENGINE_VERSION:
    raise ValueError("unsupported validation engine version")
  if report["quality_score"] is not None:
    raise ValueError("one-pass validation quality_score must be null")
  commit = report["target_commit"]
  if commit is not None and (not isinstance(commit, str)
                             or not _COMMIT_RE.fullmatch(commit)):
    raise ValueError("target_commit must be lowercase Git commit or null")
  dirty = report["target_dirty"]
  if dirty is not None and type(dirty) is not bool:
    raise ValueError("target_dirty must be boolean or null")
  if (commit is None) != (dirty is None):
    raise ValueError("target_commit and target_dirty must share availability")
  if report["validator_versions"] != VALIDATOR_VERSIONS:
    raise ValueError("validator_versions do not match this engine")
  _require_hash(report["manifest_sha256"], "manifest_sha256")
  _require_hash(
      report["workspace_manifest_sha256"], "workspace_manifest_sha256")
  _require_hash(
      report["citation_report_sha256"], "citation_report_sha256",
      nullable=True)
  if type(report["dimensions"]) is not dict:
    raise ValueError("dimensions must be an object")
  if tuple(report["dimensions"]) != DIMENSION_ORDER:
    raise ValueError("dimensions must contain the complete stable order")
  if type(report["findings"]) is not list:
    raise ValueError("findings must be an array")
  score = report["integrity_score"]
  if (isinstance(score, bool) or not isinstance(score, (int, float))
      or not math.isfinite(score) or not 0 <= score <= 100):
    raise ValueError("integrity_score must be finite and in range")
  if report["status"] not in {"valid", "valid_with_warnings", "invalid"}:
    raise ValueError("unknown validation status")
  citation = report["citation_resolution"]
  if type(citation) is not dict or set(citation) != {
      "source", "resolver", "checked_at", "response_status",
  }:
    raise ValueError("citation_resolution has unknown or missing fields")
  if citation["source"] not in {"supplied_report", "not_supplied"}:
    raise ValueError("unknown citation resolution provenance")
  if citation["resolver"] is not None and not isinstance(
      citation["resolver"], str):
    raise ValueError("citation resolver must be a string or null")
  if citation["checked_at"] is not None and not isinstance(
      citation["checked_at"], str):
    raise ValueError("citation checked_at must be a string or null")
  if citation["response_status"] not in {
      "complete", "partial", "unavailable", "not_applicable", "malformed",
  }:
    raise ValueError("unknown citation response status")
  if citation["source"] == "supplied_report":
    if report["citation_report_sha256"] is None:
      raise ValueError("supplied citation provenance requires its hash")
    if citation["response_status"] == "not_applicable":
      raise ValueError("supplied citation report cannot be not_applicable")
  else:
    if (report["citation_report_sha256"] is not None
        or citation["resolver"] is not None or citation["checked_at"] is not None
        or citation["response_status"] not in {
            "unavailable", "not_applicable",
        }):
      raise ValueError("absent citation provenance is inconsistent")
  if report["manifest_sha256"] != combined_manifest_sha256(
      report["workspace_manifest_sha256"],
      report["citation_report_sha256"]):
    raise ValueError("manifest_sha256 does not match validation inputs")
  PassReport.from_dict({
      "schema_version": SCHEMA_VERSION,
      "integrity_score": report["integrity_score"],
      "findings": report["findings"],
      "dimensions": report["dimensions"],
      "manifest_sha256": report["manifest_sha256"],
      "status": report["status"],
  })
  return report


def _stable_json_value(value: object) -> object:
  if isinstance(value, Mapping):
    return {
        key: _stable_json_value(value[key])
        for key in sorted(value)
    }
  if isinstance(value, (list, tuple)):
    return [_stable_json_value(item) for item in value]
  return value


def _ordered_finding(finding: Mapping[str, object]) -> dict:
  result = {key: finding[key] for key in _FINDING_ORDER}
  result["context"] = _stable_json_value(finding["context"])
  return result


def _ordered_dimension(dimension: Mapping[str, object]) -> dict:
  result = {key: dimension[key] for key in _DIMENSION_FIELD_ORDER}
  result["findings"] = [
      _ordered_finding(finding) for finding in dimension["findings"]]
  return result


def render_json(report: Mapping[str, object]) -> str:
  """Render exactly one compact JSON report followed by one newline."""
  value = validate_report(dict(report))
  ordered = {key: value[key] for key in _TOP_LEVEL_ORDER}
  ordered["validator_versions"] = {
      key: value["validator_versions"][key] for key in VALIDATOR_VERSIONS}
  ordered["dimensions"] = {
      name: _ordered_dimension(value["dimensions"][name])
      for name in DIMENSION_ORDER}
  ordered["findings"] = [
      _ordered_finding(finding) for finding in value["findings"]]
  ordered["citation_resolution"] = {
      key: value["citation_resolution"][key]
      for key in ("source", "resolver", "checked_at", "response_status")
  }
  return json.dumps(
      ordered, ensure_ascii=False, sort_keys=False, separators=(",", ":"),
      allow_nan=False) + "\n"


def _display(value: object) -> str:
  if value is None:
    return "N/A"
  if isinstance(value, float):
    return f"{value:.1f}"
  return str(value)


def _one_line(value: object) -> str:
  return _display(value).replace("|", "\\|").replace("\n", " ")


_MARKDOWN_ESCAPES = frozenset("\\`*{}[]()<>#+-.!_|")
_INLINE_BREAKS = {
    "\r": "\\r", "\n": "\\n", "\u0085": "\\u0085",
    "\u2028": "\\u2028", "\u2029": "\\u2029",
}


def _markdown_inline(value: object) -> str:
  """Render an untrusted value without permitting Markdown structure."""
  result = []
  for character in _display(value):
    if character in _INLINE_BREAKS:
      result.append(_INLINE_BREAKS[character])
    elif character in _MARKDOWN_ESCAPES:
      result.append("\\" + character)
    elif character == "&":
      result.append("&amp;")
    else:
      result.append(character)
  return "".join(result)


def render_markdown(
    report: Mapping[str, object], synthesis_text: str,
) -> str:
  """Render a bounded audit report using only retained report data and text."""
  value = validate_report(dict(report))
  if not isinstance(synthesis_text, str):
    raise ValueError("synthesis_text must be retained text")
  lines = [
      "# Literature Review Integrity Report", "",
      f"- Status: `{value['status']}`",
      f"- Quality score: {_display(value['quality_score'])}",
      f"- Integrity score: {_display(value['integrity_score'])}",
      f"- Manifest SHA-256: `{value['manifest_sha256']}`",
      f"- Workspace manifest SHA-256: "
      f"`{value['workspace_manifest_sha256']}`",
      f"- Citation report SHA-256: "
      f"{_display(value['citation_report_sha256'])}",
      f"- Target commit: {_display(value['target_commit'])}",
      f"- Target tracked dirty: {_display(value['target_dirty'])}", "",
  ]
  if value["status"] == "invalid":
    lines.extend([_INVALID_WARNING, ""])
  citation = value["citation_resolution"]
  lines.extend([
      "## Citation resolution", "",
      f"- Provenance: `{citation['source']}`",
      f"- Resolver: {_markdown_inline(citation['resolver'])}",
      f"- Checked at: {_markdown_inline(citation['checked_at'])}",
      f"- Response status: `{citation['response_status']}`", "",
      "## Dimensions", "",
      "| Dimension | Applicable | Score | Evaluated units | Passed units | "
      "Nominal weight | Effective weight |",
      "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
  ])
  for name, dimension in value["dimensions"].items():
    lines.append(
        f"| {_one_line(name)} | {_one_line(dimension['applicable'])} | "
        f"{_one_line(dimension['score'])} | {dimension['evaluated_units']} | "
        f"{dimension['passed_units']} | {dimension['nominal_weight']} | "
        f"{dimension['effective_weight']} |")
  lines.extend(["", "## Findings", ""])
  findings = value["findings"]
  if not findings:
    lines.extend(["No integrity findings.", ""])
  else:
    for index, finding in enumerate(findings, 1):
      context = json.dumps(
          finding["context"], ensure_ascii=False, sort_keys=True,
          separators=(",", ":"), allow_nan=False)
      lines.extend([
          f"### {index}. `{finding['reason_code']}`", "",
          f"- Severity: `{finding['severity']}`",
          f"- Artifact: {_markdown_inline(finding['artifact'])}",
          f"- Message: {_markdown_inline(finding['message'])}",
          f"- Context: {_markdown_inline(context)}", "",
      ])
  excerpt = synthesis_text[:_SYNTHESIS_EXCERPT_LIMIT]
  lines.extend(["## Synthesis excerpt", ""])
  if excerpt:
    lines.extend(f"> {line}" for line in excerpt.splitlines() or [excerpt])
  else:
    lines.append("_No synthesis text retained._")
  if len(synthesis_text) > _SYNTHESIS_EXCERPT_LIMIT:
    lines.extend(["", "_Excerpt truncated._"])
  lines.append("")
  return "\n".join(lines)


__all__ = [
    "ARTIFACT_SCORING_VERSION", "CITATION_VALIDATOR_VERSION",
    "CLAIMS_VALIDATOR_VERSION", "ENGINE_VERSION", "PRISMA_VALIDATOR_VERSION",
    "SCHEMA_VERSION", "VALIDATOR_VERSIONS", "combined_manifest_sha256", "render_json",
    "render_markdown", "validate_report",
]
