"""Append-only reports for paired literature quality and integrity runs."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from .literature_integrity import CAPABILITY, IntegrityEvalResult


SCHEMA_VERSION = "1.0.0"
INTEGRITY_EVALUATION_KIND = "quality_and_integrity"
INTEGRITY_EVALUATION_LABEL = "Paired quality and integrity evaluation"
QUALITY_HISTORY_KIND = "quality_only_history"
QUALITY_HISTORY_LABEL = (
    "Quality-only historical run — not integrity evaluated")
_RUN_ID_RE = re.compile(
    r"run[-_][A-Za-z0-9](?:[A-Za-z0-9._-]{0,125}[A-Za-z0-9])?\Z")
_CASE_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_STATUS_NAMES = ("valid", "valid_with_warnings", "invalid")
_REGISTRY_FIELDS = {
    "run_id", "timestamp", "model", "capability", "evaluation_kind",
    "evaluation_label", "result_file", "result_sha256",
}


def _text(value: object, label: str) -> str:
  if not isinstance(value, str) or not value.strip():
    raise ValueError(f"{label} must be nonempty text")
  return value


def _run_id(value: object) -> str:
  if (not isinstance(value, str) or not _RUN_ID_RE.fullmatch(value)
      or ".." in value):
    raise ValueError("unsafe run_id")
  return value


def _closed_object(
    value: object, fields: set[str], label: str, *, optional: set[str] | None = None,
) -> dict:
  if not isinstance(value, dict):
    raise ValueError(f"{label} must be a JSON object")
  optional = optional or set()
  unknown = set(value) - fields - optional
  missing = fields - set(value)
  if unknown:
    raise ValueError(f"{label} has unknown fields: {sorted(unknown)}")
  if missing:
    raise ValueError(f"{label} is missing fields: {sorted(missing)}")
  return value


def _json_bytes(value: object) -> bytes:
  return (json.dumps(
      value, indent=2, sort_keys=True, ensure_ascii=False,
  ) + "\n").encode("utf-8")


def _digest(payload: bytes) -> str:
  return hashlib.sha256(payload).hexdigest()


def _write_exclusive(path: Path, payload: bytes) -> None:
  with path.open("xb") as destination:
    destination.write(payload)


def _safe_relative_path(value: object, label: str) -> PurePosixPath:
  if not isinstance(value, str) or not value:
    raise ValueError(f"{label} must be a relative path")
  path = PurePosixPath(value)
  if path.is_absolute() or ".." in path.parts or "." in path.parts:
    raise ValueError(f"{label} must be a safe relative path")
  if path.as_posix() != value:
    raise ValueError(f"{label} must use canonical POSIX separators")
  return path


def _finite_score(value: object, label: str) -> float | None:
  if value is None:
    return None
  if isinstance(value, bool) or not isinstance(value, (int, float)):
    raise ValueError(f"{label} must be a number or null")
  score = float(value)
  if not math.isfinite(score) or not 0.0 <= score <= 100.0:
    raise ValueError(f"{label} must be between 0 and 100")
  return score


@dataclass(frozen=True, slots=True)
class CombinedCaseResult:
  """One case whose quality and integrity refer to Task 8 snapshots."""

  case_id: str
  evaluation: IntegrityEvalResult | dict
  attack_family: str | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.case_id, str) or not _CASE_ID_RE.fullmatch(
        self.case_id):
      raise ValueError("case_id must be a lowercase hyphenated identifier")
    evaluation = self.evaluation
    if isinstance(evaluation, dict):
      evaluation = IntegrityEvalResult.from_dict(evaluation)
    elif isinstance(evaluation, IntegrityEvalResult):
      # Round-trip through the strict Task 8 decoder. This prevents callers
      # from smuggling an unchecked dict-like payload into a report.
      evaluation = IntegrityEvalResult.from_dict(evaluation.to_dict())
    else:
      raise ValueError("evaluation must be an IntegrityEvalResult")
    object.__setattr__(self, "evaluation", evaluation)
    if self.attack_family is not None:
      _text(self.attack_family, "attack_family")

  def to_dict(self) -> dict:
    value = {
        "case_id": self.case_id,
        "evaluation": self.evaluation.to_dict(),
    }
    if self.attack_family is not None:
      value["attack_family"] = self.attack_family
    return value

  @classmethod
  def from_dict(cls, value: dict) -> "CombinedCaseResult":
    data = _closed_object(
        value, {"case_id", "evaluation"}, "combined case",
        optional={"attack_family"})
    return cls(
        case_id=data["case_id"],
        evaluation=data["evaluation"],
        attack_family=data.get("attack_family"),
    )


@dataclass(frozen=True, slots=True)
class CombinedRunResult:
  """Strict input model for an isolated multi-case integrity run."""

  run_id: str
  timestamp: str
  model: str
  cases: tuple[CombinedCaseResult, ...] | Sequence[CombinedCaseResult]
  capability: str = CAPABILITY

  def __post_init__(self) -> None:
    object.__setattr__(self, "run_id", _run_id(self.run_id))
    _text(self.timestamp, "timestamp")
    _text(self.model, "model")
    if self.capability != CAPABILITY:
      raise ValueError(f"capability must be {CAPABILITY!r}")
    if not isinstance(self.cases, (list, tuple)):
      raise ValueError("cases must be a sequence")
    cases = tuple(
        value if isinstance(value, CombinedCaseResult)
        else CombinedCaseResult.from_dict(value)
        for value in self.cases)
    if not cases:
      raise ValueError("cases must not be empty")
    if len({case.case_id for case in cases}) != len(cases):
      raise ValueError("case identifiers must be unique")
    object.__setattr__(self, "cases", cases)

  @classmethod
  def from_results(
      cls, *, run_id: str, timestamp: str, model: str,
      results: Mapping[str, IntegrityEvalResult] | Sequence[
          tuple[str, IntegrityEvalResult]],
  ) -> "CombinedRunResult":
    pairs = results.items() if isinstance(results, Mapping) else results
    return cls(
        run_id=run_id, timestamp=timestamp, model=model,
        cases=tuple(CombinedCaseResult(case_id, evaluation)
                    for case_id, evaluation in pairs),
    )

  def to_dict(self) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": self.run_id,
        "timestamp": self.timestamp,
        "model": self.model,
        "capability": self.capability,
        "cases": [case.to_dict() for case in self.cases],
    }

  @classmethod
  def from_dict(cls, value: dict) -> "CombinedRunResult":
    data = _closed_object(value, {
        "schema_version", "run_id", "timestamp", "model", "capability",
        "cases",
    }, "combined run")
    if data["schema_version"] != SCHEMA_VERSION:
      raise ValueError("unsupported combined run schema_version")
    if not isinstance(data["cases"], list):
      raise ValueError("combined run cases must be a list")
    return cls(
        run_id=data["run_id"], timestamp=data["timestamp"],
        model=data["model"], capability=data["capability"],
        cases=tuple(CombinedCaseResult.from_dict(item)
                    for item in data["cases"]),
    )


def _snapshot_view(snapshot) -> dict:
  return {
      "quality_score": snapshot.quality.quality_score,
      "integrity_score": round(snapshot.integrity.integrity_score, 1),
      "status": snapshot.integrity.status.value,
      "workspace_manifest_sha256": snapshot.workspace_manifest_sha256,
  }


def _repair_round_view(repair_round, path: str, sha256: str) -> dict:
  return {
      "attempt": repair_round.attempt,
      "integrity_score": round(repair_round.integrity.integrity_score, 1),
      "status": repair_round.integrity.status.value,
      "action": repair_round.action,
      "path": path,
      "sha256": sha256,
  }


def _status_summary(cases: Sequence[CombinedCaseResult]) -> dict:
  counts = {status: 0 for status in _STATUS_NAMES}
  attack_families: dict[str, int] = {}
  for case in cases:
    counts[case.evaluation.system_final.integrity.status.value] += 1
    if case.attack_family is not None:
      attack_families[case.attack_family] = (
          attack_families.get(case.attack_family, 0) + 1)
  summary = {"case_count": len(cases), "integrity_status_counts": counts}
  if attack_families:
    summary["attack_family_breakdown"] = dict(sorted(attack_families.items()))
  return summary


def _summary_markdown(result: CombinedRunResult, cases: list[dict]) -> str:
  counts = _status_summary(result.cases)["integrity_status_counts"]
  rows = []
  for case in cases:
    first = case["first_pass"]
    final = case["final"]
    quality_first = (
        "ERROR" if first["quality_score"] is None
        else f"{first['quality_score']:.1f}")
    quality_final = (
        "ERROR" if final["quality_score"] is None
        else f"{final['quality_score']:.1f}")
    artifact = case["artifact"]
    rows.append(
        f"| {case['case_id']} | {quality_first} | "
        f"{first['integrity_score']:.1f} ({first['status']}) | "
        f"{quality_final} | {final['integrity_score']:.1f} "
        f"({final['status']}) | "
        f"[{artifact['path']}]({artifact['path']}) "
        f"`{artifact['sha256']}` |")
  return (
      f"# Evaluation Run {result.run_id}\n\n"
      f"**Evaluation**: {INTEGRITY_EVALUATION_LABEL}  \n"
      f"**Capability**: {result.capability}  \n"
      f"**Model**: {result.model}  \n"
      f"**Timestamp**: {result.timestamp}  \n"
      f"**Cases**: {len(cases)}  \n"
      f"**Final integrity statuses**: valid={counts['valid']}, "
      f"valid_with_warnings={counts['valid_with_warnings']}, "
      f"invalid={counts['invalid']}\n\n"
      "Quality and integrity are separate measurements. The integrity status "
      "does not imply that the quality score passed a quality threshold.\n\n"
      "| Case | First-pass quality | First-pass integrity | Final quality | "
      "Final integrity | Validated artifact (SHA-256) |\n"
      "|---|---:|---:|---:|---:|---|\n"
      + "\n".join(rows) + "\n")


def _registry_entry(result: CombinedRunResult, result_sha256: str) -> dict:
  return {
      "run_id": result.run_id,
      "timestamp": result.timestamp,
      "model": result.model,
      "capability": result.capability,
      "evaluation_kind": INTEGRITY_EVALUATION_KIND,
      "evaluation_label": INTEGRITY_EVALUATION_LABEL,
      "result_file": f"{result.run_id}/result.json",
      "result_sha256": result_sha256,
  }


def _validate_registry_entry(value: object) -> dict:
  entry = _closed_object(value, _REGISTRY_FIELDS, "run registry entry")
  entry_run_id = _run_id(entry["run_id"])
  _text(entry["timestamp"], "run registry timestamp")
  _text(entry["model"], "run registry model")
  if entry["capability"] != CAPABILITY:
    raise ValueError("run registry capability is invalid")
  if entry["evaluation_kind"] != INTEGRITY_EVALUATION_KIND:
    raise ValueError("run registry evaluation kind is invalid")
  if entry["evaluation_label"] != INTEGRITY_EVALUATION_LABEL:
    raise ValueError("run registry evaluation label is invalid")
  expected_file = f"{entry_run_id}/result.json"
  if (_safe_relative_path(entry["result_file"], "result_file").as_posix()
      != expected_file):
    raise ValueError("run registry result_file is invalid")
  if (not isinstance(entry["result_sha256"], str)
      or not _SHA256_RE.fullmatch(entry["result_sha256"])):
    raise ValueError("run registry result_sha256 is invalid")
  return entry


def _read_registry(runs_root: Path, *, missing_ok: bool) -> list[dict]:
  registry_path = runs_root / "index.json"
  if not registry_path.exists():
    if missing_ok and not registry_path.is_symlink():
      return []
    raise ValueError("run registry must be a regular file")
  if registry_path.is_symlink() or not registry_path.is_file():
    raise ValueError("run registry must be a regular file")
  try:
    value = json.loads(registry_path.read_text(encoding="utf-8"))
  except (OSError, UnicodeError, json.JSONDecodeError) as exc:
    raise ValueError(f"cannot read run registry: {exc}") from exc
  data = _closed_object(
      value, {"schema_version", "runs"}, "run registry")
  if data["schema_version"] != SCHEMA_VERSION:
    raise ValueError("unsupported run registry schema_version")
  if not isinstance(data["runs"], list):
    raise ValueError("run registry runs must be a list")
  entries = [_validate_registry_entry(entry) for entry in data["runs"]]
  run_ids = [entry["run_id"] for entry in entries]
  if len(set(run_ids)) != len(run_ids):
    raise ValueError("run registry run_id values must be unique")
  if run_ids != sorted(run_ids):
    raise ValueError("run registry entries must be sorted by run_id")
  return entries


def _update_registry(runs_root: Path, entry: dict) -> None:
  registry_path = runs_root / "index.json"
  entries = _read_registry(runs_root, missing_ok=True)
  if any(item["run_id"] == entry["run_id"] for item in entries):
    raise FileExistsError(f"run_id already registered: {entry['run_id']}")
  entries.append(entry)
  entries.sort(key=lambda item: item["run_id"])
  payload = _json_bytes({"schema_version": SCHEMA_VERSION, "runs": entries})
  temporary = runs_root / f".index-{entry['run_id']}.tmp"
  _write_exclusive(temporary, payload)
  os.replace(temporary, registry_path)


def write_run_report(result: CombinedRunResult, root: Path) -> Path:
  """Write one append-only run below ``root/runs`` and return its directory."""
  if not isinstance(result, CombinedRunResult):
    if not isinstance(result, dict):
      raise ValueError("result must be a CombinedRunResult")
    result = CombinedRunResult.from_dict(result)
  else:
    # Strictly deserialize even an already-constructed value at the boundary.
    result = CombinedRunResult.from_dict(result.to_dict())

  root = Path(root)
  if root.is_symlink():
    raise ValueError("report root must not be a symlink")
  root.mkdir(parents=True, exist_ok=True)
  runs_root = root / "runs"
  if runs_root.is_symlink():
    raise ValueError("runs directory must not be a symlink")
  runs_root.mkdir(exist_ok=True)
  _read_registry(runs_root, missing_ok=True)
  destination = runs_root / result.run_id
  if os.path.lexists(destination):
    raise FileExistsError(f"run_id already exists: {result.run_id}")
  destination.mkdir(exist_ok=False)
  artifacts = destination / "artifacts"
  repair_rounds = destination / "repair-rounds"
  artifacts.mkdir()
  repair_rounds.mkdir()

  case_views = []
  for case in sorted(result.cases, key=lambda item: item.case_id):
    artifact_path = f"artifacts/{case.case_id}.json"
    artifact_payload = _json_bytes(case.evaluation.to_dict())
    artifact_sha256 = _digest(artifact_payload)
    _write_exclusive(destination / artifact_path, artifact_payload)
    view = {
        "case_id": case.case_id,
        "first_pass": _snapshot_view(case.evaluation.model_first_pass),
        "final": _snapshot_view(case.evaluation.system_final),
        "artifact": {"path": artifact_path, "sha256": artifact_sha256},
    }
    if case.attack_family is not None:
      view["attack_family"] = case.attack_family
    if case.evaluation.repair_rounds:
      round_views = []
      for repair_round in case.evaluation.repair_rounds:
        relative = (
            f"repair-rounds/{case.case_id}-round-"
            f"{repair_round.attempt:02d}.json")
        payload = _json_bytes(repair_round.to_dict())
        sha256 = _digest(payload)
        _write_exclusive(destination / relative, payload)
        round_views.append(_repair_round_view(
            repair_round, relative, sha256))
      view["repair_rounds"] = round_views
    case_views.append(view)

  report = {
      "schema_version": SCHEMA_VERSION,
      "evaluation_kind": INTEGRITY_EVALUATION_KIND,
      "evaluation_label": INTEGRITY_EVALUATION_LABEL,
      "run_id": result.run_id,
      "timestamp": result.timestamp,
      "model": result.model,
      "capability": result.capability,
      "summary": _status_summary(result.cases),
      "cases": case_views,
  }
  result_payload = _json_bytes(report)
  _write_exclusive(destination / "result.json", result_payload)
  _write_exclusive(
      destination / "summary.md",
      _summary_markdown(result, case_views).encode("utf-8"))
  _update_registry(runs_root, _registry_entry(result, _digest(result_payload)))
  return destination


def _artifact_payload(run_directory: Path, reference: dict, label: str) -> dict:
  data = _closed_object(reference, {"path", "sha256"}, label)
  relative = _safe_relative_path(data["path"], f"{label} path")
  if not isinstance(data["sha256"], str) or not _SHA256_RE.fullmatch(
      data["sha256"]):
    raise ValueError(f"{label} sha256 must be a SHA-256 digest")
  path = run_directory.joinpath(*relative.parts)
  if path.is_symlink() or not path.is_file():
    raise ValueError(f"{label} must reference a regular file")
  payload = path.read_bytes()
  if _digest(payload) != data["sha256"]:
    raise ValueError(f"{label} SHA-256 mismatch")
  try:
    parsed = json.loads(payload)
  except (UnicodeError, json.JSONDecodeError) as exc:
    raise ValueError(f"{label} is not valid JSON: {exc}") from exc
  if not isinstance(parsed, dict):
    raise ValueError(f"{label} must contain a JSON object")
  return parsed


def _validate_snapshot_view(value: object, snapshot, label: str) -> dict:
  data = _closed_object(value, {
      "quality_score", "integrity_score", "status",
      "workspace_manifest_sha256",
  }, label)
  expected = _snapshot_view(snapshot)
  if data != expected:
    raise ValueError(f"{label} does not match its validated Task 8 snapshot")
  return data


def _validate_repair_views(
    value: object, evaluation: IntegrityEvalResult, run_directory: Path,
    case_id: str,
) -> list[dict]:
  if not isinstance(value, list):
    raise ValueError("repair_rounds must be a list")
  if len(value) != len(evaluation.repair_rounds):
    raise ValueError("repair_rounds do not match the validated artifact")
  validated = []
  for item, repair_round in zip(value, evaluation.repair_rounds):
    data = _closed_object(item, {
        "attempt", "integrity_score", "status", "action", "path", "sha256",
    }, "repair round reference")
    parsed = _artifact_payload(
        run_directory, {"path": data["path"], "sha256": data["sha256"]},
        "repair round artifact")
    if parsed != repair_round.to_dict():
      raise ValueError("repair round artifact does not match Task 8 result")
    expected = _repair_round_view(
        repair_round, data["path"], data["sha256"])
    if data != expected:
      raise ValueError("repair round view does not match Task 8 result")
    expected_prefix = f"repair-rounds/{case_id}-round-"
    if not data["path"].startswith(expected_prefix):
      raise ValueError("repair round path does not match its case")
    validated.append(data)
  return validated


def _selected_registry_entry(runs_root: Path, selected: str) -> dict:
  try:
    entries = _read_registry(runs_root, missing_ok=False)
  except ValueError as exc:
    if "regular file" in str(exc):
      raise ValueError(f"unknown run_id: {selected}") from exc
    raise
  matches = [entry for entry in entries if entry["run_id"] == selected]
  if len(matches) != 1:
    raise ValueError(f"unknown run_id: {selected}")
  return matches[0]


def load_dashboard_data(root: Path, run_id: str) -> dict:
  """Load one selected run, validate all links, and return dashboard data."""
  selected = _run_id(run_id)
  runs_root = Path(root) / "runs"
  if runs_root.is_symlink() or not runs_root.is_dir():
    raise ValueError(f"unknown run_id: {selected}")
  registry_entry = _selected_registry_entry(runs_root, selected)
  run_directory = runs_root / selected
  if run_directory.is_symlink() or not run_directory.is_dir():
    raise ValueError(f"unknown run_id: {selected}")
  report_path = run_directory / "result.json"
  if report_path.is_symlink() or not report_path.is_file():
    raise ValueError(f"unknown run_id: {selected}")
  try:
    report_payload = report_path.read_bytes()
    report = json.loads(report_payload)
  except (OSError, UnicodeError, json.JSONDecodeError) as exc:
    raise ValueError(f"cannot read selected run: {exc}") from exc
  if _digest(report_payload) != registry_entry["result_sha256"]:
    raise ValueError("selected run result SHA-256 mismatch")
  data = _closed_object(report, {
      "schema_version", "evaluation_kind", "evaluation_label", "run_id",
      "timestamp", "model", "capability", "summary", "cases",
  }, "run report")
  if data["schema_version"] != SCHEMA_VERSION:
    raise ValueError("unsupported run report schema_version")
  if data["evaluation_kind"] != INTEGRITY_EVALUATION_KIND:
    raise ValueError("run report is not a paired integrity evaluation")
  if data["evaluation_label"] != INTEGRITY_EVALUATION_LABEL:
    raise ValueError("run report evaluation label is invalid")
  if data["run_id"] != selected:
    raise ValueError("run report run_id does not match selected directory")
  if data["capability"] != CAPABILITY:
    raise ValueError("run report capability is invalid")
  _text(data["timestamp"], "timestamp")
  _text(data["model"], "model")
  if not isinstance(data["cases"], list) or not data["cases"]:
    raise ValueError("run report cases must be a nonempty list")

  validated_cases = []
  seen = set()
  strict_cases = []
  for value in data["cases"]:
    case = _closed_object(value, {
        "case_id", "first_pass", "final", "artifact",
    }, "run case", optional={"attack_family", "repair_rounds"})
    case_id = case["case_id"]
    if (not isinstance(case_id, str) or not _CASE_ID_RE.fullmatch(case_id)
        or case_id in seen):
      raise ValueError("run case identifiers must be unique canonical IDs")
    seen.add(case_id)
    parsed = _artifact_payload(
        run_directory, case["artifact"], "case artifact")
    evaluation = IntegrityEvalResult.from_dict(parsed)
    strict = CombinedCaseResult(
        case_id=case_id, evaluation=evaluation,
        attack_family=case.get("attack_family"))
    _validate_snapshot_view(
        case["first_pass"], evaluation.model_first_pass, "first_pass")
    _validate_snapshot_view(case["final"], evaluation.system_final, "final")
    has_rounds = bool(evaluation.repair_rounds)
    if has_rounds != ("repair_rounds" in case):
      raise ValueError("repair_rounds presence does not match Task 8 result")
    if has_rounds:
      _validate_repair_views(
          case["repair_rounds"], evaluation, run_directory, case_id)
    validated_cases.append(case)
    strict_cases.append(strict)

  expected_summary = _status_summary(strict_cases)
  summary = _closed_object(
      data["summary"], {"case_count", "integrity_status_counts"},
      "run summary", optional={"attack_family_breakdown"})
  status_counts = _closed_object(
      summary["integrity_status_counts"], set(_STATUS_NAMES),
      "integrity status counts")
  if (isinstance(summary["case_count"], bool)
      or not isinstance(summary["case_count"], int)
      or summary["case_count"] < 1
      or any(isinstance(count, bool) or not isinstance(count, int) or count < 0
             for count in status_counts.values())
      or sum(status_counts.values()) != summary["case_count"]):
    raise ValueError("run summary counts are invalid")
  if "attack_family_breakdown" in summary:
    breakdown = summary["attack_family_breakdown"]
    if (not isinstance(breakdown, dict) or not breakdown
        or any(not isinstance(name, str) or not name.strip()
               or isinstance(count, bool) or not isinstance(count, int)
               or count < 1 for name, count in breakdown.items())):
      raise ValueError("attack_family_breakdown is invalid")
  if summary != expected_summary or status_counts != expected_summary[
      "integrity_status_counts"]:
    raise ValueError("run summary does not match selected run cases")
  return data


def adapt_quality_history(value: object) -> dict:
  """Label schema-v2 broad benchmark records as quality-only history."""
  data = _closed_object(
      value, {"schema_version", "runs", "summary_stats"},
      "quality history")
  if data["schema_version"] != "2.0":
    raise ValueError("unsupported quality history schema_version")
  if not isinstance(data["runs"], list):
    raise ValueError("quality history runs must be a list")
  adapted = []
  seen = set()
  required = {
      "run_id", "timestamp", "model", "tests_run",
      "tests_passed", "average_score", "scores_by_agent", "pass_rate",
      "detail_file",
  }
  for value in data["runs"]:
    run = _closed_object(
        value, required, "quality history run", optional={"model_version"})
    run_id = _run_id(run["run_id"])
    if run_id in seen:
      raise ValueError("quality history run_id values must be unique")
    seen.add(run_id)
    quality_score = _finite_score(run["average_score"], "average_score")
    if not isinstance(run["scores_by_agent"], dict):
      raise ValueError("scores_by_agent must be a dictionary")
    # Retain capability keys exactly as published. In particular,
    # literature-review history is not renamed to the new integrity capability.
    scores_by_capability = MappingProxyType(dict(run["scores_by_agent"]))
    detail_path = _safe_relative_path(run["detail_file"], "detail_file")
    model = _text(run["model"], "model")
    model_version = run.get("model_version")
    if model_version is None:
      model_version = model.split(":", 1)[1] if ":" in model else model
    adapted.append({
        "run_id": run_id,
        "timestamp": _text(run["timestamp"], "timestamp"),
        "model": model,
        "model_version": _text(model_version, "model_version"),
        "case_count": run["tests_run"],
        "quality_passed": run["tests_passed"],
        "quality_score": quality_score,
        "quality_pass_rate": run["pass_rate"],
        "scores_by_capability": dict(scores_by_capability),
        "detail_file": detail_path.as_posix(),
        "evaluation_kind": QUALITY_HISTORY_KIND,
        "evaluation_label": QUALITY_HISTORY_LABEL,
        "integrity_score": None,
        "status": "not_evaluated",
    })
  return {
      "schema_version": SCHEMA_VERSION,
      "evaluation_kind": QUALITY_HISTORY_KIND,
      "evaluation_label": QUALITY_HISTORY_LABEL,
      "runs": adapted,
  }


__all__ = [
    "CombinedCaseResult", "CombinedRunResult", "SCHEMA_VERSION",
    "adapt_quality_history", "load_dashboard_data", "write_run_report",
]
