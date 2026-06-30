"""
Oracle-recovery forking methodology.

Identifies the earliest unrecoverable execution step within multi-stage agent
pipelines, enabling systematic measurement of failure propagation and recovery
limitations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from evaluation.adaptive_intervention.models import (
    AgentState,
    ExecutionOutcome,
    ForkPoint,
    RecoveryStatus,
    TaskStatus,
    TrajectoryEvent,
)
from evaluation.adaptive_intervention.trajectory.analyzer import IrreversibilityAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class RecoveryCandidate:
    """A candidate fork point where execution might be recoverable."""

    step: int
    state_snapshot: AgentState
    remaining_trajectory: list[TrajectoryEvent]
    estimated_recovery_cost: float = 0.0
    recovery_probability: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "estimated_recovery_cost": self.estimated_recovery_cost,
            "recovery_probability": self.recovery_probability,
            "remaining_steps": len(self.remaining_trajectory),
        }


@dataclass
class OracleRecoveryResult:
    """Result of oracle-recovery analysis on a trajectory."""

    task_id: str
    earliest_unrecoverable_step: int | None = None
    latest_recoverable_step: int | None = None
    fork_points: list[ForkPoint] = field(default_factory=list)
    recovery_candidates: list[RecoveryCandidate] = field(default_factory=list)
    total_steps_analyzed: int = 0
    recovery_window_size: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "earliest_unrecoverable_step": self.earliest_unrecoverable_step,
            "latest_recoverable_step": self.latest_recoverable_step,
            "recovery_window_size": self.recovery_window_size,
            "total_steps_analyzed": self.total_steps_analyzed,
            "fork_count": len(self.fork_points),
            "fork_points": [fp.to_dict() for fp in self.fork_points],
            "recovery_candidates": [rc.to_dict() for rc in self.recovery_candidates],
        }


class OracleRecovery:
    """
    Applies oracle-recovery forking to find the earliest step in a trajectory
    from which recovery is no longer possible.

    The oracle has full knowledge of the ground-truth outcome and uses it to
    evaluate each fork point in the trajectory.
    """

    def __init__(
        self,
        task_id: str,
        ground_truth_outcome: ExecutionOutcome | None = None,
    ) -> None:
        self.task_id = task_id
        self.ground_truth_outcome = ground_truth_outcome
        self._analyzer = IrreversibilityAnalyzer(task_id)

    def analyze(
        self,
        trajectory: list[TrajectoryEvent],
        state_history: list[AgentState],
        ground_truth: dict[str, Any] | None = None,
    ) -> OracleRecoveryResult:
        result = OracleRecoveryResult(
            task_id=self.task_id,
            total_steps_analyzed=len(trajectory),
        )

        irrev_report = self._analyzer.analyze(trajectory, state_history, ground_truth)
        fork_points = self._build_fork_points(trajectory, state_history, irrev_report.first_unrecoverable_step)
        result.fork_points = fork_points

        candidates = self._identify_recovery_candidates(fork_points, trajectory, state_history)
        result.recovery_candidates = candidates

        result.earliest_unrecoverable_step = self._find_earliest_unrecoverable(fork_points)
        result.latest_recoverable_step = self._find_latest_recoverable(fork_points)

        if (
            result.earliest_unrecoverable_step is not None
            and result.latest_recoverable_step is not None
        ):
            result.recovery_window_size = (
                result.earliest_unrecoverable_step - result.latest_recoverable_step
            )

        return result

    def fork_and_replay(
        self,
        fork_point: ForkPoint,
        trajectory: list[TrajectoryEvent],
        corrected_events: list[TrajectoryEvent],
    ) -> list[TrajectoryEvent]:
        """
        Fork execution at fork_point.step, replace remaining events with
        corrected_events, and return the new trajectory prefix + corrected suffix.
        """
        prefix = [e for e in trajectory if e.step < fork_point.step]
        return prefix + corrected_events

    def _build_fork_points(
        self,
        trajectory: list[TrajectoryEvent],
        state_history: list[AgentState],
        first_unrecoverable: int | None,
    ) -> list[ForkPoint]:
        state_by_step: dict[int, AgentState] = {s.step: s for s in state_history}
        fork_points: list[ForkPoint] = []

        for event in trajectory:
            if not event.is_irreversible:
                continue
            snapshot = state_by_step.get(event.step)
            step = event.step

            if first_unrecoverable is None:
                status = RecoveryStatus.RECOVERABLE
            elif step < first_unrecoverable:
                status = RecoveryStatus.RECOVERABLE
            elif step == first_unrecoverable:
                status = RecoveryStatus.UNRECOVERABLE
            else:
                status = RecoveryStatus.UNRECOVERABLE

            fp = ForkPoint(
                step=step,
                state_snapshot=snapshot,
                event=event,
                recovery_status=status,
                reason=self._explain_status(event, status),
            )
            fork_points.append(fp)

        return fork_points

    def _identify_recovery_candidates(
        self,
        fork_points: list[ForkPoint],
        trajectory: list[TrajectoryEvent],
        state_history: list[AgentState],
    ) -> list[RecoveryCandidate]:
        state_by_step: dict[int, AgentState] = {s.step: s for s in state_history}
        candidates: list[RecoveryCandidate] = []

        for fp in fork_points:
            if fp.recovery_status != RecoveryStatus.RECOVERABLE:
                continue
            snapshot = state_by_step.get(fp.step) or AgentState(step=fp.step)
            remaining = [e for e in trajectory if e.step > fp.step]
            irreversible_remaining = sum(1 for e in remaining if e.is_irreversible)
            recovery_probability = max(0.0, 1.0 - irreversible_remaining * 0.15)
            estimated_cost = irreversible_remaining * 2.0 + len(remaining) * 0.5

            candidates.append(
                RecoveryCandidate(
                    step=fp.step,
                    state_snapshot=snapshot,
                    remaining_trajectory=remaining,
                    estimated_recovery_cost=estimated_cost,
                    recovery_probability=recovery_probability,
                )
            )

        return sorted(candidates, key=lambda c: c.recovery_probability, reverse=True)

    def _find_earliest_unrecoverable(self, fork_points: list[ForkPoint]) -> int | None:
        unrecoverable = [fp for fp in fork_points if fp.recovery_status == RecoveryStatus.UNRECOVERABLE]
        return min((fp.step for fp in unrecoverable), default=None)

    def _find_latest_recoverable(self, fork_points: list[ForkPoint]) -> int | None:
        recoverable = [fp for fp in fork_points if fp.recovery_status == RecoveryStatus.RECOVERABLE]
        return max((fp.step for fp in recoverable), default=None)

    def _explain_status(self, event: TrajectoryEvent, status: RecoveryStatus) -> str:
        if status == RecoveryStatus.UNRECOVERABLE:
            return (
                f"Tool '{event.tool_name}' produced an irreversible state change "
                f"at step {event.step} that propagated to downstream stages."
            )
        return f"Step {event.step} is a recoverable fork point before first propagation error."
