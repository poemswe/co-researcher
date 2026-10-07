"""Evaluation adapter for immutable literature-review integrity passes."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Protocol

from .core import AgentResult, CLI_CONFIG, TestCase, evaluate_output, find_cli


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_SAFE_TEMP_ROOT = Path("/tmp").resolve()
REVIEW_SCRIPTS = REPOSITORY_ROOT / "skills/literature-review/scripts"
if str(REVIEW_SCRIPTS) not in sys.path:
  sys.path.insert(0, str(REVIEW_SCRIPTS))

from review_integrity.models import (  # noqa: E402
    Finding,
    IntegrityRunReport,
    PassReport,
    ReasonCode,
    RepairRecord,
    Severity,
)
from review_integrity.repair import RepairController  # noqa: E402
from review_integrity.scoring import score_integrity  # noqa: E402
from review_integrity.validators import validate_snapshot  # noqa: E402
from review_integrity.workspace import WorkspaceError, load_workspace  # noqa: E402
import check_claims  # noqa: E402


SCHEMA_VERSION = "1.0.0"
ADVERSARIAL_SCHEMA_VERSION = "3.1.0"
_PRE_ASSESSABLE_ADVERSARIAL_VERSION = "3.0.0"
UNASSESSABLE_REASONS = frozenset({"first_pass_unloadable", "attack_not_reproduced"})
CAPABILITY = "literature-review-integrity"
QUALITY_RUBRIC_ID = "literature-review-v1"
QUALITY_DIMENSIONS = (
    "research-quality", "analytical-quality", "output-structure")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_CASE_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")

EXECUTOR_VERSION = "1.0.0"
CAPTURE_PROMPT_VERSION = "literature-integrity-capture-v2"
CAPTURE_INSTRUCTION = """Evaluation capture mode.
Read and follow the repository literature-review skill at the supplied path.
Create the complete literature-review workspace in the current directory.
Use the current directory itself as the review workspace: set WS="$(pwd)"
in step 1. Do not create review/{slug} or any other workspace subdirectory.
Write $WS/project.json as the skill's scope step describes.
Stop immediately after writing the workspace artifacts. Do not run the
plugin validation, repair, or delivery phase; the evaluation harness owns
those phases. Do not ask for or infer evaluator-only expectations.
"""
CAPTURE_PROMPT_SHA256 = hashlib.sha256(
    CAPTURE_INSTRUCTION.encode("utf-8")).hexdigest()
REPAIR_PROMPT_VERSION = "literature-integrity-repair-v1"
REPAIR_INSTRUCTION = """Repair evaluation workspace artifacts in the current
directory using only the supplied public validator feedback. Do not validate,
score, or deliver the review. Stop immediately after updating the artifacts.
"""
REPAIR_PROMPT_SHA256 = hashlib.sha256(
    REPAIR_INSTRUCTION.encode("utf-8")).hexdigest()
_CLAUDE_CAPTURE_TOOLS = (
    "WebSearch,WebFetch,Read,Grep,Glob,Write,Edit,Bash")
_CLAUDE_REPAIR_TOOLS = "Read,Grep,Glob,Write,Edit,Bash"
_MAX_COLLECTION_FILE_BYTES = 8 * 1024 * 1024
_MAX_COLLECTION_BYTES = 64 * 1024 * 1024
_MAX_COLLECTION_FILES = 4096
_SAFE_SYSTEM_PATH = (
    "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
_COMMON_CHILD_ENV = frozenset({
    "ALL_PROXY", "CURL_CA_BUNDLE", "HOME", "HTTPS_PROXY", "HTTP_PROXY",
    "LANG", "LC_ALL", "LC_CTYPE", "LOGNAME", "NO_PROXY",
    "NODE_EXTRA_CA_CERTS", "REQUESTS_CA_BUNDLE", "SHELL", "SSL_CERT_DIR",
    "SSL_CERT_FILE", "TERM", "TZ", "USER", "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "all_proxy",
    "http_proxy", "https_proxy", "no_proxy",
})
_PATH_CHILD_ENV = frozenset({
    "AWS_CONFIG_FILE", "AWS_SHARED_CREDENTIALS_FILE", "CLAUDE_CONFIG_DIR",
    "CODEX_HOME", "GEMINI_CLI_HOME", "GOOGLE_APPLICATION_CREDENTIALS",
    "HOME", "NODE_EXTRA_CA_CERTS", "REQUESTS_CA_BUNDLE", "SSL_CERT_DIR",
    "SSL_CERT_FILE", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
    "XDG_STATE_HOME", "CURL_CA_BUNDLE",
})
_PROVIDER_CHILD_ENV = {
    "claude": frozenset({
        "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
        "ANTHROPIC_VERTEX_PROJECT_ID",
        "AWS_ACCESS_KEY_ID", "AWS_CONFIG_FILE", "AWS_DEFAULT_REGION",
        "AWS_PROFILE", "AWS_REGION", "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN", "AWS_SHARED_CREDENTIALS_FILE",
        "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CONFIG_DIR",
        "CLOUD_ML_REGION", "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CLOUD_PROJECT",
    }),
    "codex": frozenset({
        "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_ENDPOINT", "CODEX_HOME", "OPENAI_API_KEY",
        "OPENAI_API_BASE", "OPENAI_BASE_URL", "OPENAI_ORG_ID",
        "OPENAI_PROJECT_ID",
    }),
    "gemini": frozenset({
        "GEMINI_API_KEY", "GEMINI_CLI_HOME", "GOOGLE_API_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_LOCATION",
        "GOOGLE_CLOUD_PROJECT", "GOOGLE_GENAI_USE_GCA",
        "GOOGLE_GENAI_USE_VERTEXAI",
    }),
}
def _closed_object(value: object, fields: set[str], label: str) -> dict:
  if not isinstance(value, dict):
    raise ValueError(f"{label} must be a JSON object")
  unknown = set(value) - fields
  missing = fields - set(value)
  if unknown:
    raise ValueError(f"{label} has unknown fields: {sorted(unknown)}")
  if missing:
    raise ValueError(f"{label} is missing fields: {sorted(missing)}")
  return value


def _wire_object(value: object, fields: set[str], label: str) -> dict:
  data = _closed_object(value, fields | {"schema_version"}, label)
  if data["schema_version"] != SCHEMA_VERSION:
    raise ValueError(f"unsupported {label} schema_version")
  return data


def _text(value: object, label: str) -> str:
  if not isinstance(value, str) or not value.strip():
    raise ValueError(f"{label} must be nonempty text")
  return value


def _finite_score(value: object, label: str) -> float:
  if isinstance(value, bool) or not isinstance(value, (int, float)):
    raise ValueError(f"{label} must be a number")
  score = float(value)
  if not math.isfinite(score) or not 0.0 <= score <= 100.0:
    raise ValueError(f"{label} must be between 0 and 100")
  return score


@dataclass(frozen=True, slots=True)
class PublicFixture:
  relative_path: PurePosixPath
  content: bytes

  def __post_init__(self) -> None:
    if (not isinstance(self.relative_path, PurePosixPath)
        or self.relative_path.is_absolute()
        or not self.relative_path.parts
        or any(part in {".", ".."} for part in self.relative_path.parts)):
      raise ValueError("public fixture path must be canonical and relative")
    if self.relative_path.name in {"case.json", "expected.json"}:
      raise ValueError("public fixture must not use a harness-owned name")
    if not isinstance(self.content, bytes):
      raise ValueError("public fixture content must be immutable bytes")


class ModelExecutionError(RuntimeError):
  """A model CLI failed to run; the case was not evaluated."""


WORKSPACE_TAMPERS = frozenset({"missing", "malformed", "symlink", "traversal"})
_TAMPER_MANIFEST_ARTIFACTS = (
    "protocol.md", "corpus.json", "claims.json", "synthesis.md", "refs.json")


def apply_workspace_tamper(tamper: str, workspace: Path) -> None:
  """Corrupt a submitted workspace the way an operational attack would."""
  if tamper == "missing":
    (workspace / "refs.json").unlink(missing_ok=True)
  elif tamper == "malformed":
    (workspace / "claims.json").write_text("{not-json", encoding="utf-8")
  elif tamper == "symlink":
    claims = workspace / "claims.json"
    target = workspace / "claims.target.json"
    if claims.exists():
      claims.replace(target)
    claims.symlink_to(target.name)
  elif tamper == "traversal":
    (workspace / "project.json").unlink(missing_ok=True)
    papers = sorted(
        path.relative_to(workspace).as_posix()
        for path in (workspace / "papers").rglob("*")
        if path.is_file() and path.name in {"fulltext.md", "abstract.md"})
    (workspace / "run-manifest.json").write_text(json.dumps({
        "schema_version": "1.0.0",
        "artifacts": [*_TAMPER_MANIFEST_ARTIFACTS, *papers, "../outside.json"],
    }), encoding="utf-8")
  else:
    raise ValueError(f"unknown workspace_tamper: {tamper!r}")


@dataclass(frozen=True, slots=True)
class CaseDefinition:
  case_id: str
  prompt: str
  domain: str
  fixture_files: tuple[PublicFixture, ...]
  quality_rubric_id: str
  workspace_tamper: str | None = None

  def __post_init__(self) -> None:
    if (self.workspace_tamper is not None
        and self.workspace_tamper not in WORKSPACE_TAMPERS):
      raise ValueError(
          f"unknown workspace_tamper: {self.workspace_tamper!r}")
    if not isinstance(self.case_id, str) or not _CASE_ID_RE.fullmatch(
        self.case_id):
      raise ValueError("case_id must be a lowercase hyphenated identifier")
    _text(self.prompt, "prompt")
    _text(self.domain, "domain")
    if self.quality_rubric_id != QUALITY_RUBRIC_ID:
      raise ValueError(
          f"quality_rubric_id must be {QUALITY_RUBRIC_ID!r}")
    if not isinstance(self.fixture_files, tuple) or not all(
        isinstance(item, PublicFixture) for item in self.fixture_files):
      raise ValueError("fixture_files must contain PublicFixture values")


@dataclass(frozen=True, slots=True)
class ModelUsage:
  duration_seconds: float
  input_tokens: int | None
  output_tokens: int | None
  estimated_cost_usd: float | None
  executor_version: str
  prompt_version: str
  prompt_sha256: str

  def __post_init__(self) -> None:
    if (isinstance(self.duration_seconds, bool)
        or not isinstance(self.duration_seconds, (int, float))
        or not math.isfinite(float(self.duration_seconds))
        or self.duration_seconds < 0):
      raise ValueError("duration_seconds must be a nonnegative finite number")
    for value, label in (
        (self.input_tokens, "input_tokens"),
        (self.output_tokens, "output_tokens"),
    ):
      if value is not None and (
          isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise ValueError(f"{label} must be a nonnegative integer or null")
    if self.estimated_cost_usd is not None and (
        isinstance(self.estimated_cost_usd, bool)
        or not isinstance(self.estimated_cost_usd, (int, float))
        or not math.isfinite(float(self.estimated_cost_usd))
        or self.estimated_cost_usd < 0):
      raise ValueError(
          "estimated_cost_usd must be a nonnegative finite number or null")
    _text(self.executor_version, "executor_version")
    _text(self.prompt_version, "prompt_version")
    if not isinstance(self.prompt_sha256, str) or not _SHA256_RE.fullmatch(
        self.prompt_sha256):
      raise ValueError("prompt_sha256 must be a SHA-256 digest")

  def to_dict(self) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "duration_seconds": float(self.duration_seconds),
        "input_tokens": self.input_tokens,
        "output_tokens": self.output_tokens,
        "estimated_cost_usd": self.estimated_cost_usd,
        "executor_version": self.executor_version,
        "prompt_version": self.prompt_version,
        "prompt_sha256": self.prompt_sha256,
    }

  @classmethod
  def from_dict(cls, value: dict) -> "ModelUsage":
    data = _wire_object(value, {
        "duration_seconds", "input_tokens", "output_tokens",
        "estimated_cost_usd", "executor_version", "prompt_version",
        "prompt_sha256",
    }, "model usage")
    return cls(**{key: data[key] for key in data if key != "schema_version"})


@dataclass(frozen=True, slots=True)
class QualityResult:
  quality_score: float | None
  scores: Mapping[str, float]
  error: str | None

  def __post_init__(self) -> None:
    if self.quality_score is None:
      if self.scores:
        raise ValueError("failed quality results cannot contain scores")
      _text(self.error, "quality error")
      object.__setattr__(self, "scores", MappingProxyType({}))
      return
    object.__setattr__(
        self, "quality_score", _finite_score(
            self.quality_score, "quality_score"))
    if self.error is not None:
      raise ValueError("successful quality results cannot contain an error")
    if set(self.scores) != set(QUALITY_DIMENSIONS):
      raise ValueError("quality scores must use the canonical dimensions")
    object.__setattr__(self, "scores", MappingProxyType({
        name: _finite_score(self.scores[name], name)
        for name in QUALITY_DIMENSIONS
    }))

  @classmethod
  def failed(cls, error: object) -> "QualityResult":
    message = str(error).strip() or error.__class__.__name__
    return cls(quality_score=None, scores={}, error=message)

  def to_dict(self) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "quality_score": self.quality_score,
        "scores": dict(self.scores),
        "error": self.error,
    }

  @classmethod
  def from_dict(cls, value: dict) -> "QualityResult":
    data = _wire_object(
        value, {"quality_score", "scores", "error"}, "quality result")
    if not isinstance(data["scores"], dict):
      raise ValueError("quality scores must be a dictionary")
    return cls(
        quality_score=data["quality_score"], scores=data["scores"],
        error=data["error"])


@dataclass(frozen=True, slots=True)
class SnapshotEvaluation:
  workspace_manifest_sha256: str
  quality: QualityResult
  integrity: PassReport
  model_usage: ModelUsage

  def __post_init__(self) -> None:
    if not isinstance(self.workspace_manifest_sha256, str) or not (
        _SHA256_RE.fullmatch(self.workspace_manifest_sha256)):
      raise ValueError("workspace_manifest_sha256 must be a SHA-256 digest")
    if not isinstance(self.quality, QualityResult):
      raise ValueError("quality must be a QualityResult")
    if not isinstance(self.integrity, PassReport):
      raise ValueError("integrity must be a PassReport")
    if self.integrity.manifest_sha256 != self.workspace_manifest_sha256:
      raise ValueError("integrity and quality must identify one snapshot")
    if not isinstance(self.model_usage, ModelUsage):
      raise ValueError("model_usage must be a ModelUsage")

  def to_dict(self) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace_manifest_sha256": self.workspace_manifest_sha256,
        "quality": self.quality.to_dict(),
        "integrity": self.integrity.to_dict(),
        "model_usage": self.model_usage.to_dict(),
    }

  @classmethod
  def from_dict(cls, value: dict) -> "SnapshotEvaluation":
    data = _wire_object(value, {
        "workspace_manifest_sha256", "quality", "integrity", "model_usage",
    }, "snapshot evaluation")
    return cls(
        workspace_manifest_sha256=data["workspace_manifest_sha256"],
        quality=QualityResult.from_dict(data["quality"]),
        integrity=PassReport.from_dict(data["integrity"]),
        model_usage=ModelUsage.from_dict(data["model_usage"]),
    )


@dataclass(frozen=True, slots=True)
class RepairRound:
  attempt: int
  previous_integrity: PassReport
  integrity: PassReport
  workspace_manifest_sha256: str
  reason_codes: tuple[ReasonCode, ...]
  action: str
  model_usage: ModelUsage

  def __post_init__(self) -> None:
    if isinstance(self.attempt, bool) or not isinstance(
        self.attempt, int) or self.attempt < 1:
      raise ValueError("attempt must be a positive integer")
    if not isinstance(self.previous_integrity, PassReport):
      raise ValueError("previous_integrity must be a PassReport")
    if not isinstance(self.integrity, PassReport):
      raise ValueError("integrity must be a PassReport")
    if self.integrity.manifest_sha256 != self.workspace_manifest_sha256:
      raise ValueError("repair integrity must match its snapshot")
    if not isinstance(self.reason_codes, (list, tuple)):
      raise ValueError("reason_codes must be a list")
    try:
      reason_codes = tuple(ReasonCode(code) for code in self.reason_codes)
    except (TypeError, ValueError) as exc:
      raise ValueError("reason_codes contain an unknown value") from exc
    expected_reason_codes = tuple(dict.fromkeys(
        finding.reason_code for finding in self.integrity.findings))
    if reason_codes != expected_reason_codes:
      raise ValueError("reason_codes must match repair integrity findings")
    object.__setattr__(self, "reason_codes", reason_codes)
    if self.action not in {"repair", "pass", "stop_invalid"}:
      raise ValueError("unknown repair action")
    if not isinstance(self.model_usage, ModelUsage):
      raise ValueError("model_usage must be a ModelUsage")

  def to_dict(self) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "attempt": self.attempt,
        "previous_integrity": self.previous_integrity.to_dict(),
        "integrity": self.integrity.to_dict(),
        "workspace_manifest_sha256": self.workspace_manifest_sha256,
        "reason_codes": [code.value for code in self.reason_codes],
        "action": self.action,
        "model_usage": self.model_usage.to_dict(),
    }

  @classmethod
  def from_dict(cls, value: dict) -> "RepairRound":
    data = _wire_object(value, {
        "attempt", "previous_integrity", "integrity",
        "workspace_manifest_sha256", "reason_codes", "action", "model_usage",
    }, "repair round")
    return cls(
        attempt=data["attempt"],
        previous_integrity=PassReport.from_dict(data["previous_integrity"]),
        integrity=PassReport.from_dict(data["integrity"]),
        workspace_manifest_sha256=data["workspace_manifest_sha256"],
        reason_codes=data["reason_codes"],
        action=data["action"],
        model_usage=ModelUsage.from_dict(data["model_usage"]),
    )


@dataclass(frozen=True, slots=True)
class RepairCost:
  rounds: int
  duration_seconds: float
  input_tokens: int | None
  output_tokens: int | None
  estimated_cost_usd: float | None

  def __post_init__(self) -> None:
    if isinstance(self.rounds, bool) or not isinstance(
        self.rounds, int) or not 0 <= self.rounds <= 3:
      raise ValueError("repair cost rounds must be between zero and three")
    if (isinstance(self.duration_seconds, bool)
        or not isinstance(self.duration_seconds, (int, float))
        or not math.isfinite(float(self.duration_seconds))
        or self.duration_seconds < 0):
      raise ValueError("repair duration must be nonnegative and finite")
    for value, label in (
        (self.input_tokens, "input_tokens"),
        (self.output_tokens, "output_tokens"),
    ):
      if value is not None and (
          isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise ValueError(f"{label} must be a nonnegative integer or null")
    if self.estimated_cost_usd is not None and (
        isinstance(self.estimated_cost_usd, bool)
        or not isinstance(self.estimated_cost_usd, (int, float))
        or not math.isfinite(float(self.estimated_cost_usd))
        or self.estimated_cost_usd < 0):
      raise ValueError("repair cost must be nonnegative and finite or null")

  @classmethod
  def from_rounds(cls, rounds: tuple[RepairRound, ...]) -> "RepairCost":
    return cls.from_usages(tuple(item.model_usage for item in rounds))

  @classmethod
  def from_usages(cls, usages: tuple[ModelUsage, ...]) -> "RepairCost":
    if not isinstance(usages, tuple) or not all(
        isinstance(item, ModelUsage) for item in usages):
      raise ValueError("repair usages must contain ModelUsage values")

    def optional_sum(attribute: str) -> int | float | None:
      values = tuple(getattr(usage, attribute) for usage in usages)
      if any(value is None for value in values):
        return None
      return sum(values)

    return cls(
        rounds=len(usages),
        duration_seconds=sum(usage.duration_seconds for usage in usages),
        input_tokens=optional_sum("input_tokens"),
        output_tokens=optional_sum("output_tokens"),
        estimated_cost_usd=optional_sum("estimated_cost_usd"),
    )

  def to_dict(self) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "rounds": self.rounds,
        "duration_seconds": self.duration_seconds,
        "input_tokens": self.input_tokens,
        "output_tokens": self.output_tokens,
        "estimated_cost_usd": self.estimated_cost_usd,
    }

  @classmethod
  def from_dict(cls, value: dict) -> "RepairCost":
    data = _wire_object(value, {
        "rounds", "duration_seconds", "input_tokens", "output_tokens",
        "estimated_cost_usd",
    }, "repair cost")
    return cls(**{key: data[key] for key in data if key != "schema_version"})


@dataclass(frozen=True, slots=True)
class RobustnessResult:
  expected_final_status: str | None
  observed_final_status: str
  minimum_repair_rounds: int | None
  maximum_repair_rounds: int | None
  expectation_met: bool | None
  error: str | None

  def __post_init__(self) -> None:
    statuses = {"valid", "valid_with_warnings", "invalid"}
    if self.observed_final_status not in statuses:
      raise ValueError("observed_final_status is invalid")
    if self.expected_final_status is None:
      if (self.minimum_repair_rounds is not None
          or self.maximum_repair_rounds is not None):
        raise ValueError("repair bounds must be null without an expectation")
      if self.expectation_met is not None:
        raise ValueError("expectation_met must be null without an expectation")
      _text(self.error, "robustness error")
    else:
      if self.expected_final_status not in statuses:
        raise ValueError("expected_final_status is invalid")
      minimum = self.minimum_repair_rounds
      maximum = self.maximum_repair_rounds
      if (isinstance(minimum, bool) or not isinstance(minimum, int)
          or isinstance(maximum, bool) or not isinstance(maximum, int)
          or minimum < 0 or maximum < minimum or maximum > 3):
        raise ValueError("robustness repair bounds are invalid")
      if not isinstance(self.expectation_met, bool):
        raise ValueError("expectation_met must be a boolean")
      if self.error is not None:
        raise ValueError("scored robustness cannot contain an error")

  def to_dict(self) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "expected_final_status": self.expected_final_status,
        "observed_final_status": self.observed_final_status,
        "minimum_repair_rounds": self.minimum_repair_rounds,
        "maximum_repair_rounds": self.maximum_repair_rounds,
        "expectation_met": self.expectation_met,
        "error": self.error,
    }

  @classmethod
  def from_dict(cls, value: dict) -> "RobustnessResult":
    data = _wire_object(value, {
        "expected_final_status", "observed_final_status", "expectation_met",
        "minimum_repair_rounds", "maximum_repair_rounds", "error",
    }, "robustness result")
    return cls(**{key: data[key] for key in data if key != "schema_version"})


def _replay_repair_chain(
    first: SnapshotEvaluation,
    rounds: tuple[RepairRound, ...],
) -> str:
  """Validate one retained chain and return its latest trusted action."""
  if len(rounds) > 3 or any(
      item.attempt != index for index, item in enumerate(rounds, 1)):
    raise ValueError("repair rounds must be bounded and contiguous")
  previous_integrity = first.integrity
  for repair_round in rounds:
    if repair_round.previous_integrity != previous_integrity:
      raise ValueError("repair round previous integrity breaks the chain")
    previous_integrity = repair_round.integrity
  initial_action = "repair" if first.integrity.repair_required else "pass"
  try:
    strict_run = IntegrityRunReport(
        pass_report=first.integrity,
        workspace_manifest_sha256=first.workspace_manifest_sha256,
        action=initial_action,
        quality_score=None,
        repairs=tuple(RepairRecord(
            attempt=repair_round.attempt,
            pass_report=repair_round.integrity,
            workspace_manifest_sha256=repair_round.workspace_manifest_sha256,
            reason_codes=repair_round.reason_codes,
            action=repair_round.action,
            resolved=(repair_round.integrity.status.value != "invalid"),
        ) for repair_round in rounds),
    )
    RepairController.from_run_report(strict_run)
  except ValueError as exc:
    raise ValueError(f"repair policy replay failed: {exc}") from exc
  return rounds[-1].action if rounds else strict_run.action


@dataclass(frozen=True, slots=True)
class IntegrityEvalResult:
  model_first_pass: SnapshotEvaluation
  repair_rounds: tuple[RepairRound, ...]
  system_final: SnapshotEvaluation
  repair_cost: RepairCost
  robustness: RobustnessResult

  def __post_init__(self) -> None:
    if not isinstance(self.model_first_pass, SnapshotEvaluation):
      raise ValueError("model_first_pass must be a SnapshotEvaluation")
    if not isinstance(self.repair_rounds, tuple) or not all(
        isinstance(item, RepairRound) for item in self.repair_rounds):
      raise ValueError("repair_rounds must contain RepairRound values")
    final_action = _replay_repair_chain(
        self.model_first_pass, self.repair_rounds)
    if final_action not in {"pass", "stop_invalid"}:
      raise ValueError("repair policy replay did not reach a terminal action")
    if not isinstance(self.system_final, SnapshotEvaluation):
      raise ValueError("system_final must be a SnapshotEvaluation")
    expected_final = (
        self.repair_rounds[-1].integrity if self.repair_rounds
        else self.model_first_pass.integrity)
    if self.system_final.integrity != expected_final:
      raise ValueError("system_final integrity must be the final snapshot")
    expected_usage = (
        self.repair_rounds[-1].model_usage if self.repair_rounds
        else self.model_first_pass.model_usage)
    if self.system_final.model_usage != expected_usage:
      raise ValueError("system_final usage must match the final model pass")
    if (not isinstance(self.repair_cost, RepairCost)
        or self.repair_cost != RepairCost.from_rounds(self.repair_rounds)):
      raise ValueError("repair_cost must match repair_rounds")
    if not isinstance(self.robustness, RobustnessResult):
      raise ValueError("robustness must be a RobustnessResult")
    if (self.robustness.observed_final_status
        != self.system_final.integrity.status.value):
      raise ValueError("robustness must describe system_final")
    if self.robustness.expected_final_status is not None:
      expected_robustness = (
          self.robustness.observed_final_status
          == self.robustness.expected_final_status
          and self.robustness.minimum_repair_rounds
          <= len(self.repair_rounds)
          <= self.robustness.maximum_repair_rounds)
      if self.robustness.expectation_met != expected_robustness:
        raise ValueError("robustness expectation does not match retained bounds")

  def to_dict(self) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_first_pass": self.model_first_pass.to_dict(),
        "repair_rounds": [item.to_dict() for item in self.repair_rounds],
        "system_final": self.system_final.to_dict(),
        "repair_cost": self.repair_cost.to_dict(),
        "robustness": self.robustness.to_dict(),
    }

  @classmethod
  def from_dict(cls, value: dict) -> "IntegrityEvalResult":
    data = _wire_object(value, {
        "model_first_pass", "repair_rounds", "system_final", "repair_cost",
        "robustness",
    }, "integrity eval result")
    if not isinstance(data["repair_rounds"], list):
      raise ValueError("repair_rounds must be a list")
    return cls(
        model_first_pass=SnapshotEvaluation.from_dict(
            data["model_first_pass"]),
        repair_rounds=tuple(
            RepairRound.from_dict(item) for item in data["repair_rounds"]),
        system_final=SnapshotEvaluation.from_dict(data["system_final"]),
        repair_cost=RepairCost.from_dict(data["repair_cost"]),
        robustness=RobustnessResult.from_dict(data["robustness"]),
    )


@dataclass(frozen=True, slots=True)
class OperationalFailure:
  phase: str
  attempt: int
  reason_code: ReasonCode
  artifact: str
  message: str
  model_usage: ModelUsage

  def __post_init__(self) -> None:
    if self.phase not in {"initial_load", "repair_load"}:
      raise ValueError("operational failure phase is invalid")
    if (isinstance(self.attempt, bool) or not isinstance(self.attempt, int)
        or not 0 <= self.attempt <= 3):
      raise ValueError("operational failure attempt must be between zero and three")
    if (self.phase == "initial_load") != (self.attempt == 0):
      raise ValueError("operational failure phase and attempt disagree")
    object.__setattr__(self, "reason_code", ReasonCode(self.reason_code))
    _text(self.artifact, "operational failure artifact")
    _text(self.message, "operational failure message")
    if not isinstance(self.model_usage, ModelUsage):
      raise ValueError("operational failure model_usage is invalid")

  def to_dict(self) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": self.phase,
        "attempt": self.attempt,
        "reason_code": self.reason_code.value,
        "artifact": self.artifact,
        "message": self.message,
        "model_usage": self.model_usage.to_dict(),
        "status": "invalid",
        "workspace_manifest_sha256": None,
        "quality": None,
    }

  @classmethod
  def from_dict(cls, value: dict) -> "OperationalFailure":
    data = _wire_object(value, {
        "phase", "attempt", "reason_code", "artifact", "message",
        "model_usage", "status", "workspace_manifest_sha256", "quality",
    }, "operational failure")
    if (data["status"] != "invalid"
        or data["workspace_manifest_sha256"] is not None
        or data["quality"] is not None):
      raise ValueError("operational failure derived fields are invalid")
    return cls(
        phase=data["phase"], attempt=data["attempt"],
        reason_code=data["reason_code"], artifact=data["artifact"],
        message=data["message"],
        model_usage=ModelUsage.from_dict(data["model_usage"]),
    )


@dataclass(frozen=True, slots=True)
class OperationalIntegrityEvalResult:
  model_first_pass: SnapshotEvaluation | None
  repair_rounds: tuple[RepairRound, ...]
  operational_failure: OperationalFailure
  repair_cost: RepairCost
  robustness: RobustnessResult

  def __post_init__(self) -> None:
    if self.model_first_pass is not None and not isinstance(
        self.model_first_pass, SnapshotEvaluation):
      raise ValueError("model_first_pass must be a SnapshotEvaluation or null")
    if not isinstance(self.repair_rounds, tuple) or not all(
        isinstance(item, RepairRound) for item in self.repair_rounds):
      raise ValueError("repair_rounds must contain RepairRound values")
    if any(item.attempt != index for index, item in enumerate(
        self.repair_rounds, 1)):
      raise ValueError("repair rounds must be contiguous")
    if not isinstance(self.operational_failure, OperationalFailure):
      raise ValueError("operational_failure must be an OperationalFailure")
    if self.operational_failure.phase == "initial_load":
      if self.model_first_pass is not None or self.repair_rounds:
        raise ValueError("initial load failure cannot retain trusted snapshots")
      expected_usages = ()
    else:
      if self.model_first_pass is None:
        raise ValueError("repair load failure requires a trusted first pass")
      if self.operational_failure.attempt != len(self.repair_rounds) + 1:
        raise ValueError("repair failure attempt must follow successful rounds")
      if _replay_repair_chain(
          self.model_first_pass, self.repair_rounds) != "repair":
        raise ValueError(
            "repair load failure must follow a trusted repair action")
      expected_usages = tuple(
          item.model_usage for item in self.repair_rounds) + (
              self.operational_failure.model_usage,)
    if self.repair_cost != RepairCost.from_usages(expected_usages):
      raise ValueError("repair_cost must match every submitted repair attempt")
    if (not isinstance(self.robustness, RobustnessResult)
        or self.robustness.observed_final_status != "invalid"):
      raise ValueError("operational robustness must report invalid")
    if self.robustness.expected_final_status is not None:
      expected = (
          self.robustness.expected_final_status == "invalid"
          and self.robustness.minimum_repair_rounds
          <= self.operational_failure.attempt
          <= self.robustness.maximum_repair_rounds)
      if self.robustness.expectation_met != expected:
        raise ValueError(
            "operational robustness expectation does not match attempts")

  def to_dict(self) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_first_pass": (
            None if self.model_first_pass is None
            else self.model_first_pass.to_dict()),
        "repair_rounds": [item.to_dict() for item in self.repair_rounds],
        "operational_failure": self.operational_failure.to_dict(),
        "repair_cost": self.repair_cost.to_dict(),
        "robustness": self.robustness.to_dict(),
    }

  @classmethod
  def from_dict(cls, value: dict) -> "OperationalIntegrityEvalResult":
    data = _wire_object(value, {
        "model_first_pass", "repair_rounds", "operational_failure",
        "repair_cost", "robustness",
    }, "operational integrity eval result")
    if not isinstance(data["repair_rounds"], list):
      raise ValueError("repair_rounds must be a list")
    return cls(
        model_first_pass=(
            None if data["model_first_pass"] is None
            else SnapshotEvaluation.from_dict(data["model_first_pass"])),
        repair_rounds=tuple(
            RepairRound.from_dict(item) for item in data["repair_rounds"]),
        operational_failure=OperationalFailure.from_dict(
            data["operational_failure"]),
        repair_cost=RepairCost.from_dict(data["repair_cost"]),
        robustness=RobustnessResult.from_dict(data["robustness"]),
    )


IntegrityResult = IntegrityEvalResult | OperationalIntegrityEvalResult


def decode_integrity_result(value: dict) -> IntegrityResult:
  if not isinstance(value, dict):
    raise ValueError("integrity result must be a JSON object")
  if "operational_failure" in value:
    return OperationalIntegrityEvalResult.from_dict(value)
  return IntegrityEvalResult.from_dict(value)


class ModelExecutor(Protocol):
  def first_pass(
      self, case: CaseDefinition, workspace: Path,
  ) -> ModelUsage: ...

  def repair(self, feedback: dict, workspace: Path) -> ModelUsage: ...


class QualityJudge(Protocol):
  def score(
      self, case: CaseDefinition, synthesis: str,
  ) -> QualityResult: ...


def _read_json_bytes(content: bytes, label: str) -> object:
  try:
    return json.loads(content.decode("utf-8"))
  except (UnicodeError, json.JSONDecodeError) as exc:
    raise ValueError(f"cannot read {label}: {exc}") from exc


@dataclass(frozen=True, slots=True)
class _CollectionFile:
  relative_path: PurePosixPath
  content: bytes


def _load_case(
    definition: _CollectionFile,
    collection: Mapping[PurePosixPath, _CollectionFile],
) -> CaseDefinition:
  fields = {
      "schema_version", "capability", "case_id", "prompt", "domain",
      "fixture_paths", "quality_rubric_id",
  }
  raw = _read_json_bytes(definition.content, "case definition")
  if isinstance(raw, dict) and "workspace_tamper" in raw:
    fields.add("workspace_tamper")
  data = _closed_object(raw, fields, "case definition")
  if data["schema_version"] != SCHEMA_VERSION:
    raise ValueError("unsupported case schema_version")
  if data["capability"] != CAPABILITY:
    raise ValueError("case capability does not match directory capability")
  if not isinstance(data["fixture_paths"], list) or not all(
      isinstance(item, str) and item for item in data["fixture_paths"]):
    raise ValueError("fixture_paths must be a list of nonempty text paths")
  base = definition.relative_path.parent
  fixtures = []
  for item in data["fixture_paths"]:
    relative = PurePosixPath(item)
    if (relative.is_absolute() or not relative.parts
        or any(part in {".", ".."} for part in relative.parts)
        or relative.as_posix() != item):
      raise ValueError("fixture paths must be canonical relative paths")
    if relative.name in {"case.json", "expected.json"}:
      raise ValueError("fixture paths must not reference harness-owned files")
    source = collection.get(base / relative)
    if source is None:
      raise ValueError(f"fixture path is not a file: {item}")
    fixtures.append(PublicFixture(
        relative_path=relative, content=source.content))
  return CaseDefinition(
      case_id=data["case_id"],
      prompt=_text(data["prompt"], "prompt"),
      domain=_text(data["domain"], "domain"),
      fixture_files=tuple(fixtures),
      quality_rubric_id=data["quality_rubric_id"],
      workspace_tamper=data.get("workspace_tamper"),
  )


def _collection_flags(*, directory: bool) -> int:
  flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | os.O_NOFOLLOW
  return flags | os.O_DIRECTORY if directory else flags


def _open_collection_root(root: Path) -> int:
  absolute = Path(os.path.abspath(os.fspath(root)))
  current = os.open(os.path.sep, _collection_flags(directory=True))
  try:
    for component in absolute.parts[1:]:
      metadata = os.stat(component, dir_fd=current, follow_symlinks=False)
      if stat.S_ISLNK(metadata.st_mode):
        raise ValueError("collection path contains a symlink ancestor")
      if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("collection path ancestor is not a directory")
      child = os.open(
          component, _collection_flags(directory=True), dir_fd=current)
      opened = os.fstat(child)
      if (opened.st_dev, opened.st_ino) != (
          metadata.st_dev, metadata.st_ino):
        os.close(child)
        raise ValueError("collection directory identity changed during open")
      os.close(current)
      current = child
    return current
  except OSError as exc:
    os.close(current)
    raise ValueError(
        f"cannot securely open collection path; symlink or swap: {exc}") from exc
  except Exception:
    os.close(current)
    raise


def _read_collection_file(
    parent: int, name: str, expected: os.stat_result,
) -> bytes:
  descriptor = os.open(
      name, _collection_flags(directory=False), dir_fd=parent)
  try:
    opened = os.fstat(descriptor)
    if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
        or (opened.st_dev, opened.st_ino)
        != (expected.st_dev, expected.st_ino)):
      raise ValueError("collection file identity changed or is aliased")
    if opened.st_size > _MAX_COLLECTION_FILE_BYTES:
      raise ValueError("collection file exceeds size limit")
    chunks = []
    total = 0
    while chunk := os.read(
        descriptor, min(1024 * 1024, _MAX_COLLECTION_FILE_BYTES + 1 - total)):
      total += len(chunk)
      if total > _MAX_COLLECTION_FILE_BYTES:
        raise ValueError("collection file exceeds size limit")
      chunks.append(chunk)
    return b"".join(chunks)
  finally:
    os.close(descriptor)


def _discover_named_paths(root: Path) -> tuple[_CollectionFile, ...]:
  """Read one bounded collection into immutable, no-follow records."""
  discovered: list[_CollectionFile] = []
  seen_directories: set[tuple[int, int]] = set()
  seen_files: set[tuple[int, int]] = set()
  total_bytes = 0
  root_descriptor = _open_collection_root(root)
  root_identity = os.fstat(root_descriptor)

  def walk(descriptor: int, relative: PurePosixPath) -> None:
    nonlocal total_bytes
    metadata = os.fstat(descriptor)
    identity = (metadata.st_dev, metadata.st_ino)
    if identity in seen_directories:
      raise ValueError("case directory contains a duplicate inode alias")
    seen_directories.add(identity)
    try:
      entries = sorted(os.scandir(descriptor), key=lambda item: item.name)
    except OSError as exc:
      raise ValueError(f"cannot inspect case directory: {exc}") from exc
    for entry in entries:
      try:
        entry_metadata = entry.stat(follow_symlinks=False)
      except OSError as exc:
        raise ValueError(f"cannot inspect case entry: {exc}") from exc
      if entry.is_symlink():
        raise ValueError(f"case collection contains a symlink: {entry.path}")
      if entry.is_dir(follow_symlinks=False):
        child = os.open(
            entry.name, _collection_flags(directory=True), dir_fd=descriptor)
        try:
          opened = os.fstat(child)
          if (opened.st_dev, opened.st_ino) != (
              entry_metadata.st_dev, entry_metadata.st_ino):
            raise ValueError("collection directory identity changed")
          walk(child, relative / entry.name)
        finally:
          os.close(child)
      elif entry.is_file(follow_symlinks=False):
        file_identity = (entry_metadata.st_dev, entry_metadata.st_ino)
        if file_identity in seen_files or entry_metadata.st_nlink != 1:
          raise ValueError("case collection contains a hardlink or inode alias")
        seen_files.add(file_identity)
        if len(seen_files) > _MAX_COLLECTION_FILES:
          raise ValueError("collection exceeds file count limit")
        content = _read_collection_file(
            descriptor, entry.name, entry_metadata)
        total_bytes += len(content)
        if total_bytes > _MAX_COLLECTION_BYTES:
          raise ValueError("collection exceeds total size limit")
        discovered.append(_CollectionFile(
            relative_path=relative / entry.name, content=content))

  try:
    walk(root_descriptor, PurePosixPath())
    verification = _open_collection_root(root)
    try:
      verified = os.fstat(verification)
      if (verified.st_dev, verified.st_ino) != (
          root_identity.st_dev, root_identity.st_ino):
        raise ValueError("collection root identity changed during discovery")
    finally:
      os.close(verification)
    return tuple(discovered)
  finally:
    os.close(root_descriptor)


def load_cases(directory: Path | str) -> tuple[CaseDefinition, ...]:
  supplied = Path(directory)
  if supplied.is_symlink():
    raise ValueError("case directory must not be a symlink")
  root = Path(os.path.abspath(os.fspath(supplied)))
  records = _discover_named_paths(root)
  collection = MappingProxyType({
      record.relative_path: record for record in records})
  definitions = tuple(
      record for record in records if record.relative_path.name == "case.json")
  cases = tuple(_load_case(record, collection) for record in definitions)
  if not cases:
    raise ValueError("case directory does not contain case definitions")
  if len({case.case_id for case in cases}) != len(cases):
    raise ValueError("case identifiers must be unique")
  return cases


class _ScorecardStore:
  def __init__(self, directory: Path | str | None):
    if directory is None:
      self._scorecards = None
      return
    supplied = Path(directory)
    if supplied.is_symlink():
      raise ValueError("scorecard directory must not be a symlink")
    root = Path(os.path.abspath(os.fspath(supplied)))
    records = _discover_named_paths(root)
    scorecards = {}
    for record in records:
      if record.relative_path.name != "expected.json":
        continue
      case_id = record.relative_path.parent.name
      if case_id in scorecards:
        raise ValueError(f"scorecard lookup is not unique: {case_id}")
      scorecards[case_id] = record.content
    self._scorecards = MappingProxyType(scorecards)

  def load(self, case_id: str) -> dict:
    if self._scorecards is None:
      raise ValueError("scorecard directory was not supplied")
    content = self._scorecards.get(case_id)
    if content is None:
      raise ValueError(f"scorecard lookup is not unique: {case_id}")
    return _read_json_bytes(content, "scorecard")


_ROBUSTNESS_SCORECARD_FIELDS = {
    "schema_version", "final_status", "minimum_repair_rounds",
    "maximum_repair_rounds",
}
_ADVERSARIAL_SCORECARD_FIELDS = {"attack_family", "reason_expectations"}


def _scorecard_object(value: object) -> dict:
  if not isinstance(value, dict):
    raise ValueError("scorecard must be a JSON object")
  unknown = (set(value) - _ROBUSTNESS_SCORECARD_FIELDS
             - _ADVERSARIAL_SCORECARD_FIELDS)
  missing = _ROBUSTNESS_SCORECARD_FIELDS - set(value)
  if unknown:
    raise ValueError(f"scorecard has unknown fields: {sorted(unknown)}")
  if missing:
    raise ValueError(f"scorecard is missing fields: {sorted(missing)}")
  has_family = "attack_family" in value
  has_expectations = "reason_expectations" in value
  if has_family != has_expectations:
    raise ValueError(
        "scorecard adversarial fields must be supplied together")
  return value


def _score_robustness(
    scorecards: _ScorecardStore, case_id: str, status: str,
    repair_count: int,
) -> RobustnessResult:
  try:
    data = _scorecard_object(scorecards.load(case_id))
    if data["schema_version"] != SCHEMA_VERSION:
      raise ValueError("unsupported scorecard schema_version")
    if "attack_family" in data:
      _text(data["attack_family"], "attack_family")
      _attack_expectations(data["reason_expectations"])
    expected = data["final_status"]
    if expected not in {"valid", "valid_with_warnings", "invalid"}:
      raise ValueError("scorecard final_status is invalid")
    minimum = data["minimum_repair_rounds"]
    maximum = data["maximum_repair_rounds"]
    if (isinstance(minimum, bool) or not isinstance(minimum, int)
        or isinstance(maximum, bool) or not isinstance(maximum, int)
        or minimum < 0 or maximum < minimum or maximum > 3):
      raise ValueError("scorecard repair bounds are invalid")
    return RobustnessResult(
        expected_final_status=expected,
        observed_final_status=status,
        minimum_repair_rounds=minimum,
        maximum_repair_rounds=maximum,
        expectation_met=(
            status == expected and minimum <= repair_count <= maximum),
        error=None,
    )
  except Exception as exc:
    return RobustnessResult(
        expected_final_status=None,
        observed_final_status=status,
        minimum_repair_rounds=None,
        maximum_repair_rounds=None,
        expectation_met=None,
        error=str(exc).strip() or exc.__class__.__name__,
    )


@dataclass(frozen=True, slots=True)
class ReasonMetric:
  true_positive: int
  false_positive: int
  true_negative: int
  false_negative: int

  def __post_init__(self) -> None:
    for value, label in (
        (self.true_positive, "true_positive"),
        (self.false_positive, "false_positive"),
        (self.true_negative, "true_negative"),
        (self.false_negative, "false_negative"),
    ):
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")

  @property
  def precision(self) -> float | None:
    denominator = self.true_positive + self.false_positive
    return None if denominator == 0 else self.true_positive / denominator

  @property
  def recall(self) -> float | None:
    denominator = self.true_positive + self.false_negative
    return None if denominator == 0 else self.true_positive / denominator

  @property
  def specificity(self) -> float | None:
    denominator = self.true_negative + self.false_positive
    return None if denominator == 0 else self.true_negative / denominator

  def to_dict(self) -> dict:
    return {
        "true_positive": self.true_positive,
        "false_positive": self.false_positive,
        "true_negative": self.true_negative,
        "false_negative": self.false_negative,
        "precision": self.precision,
        "recall": self.recall,
        "specificity": self.specificity,
    }

  @classmethod
  def from_dict(cls, value: dict) -> "ReasonMetric":
    data = _closed_object(value, {
        "true_positive", "false_positive", "true_negative", "false_negative",
        "precision", "recall", "specificity",
    }, "reason metric")
    metric = cls(
        true_positive=data["true_positive"],
        false_positive=data["false_positive"],
        true_negative=data["true_negative"],
        false_negative=data["false_negative"],
    )
    if (data["precision"] != metric.precision or data["recall"] != metric.recall
        or data["specificity"] != metric.specificity):
      raise ValueError("reason metric rates do not match counts")
    return metric


@dataclass(frozen=True, slots=True)
class AdversarialCaseScore:
  attack_family: str
  domain: str
  confusion: Mapping[str, int]
  reason_metrics: Mapping[str, ReasonMetric]
  assessable: bool = True
  unassessable_reason: str | None = None

  def __post_init__(self) -> None:
    _text(self.attack_family, "attack_family")
    _text(self.domain, "domain")
    if type(self.assessable) is not bool:
      raise ValueError("assessable must be a boolean")
    if self.assessable != (self.unassessable_reason is None) or (
        self.unassessable_reason is not None
        and self.unassessable_reason not in UNASSESSABLE_REASONS):
      raise ValueError(
          "unassessable_reason must name why a score is not assessable")
    expected_confusion = {
        "true_positive", "false_positive", "true_negative", "false_negative"}
    if set(self.confusion) != expected_confusion:
      raise ValueError("adversarial confusion fields are invalid")
    frozen_confusion = {}
    for name in sorted(expected_confusion):
      value = self.confusion[name]
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("adversarial confusion counts must be nonnegative")
      frozen_confusion[name] = value
    metrics = {}
    for code, metric in self.reason_metrics.items():
      reason = ReasonCode(code).value
      if reason in metrics:
        raise ValueError("reason metrics must be unique")
      metrics[reason] = (
          metric if isinstance(metric, ReasonMetric)
          else ReasonMetric.from_dict(metric))
    if not self.assessable and (
        metrics or any(frozen_confusion.values())):
      raise ValueError("an unassessable score cannot carry counts")
    if self.assessable and not metrics:
      raise ValueError("reason metrics must not be empty")
    for field in (
        "true_positive", "false_positive", "true_negative", "false_negative",
    ):
      if sum(getattr(metric, field) for metric in metrics.values()) != (
          frozen_confusion[field]):
        raise ValueError(
            "adversarial confusion does not reconcile with reason metrics")
    object.__setattr__(self, "confusion", MappingProxyType(frozen_confusion))
    object.__setattr__(
        self, "reason_metrics", MappingProxyType(dict(sorted(metrics.items()))))

  def to_dict(self) -> dict:
    return {
        "schema_version": ADVERSARIAL_SCHEMA_VERSION,
        "attack_family": self.attack_family,
        "domain": self.domain,
        "assessable": self.assessable,
        "unassessable_reason": self.unassessable_reason,
        "confusion": dict(self.confusion),
        "reason_metrics": {
            code: metric.to_dict()
            for code, metric in self.reason_metrics.items()
        },
    }

  @classmethod
  def from_dict(cls, value: dict) -> "AdversarialCaseScore":
    version = value.get("schema_version") if isinstance(value, dict) else None
    fields = {
        "schema_version", "attack_family", "domain", "confusion",
        "reason_metrics",
    }
    if version == ADVERSARIAL_SCHEMA_VERSION:
      fields.update({"assessable", "unassessable_reason"})
    elif version != _PRE_ASSESSABLE_ADVERSARIAL_VERSION:
      raise ValueError("unsupported adversarial case score schema_version")
    data = _closed_object(value, fields, "adversarial case score")
    if not isinstance(data["confusion"], dict):
      raise ValueError("adversarial confusion must be a dictionary")
    if not isinstance(data["reason_metrics"], dict):
      raise ValueError("reason metrics must be a dictionary")
    return cls(
        attack_family=data["attack_family"],
        domain=data["domain"],
        confusion=data["confusion"],
        reason_metrics=data["reason_metrics"],
        assessable=data.get("assessable", True),
        unassessable_reason=data.get("unassessable_reason"),
    )


def _observed_findings(value: object) -> tuple[Finding, ...]:
  if isinstance(value, IntegrityEvalResult):
    return value.model_first_pass.integrity.findings
  if isinstance(value, OperationalIntegrityEvalResult):
    failure = value.operational_failure
    trusted = ()
    if failure.phase == "repair_load":
      snapshot = (
          value.repair_rounds[-1].integrity if value.repair_rounds
          else value.model_first_pass.integrity)
      trusted = snapshot.findings
    return (*trusted, Finding(
        reason_code=failure.reason_code,
        severity=Severity.CRITICAL,
        artifact=failure.artifact,
        message=failure.message,
        context={},
    ),)
  if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
    raise ValueError("observed attack findings must be an iterable")
  findings = []
  for item in value:
    if isinstance(item, Finding):
      findings.append(item)
    elif isinstance(item, dict):
      findings.append(Finding.from_dict(item))
    else:
      raise ValueError("observed attack finding is invalid")
  return tuple(findings)


def _attack_expectations(value: object) -> tuple[dict, ...]:
  if not isinstance(value, list) or not value:
    raise ValueError("reason_expectations must be a nonempty list")
  expectations = []
  units = set()
  for item in value:
    data = _closed_object(
        item, {"reason_code", "present", "unit"}, "reason expectation")
    reason = ReasonCode(data["reason_code"])
    if not isinstance(data["present"], bool):
      raise ValueError("reason expectation present must be a boolean")
    unit = _closed_object(
        data["unit"], {"artifact", "context_key", "context_value"},
        "reason expectation unit")
    artifact = _text(unit["artifact"], "reason expectation artifact")
    key = unit["context_key"]
    context_value = unit["context_value"]
    if key is None:
      if context_value is not None:
        raise ValueError("context_value must be null without context_key")
    elif (key not in {"result_index", "synthesis_sentence_index"}
          or type(context_value) is not int or context_value < 0):
      raise ValueError("reason expectation context unit is invalid")
    identity = (reason.value, artifact, key, context_value)
    if identity in units:
      raise ValueError(
          "reason expectations contain a duplicate or contradictory unit")
    units.add(identity)
    expectations.append({
        "reason_code": reason, "present": data["present"],
        "artifact": artifact, "context_key": key,
        "context_value": context_value,
    })
  return tuple(expectations)


_PLANTED_KEYS = frozenset({"claims", "synthesis", "sources", "corpus", "references"})


def _planted_fixture(case: CaseDefinition) -> dict | None:
  """The public input a content attack asks the model to preserve, if any."""
  if case.workspace_tamper is not None:
    return None
  for fixture in case.fixture_files:
    if fixture.relative_path.name != "input.json":
      continue
    try:
      value = json.loads(fixture.content.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
      return None
    if isinstance(value, dict) and set(value) == _PLANTED_KEYS:
      return value
  return None


def _snapshot_json(snapshot, relative_path: str) -> object:
  try:
    return json.loads(snapshot.read_text(relative_path))
  except (WorkspaceError, json.JSONDecodeError):
    return None


def _contains(container: object, expected: object) -> bool:
  if isinstance(expected, dict):
    return isinstance(container, dict) and all(
        key in container and _contains(container[key], value)
        for key, value in expected.items())
  return container == expected


def fixture_preserved(fixture: dict, snapshot) -> bool:
  """True when the first pass kept every planted claim, source, and record."""
  normalize = check_claims.normalize_text
  claims = _snapshot_json(snapshot, "claims.json")
  corpus = _snapshot_json(snapshot, "corpus.json")
  references = _snapshot_json(snapshot, "refs.json")
  try:
    synthesis = normalize(snapshot.read_text("synthesis.md"))
  except WorkspaceError:
    return False
  if not all(isinstance(value, list) for value in (claims, corpus, references)):
    return False

  def claim_key(claim: dict) -> tuple:
    return (normalize(claim.get("claim") or ""), claim.get("paper_id"),
            claim.get("citation"),
            normalize(claim.get("supporting_quote") or ""),
            claim.get("role", "evidence"))

  submitted = {claim_key(claim) for claim in claims if isinstance(claim, dict)}
  if any(claim_key(claim) not in submitted for claim in fixture["claims"]):
    return False
  if any(normalize(sentence) not in synthesis
         for sentence in check_claims._split_sentences(fixture["synthesis"])
         if sentence.strip()):
    return False
  for paper_id, text in fixture["sources"].items():
    sources = []
    for name in ("fulltext.md", "abstract.md"):
      try:
        sources.append(normalize(snapshot.read_text(f"papers/{paper_id}/{name}")))
      except WorkspaceError:
        continue
    if not any(normalize(text) in source for source in sources):
      return False
  for record in fixture["corpus"]:
    planted = {key: record[key] for key in (
        "ids", "title", "authors", "year", "role") if key in record}
    if "screening" in record:
      planted["screening"] = {"status": record["screening"].get("status")}
    if not any(_contains(item, planted) for item in corpus):
      return False
  if len(references) != len(fixture["references"]):
    return False
  return all(_contains(submitted_reference, planted_reference)
             for submitted_reference, planted_reference
             in zip(references, fixture["references"]))


def _unrelated_load_failure(observed: object, expectations) -> bool:
  """True when the first pass never loaded, for a reason the case did not plant."""
  if not isinstance(observed, OperationalIntegrityEvalResult):
    return False
  failure = observed.operational_failure
  if failure.phase != "initial_load":
    return False
  return not any(
      expectation["present"]
      and expectation["reason_code"] is failure.reason_code
      and expectation["artifact"] == failure.artifact
      for expectation in expectations)


def load_adversarial_scores(
    scorecard_directory: Path | str,
    observed_by_case: Mapping[str, object],
    *,
    domains: Mapping[str, str],
    fixture_preserved: Mapping[str, bool | None] | None = None,
) -> Mapping[str, AdversarialCaseScore]:
  """Read scorer-only expectations after runs and return count-only scores."""
  if not isinstance(observed_by_case, Mapping):
    raise ValueError("observed_by_case must be a mapping")
  if not isinstance(domains, Mapping):
    raise ValueError("domains must be a mapping")
  store = _ScorecardStore(scorecard_directory)
  scores = {}
  for case_id, observed_value in observed_by_case.items():
    if not isinstance(case_id, str) or not _CASE_ID_RE.fullmatch(case_id):
      raise ValueError("adversarial score case_id is invalid")
    data = _scorecard_object(store.load(case_id))
    if "attack_family" not in data:
      continue
    family = _text(data["attack_family"], "attack_family")
    if case_id not in domains:
      raise ValueError(f"domain is missing for scored case {case_id}")
    expectations = _attack_expectations(data["reason_expectations"])
    reason = (
        "first_pass_unloadable"
        if _unrelated_load_failure(observed_value, expectations)
        else "attack_not_reproduced"
        if (fixture_preserved or {}).get(case_id) is False else None)
    if reason is not None:
      scores[case_id] = AdversarialCaseScore(
          attack_family=family, domain=domains[case_id], assessable=False,
          unassessable_reason=reason,
          confusion=dict.fromkeys((
              "true_positive", "false_positive", "true_negative",
              "false_negative"), 0),
          reason_metrics={})
      continue
    findings = _observed_findings(observed_value)
    confusion = dict.fromkeys((
        "true_positive", "false_positive", "true_negative", "false_negative"
    ), 0)
    reason_counts: dict[str, dict[str, int]] = {}
    unmatched = list(range(len(findings)))
    for expectation in expectations:
      code = expectation["reason_code"].value
      matching = next((
          index for index in unmatched
          if findings[index].reason_code is expectation["reason_code"]
          and findings[index].artifact == expectation["artifact"]
          and (expectation["context_key"] is None
               or findings[index].context.get(expectation["context_key"])
               == expectation["context_value"])
      ), None)
      matched = matching is not None
      if matching is not None:
        unmatched.remove(matching)
      if expectation["present"]:
        outcome = "true_positive" if matched else "false_negative"
      else:
        outcome = "false_positive" if matched else "true_negative"
      confusion[outcome] += 1
      counts = reason_counts.setdefault(code, {
          "true_positive": 0, "false_positive": 0,
          "true_negative": 0, "false_negative": 0})
      counts[outcome] += 1
    for index in unmatched:
      code = findings[index].reason_code.value
      confusion["false_positive"] += 1
      counts = reason_counts.setdefault(code, {
          "true_positive": 0, "false_positive": 0,
          "true_negative": 0, "false_negative": 0})
      counts["false_positive"] += 1
    scores[case_id] = AdversarialCaseScore(
        attack_family=family,
        domain=domains[case_id],
        confusion=confusion,
        reason_metrics={
            code: ReasonMetric(**counts)
            for code, counts in reason_counts.items()
        },
    )
  return MappingProxyType(scores)


class LiteratureIntegrityRunner:
  def __init__(
      self,
      executor: ModelExecutor,
      quality_judge: QualityJudge,
      *,
      workspace_parent: Path | str | None = None,
      scorecard_directory: Path | str | None = None,
  ):
    self._executor = executor
    self._quality_judge = quality_judge
    self._workspace_parent = (
        Path(workspace_parent).resolve() if workspace_parent is not None
        else Path(tempfile.gettempdir()).resolve())
    self._scorecards = _ScorecardStore(scorecard_directory)
    self.snapshots: dict[str, tuple] = {}
    self.fixture_preserved: dict[str, bool | None] = {}

  def _quality(self, case: CaseDefinition, synthesis: str) -> QualityResult:
    try:
      result = self._quality_judge.score(case, synthesis)
      if not isinstance(result, QualityResult):
        raise ValueError("quality judge returned an invalid result")
      return result
    except Exception as exc:
      return QualityResult.failed(exc)

  @staticmethod
  def _integrity(snapshot) -> PassReport:
    findings = validate_snapshot(snapshot)
    return score_integrity(snapshot, findings)

  def _operational_result(
      self, case: CaseDefinition, *, phase: str, attempt: int,
      error: WorkspaceError, usage: ModelUsage,
      first: SnapshotEvaluation | None = None,
      rounds: tuple[RepairRound, ...] = (),
  ) -> OperationalIntegrityEvalResult:
    robustness = _score_robustness(
        self._scorecards, case.case_id, "invalid", attempt)
    usages = (() if phase == "initial_load" else tuple(
        item.model_usage for item in rounds) + (usage,))
    return OperationalIntegrityEvalResult(
        model_first_pass=first,
        repair_rounds=rounds,
        operational_failure=OperationalFailure(
            phase=phase, attempt=attempt, reason_code=error.reason_code,
            artifact=error.artifact,
            message=str(error).strip() or error.__class__.__name__,
            model_usage=usage,
        ),
        repair_cost=RepairCost.from_usages(usages),
        robustness=robustness,
    )

  def run_case(self, case: CaseDefinition) -> IntegrityResult:
    """Evaluate one case and retain every loaded workspace snapshot."""
    if not isinstance(case, CaseDefinition):
      raise ValueError("case must be a CaseDefinition")
    retained = []
    self.fixture_preserved[case.case_id] = None
    try:
      return self._run_case(case, retained)
    finally:
      self.snapshots[case.case_id] = tuple(retained)

  def _run_case(self, case: CaseDefinition, retained: list) -> IntegrityResult:
    self._workspace_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="literature-run-", dir=self._workspace_parent,
    ) as temporary:
      workspace = Path(temporary).resolve()
      first_usage = self._executor.first_pass(case, workspace)
      if not isinstance(first_usage, ModelUsage):
        raise ValueError("executor returned invalid first-pass usage")
      if case.workspace_tamper is not None:
        apply_workspace_tamper(case.workspace_tamper, workspace)
      try:
        first_snapshot = load_workspace(workspace)
      except WorkspaceError as exc:
        return self._operational_result(
            case, phase="initial_load", attempt=0, error=exc,
            usage=first_usage)
      retained.append(first_snapshot)
      planted = _planted_fixture(case)
      if planted is not None:
        self.fixture_preserved[case.case_id] = fixture_preserved(
            planted, first_snapshot)

      # The quality judge sees retained first-pass text before any finding or
      # repair feedback exists.
      first_quality = self._quality(
          case, first_snapshot.read_text("synthesis.md"))
      first_integrity = self._integrity(first_snapshot)
      first = SnapshotEvaluation(
          workspace_manifest_sha256=first_snapshot.manifest_sha256,
          quality=first_quality,
          integrity=first_integrity,
          model_usage=first_usage,
      )

      controller = RepairController()
      decision = controller.record(first_integrity, first_snapshot)
      rounds = []
      current_snapshot = first_snapshot
      current_integrity = first_integrity
      while decision.action == "repair":
        previous_integrity = current_integrity
        usage = self._executor.repair(decision.repair_feedback, workspace)
        if not isinstance(usage, ModelUsage):
          raise ValueError("executor returned invalid repair usage")
        try:
          current_snapshot = load_workspace(workspace)
        except WorkspaceError as exc:
          return self._operational_result(
              case, phase="repair_load", attempt=len(rounds) + 1,
              error=exc, usage=usage, first=first,
              rounds=tuple(rounds))
        retained.append(current_snapshot)
        current_integrity = self._integrity(current_snapshot)
        decision = controller.record(current_integrity, current_snapshot)
        rounds.append(RepairRound(
            attempt=len(rounds) + 1,
            previous_integrity=previous_integrity,
            integrity=current_integrity,
            workspace_manifest_sha256=current_snapshot.manifest_sha256,
            reason_codes=tuple(dict.fromkeys(
                finding.reason_code for finding in current_integrity.findings)),
            action=decision.action,
            model_usage=usage,
        ))

      immutable_rounds = tuple(rounds)
      if immutable_rounds:
        final = SnapshotEvaluation(
            workspace_manifest_sha256=current_snapshot.manifest_sha256,
            quality=self._quality(
                case, current_snapshot.read_text("synthesis.md")),
            integrity=current_integrity,
            model_usage=immutable_rounds[-1].model_usage,
        )
      else:
        final = first

      # Preloaded scoring bytes are parsed only after model work, validation,
      # repair feedback, and quality judging are all complete.
      robustness = _score_robustness(
          self._scorecards, case.case_id, final.integrity.status.value,
          len(immutable_rounds))
      return IntegrityEvalResult(
          model_first_pass=first,
          repair_rounds=immutable_rounds,
          system_final=final,
          repair_cost=RepairCost.from_rounds(immutable_rounds),
          robustness=robustness,
      )

  def run_cases(
      self, cases: tuple[CaseDefinition, ...], run_directory: Path | str,
  ) -> tuple[IntegrityResult, ...]:
    destination = Path(run_directory)
    destination.mkdir(parents=True, exist_ok=False)
    results = []
    for case in cases:
      result = self.run_case(case)
      results.append(result)
      (destination / f"{case.case_id}.json").write_text(
          json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    (destination / "run.json").write_text(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "capability": CAPABILITY,
        "cases": [case.case_id for case in cases],
    }, indent=2) + "\n", encoding="utf-8")
    return tuple(results)


class ProductionQualityJudge:
  def __init__(self, model: str):
    self._model = _text(model, "model")

  def score(
      self, case: CaseDefinition, synthesis: str,
  ) -> QualityResult:
    test_case = TestCase(
        name=case.case_id.replace("-", " ").title(),
        agent=CAPABILITY,
        implementation_skill="literature-review",
        task_prompt=case.prompt,
        rubric_profile={
            "primary": {"rubric": "research-quality", "weight": 70},
            "secondary": {"rubric": "analytical-quality", "weight": 20},
            "tertiary": {"rubric": "output-structure", "weight": 10},
        },
    )
    report = evaluate_output(
        test_case,
        AgentResult(success=True, output=synthesis, duration=0.0),
        self._model,
    )
    try:
      output = report.judge_output
      if not isinstance(output, str) or not output.strip():
        raise ValueError("quality judge returned empty output")
      if output.startswith("Judge error:"):
        detail = output.removeprefix("Judge error:").strip()
        raise ValueError(detail or "quality judge failed")

      def explicit_score(key: str) -> float:
        matches = re.findall(
            rf"(?im)^\s*[*`]*{re.escape(key)}[*`]*\s*[:=]\s*"
            rf"(\d+(?:\.\d+)?)\s*(?:/100)?\s*$",
            output,
        )
        if len(matches) != 1:
          raise ValueError(
              f"quality judge output must contain one explicit {key}")
        return _finite_score(float(matches[0]), key)

      scores = {
          name: explicit_score(name.replace("-", "_").upper())
          for name in QUALITY_DIMENSIONS
      }
      overall = explicit_score("OVERALL_SCORE")
      return QualityResult(
          quality_score=overall, scores=scores, error=None)
    except Exception as exc:
      return QualityResult.failed(exc)


_CODEX_MODEL_RE = re.compile(r"^model:\s*(\S+)\s*$", re.MULTILINE)


def _resolved_model(provider: str, stdout: str, stderr: str) -> str | None:
  """The concrete model a CLI reports it ran, or None if it does not say."""
  if provider == "claude":
    try:
      events = json.loads(stdout)
    except json.JSONDecodeError:
      return None
    for event in events if isinstance(events, list) else [events]:
      if (isinstance(event, dict) and event.get("type") == "system"
          and isinstance(event.get("model"), str) and event["model"]):
        return event["model"]
    return None
  match = _CODEX_MODEL_RE.search(f"{stderr}\n{stdout}")
  return match.group(1) if match else None


class ProductionModelExecutor:
  def __init__(
      self, model: str, repository_root: Path | str = REPOSITORY_ROOT,
      *, timeout: int = 900,
  ):
    self._model = _text(model, "model")
    self._repository_root = Path(repository_root).resolve()
    self._timeout = timeout
    self.resolved_models: set[str] = set()

  @staticmethod
  def _inside(path: Path, root: Path) -> bool:
    try:
      path.relative_to(root)
      return True
    except ValueError:
      return False

  def _child_environment(self, workspace: Path, provider: str) -> dict[str, str]:
    allowed = _COMMON_CHILD_ENV | _PROVIDER_CHILD_ENV[provider]
    protected = (self._repository_root, workspace.parent.resolve())
    child = {}
    for name in sorted(allowed):
      value = os.environ.get(name)
      if value is None:
        continue
      if any(str(root) in value for root in protected):
        continue
      if name in _PATH_CHILD_ENV:
        candidate = Path(value).expanduser()
        try:
          candidate = candidate.resolve(strict=False)
        except OSError:
          continue
        if any(self._inside(candidate, root) for root in protected):
          continue
      child[name] = value
    child.update({
        "LANG": child.get("LANG", "C.UTF-8"),
        "PATH": _SAFE_SYSTEM_PATH,
        "PWD": str(workspace.resolve()),
        "TMPDIR": str(_SAFE_TEMP_ROOT),
    })
    return child

  def _run(
      self, prompt: str, workspace: Path, *, prompt_version: str,
      prompt_sha256: str, allow_research: bool,
      readable_directory: Path | None = None,
  ) -> ModelUsage:
    parts = self._model.split(":")
    if self._inside(workspace.resolve(), self._repository_root):
      raise ValueError("model workspace must be isolated outside the repository")
    provider = parts[0].lower()
    model_name = parts[1] if len(parts) > 1 else None
    extra = parts[2] if len(parts) > 2 else None
    if not extra and model_name and " " in model_name:
      model_name, extra = model_name.rsplit(" ", 1)
    if provider not in CLI_CONFIG:
      raise RuntimeError(f"unsupported model provider: {provider}")
    cli = find_cli(provider)
    if cli is None:
      raise RuntimeError(f"{provider} CLI not found")
    config = CLI_CONFIG[provider]
    command = [str(cli), *config["base"]]
    if model_name:
      command += ["--model", model_name]
    if extra and provider == "codex":
      command += ["-c", f'reasoning="{extra}"']
    command += (
        ["--tools", (_CLAUDE_CAPTURE_TOOLS if allow_research
                     else _CLAUDE_REPAIR_TOOLS)]
        if provider == "claude" else config["tools"])
    if provider == "claude":
      command += ["--permission-mode", "acceptEdits", "--output-format", "json"]
      if readable_directory is not None:
        command += ["--add-dir", str(readable_directory)]
    stdin = prompt if config.get("stdin") else None
    command += ["-"] if stdin is not None else ["-p", prompt]
    started = time.monotonic()
    try:
      completed = subprocess.run(
          command,
          cwd=workspace,
          env=self._child_environment(workspace, provider),
          input=stdin,
          capture_output=True,
          text=True,
          timeout=self._timeout,
          check=False,
      )
    except subprocess.TimeoutExpired as exc:
      raise ModelExecutionError(
          f"model executor timed out after {self._timeout} seconds") from exc
    except OSError as exc:
      raise ModelExecutionError(f"model executor could not start: {exc}") from exc
    duration = time.monotonic() - started
    if completed.returncode != 0:
      lines = [line.strip() for line in
               (completed.stderr or completed.stdout).strip().splitlines()]
      errors = [line for line in lines if "ERROR" in line]
      detail = errors[-1] if errors else lines[-1] if lines else "no output"
      raise ModelExecutionError(
          f"model executor exited {completed.returncode}: {detail}")
    resolved = _resolved_model(provider, completed.stdout, completed.stderr)
    if resolved is not None:
      self.resolved_models.add(resolved)
    return ModelUsage(
        duration_seconds=duration,
        input_tokens=None,
        output_tokens=None,
        estimated_cost_usd=None,
        executor_version=EXECUTOR_VERSION,
        prompt_version=prompt_version,
        prompt_sha256=prompt_sha256,
    )

  def first_pass(
      self, case: CaseDefinition, workspace: Path,
  ) -> ModelUsage:
    source_skill = self._repository_root / "skills/literature-review"
    with tempfile.TemporaryDirectory(
        dir=_SAFE_TEMP_ROOT,
    ) as temporary:
      staging = Path(temporary).resolve()
      for path in source_skill.rglob("*"):
        if path.is_symlink():
          raise ValueError("literature-review skill bundle contains a symlink")
      shutil.copytree(source_skill, staging / "skill")
      skill_path = staging / "skill/SKILL.md"
      fixture_paths = []
      for index, fixture in enumerate(case.fixture_files, 1):
        suffix = fixture.relative_path.suffix or ".bin"
        destination = staging / f"fixture-{index:03d}{suffix}"
        destination.write_bytes(fixture.content)
        fixture_paths.append(destination)
      fixtures = "\n".join(
          f"- {path}" for path in fixture_paths) or "- none"
      prompt = (
          f"{CAPTURE_INSTRUCTION}\n"
          f"Skill path: {skill_path}\n"
          f"Domain: {case.domain}\n"
          f"Public synthetic fixtures:\n{fixtures}\n\n"
          f"Task:\n{case.prompt}\n")
      return self._run(
          prompt, workspace,
          prompt_version=CAPTURE_PROMPT_VERSION,
          prompt_sha256=CAPTURE_PROMPT_SHA256,
          allow_research=True,
          readable_directory=staging,
      )

  def repair(self, feedback: dict, workspace: Path) -> ModelUsage:
    prompt = (
        f"{REPAIR_INSTRUCTION}\n"
        "Validator feedback:\n"
        f"{json.dumps(feedback, sort_keys=True, separators=(',', ':'))}\n")
    return self._run(
        prompt, workspace,
        prompt_version=REPAIR_PROMPT_VERSION,
        prompt_sha256=REPAIR_PROMPT_SHA256,
        allow_research=False,
    )


__all__ = [
    "AdversarialCaseScore", "CAPABILITY", "CAPTURE_PROMPT_SHA256",
    "CAPTURE_PROMPT_VERSION", "CaseDefinition", "IntegrityEvalResult",
    "IntegrityResult", "LiteratureIntegrityRunner", "OperationalFailure",
    "OperationalIntegrityEvalResult",
    "ModelExecutor", "ModelUsage", "ProductionModelExecutor",
    "ProductionQualityJudge", "PublicFixture", "QualityJudge",
    "QualityResult", "RepairCost",
    "ReasonMetric", "RepairRound", "RobustnessResult", "SnapshotEvaluation",
    "ModelExecutionError", "WORKSPACE_TAMPERS", "apply_workspace_tamper",
    "fixture_preserved",
    "decode_integrity_result", "load_adversarial_scores", "load_cases",
]
