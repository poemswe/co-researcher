from __future__ import annotations

import base64
import hashlib
import hmac
import re
from collections.abc import Iterable

from .canonical import canonical_bytes, sha256_hex

_KIND_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_MAPPING_PREFIX = b"review-mapping-v1\0"
_ORDER_PREFIX = b"review-order-v1\0"


class CommitmentError(ValueError):
    pass


def opaque_id(secret: bytes, kind: str, official_id: str) -> str:
    if len(secret) < 32:
        raise CommitmentError("opaque-ID secret must contain at least 32 bytes")
    if not _KIND_RE.fullmatch(kind):
        raise CommitmentError(f"invalid opaque-ID kind: {kind!r}")
    if not official_id:
        raise CommitmentError("official ID must not be empty")
    digest = hmac.new(
        secret,
        kind.encode("ascii") + b"\0" + official_id.encode("utf-8"),
        hashlib.sha256,
    ).digest()[:16]
    token = base64.b32encode(digest).decode("ascii").rstrip("=").lower()
    return f"{kind}_{token}"


def review_order(values: Iterable[str], seed: bytes) -> tuple[str, ...]:
    if len(seed) < 32:
        raise CommitmentError("review-order seed must contain at least 32 bytes")
    items = tuple(values)
    if len(set(items)) != len(items):
        raise CommitmentError("review-order values must be unique")
    return tuple(
        sorted(
            items,
            key=lambda value: (
                hashlib.sha256(
                    _ORDER_PREFIX + seed + value.encode("utf-8")
                ).digest(),
                value.encode("utf-8"),
            ),
        )
    )


def mapping_commitment(mapping: dict, salt: bytes) -> str:
    if len(salt) != 32:
        raise CommitmentError("mapping salt must contain exactly 32 bytes")
    return sha256_hex(_MAPPING_PREFIX + canonical_bytes(mapping) + salt)


def verify_mapping_commitment(mapping: dict, salt: bytes, expected: str) -> bool:
    try:
        actual = mapping_commitment(mapping, salt)
    except CommitmentError:
        return False
    return hmac.compare_digest(actual, expected.lower())
