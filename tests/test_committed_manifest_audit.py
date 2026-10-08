import builtins
import hashlib
import importlib
import io
import json
import os
import pathlib
import runpy
import socket
import subprocess
import sys
import tempfile

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

import run_eval  # noqa: E402
from lib import committed_manifest_audit, literature_integrity  # noqa: E402
from lib.committed_manifest_audit import (  # noqa: E402
    ManifestAuditError,
    audit_committed_manifests,
)


def _json_bytes(value):
  return json.dumps(
      value, sort_keys=True, separators=(",", ":"),
      ensure_ascii=False).encode("utf-8")


def _write_case_set(root, case_ids=("case-002", "case-001")):
  root.mkdir()
  entries = []
  for case_id in case_ids:
    manifest_path = f"manifests/{case_id}.json"
    payload = _json_bytes({
        "schema_version": "1.0.0",
        "case_id": case_id,
        "public_inputs": [{
            "input_id": "review-input",
            "path": f"inputs/{case_id}.tar",
            "size": 123,
            "sha256": hashlib.sha256(case_id.encode()).hexdigest(),
        }],
    })
    destination = root / manifest_path
    destination.parent.mkdir(exist_ok=True)
    destination.write_bytes(payload)
    public_input = root / f"inputs/{case_id}.tar"
    public_input.parent.mkdir(exist_ok=True)
    public_input.write_bytes(b"x" * 123)
    entries.append({
        "case_id": case_id,
        "manifest_path": manifest_path,
        "manifest_sha256": hashlib.sha256(payload).hexdigest(),
    })
  index_payload = _json_bytes({"schema_version": "1.0.0", "cases": entries})
  (root / "commitment-index.json").write_bytes(index_payload)
  return index_payload


def test_audit_is_deterministic_and_reads_only_index_and_listed_manifests(
    tmp_path, monkeypatch,
):
  case_root = tmp_path / "runtime-supplied"
  index_payload = _write_case_set(case_root)
  (case_root / "annotations.json").write_text(
      '{"case-001":"secret label"}', encoding="utf-8")
  (case_root / "gold.json").write_text(
      '{"expected_status":"invalid"}', encoding="utf-8")

  real_open = os.open
  real_fstat = os.fstat
  real_read = os.read
  opened = []
  descriptor_names = {}
  descriptor_operations = []

  def recording_open(path, flags, mode=0o777, *, dir_fd=None):
    rendered = os.fspath(path)
    opened.append(rendered)
    if rendered in {"annotations.json", "gold.json"}:
      raise AssertionError(f"trap file touched: {rendered}")
    descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
    descriptor_names[descriptor] = rendered
    return descriptor

  def recording_fstat(descriptor):
    descriptor_operations.append(("fstat", descriptor_names[descriptor]))
    return real_fstat(descriptor)

  def recording_read(descriptor, size):
    descriptor_operations.append(("read", descriptor_names[descriptor]))
    return real_read(descriptor, size)

  monkeypatch.setattr(os, "open", recording_open)
  monkeypatch.setattr(os, "fstat", recording_fstat)
  monkeypatch.setattr(os, "read", recording_read)
  audit = audit_committed_manifests(case_root)

  assert audit == {
      "schema_version": "1.0.0",
      "index_sha256": hashlib.sha256(index_payload).hexdigest(),
      "case_count": 2,
      "public_input_count": 2,
      "cases": [
          {
              "case_id": "case-001",
              "manifest_sha256": next(
                  entry["manifest_sha256"]
                  for entry in json.loads(index_payload)["cases"]
                  if entry["case_id"] == "case-001"),
              "public_input_count": 1,
          },
          {
              "case_id": "case-002",
              "manifest_sha256": next(
                  entry["manifest_sha256"]
                  for entry in json.loads(index_payload)["cases"]
                  if entry["case_id"] == "case-002"),
              "public_input_count": 1,
          },
      ],
  }
  assert not any("annotation" in path or "gold" in path for path in opened)
  assert not any(
      "annotation" in path or "gold" in path
      for _, path in descriptor_operations)
  assert [
      path for operation, path in descriptor_operations
      if operation == "read"
  ] == [
      "commitment-index.json", "commitment-index.json",
      "case-002.json", "case-002.json",
      "case-001.json", "case-001.json",
      "commitment-index.json", "commitment-index.json",
      "case-002.json", "case-002.json",
      "case-001.json", "case-001.json",
  ]
  assert not any(path.endswith(".tar") for path in opened)
  assert "path" not in json.dumps(audit)


def test_cli_dry_run_never_constructs_execution_or_network_dependencies(
    tmp_path, monkeypatch, capsys,
):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001",))

  def forbidden(*args, **kwargs):
    raise AssertionError("execution dependency constructed")

  monkeypatch.setattr(literature_integrity, "LiteratureIntegrityRunner", forbidden)
  monkeypatch.setattr(literature_integrity, "ProductionModelExecutor", forbidden)
  monkeypatch.setattr(literature_integrity, "ProductionQualityJudge", forbidden)
  monkeypatch.setattr(literature_integrity, "load_cases", forbidden)
  monkeypatch.setattr(literature_integrity, "load_adversarial_scores", forbidden)
  monkeypatch.setattr(run_eval, "run_literature_integrity", forbidden)
  monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path / "results")
  workspace = importlib.import_module("review_integrity.workspace")
  monkeypatch.setattr(workspace, "load_workspace", forbidden)
  before = set(tmp_path.rglob("*"))

  real_import = builtins.__import__
  real_import_module = importlib.import_module
  real_os_open = os.open
  protected_roots = (
      os.path.abspath(case_root), os.path.abspath(tmp_path / "results"))

  def is_execution_namespace(name, fromlist=()):
    candidates = {name}
    if fromlist:
      candidates.update(
          f"{name}.{item}" for item in fromlist
          if isinstance(item, str) and item != "*")
    return any(
        candidate == "lib.literature_integrity"
        or candidate.startswith("lib.literature_integrity.")
        or candidate == "review_integrity"
        or candidate.startswith("review_integrity.")
        for candidate in candidates)

  def guarded_import(
      name, globals=None, locals=None, fromlist=(), level=0,
  ):
    if is_execution_namespace(name, fromlist):
      raise AssertionError(f"execution module imported: {name}")
    return real_import(name, globals, locals, fromlist, level)

  def guarded_import_module(name, *args, **kwargs):
    if is_execution_namespace(name):
      raise AssertionError(f"execution module imported: {name}")
    return real_import_module(name, *args, **kwargs)

  def guarded_descriptor_open(path, flags, mode=0o777, *, dir_fd=None):
    write_flags = (
        os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_TRUNC)
    temporary_flag = getattr(os, "O_TMPFILE", 0)
    if (
        flags & write_flags
        or temporary_flag and flags & temporary_flag == temporary_flag
    ):
      raise AssertionError("execution dependency constructed")
    return real_os_open(path, flags, mode, dir_fd=dir_fd)

  def guarded_stream_open(real_operation):
    def guarded(path, mode="r", *args, **kwargs):
      if any(marker in mode for marker in "wax+"):
        raise AssertionError("execution dependency constructed")
      return guarded_path_call(real_operation)(path, mode, *args, **kwargs)
    return guarded

  transient_workspace = tmp_path / "arbitrary-transient-workspace"

  def create_then_remove_transient_workspace():
    os.mkdir(transient_workspace)
    os.rmdir(transient_workspace)

  def guarded_path_call(real_operation):
    def guarded(path, *args, **kwargs):
      if isinstance(path, (str, bytes, os.PathLike)):
        rendered = os.path.abspath(os.fsdecode(os.fspath(path)))
        if any(
            rendered == root or rendered.startswith(root + os.sep)
            for root in protected_roots
        ):
          raise AssertionError(f"path API touched protected root: {rendered}")
      return real_operation(path, *args, **kwargs)
    return guarded

  with monkeypatch.context() as isolation:
    for module_name in tuple(sys.modules):
      if is_execution_namespace(module_name):
        isolation.delitem(sys.modules, module_name)
    lib_package = sys.modules.get("lib")
    if lib_package is not None and hasattr(lib_package, "literature_integrity"):
      isolation.delattr(lib_package, "literature_integrity")
    review_package = sys.modules.get("review_integrity")
    if review_package is not None and hasattr(review_package, "workspace"):
      isolation.delattr(review_package, "workspace")

    isolation.setattr(builtins, "open", guarded_stream_open(builtins.open))
    isolation.setattr(builtins, "__import__", guarded_import)
    isolation.setattr(importlib, "import_module", guarded_import_module)
    isolation.setattr(importlib.util, "spec_from_file_location", forbidden)
    isolation.setattr(io, "open", guarded_stream_open(io.open))
    isolation.setattr(os, "open", guarded_descriptor_open)
    isolation.setattr(socket, "socket", forbidden)
    isolation.setattr(os, "stat", guarded_path_call(os.stat))
    isolation.setattr(os, "lstat", guarded_path_call(os.lstat))
    isolation.setattr(os, "listdir", guarded_path_call(os.listdir))
    isolation.setattr(os, "scandir", guarded_path_call(os.scandir))
    isolation.setattr(os, "walk", guarded_path_call(os.walk))
    isolation.setattr(os, "mkdir", forbidden)
    isolation.setattr(os, "makedirs", forbidden)
    isolation.setattr(pathlib.Path, "mkdir", forbidden)
    isolation.setattr(subprocess, "Popen", forbidden)
    isolation.setattr(subprocess, "run", forbidden)
    isolation.setattr(subprocess, "check_output", forbidden)
    isolation.setattr(tempfile, "mkdtemp", forbidden)
    isolation.setattr(tempfile, "mkstemp", forbidden)
    isolation.setattr(tempfile, "NamedTemporaryFile", forbidden)
    isolation.setattr(tempfile, "TemporaryDirectory", forbidden)
    isolation.setattr(runpy, "run_module", forbidden)
    isolation.setattr(runpy, "run_path", forbidden)

    with pytest.raises(AssertionError, match="execution module imported"):
      importlib.import_module("lib.literature_integrity")
    with pytest.raises(AssertionError, match="execution module imported"):
      exec("from lib import literature_integrity", {})
    with pytest.raises(AssertionError, match="execution module imported"):
      exec("from review_integrity import workspace", {})
    assert not hasattr(importlib.import_module("lib"), "literature_integrity")
    with pytest.raises(AssertionError, match="execution dependency"):
      tempfile.mkdtemp(dir=case_root)
    with pytest.raises(AssertionError, match="execution dependency"):
      create_then_remove_transient_workspace()
    with pytest.raises(AssertionError, match="execution dependency"):
      os.makedirs(tmp_path.parent / "arbitrary-nested-workspace")

    assert run_eval.main([
        "literature-review-integrity",
        "--official-cases-dir", str(case_root),
        "--dry-run-manifest-audit",
    ]) == 0

  captured = capsys.readouterr()
  assert json.loads(captured.out)["case_count"] == 1
  assert captured.err == ""
  assert not transient_workspace.exists()
  assert set(tmp_path.rglob("*")) == before


@pytest.mark.parametrize("argv", [
    ["list", "--official-cases-dir", "unused", "--dry-run-manifest-audit"],
    ["all", "--official-cases-dir", "unused", "--dry-run-manifest-audit"],
    ["literature-reviewer", "--official-cases-dir", "unused",
     "--dry-run-manifest-audit"],
    ["literature-review-integrity", "--official-cases-dir", "unused"],
    ["literature-review-integrity", "--dry-run-manifest-audit"],
    ["--dry-run-manifest-audit"],
    ["--check-prompts", "--official-cases-dir", "unused",
     "--dry-run-manifest-audit"],
])
def test_cli_rejects_invalid_audit_combinations_without_partial_stdout(
    argv, capsys,
):
  with pytest.raises(SystemExit) as raised:
    run_eval.main(argv)

  assert raised.value.code != 0
  assert capsys.readouterr().out == ""


@pytest.mark.parametrize("mutation, message", [
    (lambda index, manifest: index.update(extra=True), "exactly"),
    (lambda index, manifest: index["cases"].append(index["cases"][0]),
     "duplicate"),
    (lambda index, manifest: index["cases"].append({
        **index["cases"][0], "case_id": "CASE-001"}), "case_id"),
    (lambda index, manifest: index["cases"][0].update(
        manifest_path="../escape.json"), "path"),
    (lambda index, manifest: manifest.update(expected_status="invalid"),
     "exactly"),
    (lambda index, manifest: manifest["public_inputs"][0].update(size=True),
     "size"),
])
def test_closed_schemas_and_identifiers_fail_closed(
    tmp_path, mutation, message,
):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001",))
  index = json.loads((case_root / "commitment-index.json").read_bytes())
  manifest_path = case_root / index["cases"][0]["manifest_path"]
  manifest = json.loads(manifest_path.read_bytes())
  mutation(index, manifest)
  manifest_payload = _json_bytes(manifest)
  manifest_path.write_bytes(manifest_payload)
  index["cases"][0]["manifest_sha256"] = hashlib.sha256(
      manifest_payload).hexdigest()
  (case_root / "commitment-index.json").write_bytes(_json_bytes(index))

  with pytest.raises(ManifestAuditError, match=message):
    audit_committed_manifests(case_root)


@pytest.mark.parametrize("payload", [
    b'{"schema_version":"1.0.0","schema_version":"1.0.0","cases":[]}',
    b'{"schema_version":"1.0.0","cases":[],"x":NaN}',
])
def test_index_rejects_duplicate_json_keys_and_nonfinite_numbers(
    tmp_path, payload,
):
  case_root = tmp_path / "runtime-supplied"
  case_root.mkdir()
  (case_root / "commitment-index.json").write_bytes(payload)

  with pytest.raises(ManifestAuditError, match="JSON"):
    audit_committed_manifests(case_root)


@pytest.mark.parametrize("payload", [
    b'{"schema_version":"1.0.0","case_id":"case-001",'
    b'"case_id":"case-001","public_inputs":[]}',
    b'{"schema_version":"1.0.0","case_id":"case-001",'
    b'"public_inputs":[{"input_id":"review-input","path":"input.tar",'
    b'"size":NaN,"sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    b'aaaaaaaaaaaaaaaa"}]}',
])
def test_manifest_rejects_duplicate_json_keys_and_nonfinite_numbers(
    tmp_path, payload,
):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001",))
  index_path = case_root / "commitment-index.json"
  index = json.loads(index_path.read_bytes())
  (case_root / "manifests/case-001.json").write_bytes(payload)
  index["cases"][0]["manifest_sha256"] = hashlib.sha256(payload).hexdigest()
  index_path.write_bytes(_json_bytes(index))

  with pytest.raises(ManifestAuditError, match="JSON"):
    audit_committed_manifests(case_root)


def test_casefold_path_aliases_are_rejected_before_second_manifest_open(
    tmp_path, monkeypatch,
):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001", "case-002"))
  index_path = case_root / "commitment-index.json"
  index = json.loads(index_path.read_bytes())
  index["cases"][1]["manifest_path"] = index["cases"][0][
      "manifest_path"].upper()
  index_path.write_bytes(_json_bytes(index))
  real_open = os.open

  def trap_second_alias(path, flags, mode=0o777, *, dir_fd=None):
    if os.fspath(path) == "MANIFESTS":
      raise AssertionError("aliased manifest was opened")
    return real_open(path, flags, mode, dir_fd=dir_fd)

  monkeypatch.setattr(os, "open", trap_second_alias)
  with pytest.raises(ManifestAuditError, match="path aliases"):
    audit_committed_manifests(case_root)


def test_manifest_rejects_non_unicode_scalar_paths(tmp_path):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001",))
  index_path = case_root / "commitment-index.json"
  index = json.loads(index_path.read_bytes())
  manifest_path = case_root / "manifests/case-001.json"
  manifest = json.loads(manifest_path.read_bytes())
  manifest["public_inputs"][0]["path"] = "bad\ud800"
  payload = json.dumps(
      manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
  manifest_path.write_bytes(payload)
  index["cases"][0]["manifest_sha256"] = hashlib.sha256(payload).hexdigest()
  index_path.write_bytes(_json_bytes(index))

  with pytest.raises(ManifestAuditError, match="Unicode"):
    audit_committed_manifests(case_root)


def test_same_size_in_place_mutation_during_read_fails_closed(
    tmp_path, monkeypatch,
):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001",))
  manifest_path = case_root / "manifests/case-001.json"
  original = manifest_path.read_bytes()
  mutated = original.replace(b"review-input", b"review-jnput")
  assert len(mutated) == len(original) and mutated != original

  real_open = os.open
  real_read = os.read
  manifest_descriptor = None
  mutated_once = False

  def recording_open(path, flags, mode=0o777, *, dir_fd=None):
    nonlocal manifest_descriptor
    descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
    if os.fspath(path) == "case-001.json":
      manifest_descriptor = descriptor
    return descriptor

  def mutating_read(descriptor, size):
    nonlocal mutated_once
    payload = real_read(descriptor, size)
    if descriptor == manifest_descriptor and payload and not mutated_once:
      mutated_once = True
      with builtins.open(manifest_path, "r+b") as stream:
        stream.write(mutated)
        stream.flush()
        os.fsync(stream.fileno())
      before = manifest_path.stat()
      os.utime(
          manifest_path,
          ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000),
      )
    return payload

  monkeypatch.setattr(os, "open", recording_open)
  monkeypatch.setattr(os, "read", mutating_read)

  with pytest.raises(ManifestAuditError, match="changed"):
    audit_committed_manifests(case_root)


def test_manifest_path_replacement_after_leaf_open_fails_closed(
    tmp_path, monkeypatch,
):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001",))
  manifest_path = case_root / "manifests/case-001.json"
  original = manifest_path.read_bytes()
  replacement = original.replace(b"review-input", b"review-jnput")
  assert len(replacement) == len(original) and replacement != original
  real_open = os.open
  swapped = False

  def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
    nonlocal swapped
    descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
    if os.fspath(path) == "case-001.json" and not swapped:
      swapped = True
      manifest_path.rename(manifest_path.with_suffix(".old"))
      manifest_path.write_bytes(replacement)
    return descriptor

  monkeypatch.setattr(os, "open", swapping_open)
  with pytest.raises(ManifestAuditError, match="changed"):
    audit_committed_manifests(case_root)


def test_manifest_intermediate_directory_replacement_fails_closed(
    tmp_path, monkeypatch,
):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001",))
  manifests = case_root / "manifests"
  original_manifest = manifests / "case-001.json"
  original_payload = original_manifest.read_bytes()
  real_read = os.read
  replaced = False
  manifest_descriptor = None
  real_open = os.open

  def recording_open(path, flags, mode=0o777, *, dir_fd=None):
    nonlocal manifest_descriptor
    descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
    if os.fspath(path) == "case-001.json" and manifest_descriptor is None:
      manifest_descriptor = descriptor
    return descriptor

  def replacing_read(descriptor, size):
    nonlocal replaced
    payload = real_read(descriptor, size)
    if descriptor == manifest_descriptor and payload and not replaced:
      replaced = True
      manifests.rename(case_root / "detached-manifests")
      manifests.mkdir()
      (manifests / "case-001.json").write_bytes(original_payload)
    return payload

  monkeypatch.setattr(os, "open", recording_open)
  monkeypatch.setattr(os, "read", replacing_read)
  with pytest.raises(ManifestAuditError, match="changed"):
    audit_committed_manifests(case_root)


def test_supplied_root_path_replacement_before_completion_fails_closed(
    tmp_path, monkeypatch,
):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001",))
  detached_root = tmp_path / "detached-root"
  real_read = os.read
  real_open = os.open
  manifest_descriptor = None
  replaced = False

  def recording_open(path, flags, mode=0o777, *, dir_fd=None):
    nonlocal manifest_descriptor
    descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
    if os.fspath(path) == "case-001.json" and manifest_descriptor is None:
      manifest_descriptor = descriptor
    return descriptor

  def replacing_read(descriptor, size):
    nonlocal replaced
    payload = real_read(descriptor, size)
    if descriptor == manifest_descriptor and payload and not replaced:
      replaced = True
      case_root.rename(detached_root)
      case_root.mkdir()
    return payload

  monkeypatch.setattr(os, "open", recording_open)
  monkeypatch.setattr(os, "read", replacing_read)
  with pytest.raises(ManifestAuditError, match="manifest root|changed"):
    audit_committed_manifests(case_root)


def test_earlier_manifest_mutation_before_later_case_traversal_fails_closed(
    tmp_path, monkeypatch,
):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001", "case-002"))
  first_manifest = case_root / "manifests/case-001.json"
  original = first_manifest.read_bytes()
  replacement = original.replace(b"review-input", b"review-jnput")
  assert len(replacement) == len(original) and replacement != original
  real_open = os.open
  mutated = False

  def mutating_before_second_case(path, flags, mode=0o777, *, dir_fd=None):
    nonlocal mutated
    if os.fspath(path) == "case-002.json" and not mutated:
      mutated = True
      with builtins.open(first_manifest, "r+b") as stream:
        stream.write(replacement)
        stream.flush()
        os.fsync(stream.fileno())
      metadata = first_manifest.stat()
      os.utime(
          first_manifest,
          ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 1_000_000_000),
      )
    return real_open(path, flags, mode, dir_fd=dir_fd)

  monkeypatch.setattr(os, "open", mutating_before_second_case)
  with pytest.raises(ManifestAuditError, match="changed|digest"):
    audit_committed_manifests(case_root)


def test_multi_manifest_directory_replacement_before_later_case_fails_closed(
    tmp_path, monkeypatch,
):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001", "case-002"))
  manifests = case_root / "manifests"
  payloads = {
      path.name: path.read_bytes() for path in manifests.iterdir()}
  real_open = os.open
  replaced = False

  def replacing_before_second_case(path, flags, mode=0o777, *, dir_fd=None):
    nonlocal replaced
    if os.fspath(path) == "case-002.json" and not replaced:
      replaced = True
      manifests.rename(case_root / "detached-manifests")
      manifests.mkdir()
      for name, payload in payloads.items():
        (manifests / name).write_bytes(payload)
    return real_open(path, flags, mode, dir_fd=dir_fd)

  monkeypatch.setattr(os, "open", replacing_before_second_case)
  with pytest.raises(ManifestAuditError, match="changed|manifest root"):
    audit_committed_manifests(case_root)


@pytest.mark.parametrize("failure_call, append_before_failure", [
    (1, False), (2, False), (1, True), (2, True),
])
def test_witness_registration_failure_closes_every_descriptor_once(
    tmp_path, monkeypatch, failure_call, append_before_failure,
):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001",))
  real_open = os.open
  real_close = os.close
  opened = []
  closed = []
  registrations = 0

  def recording_open(path, flags, mode=0o777, *, dir_fd=None):
    descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
    opened.append(descriptor)
    return descriptor

  def recording_close(descriptor):
    closed.append(descriptor)
    return real_close(descriptor)

  def failing_append(collection, witness):
    nonlocal registrations
    registrations += 1
    if registrations == failure_call:
      if append_before_failure:
        collection.append(witness)
      raise MemoryError("synthetic witness registration failure")
    collection.append(witness)

  monkeypatch.setattr(os, "open", recording_open)
  monkeypatch.setattr(os, "close", recording_close)
  monkeypatch.setattr(
      committed_manifest_audit, "_append_witness", failing_append)

  with pytest.raises(ManifestAuditError, match="manifest root"):
    audit_committed_manifests(case_root)

  assert sorted(opened) == sorted(closed)
  assert len(opened) == len(closed)


@pytest.mark.parametrize("failure_call", [1, 2])
def test_registration_cleanup_is_allocation_free_and_preserves_original_abort(
    tmp_path, monkeypatch, failure_call,
):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001",))
  real_open = os.open
  real_close = os.close
  real_close_helper = committed_manifest_audit._close
  opened = []
  closed = []
  registrations = 0

  def recording_open(path, flags, mode=0o777, *, dir_fd=None):
    descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
    opened.append(descriptor)
    return descriptor

  def recording_close(descriptor):
    closed.append(descriptor)
    return real_close(descriptor)

  def append_then_abort(collection, witness):
    nonlocal registrations
    registrations += 1
    if registrations == failure_call:
      collection.append(witness)
      raise MemoryError("original registration allocation failure")
    collection.append(witness)

  def allocation_sensitive_close(descriptors, context):
    if context.startswith("unregistered") and isinstance(descriptors, list):
      raise MemoryError("nested cleanup allocation failure")
    result = real_close_helper(descriptors, context)
    if context.startswith("unregistered"):
      raise RuntimeError("synthetic post-close cleanup failure")
    return result

  monkeypatch.setattr(os, "open", recording_open)
  monkeypatch.setattr(os, "close", recording_close)
  monkeypatch.setattr(
      committed_manifest_audit, "_append_witness", append_then_abort)
  monkeypatch.setattr(
      committed_manifest_audit, "_close", allocation_sensitive_close)

  with pytest.raises(ManifestAuditError) as raised:
    audit_committed_manifests(case_root)

  assert isinstance(raised.value.__cause__, MemoryError)
  assert str(raised.value.__cause__) == (
      "original registration allocation failure")
  assert sorted(opened) == sorted(closed)
  assert len(opened) == len(closed)


def test_successful_audit_closes_every_descriptor_once(tmp_path, monkeypatch):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001", "case-002"))
  real_open = os.open
  real_close = os.close
  opened = []
  closed = []

  def recording_open(path, flags, mode=0o777, *, dir_fd=None):
    descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
    opened.append(descriptor)
    return descriptor

  def recording_close(descriptor):
    closed.append(descriptor)
    return real_close(descriptor)

  monkeypatch.setattr(os, "open", recording_open)
  monkeypatch.setattr(os, "close", recording_close)

  assert audit_committed_manifests(case_root)["case_count"] == 2
  assert sorted(opened) == sorted(closed)
  assert len(opened) == len(closed)


def test_symlinked_root_ancestor_and_final_root_fail_closed(tmp_path):
  real_parent = tmp_path / "real-parent"
  case_root = real_parent / "runtime-supplied"
  real_parent.mkdir()
  _write_case_set(case_root, ("case-001",))
  linked_parent = tmp_path / "linked-parent"
  linked_parent.symlink_to(real_parent, target_is_directory=True)
  linked_root = tmp_path / "linked-root"
  linked_root.symlink_to(case_root, target_is_directory=True)

  with pytest.raises(ManifestAuditError, match="manifest root"):
    audit_committed_manifests(linked_parent / "runtime-supplied")
  with pytest.raises(ManifestAuditError, match="manifest root"):
    audit_committed_manifests(linked_root)


def test_public_input_paths_require_nfc_and_allow_canonical_unicode(tmp_path):
  case_root = tmp_path / "runtime-supplied"
  _write_case_set(case_root, ("case-001",))
  index_path = case_root / "commitment-index.json"
  index = json.loads(index_path.read_bytes())
  manifest_path = case_root / "manifests/case-001.json"
  manifest = json.loads(manifest_path.read_bytes())
  manifest["public_inputs"] = [
      {
          "input_id": "review-one",
          "path": "inputs/caf\u00e9.tar",
          "size": 1,
          "sha256": "a" * 64,
      },
      {
          "input_id": "review-two",
          "path": "inputs/cafe\u0301.tar",
          "size": 1,
          "sha256": "b" * 64,
      },
  ]
  payload = _json_bytes(manifest)
  manifest_path.write_bytes(payload)
  index["cases"][0]["manifest_sha256"] = hashlib.sha256(payload).hexdigest()
  index_path.write_bytes(_json_bytes(index))

  with pytest.raises(ManifestAuditError, match="NFC|alias"):
    audit_committed_manifests(case_root)

  manifest["public_inputs"] = manifest["public_inputs"][:1]
  payload = _json_bytes(manifest)
  manifest_path.write_bytes(payload)
  index["cases"][0]["manifest_sha256"] = hashlib.sha256(payload).hexdigest()
  index_path.write_bytes(_json_bytes(index))
  assert audit_committed_manifests(case_root)["public_input_count"] == 1


def test_manifest_tamper_symlink_hardlink_and_oversize_are_rejected(tmp_path):
  tampered = tmp_path / "tampered"
  _write_case_set(tampered, ("case-001",))
  (tampered / "manifests/case-001.json").write_text("{}", encoding="utf-8")
  with pytest.raises(ManifestAuditError, match="digest"):
    audit_committed_manifests(tampered)

  symlinked = tmp_path / "symlinked"
  _write_case_set(symlinked, ("case-001",))
  manifest = symlinked / "manifests/case-001.json"
  target = tmp_path / "target.json"
  target.write_bytes(manifest.read_bytes())
  manifest.unlink()
  manifest.symlink_to(target)
  with pytest.raises(ManifestAuditError, match="securely open"):
    audit_committed_manifests(symlinked)

  hardlinked = tmp_path / "hardlinked"
  _write_case_set(hardlinked, ("case-001",))
  os.link(hardlinked / "commitment-index.json", tmp_path / "index-copy.json")
  with pytest.raises(ManifestAuditError, match="single link"):
    audit_committed_manifests(hardlinked)

  oversized = tmp_path / "oversized"
  oversized.mkdir()
  (oversized / "commitment-index.json").write_bytes(b" " * (1024 * 1024 + 1))
  with pytest.raises(ManifestAuditError, match="size limit"):
    audit_committed_manifests(oversized)
