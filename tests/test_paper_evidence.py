import json
import pathlib
import subprocess
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI = ROOT / "skills/literature-review/scripts/validate_review.py"
EVIDENCE = ROOT / "evals/published/paper"
COUNTEREXAMPLES = ("polarity-reversal", "uncited-qualitative",
                   "background-role", "number-swap")
CAUGHT = {"polarity-reversal": "claim_needs_review",
          "number-swap": "coverage_number_missing"}


def _validate(workspace, tmp_path, returncode=0):
  output = tmp_path / "report.json"
  completed = subprocess.run(
      [sys.executable, str(CLI), "--workspace", str(workspace),
       "--synthetic-fixture", "--output", str(output)],
      capture_output=True, text=True, check=False)
  assert completed.returncode == returncode, completed.stdout + completed.stderr
  return json.loads(output.read_text())


@pytest.mark.parametrize("name", ("base",) + tuple(
    name for name in COUNTEREXAMPLES if name not in CAUGHT))
def test_counterexample_workspaces_pass_the_gate(name, tmp_path):
  report = _validate(EVIDENCE / "counterexamples" / name, tmp_path)

  assert report["status"] == "valid"
  assert report["integrity_score"] == 100.0
  assert report["findings"] == []


@pytest.mark.parametrize("name, reason_code", CAUGHT.items())
def test_fixed_counterexample_no_longer_passes(name, reason_code, tmp_path):
  report = _validate(EVIDENCE / "counterexamples" / name, tmp_path, 1)

  assert report["status"] == "invalid"
  assert reason_code in report["repair_feedback"]["reason_codes"]


@pytest.mark.parametrize("name", COUNTEREXAMPLES)
def test_counterexample_reports_match_their_workspaces(name, tmp_path):
  report = _validate(EVIDENCE / "counterexamples" / name, tmp_path,
                     int(name in CAUGHT))
  saved = json.loads(
      (EVIDENCE / "counterexamples" / f"{name}-report.json").read_text())

  assert report["workspace_manifest_sha256"] == saved["workspace_manifest_sha256"]


def test_table6_script_reproduces_the_paper_values():
  completed = subprocess.run(
      [sys.executable, str(EVIDENCE / "rejudge/table6.py")],
      capture_output=True, text=True, check=True)
  values = json.loads(completed.stdout)

  assert values["texts"] == 15
  assert values["judgments_per_text"] == [4, 8]
  assert values["pooled_sd"] == 9.6
  assert values["median_range"] == 18.6
  assert values["max_range"] == 38.5
  assert values["clean_control"] == {
      "judgments": 6, "sd": 1.0, "range": 2.9, "chars": 5090}
