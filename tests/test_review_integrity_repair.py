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


def _report(*, passed, evaluated=1, manifest="a", valid=False, context=None,
            reason=ReasonCode.FABRICATED_QUOTE, severity=Severity.CRITICAL):
  finding = None if valid else Finding(
      reason_code=reason,
      severity=severity,
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


def _warning(reason, **kwargs):
  return _report(reason=reason, severity=Severity.WARNING, **kwargs)


@pytest.mark.parametrize("reason", [
    ReasonCode.CLAIM_NEEDS_REVIEW,
    ReasonCode.BIBLIOGRAPHY_INCOMPLETE,
    ReasonCode.PRISMA_EXCLUSION_REASON_MISSING,
])
def test_controller_repairs_repairable_warning(tmp_path, reason):
  decision = RepairController().record(
      _warning(reason, passed=0), _snapshot(tmp_path / "review", "first"))

  assert decision.action == "repair"


@pytest.mark.parametrize("reason", [
    ReasonCode.ABSTRACT_ONLY_SUPPORT,
    ReasonCode.CITATION_RESOLUTION_UNAVAILABLE,
])
def test_controller_passes_policy_warning_without_repair(tmp_path, reason):
  decision = RepairController().record(
      _warning(reason, passed=0), _snapshot(tmp_path / "review", "first"))

  assert decision.action == "pass"


def test_controller_passes_resolved_repairable_warning(tmp_path):
  controller = RepairController()
  review = tmp_path / "review"
  first = controller.record(
      _warning(ReasonCode.CLAIM_NEEDS_REVIEW, passed=0, manifest="a"),
      _snapshot(review, "initial"))
  second = controller.record(
      _report(passed=1, manifest="b", valid=True),
      _snapshot(review, "repair-one"))

  assert [first.action, second.action] == ["repair", "pass"]
  assert controller.run_report.repairs[0].resolved is True


def test_controller_passes_with_warnings_after_repair_limit(tmp_path):
  controller = RepairController()
  review = tmp_path / "review"
  actions = [controller.record(
      _warning(ReasonCode.CLAIM_NEEDS_REVIEW, passed=0, manifest="a"),
      _snapshot(review, "initial")).action]
  for index, marker in enumerate(("repair-one", "repair-two", "repair-three"), 1):
    actions.append(controller.record(
        _warning(ReasonCode.CLAIM_NEEDS_REVIEW, passed=index, evaluated=10,
                 manifest=chr(97 + index)),
        _snapshot(review, marker)).action)

  assert actions == ["repair", "repair", "repair", "pass"]


def test_controller_passes_with_warnings_after_no_progress(tmp_path):
  controller = RepairController()
  review = tmp_path / "review"
  actions = [controller.record(
      _warning(ReasonCode.BIBLIOGRAPHY_INCOMPLETE, passed=1, evaluated=2,
               manifest=manifest),
      _snapshot(review, marker)).action
      for manifest, marker in (("a", "initial"), ("b", "one"), ("c", "two"))]

  assert actions == ["repair", "repair", "pass"]


def test_repair_report_with_warning_round_trips(tmp_path):
  controller = RepairController()
  review = tmp_path / "review"
  controller.record(
      _warning(ReasonCode.CLAIM_NEEDS_REVIEW, passed=0, manifest="a"),
      _snapshot(review, "initial"))
  controller.record(
      _warning(ReasonCode.CLAIM_NEEDS_REVIEW, passed=0, manifest="b"),
      _snapshot(review, "repair-one"))

  restored = RepairController.from_run_report(controller.run_report)

  assert restored.run_report == controller.run_report


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


def test_feedback_names_the_flagged_synthesis_sentence():
  sentence = "Scores rose 73 percent (Synthetic, 2024)."
  report = _report(
      passed=0, reason=ReasonCode.COVERAGE_NUMBER_MISSING,
      context={"synthesis_sentence": sentence, "synthesis_sentence_index": 4,
               "gold_label": "added-number"})

  feedback = safe_repair_feedback(report)

  assert feedback["findings"][0]["sentence"] == sentence
  assert set(feedback["findings"][0]) == {
      "reason_code", "severity", "artifact", "message", "sentence"}
  assert "gold" not in json.dumps(feedback)
  assert "added-number" not in json.dumps(feedback)


@pytest.mark.parametrize("kwargs", [
    {"max_rounds": 0},
    {"max_rounds": True},
    {"no_progress_limit": 0},
    {"no_progress_limit": True},
])
def test_controller_rejects_invalid_limits(kwargs):
  with pytest.raises(ValueError, match="positive integer"):
    RepairController(**kwargs)
