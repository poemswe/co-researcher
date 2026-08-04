"""Strict, versioned result types for literature-review integrity checks."""

from .models import (
    DIMENSION_NAMES,
    SCHEMA_VERSION,
    DimensionResult,
    Finding,
    IntegrityRunReport,
    IntegrityStatus,
    PassReport,
    ReasonCode,
    RepairRecord,
    Severity,
)

__all__ = [
    "DIMENSION_NAMES",
    "SCHEMA_VERSION",
    "DimensionResult",
    "Finding",
    "IntegrityRunReport",
    "IntegrityStatus",
    "PassReport",
    "ReasonCode",
    "RepairRecord",
    "Severity",
]
