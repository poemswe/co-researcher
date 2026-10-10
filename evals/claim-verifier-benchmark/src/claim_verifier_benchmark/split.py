from __future__ import annotations

import dataclasses
import hashlib
import re
import struct
import unicodedata
from collections import Counter
from collections.abc import Iterable

from .constants import DOMAINS

_SPLIT_PREFIX = b"claim-verifier-split-v1\0"
_PAPER_PREFIX = b"claim-verifier-paper-v1\0"


class SplitError(ValueError):
  pass


@dataclasses.dataclass(frozen=True, slots=True)
class Paper:
  stable_id: str
  domain: str

  def __post_init__(self):
    canonical = unicodedata.normalize("NFC", self.stable_id).strip()
    if not canonical or canonical != self.stable_id:
      raise SplitError(f"stable ID is not canonical: {self.stable_id!r}")
    if self.domain not in DOMAINS:
      raise SplitError(f"unknown domain: {self.domain!r}")


def _decode_hex(name: str, value: str, byte_length: int) -> bytes:
  if len(value) != byte_length * 2:
    raise SplitError(f"{name} must contain {byte_length * 2} hex characters")
  if re.fullmatch(r"[0-9A-Fa-f]+", value) is None:
    raise SplitError(f"{name} is not ASCII hexadecimal")
  try:
    decoded = bytes.fromhex(value)
  except ValueError as exc:
    raise SplitError(f"{name} is not hexadecimal") from exc
  if len(decoded) != byte_length:
    raise SplitError(f"{name} decoded to the wrong length")
  return decoded


def derive_split_key(output_value_hex: str, archive_sha256_hex: str) -> bytes:
  if archive_sha256_hex != archive_sha256_hex.lower():
    raise SplitError("construction archive SHA-256 must be lowercase")
  beacon = _decode_hex("outputValue", output_value_hex, 64)
  archive = _decode_hex("construction archive SHA-256", archive_sha256_hex, 32)
  return hashlib.sha256(_SPLIT_PREFIX + beacon + archive).digest()


def paper_order_key(split_key: bytes, paper: Paper) -> bytes:
  if len(split_key) != 32:
    raise SplitError("split key must contain 32 bytes")
  domain = paper.domain.encode("ascii")
  stable_id = paper.stable_id.encode("utf-8")
  if len(domain) > 0xFFFF or len(stable_id) > 0xFFFFFFFF:
    raise SplitError("domain or stable ID exceeds its length prefix")
  payload = (
      _PAPER_PREFIX
      + split_key
      + struct.pack(">H", len(domain))
      + domain
      + struct.pack(">I", len(stable_id))
      + stable_id
  )
  return hashlib.sha256(payload).digest()


def assign_split(
    split_key: bytes,
    papers: Iterable[Paper],
) -> dict[str, str]:
  items = tuple(papers)
  identifiers = [paper.stable_id for paper in items]
  if len(set(identifiers)) != len(identifiers):
    raise SplitError("stable paper IDs must be globally unique")
  counts = Counter(paper.domain for paper in items)
  if counts != Counter({domain: 5 for domain in DOMAINS}):
    raise SplitError("each domain must contain exactly five papers")
  assignment: dict[str, str] = {}
  for domain in DOMAINS:
    ordered = sorted(
        (paper for paper in items if paper.domain == domain),
        key=lambda paper: (
            paper_order_key(split_key, paper),
            paper.stable_id.encode("utf-8"),
        ),
    )
    for index, paper in enumerate(ordered):
      assignment[paper.stable_id] = "development" if index < 2 else "test"
  return assignment
