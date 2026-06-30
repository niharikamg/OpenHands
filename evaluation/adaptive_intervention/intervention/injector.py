"""
Corrective action injector.

Injects corrective actions before irreversible state transitions occur during
task execution, based on signals from the HighRiskDetector.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from evaluation.adaptive_intervention.models import (
    AgentState,
    EventType,
    InterventionResult,
    RiskLevel,
    TrajectoryEvent,
)
from evaluation.adaptive_intervention.intervention.detector import DetectionResult

logger = logging.getLogger(__name__)


@dataclass
class CorrectiveAction:
    action_type: str
    target: str
    parameters: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    priority: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target": self.target,
            "parameters": self.parameters,
            "rationale": self.rationale,
            "priority": self.priority,
        }


class ActionInjector:
    """
    Generates and injects corrective actions into an agent trajectory when
    a high-risk detection result crosses the intervention threshold.

    Strategies:
      - REVERT: Roll back a specific state write.
      - CHECKPOINT: Force a validation step before proceeding.
      - REDIRECT: Replace the next planned tool call with a safer alternative.
      - ABORT: Stop execution and surface the risk to the caller.
      - REROUTE: Re-route through a safer sub-trajectory.
    """

    STRATEGIES = ("REVERT", "CHECKPOINT", "REDIRECT", "ABORT", "REROUTE")

    def __init__(self, default_strategy: str = "CHECKPOINT") -> None:
        if default_strategy not in self.STRATEGIES:
            raise ValueError(f"Unknown strategy '{default_strategy}'. Choose from {self.STRATEGIES}.")
        self.default_strategy = default_strategy

    def build_corrective_actions(
        self,
        detection: DetectionResult,
        current_state: AgentState,
        strategy: str | None = None,
    ) -> list[CorrectiveAction]:
        strategy = strategy or self.default_strategy
        actions: list[CorrectiveAction] = []

        if strategy == "REVERT":
            actions.extend(self._revert_actions(detection, current_state))
        elif strategy == "CHECKPOINT":
            actions.extend(self._checkpoint_actions(detection, current_state))
        elif strategy == "REDIRECT":
            actions.extend(self._redirect_actions(detection, current_state))
        elif strategy == "ABORT":
            actions.extend(self._abort_actions(detection))
        elif strategy == "REROUTE":
            actions.extend(self._reroute_actions(detection, current_state))

        actions.sort(key=lambda a: a.priority)
        return actions

    def inject(
        self,
        detection: DetectionResult,
        trajectory: list[TrajectoryEvent],
        current_state: AgentState,
        strategy: str | None = None,
    ) -> InterventionResult:
        t0 = time.monotonic()
        strategy = strategy or self.default_strategy
        actions = self.build_corrective_actions(detection, current_state, strategy)

        injection_events = self._actions_to_events(
            actions,
            at_step=detection.intervention_step or (trajectory[-1].step + 1 if trajectory else 0),
        )

        result = InterventionResult(
            triggered_at_step=detection.intervention_step or 0,
            risk_level=detection.aggregate_risk,
            corrective_actions=[a.to_dict() for a in actions],
            timing_ms=(time.monotonic() - t0) * 1000,
            strategy=strategy,
            metadata={
                "signal_count": len(detection.signals),
                "confidence": detection.confidence,
                "injected_events": len(injection_events),
            },
        )
        logger.info(
            "Intervention triggered at step=%d strategy=%s confidence=%.3f actions=%d",
            result.triggered_at_step,
            strategy,
            detection.confidence,
            len(actions),
        )
        return result

    # ------------------------------------------------------------------
    # Strategy implementations
    # ------------------------------------------------------------------

    def _revert_actions(
        self, detection: DetectionResult, state: AgentState
    ) -> list[CorrectiveAction]:
        actions: list[CorrectiveAction] = []
        for sig in detection.signals:
            if sig.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                if sig.trigger_event and sig.trigger_event.tool_name:
                    actions.append(
                        CorrectiveAction(
                            action_type="REVERT",
                            target=sig.trigger_event.tool_name,
                            parameters={"step": sig.step},
                            rationale=sig.reason,
                            priority=1,
                        )
                    )
        if not actions:
            actions.append(
                CorrectiveAction(
                    action_type="REVERT",
                    target="last_irreversible",
                    rationale="Reverting most recent irreversible operation as a precaution.",
                    priority=1,
                )
            )
        return actions

    def _checkpoint_actions(
        self, detection: DetectionResult, state: AgentState
    ) -> list[CorrectiveAction]:
        return [
            CorrectiveAction(
                action_type="CHECKPOINT",
                target="state_validation",
                parameters={
                    "validate_keys": list(state.intermediate_outputs.keys()),
                    "reason": f"Risk level={detection.aggregate_risk.value}, confidence={detection.confidence:.2f}",
                },
                rationale="Force validation of intermediate state before proceeding.",
                priority=1,
            ),
            CorrectiveAction(
                action_type="CHECKPOINT",
                target="output_schema_check",
                parameters={"files": state.files_written},
                rationale="Verify output schema matches expected format before downstream stages.",
                priority=2,
            ),
        ]

    def _redirect_actions(
        self, detection: DetectionResult, state: AgentState
    ) -> list[CorrectiveAction]:
        actions: list[CorrectiveAction] = []
        for sig in detection.signals:
            if sig.trigger_event and sig.trigger_event.tool_name in (
                "delete_file",
                "database_delete",
                "http_delete",
            ):
                actions.append(
                    CorrectiveAction(
                        action_type="REDIRECT",
                        target=sig.trigger_event.tool_name,
                        parameters={"replacement": "archive_file", "reason": sig.reason},
                        rationale=f"Redirect destructive call to safer archive operation.",
                        priority=1,
                    )
                )
        if not actions:
            actions.append(
                CorrectiveAction(
                    action_type="REDIRECT",
                    target="next_tool_call",
                    parameters={"safer_alternative": "read_and_validate"},
                    rationale="Inject a read-and-validate step before the next write.",
                    priority=1,
                )
            )
        return actions

    def _abort_actions(self, detection: DetectionResult) -> list[CorrectiveAction]:
        return [
            CorrectiveAction(
                action_type="ABORT",
                target="execution",
                parameters={
                    "risk_level": detection.aggregate_risk.value,
                    "confidence": detection.confidence,
                    "signals": [s.reason for s in detection.signals],
                },
                rationale="Risk exceeds abort threshold; surfacing to caller for human review.",
                priority=0,
            )
        ]

    def _reroute_actions(
        self, detection: DetectionResult, state: AgentState
    ) -> list[CorrectiveAction]:
        return [
            CorrectiveAction(
                action_type="REROUTE",
                target="sub_trajectory",
                parameters={
                    "from_step": detection.intervention_step,
                    "via": "safe_path",
                    "skip_tools": [
                        s.trigger_event.tool_name
                        for s in detection.signals
                        if s.trigger_event and s.trigger_event.tool_name
                    ],
                },
                rationale="Re-route execution through a validated safe sub-trajectory.",
                priority=1,
            )
        ]

    # ------------------------------------------------------------------
    # Helper: convert actions to synthetic TrajectoryEvents
    # ------------------------------------------------------------------

    def _actions_to_events(
        self, actions: list[CorrectiveAction], at_step: int
    ) -> list[TrajectoryEvent]:
        events: list[TrajectoryEvent] = []
        for i, action in enumerate(actions):
            events.append(
                TrajectoryEvent(
                    event_type=EventType.INTERVENTION,
                    step=at_step + i,
                    tool_name=f"intervention:{action.action_type.lower()}",
                    tool_args={"target": action.target, **action.parameters},
                    reasoning=action.rationale,
                    metadata={"strategy": action.action_type, "priority": action.priority},
                )
            )
        return events
