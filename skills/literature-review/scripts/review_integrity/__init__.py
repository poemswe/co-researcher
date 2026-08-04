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
from .validators import (
    artifact_findings,
    citation_findings,
    claim_findings,
    prisma_findings,
    validate_snapshot,
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
    "artifact_findings",
    "citation_findings",
    "claim_findings",
    "prisma_findings",
    "validate_snapshot",
]
