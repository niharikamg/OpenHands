"""Core data models for the Adaptive Intervention Node framework."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    REASONING = "reasoning"
    STATE_WRITE = "state_write"
    OBSERVATION = "observation"
    INTERVENTION = "intervention"
    FORK = "fork"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryStatus(str, Enum):
    RECOVERABLE = "recoverable"
    UNRECOVERABLE = "unrecoverable"
    UNKNOWN = "unknown"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERVENED = "intervened"


@dataclass
class TrajectoryEvent:
    event_type: EventType
    step: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: Any = None
    reasoning: str | None = None
    state_delta: dict[str, Any] = field(default_factory=dict)
    is_irreversible: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "step": self.step,
            "timestamp": self.timestamp.isoformat(),
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "tool_result": self.tool_result,
            "reasoning": self.reasoning,
            "state_delta": self.state_delta,
            "is_irreversible": self.is_irreversible,
            "risk_level": self.risk_level.value,
            "metadata": self.metadata,
        }


@dataclass
class AgentState:
    step: int
    workspace: dict[str, Any] = field(default_factory=dict)
    files_written: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    commands_executed: list[str] = field(default_factory=list)
    api_calls_made: list[str] = field(default_factory=list)
    intermediate_outputs: dict[str, Any] = field(default_factory=dict)
    downstream_dependencies: dict[str, list[str]] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def clone(self) -> AgentState:
        import copy
        return copy.deepcopy(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "workspace": self.workspace,
            "files_written": self.files_written,
            "files_deleted": self.files_deleted,
            "commands_executed": self.commands_executed,
            "api_calls_made": self.api_calls_made,
            "intermediate_outputs": self.intermediate_outputs,
            "downstream_dependencies": self.downstream_dependencies,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ExecutionOutcome:
    task_id: str
    status: TaskStatus
    final_state: AgentState
    trajectory: list[TrajectoryEvent] = field(default_factory=list)
    total_steps: int = 0
    wall_time_seconds: float = 0.0
    llm_calls: int = 0
    tokens_used: int = 0
    error_message: str | None = None
    benchmark_score: float | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "total_steps": self.total_steps,
            "wall_time_seconds": self.wall_time_seconds,
            "llm_calls": self.llm_calls,
            "tokens_used": self.tokens_used,
            "error_message": self.error_message,
            "benchmark_score": self.benchmark_score,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
            "trajectory_length": len(self.trajectory),
        }


@dataclass
class ForkPoint:
    step: int
    fork_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state_snapshot: AgentState | None = None
    event: TrajectoryEvent | None = None
    recovery_status: RecoveryStatus = RecoveryStatus.UNKNOWN
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "fork_id": self.fork_id,
            "step": self.step,
            "recovery_status": self.recovery_status.value,
            "reason": self.reason,
            "state_snapshot": self.state_snapshot.to_dict() if self.state_snapshot else None,
        }


@dataclass
class InterventionResult:
    intervention_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    triggered_at_step: int = 0
    risk_level: RiskLevel = RiskLevel.LOW
    corrective_actions: list[dict[str, Any]] = field(default_factory=list)
    outcome_before: ExecutionOutcome | None = None
    outcome_after: ExecutionOutcome | None = None
    recovery_success: bool = False
    timing_ms: float = 0.0
    strategy: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intervention_id": self.intervention_id,
            "triggered_at_step": self.triggered_at_step,
            "risk_level": self.risk_level.value,
            "corrective_actions_count": len(self.corrective_actions),
            "recovery_success": self.recovery_success,
            "timing_ms": self.timing_ms,
            "strategy": self.strategy,
            "metadata": self.metadata,
        }
