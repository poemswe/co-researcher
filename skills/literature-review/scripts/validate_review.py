#!/usr/bin/env python3
"""Deterministic offline one-pass validation for a literature-review workspace."""

from __future__ import annotations

import argparse
import errno
import hashlib
import os
import pathlib
import re
import stat
import subprocess
import sys
from typing import Optional


# Absolute-path invocation must work without installing the local scripts.
_SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(_SCRIPT_DIR))

import verify_citations  # noqa: E402
from review_integrity.models import PassReport  # noqa: E402
from review_integrity.reporting import (  # noqa: E402
    ENGINE_VERSION,
    SCHEMA_VERSION,
    VALIDATOR_VERSIONS,
    combined_manifest_sha256,
    render_json,
    render_markdown,
    validate_report,
)
from review_integrity.scoring import score_integrity  # noqa: E402
from review_integrity.validators import validate_snapshot  # noqa: E402
from review_integrity.workspace import (  # noqa: E402
    MAX_ARTIFACT_BYTES,
    WorkspaceError,
    decode_json_bytes,
    load_workspace,
)


_READ_SIZE = 1024 * 1024
_COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")


class ValidationInputError(ValueError):
  """Validation could not safely retain or interpret its explicit input."""


class _ValidationArgumentParser(argparse.ArgumentParser):
  def error(self, message):
    self.print_usage(sys.stderr)
    self.exit(2, f"{self.prog}: error: {message}; result is not validated\n")


def _secure_flags(*, directory: bool) -> int:
  nofollow = getattr(os, "O_NOFOLLOW", 0)
  directory_flag = getattr(os, "O_DIRECTORY", 0)
  nonblock = getattr(os, "O_NONBLOCK", 0)
  if not nofollow or not directory_flag or not nonblock:
    raise ValidationInputError(
        "secure file access requires O_NOFOLLOW, O_DIRECTORY, and O_NONBLOCK")
  flags = os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0)
  return flags | directory_flag if directory else flags | nonblock


def _text_absolute_path(path: os.PathLike[str] | str, label: str) -> pathlib.Path:
  raw = os.fspath(path)
  if type(raw) is not str or not raw:
    raise ValidationInputError(f"{label} must be a nonempty text path")
  return pathlib.Path(os.path.abspath(raw))


def _open_directory(path: pathlib.Path, label: str) -> int:
  """Open every absolute directory component without following symlinks."""
  current = -1
  try:
    current = os.open(os.path.sep, _secure_flags(directory=True))
    for component in path.parts[1:]:
      child = os.open(component, _secure_flags(directory=True), dir_fd=current)
      metadata = os.fstat(child)
      if not stat.S_ISDIR(metadata.st_mode):
        os.close(child)
        raise ValidationInputError(f"{label} parent is not a directory")
      os.close(current)
      current = child
    return current
  except ValidationInputError:
    if current >= 0:
      os.close(current)
    raise
  except Exception as exc:
    if current >= 0:
      os.close(current)
    raise ValidationInputError(
        f"cannot securely traverse {label} (symlinks are forbidden): {exc}"
    ) from exc


def _read_regular_bytes(path: os.PathLike[str] | str, label: str) -> bytes:
  absolute = _text_absolute_path(path, label)
  if absolute.name in {"", ".", ".."}:
    raise ValidationInputError(f"{label} must name a regular file")
  parent = _open_directory(absolute.parent, label)
  descriptor = -1
  try:
    descriptor = os.open(
        absolute.name, _secure_flags(directory=False), dir_fd=parent)
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
      raise ValidationInputError(f"{label} is not a regular file")
    if metadata.st_size < 0 or metadata.st_size > MAX_ARTIFACT_BYTES:
      raise ValidationInputError(
          f"{label} exceeds size limit ({MAX_ARTIFACT_BYTES} bytes)")
    chunks: list[bytes] = []
    retained = 0
    while True:
      allowance = MAX_ARTIFACT_BYTES + 1 - retained
      if allowance <= 0:
        raise ValidationInputError(
            f"{label} exceeds size limit ({MAX_ARTIFACT_BYTES} bytes)")
      chunk = os.read(descriptor, min(_READ_SIZE, allowance))
      if not chunk:
        break
      retained += len(chunk)
      if retained > MAX_ARTIFACT_BYTES:
        raise ValidationInputError(
            f"{label} exceeds size limit ({MAX_ARTIFACT_BYTES} bytes)")
      chunks.append(chunk)
    return b"".join(chunks)
  except ValidationInputError:
    raise
  except Exception as exc:
    raise ValidationInputError(
        f"cannot securely read {label} (symlinks are forbidden): {exc}") from exc
  finally:
    if descriptor >= 0:
      os.close(descriptor)
    os.close(parent)


def _git_provenance(workspace: pathlib.Path) -> tuple[Optional[str], Optional[bool]]:
  environment = dict(os.environ)
  environment.update({"GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
  common = {
      "cwd": workspace, "env": environment, "capture_output": True,
      "text": True, "check": False, "timeout": 5,
  }
  try:
    commit_result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"], **common)
    if commit_result.returncode != 0:
      return None, None
    commit = commit_result.stdout.strip()
    if not _COMMIT_RE.fullmatch(commit):
      return None, None
    status_result = subprocess.run([
        "git", "status", "--porcelain=v1", "--untracked-files=no",
        "--ignored=no",
    ], **common)
    if status_result.returncode != 0:
      return None, None
    return commit, bool(status_result.stdout)
  except (OSError, subprocess.SubprocessError):
    return None, None


def _citation_resolution(
    report: object, *, supplied: bool, bibliography: object,
) -> dict[str, object]:
  if not supplied:
    response = "not_applicable" if bibliography == [] else "unavailable"
    return {
        "source": "not_supplied", "resolver": None, "checked_at": None,
        "response_status": response,
    }
  if not isinstance(report, dict):
    return {
        "source": "supplied_report", "resolver": None, "checked_at": None,
        "response_status": "malformed",
    }
  resolver = report.get("resolver")
  checked_at = report.get("checked_at")
  response_status = report.get("response_status")
  if (not isinstance(resolver, str) or not resolver
      or not isinstance(checked_at, str) or not checked_at
      or response_status not in {"complete", "partial", "unavailable"}):
    return {
        "source": "supplied_report",
        "resolver": resolver if isinstance(resolver, str) else None,
        "checked_at": checked_at if isinstance(checked_at, str) else None,
        "response_status": "malformed",
    }
  return {
      "source": "supplied_report", "resolver": resolver,
      "checked_at": checked_at, "response_status": response_status,
  }


def run_validation(
    workspace: os.PathLike[str] | str,
    citation_report: os.PathLike[str] | str | None,
) -> tuple[dict, str]:
  """Retain all inputs once, execute offline validators, and build a report."""
  citation_payload = None
  parsed_citation_report = None
  if citation_report is not None:
    citation_payload = _read_regular_bytes(citation_report, "citation report")
    try:
      parsed_citation_report = decode_json_bytes(
          citation_payload, "citation report")
    except WorkspaceError as exc:
      raise ValidationInputError(str(exc)) from exc

  workspace_path = _text_absolute_path(workspace, "workspace")
  try:
    snapshot = load_workspace(workspace_path)
  except WorkspaceError as exc:
    raise ValidationInputError(str(exc)) from exc

  findings = validate_snapshot(snapshot, parsed_citation_report)
  scored = score_integrity(snapshot, findings)
  citation_hash = (None if citation_payload is None else
                   hashlib.sha256(citation_payload).hexdigest())
  combined_hash = combined_manifest_sha256(
      snapshot.manifest_sha256, citation_hash)
  # Keep WorkspaceSnapshot immutable: reconstruct the strict score model with
  # the complete validation-input hash after dimensions/findings are computed.
  combined_pass = PassReport(
      integrity_score=scored.unrounded_integrity_score,
      findings=scored.findings,
      dimensions=scored.dimensions,
      manifest_sha256=combined_hash,
  )
  combined_pass = PassReport.from_dict(combined_pass.to_dict())
  pass_wire = combined_pass.to_dict()
  try:
    bibliography = snapshot.read_json("refs.json")
  except WorkspaceError:
    bibliography = None
  target_commit, target_dirty = _git_provenance(workspace_path)
  report = {
      "schema_version": SCHEMA_VERSION,
      "engine_version": ENGINE_VERSION,
      "quality_score": None,
      "target_commit": target_commit,
      "target_dirty": target_dirty,
      "validator_versions": dict(VALIDATOR_VERSIONS),
      "manifest_sha256": combined_hash,
      "workspace_manifest_sha256": snapshot.manifest_sha256,
      "citation_report_sha256": citation_hash,
      "dimensions": pass_wire["dimensions"],
      "findings": pass_wire["findings"],
      "integrity_score": pass_wire["integrity_score"],
      "status": pass_wire["status"],
      "citation_resolution": _citation_resolution(
          parsed_citation_report, supplied=citation_payload is not None,
          bibliography=bibliography),
  }
  validate_report(report)
  return report, snapshot.read_text("synthesis.md")


class _OutputDestination:
  def __init__(self, parent_descriptor: int, name: str, suffix: str):
    self.parent_descriptor = parent_descriptor
    self.name = name
    self.suffix = suffix

  def close(self) -> None:
    if self.parent_descriptor >= 0:
      os.close(self.parent_descriptor)
      self.parent_descriptor = -1


def _prepare_output(
    output: os.PathLike[str] | str,
    workspace: os.PathLike[str] | str,
) -> _OutputDestination:
  absolute = _text_absolute_path(output, "output path")
  suffix = absolute.suffix
  if suffix not in {".json", ".md"}:
    raise ValidationInputError("output suffix must be .json or .md")
  workspace_absolute = _text_absolute_path(workspace, "workspace")
  try:
    common = os.path.commonpath((absolute, workspace_absolute))
  except ValueError as exc:
    raise ValidationInputError("cannot compare output and workspace paths") from exc
  if common == os.fspath(workspace_absolute):
    raise ValidationInputError(
        "output must be outside the submitted workspace")
  parent = _open_directory(absolute.parent, "output path")
  try:
    try:
      os.stat(absolute.name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
      pass
    else:
      raise ValidationInputError("output already exists; refusing to overwrite")
    return _OutputDestination(parent, absolute.name, suffix)
  except Exception:
    os.close(parent)
    raise


def _write_output(destination: _OutputDestination, payload: bytes) -> None:
  temp_name = None
  descriptor = -1
  flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL
           | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
  try:
    for attempt in range(100):
      candidate = f".{destination.name}.tmp.{os.getpid()}.{attempt}"
      try:
        descriptor = os.open(
            candidate, flags, 0o600, dir_fd=destination.parent_descriptor)
      except FileExistsError:
        continue
      temp_name = candidate
      break
    if descriptor < 0 or temp_name is None:
      raise ValidationInputError("cannot reserve an exclusive output file")
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
      raise ValidationInputError("temporary output is not a regular file")
    view = memoryview(payload)
    written = 0
    while written < len(view):
      count = os.write(descriptor, view[written:])
      if count <= 0:
        raise ValidationInputError("could not write complete output")
      written += count
    os.fsync(descriptor)
    os.close(descriptor)
    descriptor = -1
    try:
      os.link(
          temp_name, destination.name,
          src_dir_fd=destination.parent_descriptor,
          dst_dir_fd=destination.parent_descriptor,
          follow_symlinks=False)
    except FileExistsError as exc:
      raise ValidationInputError(
          "output appeared during validation; refusing to overwrite") from exc
    os.unlink(temp_name, dir_fd=destination.parent_descriptor)
    temp_name = None
    os.fsync(destination.parent_descriptor)
  except ValidationInputError:
    raise
  except OSError as exc:
    if exc.errno == errno.EEXIST:
      raise ValidationInputError("output exists; refusing to overwrite") from exc
    raise ValidationInputError(f"cannot write output safely: {exc}") from exc
  finally:
    if descriptor >= 0:
      os.close(descriptor)
    if temp_name is not None:
      try:
        os.unlink(temp_name, dir_fd=destination.parent_descriptor)
      except FileNotFoundError:
        pass


def _parser() -> argparse.ArgumentParser:
  parser = _ValidationArgumentParser(
      description="Offline one-pass literature-review integrity validation.")
  parser.add_argument("--workspace", required=True)
  parser.add_argument("--citation-report")
  parser.add_argument("--output")
  return parser


def main(argv=None) -> int:
  args = _parser().parse_args(argv)
  destination = None
  try:
    if args.output is not None:
      destination = _prepare_output(args.output, args.workspace)
    report, synthesis = run_validation(args.workspace, args.citation_report)
    json_output = render_json(report)
    if destination is not None:
      rendered = (json_output if destination.suffix == ".json"
                  else render_markdown(report, synthesis))
      _write_output(destination, rendered.encode("utf-8"))
    sys.stdout.write(json_output)
    status = report["status"]
    print(
        f"{status.upper()}: integrity {report['integrity_score']:.1f}; "
        f"{len(report['findings'])} finding(s)", file=sys.stderr)
    return 1 if status == "invalid" else 0
  except (ValidationInputError, ValueError, OSError) as exc:
    print(f"NOT VALIDATED: {exc}", file=sys.stderr)
    return 2
  finally:
    if destination is not None:
      destination.close()


if __name__ == "__main__":
  sys.exit(main())
