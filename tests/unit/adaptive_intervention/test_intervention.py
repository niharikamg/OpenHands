"""Tests for the prefix-only intervention detector and action injector."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from evaluation.adaptive_intervention.models import AgentState, EventType, RiskLevel, TrajectoryEvent
from evaluation.adaptive_intervention.intervention.detector import HighRiskDetector
from evaluation.adaptive_intervention.intervention.injector import ActionInjector


def _make_event(step, tool_name=None, risk=RiskLevel.LOW, irreversible=False, event_type=EventType.TOOL_CALL, reasoning=None):
    return TrajectoryEvent(
        event_type=event_type,
        step=step,
        tool_name=tool_name,
        is_irreversible=irreversible,
        risk_level=risk,
        reasoning=reasoning,
    )


def test_detector_empty_trajectory_no_intervention():
    detector = HighRiskDetector()
    result = detector.detect([])
    assert result.should_intervene is False
    assert result.confidence == 0.0


def test_detector_low_risk_trajectory_no_intervention():
    trajectory = [
        _make_event(0, "read_file", RiskLevel.LOW),
        _make_event(1, "search", RiskLevel.LOW),
        _make_event(2, "list_files", RiskLevel.LOW),
    ]
    detector = HighRiskDetector()
    result = detector.detect(trajectory)
    assert result.should_intervene is False


def test_detector_accumulating_irreversible_triggers_intervention():
    trajectory = [
        _make_event(0, "write_file", RiskLevel.HIGH, irreversible=True),
        _make_event(1, "write_file", RiskLevel.HIGH, irreversible=True),
        _make_event(2, "write_file", RiskLevel.HIGH, irreversible=True),
        _make_event(3, "write_file", RiskLevel.HIGH, irreversible=True),
    ]
    detector = HighRiskDetector(intervene_threshold=0.5)
    result = detector.detect(trajectory)
    assert result.should_intervene is True
    assert len(result.signals) > 0


def test_detector_repeated_tool_failures_triggers_intervention():
    trajectory = []
    for i in range(4):
        e = TrajectoryEvent(
            event_type=EventType.TOOL_RESULT,
            step=i,
            metadata={"error": f"Error at step {i}"},
        )
        trajectory.append(e)
    detector = HighRiskDetector(intervene_threshold=0.5)
    result = detector.detect(trajectory)
    assert result.should_intervene is True


def test_detector_delete_without_read_is_critical():
    trajectory = [
        _make_event(0, "write_file", RiskLevel.HIGH, irreversible=True),
        _make_event(1, "delete_file", RiskLevel.CRITICAL, irreversible=True),
    ]
    detector = HighRiskDetector(intervene_threshold=0.5)
    result = detector.detect(trajectory)
    critical_signals = [s for s in result.signals if s.risk_level == RiskLevel.CRITICAL]
    assert len(critical_signals) > 0


def test_detector_uncertainty_in_reasoning():
    trajectory = [
        _make_event(0, event_type=EventType.REASONING, reasoning="I'm not sure what to do here, maybe try this."),
        _make_event(1, event_type=EventType.REASONING, reasoning="I think this might work, unclear though."),
    ]
    detector = HighRiskDetector()
    result = detector.detect(trajectory)
    assert len(result.signals) > 0


def test_detector_result_has_intervention_step():
    trajectory = [
        _make_event(i, "write_file", RiskLevel.HIGH, irreversible=True)
        for i in range(4)
    ]
    detector = HighRiskDetector(intervene_threshold=0.5)
    result = detector.detect(trajectory)
    if result.should_intervene:
        assert result.intervention_step is not None
        assert result.intervention_step >= 0


def test_injector_checkpoint_strategy():
    trajectory = [_make_event(i, "write_file", RiskLevel.HIGH, irreversible=True) for i in range(4)]
    detector = HighRiskDetector(intervene_threshold=0.5)
    detection = detector.detect(trajectory)
    injector = ActionInjector(default_strategy="CHECKPOINT")
    state = AgentState(step=4, intermediate_outputs={"result": [1, 2, 3]})
    result = injector.inject(detection, trajectory, state, strategy="CHECKPOINT")
    assert result.strategy == "CHECKPOINT"
    assert len(result.corrective_actions) > 0


def test_injector_abort_strategy():
    trajectory = [_make_event(i, "delete_file", RiskLevel.CRITICAL, irreversible=True) for i in range(3)]
    detector = HighRiskDetector(intervene_threshold=0.5)
    detection = detector.detect(trajectory)
    injector = ActionInjector(default_strategy="ABORT")
    state = AgentState(step=3)
    result = injector.inject(detection, trajectory, state, strategy="ABORT")
    assert result.strategy == "ABORT"
    assert any(a["action_type"] == "ABORT" for a in result.corrective_actions)


def test_injector_invalid_strategy_raises():
    try:
        ActionInjector(default_strategy="INVALID")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_injector_timing_recorded():
    trajectory = [_make_event(i, "write_file", RiskLevel.HIGH, irreversible=True) for i in range(4)]
    detector = HighRiskDetector(intervene_threshold=0.5)
    detection = detector.detect(trajectory)
    injector = ActionInjector()
    state = AgentState(step=4)
    result = injector.inject(detection, trajectory, state)
    assert result.timing_ms >= 0.0
