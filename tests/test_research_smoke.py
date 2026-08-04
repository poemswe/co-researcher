# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytest",
# ]
# ///

"""Offline end-to-end smoke checks for the local research workflow."""

import json
import os
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECK_CLAIMS = ROOT / "skills/literature-review/scripts/check_claims.py"
PRISMA_COUNTS = ROOT / "skills/literature-review/scripts/prisma_counts.py"
VALIDATE_REVIEW = ROOT / "skills/literature-review/scripts/validate_review.py"
LITERATURE_REVIEW_SKILL = ROOT / "skills/literature-review/SKILL.md"
PUBLIC_ALTERED_NUMBER_SCENARIO = (
    ROOT / "evals/test-cases/literature-review-integrity/synthetic-attacks/"
    "integrity-case-008/input.json")
INVALID_WARNING = (
    "INVALID EVIDENCE — This draft contains unresolved evidence-integrity "
    "failures\nand must not be treated as verified research."
)


def _run(script, *args):
  return subprocess.run(
      [sys.executable, str(script), *map(str, args)],
      cwd=ROOT,
      capture_output=True,
      text=True,
      check=False,
  )


def _write_fixture(tmp_path):
  workspace = tmp_path / "review" / "structured-exercise-readmissions"
  paper = workspace / "papers" / "p1"
  paper.mkdir(parents=True)
  (paper / "fulltext.md").write_text(
      "# Structured Exercise and Readmissions\n\n"
      "Thirty-day readmissions fell 18% in the treatment arm relative to "
      "usual care after discharge from hospital.",
      encoding="utf-8",
  )
  claims = tmp_path / "claims.json"
  claims.write_text(json.dumps([{
      "claim": "Readmissions fell 18% in the treatment arm.",
      "paper_id": "p1",
      "citation": "Patel, 2022",
      "supporting_quote": (
          "Thirty-day readmissions fell 18% in the treatment arm relative "
          "to usual care after discharge from hospital."),
      "role": "evidence",
  }]), encoding="utf-8")
  synthesis = tmp_path / "synthesis.md"
  synthesis.write_text(
      "Readmissions fell 18% in the treatment arm (Patel, 2022).\n",
      encoding="utf-8",
  )
  corpus = workspace / "corpus.json"
  corpus.write_text(json.dumps([{
      "key": "p1",
      "ids": {"paper_id": "p1"},
      "authors": ["Patel"],
      "year": 2022,
      "role": "evidence",
      "found_via": "openalex",
      "fulltext": "fulltext",
      "screening": {"status": "included", "reason": None},
  }, {
      "key": "p2",
      "ids": {"paper_id": "p2"},
      "role": "background",
      "found_via": "europepmc",
      "fulltext": "abstract-only",
      "screening": {"status": "excluded", "reason": "wrong population"},
  }]), encoding="utf-8")
  return workspace, claims, synthesis, corpus


def _write_public_altered_number_fixture(tmp_path):
  """Materialize only the public altered-number scenario for CLI smoke."""
  scenario = json.loads(PUBLIC_ALTERED_NUMBER_SCENARIO.read_text(
      encoding="utf-8"))
  workspace = tmp_path / "review" / "altered-number"
  payloads = {
      "project.json": {"project": "offline-public-smoke"},
      "protocol.md": "# Synthetic protocol\n",
      "corpus.json": scenario["corpus"],
      "claims.json": scenario["claims"],
      "synthesis.md": scenario["synthesis"],
      "refs.json": scenario["references"],
  }
  for paper_id, source in scenario["sources"].items():
    payloads[f"papers/{paper_id}/fulltext.md"] = source
  for relative, value in payloads.items():
    destination = workspace / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        value if isinstance(value, str) else json.dumps(value),
        encoding="utf-8")
  return workspace


def test_offline_research_workflow_smoke(tmp_path):
  workspace, claims, synthesis, corpus = _write_fixture(tmp_path)

  claims_run = _run(
      CHECK_CLAIMS, "--claims", claims, "--workspace", workspace,
      "--synthesis", synthesis)
  assert claims_run.returncode == 0, claims_run.stderr
  claims_output = json.loads(claims_run.stdout)
  assert claims_output["verified"] == 1
  assert claims_output["uncovered_claim"] == 0

  prisma_run = _run(PRISMA_COUNTS, "--corpus", corpus)
  assert prisma_run.returncode == 0, prisma_run.stderr
  prisma_output = json.loads(prisma_run.stdout)
  assert prisma_output["after_dedup"] == 2
  assert prisma_output["included"] == 1
  assert prisma_output["in_synthesis"] == 1

  project_dir = tmp_path / "research" / "structured-exercise-readmissions"
  project_dir.mkdir(parents=True)
  (project_dir / "project.json").write_text(json.dumps({
      "question": "Does structured exercise reduce hospital readmissions?",
      "methodology": "systematic review",
      "phase": "scoping",
      "decisions": [{"decision": "Initialize smoke-test scaffold.",
                     "why": "Verify resumable project state."}],
      "next_action": "Define inclusion criteria.",
  }), encoding="utf-8")
  (project_dir / "research-tasks.md").write_text(
      "- [ ] Define inclusion criteria.\n", encoding="utf-8")
  project = json.loads((project_dir / "project.json").read_text())
  assert project["question"]
  assert project["phase"] == "scoping"
  assert project["decisions"]
  assert project["next_action"]
  assert (project_dir / "research-tasks.md").is_file()


def test_codex_smoke_skips_without_opt_in():
  script = ROOT / "scripts/codex_smoke_research.py"
  result = subprocess.run(
      [sys.executable, str(script)], cwd=ROOT, capture_output=True, text=True,
      env={key: value for key, value in os.environ.items()
           if key != "CO_RESEARCHER_CODEX_SMOKE"}, check=False)
  assert result.returncode == 0
  assert "skipped" in result.stdout.lower()


def test_literature_review_delivery_validation_smoke(tmp_path):
  workspace, claims, synthesis, _corpus = _write_fixture(tmp_path)
  (workspace / "protocol.md").write_text("# Protocol\n", encoding="utf-8")
  (workspace / "claims.json").write_bytes(claims.read_bytes())
  (workspace / "synthesis.md").write_bytes(synthesis.read_bytes())
  (workspace / "refs.json").write_text("[]", encoding="utf-8")
  (workspace / "project.json").write_text(
      json.dumps({"project": "smoke"}), encoding="utf-8")
  run_report = tmp_path / "literature-review-run.json"

  result = _run(
      VALIDATE_REVIEW, "--workspace", workspace,
      "--run-report", run_report)

  assert result.returncode == 0, result.stderr
  report = json.loads(result.stdout)
  assert report["integrity_score"] == 100.0
  assert report["status"] == "valid"
  assert report["action"] == "pass"
  assert report["repair_feedback"] == {
      "reason_codes": [], "affected_artifacts": [], "findings": []}
  ledger = json.loads(run_report.read_text(encoding="utf-8"))
  assert ledger["action"] == "pass"
  assert ledger["repairs"] == []


def test_literature_review_altered_number_smoke_is_invalid(tmp_path):
  workspace = _write_public_altered_number_fixture(tmp_path)
  run_report = tmp_path / "altered-number-run.json"

  result = _run(
      VALIDATE_REVIEW, "--workspace", workspace,
      "--run-report", run_report)

  assert result.returncode == 1, result.stderr
  report = json.loads(result.stdout)
  assert report["status"] == "invalid"
  assert "coverage_number_missing" in {
      finding["reason_code"] for finding in report["findings"]}


def test_literature_review_invalid_repair_sequence_smoke(tmp_path):
  workspace, claims, synthesis, _corpus = _write_fixture(tmp_path)
  claims_payload = json.loads(claims.read_text(encoding="utf-8"))
  claims_payload[0]["supporting_quote"] = (
      "This invented supporting passage is long enough for validation but "
      "does not occur anywhere in the retained source text.")
  (workspace / "protocol.md").write_text("# Protocol\n", encoding="utf-8")
  (workspace / "claims.json").write_text(
      json.dumps(claims_payload), encoding="utf-8")
  (workspace / "synthesis.md").write_bytes(synthesis.read_bytes())
  (workspace / "refs.json").write_text("[]", encoding="utf-8")
  (workspace / "project.json").write_text(
      json.dumps({"project": "smoke"}), encoding="utf-8")
  run_report = tmp_path / "literature-review-run.json"

  actions = []
  for index in range(3):
    if index:
      (workspace / "protocol.md").write_text(
          f"# Protocol\n\nRepair {index} changed files but not evidence.\n",
          encoding="utf-8")
    result = _run(
        VALIDATE_REVIEW, "--workspace", workspace,
        "--run-report", run_report)
    assert result.returncode == 1, result.stderr
    actions.append(json.loads(result.stdout)["action"])

  assert actions == ["repair", "repair", "stop_invalid"]
  ledger = json.loads(run_report.read_text(encoding="utf-8"))
  assert len(ledger["repairs"]) == 2
  assert ledger["action"] == "repair"
  assert ledger["repairs"][-1]["action"] == "stop_invalid"


def test_literature_review_skill_pins_delivery_repair_contract():
  skill = LITERATURE_REVIEW_SKILL.read_text(encoding="utf-8")

  assert 'validate_review.py --workspace "$WS"' in skill
  assert '--run-report "$RUN_REPORT"' in skill
  assert "Before every delivery" in skill
  assert "after every repair" in skill
  assert "only the emitted `repair_feedback` object" in skill
  assert "Obey its `action` field" in skill
  assert "outside `$WS`" in skill
  assert INVALID_WARNING in skill
  assert "unresolved `reason_codes` and `affected_artifacts`" in skill
  assert "not verified or publication-ready" in skill
  assert "do not describe it with either label" in skill
