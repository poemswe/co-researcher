import hashlib
import json
import os
import pathlib
import socket
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

import run_eval  # noqa: E402
from lib import literature_integrity  # noqa: E402
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
  assert opened[1:] == [
      "commitment-index.json",
      "manifests",
      "case-002.json",
      "manifests",
      "case-001.json",
  ]
  assert not any("annotation" in path or "gold" in path for path in opened)
  assert not any(
      "annotation" in path or "gold" in path
      for _, path in descriptor_operations)
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
  monkeypatch.setattr(socket, "socket", forbidden)
  monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path / "results")
  before = set(tmp_path.rglob("*"))

  assert run_eval.main([
      "literature-review-integrity",
      "--official-cases-dir", str(case_root),
      "--dry-run-manifest-audit",
  ]) == 0

  captured = capsys.readouterr()
  assert json.loads(captured.out)["case_count"] == 1
  assert captured.err == ""
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
