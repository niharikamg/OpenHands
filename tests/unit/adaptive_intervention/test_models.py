"""Tests for core data models."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from evaluation.adaptive_intervention.models import (
    AgentState,
    EventType,
    ForkPoint,
    InterventionResult,
    RecoveryStatus,
    RiskLevel,
    TaskStatus,
    TrajectoryEvent,
)


def test_trajectory_event_defaults():
    event = TrajectoryEvent(event_type=EventType.REASONING, step=0)
    assert event.step == 0
    assert event.event_type == EventType.REASONING
    assert event.is_irreversible is False
    assert event.risk_level == RiskLevel.LOW
    assert event.event_id is not None


def test_trajectory_event_to_dict():
    event = TrajectoryEvent(
        event_type=EventType.TOOL_CALL,
        step=3,
        tool_name="write_file",
        tool_args={"path": "out.csv"},
        is_irreversible=True,
        risk_level=RiskLevel.HIGH,
    )
    d = event.to_dict()
    assert d["step"] == 3
    assert d["tool_name"] == "write_file"
    assert d["is_irreversible"] is True
    assert d["risk_level"] == "high"


def test_agent_state_clone_is_independent():
    state = AgentState(step=1)
    state.files_written.append("a.csv")
    clone = state.clone()
    clone.files_written.append("b.csv")
    assert "b.csv" not in state.files_written
    assert len(clone.files_written) == 2


def test_agent_state_to_dict():
    state = AgentState(step=5, files_written=["output.csv"])
    d = state.to_dict()
    assert d["step"] == 5
    assert "output.csv" in d["files_written"]


def test_fork_point_to_dict():
    fp = ForkPoint(step=4, recovery_status=RecoveryStatus.RECOVERABLE, reason="test")
    d = fp.to_dict()
    assert d["step"] == 4
    assert d["recovery_status"] == "recoverable"


def test_intervention_result_to_dict():
    ir = InterventionResult(
        triggered_at_step=3,
        risk_level=RiskLevel.CRITICAL,
        recovery_success=True,
        strategy="CHECKPOINT",
    )
    d = ir.to_dict()
    assert d["triggered_at_step"] == 3
    assert d["risk_level"] == "critical"
    assert d["recovery_success"] is True


def test_risk_level_ordering():
    levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
    assert len(levels) == 4


def test_task_status_values():
    assert TaskStatus.COMPLETED.value == "completed"
    assert TaskStatus.FAILED.value == "failed"
    assert TaskStatus.INTERVENED.value == "intervened"
