"""Immutable, fail-closed result schema for literature-review integrity runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional, Type, TypeVar, Union


try:  # Python 3.11+
  from enum import StrEnum as _StringEnum
except ImportError:  # Python 3.10 compatibility
  class _StringEnum(str, Enum):
    """Compatibility implementation of :class:`enum.StrEnum`."""


SCHEMA_VERSION = "1.0.0"
REASON_CODE_SCHEMA_VERSION = SCHEMA_VERSION

DIMENSION_ORDER = (
    "quote_authenticity",
    "citation_binding",
    "quantitative_grounding",
    "synthesis_coverage",
    "bibliography_verification",
    "prisma_artifact_completeness",
)
DIMENSION_NAMES = frozenset(DIMENSION_ORDER)
DIMENSION_WEIGHTS = MappingProxyType(dict(zip(
    DIMENSION_ORDER, (25.0, 20.0, 20.0, 15.0, 10.0, 10.0))))


class Severity(_StringEnum):
  INFO = "info"
  WARNING = "warning"
  CRITICAL = "critical"


class IntegrityStatus(_StringEnum):
  VALID = "valid"
  VALID_WITH_WARNINGS = "valid_with_warnings"
  INVALID = "invalid"


class ReasonCode(_StringEnum):
  """The versioned, closed reason-code vocabulary for integrity findings."""

  FABRICATED_QUOTE = "fabricated_quote"
  CITATION_IDENTITY_MISMATCH = "citation_identity_mismatch"
  CITATION_AMBIGUOUS = "citation_ambiguous"
  CITATION_RETRACTED = "citation_retracted"
  CITATION_RESOLUTION_UNAVAILABLE = "citation_resolution_unavailable"
  CLAIM_NEEDS_REVIEW = "claim_needs_review"
  COVERAGE_NUMBER_MISSING = "coverage_number_missing"
  COVERAGE_CLAIM_MISSING = "coverage_claim_missing"
  COVERAGE_ROLE_INVALID = "coverage_role_invalid"
  BIBLIOGRAPHY_INCOMPLETE = "bibliography_incomplete"
  PRISMA_EXCLUSION_REASON_MISSING = "prisma_exclusion_reason_missing"
  ABSTRACT_ONLY_SUPPORT = "abstract_only_support"
  ARTIFACT_MISSING = "artifact_missing"
  ARTIFACT_MALFORMED = "artifact_malformed"
  ARTIFACT_SYMLINK = "artifact_symlink"
  ARTIFACT_TRAVERSAL = "artifact_traversal"
  ARTIFACT_TYPE_INVALID = "artifact_type_invalid"
  ARTIFACT_SIZE_LIMIT = "artifact_size_limit"
  MANIFEST_MISMATCH = "manifest_mismatch"
  VALIDATOR_INCOMPLETE = "validator_incomplete"


_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}\Z")
_T = TypeVar("_T")


def _require_fields(value: object, expected: set[str], model: str) -> dict[str, Any]:
  if not isinstance(value, dict):
    raise ValueError(f"{model} must be a dictionary")
  unknown = set(value) - expected
  if unknown:
    raise ValueError(f"{model} contains unknown fields: {sorted(unknown)!r}")
  missing = expected - set(value)
  if missing:
    raise ValueError(f"{model} is missing fields: {sorted(missing)!r}")
  if value["schema_version"] != SCHEMA_VERSION:
    raise ValueError(
        f"unsupported schema_version: {value['schema_version']!r}")
  return value


def _enum(value: object, enum_type: Type[_T], field: str) -> _T:
  if isinstance(value, enum_type):
    return value
  if not isinstance(value, str):
    raise ValueError(f"{field} must be a string")
  try:
    return enum_type(value)
  except ValueError as exc:
    raise ValueError(f"unknown {field}: {value!r}") from exc


def _nonempty_string(value: object, field: str) -> str:
  if not isinstance(value, str) or not value:
    raise ValueError(f"{field} must be a non-empty string")
  return value


def _score(value: object, field: str) -> float:
  if isinstance(value, bool) or not isinstance(value, (int, float)):
    raise ValueError(f"{field} must be a finite score from 0 to 100")
  result = float(value)
  if not math.isfinite(result) or not 0.0 <= result <= 100.0:
    raise ValueError(f"{field} must be a finite score from 0 to 100")
  return result


def _finite_number(value: object, field: str) -> float:
  if isinstance(value, bool) or not isinstance(value, (int, float)):
    raise ValueError(f"{field} must be a finite number")
  result = float(value)
  if not math.isfinite(result):
    raise ValueError(f"{field} must be a finite number")
  return result


def _unit_count(value: object, field: str) -> int:
  if isinstance(value, bool) or not isinstance(value, int) or value < 0:
    raise ValueError(f"{field} must be a nonnegative integer")
  return value


def _model_list(value: object, model_type: Type[_T], field: str) -> tuple[_T, ...]:
  if not isinstance(value, (list, tuple)):
    raise ValueError(f"{field} must be a list")
  result = []
  for item in value:
    if isinstance(item, model_type):
      result.append(item)
    elif isinstance(item, dict):
      result.append(model_type.from_dict(item))
    else:
      raise ValueError(f"{field} contains an invalid {model_type.__name__}")
  return tuple(result)


def _freeze_json(value: object, field_name: str,
                 active: Optional[set[int]] = None) -> object:
  """Validate and recursively freeze one JSON-safe value."""
  if active is None:
    active = set()
  if value is None or isinstance(value, (str, bool, int)):
    return value
  if isinstance(value, float):
    if not math.isfinite(value):
      raise ValueError(f"{field_name} must contain only finite numbers")
    return value
  if isinstance(value, Mapping):
    identity = id(value)
    if identity in active:
      raise ValueError(f"{field_name} must not contain recursive values")
    active.add(identity)
    result = {}
    try:
      for key, item in value.items():
        if not isinstance(key, str):
          raise ValueError(f"{field_name} mapping keys must be strings")
        result[key] = _freeze_json(item, field_name, active)
    finally:
      active.remove(identity)
    return MappingProxyType(result)
  if isinstance(value, (list, tuple)):
    identity = id(value)
    if identity in active:
      raise ValueError(f"{field_name} must not contain recursive values")
    active.add(identity)
    try:
      return tuple(_freeze_json(item, field_name, active) for item in value)
    finally:
      active.remove(identity)
  raise ValueError(f"{field_name} contains a value that is not JSON-safe")


def _thaw_json(value: object) -> object:
  if isinstance(value, Mapping):
    return {key: _thaw_json(item) for key, item in value.items()}
  if isinstance(value, tuple):
    return [_thaw_json(item) for item in value]
  return value


@dataclass(frozen=True)
class Finding:
  reason_code: ReasonCode
  severity: Severity
  artifact: str
  message: str
  context: Mapping[str, Any] = field(default_factory=dict)

  def __post_init__(self) -> None:
    object.__setattr__(self, "reason_code", _enum(
        self.reason_code, ReasonCode, "reason_code"))
    object.__setattr__(self, "severity", _enum(
        self.severity, Severity, "severity"))
    object.__setattr__(self, "artifact", _nonempty_string(
        self.artifact, "artifact"))
    object.__setattr__(self, "message", _nonempty_string(
        self.message, "message"))
    if not isinstance(self.context, Mapping):
      raise ValueError("context must be a mapping")
    object.__setattr__(self, "context", _freeze_json(
        self.context, "context"))

  def to_dict(self) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "reason_code": self.reason_code.value,
        "severity": self.severity.value,
        "artifact": self.artifact,
        "message": self.message,
        "context": _thaw_json(self.context),
    }

  @classmethod
  def from_dict(cls, value: dict) -> Finding:
    data = _require_fields(value, {
        "schema_version", "reason_code", "severity", "artifact", "message",
        "context",
    }, cls.__name__)
    return cls(
        reason_code=data["reason_code"],
        severity=data["severity"],
        artifact=data["artifact"],
        message=data["message"],
        context=data["context"],
    )


@dataclass(frozen=True)
class DimensionResult:
  name: str
  score: Optional[float]
  applicable: bool
  evaluated_units: int
  passed_units: int
  nominal_weight: float
  effective_weight: float
  findings: tuple[Finding, ...]

  def __post_init__(self) -> None:
    if self.name not in DIMENSION_NAMES:
      raise ValueError(f"unknown dimension: {self.name!r}")
    if not isinstance(self.applicable, bool):
      raise ValueError("applicable must be a boolean")
    evaluated = _unit_count(self.evaluated_units, "evaluated_units")
    passed = _unit_count(self.passed_units, "passed_units")
    if passed > evaluated:
      raise ValueError("passed_units must not exceed evaluated_units")
    nominal = _finite_number(self.nominal_weight, "nominal_weight")
    if nominal != DIMENSION_WEIGHTS[self.name]:
      raise ValueError("nominal_weight does not match the dimension")
    effective = _finite_number(self.effective_weight, "effective_weight")
    if not 0.0 <= effective <= 100.0:
      raise ValueError("effective_weight must be from 0 to 100")
    if not self.applicable:
      if (self.score is not None or evaluated != 0 or passed != 0
          or effective != 0.0):
        raise ValueError(
            "not_applicable dimensions require null score, zero units, and "
            "zero effective_weight")
    else:
      actual = _score(self.score, "score")
      expected = 0.0 if evaluated == 0 else 100.0 * passed / evaluated
      if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("score does not match evaluated and passed units")
      object.__setattr__(self, "score", expected)
    object.__setattr__(self, "nominal_weight", nominal)
    object.__setattr__(self, "effective_weight", effective)
    object.__setattr__(self, "findings", _model_list(
        self.findings, Finding, "findings"))

  @property
  def unrounded_score(self) -> Optional[float]:
    if not self.applicable:
      return None
    if self.evaluated_units == 0:
      return 0.0
    return 100.0 * self.passed_units / self.evaluated_units

  def to_dict(self) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "name": self.name,
        "score": (None if self.score is None else round(self.score, 1)),
        "applicable": self.applicable,
        "evaluated_units": self.evaluated_units,
        "passed_units": self.passed_units,
        "nominal_weight": round(self.nominal_weight, 1),
        "effective_weight": round(self.effective_weight, 1),
        "findings": [finding.to_dict() for finding in self.findings],
    }

  @classmethod
  def from_dict(cls, value: dict) -> DimensionResult:
    data = _require_fields(value, {
        "schema_version", "name", "score", "applicable",
        "evaluated_units", "passed_units", "nominal_weight",
        "effective_weight", "findings",
    }, cls.__name__)
    applicable = data["applicable"]
    evaluated = _unit_count(data["evaluated_units"], "evaluated_units")
    passed = _unit_count(data["passed_units"], "passed_units")
    expected_score = (None if applicable is False else
                      (0.0 if evaluated == 0 else 100.0 * passed / evaluated))
    wire_score = data["score"]
    if expected_score is None:
      if wire_score is not None:
        raise ValueError("not_applicable score must be null")
    else:
      parsed_score = _score(wire_score, "score")
      if parsed_score != round(expected_score, 1):
        raise ValueError("score does not match evaluated and passed units")
    return cls(
        name=data["name"], score=expected_score, applicable=applicable,
        evaluated_units=evaluated, passed_units=passed,
        nominal_weight=data["nominal_weight"],
        effective_weight=data["effective_weight"], findings=data["findings"])


DimensionsInput = Union[
    Mapping[str, DimensionResult], Iterable[DimensionResult],
]


def _dimensions(value: DimensionsInput) -> Mapping[str, DimensionResult]:
  if isinstance(value, Mapping):
    pairs = value.items()
  else:
    pairs = ((dimension.name, dimension) for dimension in value)
  result: dict[str, DimensionResult] = {}
  for name, dimension in pairs:
    if not isinstance(name, str):
      raise ValueError("dimension names must be strings")
    if not isinstance(dimension, DimensionResult):
      raise ValueError("dimensions must contain DimensionResult values")
    if name != dimension.name:
      raise ValueError("dimension mapping keys must match dimension names")
    if name in result:
      raise ValueError(f"duplicate dimension name: {name!r}")
    result[name] = dimension
  return MappingProxyType(result)


@dataclass(frozen=True)
class PassReport:
  integrity_score: float
  findings: tuple[Finding, ...]
  dimensions: DimensionsInput
  manifest_sha256: str

  def __post_init__(self) -> None:
    actual_score = _score(self.integrity_score, "integrity_score")
    object.__setattr__(self, "findings", _model_list(
        self.findings, Finding, "findings"))
    dimensions = _dimensions(self.dimensions)
    object.__setattr__(self, "dimensions", dimensions)
    applicable = [dimension for dimension in dimensions.values()
                  if dimension.applicable]
    if applicable:
      nominal_total = sum(dimension.nominal_weight for dimension in applicable)
      for dimension in dimensions.values():
        expected_weight = (dimension.nominal_weight * 100.0 / nominal_total
                           if dimension.applicable else 0.0)
        if not math.isclose(
            dimension.effective_weight, expected_weight,
            rel_tol=0.0, abs_tol=1e-12,
        ):
          raise ValueError(
              "effective_weight does not match applicable nominal weights")
      expected_score = sum(
          dimension.nominal_weight * (dimension.unrounded_score or 0.0)
          for dimension in applicable) / nominal_total
      if not math.isclose(
          actual_score, expected_score, rel_tol=0.0, abs_tol=1e-12,
      ):
        raise ValueError(
            "integrity_score does not match dimension counts and weights")
      actual_score = expected_score
    object.__setattr__(self, "integrity_score", actual_score)
    if not isinstance(self.manifest_sha256, str) or not _SHA256_RE.fullmatch(
        self.manifest_sha256):
      raise ValueError("manifest_sha256 must be a 64-character hexadecimal hash")

  @property
  def status(self) -> IntegrityStatus:
    if any(f.severity is Severity.CRITICAL for f in self.findings):
      return IntegrityStatus.INVALID
    if self.findings:
      return IntegrityStatus.VALID_WITH_WARNINGS
    return IntegrityStatus.VALID

  @property
  def unrounded_integrity_score(self) -> float:
    applicable = [dimension for dimension in self.dimensions.values()
                  if dimension.applicable]
    if not applicable:
      return self.integrity_score
    nominal_total = sum(dimension.nominal_weight for dimension in applicable)
    return sum(
        dimension.nominal_weight * (dimension.unrounded_score or 0.0)
        for dimension in applicable) / nominal_total

  def to_dict(self) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "integrity_score": round(self.integrity_score, 1),
        "findings": [finding.to_dict() for finding in self.findings],
        "dimensions": {
            name: dimension.to_dict()
            for name, dimension in self.dimensions.items()
        },
        "manifest_sha256": self.manifest_sha256,
        "status": self.status.value,
    }

  @classmethod
  def from_dict(cls, value: dict) -> PassReport:
    data = _require_fields(value, {
        "schema_version", "integrity_score", "findings", "dimensions",
        "manifest_sha256", "status",
    }, cls.__name__)
    if not isinstance(data["dimensions"], dict):
      raise ValueError("dimensions must be a dictionary")
    serialized_dimensions = data["dimensions"]
    applicable_nominal = 0.0
    for serialized in serialized_dimensions.values():
      if not isinstance(serialized, dict):
        raise ValueError("dimensions must contain dictionaries")
      if serialized.get("applicable") is True:
        applicable_nominal += _finite_number(
            serialized.get("nominal_weight"), "nominal_weight")
    dimensions = {}
    for name, serialized in serialized_dimensions.items():
      if not isinstance(serialized, dict):
        raise ValueError("dimensions must contain dictionaries")
      copied = dict(serialized)
      if copied.get("applicable") is True:
        nominal = _finite_number(copied.get("nominal_weight"),
                                 "nominal_weight")
        expected_effective = nominal * 100.0 / applicable_nominal
        wire_effective = _finite_number(
            copied.get("effective_weight"), "effective_weight")
        if wire_effective != round(expected_effective, 1):
          raise ValueError(
              "effective_weight does not match applicable nominal weights")
        copied["effective_weight"] = expected_effective
      dimensions[name] = DimensionResult.from_dict(copied)
    applicable = [dimension for dimension in dimensions.values()
                  if dimension.applicable]
    if applicable:
      expected_integrity = sum(
          dimension.nominal_weight * (dimension.unrounded_score or 0.0)
          for dimension in applicable) / sum(
              dimension.nominal_weight for dimension in applicable)
      wire_integrity = _score(data["integrity_score"], "integrity_score")
      if wire_integrity != round(expected_integrity, 1):
        raise ValueError(
            "integrity_score does not match dimension counts and weights")
    else:
      expected_integrity = data["integrity_score"]
    report = cls(
        integrity_score=expected_integrity,
        findings=data["findings"],
        dimensions=dimensions,
        manifest_sha256=data["manifest_sha256"],
    )
    if data["status"] != report.status.value:
      raise ValueError("status does not match the fail-closed finding status")
    return report


@dataclass(frozen=True)
class RepairRecord:
  attempt: int
  reason_codes: tuple[ReasonCode, ...]
  action: str
  resolved: bool

  def __post_init__(self) -> None:
    if isinstance(self.attempt, bool) or not isinstance(self.attempt, int) or self.attempt < 1:
      raise ValueError("attempt must be a positive integer")
    if not isinstance(self.reason_codes, (list, tuple)):
      raise ValueError("reason_codes must be a list")
    object.__setattr__(self, "reason_codes", tuple(
        _enum(code, ReasonCode, "reason_code") for code in self.reason_codes))
    object.__setattr__(self, "action", _nonempty_string(self.action, "action"))
    if not isinstance(self.resolved, bool):
      raise ValueError("resolved must be a boolean")

  def to_dict(self) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "attempt": self.attempt,
        "reason_codes": [code.value for code in self.reason_codes],
        "action": self.action,
        "resolved": self.resolved,
    }

  @classmethod
  def from_dict(cls, value: dict) -> RepairRecord:
    data = _require_fields(value, {
        "schema_version", "attempt", "reason_codes", "action", "resolved",
    }, cls.__name__)
    return cls(
        attempt=data["attempt"],
        reason_codes=data["reason_codes"],
        action=data["action"],
        resolved=data["resolved"],
    )


@dataclass(frozen=True)
class IntegrityRunReport:
  pass_report: PassReport
  quality_score: Optional[float]
  repairs: tuple[RepairRecord, ...]

  def __post_init__(self) -> None:
    if not isinstance(self.pass_report, PassReport):
      raise ValueError("pass_report must be a PassReport")
    if self.quality_score is not None:
      object.__setattr__(self, "quality_score", _score(
          self.quality_score, "quality_score"))
    object.__setattr__(self, "repairs", _model_list(
        self.repairs, RepairRecord, "repairs"))

  def to_dict(self) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "pass_report": self.pass_report.to_dict(),
        "quality_score": self.quality_score,
        "repairs": [repair.to_dict() for repair in self.repairs],
    }

  @classmethod
  def from_dict(cls, value: dict) -> IntegrityRunReport:
    data = _require_fields(value, {
        "schema_version", "pass_report", "quality_score", "repairs",
    }, cls.__name__)
    if not isinstance(data["pass_report"], dict):
      raise ValueError("pass_report must be a dictionary")
    return cls(
        pass_report=PassReport.from_dict(data["pass_report"]),
        quality_score=data["quality_score"],
        repairs=data["repairs"],
    )

  @classmethod
  def example_valid(cls) -> IntegrityRunReport:
    dimensions = {
        name: DimensionResult(
            name=name, score=100.0, applicable=True,
            evaluated_units=1, passed_units=1,
            nominal_weight=DIMENSION_WEIGHTS[name],
            effective_weight=DIMENSION_WEIGHTS[name], findings=[])
        for name in DIMENSION_ORDER
    }
    return cls(
        pass_report=PassReport(
            integrity_score=100.0,
            findings=[],
            dimensions=dimensions,
            manifest_sha256="0" * 64,
        ),
        quality_score=None,
        repairs=[],
    )
