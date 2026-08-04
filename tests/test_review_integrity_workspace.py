import hashlib
import errno
import json
import os
import pathlib
import subprocess
import sys

import pytest


SCRIPTS = (pathlib.Path(__file__).resolve().parents[1]
           / "skills/literature-review/scripts")
sys.path.insert(0, str(SCRIPTS))

from review_integrity import workspace  # noqa: E402
from review_integrity.models import ReasonCode  # noqa: E402
from review_integrity.workspace import (  # noqa: E402
    Artifact,
    CANONICALIZATION,
    WorkspaceError,
    WorkspaceSnapshot,
    canonical_manifest_bytes,
    load_workspace,
)


FIXED_PAYLOADS = {
    "protocol.md": b"# Protocol\n",
    "claims.json": b"[{\"claim\":\"original\"}]\n",
    "synthesis.md": b"# Synthesis\n",
    "refs.json": b"[]\n",
    "project.json": b'{"project":"review"}\n',
}


def _corpus(*, key="10.1/example", status="included", role="evidence",
            ids=None):
  return [{
      "key": key,
      "ids": ids if ids is not None else {"doi": key},
      "screening": {"status": status},
      "role": role,
  }]


def _write_project_workspace(root, *, corpus=None, source="fulltext.md",
                             order=None):
  root.mkdir(parents=True, exist_ok=True)
  payloads = dict(FIXED_PAYLOADS)
  payloads["corpus.json"] = json.dumps(
      _corpus() if corpus is None else corpus).encode("utf-8")
  if source:
    payloads[f"papers/10.1_example/{source}"] = b"trusted paper bytes\n"
  paths = list(payloads) if order is None else order
  for relative_path in paths:
    destination = root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payloads[relative_path])
  return root


def _write_manifest_workspace(root, *, artifacts=None, manifest_extra=None,
                              corpus=None):
  root.mkdir(parents=True, exist_ok=True)
  corpus_payload = json.dumps(
      _corpus() if corpus is None else corpus).encode("utf-8")
  payloads = {
      key: value for key, value in FIXED_PAYLOADS.items()
      if key != "project.json"
  }
  payloads["corpus.json"] = corpus_payload
  payloads["papers/10.1_example/fulltext.md"] = b"trusted paper bytes\n"
  for relative_path, payload in payloads.items():
    destination = root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
  manifest = {
      "schema_version": "1.0.0",
      "artifacts": artifacts if artifacts is not None else list(payloads),
  }
  if manifest_extra:
    manifest.update(manifest_extra)
  (root / "run-manifest.json").write_text(
      json.dumps(manifest), encoding="utf-8")
  return root


@pytest.mark.parametrize("missing", [
    "protocol.md", "corpus.json", "claims.json", "synthesis.md", "refs.json",
])
def test_workspace_requires_protocol_corpus_claims_synthesis_and_refs(
    tmp_path, missing,
):
  root = _write_project_workspace(tmp_path / "review")
  (root / missing).unlink()

  with pytest.raises(WorkspaceError, match=missing) as captured:
    load_workspace(root)
  assert captured.value.reason_code is ReasonCode.ARTIFACT_MISSING
  assert captured.value.artifact == missing


def test_missing_workspace_root_is_classified_without_message_parsing(tmp_path):
  missing = tmp_path / "missing-root"

  with pytest.raises(WorkspaceError) as captured:
    load_workspace(missing)

  assert captured.value.reason_code is ReasonCode.ARTIFACT_MISSING
  assert captured.value.artifact == "."


def test_non_directory_workspace_root_is_type_invalid(tmp_path):
  parent_file = tmp_path / "not-a-directory"
  parent_file.write_text("x")

  with pytest.raises(WorkspaceError) as captured:
    load_workspace(parent_file / "child")

  assert captured.value.reason_code is ReasonCode.ARTIFACT_TYPE_INVALID
  assert captured.value.artifact == "."


def test_workspace_root_permission_error_is_validator_incomplete(
    monkeypatch, tmp_path,
):
  root = tmp_path / "permission-root"
  root.mkdir()
  real_open = workspace.os.open

  def denied(path, flags, *args, **kwargs):
    if path == root.name and kwargs.get("dir_fd") is not None:
      raise PermissionError(errno.EACCES, "permission denied", path)
    return real_open(path, flags, *args, **kwargs)

  monkeypatch.setattr(workspace.os, "open", denied)

  with pytest.raises(WorkspaceError) as captured:
    load_workspace(root)

  assert captured.value.reason_code is ReasonCode.VALIDATOR_INCOMPLETE
  assert captured.value.artifact == "."


def test_workspace_requires_project_link_or_run_manifest(tmp_path):
  root = _write_project_workspace(tmp_path / "review")
  (root / "project.json").unlink()

  with pytest.raises(WorkspaceError, match="project.json|run-manifest.json"):
    load_workspace(root)


def test_workspace_rejects_both_project_link_artifacts(tmp_path):
  root = _write_project_workspace(tmp_path / "review")
  (root / "run-manifest.json").write_text(
      '{"schema_version":"1.0.0","artifacts":[]}', encoding="utf-8")

  with pytest.raises(WorkspaceError, match="both|ambiguous"):
    load_workspace(root)


def test_project_link_must_be_a_nonempty_json_object(tmp_path):
  root = _write_project_workspace(tmp_path / "review")
  (root / "project.json").write_text("[]", encoding="utf-8")
  with pytest.raises(WorkspaceError, match="project.json"):
    load_workspace(root)

  (root / "project.json").write_text("{}", encoding="utf-8")
  with pytest.raises(WorkspaceError, match="project.json"):
    load_workspace(root)


def test_workspace_rejects_symlinked_root(tmp_path):
  target = _write_project_workspace(tmp_path / "target")
  link = tmp_path / "review"
  link.symlink_to(target, target_is_directory=True)

  with pytest.raises(WorkspaceError, match="root|symlink") as captured:
    load_workspace(link)
  assert captured.value.reason_code is ReasonCode.ARTIFACT_SYMLINK
  assert captured.value.artifact == "."


def test_workspace_rejects_symlinked_artifact(tmp_path):
  root = _write_project_workspace(tmp_path / "review")
  external = tmp_path / "claims.json"
  external.write_bytes(b"[]")
  (root / "claims.json").unlink()
  (root / "claims.json").symlink_to(external)

  with pytest.raises(WorkspaceError, match="claims.json") as captured:
    load_workspace(root)
  assert captured.value.reason_code is ReasonCode.ARTIFACT_SYMLINK
  assert captured.value.artifact == "claims.json"


def test_workspace_rejects_symlinked_intermediate_directory(tmp_path):
  root = _write_project_workspace(tmp_path / "review")
  external = tmp_path / "external-paper"
  external.mkdir()
  (external / "fulltext.md").write_bytes(b"outside")
  source_dir = root / "papers/10.1_example"
  (source_dir / "fulltext.md").unlink()
  source_dir.rmdir()
  source_dir.symlink_to(external, target_is_directory=True)

  with pytest.raises(WorkspaceError, match="papers/10.1_example"):
    load_workspace(root)


def test_workspace_rejects_fifo_leaf_without_blocking(tmp_path):
  root = _write_project_workspace(tmp_path / "review")
  (root / "claims.json").unlink()
  os.mkfifo(root / "claims.json")
  script = (
      "import pathlib,sys;"
      f"sys.path.insert(0,{str(SCRIPTS)!r});"
      "from review_integrity.workspace import load_workspace,WorkspaceError;"
      "root=pathlib.Path(sys.argv[1]);"
      "\ntry: load_workspace(root)"
      "\nexcept WorkspaceError: raise SystemExit(0)"
      "\nraise SystemExit(1)"
  )
  try:
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, str(root)],
        check=False, capture_output=True, text=True, timeout=2)
  except subprocess.TimeoutExpired:
    pytest.fail("load_workspace blocked while opening a FIFO artifact")

  assert result.returncode == 0, result.stderr

  with pytest.raises(WorkspaceError) as captured:
    load_workspace(root)
  assert captured.value.reason_code is ReasonCode.ARTIFACT_TYPE_INVALID
  assert captured.value.artifact == "claims.json"


def test_workspace_rejects_directory_artifact_as_type_invalid(tmp_path):
  root = _write_project_workspace(tmp_path / "review")
  (root / "claims.json").unlink()
  (root / "claims.json").mkdir()

  with pytest.raises(WorkspaceError) as captured:
    load_workspace(root)

  assert captured.value.reason_code is ReasonCode.ARTIFACT_TYPE_INVALID
  assert captured.value.artifact == "claims.json"


@pytest.mark.parametrize("artifact", [
    "project.json", "corpus.json", "claims.json",
])
def test_malformed_json_reports_exact_artifact(tmp_path, artifact):
  root = _write_project_workspace(tmp_path / "review")
  (root / artifact).write_text("{not-json", encoding="utf-8")

  with pytest.raises(WorkspaceError) as captured:
    snapshot = load_workspace(root)
    snapshot.read_json(artifact)

  assert captured.value.reason_code is ReasonCode.ARTIFACT_MALFORMED
  assert captured.value.artifact == artifact


def test_semantically_invalid_corpus_reports_corpus_artifact(tmp_path):
  root = _write_project_workspace(tmp_path / "review")
  (root / "corpus.json").write_text("{}", encoding="utf-8")

  with pytest.raises(WorkspaceError) as captured:
    load_workspace(root)

  assert captured.value.artifact == "corpus.json"


def test_semantically_invalid_project_reports_project_artifact(tmp_path):
  root = _write_project_workspace(tmp_path / "review")
  (root / "project.json").write_text("{}", encoding="utf-8")

  with pytest.raises(WorkspaceError) as captured:
    load_workspace(root)

  assert captured.value.artifact == "project.json"


@pytest.mark.parametrize("bad", [
    "../claims.json", "papers/../claims.json", "/absolute/claims.json",
    "./claims.json", "papers//10.1_example/fulltext.md",
])
def test_workspace_rejects_parent_traversal_and_noncanonical_paths(
    tmp_path, bad,
):
  required = [
      "protocol.md", "corpus.json", "claims.json", "synthesis.md", "refs.json",
      "papers/10.1_example/fulltext.md",
  ]
  root = _write_manifest_workspace(tmp_path / "review",
                                   artifacts=required + [bad])

  with pytest.raises(WorkspaceError, match="path|artifact") as captured:
    load_workspace(root)
  assert captured.value.reason_code is ReasonCode.ARTIFACT_TRAVERSAL
  assert captured.value.artifact == bad


def test_run_manifest_rejects_missing_extra_and_duplicate_fields(tmp_path):
  root = _write_manifest_workspace(tmp_path / "missing")
  (root / "run-manifest.json").write_text(
      '{"schema_version":"1.0.0"}', encoding="utf-8")
  with pytest.raises(WorkspaceError, match="run-manifest.json"):
    load_workspace(root)

  root = _write_manifest_workspace(tmp_path / "extra", manifest_extra={"x": 1})
  with pytest.raises(WorkspaceError, match="run-manifest.json"):
    load_workspace(root)

  root = _write_manifest_workspace(tmp_path / "duplicate")
  (root / "run-manifest.json").write_text(
      '{"schema_version":"1.0.0","schema_version":"1.0.0",'
      '"artifacts":[]}', encoding="utf-8")
  with pytest.raises(WorkspaceError, match="duplicate"):
    load_workspace(root)


def test_run_manifest_rejects_duplicate_or_incomplete_artifact_lists(tmp_path):
  required = [
      "protocol.md", "corpus.json", "claims.json", "synthesis.md", "refs.json",
      "papers/10.1_example/fulltext.md",
  ]
  root = _write_manifest_workspace(tmp_path / "duplicate",
                                   artifacts=required + ["claims.json"])
  with pytest.raises(WorkspaceError, match="duplicate"):
    load_workspace(root)

  root = _write_manifest_workspace(tmp_path / "incomplete",
                                   artifacts=required[:-1])
  with pytest.raises(WorkspaceError, match="source|manifest"):
    load_workspace(root)


@pytest.mark.parametrize("unexpected", [
    "notes.txt", "papers/10.1_example/paper.pdf", "project.json",
    "papers/unrelated/fulltext.md", "nested/claims.json",
])
def test_run_manifest_may_only_name_contract_files(tmp_path, unexpected):
  required = [
      "protocol.md", "corpus.json", "claims.json", "synthesis.md", "refs.json",
      "papers/10.1_example/fulltext.md",
  ]
  root = _write_manifest_workspace(tmp_path / "review",
                                   artifacts=required + [unexpected])
  destination = root / unexpected
  destination.parent.mkdir(parents=True, exist_ok=True)
  destination.write_bytes(b"unexpected")

  with pytest.raises(WorkspaceError, match="contract|manifest|artifact"):
    load_workspace(root)


def test_workspace_manifest_is_independent_of_creation_order(tmp_path):
  default_paths = list(FIXED_PAYLOADS) + [
      "corpus.json", "papers/10.1_example/fulltext.md",
  ]
  first = _write_project_workspace(tmp_path / "first", order=default_paths)
  second = _write_project_workspace(tmp_path / "second",
                                    order=list(reversed(default_paths)))

  first_snapshot = load_workspace(first)
  second_snapshot = load_workspace(second)

  assert first_snapshot.manifest_sha256 == second_snapshot.manifest_sha256
  assert [item.relative_path for item in first_snapshot.files] == sorted(
      default_paths, key=lambda value: value.encode("utf-8"))


def test_workspace_hash_changes_when_claims_change(tmp_path):
  first = _write_project_workspace(tmp_path / "first")
  second = _write_project_workspace(tmp_path / "second")
  (second / "claims.json").write_bytes(b'[{"claim":"changed"}]\n')

  assert (load_workspace(first).manifest_sha256
          != load_workspace(second).manifest_sha256)


def test_snapshot_reads_the_bytes_that_were_hashed_even_after_source_mutation(
    tmp_path,
):
  root = _write_project_workspace(tmp_path / "review")
  snapshot = load_workspace(root)
  digest = snapshot.manifest_sha256
  (root / "claims.json").write_bytes(b'[{"claim":"mutated"}]\n')

  assert snapshot.read_json("claims.json") == [{"claim": "original"}]
  assert snapshot.manifest_sha256 == digest
  claims = next(item for item in snapshot.files
                if item.relative_path == "claims.json")
  assert claims.sha256 == hashlib.sha256(
      b'[{"claim":"original"}]\n').hexdigest()


def test_snapshot_json_and_text_reads_reject_bad_immutable_bytes(tmp_path):
  root = _write_project_workspace(tmp_path / "review")
  (root / "claims.json").write_bytes(b'{"x":1,"x":2}')
  (root / "synthesis.md").write_bytes(b"\xff")
  snapshot = load_workspace(root)

  with pytest.raises(WorkspaceError, match="duplicate"):
    snapshot.read_json("claims.json")
  with pytest.raises(WorkspaceError, match="UTF-8"):
    snapshot.read_text("synthesis.md")


def test_snapshot_read_json_rejects_malformed_json(tmp_path):
  root = _write_project_workspace(tmp_path / "review")
  (root / "refs.json").write_bytes(b"{")
  snapshot = load_workspace(root)

  with pytest.raises(WorkspaceError, match="JSON"):
    snapshot.read_json("refs.json")


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_snapshot_read_json_rejects_nonstandard_numeric_constants(
    tmp_path, constant,
):
  root = _write_project_workspace(tmp_path / "review")
  (root / "refs.json").write_text(f"[{constant}]", encoding="utf-8")
  snapshot = load_workspace(root)

  with pytest.raises(WorkspaceError, match="JSON"):
    snapshot.read_json("refs.json")


@pytest.mark.parametrize("payload", [b"1e400", b'[{"nested":1e400}]'])
def test_snapshot_read_json_rejects_overflowed_floats(tmp_path, payload):
  root = _write_project_workspace(tmp_path / "review")
  (root / "refs.json").write_bytes(payload)
  snapshot = load_workspace(root)

  with pytest.raises(WorkspaceError, match="finite|JSON"):
    snapshot.read_json("refs.json")


def test_trusted_dataclasses_reject_public_direct_construction(tmp_path):
  root = _write_project_workspace(tmp_path / "review")
  trusted = load_workspace(root)

  with pytest.raises(WorkspaceError, match="loader"):
    WorkspaceSnapshot(files=())
  with pytest.raises(WorkspaceError, match="loader"):
    WorkspaceSnapshot(files=trusted.files)
  assert trusted.read_json("claims.json") == [{"claim": "original"}]


def test_artifact_direct_construction_cannot_bypass_size_limit(monkeypatch):
  payload = b"oversized"
  monkeypatch.setattr(workspace, "MAX_ARTIFACT_BYTES", len(payload) - 1)

  with pytest.raises(WorkspaceError, match="loader"):
    Artifact(
        relative_path="claims.json",
        payload=payload,
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def test_discovery_requires_sources_only_for_included_evidence_or_background(
    tmp_path,
):
  excluded = _corpus(status="excluded", role="evidence")
  root = _write_project_workspace(tmp_path / "excluded", corpus=excluded,
                                  source=None)
  assert load_workspace(root).manifest_sha256

  included = _corpus(status="included", role="evidence")
  root = _write_project_workspace(tmp_path / "included", corpus=included,
                                  source=None)
  with pytest.raises(WorkspaceError, match="source"):
    load_workspace(root)


def test_discovery_hashes_both_sources_and_prefers_fulltext(tmp_path):
  root = _write_project_workspace(tmp_path / "review")
  abstract = root / "papers/10.1_example/abstract.md"
  abstract.write_bytes(b"abstract bytes")

  snapshot = load_workspace(root)
  sources = {item.relative_path: item for item in snapshot.files
             if item.relative_path.startswith("papers/")}

  assert set(sources) == {
      "papers/10.1_example/fulltext.md",
      "papers/10.1_example/abstract.md",
  }
  assert sources["papers/10.1_example/fulltext.md"].preferred_for_claims
  assert not sources["papers/10.1_example/abstract.md"].preferred_for_claims


def test_discovery_rejects_missing_ambiguous_and_duplicate_derived_ids(tmp_path):
  missing = _corpus(key=None, ids={})
  root = _write_project_workspace(tmp_path / "missing", corpus=missing,
                                  source=None)
  with pytest.raises(WorkspaceError, match="identifier"):
    load_workspace(root)

  ambiguous = _corpus(key="10.1/example", ids={"pmcid": "PMC1"})
  root = _write_project_workspace(tmp_path / "ambiguous", corpus=ambiguous)
  other = root / "papers/PMC1/fulltext.md"
  other.parent.mkdir(parents=True)
  other.write_bytes(b"also a source")
  with pytest.raises(WorkspaceError, match="ambiguous"):
    load_workspace(root)

  duplicate = _corpus() + _corpus()
  root = _write_project_workspace(tmp_path / "duplicate", corpus=duplicate)
  with pytest.raises(WorkspaceError, match="duplicate"):
    load_workspace(root)


def test_discovery_rejects_shared_trusted_aliases_with_distinct_source_dirs(
    tmp_path,
):
  corpus = [
      {"key": "paper-one", "ids": {"doi": "10.1/shared"},
       "screening": {"status": "included"}, "role": "evidence"},
      {"key": "paper-two", "ids": {"doi": "10.1/shared"},
       "screening": {"status": "included"}, "role": "background"},
  ]
  root = _write_project_workspace(
      tmp_path / "review", corpus=corpus, source=None)
  for identifier in ("paper-one", "paper-two"):
    source = root / f"papers/{identifier}/fulltext.md"
    source.parent.mkdir(parents=True)
    source.write_bytes(identifier.encode("ascii"))

  with pytest.raises(WorkspaceError, match="duplicate"):
    load_workspace(root)


@pytest.mark.parametrize("field, malformed", [
    ("ids", []), ("ids", False), ("screening", []), ("screening", False),
])
def test_discovery_rejects_falsy_malformed_corpus_objects(
    tmp_path, field, malformed,
):
  record = _corpus()[0]
  record[field] = malformed
  root = _write_project_workspace(tmp_path / "review", corpus=[record])

  with pytest.raises(WorkspaceError, match=field):
    load_workspace(root)


def test_size_limits_are_enforced_without_large_fixtures(tmp_path, monkeypatch):
  root = _write_project_workspace(tmp_path / "per-file")
  monkeypatch.setattr(workspace, "MAX_ARTIFACT_BYTES", 8)
  with pytest.raises(WorkspaceError, match="size"):
    load_workspace(root)

  root = _write_project_workspace(tmp_path / "total")
  monkeypatch.setattr(workspace, "MAX_ARTIFACT_BYTES", 1_000)
  monkeypatch.setattr(workspace, "MAX_TOTAL_ARTIFACT_BYTES", 40)
  with pytest.raises(WorkspaceError, match="total|size"):
    load_workspace(root)


def test_restricted_manifest_bytes_are_deterministic_and_reject_bad_values():
  manifest = {
      "files": [{
          "size": 6,
          "sha256": "0" * 64,
          "path": "papers/café/abstract.md",
      }],
      "canonicalization": CANONICALIZATION,
  }
  assert canonical_manifest_bytes(manifest) == (
      b'{"canonicalization":"rfc8785-restricted-v1","files":['
      b'{"path":"papers/caf\xc3\xa9/abstract.md","sha256":"'
      + b"0" * 64 + b'","size":6}]}'
  )

  with pytest.raises(WorkspaceError, match="canonicalization"):
    canonical_manifest_bytes({**manifest, "canonicalization": "unknown"})
  with pytest.raises(WorkspaceError, match="integer"):
    canonical_manifest_bytes({
        **manifest,
        "files": [{**manifest["files"][0], "size": 2 ** 53}],
    })
  with pytest.raises(WorkspaceError, match="Unicode"):
    canonical_manifest_bytes({
        **manifest,
        "files": [{**manifest["files"][0], "path": "bad\ud800"}],
    })


def test_artifact_payloads_are_immutable_bytes(tmp_path):
  snapshot = load_workspace(_write_project_workspace(tmp_path / "review"))
  artifact = snapshot.files[0]
  assert type(artifact.payload) is bytes
  with pytest.raises((AttributeError, TypeError)):
    artifact.payload[0] = 0
