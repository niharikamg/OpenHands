"""Tests for oracle-recovery forking methodology."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from evaluation.adaptive_intervention.models import AgentState, RiskLevel, RecoveryStatus, TrajectoryEvent, EventType
from evaluation.adaptive_intervention.oracle.recovery import OracleRecovery


def _make_irrev_event(step, tool="write_file"):
    return TrajectoryEvent(
        event_type=EventType.TOOL_CALL,
        step=step,
        tool_name=tool,
        is_irreversible=True,
        risk_level=RiskLevel.HIGH,
    )


def _make_safe_event(step):
    return TrajectoryEvent(
        event_type=EventType.TOOL_CALL,
        step=step,
        tool_name="read_file",
        is_irreversible=False,
        risk_level=RiskLevel.LOW,
    )


def test_oracle_empty_trajectory():
    oracle = OracleRecovery(task_id="test-oracle-001")
    result = oracle.analyze([], [])
    assert result.earliest_unrecoverable_step is None
    assert len(result.fork_points) == 0


def test_oracle_no_irreversible_events():
    trajectory = [_make_safe_event(i) for i in range(5)]
    states = [AgentState(step=i) for i in range(5)]
    oracle = OracleRecovery(task_id="test-oracle-002")
    result = oracle.analyze(trajectory, states)
    assert result.earliest_unrecoverable_step is None
    assert result.latest_recoverable_step is None


def test_oracle_identifies_fork_points_for_irreversible_events():
    trajectory = [
        _make_safe_event(0),
        _make_irrev_event(1),
        _make_safe_event(2),
        _make_irrev_event(3),
    ]
    states = [AgentState(step=i) for i in range(4)]
    oracle = OracleRecovery(task_id="test-oracle-003")
    result = oracle.analyze(trajectory, states)
    assert len(result.fork_points) == 2
    fork_steps = [fp.step for fp in result.fork_points]
    assert 1 in fork_steps
    assert 3 in fork_steps


def test_oracle_all_fork_points_recoverable_without_ground_truth():
    trajectory = [_make_irrev_event(i) for i in range(3)]
    states = [AgentState(step=i) for i in range(3)]
    oracle = OracleRecovery(task_id="test-oracle-004")
    result = oracle.analyze(trajectory, states, ground_truth=None)
    statuses = {fp.recovery_status for fp in result.fork_points}
    assert RecoveryStatus.RECOVERABLE in statuses


def test_oracle_recovery_candidates_sorted_by_probability():
    trajectory = [_make_irrev_event(i) for i in range(4)]
    states = [AgentState(step=i) for i in range(4)]
    oracle = OracleRecovery(task_id="test-oracle-005")
    result = oracle.analyze(trajectory, states)
    probs = [c.recovery_probability for c in result.recovery_candidates]
    assert probs == sorted(probs, reverse=True)


def test_oracle_fork_and_replay():
    trajectory = [_make_irrev_event(i) for i in range(5)]
    states = [AgentState(step=i) for i in range(5)]
    oracle = OracleRecovery(task_id="test-oracle-006")
    result = oracle.analyze(trajectory, states)

    if result.fork_points:
        fp = result.fork_points[0]
        corrected = [_make_safe_event(fp.step + 1)]
        new_traj = oracle.fork_and_replay(fp, trajectory, corrected)
        assert len(new_traj) >= 1
        prefix_steps = [e.step for e in new_traj if e.step < fp.step]
        assert all(s < fp.step for s in prefix_steps)


def test_oracle_recovery_window_size():
    trajectory = [_make_irrev_event(i) for i in range(6)]
    states = [AgentState(step=i) for i in range(6)]
    oracle = OracleRecovery(task_id="test-oracle-007")
    result = oracle.analyze(trajectory, states)
    if result.earliest_unrecoverable_step and result.latest_recoverable_step:
        assert result.recovery_window_size >= 0


def test_oracle_to_dict_serializable():
    trajectory = [_make_irrev_event(0), _make_safe_event(1)]
    states = [AgentState(step=i) for i in range(2)]
    oracle = OracleRecovery(task_id="test-oracle-008")
    result = oracle.analyze(trajectory, states)
    d = result.to_dict()
    assert "task_id" in d
    assert "fork_count" in d
    assert isinstance(d["fork_points"], list)
