import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import replace
from types import SimpleNamespace
from html.parser import HTMLParser

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

from lib.literature_integrity import (  # noqa: E402
    AdversarialCaseScore,
    IntegrityEvalResult,
    ModelUsage,
    OperationalFailure,
    OperationalIntegrityEvalResult,
    QualityResult,
    RepairCost,
    ReasonMetric,
    RobustnessResult,
    SnapshotEvaluation,
)
from lib.run_reports import (  # noqa: E402
    CombinedCaseResult,
    CombinedRunResult,
    adapt_quality_history,
    load_dashboard_data,
    write_run_report,
)
from review_integrity.models import IntegrityRunReport, ReasonCode  # noqa: E402
import run_eval  # noqa: E402
from lib import literature_integrity  # noqa: E402
from lib import run_reports  # noqa: E402


def _evaluation(quality_score: float) -> IntegrityEvalResult:
  integrity = IntegrityRunReport.example_valid().pass_report
  usage = ModelUsage(
      duration_seconds=1.0,
      input_tokens=10,
      output_tokens=20,
      estimated_cost_usd=0.03,
      executor_version="test-executor-v1",
      prompt_version="test-prompt-v1",
      prompt_sha256="a" * 64,
  )
  snapshot = SnapshotEvaluation(
      workspace_manifest_sha256=integrity.manifest_sha256,
      quality=QualityResult(
          quality_score=quality_score,
          scores={
              "research-quality": quality_score,
              "analytical-quality": quality_score,
              "output-structure": quality_score,
          },
          error=None,
      ),
      integrity=integrity,
      model_usage=usage,
  )
  return IntegrityEvalResult(
      model_first_pass=snapshot,
      repair_rounds=(),
      system_final=snapshot,
      repair_cost=RepairCost.from_rounds(()),
      robustness=RobustnessResult(
          expected_final_status="valid",
          observed_final_status="valid",
          minimum_repair_rounds=0,
          maximum_repair_rounds=0,
          expectation_met=True,
          error=None,
      ),
  )


_PROVENANCE = {
    "target_commit": "a" * 40,
    "target_dirty": False,
    "engine_version": "1.0.0",
    "validator_versions": {
        "claims": "1.0.0", "citation": "1.0.0", "prisma": "1.0.0",
        "artifact_scoring": "1.0.0",
    },
}


def _run(run_id: str, *quality_scores: float) -> CombinedRunResult:
  return CombinedRunResult(
      run_id=run_id,
      timestamp="2026-08-04T12:00:00Z",
      model="codex:test",
      provenance=_PROVENANCE,
      cases=tuple(
          CombinedCaseResult(
              case_id=f"case-{index}", evaluation=_evaluation(score))
          for index, score in enumerate(quality_scores, 1)
      ),
  )


def _operational_evaluation() -> OperationalIntegrityEvalResult:
  usage = ModelUsage(
      duration_seconds=1.0, input_tokens=10, output_tokens=20,
      estimated_cost_usd=0.03, executor_version="test-executor-v1",
      prompt_version="test-prompt-v1", prompt_sha256="b" * 64)
  return OperationalIntegrityEvalResult(
      model_first_pass=None,
      repair_rounds=(),
      operational_failure=OperationalFailure(
          phase="initial_load", attempt=0,
          reason_code=ReasonCode.ARTIFACT_MISSING,
          artifact="refs.json", message="required artifact is missing",
          model_usage=usage),
      repair_cost=RepairCost.from_rounds(()),
      robustness=RobustnessResult(
          expected_final_status="invalid", observed_final_status="invalid",
          minimum_repair_rounds=0, maximum_repair_rounds=0,
          expectation_met=True, error=None),
  )


def test_operational_failure_round_trips_through_report_and_dashboard(tmp_path):
  run = CombinedRunResult(
      run_id="run-operational", timestamp="2026-08-04T12:00:00Z",
      model="codex:test",
      provenance=_PROVENANCE, cases=(CombinedCaseResult(
          case_id="case-one", evaluation=_operational_evaluation()),))

  run_path = write_run_report(run, tmp_path)
  selected = load_dashboard_data(tmp_path, "run-operational")
  case = selected["cases"][0]

  assert selected["summary"]["integrity_status_counts"]["invalid"] == 1
  assert case["first_pass"] is None
  assert case["final"] == {
      "quality_score": None, "integrity_score": None, "status": "invalid",
      "workspace_manifest_sha256": None}
  assert case["operational_failure"]["reason_code"] == "artifact_missing"
  summary_row = next(
      line for line in (run_path / "summary.md").read_text().splitlines()
      if line.startswith("| case-one |"))
  assert summary_row.startswith(
      "| case-one | N/A | N/A | N/A | N/A (invalid) |")
  assert "ERROR" not in summary_row


def test_judge_failure_remains_error_in_summary(tmp_path):
  evaluation = _evaluation(81.0)
  failed = replace(
      evaluation.system_final,
      quality=QualityResult.failed("synthetic judge failure"))
  evaluation = replace(evaluation, system_final=failed)
  run = CombinedRunResult(
      run_id="run-judge-failure", timestamp="2026-08-04T12:00:00Z",
      model="codex:test",
      provenance=_PROVENANCE, cases=(CombinedCaseResult(
          case_id="case-one", evaluation=evaluation),))

  run_path = write_run_report(run, tmp_path)
  summary_row = next(
      line for line in (run_path / "summary.md").read_text().splitlines()
      if line.startswith("| case-one |"))

  assert "| ERROR |" in summary_row


def test_two_runs_do_not_share_result_files(tmp_path):
  first_path = write_run_report(_run("run-one", 81.0), tmp_path)
  second_path = write_run_report(_run("run-two", 92.0), tmp_path)

  assert first_path == tmp_path / "runs" / "run-one"
  assert second_path == tmp_path / "runs" / "run-two"
  assert json.loads((first_path / "result.json").read_text())["run_id"] == (
      "run-one")
  assert json.loads((second_path / "result.json").read_text())["run_id"] == (
      "run-two")
  assert (first_path / "artifacts" / "case-1.json").read_bytes() != (
      second_path / "artifacts" / "case-1.json").read_bytes()
  with pytest.raises(FileExistsError):
    write_run_report(_run("run-one", 100.0), tmp_path)


def test_summary_counts_only_selected_run(tmp_path):
  write_run_report(_run("run-one", 81.0, 82.0), tmp_path)
  write_run_report(_run("run-two", 92.0), tmp_path)

  selected = load_dashboard_data(tmp_path, "run-two")

  assert selected["summary"] == {
      "case_count": 1,
      "integrity_status_counts": {
          "valid": 1,
          "valid_with_warnings": 0,
          "invalid": 0,
      },
  }
  assert [case["case_id"] for case in selected["cases"]] == ["case-1"]


def test_combined_report_keeps_quality_and_integrity_separate(tmp_path):
  run_path = write_run_report(_run("run-separated", 81.0), tmp_path)
  report = json.loads((run_path / "result.json").read_text())
  case = report["cases"][0]

  assert case["first_pass"] == {
      "quality_score": 81.0,
      "integrity_score": 100.0,
      "status": "valid",
      "workspace_manifest_sha256": case["first_pass"][
          "workspace_manifest_sha256"],
  }
  assert case["final"] == case["first_pass"]
  assert "overall_score" not in json.dumps(report)
  assert "passed" not in case
  assert case["artifact"] == {
      "path": "artifacts/case-1.json",
      "sha256": case["artifact"]["sha256"],
  }
  assert len(case["artifact"]["sha256"]) == 64


def test_dashboard_data_rejects_unknown_run_id(tmp_path):
  write_run_report(_run("run-known", 81.0), tmp_path)

  with pytest.raises(ValueError, match="unknown run_id"):
    load_dashboard_data(tmp_path, "run-unknown")
  with pytest.raises(ValueError, match="unsafe run_id"):
    load_dashboard_data(tmp_path, "../run-known")


def test_quality_only_history_is_labeled_not_integrity_evaluated(tmp_path):
  history = {
      "schema_version": "2.0",
      "runs": [{
          "run_id": "run_20260728_211624",
          "timestamp": "2026-07-28T21:26:24Z",
          "model": "codex:test",
          "model_version": "test",
          "tests_run": 26,
          "tests_passed": 25,
          "average_score": 88.5,
          "scores_by_agent": {"literature-review": [90.0]},
          "pass_rate": 96.2,
          "detail_file": "test_results_detail/run_20260728_211624.json",
      }],
      "summary_stats": {},
  }

  adapted = adapt_quality_history(history)
  run = adapted["runs"][0]

  assert run["evaluation_kind"] == "quality_only_history"
  assert run["evaluation_label"] == (
      "Quality-only historical run — not integrity evaluated")
  assert run["quality_score"] == 88.5
  assert run["integrity_score"] is None
  assert run["status"] == "not_evaluated"


def test_repository_quality_history_remains_readable():
  history = json.loads((ROOT / "evals/benchmark_overview.json").read_text())

  adapted = adapt_quality_history(history)

  assert len(adapted["runs"]) == len(history["runs"])
  assert all(run["status"] == "not_evaluated" for run in adapted["runs"])
  assert adapted["runs"][-1]["scores_by_capability"] == (
      history["runs"][-1]["scores_by_agent"])


@pytest.mark.parametrize("run_id", ["../run-safe", "run/unsafe", "run-..-x"])
def test_run_ids_cannot_escape_the_runs_directory(run_id):
  with pytest.raises(ValueError, match="unsafe run_id"):
    _run(run_id, 81.0)


def test_run_ids_are_lowercase_for_portable_uniqueness():
  with pytest.raises(ValueError, match="unsafe run_id"):
    _run("run-Case", 81.0)


def test_quality_history_rejects_case_variant_run_ids():
  history = json.loads((ROOT / "evals/benchmark_overview.json").read_text())
  duplicate = dict(history["runs"][0])
  duplicate["run_id"] = "run-Case"
  history["runs"].append(duplicate)

  with pytest.raises(ValueError, match="unsafe run_id"):
    adapt_quality_history(history)


def test_writer_refuses_a_symlink_at_the_selected_run_id(tmp_path):
  runs = tmp_path / "runs"
  runs.mkdir()
  outside = tmp_path / "outside"
  outside.mkdir()
  (runs / "run-linked").symlink_to(outside, target_is_directory=True)

  with pytest.raises(FileExistsError):
    write_run_report(_run("run-linked", 81.0), tmp_path)
  assert tuple(outside.iterdir()) == ()


def test_writer_rejects_a_symlinked_registry_lock(tmp_path):
  runs = tmp_path / "runs"
  runs.mkdir()
  outside = tmp_path / "outside.lock"
  outside.write_text("do not touch")
  (runs / ".index.lock").symlink_to(outside)

  with pytest.raises((OSError, ValueError)):
    write_run_report(_run("run-lock-link", 81.0), tmp_path)
  assert outside.read_text() == "do not touch"


def test_writer_rejects_a_hardlinked_registry_lock(tmp_path):
  runs = tmp_path / "runs"
  runs.mkdir()
  outside = tmp_path / "outside.lock"
  outside.write_text("do not touch")
  os.link(outside, runs / ".index.lock")

  with pytest.raises(ValueError, match="single-link"):
    write_run_report(_run("run-lock-hardlink", 81.0), tmp_path)
  assert outside.read_text() == "do not touch"


def test_dashboard_loader_rejects_symlinked_selected_run(tmp_path):
  run_path = write_run_report(_run("run-linked-load", 81.0), tmp_path)
  outside = tmp_path / "moved-run"
  run_path.rename(outside)
  run_path.symlink_to(outside, target_is_directory=True)

  with pytest.raises(ValueError, match="unknown run_id"):
    load_dashboard_data(tmp_path, "run-linked-load")


def test_dashboard_loader_rejects_a_tampered_task8_artifact(tmp_path):
  run_path = write_run_report(_run("run-tampered", 81.0), tmp_path)
  artifact = run_path / "artifacts" / "case-1.json"
  artifact.write_text(artifact.read_text().replace("81.0", "99.0"))

  with pytest.raises(ValueError, match="SHA-256 mismatch"):
    load_dashboard_data(tmp_path, "run-tampered")


def test_summary_digest_is_committed_in_result_registry_and_publication(tmp_path):
  run_path = write_run_report(_run("run-summary-commitment", 81.0), tmp_path)
  summary_digest = hashlib.sha256((run_path / "summary.md").read_bytes()).hexdigest()
  result = json.loads((run_path / "result.json").read_text())
  registry = json.loads((tmp_path / "runs/index.json").read_text())["runs"][0]
  publication = json.loads((run_path / "publication.json").read_text())

  assert result["schema_version"] == "1.2.0"
  assert result["summary_sha256"] == summary_digest
  assert registry["report_schema_version"] == "1.2.0"
  assert registry["summary_sha256"] == summary_digest
  assert publication["schema_version"] == "1.2.0"
  assert publication["summary_sha256"] == summary_digest


def test_dashboard_loader_rejects_tampered_summary(tmp_path):
  run_path = write_run_report(_run("run-summary-tampered", 81.0), tmp_path)
  summary = run_path / "summary.md"
  summary.write_bytes(summary.read_bytes().replace(b"81.0", b"99.0"))

  with pytest.raises(ValueError, match="summary.*SHA-256"):
    load_dashboard_data(tmp_path, "run-summary-tampered")


def test_run_report_records_provenance(tmp_path):
  run_path = write_run_report(_run("run-provenance", 81.0), tmp_path)

  result = json.loads((run_path / "result.json").read_text())
  assert result["schema_version"] == "1.2.0"
  assert result["provenance"] == _PROVENANCE
  assert f"**Target commit**: {'a' * 40} (clean)" in (
      run_path / "summary.md").read_text()
  assert load_dashboard_data(tmp_path, "run-provenance")[
      "provenance"] == _PROVENANCE


def test_write_run_report_requires_provenance(tmp_path):
  run = CombinedRunResult(
      run_id="run-no-provenance", timestamp="2026-08-04T12:00:00Z",
      model="codex:test",
      cases=(CombinedCaseResult(
          case_id="case-1", evaluation=_evaluation(81.0)),))

  with pytest.raises(ValueError, match="provenance"):
    write_run_report(run, tmp_path)


@pytest.mark.parametrize("change", [
    {"target_commit": "abc"},
    {"target_commit": None},
    {"target_dirty": "no"},
    {"engine_version": ""},
    {"validator_versions": {}},
    {"extra": 1},
])
def test_provenance_rejects_malformed_values(change):
  with pytest.raises(ValueError, match="provenance"):
    CombinedRunResult(
        run_id="run-bad-provenance", timestamp="2026-08-04T12:00:00Z",
        model="codex:test", provenance={**_PROVENANCE, **change},
        cases=(CombinedCaseResult(
            case_id="case-1", evaluation=_evaluation(81.0)),))


def test_provenance_allows_unavailable_git_state():
  run = CombinedRunResult(
      run_id="run-no-git", timestamp="2026-08-04T12:00:00Z",
      model="codex:test",
      provenance={**_PROVENANCE, "target_commit": None, "target_dirty": None},
      cases=(CombinedCaseResult(
          case_id="case-1", evaluation=_evaluation(81.0)),))

  assert run.provenance["target_commit"] is None


def test_pre_provenance_report_still_loads(tmp_path):
  run_path = write_run_report(_run("run-pre-provenance", 81.0), tmp_path)
  summary_path = run_path / "summary.md"
  summary = summary_path.read_text()
  summary = "".join(
      line for line in summary.splitlines(keepends=True)
      if not line.startswith(("**Target commit**", "**Engine**")))
  summary_path.write_text(summary)
  summary_digest = hashlib.sha256(summary.encode()).hexdigest()
  result_path = run_path / "result.json"
  result = json.loads(result_path.read_text())
  result["schema_version"] = "1.1.0"
  result.pop("provenance")
  result["summary_sha256"] = summary_digest
  result_payload = (json.dumps(
      result, indent=2, sort_keys=True) + "\n").encode()
  result_path.write_bytes(result_payload)
  result_digest = hashlib.sha256(result_payload).hexdigest()
  registry_path = tmp_path / "runs/index.json"
  registry = json.loads(registry_path.read_text())
  entry = registry["runs"][0]
  entry["report_schema_version"] = "1.1.0"
  entry["summary_sha256"] = summary_digest
  entry["result_sha256"] = result_digest
  registry_path.write_text(json.dumps(
      registry, indent=2, sort_keys=True) + "\n")
  publication_path = run_path / "publication.json"
  publication = json.loads(publication_path.read_text())
  publication["schema_version"] = "1.1.0"
  publication["summary_sha256"] = summary_digest
  publication["result_sha256"] = result_digest
  publication_path.write_text(json.dumps(
      publication, indent=2, sort_keys=True) + "\n")

  selected = load_dashboard_data(tmp_path, "run-pre-provenance")

  assert selected["schema_version"] == "1.1.0"
  assert "provenance" not in selected


def test_legacy_summary_is_accepted_only_when_deterministically_reconstructed(
    tmp_path,
):
  run_path = write_run_report(_run("run-legacy-summary", 81.0), tmp_path)
  summary_path = run_path / "summary.md"
  summary_path.write_text("".join(
      line for line in summary_path.read_text().splitlines(keepends=True)
      if not line.startswith(("**Target commit**", "**Engine**"))))
  result_path = run_path / "result.json"
  result = json.loads(result_path.read_text())
  result["schema_version"] = "1.0.0"
  result.pop("summary_sha256")
  result.pop("provenance")
  result_payload = (json.dumps(
      result, indent=2, sort_keys=True) + "\n").encode()
  result_path.write_bytes(result_payload)
  result_digest = hashlib.sha256(result_payload).hexdigest()

  registry_path = tmp_path / "runs/index.json"
  registry = json.loads(registry_path.read_text())
  entry = registry["runs"][0]
  entry.pop("report_schema_version")
  entry.pop("summary_sha256")
  entry["result_sha256"] = result_digest
  registry_path.write_text(json.dumps(
      registry, indent=2, sort_keys=True) + "\n")
  publication_path = run_path / "publication.json"
  publication = json.loads(publication_path.read_text())
  publication["schema_version"] = "1.0.0"
  publication.pop("summary_sha256")
  publication["result_sha256"] = result_digest
  publication_path.write_text(json.dumps(
      publication, indent=2, sort_keys=True) + "\n")

  assert load_dashboard_data(tmp_path, "run-legacy-summary")[
      "schema_version"] == "1.0.0"
  (run_path / "summary.md").write_bytes(
      (run_path / "summary.md").read_bytes() + b"tampered\n")
  with pytest.raises(ValueError, match="summary markdown"):
    load_dashboard_data(tmp_path, "run-legacy-summary")


def test_dashboard_loader_couples_case_count_to_registry(tmp_path):
  write_run_report(_run("run-count", 81.0), tmp_path)
  index_path = tmp_path / "runs" / "index.json"
  registry = json.loads(index_path.read_text())
  registry["runs"][0]["case_count"] = 2
  index_path.write_text(json.dumps(registry))

  with pytest.raises(ValueError, match="metadata does not match"):
    load_dashboard_data(tmp_path, "run-count")


def _rewrite_result_and_registry(tmp_path, run_id, mutate):
  result_path = tmp_path / "runs" / run_id / "result.json"
  result = json.loads(result_path.read_text())
  mutate(result)
  payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
  result_path.write_bytes(payload)
  registry_path = tmp_path / "runs" / "index.json"
  registry = json.loads(registry_path.read_text())
  entry = next(item for item in registry["runs"] if item["run_id"] == run_id)
  digest = hashlib.sha256(payload).hexdigest()
  entry["result_sha256"] = digest
  registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
  marker_path = tmp_path / "runs" / run_id / "publication.json"
  marker = json.loads(marker_path.read_text())
  marker["result_sha256"] = digest
  marker_path.write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n")


def test_dashboard_loader_rejects_symlinked_artifact_parent(tmp_path):
  run_path = write_run_report(_run("run-parent-link", 81.0), tmp_path)
  outside = tmp_path / "outside-artifacts"
  (run_path / "artifacts").rename(outside)
  (run_path / "artifacts").symlink_to(outside, target_is_directory=True)

  with pytest.raises(ValueError, match="artifact"):
    load_dashboard_data(tmp_path, "run-parent-link")


def test_dashboard_loader_rejects_hardlinked_artifact(tmp_path):
  run_path = write_run_report(_run("run-hardlink", 81.0), tmp_path)
  artifact = run_path / "artifacts" / "case-1.json"
  second_link = tmp_path / "artifact-hardlink.json"
  os.link(artifact, second_link)

  with pytest.raises(ValueError, match="single-link"):
    load_dashboard_data(tmp_path, "run-hardlink")


def test_dashboard_loader_rejects_noncanonical_artifact_alias(tmp_path):
  run_path = write_run_report(_run("run-alias", 81.0), tmp_path)
  artifact = run_path / "artifacts" / "case-1.json"
  alias = run_path / "artifacts" / "alias.json"
  shutil.copyfile(artifact, alias)
  alias_digest = hashlib.sha256(alias.read_bytes()).hexdigest()
  _rewrite_result_and_registry(
      tmp_path, "run-alias",
      lambda result: result["cases"][0].update(
          artifact={"path": "artifacts/alias.json", "sha256": alias_digest}),
  )

  with pytest.raises(ValueError, match="canonical"):
    load_dashboard_data(tmp_path, "run-alias")


def test_dashboard_loader_rejects_unreferenced_artifact(tmp_path):
  run_path = write_run_report(_run("run-extra-artifact", 81.0), tmp_path)
  (run_path / "artifacts" / "extra.json").write_text("{}\n")

  with pytest.raises(ValueError, match="unexpected"):
    load_dashboard_data(tmp_path, "run-extra-artifact")


def test_dashboard_loader_rejects_oversized_artifact(tmp_path):
  run_path = write_run_report(_run("run-oversized", 81.0), tmp_path)
  artifact = run_path / "artifacts" / "case-1.json"
  payload = artifact.read_bytes() + b" " * (16 * 1024 * 1024)
  artifact.write_bytes(payload)
  digest = hashlib.sha256(payload).hexdigest()
  _rewrite_result_and_registry(
      tmp_path, "run-oversized",
      lambda result: result["cases"][0]["artifact"].update(sha256=digest),
  )

  with pytest.raises(ValueError, match="size limit"):
    load_dashboard_data(tmp_path, "run-oversized")


def test_dashboard_loader_rejects_boolean_summary_counts(tmp_path):
  run_path = write_run_report(_run("run-boolean-count", 81.0), tmp_path)
  result_path = run_path / "result.json"
  result = json.loads(result_path.read_text())
  result["summary"]["case_count"] = True
  result["summary"]["integrity_status_counts"]["valid"] = True
  payload = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
  result_path.write_bytes(payload)
  registry_path = tmp_path / "runs" / "index.json"
  registry = json.loads(registry_path.read_text())
  digest = hashlib.sha256(payload).hexdigest()
  registry["runs"][0]["result_sha256"] = digest
  registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
  marker_path = run_path / "publication.json"
  marker = json.loads(marker_path.read_text())
  marker["result_sha256"] = digest
  marker_path.write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n")

  with pytest.raises(ValueError, match="summary counts"):
    load_dashboard_data(tmp_path, "run-boolean-count")


def test_dashboard_loader_requires_run_id_in_registry(tmp_path):
  known = write_run_report(_run("run-known", 81.0), tmp_path)
  unknown = tmp_path / "runs" / "run-unregistered"
  shutil.copytree(known, unknown)
  result_path = unknown / "result.json"
  result = json.loads(result_path.read_text())
  result["run_id"] = "run-unregistered"
  result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

  with pytest.raises(ValueError, match="unknown run_id"):
    load_dashboard_data(tmp_path, "run-unregistered")


def test_writer_refuses_a_registry_with_unknown_fields(tmp_path):
  write_run_report(_run("run-first", 81.0), tmp_path)
  registry_path = tmp_path / "runs" / "index.json"
  registry = json.loads(registry_path.read_text())
  registry["runs"][0]["overall_score"] = 90.0
  registry_path.write_text(json.dumps(registry))

  with pytest.raises(ValueError, match="unknown fields"):
    write_run_report(_run("run-second", 82.0), tmp_path)
  assert not (tmp_path / "runs" / "run-second").exists()


def test_failed_run_write_leaves_no_partial_run_and_can_retry(
    monkeypatch, tmp_path,
):
  original = run_reports._write_exclusive

  def fail_result(path, payload):
    if path.name == "result.json":
      raise OSError("injected result write failure")
    return original(path, payload)

  monkeypatch.setattr(run_reports, "_write_exclusive", fail_result)
  with pytest.raises(OSError, match="injected result write failure"):
    write_run_report(_run("run-retry-write", 81.0), tmp_path)

  runs = tmp_path / "runs"
  assert not (runs / "run-retry-write").exists()
  assert not list(runs.glob(".run-retry-write-*.tmp"))
  monkeypatch.setattr(run_reports, "_write_exclusive", original)
  assert write_run_report(_run("run-retry-write", 81.0), tmp_path).is_dir()


def test_failed_registry_publication_rolls_back_run_and_registry(
    monkeypatch, tmp_path,
):
  original = run_reports._update_registry

  def publish_then_fail(*args, **kwargs):
    original(*args, **kwargs)
    raise OSError("injected post-registry failure")

  monkeypatch.setattr(run_reports, "_update_registry", publish_then_fail)
  with pytest.raises(OSError, match="injected post-registry failure"):
    write_run_report(_run("run-retry-registry", 81.0), tmp_path)

  runs = tmp_path / "runs"
  assert not (runs / "run-retry-registry").exists()
  if (runs / "index.json").exists():
    registry = json.loads((runs / "index.json").read_text())
    assert registry["runs"] == []
  monkeypatch.setattr(run_reports, "_update_registry", original)
  assert write_run_report(_run("run-retry-registry", 81.0), tmp_path).is_dir()


@pytest.mark.parametrize("post_rename_fsync", [1, 2, 3, 4])
def test_every_post_rename_fsync_failure_rolls_back_and_allows_retry(
    monkeypatch, tmp_path, post_rename_fsync,
):
  original = run_reports.os.fsync
  final = tmp_path / "runs" / "run-fsync-rollback"
  calls = 0
  injected = False

  def fail_selected_fsync(descriptor):
    nonlocal calls, injected
    if final.exists() and not injected:
      calls += 1
      if calls == post_rename_fsync:
        injected = True
        raise OSError(f"injected post-rename fsync {post_rename_fsync}")
    return original(descriptor)

  monkeypatch.setattr(run_reports.os, "fsync", fail_selected_fsync)
  with pytest.raises(OSError, match="injected post-rename fsync"):
    write_run_report(_run("run-fsync-rollback", 81.0), tmp_path)

  assert not final.exists()
  registry_path = tmp_path / "runs" / "index.json"
  if registry_path.exists():
    assert json.loads(registry_path.read_text())["runs"] == []
  monkeypatch.setattr(run_reports.os, "fsync", original)
  assert write_run_report(
      _run("run-fsync-rollback", 81.0), tmp_path) == final


def test_rename_that_completes_then_raises_rolls_back_and_allows_retry(
    monkeypatch, tmp_path,
):
  original = run_reports.os.rename
  injected = False

  def rename_then_fail(*args, **kwargs):
    nonlocal injected
    original(*args, **kwargs)
    if not injected:
      injected = True
      raise OSError("injected completed rename failure")

  monkeypatch.setattr(run_reports.os, "rename", rename_then_fail)
  with pytest.raises(OSError, match="completed rename failure"):
    write_run_report(_run("run-rename-rollback", 81.0), tmp_path)

  final = tmp_path / "runs" / "run-rename-rollback"
  assert not final.exists()
  monkeypatch.setattr(run_reports.os, "rename", original)
  assert write_run_report(_run("run-rename-rollback", 81.0), tmp_path) == final


@pytest.mark.parametrize("registry_phase", ["create", "write", "replace"])
def test_every_registry_replacement_phase_rolls_back_and_allows_retry(
    monkeypatch, tmp_path, registry_phase,
):
  original_open = run_reports.os.open
  original_write = run_reports._write_all
  original_replace = run_reports.os.replace
  injected = False

  def fail_create(path, *args, **kwargs):
    nonlocal injected
    if (not injected and isinstance(path, str)
        and path.startswith(".index-") and path.endswith(".tmp")):
      injected = True
      raise OSError("injected registry create failure")
    return original_open(path, *args, **kwargs)

  def fail_write(*args, **kwargs):
    nonlocal injected
    if not injected:
      injected = True
      raise OSError("injected registry write failure")
    return original_write(*args, **kwargs)

  def fail_replace(*args, **kwargs):
    nonlocal injected
    if not injected:
      injected = True
      raise OSError("injected registry replace failure")
    return original_replace(*args, **kwargs)

  if registry_phase == "create":
    monkeypatch.setattr(run_reports.os, "open", fail_create)
  elif registry_phase == "write":
    monkeypatch.setattr(run_reports, "_write_all", fail_write)
  else:
    monkeypatch.setattr(run_reports.os, "replace", fail_replace)

  with pytest.raises(OSError, match=f"registry {registry_phase} failure"):
    write_run_report(_run("run-registry-phase", 81.0), tmp_path)

  final = tmp_path / "runs" / "run-registry-phase"
  assert not final.exists()
  registry_path = tmp_path / "runs" / "index.json"
  if registry_path.exists():
    assert json.loads(registry_path.read_text())["runs"] == []
  assert write_run_report(_run("run-registry-phase", 81.0), tmp_path) == final


def _leave_process_death_orphan(tmp_path, result):
  payload_path = tmp_path / f"{result.run_id}-input.json"
  payload_path.write_text(json.dumps(result.to_dict()))
  script = r"""
import json
import os
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
from lib import run_reports
payload = run_reports.CombinedRunResult.from_dict(
    json.loads(pathlib.Path(sys.argv[2]).read_text()))
run_reports._update_registry = lambda *args, **kwargs: os._exit(77)
run_reports.write_run_report(payload, pathlib.Path(sys.argv[3]))
"""
  completed = subprocess.run(
      [sys.executable, "-c", script, str(ROOT / "evals"),
       str(payload_path), str(tmp_path)],
      check=False, capture_output=True, text=True)
  assert completed.returncode == 77, completed.stderr
  return tmp_path / "runs" / result.run_id


def test_complete_process_death_orphan_is_recovered_idempotently(tmp_path):
  expected = _run("run-crash-recovery", 81.0)
  orphan = _leave_process_death_orphan(tmp_path, expected)

  assert orphan.is_dir()
  assert not (tmp_path / "runs" / "index.json").exists()
  assert write_run_report(expected, tmp_path) == orphan

  registry = json.loads((tmp_path / "runs" / "index.json").read_text())
  assert [entry["run_id"] for entry in registry["runs"]] == [
      "run-crash-recovery"]
  with pytest.raises(FileExistsError):
    write_run_report(expected, tmp_path)


def test_mismatched_process_death_orphan_fails_closed(tmp_path):
  orphan = _leave_process_death_orphan(
      tmp_path, _run("run-crash-mismatch", 81.0))

  with pytest.raises((FileExistsError, ValueError)):
    write_run_report(_run("run-crash-mismatch", 82.0), tmp_path)

  assert orphan.is_dir()
  assert not (tmp_path / "runs" / "index.json").exists()


@pytest.mark.parametrize("tamper", ["artifact", "marker", "summary"])
def test_process_death_marker_cannot_bypass_full_orphan_validation(
    tmp_path, tamper,
):
  expected = _run(f"run-crash-tampered-{tamper}", 81.0)
  orphan = _leave_process_death_orphan(tmp_path, expected)
  if tamper == "artifact":
    artifact = orphan / "artifacts" / "case-1.json"
    artifact.write_bytes(artifact.read_bytes() + b" ")
  elif tamper == "summary":
    summary = orphan / "summary.md"
    summary.write_bytes(summary.read_bytes() + b"tampered\n")
  else:
    (orphan / "publication.json").unlink()

  with pytest.raises(ValueError, match="unregistered|publication|summary"):
    write_run_report(expected, tmp_path)

  assert orphan.is_dir()
  assert not (tmp_path / "runs" / "index.json").exists()


def test_concurrent_distinct_writers_both_remain_in_registry(
    monkeypatch, tmp_path,
):
  original = run_reports._read_registry
  rendezvous = threading.Barrier(2)
  calls = {}
  calls_lock = threading.Lock()

  def synchronized_read(*args, **kwargs):
    result = original(*args, **kwargs)
    thread_id = threading.get_ident()
    with calls_lock:
      calls[thread_id] = calls.get(thread_id, 0) + 1
      update_read = calls[thread_id] == 2
    if update_read:
      rendezvous.wait(timeout=5)
    return result

  monkeypatch.setattr(run_reports, "_read_registry", synchronized_read)
  outcomes = []

  def worker(run_id, score):
    try:
      outcomes.append(write_run_report(_run(run_id, score), tmp_path))
    except Exception as exc:  # pragma: no cover - asserted below
      outcomes.append(exc)

  threads = [
      threading.Thread(target=worker, args=("run-concurrent-one", 81.0)),
      threading.Thread(target=worker, args=("run-concurrent-two", 82.0)),
  ]
  for thread in threads:
    thread.start()
  for thread in threads:
    thread.join(timeout=10)

  assert all(isinstance(outcome, pathlib.Path) for outcome in outcomes), outcomes
  registry = json.loads((tmp_path / "runs" / "index.json").read_text())
  assert [entry["run_id"] for entry in registry["runs"]] == [
      "run-concurrent-one", "run-concurrent-two"]


def test_concurrent_same_id_has_exactly_one_success(tmp_path):
  start = threading.Barrier(2)
  outcomes = []

  def worker():
    start.wait(timeout=5)
    try:
      outcomes.append(write_run_report(
          _run("run-concurrent-same", 81.0), tmp_path))
    except Exception as exc:
      outcomes.append(exc)

  threads = [threading.Thread(target=worker) for _ in range(2)]
  for thread in threads:
    thread.start()
  for thread in threads:
    thread.join(timeout=10)

  assert sum(isinstance(outcome, pathlib.Path) for outcome in outcomes) == 1
  assert sum(isinstance(outcome, FileExistsError) for outcome in outcomes) == 1, outcomes


def test_concurrent_processes_preserve_both_registry_entries(tmp_path):
  inputs = []
  for run_id, score in (
      ("run-process-one", 81.0), ("run-process-two", 82.0)):
    path = tmp_path / f"{run_id}.json"
    path.write_text(json.dumps(_run(run_id, score).to_dict()))
    inputs.append(path)
  go = tmp_path / "go"
  script = r"""
import json
import pathlib
import sys
import time
sys.path.insert(0, sys.argv[1])
from lib.run_reports import CombinedRunResult, write_run_report
payload = CombinedRunResult.from_dict(json.loads(pathlib.Path(sys.argv[2]).read_text()))
pathlib.Path(sys.argv[3]).write_text('ready')
deadline = time.monotonic() + 10
while not pathlib.Path(sys.argv[4]).exists():
  if time.monotonic() >= deadline:
    raise TimeoutError('process rendezvous timed out')
  time.sleep(0.01)
write_run_report(payload, pathlib.Path(sys.argv[5]))
"""
  processes = []
  ready_paths = []
  for index, input_path in enumerate(inputs):
    ready = tmp_path / f"ready-{index}"
    ready_paths.append(ready)
    processes.append(subprocess.Popen(
        [sys.executable, "-c", script, str(ROOT / "evals"),
         str(input_path), str(ready), str(go), str(tmp_path / "results")],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
  deadline = time.monotonic() + 10
  while not all(path.exists() for path in ready_paths):
    if time.monotonic() >= deadline:
      raise AssertionError("subprocesses did not reach rendezvous")
    time.sleep(0.01)
  go.write_text("go")
  completed = [process.communicate(timeout=15) for process in processes]

  assert [process.returncode for process in processes] == [0, 0], completed
  registry = json.loads(
      (tmp_path / "results" / "runs" / "index.json").read_text())
  assert [entry["run_id"] for entry in registry["runs"]] == [
      "run-process-one", "run-process-two"]


def test_combined_case_deserializes_task8_with_a_closed_schema():
  serialized = _evaluation(81.0).to_dict()
  serialized["overall_score"] = 90.5

  with pytest.raises(ValueError, match="unknown fields"):
    CombinedCaseResult(case_id="case-1", evaluation=serialized)


def test_empty_optional_breakdowns_are_omitted(tmp_path):
  run_path = write_run_report(_run("run-no-breakdown", 81.0), tmp_path)
  case = json.loads((run_path / "result.json").read_text())["cases"][0]

  assert "repair_rounds" not in case
  assert "attack_family" not in case
  assert list((run_path / "repair-rounds").iterdir()) == []


def test_attack_family_breakdown_is_written_only_when_present(tmp_path):
  score = AdversarialCaseScore(
      attack_family="citation-substitution",
      domain="synthetic",
      confusion={
          "true_positive": 1, "false_positive": 0,
          "true_negative": 0, "false_negative": 0},
      reason_metrics={
          "citation_identity_mismatch": ReasonMetric(1, 0, 0, 0)})
  run = CombinedRunResult(
      run_id="run-attacks",
      timestamp="2026-08-04T12:00:00Z",
      model="codex:test",
      provenance=_PROVENANCE,
      cases=(
          CombinedCaseResult(
              case_id="case-one", evaluation=_evaluation(81.0),
              adversarial_score=score),
          CombinedCaseResult(
              case_id="case-two", evaluation=_evaluation(82.0),
              adversarial_score=score),
      ),
  )

  run_path = write_run_report(run, tmp_path)
  selected = load_dashboard_data(tmp_path, "run-attacks")

  assert selected["summary"]["attack_family_breakdown"] == {
      "citation-substitution": 2}
  assert json.loads((run_path / "result.json").read_text())["cases"][0][
      "attack_family"] == "citation-substitution"


def test_summary_reports_rates_by_attack_family_and_domain(tmp_path):
  def score(family, domain, counts):
    return AdversarialCaseScore(
        attack_family=family, domain=domain,
        confusion=dict(zip(("true_positive", "false_positive",
                            "true_negative", "false_negative"), counts)),
        reason_metrics={"fabricated_quote": ReasonMetric(*counts)})
  run = CombinedRunResult(
      run_id="run-rates", timestamp="2026-08-04T12:00:00Z",
      model="codex:test",
      provenance=_PROVENANCE,
      cases=(
          CombinedCaseResult(
              case_id="case-one", evaluation=_evaluation(81.0),
              adversarial_score=score("unicode", "clinical", (1, 0, 1, 0))),
          CombinedCaseResult(
              case_id="case-two", evaluation=_evaluation(82.0),
              adversarial_score=score("unicode", "policy", (0, 1, 1, 1))),
      ),
  )

  write_run_report(run, tmp_path)
  summary = load_dashboard_data(tmp_path, "run-rates")["summary"]

  assert summary["attack_family_confusion"]["unicode"] == {
      "true_positive": 1, "false_positive": 1, "true_negative": 2,
      "false_negative": 1, "precision": 0.5, "recall": 0.5,
      "specificity": 2 / 3}
  assert summary["domain_confusion"] == {
      "clinical": ReasonMetric(1, 0, 1, 0).to_dict(),
      "policy": ReasonMetric(0, 1, 1, 1).to_dict(),
  }


def test_combined_case_rejects_caller_supplied_attack_family():
  with pytest.raises(TypeError):
    CombinedCaseResult(
        case_id="case-one", evaluation=_evaluation(81.0),
        attack_family="citation-substitution")

  serialized = {
      "case_id": "case-one", "evaluation": _evaluation(81.0).to_dict(),
      "attack_family": "citation-substitution",
  }
  with pytest.raises(ValueError, match="unknown fields"):
    CombinedCaseResult.from_dict(serialized)


def test_integrity_cli_mode_uses_the_isolated_report_writer(
    monkeypatch, tmp_path,
):
  cases = (SimpleNamespace(case_id="case-one", domain="synthetic"),)

  class FakeRunner:
    def __init__(self, *args, **kwargs):
      pass

    def run_case(self, case):
      assert case is cases[0]
      return _evaluation(81.0)

  monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
  monkeypatch.setattr(run_eval, "generate_run_id", lambda: "run-cli")
  monkeypatch.setattr(literature_integrity, "load_cases", lambda _path: cases)
  monkeypatch.setattr(
      literature_integrity, "LiteratureIntegrityRunner", FakeRunner)
  monkeypatch.setattr(
      literature_integrity, "ProductionModelExecutor", lambda *args: object())
  monkeypatch.setattr(
      literature_integrity, "ProductionQualityJudge", lambda *args: object())
  monkeypatch.setattr(
      literature_integrity, "load_adversarial_scores",
      lambda *args, domains: {})

  results = run_eval.run_literature_integrity("codex:test")

  assert results == (_evaluation(81.0),)
  selected = load_dashboard_data(tmp_path, "run-cli")
  assert selected["summary"]["case_count"] == 1
  head = subprocess.run(
      ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
      capture_output=True, text=True, check=True).stdout.strip()
  assert selected["provenance"]["target_commit"] == head
  assert isinstance(selected["provenance"]["target_dirty"], bool)
  assert selected["provenance"]["engine_version"] == "1.0.0"
  assert not (tmp_path / "literature-review-integrity").exists()


class _ScriptCollector(HTMLParser):
  def __init__(self):
    super().__init__()
    self._inside = False
    self._chunks = []
    self.scripts = []

  def handle_starttag(self, tag, attrs):
    if tag == "script" and not dict(attrs).get("src"):
      self._inside = True
      self._chunks = []

  def handle_data(self, data):
    if self._inside:
      self._chunks.append(data)

  def handle_endtag(self, tag):
    if tag == "script" and self._inside:
      self.scripts.append("".join(self._chunks))
      self._inside = False


def test_dashboard_parser_selects_one_integrity_run_without_network(tmp_path):
  collector = _ScriptCollector()
  collector.feed((ROOT / "evals/index.html").read_text())
  main_script = next(
      script for script in collector.scripts if "GITHUB_RAW_URL" in script)
  script_path = tmp_path / "dashboard-main.js"
  script_path.write_text(main_script)
  driver = r"""
    const fs = require('fs');
    const { webcrypto } = require('crypto');
    const vm = require('vm');
    const classes = new Set();
    const elements = {
      integrityRunFilter: {
        value: '../bad', disabled: false, innerHTML: '',
        setAttribute(name, value) { this[name] = value; },
        removeAttribute(name) { delete this[name]; },
      },
      integrityRunSummary: {
        textContent: 'stale summary',
        classList: { toggle(name, active) {
          if (active) classes.add(name); else classes.delete(name);
        }},
      },
      integrityRunCases: { innerHTML: 'stale cases' },
      integrityEvaluationLabel: { textContent: 'stale label' },
      firstPassToggle: { disabled: false, classList: { toggle() {} } },
      finalToggle: { disabled: false, classList: { toggle() {} } },
    };
    const context = {
      window: { addEventListener() {}, location: {search: ''} },
      document: { body: {}, getElementById(id) { return elements[id]; } },
      crypto: webcrypto,
      TextDecoder,
      URLSearchParams,
      console,
    };
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
    const report = {
      schema_version: '1.0.0',
      evaluation_kind: 'quality_and_integrity',
      evaluation_label: 'Paired quality and integrity evaluation',
      run_id: 'run-selected',
      timestamp: '2026-08-04T12:00:00Z',
      model: 'codex:test',
      capability: 'literature-review-integrity',
      summary: {case_count: 1, integrity_status_counts: {
        valid: 1, valid_with_warnings: 0, invalid: 0}},
      cases: [{
        case_id: 'case-1',
        first_pass: {quality_score: 81, integrity_score: 72,
          status: 'valid_with_warnings', workspace_manifest_sha256: 'a'.repeat(64)},
        final: {quality_score: 91, integrity_score: 100,
          status: 'valid', workspace_manifest_sha256: 'b'.repeat(64)},
        artifact: {path: 'artifacts/case-1.json', sha256: 'c'.repeat(64)},
      }],
    };
    const entry = {
      run_id: 'run-selected', timestamp: report.timestamp, model: report.model,
      capability: report.capability, evaluation_kind: report.evaluation_kind,
      evaluation_label: report.evaluation_label, case_count: 1,
      result_file: 'run-selected/result.json', result_sha256: 'f'.repeat(64),
    };
    const selected = context.parseIntegrityRunData(report, entry);
    if (selected.summary.case_count !== 1) process.exit(2);
    if (selected.cases[0].first_pass.quality_score !== 81) process.exit(3);
    if (selected.cases[0].final.integrity_score !== 100) process.exit(4);
    const committedEntry = {...entry, report_schema_version: '1.1.0',
      summary_sha256: 'e'.repeat(64)};
    const v11 = {...JSON.parse(JSON.stringify(report)), schema_version: '1.1.0',
      summary_sha256: 'e'.repeat(64)};
    context.parseIntegrityRunData(v11, committedEntry);
    const provenance = {target_commit: 'a'.repeat(40), target_dirty: false,
      engine_version: '1.0.0', validator_versions: {claims: '1.0.0'}};
    const v12Entry = {...committedEntry, report_schema_version: '1.2.0'};
    const v12 = {...v11, schema_version: '1.2.0', provenance};
    context.parseIntegrityRunData(v12, v12Entry);
    try {
      context.parseIntegrityRunData(
        {...v12, provenance: {...provenance, target_commit: 'abc'}}, v12Entry);
      process.exit(30);
    } catch (error) {
      if (!String(error).includes('provenance')) process.exit(31);
    }
    try {
      context.parseIntegrityRunData(v11, v12Entry);
      process.exit(32);
    } catch (error) {
      if (!String(error).includes('summary commitment')) process.exit(33);
    }
    try {
      context.parseIntegrityRunData({...v11, provenance}, committedEntry);
      process.exit(34);
    } catch (error) {
      if (!String(error).includes('closed schema')) process.exit(35);
    }
    const traversal = JSON.parse(JSON.stringify(report));
    traversal.cases[0].artifact.path = '../case-1.json';
    try {
      context.parseIntegrityRunData(traversal, entry);
      process.exit(11);
    } catch (error) {
      if (!String(error).includes('artifact reference')) process.exit(12);
    }
    try {
      context.parseIntegrityRunData(report, {...entry,
        run_id: 'run-unknown', result_file: 'run-unknown/result.json'});
      process.exit(5);
    } catch (error) {
      if (!String(error).includes('unknown run ID')) process.exit(6);
    }
    const withBreakdown = JSON.parse(JSON.stringify(report));
    withBreakdown.cases[0].attack_family = 'citation-substitution';
    withBreakdown.cases[0].adversarial_score = {
      schema_version: '3.0.0', attack_family: 'citation-substitution',
      domain: 'synthetic',
      confusion: {true_positive: 1, false_positive: 0,
        true_negative: 0, false_negative: 0},
      reason_metrics: {citation_identity_mismatch: {
        true_positive: 1, false_positive: 0,
        true_negative: 0, false_negative: 0,
        precision: 1, recall: 1, specificity: null,
      }},
    };
    withBreakdown.cases[0].repair_rounds = [{
      attempt: 1, integrity_score: 100, status: 'valid', action: 'pass',
      path: 'repair-rounds/case-1-round-01.json', sha256: 'd'.repeat(64),
    }];
    withBreakdown.summary.attack_family_breakdown = {'citation-substitution': 1};
    withBreakdown.summary.attack_family_confusion = {'citation-substitution': {
      true_positive: 1, false_positive: 0,
      true_negative: 0, false_negative: 0,
      precision: 1, recall: 1, specificity: null,
    }};
    withBreakdown.summary.domain_confusion = {synthetic: {
      true_positive: 1, false_positive: 0,
      true_negative: 0, false_negative: 0,
      precision: 1, recall: 1, specificity: null,
    }};
    withBreakdown.summary.reason_code_metrics = {citation_identity_mismatch: {
      true_positive: 1, false_positive: 0,
      true_negative: 0, false_negative: 0,
      precision: 1, recall: 1, specificity: null,
    }};
    context.parseIntegrityRunData(withBreakdown, entry);
    withBreakdown.cases[0].repair_rounds[0].overall_score = 100;
    try {
      context.parseIntegrityRunData(withBreakdown, entry);
      process.exit(9);
    } catch (error) {
      if (!String(error).includes('closed schema')) process.exit(10);
    }
    const historical = context.adaptQualityOnlyHistory({
      run_id: 'run_history', average_score: 88.5,
    });
    if (historical.integrity_score !== null) process.exit(7);
    if (historical.status !== 'not_evaluated') process.exit(8);

    const falseCounts = JSON.parse(JSON.stringify(report));
    falseCounts.summary.integrity_status_counts = {
      valid: 0, valid_with_warnings: 0, invalid: 1,
    };
    try {
      context.parseIntegrityRunData(falseCounts, entry);
      process.exit(13);
    } catch (error) {
      if (!String(error).includes('summary')) process.exit(14);
    }
    try {
      context.parseIntegrityRunData(report, {...entry, model: 'other:model'});
      process.exit(15);
    } catch (error) {
      if (!String(error).includes('metadata')) process.exit(16);
    }
    try {
      context.adaptQualityOnlyHistory({run_id: 'run-Case', average_score: 88.5});
      process.exit(17);
    } catch (error) {
      if (!String(error).includes('unsafe')) process.exit(18);
    }

    (async () => {
      const bytes = Buffer.from(JSON.stringify(report));
      const response = {ok: true, async arrayBuffer() {
        return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
      }};
      try {
        await context.parseIntegrityRunResponse(entry, response);
        process.exit(19);
      } catch (error) {
        if (!String(error).includes('SHA-256')) process.exit(20);
      }
      await context.handleIntegrityRunChange();
      if (elements.integrityRunCases.innerHTML !== '') process.exit(21);
      if (!classes.has('integrity-run-error')) process.exit(22);
      if (!elements.integrityRunSummary.textContent.includes('unsafe')) process.exit(23);

      const makeReport = (runId, caseId) => {
        const value = JSON.parse(JSON.stringify(report));
        value.run_id = runId;
        value.cases[0].case_id = caseId;
        value.cases[0].artifact.path = `artifacts/${caseId}.json`;
        return value;
      };
      const one = makeReport('run-one', 'case-one');
      const two = makeReport('run-two', 'case-two');
      const makeEntry = async value => {
        const payload = Buffer.from(JSON.stringify(value));
        const digest = await webcrypto.subtle.digest(
          'SHA-256', payload.buffer.slice(
            payload.byteOffset, payload.byteOffset + payload.byteLength));
        return {
          run_id: value.run_id, timestamp: value.timestamp, model: value.model,
          capability: value.capability, evaluation_kind: value.evaluation_kind,
          evaluation_label: value.evaluation_label, case_count: 1,
          result_file: `${value.run_id}/result.json`,
          result_sha256: Buffer.from(digest).toString('hex'),
        };
      };
      const responseFor = value => {
        const payload = Buffer.from(JSON.stringify(value));
        return {ok: true, async arrayBuffer() {
          return payload.buffer.slice(
            payload.byteOffset, payload.byteOffset + payload.byteLength);
        }};
      };
      const entries = [await makeEntry(one), await makeEntry(two)];
      context.fetch = async url => {
        if (url === 'results/runs/index.json') {
          return {ok: true, async json() {
            return {schema_version: '1.0.0', runs: entries};
          }};
        }
        return responseFor(two);
      };
      await context.loadIntegrityRunIndex();

      let settleOld;
      context.fetch = url => {
        if (url.includes('run-one')) {
          return new Promise((resolve, reject) => { settleOld = {resolve, reject}; });
        }
        return Promise.resolve(responseFor(two));
      };
      elements.integrityRunFilter.value = 'run-one';
      const oldSuccess = context.handleIntegrityRunChange();
      elements.integrityRunFilter.value = 'run-two';
      await context.handleIntegrityRunChange();
      settleOld.resolve(responseFor(one));
      await oldSuccess;
      if (!elements.integrityRunCases.innerHTML.includes('case-two')) process.exit(25);
      if (elements.integrityRunCases.innerHTML.includes('case-one')) process.exit(26);

      elements.integrityRunFilter.value = 'run-one';
      const oldFailure = context.handleIntegrityRunChange();
      elements.integrityRunFilter.value = 'run-two';
      await context.handleIntegrityRunChange();
      settleOld.reject(new Error('late old failure'));
      await oldFailure;
      if (!elements.integrityRunCases.innerHTML.includes('case-two')) process.exit(27);
      if (classes.has('integrity-run-error')) process.exit(28);
    })().catch(error => {
      console.error(error);
      process.exit(24);
    });
  """

  completed = subprocess.run(
      ["node", "-e", driver, str(script_path)],
      check=False, capture_output=True, text=True)

  assert completed.returncode == 0, completed.stderr


def test_dashboard_parser_accepts_real_attack_and_operational_unions(tmp_path):
  score = AdversarialCaseScore(
      attack_family="citation-substitution",
      domain="synthetic",
      confusion={
          "true_positive": 1, "false_positive": 0,
          "true_negative": 1, "false_negative": 0},
      reason_metrics={
          "citation_identity_mismatch": ReasonMetric(1, 0, 1, 0)})
  attack = CombinedRunResult(
      run_id="run-browser-attack", timestamp="2026-08-04T12:00:00Z",
      model="codex:test",
      provenance=_PROVENANCE, cases=(CombinedCaseResult(
          case_id="case-attack", evaluation=_evaluation(81.0),
          adversarial_score=score),))
  operational = CombinedRunResult(
      run_id="run-browser-operational", timestamp="2026-08-04T12:00:00Z",
      model="codex:test",
      provenance=_PROVENANCE, cases=(CombinedCaseResult(
          case_id="case-operational",
          evaluation=_operational_evaluation()),))
  payloads = []
  for run in (attack, operational):
    run_path = write_run_report(run, tmp_path / "browser-results")
    registry = json.loads(
        (tmp_path / "browser-results/runs/index.json").read_text())
    payloads.append({
        "result_text": (run_path / "result.json").read_text(),
        "summary_text": (run_path / "summary.md").read_text(),
        "report": json.loads((run_path / "result.json").read_text()),
        "entry": next(item for item in registry["runs"]
                      if item["run_id"] == run.run_id),
    })
  fixture_path = tmp_path / "real-report-unions.json"
  fixture_path.write_text(json.dumps(payloads), encoding="utf-8")

  collector = _ScriptCollector()
  collector.feed((ROOT / "evals/index.html").read_text())
  main_script = next(
      script for script in collector.scripts if "GITHUB_RAW_URL" in script)
  script_path = tmp_path / "dashboard-unions.js"
  script_path.write_text(main_script, encoding="utf-8")
  driver = r"""
    const fs = require('fs');
    const {webcrypto} = require('crypto');
    const vm = require('vm');
    const elements = {
      integrityRunSummary: {innerHTML: '', textContent: '',
        classList: {toggle() {}}},
      integrityRunCases: {innerHTML: 'stale'},
      integrityEvaluationLabel: {textContent: ''},
      firstPassToggle: {classList: {toggle() {}}},
      finalToggle: {classList: {toggle() {}}},
    };
    const context = {
      window: {addEventListener() {}, location: {search: ''}},
      document: {body: {}, getElementById(id) { return elements[id]; }},
      URLSearchParams, TextDecoder, console, crypto: webcrypto,
    };
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
    const fixtures = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
    const attack = context.parseIntegrityRunData(
      fixtures[0].report, fixtures[0].entry);
    if (attack.cases[0].adversarial_score.schema_version !== '3.0.0') {
      process.exit(2);
    }
    const operational = context.parseIntegrityRunData(
      fixtures[1].report, fixtures[1].entry);
    context.fixture = operational;
    vm.runInContext("selectedIntegrityRun = fixture; integritySnapshot = 'final'; renderIntegrityRun();", context);
    if (!elements.integrityRunCases.innerHTML.includes('N/A') ||
        elements.integrityRunCases.innerHTML.includes('stale')) process.exit(3);
    vm.runInContext("integritySnapshot = 'first_pass'; renderIntegrityRun();", context);
    if (!elements.integrityRunCases.innerHTML.includes('N/A')) process.exit(4);

    const mixed = JSON.parse(JSON.stringify(fixtures[0].report));
    mixed.cases[0].operational_failure =
      fixtures[1].report.cases[0].operational_failure;
    try {
      context.parseIntegrityRunData(mixed, fixtures[0].entry);
      process.exit(5);
    } catch (error) {
      if (!String(error).includes('union')) process.exit(6);
    }
    const missingFailure = JSON.parse(JSON.stringify(fixtures[1].report));
    delete missingFailure.cases[0].operational_failure;
    try {
      context.parseIntegrityRunData(missingFailure, fixtures[1].entry);
      process.exit(7);
    } catch (error) {
      if (!String(error).includes('union')) process.exit(8);
    }
    const responseFor = text => {
      const payload = Buffer.from(text);
      return {ok: true, async arrayBuffer() {
        return payload.buffer.slice(
          payload.byteOffset, payload.byteOffset + payload.byteLength);
      }};
    };
    (async () => {
      await context.parseIntegrityRunResponse(
        fixtures[0].entry, responseFor(fixtures[0].result_text),
        responseFor(fixtures[0].summary_text));
      try {
        await context.parseIntegrityRunResponse(
          fixtures[0].entry, responseFor(fixtures[0].result_text),
          responseFor(fixtures[0].summary_text + 'tampered'));
        process.exit(9);
      } catch (error) {
        if (!String(error).includes('summary SHA-256')) process.exit(10);
      }
    })().catch(error => { console.error(error); process.exit(11); });
  """
  completed = subprocess.run(
      ["node", "-e", driver, str(script_path), str(fixture_path)],
      check=False, capture_output=True, text=True)
  assert completed.returncode == 0, completed.stderr
