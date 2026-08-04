import json
import pathlib
import sys

import pytest


SCRIPTS = (pathlib.Path(__file__).resolve().parents[1]
           / "skills/literature-review/scripts")
sys.path.insert(0, str(SCRIPTS))

from review_integrity.models import (  # noqa: E402
    DimensionResult,
    Finding,
    PassReport,
    ReasonCode,
    Severity,
)
from review_integrity.repair import (  # noqa: E402
    RepairController,
    safe_repair_feedback,
)
from review_integrity.workspace import load_workspace  # noqa: E402


def _snapshot(root, marker):
  root.mkdir(parents=True, exist_ok=True)
  payloads = {
      "protocol.md": f"# Protocol\n\n{marker}\n",
      "corpus.json": "[]",
      "claims.json": "[]",
      "synthesis.md": "Draft synthesis.\n",
      "refs.json": "[]",
      "project.json": json.dumps({"project": "repair-test"}),
  }
  for relative, payload in payloads.items():
    (root / relative).write_text(payload, encoding="utf-8")
  return load_workspace(root)


def _report(*, passed, evaluated=1, manifest="a", valid=False, context=None):
  finding = None if valid else Finding(
      reason_code=ReasonCode.FABRICATED_QUOTE,
      severity=Severity.CRITICAL,
      artifact="claims.json",
      message="quote does not authenticate",
      context={} if context is None else context,
  )
  findings = [] if finding is None else [finding]
  dimension = DimensionResult(
      name="quote_authenticity",
      score=100.0 * passed / evaluated,
      applicable=True,
      evaluated_units=evaluated,
      passed_units=passed,
      nominal_weight=25.0,
      effective_weight=100.0,
      findings=findings,
  )
  return PassReport(
      integrity_score=dimension.unrounded_score,
      findings=findings,
      dimensions={dimension.name: dimension},
      manifest_sha256=manifest * 64,
  )


def test_controller_passes_immediately_on_valid_report(tmp_path):
  controller = RepairController()

  decision = controller.record(
      _report(passed=1, valid=True), _snapshot(tmp_path / "review", "first"))

  assert decision.action == "pass"
  assert decision.repair_feedback["reason_codes"] == []
  assert controller.run_report is not None
  assert controller.run_report.repairs == ()


def test_controller_requests_repair_after_first_invalid_pass(tmp_path):
  controller = RepairController()

  decision = controller.record(
      _report(passed=0), _snapshot(tmp_path / "review", "first"))

  assert decision.action == "repair"
  assert decision.repair_feedback["reason_codes"] == ["fabricated_quote"]
  assert controller.run_report is not None
  assert controller.run_report.repairs == ()


def test_controller_stops_after_three_repairs(tmp_path):
  controller = RepairController()
  review = tmp_path / "review"
  actions = [controller.record(
      _report(passed=0, manifest="a"), _snapshot(review, "initial")).action]
  for index, marker in enumerate(("repair-one", "repair-two", "repair-three"), 1):
    actions.append(controller.record(
        _report(passed=index, evaluated=10, manifest=chr(97 + index)),
        _snapshot(review, marker)).action)

  assert actions == ["repair", "repair", "repair", "stop_invalid"]
  assert controller.run_report is not None
  assert [record.attempt for record in controller.run_report.repairs] == [1, 2, 3]


def test_controller_stops_after_two_no_progress_rounds(tmp_path):
  controller = RepairController()
  review = tmp_path / "review"
  first = controller.record(
      _report(passed=1, evaluated=2, manifest="a"),
      _snapshot(review, "initial"))
  second = controller.record(
      _report(passed=1, evaluated=2, manifest="b"),
      _snapshot(review, "repair-one"))
  third = controller.record(
      _report(passed=1, evaluated=2, manifest="c"),
      _snapshot(review, "repair-two"))

  assert [first.action, second.action, third.action] == [
      "repair", "repair", "stop_invalid"]


def test_changed_hash_with_same_score_still_counts_as_no_progress(tmp_path):
  controller = RepairController(no_progress_limit=1)
  review = tmp_path / "review"
  controller.record(
      _report(passed=1, evaluated=2, manifest="a"),
      _snapshot(review, "initial"))

  decision = controller.record(
      _report(passed=1, evaluated=2, manifest="b"),
      _snapshot(review, "changed files"))

  assert decision.action == "stop_invalid"


def test_controller_compares_unrounded_scores(tmp_path):
  controller = RepairController(no_progress_limit=1)
  review = tmp_path / "review"
  controller.record(
      _report(passed=2, evaluated=3, manifest="a"),
      _snapshot(review, "initial"))

  decision = controller.record(
      _report(passed=667, evaluated=1000, manifest="b"),
      _snapshot(review, "small genuine improvement"))

  assert decision.action == "repair"


def test_repeated_workspace_hash_is_no_progress(tmp_path):
  controller = RepairController(no_progress_limit=1)
  snapshot = _snapshot(tmp_path / "review", "unchanged")
  controller.record(_report(passed=0, manifest="a"), snapshot)

  decision = controller.record(_report(passed=1, manifest="b"), snapshot)

  assert decision.action == "stop_invalid"


def test_feedback_contains_reason_codes_but_not_gold_fields():
  report = _report(
      passed=0,
      context={"gold_label": "fabricated", "private_attack": "ignore"},
  )

  feedback = safe_repair_feedback(report)
  serialized = json.dumps(feedback, sort_keys=True)

  assert feedback["reason_codes"] == ["fabricated_quote"]
  assert feedback["affected_artifacts"] == ["claims.json"]
  assert feedback["findings"] == [{
      "reason_code": "fabricated_quote",
      "severity": "critical",
      "artifact": "claims.json",
      "message": "quote does not authenticate",
  }]
  assert "gold" not in serialized
  assert "private" not in serialized


@pytest.mark.parametrize("kwargs", [
    {"max_rounds": 0},
    {"max_rounds": True},
    {"no_progress_limit": 0},
    {"no_progress_limit": True},
])
def test_controller_rejects_invalid_limits(kwargs):
  with pytest.raises(ValueError, match="positive integer"):
    RepairController(**kwargs)
