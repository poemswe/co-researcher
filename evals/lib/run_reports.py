"""Append-only reports for paired literature quality and integrity runs."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import stat
from contextlib import contextmanager
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType

import fcntl

from .literature_integrity import (
    AdversarialCaseScore,
    CAPABILITY,
    IntegrityEvalResult,
    IntegrityResult,
    OperationalIntegrityEvalResult,
    ReasonMetric,
    decode_integrity_result,
)


SCHEMA_VERSION = "1.0.0"
INTEGRITY_EVALUATION_KIND = "quality_and_integrity"
INTEGRITY_EVALUATION_LABEL = "Paired quality and integrity evaluation"
QUALITY_HISTORY_KIND = "quality_only_history"
QUALITY_HISTORY_LABEL = (
    "Quality-only historical run — not integrity evaluated")
_RUN_ID_RE = re.compile(
    r"run[-_][a-z0-9](?:[a-z0-9._-]{0,125}[a-z0-9])?\Z")
_CASE_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_NONCE_RE = re.compile(r"[0-9a-f]{32}\Z")
_STATUS_NAMES = ("valid", "valid_with_warnings", "invalid")
_MAX_REPORT_BYTES = 16 * 1024 * 1024
_REGISTRY_FIELDS = {
    "run_id", "timestamp", "model", "capability", "evaluation_kind",
    "evaluation_label", "case_count", "result_file", "result_sha256",
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
    destination.flush()
    os.fsync(destination.fileno())


def _directory_flags() -> int:
  return os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)


def _file_flags() -> int:
  return os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def _regular_single_link(descriptor: int, label: str) -> os.stat_result:
  metadata = os.fstat(descriptor)
  if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
    raise ValueError(f"{label} must be a regular single-link file")
  if metadata.st_size > _MAX_REPORT_BYTES:
    raise ValueError(f"{label} exceeds the size limit")
  return metadata


def _write_all(descriptor: int, payload: bytes) -> None:
  view = memoryview(payload)
  while view:
    written = os.write(descriptor, view)
    if written <= 0:
      raise OSError("short filesystem write")
    view = view[written:]


def _read_fd_bytes(descriptor: int, label: str) -> bytes:
  metadata = _regular_single_link(descriptor, label)
  stable_metadata = (
      metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_nlink,
      metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns)
  chunks = []
  remaining = metadata.st_size
  while remaining:
    chunk = os.read(descriptor, min(remaining, 1024 * 1024))
    if not chunk:
      raise ValueError(f"{label} changed while being read")
    chunks.append(chunk)
    remaining -= len(chunk)
  if os.read(descriptor, 1):
    raise ValueError(f"{label} grew while being read")
  current = os.fstat(descriptor)
  if (
      current.st_dev, current.st_ino, current.st_mode, current.st_nlink,
      current.st_size, current.st_mtime_ns, current.st_ctime_ns,
  ) != stable_metadata:
    raise ValueError(f"{label} changed while being read")
  return b"".join(chunks)


def _open_runs_root(runs_root: Path) -> int:
  try:
    descriptor = os.open(runs_root, _directory_flags())
  except OSError as exc:
    raise ValueError(f"runs directory is not trusted: {exc}") from exc
  return descriptor


@contextmanager
def _registry_lock(runs_root: Path):
  root_descriptor = _open_runs_root(runs_root)
  lock_descriptor = None
  try:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    for _ in range(32):
      try:
        lock_descriptor = os.open(
            ".index.lock", os.O_RDWR | nofollow,
            dir_fd=root_descriptor)
        break
      except FileNotFoundError:
        try:
          lock_descriptor = os.open(
              ".index.lock",
              os.O_RDWR | os.O_CREAT | os.O_EXCL | nofollow,
              0o600, dir_fd=root_descriptor)
          os.fsync(root_descriptor)
          break
        except FileExistsError:
          continue
    if lock_descriptor is None:
      raise OSError("could not open the run registry lock")
    _regular_single_link(lock_descriptor, "run registry lock")
    fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
    yield root_descriptor
  finally:
    if lock_descriptor is not None:
      try:
        fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
      finally:
        os.close(lock_descriptor)
    os.close(root_descriptor)


def _entry_metadata(
    parent_descriptor: int, name: str,
) -> os.stat_result | None:
  try:
    return os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
  except FileNotFoundError:
    return None


def _new_staging_directory(
    runs_root: Path, run_id: str,
) -> tuple[str, tuple[int, int]]:
  root_descriptor = _open_runs_root(runs_root)
  try:
    for _ in range(32):
      name = f".{run_id}-{secrets.token_hex(8)}.tmp"
      try:
        os.mkdir(name, mode=0o700, dir_fd=root_descriptor)
      except FileExistsError:
        continue
      descriptor = os.open(name, _directory_flags(), dir_fd=root_descriptor)
      try:
        metadata = os.fstat(descriptor)
        os.fsync(root_descriptor)
        return name, (metadata.st_dev, metadata.st_ino)
      finally:
        os.close(descriptor)
    raise FileExistsError("could not allocate a unique run staging directory")
  finally:
    os.close(root_descriptor)


def _remove_directory_contents(descriptor: int) -> None:
  for name in os.listdir(descriptor):
    metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
    if stat.S_ISDIR(metadata.st_mode):
      child = os.open(name, _directory_flags(), dir_fd=descriptor)
      try:
        _remove_directory_contents(child)
      finally:
        os.close(child)
      os.rmdir(name, dir_fd=descriptor)
    else:
      os.unlink(name, dir_fd=descriptor)


def _remove_owned_directory(
    runs_root: Path, name: str, identity: tuple[int, int],
) -> None:
  root_descriptor = _open_runs_root(runs_root)
  try:
    try:
      descriptor = os.open(name, _directory_flags(), dir_fd=root_descriptor)
    except FileNotFoundError:
      return
    try:
      metadata = os.fstat(descriptor)
      if (metadata.st_dev, metadata.st_ino) != identity:
        raise ValueError("refusing to remove a directory not owned by this run")
      _remove_directory_contents(descriptor)
    finally:
      os.close(descriptor)
    os.rmdir(name, dir_fd=root_descriptor)
    os.fsync(root_descriptor)
  finally:
    os.close(root_descriptor)


def _fsync_directory(path: Path) -> None:
  descriptor = os.open(path, _directory_flags())
  try:
    os.fsync(descriptor)
  finally:
    os.close(descriptor)


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
  evaluation: IntegrityResult | dict
  adversarial_score: AdversarialCaseScore | dict | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.case_id, str) or not _CASE_ID_RE.fullmatch(
        self.case_id):
      raise ValueError("case_id must be a lowercase hyphenated identifier")
    evaluation = self.evaluation
    if isinstance(evaluation, dict):
      evaluation = decode_integrity_result(evaluation)
    elif isinstance(evaluation, (IntegrityEvalResult,
                                 OperationalIntegrityEvalResult)):
      # Round-trip through the strict Task 8 decoder. This prevents callers
      # from smuggling an unchecked dict-like payload into a report.
      evaluation = decode_integrity_result(evaluation.to_dict())
    else:
      raise ValueError("evaluation must be an integrity result")
    object.__setattr__(self, "evaluation", evaluation)
    adversarial = self.adversarial_score
    if isinstance(adversarial, dict):
      adversarial = AdversarialCaseScore.from_dict(adversarial)
    elif adversarial is not None and not isinstance(
        adversarial, AdversarialCaseScore):
      raise ValueError(
          "adversarial_score must be an AdversarialCaseScore or null")
    object.__setattr__(self, "adversarial_score", adversarial)

  @property
  def attack_family(self) -> str | None:
    return (None if self.adversarial_score is None
            else self.adversarial_score.attack_family)

  def to_dict(self) -> dict:
    value = {
        "case_id": self.case_id,
        "evaluation": self.evaluation.to_dict(),
    }
    if self.adversarial_score is not None:
      value["adversarial_score"] = self.adversarial_score.to_dict()
    return value

  @classmethod
  def from_dict(cls, value: dict) -> "CombinedCaseResult":
    data = _closed_object(
        value, {"case_id", "evaluation"}, "combined case",
        optional={"adversarial_score"})
    return cls(
        case_id=data["case_id"],
        evaluation=data["evaluation"],
        adversarial_score=data.get("adversarial_score"),
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
      results: Mapping[str, IntegrityResult] | Sequence[
          tuple[str, IntegrityResult]],
      adversarial_scores: Mapping[str, AdversarialCaseScore] | None = None,
  ) -> "CombinedRunResult":
    pairs = results.items() if isinstance(results, Mapping) else results
    scores = {} if adversarial_scores is None else adversarial_scores
    if not isinstance(scores, Mapping):
      raise ValueError("adversarial_scores must be a mapping or null")
    return cls(
        run_id=run_id, timestamp=timestamp, model=model,
        cases=tuple(CombinedCaseResult(
                        case_id, evaluation,
                        adversarial_score=scores.get(case_id))
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


def _operational_view() -> dict:
  return {
      "quality_score": None,
      "integrity_score": None,
      "status": "invalid",
      "workspace_manifest_sha256": None,
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
  family_confusion: dict[str, dict[str, int]] = {}
  reason_counts: dict[str, dict[str, int]] = {}
  for case in cases:
    status = (
        "invalid" if isinstance(
            case.evaluation, OperationalIntegrityEvalResult)
        else case.evaluation.system_final.integrity.status.value)
    counts[status] += 1
    if case.attack_family is not None:
      attack_families[case.attack_family] = (
          attack_families.get(case.attack_family, 0) + 1)
    if case.adversarial_score is not None:
      family = case.adversarial_score.attack_family
      confusion = family_confusion.setdefault(family, {
          "true_positive": 0, "false_positive": 0,
          "true_negative": 0, "false_negative": 0})
      for name, value in case.adversarial_score.confusion.items():
        confusion[name] += value
      for code, metric in case.adversarial_score.reason_metrics.items():
        combined = reason_counts.setdefault(code, {
            "true_positive": 0, "false_positive": 0, "false_negative": 0})
        combined["true_positive"] += metric.true_positive
        combined["false_positive"] += metric.false_positive
        combined["false_negative"] += metric.false_negative
  summary = {"case_count": len(cases), "integrity_status_counts": counts}
  if attack_families:
    summary["attack_family_breakdown"] = dict(sorted(attack_families.items()))
  if family_confusion:
    summary["attack_family_confusion"] = dict(sorted(family_confusion.items()))
    summary["reason_code_metrics"] = {
        code: ReasonMetric(**values).to_dict()
        for code, values in sorted(reason_counts.items())
    }
  return summary


def _summary_markdown(result: CombinedRunResult, cases: list[dict]) -> str:
  counts = _status_summary(result.cases)["integrity_status_counts"]
  rows = []
  for case in cases:
    first = case["first_pass"]
    final = case["final"]
    quality_first = (
        "N/A" if first is None
        else "ERROR" if first["quality_score"] is None
        else f"{first['quality_score']:.1f}")
    quality_final = (
        "ERROR" if final["quality_score"] is None
        else f"{final['quality_score']:.1f}")
    artifact = case["artifact"]
    first_integrity = (
        "N/A" if first is None or first["integrity_score"] is None
        else f"{first['integrity_score']:.1f} ({first['status']})")
    final_integrity = (
        "N/A (invalid)" if final["integrity_score"] is None
        else f"{final['integrity_score']:.1f} ({final['status']})")
    rows.append(
        f"| {case['case_id']} | {quality_first} | "
        f"{first_integrity} | {quality_final} | {final_integrity} | "
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
      "case_count": len(result.cases),
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
  if (isinstance(entry["case_count"], bool)
      or not isinstance(entry["case_count"], int)
      or entry["case_count"] < 1):
    raise ValueError("run registry case_count is invalid")
  expected_file = f"{entry_run_id}/result.json"
  if (_safe_relative_path(entry["result_file"], "result_file").as_posix()
      != expected_file):
    raise ValueError("run registry result_file is invalid")
  if (not isinstance(entry["result_sha256"], str)
      or not _SHA256_RE.fullmatch(entry["result_sha256"])):
    raise ValueError("run registry result_sha256 is invalid")
  return entry


def _decode_registry(payload: bytes) -> list[dict]:
  try:
    value = json.loads(payload)
  except (UnicodeError, json.JSONDecodeError) as exc:
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


def _read_registry_locked(
    root_descriptor: int, *, missing_ok: bool,
) -> tuple[list[dict], bytes | None]:
  try:
    descriptor = os.open("index.json", _file_flags(), dir_fd=root_descriptor)
  except FileNotFoundError:
    if missing_ok:
      return [], None
    raise ValueError("run registry must be a regular file") from None
  try:
    payload = _read_fd_bytes(descriptor, "run registry")
  finally:
    os.close(descriptor)
  return _decode_registry(payload), payload


def _read_registry(runs_root: Path, *, missing_ok: bool) -> list[dict]:
  with _registry_lock(runs_root) as root_descriptor:
    entries, _ = _read_registry_locked(
        root_descriptor, missing_ok=missing_ok)
    return entries


def _replace_registry_payload(
    root_descriptor: int, payload: bytes, token: str,
) -> None:
  temporary = f".index-{token}-{secrets.token_hex(8)}.tmp"
  descriptor = None
  try:
    flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL
             | getattr(os, "O_NOFOLLOW", 0))
    descriptor = os.open(
        temporary, flags, 0o600, dir_fd=root_descriptor)
    _write_all(descriptor, payload)
    os.fsync(descriptor)
    os.close(descriptor)
    descriptor = None
    os.replace(
        temporary, "index.json",
        src_dir_fd=root_descriptor, dst_dir_fd=root_descriptor)
    published = os.open("index.json", _file_flags(), dir_fd=root_descriptor)
    try:
      _regular_single_link(published, "run registry")
      os.fsync(published)
    finally:
      os.close(published)
    os.fsync(root_descriptor)
  finally:
    if descriptor is not None:
      os.close(descriptor)
    try:
      os.unlink(temporary, dir_fd=root_descriptor)
    except FileNotFoundError:
      pass


def _restore_registry_locked(
    root_descriptor: int, previous_payload: bytes | None, token: str,
) -> None:
  if previous_payload is not None:
    _replace_registry_payload(root_descriptor, previous_payload, token)
    return
  try:
    descriptor = os.open("index.json", _file_flags(), dir_fd=root_descriptor)
  except FileNotFoundError:
    return
  try:
    _regular_single_link(descriptor, "run registry")
  finally:
    os.close(descriptor)
  os.unlink("index.json", dir_fd=root_descriptor)
  os.fsync(root_descriptor)


def _update_registry(
    runs_root: Path, entry: dict, *, root_descriptor: int | None = None,
    entries: list[dict] | None = None,
) -> None:
  if root_descriptor is None:
    with _registry_lock(runs_root) as locked_descriptor:
      locked_entries, _ = _read_registry_locked(
          locked_descriptor, missing_ok=True)
      _update_registry(
          runs_root, entry, root_descriptor=locked_descriptor,
          entries=locked_entries)
    return
  if entries is None:
    entries, _ = _read_registry_locked(root_descriptor, missing_ok=True)
  entries = list(entries)
  if any(item["run_id"] == entry["run_id"] for item in entries):
    raise FileExistsError(f"run_id already registered: {entry['run_id']}")
  entries.append(entry)
  entries.sort(key=lambda item: item["run_id"])
  payload = _json_bytes({"schema_version": SCHEMA_VERSION, "runs": entries})
  _replace_registry_payload(root_descriptor, payload, entry["run_id"])


def _read_owned_file(path: Path, label: str) -> bytes:
  descriptor = os.open(path, _file_flags())
  try:
    return _read_fd_bytes(descriptor, label)
  finally:
    os.close(descriptor)


def _prepare_run_payloads(result: CombinedRunResult) -> dict:
  case_views = []
  artifact_payloads = {}
  repair_payloads = {}
  for case in sorted(result.cases, key=lambda item: item.case_id):
    artifact_path = f"artifacts/{case.case_id}.json"
    artifact_payload = _json_bytes(case.evaluation.to_dict())
    artifact_payloads[f"{case.case_id}.json"] = artifact_payload
    if isinstance(case.evaluation, OperationalIntegrityEvalResult):
      view = {
          "case_id": case.case_id,
          "first_pass": (
              None if case.evaluation.model_first_pass is None
              else _snapshot_view(case.evaluation.model_first_pass)),
          "final": _operational_view(),
          "operational_failure": (
              case.evaluation.operational_failure.to_dict()),
          "artifact": {
              "path": artifact_path, "sha256": _digest(artifact_payload)},
      }
    else:
      view = {
          "case_id": case.case_id,
          "first_pass": _snapshot_view(case.evaluation.model_first_pass),
          "final": _snapshot_view(case.evaluation.system_final),
          "artifact": {
              "path": artifact_path, "sha256": _digest(artifact_payload)},
      }
    if case.attack_family is not None:
      view["attack_family"] = case.attack_family
    if case.adversarial_score is not None:
      view["adversarial_score"] = case.adversarial_score.to_dict()
    if case.evaluation.repair_rounds:
      round_views = []
      for repair_round in case.evaluation.repair_rounds:
        name = f"{case.case_id}-round-{repair_round.attempt:02d}.json"
        relative = f"repair-rounds/{name}"
        payload = _json_bytes(repair_round.to_dict())
        repair_payloads[name] = payload
        round_views.append(_repair_round_view(
            repair_round, relative, _digest(payload)))
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
  return {
      "report": report,
      "case_views": case_views,
      "result": _json_bytes(report),
      "summary": _summary_markdown(result, case_views).encode("utf-8"),
      "artifacts": artifact_payloads,
      "repair_rounds": repair_payloads,
  }


def _publication_payload(
    result: CombinedRunResult, result_sha256: str, nonce: str,
) -> bytes:
  return _json_bytes({
      "schema_version": SCHEMA_VERSION,
      "run_id": result.run_id,
      "result_sha256": result_sha256,
      "nonce": nonce,
  })


def _validate_publication_marker(
    payload: bytes, run_id: str, result_sha256: str,
) -> dict:
  try:
    marker = json.loads(payload)
  except (UnicodeError, json.JSONDecodeError) as exc:
    raise ValueError(f"publication marker is not valid JSON: {exc}") from exc
  data = _closed_object(marker, {
      "schema_version", "run_id", "result_sha256", "nonce",
  }, "publication marker")
  if (data["schema_version"] != SCHEMA_VERSION
      or data["run_id"] != run_id
      or data["result_sha256"] != result_sha256
      or not isinstance(data["nonce"], str)
      or not _NONCE_RE.fullmatch(data["nonce"])):
    raise ValueError("publication marker does not match the requested run")
  return data


def _validate_and_sync_staging(
    destination: Path, prepared: dict,
) -> bytes:
  report = prepared["report"]
  case_views = prepared["case_views"]
  expected_artifacts = {Path(case["artifact"]["path"]).name
                        for case in case_views}
  expected_rounds = {
      Path(round_view["path"]).name
      for case in case_views for round_view in case.get("repair_rounds", [])
  }
  if set(os.listdir(destination)) != {
      "artifacts", "repair-rounds", "result.json", "summary.md",
      "publication.json",
  }:
    raise ValueError("staged run contains unexpected top-level entries")
  if set(os.listdir(destination / "artifacts")) != expected_artifacts:
    raise ValueError("staged run artifacts do not match result references")
  if set(os.listdir(destination / "repair-rounds")) != expected_rounds:
    raise ValueError("staged repair rounds do not match result references")
  for case in case_views:
    reference = case["artifact"]
    payload = _read_owned_file(destination / reference["path"], "case artifact")
    if _digest(payload) != reference["sha256"]:
      raise ValueError("staged case artifact digest mismatch")
    decode_integrity_result(json.loads(payload))
    for round_view in case.get("repair_rounds", []):
      payload = _read_owned_file(
          destination / round_view["path"], "repair round artifact")
      if _digest(payload) != round_view["sha256"]:
        raise ValueError("staged repair round digest mismatch")
  result_payload = _read_owned_file(
      destination / "result.json", "run result")
  if json.loads(result_payload) != report:
    raise ValueError("staged result does not match the run report")
  marker_payload = _read_owned_file(
      destination / "publication.json", "publication marker")
  _validate_publication_marker(
      marker_payload, report["run_id"], _digest(result_payload))
  _read_owned_file(destination / "summary.md", "run summary")
  _fsync_directory(destination / "artifacts")
  _fsync_directory(destination / "repair-rounds")
  _fsync_directory(destination)
  return result_payload


def _validate_matching_orphan(
    root_descriptor: int, result: CombinedRunResult, prepared: dict,
) -> str:
  try:
    run_descriptor = os.open(
        result.run_id, _directory_flags(), dir_fd=root_descriptor)
  except OSError as exc:
    raise ValueError("unregistered run directory is not recoverable") from exc
  try:
    if set(os.listdir(run_descriptor)) != {
        "artifacts", "repair-rounds", "result.json", "summary.md",
        "publication.json",
    }:
      raise ValueError("unregistered run has a non-canonical layout")
    result_payload = _read_regular_at(
        run_descriptor, "result.json", "orphan run result")
    if result_payload != prepared["result"]:
      raise ValueError("unregistered run does not match the requested result")
    result_sha256 = _digest(result_payload)
    marker_payload = _read_regular_at(
        run_descriptor, "publication.json", "publication marker")
    _validate_publication_marker(
        marker_payload, result.run_id, result_sha256)
    if (_read_regular_at(
        run_descriptor, "summary.md", "orphan run summary")
        != prepared["summary"]):
      raise ValueError("unregistered run summary does not match")

    for directory_name, expected in (
        ("artifacts", prepared["artifacts"]),
        ("repair-rounds", prepared["repair_rounds"]),
    ):
      descriptor = _open_child_directory(
          run_descriptor, directory_name, f"orphan {directory_name}")
      try:
        if set(os.listdir(descriptor)) != set(expected):
          raise ValueError(
              f"unregistered run {directory_name} layout does not match")
        for name, payload in expected.items():
          if _read_regular_at(
              descriptor, name, f"orphan {directory_name} artifact") != payload:
            raise ValueError(
                f"unregistered run {directory_name} artifact does not match")
      finally:
        os.close(descriptor)
    return result_sha256
  finally:
    os.close(run_descriptor)


def _register_matching_orphan(
    runs_root: Path, root_descriptor: int, result: CombinedRunResult,
    prepared: dict, entries: list[dict], previous_registry: bytes | None,
) -> None:
  result_sha256 = _validate_matching_orphan(
      root_descriptor, result, prepared)
  try:
    _update_registry(
        runs_root, _registry_entry(result, result_sha256),
        root_descriptor=root_descriptor, entries=entries)
  except BaseException:
    _restore_registry_locked(
        root_descriptor, previous_registry, result.run_id)
    raise


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
  prepared = _prepare_run_payloads(result)
  final_destination = runs_root / result.run_id
  with _registry_lock(runs_root) as root_descriptor:
    existing, previous_registry = _read_registry_locked(
        root_descriptor, missing_ok=True)
    if any(item["run_id"] == result.run_id for item in existing):
      raise FileExistsError(f"run_id already exists: {result.run_id}")
    final_metadata = _entry_metadata(root_descriptor, result.run_id)
    if final_metadata is not None and not stat.S_ISDIR(final_metadata.st_mode):
      raise FileExistsError(f"run_id already exists: {result.run_id}")
    if final_metadata is not None:
      _register_matching_orphan(
          runs_root, root_descriptor, result, prepared, existing,
          previous_registry)
      return final_destination

  staging_name, owned_identity = _new_staging_directory(
      runs_root, result.run_id)
  destination = runs_root / staging_name
  published = False
  completed = False
  try:
    artifacts = destination / "artifacts"
    repair_rounds = destination / "repair-rounds"
    artifacts.mkdir()
    repair_rounds.mkdir()
    for name, payload in prepared["artifacts"].items():
      _write_exclusive(artifacts / name, payload)
    for name, payload in prepared["repair_rounds"].items():
      _write_exclusive(repair_rounds / name, payload)
    result_payload = prepared["result"]
    result_sha256 = _digest(result_payload)
    _write_exclusive(destination / "result.json", result_payload)
    _write_exclusive(destination / "summary.md", prepared["summary"])
    _write_exclusive(
        destination / "publication.json",
        _publication_payload(result, result_sha256, secrets.token_hex(16)))
    result_payload = _validate_and_sync_staging(destination, prepared)

    with _registry_lock(runs_root) as root_descriptor:
      entries, previous_registry = _read_registry_locked(
          root_descriptor, missing_ok=True)
      if any(item["run_id"] == result.run_id for item in entries):
        raise FileExistsError(f"run_id already exists: {result.run_id}")
      final_metadata = _entry_metadata(root_descriptor, result.run_id)
      if final_metadata is not None and not stat.S_ISDIR(final_metadata.st_mode):
        raise FileExistsError(f"run_id already exists: {result.run_id}")
      if final_metadata is not None:
        _register_matching_orphan(
            runs_root, root_descriptor, result, prepared, entries,
            previous_registry)
        return final_destination
      registry_started = False
      try:
        # Mark rollback responsibility before the syscall: a wrapper or signal
        # may report failure after the directory entry was already renamed.
        published = True
        os.rename(
            staging_name, result.run_id,
            src_dir_fd=root_descriptor, dst_dir_fd=root_descriptor)
        os.fsync(root_descriptor)
        registry_started = True
        _update_registry(
            runs_root, _registry_entry(result, _digest(result_payload)),
            root_descriptor=root_descriptor, entries=entries)
      except BaseException:
        if published:
          try:
            if registry_started:
              _restore_registry_locked(
                  root_descriptor, previous_registry, result.run_id)
          finally:
            try:
              _remove_owned_directory(
                  runs_root, result.run_id, owned_identity)
            finally:
              published = False
        raise
    completed = True
    return final_destination
  finally:
    if not completed and not published:
      _remove_owned_directory(runs_root, staging_name, owned_identity)


def _open_child_directory(
    parent_descriptor: int, name: str, label: str,
) -> int:
  try:
    descriptor = os.open(
        name, _directory_flags(), dir_fd=parent_descriptor)
  except OSError as exc:
    raise ValueError(f"{label} must be a real directory: {exc}") from exc
  metadata = os.fstat(descriptor)
  if not stat.S_ISDIR(metadata.st_mode):
    os.close(descriptor)
    raise ValueError(f"{label} must be a directory")
  return descriptor


def _read_regular_at(
    parent_descriptor: int, name: str, label: str,
) -> bytes:
  try:
    descriptor = os.open(name, _file_flags(), dir_fd=parent_descriptor)
  except OSError as exc:
    raise ValueError(f"{label} must be a regular file: {exc}") from exc
  try:
    return _read_fd_bytes(descriptor, label)
  finally:
    os.close(descriptor)


def _artifact_payload(
    run_descriptor: int, reference: dict, label: str, expected_path: str,
) -> dict:
  data = _closed_object(reference, {"path", "sha256"}, label)
  relative = _safe_relative_path(data["path"], f"{label} path")
  if relative.as_posix() != expected_path:
    raise ValueError(f"{label} path is not canonical for its case")
  if not isinstance(data["sha256"], str) or not _SHA256_RE.fullmatch(
      data["sha256"]):
    raise ValueError(f"{label} sha256 must be a SHA-256 digest")
  if len(relative.parts) != 2:
    raise ValueError(f"{label} path must contain one artifact directory")
  parent = _open_child_directory(
      run_descriptor, relative.parts[0], f"{label} parent")
  try:
    payload = _read_regular_at(parent, relative.parts[1], label)
  finally:
    os.close(parent)
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
    value: object, evaluation: IntegrityResult, run_descriptor: int,
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
    expected_path = (
        f"repair-rounds/{case_id}-round-{repair_round.attempt:02d}.json")
    parsed = _artifact_payload(
        run_descriptor,
        {"path": data["path"], "sha256": data["sha256"]},
        "repair round artifact", expected_path)
    if parsed != repair_round.to_dict():
      raise ValueError("repair round artifact does not match Task 8 result")
    expected = _repair_round_view(
        repair_round, data["path"], data["sha256"])
    if data != expected:
      raise ValueError("repair round view does not match Task 8 result")
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
  with _registry_lock(runs_root) as root_descriptor:
    entries, _ = _read_registry_locked(root_descriptor, missing_ok=False)
    matches = [entry for entry in entries if entry["run_id"] == selected]
    if len(matches) != 1:
      raise ValueError(f"unknown run_id: {selected}")
    registry_entry = matches[0]
    try:
      run_descriptor = os.open(
          selected, _directory_flags(), dir_fd=root_descriptor)
    except OSError as exc:
      raise ValueError(f"unknown run_id: {selected}") from exc
    try:
      if set(os.listdir(run_descriptor)) != {
          "artifacts", "repair-rounds", "result.json", "summary.md",
          "publication.json",
      }:
        raise ValueError("selected run contains unexpected entries")
      report_payload = _read_regular_at(
          run_descriptor, "result.json", "selected run result")
      if _digest(report_payload) != registry_entry["result_sha256"]:
        raise ValueError("selected run result SHA-256 mismatch")
      marker_payload = _read_regular_at(
          run_descriptor, "publication.json", "publication marker")
      _validate_publication_marker(
          marker_payload, selected, registry_entry["result_sha256"])
      try:
        report = json.loads(report_payload)
      except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read selected run: {exc}") from exc
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
      if not isinstance(data["cases"], list) or not data["cases"]:
        raise ValueError("run report cases must be a nonempty list")
      if (data["timestamp"] != registry_entry["timestamp"]
          or data["model"] != registry_entry["model"]
          or len(data["cases"]) != registry_entry["case_count"]):
        raise ValueError("run report metadata does not match its registry entry")
      _text(data["timestamp"], "timestamp")
      _text(data["model"], "model")

      seen = set()
      strict_cases = []
      expected_artifacts = set()
      expected_rounds = set()
      for value in data["cases"]:
        case = _closed_object(value, {
            "case_id", "first_pass", "final", "artifact",
        }, "run case", optional={
            "attack_family", "adversarial_score", "repair_rounds",
            "operational_failure"})
        case_id = case["case_id"]
        if (not isinstance(case_id, str) or not _CASE_ID_RE.fullmatch(case_id)
            or case_id in seen):
          raise ValueError("run case identifiers must be unique canonical IDs")
        seen.add(case_id)
        expected_artifact = f"artifacts/{case_id}.json"
        parsed = _artifact_payload(
            run_descriptor, case["artifact"], "case artifact",
            expected_artifact)
        expected_artifacts.add(f"{case_id}.json")
        evaluation = decode_integrity_result(parsed)
        strict = CombinedCaseResult(
            case_id=case_id, evaluation=evaluation,
            adversarial_score=case.get("adversarial_score"))
        if case.get("attack_family") != strict.attack_family:
          raise ValueError("attack_family does not match adversarial_score")
        if isinstance(evaluation, OperationalIntegrityEvalResult):
          expected_first = (
              None if evaluation.model_first_pass is None
              else _snapshot_view(evaluation.model_first_pass))
          if case["first_pass"] != expected_first:
            raise ValueError("first_pass does not match trusted snapshot")
          if case["final"] != _operational_view():
            raise ValueError("final does not match operational failure")
          if case.get("operational_failure") != (
              evaluation.operational_failure.to_dict()):
            raise ValueError(
                "operational failure view does not match its artifact")
        else:
          if "operational_failure" in case:
            raise ValueError(
                "successful evaluation cannot have operational_failure")
          _validate_snapshot_view(
              case["first_pass"], evaluation.model_first_pass, "first_pass")
          _validate_snapshot_view(
              case["final"], evaluation.system_final, "final")
        has_rounds = bool(evaluation.repair_rounds)
        if has_rounds != ("repair_rounds" in case):
          raise ValueError("repair_rounds presence does not match Task 8 result")
        if has_rounds:
          _validate_repair_views(
              case["repair_rounds"], evaluation, run_descriptor, case_id)
          expected_rounds.update(
              f"{case_id}-round-{item.attempt:02d}.json"
              for item in evaluation.repair_rounds)
        strict_cases.append(strict)

      artifacts_descriptor = _open_child_directory(
          run_descriptor, "artifacts", "artifact directory")
      try:
        if set(os.listdir(artifacts_descriptor)) != expected_artifacts:
          raise ValueError("artifact directory contains unexpected entries")
      finally:
        os.close(artifacts_descriptor)
      rounds_descriptor = _open_child_directory(
          run_descriptor, "repair-rounds", "repair-round directory")
      try:
        if set(os.listdir(rounds_descriptor)) != expected_rounds:
          raise ValueError("repair-round directory contains unexpected entries")
      finally:
        os.close(rounds_descriptor)
      _read_regular_at(run_descriptor, "summary.md", "run summary markdown")

      expected_summary = _status_summary(strict_cases)
      summary = _closed_object(
          data["summary"], {"case_count", "integrity_status_counts"},
          "run summary", optional={
              "attack_family_breakdown", "attack_family_confusion",
              "reason_code_metrics"})
      status_counts = _closed_object(
          summary["integrity_status_counts"], set(_STATUS_NAMES),
          "integrity status counts")
      if (isinstance(summary["case_count"], bool)
          or not isinstance(summary["case_count"], int)
          or summary["case_count"] < 1
          or any(isinstance(count, bool) or not isinstance(count, int)
                 or count < 0 for count in status_counts.values())
          or sum(status_counts.values()) != summary["case_count"]):
        raise ValueError("run summary counts are invalid")
      if "attack_family_breakdown" in summary:
        breakdown = summary["attack_family_breakdown"]
        if (not isinstance(breakdown, dict) or not breakdown
            or any(not isinstance(name, str) or not name.strip()
                   or isinstance(count, bool) or not isinstance(count, int)
                   or count < 1 for name, count in breakdown.items())):
          raise ValueError("attack_family_breakdown is invalid")
      if summary != expected_summary:
        raise ValueError("run summary does not match selected run cases")
      return data
    finally:
      os.close(run_descriptor)


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
