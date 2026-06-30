"""
Irreversibility analysis for agentic data-engineering workflows.

Investigates how incorrect intermediate outputs become materialized and
subsequently propagated across downstream execution stages as trusted system state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from evaluation.adaptive_intervention.models import (
    AgentState,
    EventType,
    RiskLevel,
    TrajectoryEvent,
)

logger = logging.getLogger(__name__)

# State keys that represent materialized durable outputs
_DURABLE_OUTPUT_KEYS = {
    "files_written",
    "commands_executed",
    "api_calls_made",
    "database_writes",
}


@dataclass
class MaterializationPoint:
    """A step where an intermediate output was durably written to the environment."""

    step: int
    key: str
    value: Any
    propagated_to: list[str] = field(default_factory=list)
    is_incorrect: bool = False
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "key": self.key,
            "propagated_to": self.propagated_to,
            "is_incorrect": self.is_incorrect,
            "confidence": self.confidence,
        }


@dataclass
class PropagationChain:
    """Tracks how an incorrect value flows across downstream execution stages."""

    root_step: int
    root_key: str
    chain: list[tuple[int, str]] = field(default_factory=list)

    def depth(self) -> int:
        return len(self.chain)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_step": self.root_step,
            "root_key": self.root_key,
            "chain_depth": self.depth(),
            "chain": [{"step": s, "key": k} for s, k in self.chain],
        }


@dataclass
class IrreversibilityReport:
    task_id: str
    total_steps: int
    materialization_points: list[MaterializationPoint] = field(default_factory=list)
    propagation_chains: list[PropagationChain] = field(default_factory=list)
    first_unrecoverable_step: int | None = None
    irreversibility_fraction: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "total_steps": self.total_steps,
            "materialization_count": len(self.materialization_points),
            "propagation_chain_count": len(self.propagation_chains),
            "first_unrecoverable_step": self.first_unrecoverable_step,
            "irreversibility_fraction": self.irreversibility_fraction,
            "materialization_points": [m.to_dict() for m in self.materialization_points],
            "propagation_chains": [c.to_dict() for c in self.propagation_chains],
        }


class IrreversibilityAnalyzer:
    """
    Analyzes an agent trajectory to detect when intermediate outputs become
    irreversibly materialized and how errors propagate through subsequent steps.
    """

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id

    def analyze(
        self,
        trajectory: list[TrajectoryEvent],
        state_history: list[AgentState] | None = None,
        ground_truth: dict[str, Any] | None = None,
    ) -> IrreversibilityReport:
        report = IrreversibilityReport(
            task_id=self.task_id,
            total_steps=max((e.step for e in trajectory), default=0),
        )

        materialization_points = self._find_materialization_points(trajectory)
        report.materialization_points = materialization_points

        if ground_truth:
            self._flag_incorrect_materializations(materialization_points, state_history, ground_truth)

        report.propagation_chains = self._trace_propagation(trajectory, materialization_points)
        report.first_unrecoverable_step = self._find_first_unrecoverable(materialization_points)

        irreversible_steps = {m.step for m in materialization_points}
        if report.total_steps > 0:
            report.irreversibility_fraction = len(irreversible_steps) / report.total_steps

        return report

    def _find_materialization_points(
        self, trajectory: list[TrajectoryEvent]
    ) -> list[MaterializationPoint]:
        points: list[MaterializationPoint] = []
        for event in trajectory:
            if event.is_irreversible:
                point = MaterializationPoint(
                    step=event.step,
                    key=event.tool_name or f"state_write@{event.step}",
                    value=event.tool_args or event.state_delta,
                )
                points.append(point)
            elif event.event_type == EventType.STATE_WRITE and event.state_delta:
                for key, value in event.state_delta.items():
                    points.append(MaterializationPoint(step=event.step, key=key, value=value))
        return points

    def _flag_incorrect_materializations(
        self,
        points: list[MaterializationPoint],
        state_history: list[AgentState] | None,
        ground_truth: dict[str, Any],
    ) -> None:
        if not state_history:
            return
        state_by_step: dict[int, AgentState] = {s.step: s for s in state_history}
        for point in points:
            state = state_by_step.get(point.step)
            if state is None:
                continue
            actual = state.intermediate_outputs.get(point.key)
            expected = ground_truth.get(point.key)
            if expected is not None and actual != expected:
                point.is_incorrect = True
                point.confidence = self._compute_confidence(actual, expected)

    def _compute_confidence(self, actual: Any, expected: Any) -> float:
        if actual is None or expected is None:
            return 0.0
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            denom = max(abs(expected), 1e-9)
            return max(0.0, 1.0 - abs(actual - expected) / denom)
        if isinstance(expected, str) and isinstance(actual, str):
            longer = max(len(expected), len(actual), 1)
            common = sum(a == b for a, b in zip(expected, actual))
            return common / longer
        return 0.0

    def _trace_propagation(
        self,
        trajectory: list[TrajectoryEvent],
        materialization_points: list[MaterializationPoint],
    ) -> list[PropagationChain]:
        # Build a map of which steps consume which keys
        consumers: dict[str, list[tuple[int, str]]] = {}
        for event in trajectory:
            if event.event_type == EventType.TOOL_CALL and event.tool_args:
                for arg_key, arg_val in event.tool_args.items():
                    consumers.setdefault(str(arg_val), []).append((event.step, arg_key))

        chains: list[PropagationChain] = []
        for point in materialization_points:
            if not point.is_incorrect:
                continue
            chain = PropagationChain(root_step=point.step, root_key=point.key)
            downstream = consumers.get(str(point.value), [])
            for step, key in downstream:
                if step > point.step:
                    chain.chain.append((step, key))
                    point.propagated_to.append(key)
            if chain.depth() > 0:
                chains.append(chain)

        return chains

    def _find_first_unrecoverable(
        self, points: list[MaterializationPoint]
    ) -> int | None:
        incorrect = [p for p in points if p.is_incorrect and p.propagated_to]
        if not incorrect:
            return None
        return min(p.step for p in incorrect)

    def summarize_risk_distribution(
        self, trajectory: list[TrajectoryEvent]
    ) -> dict[str, int]:
        dist: dict[str, int] = {level.value: 0 for level in RiskLevel}
        for event in trajectory:
            dist[event.risk_level.value] += 1
        return dist
