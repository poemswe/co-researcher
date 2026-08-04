"""Fail-closed loading and hashing of literature-review workspaces.

All paths are opened descriptor-relatively with symlink following disabled.
The returned snapshot retains the exact immutable bytes used to compute its
manifest, so later validators never need to reopen an artifact pathname.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from contextlib import contextmanager
import errno
import hashlib
import json
import math
import os
import pathlib
import re
import stat
from types import MappingProxyType
from typing import Any, Mapping, Optional

from .models import ReasonCode


SCHEMA_VERSION = "1.0.0"
CANONICALIZATION = "rfc8785-restricted-v1"
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_TOTAL_ARTIFACT_BYTES = 256 * 1024 * 1024

_FIXED_ARTIFACTS = frozenset({
    "protocol.md", "corpus.json", "claims.json", "synthesis.md", "refs.json",
})
_SOURCE_FILENAMES = ("fulltext.md", "abstract.md")
_EVIDENCE_ROLES = frozenset({"evidence", "background"})
_READ_SIZE = 1024 * 1024
_OPEN_SUPPORTS_DIR_FD = os.open in getattr(os, "supports_dir_fd", ())
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_LOADER_TOKEN = object()


class WorkspaceError(ValueError):
  """The workspace cannot be snapshotted without weakening the contract."""

  def __init__(
      self, message: str,
      reason_code: ReasonCode = ReasonCode.ARTIFACT_MALFORMED,
      artifact: str = ".",
  ):
    super().__init__(message)
    self.reason_code = ReasonCode(reason_code)
    self.artifact = artifact


def _filesystem_reason(exc: OSError) -> ReasonCode:
  """Classify operating-system failures without interpreting messages."""
  if exc.errno == errno.ENOENT:
    return ReasonCode.ARTIFACT_MISSING
  if exc.errno == errno.ELOOP:
    return ReasonCode.ARTIFACT_SYMLINK
  if exc.errno == errno.ENOTDIR:
    return ReasonCode.ARTIFACT_TYPE_INVALID
  return ReasonCode.VALIDATOR_INCOMPLETE


@contextmanager
def _artifact_context(relative_path: str):
  """Attach the submitted artifact to semantic errors that lack provenance."""
  try:
    yield
  except WorkspaceError as exc:
    if exc.artifact != ".":
      raise
    raise WorkspaceError(
        str(exc), exc.reason_code, relative_path) from exc


def _valid_unicode(value: str, field_name: str) -> str:
  if type(value) is not str:
    raise WorkspaceError(f"{field_name} must be a string")
  try:
    value.encode("utf-8")
  except UnicodeEncodeError as exc:
    raise WorkspaceError(f"{field_name} must contain valid Unicode") from exc
  return value


def _canonical_relative_path(raw: object) -> str:
  value = _valid_unicode(raw, "artifact path")
  path = pathlib.PurePosixPath(value)
  if (not value or path.is_absolute() or "." in path.parts
      or ".." in path.parts or path.as_posix() != value):
    raise WorkspaceError(
        f"artifact path is not canonical and relative: {value!r}",
        ReasonCode.ARTIFACT_TRAVERSAL, value)
  return value


def canonical_manifest_bytes(value: object) -> bytes:
  """Encode the closed snapshot-manifest schema in RFC 8785-equivalent bytes.

  This restricted schema contains only fixed ASCII keys, valid Unicode string
  values, and nonnegative integers within the interoperable JSON range. Those
  constraints make sorted, compact UTF-8 JSON byte-for-byte equivalent to RFC
  8785 without making the runtime depend on a canonicalization package.
  """
  if type(value) is not dict or set(value) != {"canonicalization", "files"}:
    raise WorkspaceError(
        "manifest must contain exactly canonicalization and files")
  if value["canonicalization"] != CANONICALIZATION:
    raise WorkspaceError(
        f"unsupported canonicalization: {value['canonicalization']!r}")
  files = value["files"]
  if type(files) is not list:
    raise WorkspaceError("manifest files must be a list")
  for record in files:
    if type(record) is not dict or set(record) != {"path", "size", "sha256"}:
      raise WorkspaceError(
          "manifest file records must contain exactly path, size, and sha256")
    _valid_unicode(record["path"], "manifest path")
    digest = _valid_unicode(record["sha256"], "manifest sha256")
    if not _SHA256_RE.fullmatch(digest):
      raise WorkspaceError("manifest sha256 must be lowercase hexadecimal")
    size = record["size"]
    if type(size) is not int or not 0 <= size <= (2 ** 53 - 1):
      raise WorkspaceError(
          "manifest size integer must be in the range 0..2**53-1")
  try:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
  except (TypeError, ValueError, UnicodeEncodeError) as exc:
    raise WorkspaceError(f"cannot canonicalize manifest: {exc}") from exc


@dataclass(frozen=True)
class Artifact:
  """One immutable submitted artifact and the digest of its retained bytes."""

  relative_path: str
  payload: bytes = field(repr=False)
  sha256: str
  preferred_for_claims: bool = False
  _loader_token: InitVar[object] = None

  def __post_init__(self, _loader_token: object) -> None:
    if _loader_token is not _LOADER_TOKEN:
      raise WorkspaceError(
          "Artifact construction is restricted to the workspace loader")
    _canonical_relative_path(self.relative_path)
    if type(self.payload) is not bytes:
      raise WorkspaceError(
          "artifact payload must be immutable bytes",
          ReasonCode.ARTIFACT_MALFORMED, self.relative_path)
    if len(self.payload) > MAX_ARTIFACT_BYTES:
      raise WorkspaceError(
          f"artifact exceeds size limit ({MAX_ARTIFACT_BYTES} bytes): "
          f"{self.relative_path}", ReasonCode.ARTIFACT_MALFORMED,
          self.relative_path)
    expected = hashlib.sha256(self.payload).hexdigest()
    if self.sha256 != expected:
      raise WorkspaceError(
          "artifact sha256 does not match its retained bytes",
          ReasonCode.ARTIFACT_MALFORMED, self.relative_path)
    if type(self.preferred_for_claims) is not bool:
      raise WorkspaceError(
          "preferred_for_claims must be a boolean",
          ReasonCode.ARTIFACT_MALFORMED, self.relative_path)

  @property
  def size(self) -> int:
    return len(self.payload)

  def manifest_record(self) -> dict[str, object]:
    return {
        "path": self.relative_path,
        "size": self.size,
        "sha256": self.sha256,
    }


@dataclass(frozen=True)
class WorkspaceSnapshot:
  """A deterministic manifest plus the exact bytes described by it."""

  files: tuple[Artifact, ...]
  canonicalization: str = CANONICALIZATION
  manifest_sha256: str = field(init=False)
  _files_by_path: Mapping[str, Artifact] = field(
      init=False, repr=False, compare=False)
  _loader_token: InitVar[object] = None

  def __post_init__(self, _loader_token: object) -> None:
    if _loader_token is not _LOADER_TOKEN:
      raise WorkspaceError(
          "WorkspaceSnapshot construction is restricted to the workspace "
          "loader")
    if self.canonicalization != CANONICALIZATION:
      raise WorkspaceError(
          f"unsupported canonicalization: {self.canonicalization!r}")
    if not isinstance(self.files, tuple) or not all(
        isinstance(item, Artifact) for item in self.files):
      raise WorkspaceError("files must be a tuple of Artifact values")
    paths = [item.relative_path for item in self.files]
    ordered = sorted(paths, key=lambda value: value.encode("utf-8"))
    if paths != ordered:
      raise WorkspaceError("artifacts must be ordered by UTF-8 path bytes")
    if len(paths) != len(set(paths)):
      raise WorkspaceError("artifact paths must be unique")
    total_size = sum(item.size for item in self.files)
    if total_size > MAX_TOTAL_ARTIFACT_BYTES:
      raise WorkspaceError(
          "workspace exceeds total retained artifact size limit "
          f"({MAX_TOTAL_ARTIFACT_BYTES} bytes)")
    by_path = MappingProxyType(dict(zip(paths, self.files)))
    object.__setattr__(self, "_files_by_path", by_path)
    digest = hashlib.sha256(canonical_manifest_bytes(self.manifest)).hexdigest()
    object.__setattr__(self, "manifest_sha256", digest)

  @property
  def manifest(self) -> dict[str, object]:
    return {
        "canonicalization": self.canonicalization,
        "files": [item.manifest_record() for item in self.files],
    }

  def read_bytes(self, relative_path: str) -> bytes:
    try:
      return self._files_by_path[relative_path].payload
    except (KeyError, TypeError) as exc:
      raise WorkspaceError(
          f"artifact is not present in the snapshot: {relative_path!r}",
          ReasonCode.ARTIFACT_MISSING, relative_path) from exc

  def read_text(self, relative_path: str) -> str:
    payload = self.read_bytes(relative_path)
    try:
      return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
      raise WorkspaceError(
          f"artifact is not valid UTF-8: {relative_path}",
          ReasonCode.ARTIFACT_MALFORMED, relative_path) from exc

  def read_json(self, relative_path: str) -> object:
    return _decode_json(self.read_bytes(relative_path), relative_path)


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
  result: dict[str, Any] = {}
  for key, value in pairs:
    if key in result:
      raise WorkspaceError(f"duplicate JSON key: {key!r}")
    result[key] = value
  return result


def _reject_json_constant(value: str) -> object:
  raise WorkspaceError(f"nonstandard JSON numeric constant: {value}")


def _parse_finite_float(value: str) -> float:
  result = float(value)
  if not math.isfinite(result):
    raise WorkspaceError(f"JSON number must be finite: {value}")
  return result


def _decode_json(payload: bytes, relative_path: str) -> object:
  try:
    text = payload.decode("utf-8")
  except UnicodeDecodeError as exc:
    raise WorkspaceError(
        f"artifact is not valid UTF-8: {relative_path}",
        ReasonCode.ARTIFACT_MALFORMED, relative_path) from exc
  try:
    with _artifact_context(relative_path):
      return json.loads(
          text,
          object_pairs_hook=_duplicate_rejecting_object,
          parse_constant=_reject_json_constant,
          parse_float=_parse_finite_float,
      )
  except json.JSONDecodeError as exc:
    raise WorkspaceError(
        f"artifact contains malformed JSON: {relative_path}: {exc}",
        ReasonCode.ARTIFACT_MALFORMED, relative_path) from exc


def decode_json_bytes(payload: bytes, label: str) -> object:
  """Decode retained JSON bytes with the workspace's strict JSON rules."""
  if type(payload) is not bytes:
    raise WorkspaceError("JSON payload must be immutable bytes")
  if type(label) is not str or not label:
    raise WorkspaceError("JSON input label must be a nonempty string")
  return _decode_json(payload, label)


def _secure_open_flags(*, directory: bool) -> int:
  no_follow = getattr(os, "O_NOFOLLOW", 0)
  directory_only = getattr(os, "O_DIRECTORY", 0)
  nonblocking = getattr(os, "O_NONBLOCK", 0)
  required = ("open", "close", "fstat", "read")
  if (not _OPEN_SUPPORTS_DIR_FD or not no_follow or not directory_only
      or not nonblocking
      or not all(callable(getattr(os, name, None)) for name in required)):
    raise WorkspaceError(
        "secure workspace traversal requires descriptor-relative open, "
        "O_NOFOLLOW, O_DIRECTORY, O_NONBLOCK, fstat, read, and close")
  flags = os.O_RDONLY | no_follow | getattr(os, "O_CLOEXEC", 0)
  return flags | directory_only if directory else flags | nonblocking


def _open_root(root: pathlib.Path) -> int:
  try:
    raw = os.fspath(root)
    if type(raw) is not str:
      raise WorkspaceError("workspace root must be a text path")
    absolute = pathlib.PurePath(os.path.abspath(raw))
    current = os.open(os.path.sep, _secure_open_flags(directory=True))
    try:
      for component in absolute.parts[1:]:
        try:
          metadata = os.stat(component, dir_fd=current, follow_symlinks=False)
        except OSError as exc:
          raise WorkspaceError(
              f"cannot inspect workspace root component: {exc}",
              _filesystem_reason(exc), ".") from exc
        if stat.S_ISLNK(metadata.st_mode):
          raise WorkspaceError(
              "workspace root must not contain symlinks",
              ReasonCode.ARTIFACT_SYMLINK, ".")
        if not stat.S_ISDIR(metadata.st_mode):
          raise WorkspaceError(
              "workspace root is not a directory",
              ReasonCode.ARTIFACT_TYPE_INVALID, ".")
        child = os.open(
            component, _secure_open_flags(directory=True), dir_fd=current)
        try:
          if not stat.S_ISDIR(os.fstat(child).st_mode):
            raise WorkspaceError(
                "workspace root is not a directory",
                ReasonCode.ARTIFACT_TYPE_INVALID, ".")
        except Exception:
          os.close(child)
          raise
        try:
          os.close(current)
        except Exception:
          try:
            os.close(child)
          except Exception:
            pass
          raise
        current = child
      if not stat.S_ISDIR(os.fstat(current).st_mode):
        raise WorkspaceError(
            "workspace root is not a directory",
            ReasonCode.ARTIFACT_TYPE_INVALID, ".")
      return current
    except Exception:
      os.close(current)
      raise
  except WorkspaceError:
    raise
  except OSError as exc:
    raise WorkspaceError(
        f"cannot securely open workspace root: {exc}",
        _filesystem_reason(exc), ".",
    ) from exc


def _read_member(root_descriptor: int, relative_path: str) -> bytes:
  path = pathlib.PurePosixPath(_canonical_relative_path(relative_path))
  descriptors: list[int] = []
  try:
    parent = root_descriptor
    for component in path.parts[:-1]:
      metadata = os.stat(component, dir_fd=parent, follow_symlinks=False)
      if stat.S_ISLNK(metadata.st_mode):
        raise WorkspaceError(
            f"artifact path contains a symlink: {relative_path}",
            ReasonCode.ARTIFACT_SYMLINK, relative_path)
      if not stat.S_ISDIR(metadata.st_mode):
        raise WorkspaceError(
            f"artifact path component is not a directory: {relative_path}",
            ReasonCode.ARTIFACT_TYPE_INVALID, relative_path)
      descriptor = os.open(
          component, _secure_open_flags(directory=True), dir_fd=parent)
      descriptors.append(descriptor)
      if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        raise WorkspaceError(
            f"artifact path component is not a directory: {relative_path}",
            ReasonCode.ARTIFACT_TYPE_INVALID, relative_path)
      parent = descriptor
    metadata = os.stat(
        path.parts[-1], dir_fd=parent, follow_symlinks=False)
    if stat.S_ISLNK(metadata.st_mode):
      raise WorkspaceError(
          f"artifact is a symlink: {relative_path}",
          ReasonCode.ARTIFACT_SYMLINK, relative_path)
    if not stat.S_ISREG(metadata.st_mode):
      raise WorkspaceError(
          f"artifact is not a regular file: {relative_path}",
          ReasonCode.ARTIFACT_TYPE_INVALID, relative_path)
    leaf = os.open(
        path.parts[-1], _secure_open_flags(directory=False), dir_fd=parent)
    descriptors.append(leaf)
    metadata = os.fstat(leaf)
    if not stat.S_ISREG(metadata.st_mode):
      raise WorkspaceError(
          f"artifact is not a regular file: {relative_path}",
          ReasonCode.ARTIFACT_TYPE_INVALID, relative_path)
    if metadata.st_size < 0 or metadata.st_size > MAX_ARTIFACT_BYTES:
      raise WorkspaceError(
          f"artifact exceeds size limit ({MAX_ARTIFACT_BYTES} bytes): "
          f"{relative_path}", ReasonCode.ARTIFACT_MALFORMED, relative_path)
    chunks: list[bytes] = []
    retained = 0
    while True:
      allowance = MAX_ARTIFACT_BYTES + 1 - retained
      if allowance <= 0:
        raise WorkspaceError(
            f"artifact exceeds size limit ({MAX_ARTIFACT_BYTES} bytes): "
            f"{relative_path}", ReasonCode.ARTIFACT_MALFORMED, relative_path)
      chunk = os.read(leaf, min(_READ_SIZE, allowance))
      if not chunk:
        break
      chunks.append(chunk)
      retained += len(chunk)
      if retained > MAX_ARTIFACT_BYTES:
        raise WorkspaceError(
            f"artifact exceeds size limit ({MAX_ARTIFACT_BYTES} bytes): "
            f"{relative_path}", ReasonCode.ARTIFACT_MALFORMED, relative_path)
    return b"".join(chunks)
  finally:
    close_error: Optional[Exception] = None
    for descriptor in reversed(descriptors):
      try:
        os.close(descriptor)
      except Exception as exc:
        close_error = exc
    if close_error is not None:
      raise WorkspaceError(
          f"cannot close artifact descriptor for {relative_path}: {close_error}",
          ReasonCode.VALIDATOR_INCOMPLETE, relative_path,
      ) from close_error


class _SnapshotReader:
  def __init__(self, root_descriptor: int):
    self.root_descriptor = root_descriptor
    self.payloads: dict[str, bytes] = {}
    self.missing: set[str] = set()
    self.total_size = 0

  def optional(self, relative_path: str) -> Optional[bytes]:
    if relative_path in self.payloads:
      return self.payloads[relative_path]
    if relative_path in self.missing:
      return None
    try:
      payload = _read_member(self.root_descriptor, relative_path)
    except FileNotFoundError:
      self.missing.add(relative_path)
      return None
    except WorkspaceError:
      raise
    except OSError as exc:
      raise WorkspaceError(
          f"cannot securely read artifact {relative_path}: {exc}",
          _filesystem_reason(exc), relative_path) from exc
    except Exception as exc:
      raise WorkspaceError(
          f"cannot securely read artifact {relative_path}: {exc}",
          ReasonCode.VALIDATOR_INCOMPLETE, relative_path) from exc
    self.total_size += len(payload)
    if self.total_size > MAX_TOTAL_ARTIFACT_BYTES:
      raise WorkspaceError(
          "workspace exceeds total retained artifact size limit "
          f"({MAX_TOTAL_ARTIFACT_BYTES} bytes)")
    self.payloads[relative_path] = payload
    return payload

  def required(self, relative_path: str) -> bytes:
    payload = self.optional(relative_path)
    if payload is None:
      raise WorkspaceError(
          f"required artifact is missing: {relative_path}",
          ReasonCode.ARTIFACT_MISSING, relative_path)
    return payload


def _sanitize_id(identifier: str) -> str:
  safe = re.sub(r"[^A-Za-z0-9._-]", "_", identifier)
  return re.sub(r"^\.+", "_", safe) or "_"


def _trusted_ids(record: dict[str, object], index: int) -> set[str]:
  ids_value = record.get("ids")
  ids = {} if ids_value is None else ids_value
  if type(ids) is not dict:
    raise WorkspaceError(f"corpus record {index} ids must be an object")
  values = [record.get("key"), *ids.values()]
  derived = set()
  for value in values:
    if value is None or value == "":
      continue
    if not isinstance(value, (str, int)) or isinstance(value, bool):
      raise WorkspaceError(
          f"corpus record {index} contains an invalid trusted identifier")
    normalized = str(value).removeprefix("https://doi.org/")
    derived.add(_sanitize_id(normalized))
  if not derived:
    raise WorkspaceError(
        f"corpus record {index} has no trusted identifier")
  return derived


def _relevant_records(corpus: object) -> list[tuple[int, dict[str, object]]]:
  if not isinstance(corpus, list):
    raise WorkspaceError("corpus.json must be a JSON array")
  result = []
  for index, record in enumerate(corpus):
    if not isinstance(record, dict):
      raise WorkspaceError(f"corpus record {index} must be an object")
    screening_value = record.get("screening")
    screening = {} if screening_value is None else screening_value
    if type(screening) is not dict:
      raise WorkspaceError(
          f"corpus record {index} screening must be an object")
    if (screening.get("status") == "included"
        and record.get("role") in _EVIDENCE_ROLES):
      result.append((index, record))
  return result


def _records_with_unique_ids(
    corpus: object,
) -> list[tuple[int, dict[str, object], set[str]]]:
  result = []
  seen: set[str] = set()
  for index, record in _relevant_records(corpus):
    identifiers = _trusted_ids(record, index)
    duplicate = seen & identifiers
    if duplicate:
      raise WorkspaceError(
          f"duplicate derived paper identifier: {sorted(duplicate)!r}")
    seen.update(identifiers)
    result.append((index, record, identifiers))
  return result


def _discover_sources(reader: _SnapshotReader, corpus: object) -> dict[str, bool]:
  sources: dict[str, bool] = {}
  selected_ids: set[str] = set()
  for index, _record, candidates in _records_with_unique_ids(corpus):
    found: dict[str, list[str]] = {}
    for identifier in candidates:
      paths = []
      for filename in _SOURCE_FILENAMES:
        relative_path = f"papers/{identifier}/{filename}"
        if reader.optional(relative_path) is not None:
          paths.append(relative_path)
      if paths:
        found[identifier] = paths
    if not found:
      raise WorkspaceError(
          f"included corpus record {index} is missing a source artifact")
    if len(found) != 1:
      raise WorkspaceError(
          f"included corpus record {index} has ambiguous source identifiers")
    identifier, paths = next(iter(found.items()))
    if identifier in selected_ids:
      raise WorkspaceError(f"duplicate derived paper identifier: {identifier}")
    selected_ids.add(identifier)
    preferred = (f"papers/{identifier}/fulltext.md"
                 if any(path.endswith("/fulltext.md") for path in paths)
                 else paths[0])
    for relative_path in paths:
      sources[relative_path] = relative_path == preferred
  return sources


def _manifest_sources(paths: set[str]) -> set[str]:
  sources = set()
  for relative_path in paths:
    if relative_path in _FIXED_ARTIFACTS:
      continue
    path = pathlib.PurePosixPath(relative_path)
    if (len(path.parts) != 3 or path.parts[0] != "papers"
        or not path.parts[1] or path.parts[2] not in _SOURCE_FILENAMES):
      raise WorkspaceError(
          f"run manifest names an artifact outside the allowed contract: "
          f"{relative_path}")
    sources.add(relative_path)
  return sources


def _load_run_manifest(
    reader: _SnapshotReader, payload: bytes,
) -> dict[str, bool]:
  value = _decode_json(payload, "run-manifest.json")
  if type(value) is not dict or set(value) != {"schema_version", "artifacts"}:
    raise WorkspaceError(
        "run-manifest.json must contain exactly schema_version and artifacts")
  if value["schema_version"] != SCHEMA_VERSION:
    raise WorkspaceError(
        f"run-manifest.json has unsupported schema_version: "
        f"{value['schema_version']!r}")
  artifacts = value["artifacts"]
  if type(artifacts) is not list:
    raise WorkspaceError("run-manifest.json artifacts must be a list")
  paths = [_canonical_relative_path(item) for item in artifacts]
  if len(paths) != len(set(paths)):
    raise WorkspaceError("run-manifest.json contains duplicate artifact paths")
  submitted = set(paths)
  missing = _FIXED_ARTIFACTS - submitted
  if missing:
    raise WorkspaceError(
        f"run manifest is missing required artifacts: {sorted(missing)!r}")
  declared_sources = _manifest_sources(submitted)
  for relative_path in paths:
    reader.required(relative_path)
  corpus = _decode_json(reader.required("corpus.json"), "corpus.json")
  expected_sources = _sources_from_manifest(corpus, declared_sources)
  if declared_sources != set(expected_sources):
    extras = declared_sources - set(expected_sources)
    missing_sources = set(expected_sources) - declared_sources
    raise WorkspaceError(
        "run manifest source contract mismatch; "
        f"missing={sorted(missing_sources)!r}, extra={sorted(extras)!r}")
  return expected_sources


def _sources_from_manifest(
    corpus: object, declared_sources: set[str],
) -> dict[str, bool]:
  result: dict[str, bool] = {}
  selected_ids: set[str] = set()
  for index, _record, candidates in _records_with_unique_ids(corpus):
    found: dict[str, list[str]] = {}
    for identifier in candidates:
      paths = [
          f"papers/{identifier}/{filename}" for filename in _SOURCE_FILENAMES
          if f"papers/{identifier}/{filename}" in declared_sources
      ]
      if paths:
        found[identifier] = paths
    if not found:
      raise WorkspaceError(
          f"run manifest is missing a source for corpus record {index}")
    if len(found) != 1:
      raise WorkspaceError(
          f"corpus record {index} has ambiguous manifest source identifiers")
    identifier, paths = next(iter(found.items()))
    if identifier in selected_ids:
      raise WorkspaceError(f"duplicate derived paper identifier: {identifier}")
    selected_ids.add(identifier)
    preferred = (f"papers/{identifier}/fulltext.md"
                 if any(path.endswith("/fulltext.md") for path in paths)
                 else paths[0])
    for path in paths:
      result[path] = path == preferred
  return result


def _artifacts(
    payloads: dict[str, bytes], preferred_sources: dict[str, bool],
) -> tuple[Artifact, ...]:
  ordered_paths = sorted(payloads, key=lambda value: value.encode("utf-8"))
  return tuple(Artifact(
      relative_path=relative_path,
      payload=payloads[relative_path],
      sha256=hashlib.sha256(payloads[relative_path]).hexdigest(),
      preferred_for_claims=preferred_sources.get(relative_path, False),
      _loader_token=_LOADER_TOKEN,
  ) for relative_path in ordered_paths)


def load_workspace(root: pathlib.Path) -> WorkspaceSnapshot:
  """Securely load, retain, order, and hash one review workspace."""
  root_descriptor = _open_root(root)
  try:
    reader = _SnapshotReader(root_descriptor)
    project_payload = reader.optional("project.json")
    run_manifest_payload = reader.optional("run-manifest.json")
    if project_payload is not None and run_manifest_payload is not None:
      raise WorkspaceError(
          "workspace has both project.json and run-manifest.json; "
          "the project link is ambiguous",
          ReasonCode.ARTIFACT_MALFORMED, "project.json")
    if project_payload is None and run_manifest_payload is None:
      raise WorkspaceError(
          "workspace requires exactly one of project.json or run-manifest.json",
          ReasonCode.ARTIFACT_MISSING, "project.json")

    if run_manifest_payload is not None:
      with _artifact_context("run-manifest.json"):
        preferred_sources = _load_run_manifest(reader, run_manifest_payload)
    else:
      assert project_payload is not None
      with _artifact_context("project.json"):
        project = _decode_json(project_payload, "project.json")
        if type(project) is not dict or not project:
          raise WorkspaceError("project.json must be a nonempty JSON object")
      for relative_path in _FIXED_ARTIFACTS:
        reader.required(relative_path)
      with _artifact_context("corpus.json"):
        corpus = _decode_json(reader.required("corpus.json"), "corpus.json")
        preferred_sources = _discover_sources(reader, corpus)
    return WorkspaceSnapshot(
        files=_artifacts(reader.payloads, preferred_sources),
        canonicalization=CANONICALIZATION,
        _loader_token=_LOADER_TOKEN,
    )
  finally:
    try:
      os.close(root_descriptor)
    except Exception as exc:
      raise WorkspaceError(
          f"cannot close workspace root descriptor: {exc}") from exc
