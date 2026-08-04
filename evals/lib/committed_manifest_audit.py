"""Read and audit a runtime-supplied set of committed public-input manifests."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import stat
import unicodedata
from dataclasses import dataclass


INDEX_NAME = "commitment-index.json"
SCHEMA_VERSION = "1.0.0"
MAX_INDEX_BYTES = 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_CASES = 10_000
MAX_INPUTS_PER_CASE = 1_000

_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_OPEN_SUPPORTS_DIR_FD = os.open in getattr(os, "supports_dir_fd", ())


class ManifestAuditError(ValueError):
  """A committed manifest set cannot be audited safely."""


@dataclass(frozen=True)
class _FileWitness:
  relative_path: pathlib.PurePosixPath
  context: str
  limit: int
  digest: str
  descriptors: tuple[int, ...]
  metadata: tuple[os.stat_result, ...]


def _require_secure_descriptor_support() -> None:
  required = ("open", "close", "fstat", "read")
  if (
      not _OPEN_SUPPORTS_DIR_FD
      or not getattr(os, "O_NOFOLLOW", 0)
      or not getattr(os, "O_DIRECTORY", 0)
      or not all(callable(getattr(os, name, None)) for name in required)
  ):
    raise ManifestAuditError(
        "secure audit requires descriptor-relative nofollow file access")


def _open_flags(*, directory: bool) -> int:
  flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
  if directory:
    flags |= os.O_DIRECTORY
  return flags


def _component_identity(value: os.stat_result) -> tuple[int, int, int]:
  return value.st_dev, value.st_ino, value.st_mode


def _open_root_directory(
    root: pathlib.Path,
) -> tuple[int, str, tuple[tuple[int, int, int], ...]]:
  """Open every absolute root component without following a symlink."""
  raw_root = os.fspath(root)
  if type(raw_root) is not str:
    raise ManifestAuditError("manifest root path must be text")
  absolute = os.path.abspath(raw_root)
  components = pathlib.PurePath(absolute).parts
  descriptors: list[int] = []
  identities = []
  try:
    descriptor = os.open(os.path.sep, _open_flags(directory=True))
    descriptors.append(descriptor)
    identities.append(_component_identity(os.fstat(descriptor)))
    for component in components[1:]:
      descriptor = os.open(
          component, _open_flags(directory=True), dir_fd=descriptor)
      descriptors.append(descriptor)
      metadata = os.fstat(descriptor)
      if not stat.S_ISDIR(metadata.st_mode):
        raise ManifestAuditError("manifest root component is not a directory")
      identities.append(_component_identity(metadata))
    root_descriptor = descriptors.pop()
    ancestors = descriptors
    descriptors = [root_descriptor]
    _close(ancestors, "manifest root ancestors")
    descriptors = []
    return root_descriptor, absolute, tuple(identities)
  except ManifestAuditError:
    _close(descriptors, "manifest root")
    raise
  except Exception as exc:
    _close(descriptors, "manifest root")
    raise ManifestAuditError("cannot securely open manifest root") from exc


def _close(descriptors: list[int], context: str) -> None:
  error = None
  for descriptor in reversed(descriptors):
    try:
      os.close(descriptor)
    except Exception as exc:  # pragma: no cover - OS failure conversion
      error = exc
  if error is not None:
    raise ManifestAuditError(f"cannot close {context}: {error}") from error


def _safe_relative_path(value: object, context: str) -> pathlib.PurePosixPath:
  if type(value) is not str:
    raise ManifestAuditError(f"{context} path must be a string")
  try:
    value.encode("utf-8")
  except UnicodeEncodeError as exc:
    raise ManifestAuditError(
        f"{context} path must contain valid Unicode scalar values") from exc
  if unicodedata.normalize("NFC", value) != value:
    raise ManifestAuditError(f"{context} path must use canonical NFC Unicode")
  path = pathlib.PurePosixPath(value)
  if (
      not value
      or "\\" in value
      or "\x00" in value
      or path.is_absolute()
      or "." in path.parts
      or ".." in path.parts
      or path.as_posix() != value
  ):
    raise ManifestAuditError(f"{context} path is not canonical and relative")
  return path


def _path_alias(value: str) -> str:
  return unicodedata.normalize(
      "NFC", unicodedata.normalize("NFC", value).casefold())


def _stable_file_metadata(value: os.stat_result) -> tuple[int, ...]:
  return (
      value.st_dev,
      value.st_ino,
      value.st_mode,
      value.st_nlink,
      value.st_uid,
      value.st_gid,
      value.st_size,
      value.st_mtime_ns,
      value.st_ctime_ns,
  )


def _read_regular_file(
    root_descriptor: int,
    relative_path: pathlib.PurePosixPath,
    *,
    limit: int,
    context: str,
) -> tuple[bytes, _FileWitness]:
  descriptors: list[int] = []
  directory_metadata = []
  try:
    parent_descriptor = root_descriptor
    for component in relative_path.parts[:-1]:
      descriptor = os.open(
          component, _open_flags(directory=True), dir_fd=parent_descriptor)
      descriptors.append(descriptor)
      parent_descriptor = descriptor
      metadata = os.fstat(descriptor)
      if not stat.S_ISDIR(metadata.st_mode):
        raise ManifestAuditError(f"{context} parent is not a directory")
      directory_metadata.append(metadata)

    descriptor = os.open(
        relative_path.parts[-1], _open_flags(directory=False),
        dir_fd=parent_descriptor)
    descriptors.append(descriptor)
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode):
      raise ManifestAuditError(f"{context} is not a regular file")
    if before.st_nlink != 1:
      raise ManifestAuditError(f"{context} must have a single link")
    if before.st_size < 0 or before.st_size > limit:
      raise ManifestAuditError(f"{context} exceeds the size limit")

    chunks = []
    total = 0
    while True:
      chunk = os.read(descriptor, min(64 * 1024, limit + 1 - total))
      if not chunk:
        break
      chunks.append(chunk)
      total += len(chunk)
      if total > limit:
        raise ManifestAuditError(f"{context} exceeds the size limit")

    after = os.fstat(descriptor)
    if _stable_file_metadata(before) != _stable_file_metadata(after):
      raise ManifestAuditError(f"{context} changed while it was read")
    if after.st_nlink != 1 or after.st_size != total:
      raise ManifestAuditError(f"{context} changed while it was read")

    payload = b"".join(chunks)
    witness = _FileWitness(
        relative_path=relative_path,
        context=context,
        limit=limit,
        digest=hashlib.sha256(payload).hexdigest(),
        descriptors=tuple(descriptors),
        metadata=tuple([*directory_metadata, after]),
    )
    _check_held_witness(witness)
    _validate_witness_path(root_descriptor, witness, hash_bytes=False)
    descriptors = []
    return payload, witness
  except ManifestAuditError:
    raise
  except Exception as exc:
    raise ManifestAuditError(f"cannot securely open {context}: {exc}") from exc
  finally:
    _close(descriptors, context)


def _check_held_witness(witness: _FileWitness) -> None:
  if len(witness.descriptors) != len(witness.metadata):
    raise ManifestAuditError(f"{witness.context} has an incomplete witness")
  for descriptor, expected in zip(witness.descriptors, witness.metadata):
    if _stable_file_metadata(os.fstat(descriptor)) != (
        _stable_file_metadata(expected)):
      raise ManifestAuditError(
          f"{witness.context} changed during manifest-set audit")


def _validate_witness_path(
    root_descriptor: int,
    witness: _FileWitness,
    *,
    hash_bytes: bool,
) -> None:
  descriptors = []
  try:
    parent_descriptor = root_descriptor
    for component, expected in zip(
        witness.relative_path.parts[:-1], witness.metadata[:-1]):
      descriptor = os.open(
          component, _open_flags(directory=True), dir_fd=parent_descriptor)
      descriptors.append(descriptor)
      current = os.fstat(descriptor)
      if (
          not stat.S_ISDIR(current.st_mode)
          or _stable_file_metadata(current) != _stable_file_metadata(expected)
      ):
        raise ManifestAuditError(
            f"{witness.context} changed during manifest-set audit")
      parent_descriptor = descriptor

    descriptor = os.open(
        witness.relative_path.parts[-1], _open_flags(directory=False),
        dir_fd=parent_descriptor)
    descriptors.append(descriptor)
    before = os.fstat(descriptor)
    if (
        not stat.S_ISREG(before.st_mode)
        or _stable_file_metadata(before) != (
            _stable_file_metadata(witness.metadata[-1]))
    ):
      raise ManifestAuditError(
          f"{witness.context} changed during manifest-set audit")
    if not hash_bytes:
      return

    digest = hashlib.sha256()
    total = 0
    while True:
      payload = os.read(
          descriptor, min(64 * 1024, witness.limit + 1 - total))
      if not payload:
        break
      digest.update(payload)
      total += len(payload)
      if total > witness.limit:
        raise ManifestAuditError(
            f"{witness.context} exceeds the size limit")
    after = os.fstat(descriptor)
    if (
        _stable_file_metadata(before) != _stable_file_metadata(after)
        or total != after.st_size
        or digest.hexdigest() != witness.digest
    ):
      raise ManifestAuditError(
          f"{witness.context} changed during manifest-set audit")
  except ManifestAuditError:
    raise
  except Exception as exc:
    raise ManifestAuditError(
        f"{witness.context} changed during manifest-set audit") from exc
  finally:
    _close(descriptors, f"reopened {witness.context}")


def _revalidate_witnesses(
    root_descriptor: int,
    witnesses: list[_FileWitness],
) -> None:
  for witness in witnesses:
    _check_held_witness(witness)
  for witness in witnesses:
    _validate_witness_path(root_descriptor, witness, hash_bytes=True)
  for witness in witnesses:
    _check_held_witness(witness)


def _append_witness(
    witnesses: list[_FileWitness], witness: _FileWitness,
) -> None:
  """Registration seam for deterministic ownership-failure tests."""
  witnesses.append(witness)


def _register_witness(
    witnesses: list[_FileWitness], witness: _FileWitness,
) -> None:
  """Transfer descriptor ownership to witnesses or close it on any abort."""
  original_length = len(witnesses)
  try:
    _append_witness(witnesses, witness)
  except BaseException:
    del witnesses[original_length:]
    _close(list(witness.descriptors), f"unregistered {witness.context}")
    raise


def _verify_root_directory(
    root_descriptor: int,
    root_absolute: str,
    expected_chain: tuple[tuple[int, int, int], ...],
    root_before: os.stat_result,
) -> None:
  root_after = os.fstat(root_descriptor)
  if _stable_file_metadata(root_before) != _stable_file_metadata(root_after):
    raise ManifestAuditError("manifest root changed during audit")
  reopened_descriptor = None
  try:
    reopened_descriptor, _, current_chain = _open_root_directory(
        pathlib.Path(root_absolute))
    current = os.fstat(reopened_descriptor)
    if (
        current_chain != expected_chain
        or _stable_file_metadata(current) != _stable_file_metadata(root_after)
    ):
      raise ManifestAuditError("manifest root path changed during audit")
  finally:
    if reopened_descriptor is not None:
      _close([reopened_descriptor], "reopened manifest root")


def _reject_constant(value: str):
  raise ManifestAuditError(f"JSON contains nonfinite number {value}")


def _unique_object(pairs):
  value = {}
  for key, item in pairs:
    if key in value:
      raise ManifestAuditError(f"JSON contains duplicate key {key!r}")
    value[key] = item
  return value


def _decode_json(payload: bytes, context: str) -> object:
  try:
    text = payload.decode("utf-8")
    return json.loads(
        text, object_pairs_hook=_unique_object,
        parse_constant=_reject_constant)
  except ManifestAuditError:
    raise
  except (UnicodeDecodeError, json.JSONDecodeError) as exc:
    raise ManifestAuditError(f"{context} is not valid JSON: {exc}") from exc


def _require_exact_keys(value: object, expected: set[str], context: str) -> dict:
  if type(value) is not dict or set(value) != expected:
    raise ManifestAuditError(
        f"{context} must contain exactly {sorted(expected)!r}")
  return value


def _require_id(value: object, context: str) -> str:
  if type(value) is not str or len(value) > 64 or not _ID_RE.fullmatch(value):
    raise ManifestAuditError(
        f"{context} must be a lowercase opaque identifier")
  return value


def _require_sha256(value: object, context: str) -> str:
  if type(value) is not str or not _SHA256_RE.fullmatch(value):
    raise ManifestAuditError(f"{context} must be a lowercase SHA-256 digest")
  return value


def _require_schema_version(value: object, context: str) -> None:
  if value != SCHEMA_VERSION:
    raise ManifestAuditError(
        f"{context} has unsupported schema_version {value!r}")


def _load_manifest(payload: bytes, expected_case_id: str) -> tuple[int, set[str]]:
  manifest = _require_exact_keys(
      _decode_json(payload, "case manifest"),
      {"schema_version", "case_id", "public_inputs"},
      "case manifest",
  )
  _require_schema_version(manifest["schema_version"], "case manifest")
  case_id = _require_id(manifest["case_id"], "case manifest case_id")
  if case_id != expected_case_id:
    raise ManifestAuditError("case manifest case_id does not match its index entry")
  inputs = manifest["public_inputs"]
  if type(inputs) is not list or not inputs or len(inputs) > MAX_INPUTS_PER_CASE:
    raise ManifestAuditError(
        "case manifest public_inputs must be a nonempty bounded list")

  input_ids: set[str] = set()
  input_id_aliases: set[str] = set()
  input_paths: set[str] = set()
  for offset, raw_input in enumerate(inputs):
    item = _require_exact_keys(
        raw_input, {"input_id", "path", "size", "sha256"},
        f"public input {offset}")
    input_id = _require_id(item["input_id"], f"public input {offset} input_id")
    alias = input_id.casefold()
    if input_id in input_ids or alias in input_id_aliases:
      raise ManifestAuditError("case manifest contains duplicate input_id aliases")
    input_ids.add(input_id)
    input_id_aliases.add(alias)
    path = _safe_relative_path(item["path"], f"public input {offset}").as_posix()
    path_alias = _path_alias(path)
    if path_alias in input_paths:
      raise ManifestAuditError("case manifest contains duplicate input path aliases")
    input_paths.add(path_alias)
    size = item["size"]
    if type(size) is not int or size < 0 or size > 2 ** 53 - 1:
      raise ManifestAuditError("public input size must be a nonnegative safe integer")
    _require_sha256(item["sha256"], f"public input {offset} sha256")
  return len(inputs), input_paths


def audit_committed_manifests(root: pathlib.Path) -> dict[str, object]:
  """Verify an index and its listed manifests without opening public inputs."""
  _require_secure_descriptor_support()
  root_descriptor = None
  witnesses: list[_FileWitness] = []
  try:
    root_descriptor, root_absolute, root_chain = _open_root_directory(root)
    root_before = os.fstat(root_descriptor)
    if not stat.S_ISDIR(root_before.st_mode):
      raise ManifestAuditError("manifest root is not a directory")
    index_payload, index_witness = _read_regular_file(
        root_descriptor, pathlib.PurePosixPath(INDEX_NAME),
        limit=MAX_INDEX_BYTES, context="commitment index")
    _register_witness(witnesses, index_witness)
    index = _require_exact_keys(
        _decode_json(index_payload, "commitment index"),
        {"schema_version", "cases"}, "commitment index")
    _require_schema_version(index["schema_version"], "commitment index")
    entries = index["cases"]
    if type(entries) is not list or not entries or len(entries) > MAX_CASES:
      raise ManifestAuditError("commitment index cases must be a nonempty bounded list")

    case_ids: set[str] = set()
    case_aliases: set[str] = set()
    manifest_paths: set[str] = set()
    audit_cases = []
    all_input_paths: set[str] = set()
    total_inputs = 0
    for offset, raw_entry in enumerate(entries):
      entry = _require_exact_keys(
          raw_entry, {"case_id", "manifest_path", "manifest_sha256"},
          f"commitment index case {offset}")
      case_id = _require_id(entry["case_id"], f"commitment index case {offset} case_id")
      case_alias = case_id.casefold()
      if case_id in case_ids or case_alias in case_aliases:
        raise ManifestAuditError("commitment index contains duplicate case_id aliases")
      case_ids.add(case_id)
      case_aliases.add(case_alias)

      manifest_path = _safe_relative_path(
          entry["manifest_path"],
          f"commitment index case {offset} manifest").as_posix()
      path_alias = _path_alias(manifest_path)
      if path_alias in manifest_paths:
        raise ManifestAuditError("commitment index contains duplicate manifest path aliases")
      manifest_paths.add(path_alias)
      expected_digest = _require_sha256(
          entry["manifest_sha256"],
          f"commitment index case {offset} manifest_sha256")
      payload, manifest_witness = _read_regular_file(
          root_descriptor, pathlib.PurePosixPath(manifest_path),
          limit=MAX_MANIFEST_BYTES, context=f"manifest for {case_id}")
      _register_witness(witnesses, manifest_witness)
      actual_digest = hashlib.sha256(payload).hexdigest()
      if actual_digest != expected_digest:
        raise ManifestAuditError(f"manifest digest mismatch for {case_id}")
      input_count, input_paths = _load_manifest(payload, case_id)
      if all_input_paths.intersection(input_paths):
        raise ManifestAuditError("case manifests contain duplicate public input path aliases")
      all_input_paths.update(input_paths)
      total_inputs += input_count
      audit_cases.append({
          "case_id": case_id,
          "manifest_sha256": actual_digest,
          "public_input_count": input_count,
      })

    audit = {
        "schema_version": SCHEMA_VERSION,
        "index_sha256": hashlib.sha256(index_payload).hexdigest(),
        "case_count": len(audit_cases),
        "public_input_count": total_inputs,
        "cases": sorted(audit_cases, key=lambda item: item["case_id"]),
    }
    _revalidate_witnesses(root_descriptor, witnesses)
    _verify_root_directory(
        root_descriptor, root_absolute, root_chain, root_before)
    return audit
  except ManifestAuditError:
    raise
  except Exception as exc:
    raise ManifestAuditError("cannot securely open manifest root") from exc
  finally:
    descriptors = []
    if root_descriptor is not None:
      descriptors.append(root_descriptor)
    for witness in witnesses:
      descriptors.extend(witness.descriptors)
    _close(descriptors, "manifest audit")


__all__ = ["ManifestAuditError", "audit_committed_manifests"]
