import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/literature-review/scripts"
CLI = SCRIPTS / "validate_review.py"
sys.path.insert(0, str(SCRIPTS))

import verify_citations  # noqa: E402


class _StaticResolver:
  identity = "static-offline-test"

  def __init__(self, *, status="verified"):
    self.status = status

  def resolve(self, entry):
    if self.status == "not_found":
      return {
          "input": entry["raw"], "status": "not_found", "doi": entry["doi"],
          "matched_title": None, "source": "fixture",
          "retraction_checked": False, "retraction_source": None,
          "retraction_status": "not_applicable",
          "resolution_status": "complete",
      }
    return {
        "input": entry["raw"], "status": "verified", "doi": entry["doi"],
        "matched_title": "Example Study", "source": "fixture",
        "retraction_checked": True, "retraction_source": "fixture",
        "retraction_status": "complete", "resolution_status": "complete",
    }


def _review(root, *, refs=None, quote=None, synthesis=None):
  refs = ([{"doi": "10.1/example", "title": "Example Study"}]
          if refs is None else refs)
  payloads = {
      "protocol.md": "# Protocol\n",
      "corpus.json": json.dumps([{
          "key": "paper-one", "ids": {"pmcid": "p1"},
          "authors": ["Priya Patel"], "year": 2022,
          "role": "evidence", "found_via": "openalex",
          "fulltext": "fulltext", "screening": {"status": "included"},
      }]),
      "claims.json": json.dumps([{
          "claim": "Readmissions fell 18% in the treatment arm.",
          "paper_id": "p1", "citation": "Patel, 2022",
          "supporting_quote": quote or (
              "Thirty-day readmissions fell 18% in the treatment arm relative "
              "to usual care across all enrolled regional hospitals."),
      }]),
      "synthesis.md": synthesis or (
          "Readmissions fell 18% in the treatment arm (Patel, 2022)."),
      "refs.json": json.dumps(refs),
      "project.json": json.dumps({"project": "review"}),
      "papers/p1/fulltext.md": (
          "Thirty-day readmissions fell 18% in the treatment arm relative "
          "to usual care across all enrolled regional hospitals."),
  }
  for relative, text in payloads.items():
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
  return root


def _citation_report(path, refs, *, status="verified"):
  entries = verify_citations.normalize_citation_entries(refs)
  report = verify_citations.verify_citation_entries(
      entries, _StaticResolver(status=status),
      datetime(2026, 8, 4, 12, 30, tzinfo=timezone.utc))
  payload = json.dumps(report, sort_keys=True).encode("utf-8")
  path.write_bytes(payload)
  return payload, report


def _run(workspace, *args, cwd=None):
  return subprocess.run(
      [sys.executable, "-B", str(CLI), "--workspace", str(workspace), *args],
      cwd=cwd, capture_output=True, text=True, check=False, timeout=15)


def _report(result):
  assert result.stdout.endswith("\n")
  assert result.stdout.count("\n") == 1
  return json.loads(result.stdout)


def _load_cli_module():
  spec = importlib.util.spec_from_file_location("validate_review_test", CLI)
  assert spec is not None and spec.loader is not None
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


def test_valid_review_cli_exits_zero_and_prints_strict_json_from_any_cwd(
    tmp_path,
):
  refs = [{"doi": "10.1/example", "title": "Example Study"}]
  workspace = _review(tmp_path / "review", refs=refs)
  citation_path = tmp_path / "citation.json"
  payload, citation = _citation_report(citation_path, refs)

  result = _run(
      workspace, "--citation-report", str(citation_path), cwd=tmp_path)

  assert result.returncode == 0, result.stderr
  report = _report(result)
  assert set(report) == {
      "schema_version", "engine_version", "quality_score", "target_commit",
      "target_dirty", "validator_versions", "manifest_sha256",
      "workspace_manifest_sha256", "citation_report_sha256", "dimensions",
      "findings", "integrity_score", "status", "action", "repair_feedback",
      "citation_resolution",
  }
  assert report["schema_version"] == "1.0.0"
  assert report["engine_version"] == "1.0.0"
  assert report["quality_score"] is None
  assert report["status"] == "valid"
  assert report["integrity_score"] == 100.0
  assert report["citation_report_sha256"] == hashlib.sha256(payload).hexdigest()
  assert report["citation_resolution"] == {
      "source": "supplied_report", "resolver": citation["resolver"],
      "checked_at": citation["checked_at"],
      "response_status": citation["response_status"],
  }
  assert all(key not in report for key in ("unknown", "gold", "expected", "attack"))
  assert set(report["validator_versions"]) == {
      "claims", "citation", "prisma", "artifact_scoring"}
  assert result.stderr.startswith("VALID: ")


def test_cli_without_report_is_offline_unresolved_warning_not_incomplete(
    tmp_path, monkeypatch,
):
  workspace = _review(tmp_path / "review")
  module = _load_cli_module()

  class ForbiddenNetworkResolver:
    def __init__(self, *args, **kwargs):
      raise AssertionError("network resolver must never be constructed")

  monkeypatch.setattr(
      module.verify_citations, "NetworkCitationResolver",
      ForbiddenNetworkResolver)
  report, _synthesis = module.run_validation(workspace, None)

  assert report["status"] == "valid_with_warnings"
  assert report["citation_report_sha256"] is None
  assert report["citation_resolution"] == {
      "source": "not_supplied", "resolver": None, "checked_at": None,
      "response_status": "unavailable",
  }
  assert [item["reason_code"] for item in report["findings"]] == [
      "citation_resolution_unavailable"]
  assert report["findings"][0]["severity"] == "warning"
  assert report["findings"][0]["context"]["response_status"] == "unavailable"
  bibliography = report["dimensions"]["bibliography_verification"]
  assert (bibliography["evaluated_units"], bibliography["passed_units"]) == (
      1, 0)
  assert bibliography["score"] == 0.0


def test_empty_bibliography_without_report_is_not_applicable(tmp_path):
  workspace = _review(tmp_path / "review", refs=[])

  result = _run(workspace)

  assert result.returncode == 0, result.stderr
  report = _report(result)
  assert report["status"] == "valid"
  assert report["citation_resolution"]["response_status"] == "not_applicable"
  assert report["dimensions"]["bibliography_verification"]["applicable"] is False
  assert not any(item["artifact"] == "refs.json" for item in report["findings"])


def test_supplied_report_is_strict_and_cli_never_constructs_network_resolver(
    tmp_path, monkeypatch,
):
  refs = [{"doi": "10.1/example", "title": "Example Study"}]
  workspace = _review(tmp_path / "review", refs=refs)
  citation_path = tmp_path / "citation.json"
  _citation_report(citation_path, refs)
  module = _load_cli_module()

  class ForbiddenNetworkResolver:
    def __init__(self, *args, **kwargs):
      raise AssertionError("network resolver must never be constructed")

  monkeypatch.setattr(
      module.verify_citations, "NetworkCitationResolver",
      ForbiddenNetworkResolver)
  report, _synthesis = module.run_validation(workspace, citation_path)
  assert report["status"] == "valid"

  citation_path.write_text('{"x":1,"x":2}', encoding="utf-8")
  with pytest.raises(module.ValidationInputError, match="duplicate"):
    module.run_validation(workspace, citation_path)
  citation_path.write_text('{"x":NaN}', encoding="utf-8")
  with pytest.raises(module.ValidationInputError, match="numeric|JSON"):
    module.run_validation(workspace, citation_path)
  citation_path.write_bytes(b"\xff")
  with pytest.raises(module.ValidationInputError, match="UTF-8"):
    module.run_validation(workspace, citation_path)


def test_malformed_supplied_report_constructs_invalid_report(tmp_path):
  workspace = _review(tmp_path / "review")
  citation_path = tmp_path / "citation.json"
  citation_path.write_text("{}", encoding="utf-8")

  result = _run(workspace, "--citation-report", str(citation_path))

  assert result.returncode == 1
  report = _report(result)
  assert report["status"] == "invalid"
  assert "validator_incomplete" in {
      item["reason_code"] for item in report["findings"]}
  assert report["citation_resolution"] == {
      "source": "supplied_report", "resolver": None, "checked_at": None,
      "response_status": "malformed",
  }


def test_invalid_claim_report_exits_one_and_preserves_json_report(tmp_path):
  workspace = _review(
      tmp_path / "review",
      quote=("This invented evidence passage is deliberately long enough to "
             "be checked but it does not occur in the retained source text."))

  result = _run(workspace)

  assert result.returncode == 1
  report = _report(result)
  assert report["status"] == "invalid"
  assert any(item["severity"] == "critical" for item in report["findings"])
  assert "verified" not in result.stderr.lower()


def test_cli_run_report_retains_first_and_intermediate_passes(tmp_path):
  workspace = _review(
      tmp_path / "review",
      quote=("This invented evidence passage is deliberately long enough to "
             "be checked but it does not occur in the retained source text."))
  run_report = tmp_path / "run-report.json"

  first = _run(workspace, "--run-report", str(run_report))
  first_stdout = _report(first)
  first_ledger = json.loads(run_report.read_text(encoding="utf-8"))
  (workspace / "protocol.md").write_text(
      "# Protocol\n\nA submitted repair that remains invalid.\n",
      encoding="utf-8")
  second = _run(workspace, "--run-report", str(run_report))
  second_stdout = _report(second)
  second_ledger = json.loads(run_report.read_text(encoding="utf-8"))

  assert first.returncode == second.returncode == 1
  assert first_stdout["action"] == second_stdout["action"] == "repair"
  assert first_stdout["repair_feedback"]["reason_codes"] == list(dict.fromkeys(
      finding["reason_code"] for finding in first_stdout["findings"]))
  assert "fabricated_quote" in first_stdout[
      "repair_feedback"]["reason_codes"]
  assert second_ledger["pass_report"] == first_ledger["pass_report"]
  assert second_ledger["workspace_manifest_sha256"] == first_ledger[
      "workspace_manifest_sha256"]
  assert second_ledger["action"] == first_ledger["action"] == "repair"
  assert len(second_ledger["repairs"]) == 1
  repair = second_ledger["repairs"][0]
  assert repair["attempt"] == 1
  assert repair["pass_report"] == {
      key: second_stdout[key]
      for key in ("schema_version", "integrity_score", "findings",
                  "dimensions", "manifest_sha256", "status")
  }
  assert repair["workspace_manifest_sha256"] != second_ledger[
      "workspace_manifest_sha256"]


def test_cli_rejects_run_report_inside_workspace(tmp_path):
  workspace = _review(tmp_path / "review")
  run_report = workspace / "run-report.json"

  result = _run(workspace, "--run-report", str(run_report))

  assert result.returncode == 2
  assert result.stdout == ""
  assert "outside" in result.stderr.lower()
  assert not run_report.exists()


@pytest.mark.parametrize(("option", "filename"), [
    ("--run-report", "run-report.json"),
    ("--output", "validation.json"),
])
def test_cli_rejects_case_alias_inside_workspace(
    tmp_path, option, filename,
):
  workspace = _review(tmp_path / "Review")
  alias = tmp_path / "review"
  try:
    same_directory = alias.exists() and os.path.samefile(workspace, alias)
  except OSError:
    same_directory = False
  if not same_directory:
    pytest.skip("filesystem is genuinely case-sensitive")

  result = _run(workspace, option, str(alias / filename))

  assert result.returncode == 2
  assert result.stdout == ""
  assert "outside" in result.stderr.lower()
  assert not (workspace / filename).exists()


@pytest.mark.parametrize("payload", [
    b'{"schema_version":"1.0.0","schema_version":"1.0.0"}',
    b'{"schema_version":"1.0.0","quality_score":NaN}',
    b'{"schema_version":"1.0.0","gold_label":true}',
    b'not-json',
    b'\xff',
])
def test_cli_rejects_unsafe_run_report_json_without_overwrite(
    tmp_path, payload,
):
  workspace = _review(tmp_path / "review")
  run_report = tmp_path / "run-report.json"
  run_report.write_bytes(payload)

  result = _run(workspace, "--run-report", str(run_report))

  assert result.returncode == 2
  assert result.stdout == ""
  assert "not validated" in result.stderr.lower()
  assert run_report.read_bytes() == payload


def test_cli_rejects_symlinked_run_report_and_parent(tmp_path):
  workspace = _review(tmp_path / "review")
  target = tmp_path / "target.json"
  target.write_text("do not overwrite", encoding="utf-8")
  symlink = tmp_path / "run-report.json"
  symlink.symlink_to(target)
  real_parent = tmp_path / "real-parent"
  real_parent.mkdir()
  linked_parent = tmp_path / "linked-parent"
  linked_parent.symlink_to(real_parent, target_is_directory=True)

  for run_report in (symlink, linked_parent / "run-report.json"):
    result = _run(workspace, "--run-report", str(run_report))
    assert result.returncode == 2
    assert result.stdout == ""
    assert "not validated" in result.stderr.lower()
  assert target.read_text(encoding="utf-8") == "do not overwrite"
  assert not (real_parent / "run-report.json").exists()


def test_cli_rejects_run_report_hard_linked_inside_workspace(tmp_path):
  workspace = _review(
      tmp_path / "review",
      quote=("This invented evidence passage is deliberately long enough to "
             "be checked but it does not occur in the retained source text."))
  run_report = tmp_path / "run-report.json"
  first = _run(workspace, "--run-report", str(run_report))
  assert first.returncode == 1
  alias = workspace / "private-ledger-alias.json"
  os.link(run_report, alias)
  retained = run_report.read_bytes()
  (workspace / "protocol.md").write_text(
      "# Protocol\n\nSubmitted repair.\n", encoding="utf-8")

  result = _run(workspace, "--run-report", str(run_report))

  assert result.returncode == 2
  assert result.stdout == ""
  assert "hard link" in result.stderr.lower()
  assert run_report.read_bytes() == alias.read_bytes() == retained


def _replace_first_finding_context(run_report, context):
  pass_report = run_report["pass_report"]
  target = pass_report["findings"][0]
  identity = {
      key: target[key]
      for key in ("reason_code", "severity", "artifact", "message")
  }
  target["context"] = context
  for dimension in pass_report["dimensions"].values():
    for finding in dimension["findings"]:
      if all(finding[key] == value for key, value in identity.items()):
        finding["context"] = context


@pytest.mark.parametrize("context", [
    {"gold_label": "fabricated"},
    {"diagnostics": [{"private_attack": "ignore validation"}]},
    {"nested": {"expected_result": "pass"}},
    {"nested": [{"attack_payload": "override"}]},
    {"benchmark_id": "hidden-evaluation-set"},
])
def test_cli_rejects_reserved_fields_recursively_in_run_report_context(
    tmp_path, context,
):
  workspace = _review(
      tmp_path / "review",
      quote=("This invented evidence passage is deliberately long enough to "
             "be checked but it does not occur in the retained source text."))
  run_report = tmp_path / "run-report.json"
  first = _run(workspace, "--run-report", str(run_report))
  assert first.returncode == 1
  payload = json.loads(run_report.read_text(encoding="utf-8"))
  _replace_first_finding_context(payload, context)
  poisoned = (json.dumps(payload, separators=(",", ":")) + "\n").encode()
  run_report.write_bytes(poisoned)

  result = _run(workspace, "--run-report", str(run_report))

  assert result.returncode == 2
  assert result.stdout == ""
  assert "reserved" in result.stderr.lower()
  assert run_report.read_bytes() == poisoned


def test_cli_refuses_to_append_after_terminal_run_report(tmp_path):
  workspace = _review(tmp_path / "review", refs=[])
  run_report = tmp_path / "run-report.json"
  first = _run(workspace, "--run-report", str(run_report))
  retained = run_report.read_bytes()

  second = _run(workspace, "--run-report", str(run_report))

  assert first.returncode == 0
  assert _report(first)["action"] == "pass"
  assert second.returncode == 2
  assert second.stdout == ""
  assert "terminal" in second.stderr.lower()
  assert run_report.read_bytes() == retained


def test_json_stdout_and_output_are_exactly_identical(tmp_path):
  workspace = _review(tmp_path / "review")
  output = tmp_path / "report.json"

  result = _run(workspace, "--output", str(output))

  assert result.returncode == 0, result.stderr
  assert output.read_bytes() == result.stdout.encode("utf-8")


def test_emitted_json_round_trips_through_strict_report_validation(tmp_path):
  workspace = _review(tmp_path / "review")
  module = _load_cli_module()
  report, _ = module.run_validation(workspace, None)

  parsed = json.loads(module.render_json(report))

  assert module.validate_report(parsed) is parsed
  assert tuple(parsed["dimensions"]) == (
      "quote_authenticity", "citation_binding", "quantitative_grounding",
      "synthesis_coverage", "bibliography_verification",
      "prisma_artifact_completeness",
  )


def test_json_render_is_independent_of_mapping_insertion_order(tmp_path):
  workspace = _review(
      tmp_path / "review",
      quote=("This invented evidence passage is deliberately long enough to "
             "be checked but it does not occur in the retained source text."))
  module = _load_cli_module()
  report, _ = module.run_validation(workspace, None)
  reordered = {key: deepcopy(report[key]) for key in reversed(report)}
  for finding in reordered["findings"]:
    finding["context"] = dict(reversed(tuple(finding["context"].items())))
  for dimension in reordered["dimensions"].values():
    for finding in dimension["findings"]:
      finding["context"] = dict(reversed(tuple(finding["context"].items())))

  assert module.render_json(reordered) == module.render_json(report)


def test_strict_report_rejects_nested_findings_hidden_from_top_level(tmp_path):
  workspace = _review(
      tmp_path / "review",
      quote=("This invented evidence passage is deliberately long enough to "
             "be checked but it does not occur in the retained source text."))
  module = _load_cli_module()
  report, _ = module.run_validation(workspace, None)
  assert any(
      finding["severity"] == "critical"
      for dimension in report["dimensions"].values()
      for finding in dimension["findings"])
  report["findings"] = []
  report["status"] = "valid"

  with pytest.raises(ValueError, match="finding|consistent|dimension"):
    module.validate_report(report)


def test_combined_manifest_hash_commits_to_citation_report_or_null(tmp_path):
  refs = [{"doi": "10.1/example", "title": "Example Study"}]
  workspace = _review(tmp_path / "review", refs=refs)
  citation_path = tmp_path / "citation.json"
  payload, _citation = _citation_report(citation_path, refs)
  module = _load_cli_module()

  supplied, _ = module.run_validation(workspace, citation_path)
  absent, _ = module.run_validation(workspace, None)
  workspace_hash = supplied["workspace_manifest_sha256"]
  citation_hash = hashlib.sha256(payload).hexdigest()
  supplied_records = [
      {"workspace_manifest_sha256": workspace_hash},
      {"citation_report_sha256": citation_hash},
  ]
  absent_records = [
      {"workspace_manifest_sha256": workspace_hash},
      {"citation_report": None},
  ]
  expected_supplied = hashlib.sha256(json.dumps(
      supplied_records, ensure_ascii=False, sort_keys=True,
      separators=(",", ":")).encode("utf-8")).hexdigest()
  expected_absent = hashlib.sha256(json.dumps(
      absent_records, ensure_ascii=False, sort_keys=True,
      separators=(",", ":")).encode("utf-8")).hexdigest()

  assert supplied["manifest_sha256"] == expected_supplied
  assert absent["manifest_sha256"] == expected_absent
  assert supplied["manifest_sha256"] != absent["manifest_sha256"]


def test_citation_report_mutation_after_secure_read_cannot_change_run(
    tmp_path, monkeypatch,
):
  refs = [{"doi": "10.1/example", "title": "Example Study"}]
  workspace = _review(tmp_path / "review", refs=refs)
  citation_path = tmp_path / "citation.json"
  original_payload, _ = _citation_report(citation_path, refs)
  module = _load_cli_module()
  original_load = module.load_workspace

  def mutate_then_load(path):
    citation_path.write_text("{}", encoding="utf-8")
    return original_load(path)

  monkeypatch.setattr(module, "load_workspace", mutate_then_load)
  report, _ = module.run_validation(workspace, citation_path)

  assert report["status"] == "valid"
  assert report["citation_report_sha256"] == hashlib.sha256(
      original_payload).hexdigest()


def test_markdown_places_exact_invalid_warning_before_synthesis(tmp_path):
  marker = "SYNTHESIS-EXCERPT-MARKER"
  workspace = _review(
      tmp_path / "review", synthesis=(
          f"{marker}: Readmissions fell 18% in the treatment arm "
          "(Patel, 2022)."),
      quote=("This invented evidence passage is deliberately long enough to "
             "be checked but it does not occur in the retained source text."))
  output = tmp_path / "report.md"

  result = _run(workspace, "--output", str(output))

  assert result.returncode == 1
  markdown = output.read_text(encoding="utf-8")
  warning = (
      "INVALID EVIDENCE — This draft contains unresolved evidence-integrity "
      "failures\nand must not be treated as verified research.")
  assert warning in markdown
  assert markdown.index(warning) < markdown.index(marker)
  assert "publication-ready" not in markdown.lower()
  assert "Integrity score" in markdown and "Quality score" in markdown
  assert "Effective weight" in markdown and "Context" in markdown


def test_markdown_escapes_untrusted_inline_heading_injection(tmp_path):
  refs = [{"doi": "10.1/example", "title": "Example Study"}]
  workspace = _review(
      tmp_path / "review", refs=refs,
      quote=("This invented evidence passage is deliberately long enough to "
             "be checked but it does not occur in the retained source text."))
  citation_path = tmp_path / "citation.json"
  _citation_report(citation_path, refs)
  module = _load_cli_module()
  report, synthesis = module.run_validation(workspace, citation_path)
  injection = "trusted\n## INJECTED HEADING"
  report["citation_resolution"]["resolver"] = injection
  report["citation_resolution"]["checked_at"] = injection
  for finding in report["findings"]:
    finding["artifact"] = injection
    finding["message"] = injection
    finding["context"] = {"private": injection}
  for dimension in report["dimensions"].values():
    for finding in dimension["findings"]:
      finding["artifact"] = injection
      finding["message"] = injection
      finding["context"] = {"private": injection}
  report["repair_feedback"] = {
      "reason_codes": list(dict.fromkeys(
          finding["reason_code"] for finding in report["findings"])),
      "affected_artifacts": [injection],
      "findings": [{
          "reason_code": finding["reason_code"],
          "severity": finding["severity"],
          "artifact": injection,
          "message": injection,
      } for finding in report["findings"]],
  }

  markdown = module.render_markdown(report, synthesis)

  assert "\n## INJECTED HEADING" not in markdown
  assert "trusted\\n\\#\\# INJECTED HEADING" in markdown


@pytest.mark.parametrize("suffix", [".txt", ".JSON", ""])
def test_cli_rejects_unsupported_output_suffix_as_not_validated(
    tmp_path, suffix,
):
  workspace = _review(tmp_path / "review")
  result = _run(workspace, "--output", str(tmp_path / f"report{suffix}"))
  assert result.returncode == 2
  assert result.stdout == ""
  assert "not validated" in result.stderr.lower()


def test_cli_rejects_output_anywhere_inside_workspace(tmp_path):
  workspace = _review(tmp_path / "review")
  for output in (workspace / "report.json", workspace / "papers/report.md"):
    result = _run(workspace, "--output", str(output))
    assert result.returncode == 2
    assert result.stdout == ""
    assert "outside" in result.stderr.lower()
    assert "not validated" in result.stderr.lower()


def test_cli_rejects_existing_symlink_and_symlinked_parent_outputs(tmp_path):
  workspace = _review(tmp_path / "review")
  existing = tmp_path / "existing.json"
  existing.write_text("do not overwrite", encoding="utf-8")
  target = tmp_path / "target.json"
  target.write_text("target", encoding="utf-8")
  symlink = tmp_path / "link.json"
  symlink.symlink_to(target)
  real_parent = tmp_path / "real-parent"
  real_parent.mkdir()
  linked_parent = tmp_path / "linked-parent"
  linked_parent.symlink_to(real_parent, target_is_directory=True)

  for output in (existing, symlink, linked_parent / "report.json"):
    result = _run(workspace, "--output", str(output))
    assert result.returncode == 2
    assert result.stdout == ""
    assert "not validated" in result.stderr.lower()
  assert existing.read_text(encoding="utf-8") == "do not overwrite"
  assert target.read_text(encoding="utf-8") == "target"
  assert not (real_parent / "report.json").exists()


def test_cli_rejects_symlink_and_special_citation_inputs(tmp_path):
  workspace = _review(tmp_path / "review")
  report = tmp_path / "citation.json"
  report.write_text("{}", encoding="utf-8")
  symlink = tmp_path / "citation-link.json"
  symlink.symlink_to(report)
  directory = tmp_path / "citation-dir"
  directory.mkdir()

  for path in (symlink, directory):
    result = _run(workspace, "--citation-report", str(path))
    assert result.returncode == 2
    assert result.stdout == ""
    assert "not validated" in result.stderr.lower()


def test_target_provenance_falls_back_outside_git(tmp_path):
  workspace = _review(tmp_path / "review")
  result = _run(workspace)
  report = _report(result)
  assert report["target_commit"] is None
  assert report["target_dirty"] is None


def test_target_provenance_uses_commit_and_tracked_dirty_only(tmp_path):
  if subprocess.run(["git", "--version"], capture_output=True).returncode:
    pytest.skip("git unavailable")
  repo = tmp_path / "repo"
  workspace = _review(repo / "review")
  commands = [
      ["git", "init", "-q"],
      ["git", "config", "user.name", "Integrity Test"],
      ["git", "config", "user.email", "integrity@example.test"],
      ["git", "add", "review"],
      ["git", "commit", "-qm", "fixture"],
  ]
  for command in commands:
    subprocess.run(command, cwd=repo, check=True)
  commit = subprocess.run(
      ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
      capture_output=True, text=True).stdout.strip()
  (repo / "ignored-private.txt").write_text("untracked", encoding="utf-8")

  clean = _report(_run(workspace))
  assert clean["target_commit"] == commit
  assert clean["target_dirty"] is False
  (workspace / "protocol.md").write_text("# changed\n", encoding="utf-8")
  dirty = _report(_run(workspace))
  assert dirty["target_commit"] == commit
  assert dirty["target_dirty"] is True


def test_argparse_and_unsafe_workspace_exit_two_say_not_validated(tmp_path):
  usage = subprocess.run(
      [sys.executable, "-B", str(CLI)], capture_output=True, text=True,
      check=False, timeout=10)
  assert usage.returncode == 2
  assert usage.stdout == ""
  assert "not validated" in usage.stderr.lower()

  missing = _run(tmp_path / "missing")
  assert missing.returncode == 2
  assert missing.stdout == ""
  assert "not validated" in missing.stderr.lower()


def test_help_exits_two_on_stderr_without_non_json_stdout():
  result = subprocess.run(
      [sys.executable, "-B", str(CLI), "--help"],
      capture_output=True, text=True, check=False, timeout=10)

  assert result.returncode == 2
  assert result.stdout == ""
  assert "usage:" in result.stderr.lower()
  assert "not validated" in result.stderr.lower()
