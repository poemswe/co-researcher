"""Bounded repair decisions for literature-review integrity validation."""

from __future__ import annotations

from dataclasses import dataclass

from .models import (
    IntegrityRunReport,
    IntegrityStatus,
    PassReport,
    REPAIR_ACTIONS,
    RepairRecord,
)
from .workspace import WorkspaceSnapshot


@dataclass(frozen=True)
class RepairDecision:
  action: str
  repair_feedback: dict

  def __post_init__(self) -> None:
    if self.action not in REPAIR_ACTIONS:
      raise ValueError(f"unknown repair action: {self.action!r}")
    if type(self.repair_feedback) is not dict:
      raise ValueError("repair_feedback must be a dictionary")


class RepairController:
  def __init__(self, max_rounds: int = 3, no_progress_limit: int = 2):
    for value, label in (
        (max_rounds, "max_rounds"),
        (no_progress_limit, "no_progress_limit"),
    ):
      if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    self._max_rounds = max_rounds
    self._no_progress_limit = no_progress_limit
    self._run_report: IntegrityRunReport | None = None

  @property
  def run_report(self) -> IntegrityRunReport | None:
    return self._run_report

  @classmethod
  def from_run_report(
      cls,
      run_report: IntegrityRunReport,
      max_rounds: int = 3,
      no_progress_limit: int = 2,
  ) -> RepairController:
    if not isinstance(run_report, IntegrityRunReport):
      raise ValueError("run_report must be an IntegrityRunReport")
    controller = cls(max_rounds, no_progress_limit)
    expected_actions = controller._replay_actions(run_report)
    actual_actions = (
        run_report.action,
        *(repair.action for repair in run_report.repairs),
    )
    if actual_actions != expected_actions:
      raise ValueError("run report actions do not match bounded repair policy")
    controller._run_report = run_report
    return controller

  @staticmethod
  def _reason_codes(report: PassReport) -> tuple:
    return tuple(dict.fromkeys(
        finding.reason_code for finding in report.findings))

  @staticmethod
  def _observations(run_report: IntegrityRunReport):
    yield run_report.pass_report, run_report.workspace_manifest_sha256
    for repair in run_report.repairs:
      yield repair.pass_report, repair.workspace_manifest_sha256

  def _action_for(self, observations: tuple[tuple[PassReport, str], ...]) -> str:
    report, _workspace_hash = observations[-1]
    if not report.repair_required:
      return "pass"
    repair_count = len(observations) - 1
    best_score = observations[0][0].unrounded_integrity_score
    seen_hashes = {observations[0][1]}
    no_progress = 0
    for prior_report, prior_hash in observations[1:]:
      score = prior_report.unrounded_integrity_score
      if prior_hash in seen_hashes or score <= best_score:
        no_progress += 1
      else:
        no_progress = 0
        best_score = score
      seen_hashes.add(prior_hash)
    if (repair_count >= self._max_rounds
        or no_progress >= self._no_progress_limit):
      return ("stop_invalid" if report.status is IntegrityStatus.INVALID
              else "pass")
    return "repair"

  def _replay_actions(
      self, run_report: IntegrityRunReport,
  ) -> tuple[str, ...]:
    observations = tuple(self._observations(run_report))
    return tuple(
        self._action_for(observations[:index])
        for index in range(1, len(observations) + 1))

  def record(
      self, report: PassReport, snapshot: WorkspaceSnapshot,
  ) -> RepairDecision:
    if not isinstance(report, PassReport):
      raise ValueError("report must be a PassReport")
    if not isinstance(snapshot, WorkspaceSnapshot):
      raise ValueError("snapshot must be a WorkspaceSnapshot")
    if self._run_report is not None:
      latest_action = (self._run_report.repairs[-1].action
                       if self._run_report.repairs
                       else self._run_report.action)
      if latest_action in {"pass", "stop_invalid"}:
        raise ValueError("cannot append after a terminal repair action")
      observations = (*tuple(self._observations(self._run_report)),
                      (report, snapshot.manifest_sha256))
      action = self._action_for(observations)
      repair = RepairRecord(
          attempt=len(self._run_report.repairs) + 1,
          pass_report=report,
          workspace_manifest_sha256=snapshot.manifest_sha256,
          reason_codes=self._reason_codes(report),
          action=action,
          resolved=report.status is not IntegrityStatus.INVALID,
      )
      self._run_report = IntegrityRunReport(
          pass_report=self._run_report.pass_report,
          workspace_manifest_sha256=(
              self._run_report.workspace_manifest_sha256),
          action=self._run_report.action,
          quality_score=self._run_report.quality_score,
          repairs=(*self._run_report.repairs, repair),
      )
    else:
      action = self._action_for(((report, snapshot.manifest_sha256),))
      self._run_report = IntegrityRunReport(
          pass_report=report,
          workspace_manifest_sha256=snapshot.manifest_sha256,
          action=action,
          quality_score=None,
          repairs=(),
      )
    return RepairDecision(
        action=action,
        repair_feedback=safe_repair_feedback(report),
    )


def safe_repair_feedback(report: PassReport) -> dict:
  """Return the public finding allowlist used in a repair prompt."""
  if not isinstance(report, PassReport):
    raise ValueError("report must be a PassReport")
  findings = [{
      "reason_code": finding.reason_code.value,
      "severity": finding.severity.value,
      "artifact": finding.artifact,
      "message": finding.message,
  } for finding in report.findings]
  return {
      "reason_codes": list(dict.fromkeys(
          finding["reason_code"] for finding in findings)),
      "affected_artifacts": list(dict.fromkeys(
          finding["artifact"] for finding in findings)),
      "findings": findings,
  }


__all__ = ["RepairController", "RepairDecision", "safe_repair_feedback"]
