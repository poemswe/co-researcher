"""Evaluation adapter for immutable literature-review integrity passes."""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Protocol

from .core import AgentResult, CLI_CONFIG, TestCase, evaluate_output, find_cli


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REVIEW_SCRIPTS = REPOSITORY_ROOT / "skills/literature-review/scripts"
if str(REVIEW_SCRIPTS) not in sys.path:
  sys.path.insert(0, str(REVIEW_SCRIPTS))

from review_integrity.models import PassReport  # noqa: E402
from review_integrity.repair import RepairController  # noqa: E402
from review_integrity.scoring import score_integrity  # noqa: E402
from review_integrity.validators import validate_snapshot  # noqa: E402
from review_integrity.workspace import load_workspace  # noqa: E402


SCHEMA_VERSION = "1.0.0"
CAPABILITY = "literature-review-integrity"
QUALITY_RUBRIC_ID = "literature-review-v1"
QUALITY_DIMENSIONS = (
    "research-quality", "analytical-quality", "output-structure")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_CASE_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")

EXECUTOR_VERSION = "1.0.0"
CAPTURE_PROMPT_VERSION = "literature-integrity-capture-v1"
CAPTURE_INSTRUCTION = """Evaluation capture mode.
Read and follow the repository literature-review skill at the supplied path.
Create the complete literature-review workspace in the current directory.
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
class CaseDefinition:
  case_id: str
  prompt: str
  domain: str
  fixture_paths: tuple[Path, ...]
  quality_rubric_id: str
  _scorecard_path: Path = field(repr=False, compare=False)

  def __post_init__(self) -> None:
    if not isinstance(self.case_id, str) or not _CASE_ID_RE.fullmatch(
        self.case_id):
      raise ValueError("case_id must be a lowercase hyphenated identifier")
    _text(self.prompt, "prompt")
    _text(self.domain, "domain")
    if self.quality_rubric_id != QUALITY_RUBRIC_ID:
      raise ValueError(
          f"quality_rubric_id must be {QUALITY_RUBRIC_ID!r}")
    if not isinstance(self.fixture_paths, tuple) or not all(
        isinstance(path, Path) and path.is_absolute()
        for path in self.fixture_paths):
      raise ValueError("fixture_paths must contain absolute paths")
    if not isinstance(self._scorecard_path, Path):
      raise ValueError("scorecard path must be a path")


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
        "action": self.action,
        "model_usage": self.model_usage.to_dict(),
    }

  @classmethod
  def from_dict(cls, value: dict) -> "RepairRound":
    data = _wire_object(value, {
        "attempt", "previous_integrity", "integrity",
        "workspace_manifest_sha256", "action", "model_usage",
    }, "repair round")
    return cls(
        attempt=data["attempt"],
        previous_integrity=PassReport.from_dict(data["previous_integrity"]),
        integrity=PassReport.from_dict(data["integrity"]),
        workspace_manifest_sha256=data["workspace_manifest_sha256"],
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
    usages = tuple(item.model_usage for item in rounds)

    def optional_sum(attribute: str) -> int | float | None:
      values = tuple(getattr(usage, attribute) for usage in usages)
      if any(value is None for value in values):
        return None
      return sum(values)

    return cls(
        rounds=len(rounds),
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
  expectation_met: bool | None
  error: str | None

  def __post_init__(self) -> None:
    statuses = {"valid", "valid_with_warnings", "invalid"}
    if self.observed_final_status not in statuses:
      raise ValueError("observed_final_status is invalid")
    if self.expected_final_status is None:
      if self.expectation_met is not None:
        raise ValueError("expectation_met must be null without an expectation")
      _text(self.error, "robustness error")
    else:
      if self.expected_final_status not in statuses:
        raise ValueError("expected_final_status is invalid")
      if not isinstance(self.expectation_met, bool):
        raise ValueError("expectation_met must be a boolean")
      if self.error is not None:
        raise ValueError("scored robustness cannot contain an error")

  def to_dict(self) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "expected_final_status": self.expected_final_status,
        "observed_final_status": self.observed_final_status,
        "expectation_met": self.expectation_met,
        "error": self.error,
    }

  @classmethod
  def from_dict(cls, value: dict) -> "RobustnessResult":
    data = _wire_object(value, {
        "expected_final_status", "observed_final_status", "expectation_met",
        "error",
    }, "robustness result")
    return cls(**{key: data[key] for key in data if key != "schema_version"})


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
    if len(self.repair_rounds) > 3 or any(
        item.attempt != index
        for index, item in enumerate(self.repair_rounds, 1)):
      raise ValueError("repair rounds must be bounded and contiguous")
    previous_integrity = self.model_first_pass.integrity
    for repair_round in self.repair_rounds:
      if repair_round.previous_integrity != previous_integrity:
        raise ValueError("repair round previous integrity breaks the chain")
      previous_integrity = repair_round.integrity
    if not isinstance(self.system_final, SnapshotEvaluation):
      raise ValueError("system_final must be a SnapshotEvaluation")
    expected_final = (
        self.repair_rounds[-1].integrity if self.repair_rounds
        else self.model_first_pass.integrity)
    if self.system_final.integrity != expected_final:
      raise ValueError("system_final integrity must be the final snapshot")
    if (not isinstance(self.repair_cost, RepairCost)
        or self.repair_cost != RepairCost.from_rounds(self.repair_rounds)):
      raise ValueError("repair_cost must match repair_rounds")
    if not isinstance(self.robustness, RobustnessResult):
      raise ValueError("robustness must be a RobustnessResult")
    if (self.robustness.observed_final_status
        != self.system_final.integrity.status.value):
      raise ValueError("robustness must describe system_final")

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


class ModelExecutor(Protocol):
  def first_pass(
      self, case: CaseDefinition, workspace: Path,
  ) -> ModelUsage: ...

  def repair(self, feedback: dict, workspace: Path) -> ModelUsage: ...


class QualityJudge(Protocol):
  def score(
      self, case: CaseDefinition, synthesis: str,
  ) -> QualityResult: ...


def _read_json(path: Path, label: str) -> object:
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except (OSError, UnicodeError, json.JSONDecodeError) as exc:
    raise ValueError(f"cannot read {label}: {exc}") from exc


def _load_case(path: Path) -> CaseDefinition:
  fields = {
      "schema_version", "capability", "case_id", "prompt", "domain",
      "fixture_paths", "quality_rubric_id",
  }
  data = _closed_object(_read_json(path, "case definition"), fields,
                        "case definition")
  if data["schema_version"] != SCHEMA_VERSION:
    raise ValueError("unsupported case schema_version")
  if data["capability"] != CAPABILITY:
    raise ValueError("case capability does not match directory capability")
  if not isinstance(data["fixture_paths"], list) or not all(
      isinstance(item, str) and item for item in data["fixture_paths"]):
    raise ValueError("fixture_paths must be a list of nonempty text paths")
  base = path.parent.resolve()
  fixtures = []
  for item in data["fixture_paths"]:
    candidate = (base / item).resolve()
    try:
      candidate.relative_to(base)
    except ValueError as exc:
      raise ValueError("fixture paths must remain inside the case directory") from exc
    if not candidate.is_file():
      raise ValueError(f"fixture path is not a file: {item}")
    fixtures.append(candidate)
  return CaseDefinition(
      case_id=data["case_id"],
      prompt=_text(data["prompt"], "prompt"),
      domain=_text(data["domain"], "domain"),
      fixture_paths=tuple(fixtures),
      quality_rubric_id=data["quality_rubric_id"],
      _scorecard_path=path.parent / "expected.json",
  )


def load_cases(directory: Path | str) -> tuple[CaseDefinition, ...]:
  root = Path(directory).resolve()
  if not root.is_dir():
    raise ValueError("case directory must exist")
  paths = sorted(root.glob("*/case.json"))
  if not paths and (root / "case.json").is_file():
    paths = [root / "case.json"]
  cases = tuple(_load_case(path) for path in paths)
  if not cases:
    raise ValueError("case directory does not contain case definitions")
  if len({case.case_id for case in cases}) != len(cases):
    raise ValueError("case identifiers must be unique")
  return cases


def _score_robustness(
    case: CaseDefinition, status: str, repair_count: int,
) -> RobustnessResult:
  try:
    fields = {
        "schema_version", "final_status", "minimum_repair_rounds",
        "maximum_repair_rounds",
    }
    data = _closed_object(
        _read_json(case._scorecard_path, "scorecard"), fields, "scorecard")
    if data["schema_version"] != SCHEMA_VERSION:
      raise ValueError("unsupported scorecard schema_version")
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
        expectation_met=(
            status == expected and minimum <= repair_count <= maximum),
        error=None,
    )
  except Exception as exc:
    return RobustnessResult(
        expected_final_status=None,
        observed_final_status=status,
        expectation_met=None,
        error=str(exc).strip() or exc.__class__.__name__,
    )


class LiteratureIntegrityRunner:
  def __init__(
      self,
      executor: ModelExecutor,
      quality_judge: QualityJudge,
      *,
      workspace_parent: Path | str | None = None,
  ):
    self._executor = executor
    self._quality_judge = quality_judge
    self._workspace_parent = (
        Path(workspace_parent).resolve() if workspace_parent is not None
        else Path(tempfile.gettempdir()).resolve())

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

  def run_case(self, case: CaseDefinition) -> IntegrityEvalResult:
    if not isinstance(case, CaseDefinition):
      raise ValueError("case must be a CaseDefinition")
    self._workspace_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"{case.case_id}-", dir=self._workspace_parent,
    ) as temporary:
      workspace = Path(temporary).resolve()
      first_usage = self._executor.first_pass(case, workspace)
      if not isinstance(first_usage, ModelUsage):
        raise ValueError("executor returned invalid first-pass usage")
      first_snapshot = load_workspace(workspace)

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
        current_snapshot = load_workspace(workspace)
        current_integrity = self._integrity(current_snapshot)
        decision = controller.record(current_integrity, current_snapshot)
        rounds.append(RepairRound(
            attempt=len(rounds) + 1,
            previous_integrity=previous_integrity,
            integrity=current_integrity,
            workspace_manifest_sha256=current_snapshot.manifest_sha256,
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

      # Scoring-only data is deliberately read after model work, validation,
      # repair feedback, and quality judging are all complete.
      robustness = _score_robustness(
          case, final.integrity.status.value, len(immutable_rounds))
      return IntegrityEvalResult(
          model_first_pass=first,
          repair_rounds=immutable_rounds,
          system_final=final,
          repair_cost=RepairCost.from_rounds(immutable_rounds),
          robustness=robustness,
      )

  def run_cases(
      self, cases: tuple[CaseDefinition, ...], run_directory: Path | str,
  ) -> tuple[IntegrityEvalResult, ...]:
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
    if report.judge_output.startswith("Judge error:"):
      raise RuntimeError(report.judge_output.removeprefix("Judge error:").strip())
    return QualityResult(
        quality_score=report.overall_score,
        scores={name: report.scores[name] for name in QUALITY_DIMENSIONS},
        error=None,
    )


class ProductionModelExecutor:
  def __init__(
      self, model: str, repository_root: Path | str = REPOSITORY_ROOT,
      *, timeout: int = 900,
  ):
    self._model = _text(model, "model")
    self._repository_root = Path(repository_root).resolve()
    self._timeout = timeout

  def _run(
      self, prompt: str, workspace: Path, *, prompt_version: str,
      prompt_sha256: str,
  ) -> ModelUsage:
    parts = self._model.split(":")
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
    command += config["tools"]
    stdin = prompt if config.get("stdin") else None
    command += ["-"] if stdin is not None else ["-p", prompt]
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=workspace,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=self._timeout,
        check=False,
    )
    duration = time.monotonic() - started
    if completed.returncode != 0:
      detail = (completed.stderr or completed.stdout).strip()
      raise RuntimeError(
          f"model executor exited {completed.returncode}: {detail}")
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
    skill_path = self._repository_root / "skills/literature-review/SKILL.md"
    fixtures = "\n".join(f"- {path}" for path in case.fixture_paths) or "- none"
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
    )


__all__ = [
    "CAPABILITY", "CAPTURE_PROMPT_SHA256", "CAPTURE_PROMPT_VERSION",
    "CaseDefinition", "IntegrityEvalResult", "LiteratureIntegrityRunner",
    "ModelExecutor", "ModelUsage", "ProductionModelExecutor",
    "ProductionQualityJudge", "QualityJudge", "QualityResult", "RepairCost",
    "RepairRound", "RobustnessResult", "SnapshotEvaluation", "load_cases",
]
