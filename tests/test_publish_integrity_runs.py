import json
import pathlib
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

from lib.run_reports import (  # noqa: E402
    load_dashboard_data,
    publish_runs,
    write_run_report,
)
from test_eval_run_reports import _run  # noqa: E402


def _index(root):
  return json.loads((root / "runs/index.json").read_text())["runs"]


def test_publish_copies_only_selected_runs_and_they_still_validate(tmp_path):
  source, published = tmp_path / "results", tmp_path / "published"
  write_run_report(_run("run-one", 81.0), source)
  write_run_report(_run("run-two", 92.0), source)

  publish_runs(source, published, ["run-two"])

  assert [entry["run_id"] for entry in _index(published)] == ["run-two"]
  assert not (published / "runs/run-one").exists()
  assert load_dashboard_data(published, "run-two")["run_id"] == "run-two"


def test_publishing_again_merges_into_a_sorted_index(tmp_path):
  source, published = tmp_path / "results", tmp_path / "published"
  write_run_report(_run("run-one", 81.0), source)
  write_run_report(_run("run-two", 92.0), source)

  publish_runs(source, published, ["run-two"])
  publish_runs(source, published, ["run-one"])

  assert [entry["run_id"] for entry in _index(published)] == [
      "run-one", "run-two"]
  assert load_dashboard_data(published, "run-one")["run_id"] == "run-one"


def test_publish_refuses_a_run_containing_forbidden_text(tmp_path):
  source, published = tmp_path / "results", tmp_path / "published"
  run = _run("run-one", 81.0)
  write_run_report(run, source)

  with pytest.raises(ValueError, match="local path"):
    publish_runs(source, published, ["run-one"], forbidden_text=(run.model,))

  assert not (published / "runs/run-one").exists()


def test_publish_rejects_an_unknown_run(tmp_path):
  source, published = tmp_path / "results", tmp_path / "published"
  write_run_report(_run("run-one", 81.0), source)

  with pytest.raises(ValueError, match="unknown run_id"):
    publish_runs(source, published, ["run-missing"])


def test_failed_validation_leaves_no_published_entry(tmp_path, monkeypatch):
  from lib import run_reports
  source, published = tmp_path / "results", tmp_path / "published"
  write_run_report(_run("run-one", 81.0), source)
  original = run_reports.load_dashboard_data

  def fail_on_published(root, run_id):
    if pathlib.Path(root) == published:
      raise ValueError("published copy is invalid")
    return original(root, run_id)

  monkeypatch.setattr(run_reports, "load_dashboard_data", fail_on_published)
  with pytest.raises(ValueError, match="published copy is invalid"):
    publish_runs(source, published, ["run-one"])

  assert not (published / "runs/run-one").exists()
  assert _index(published) == []


def test_publish_command_publishes_named_runs(tmp_path, capsys):
  import publish_integrity_runs
  source, published = tmp_path / "results", tmp_path / "published"
  write_run_report(_run("run-one", 81.0), source)

  assert publish_integrity_runs.main([
      "--source", str(source), "--published", str(published), "run-one"]) == 0
  assert [entry["run_id"] for entry in _index(published)] == ["run-one"]
  assert "run-one" in capsys.readouterr().out


def test_publish_command_reports_refusals_without_a_traceback(tmp_path, capsys):
  import publish_integrity_runs
  source, published = tmp_path / "results", tmp_path / "published"
  write_run_report(_run("run-one", 81.0), source)

  assert publish_integrity_runs.main([
      "--source", str(source), "--published", str(published), "run-missing"]) == 1
  assert "unknown run_id" in capsys.readouterr().err
