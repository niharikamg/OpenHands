"""Tests for trajectory capture and irreversibility analysis."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from evaluation.adaptive_intervention.models import EventType, RiskLevel
from evaluation.adaptive_intervention.trajectory.capture import TrajectoryCapture
from evaluation.adaptive_intervention.trajectory.analyzer import IrreversibilityAnalyzer


def _build_capture_with_events() -> TrajectoryCapture:
    capture = TrajectoryCapture(task_id="test-001")
    capture.record_reasoning(step=0, text="Starting task.")
    capture.record_tool_call(step=1, tool_name="read_file", args={"path": "input.csv"})
    capture.record_tool_result(step=1, result={"rows": [{"id": 1}]})
    capture.record_tool_call(step=2, tool_name="write_file", args={"path": "out.csv"})
    capture.record_tool_result(step=2, result={"file": "out.csv"})
    capture.record_tool_call(step=3, tool_name="execute_bash", args={"cmd": "python run.py"})
    capture.record_tool_result(step=3, result={"output": "ok"})
    return capture


def test_capture_records_all_events():
    capture = _build_capture_with_events()
    trajectory = capture.get_trajectory()
    assert len(trajectory) == 7  # reasoning + 3 tool_call + 3 tool_result


def test_capture_classifies_irreversible_tools():
    capture = TrajectoryCapture(task_id="test-002")
    capture.record_tool_call(step=1, tool_name="write_file", args={"path": "x.csv"})
    capture.record_tool_call(step=2, tool_name="read_file", args={"path": "x.csv"})
    trajectory = capture.get_trajectory()
    write_event = next(e for e in trajectory if e.tool_name == "write_file")
    read_event = next(e for e in trajectory if e.tool_name == "read_file")
    assert write_event.is_irreversible is True
    assert read_event.is_irreversible is False


def test_capture_classifies_execute_bash_as_critical():
    capture = TrajectoryCapture(task_id="test-003")
    capture.record_tool_call(step=1, tool_name="execute_bash", args={"cmd": "rm -rf /tmp/x"})
    event = capture.get_trajectory()[0]
    assert event.risk_level == RiskLevel.CRITICAL
    assert event.is_irreversible is True


def test_capture_get_prefix():
    capture = _build_capture_with_events()
    prefix = capture.get_prefix(up_to_step=2)
    assert all(e.step <= 2 for e in prefix)
    assert len(prefix) < len(capture.get_trajectory())


def test_capture_irreversible_events_filter():
    capture = _build_capture_with_events()
    irrev = capture.irreversible_events()
    assert all(e.is_irreversible for e in irrev)
    assert len(irrev) > 0


def test_capture_listener_fires():
    received = []
    capture = TrajectoryCapture(task_id="test-004")
    capture.add_listener(received.append)
    capture.record_reasoning(step=0, text="Hello")
    assert len(received) == 1
    assert received[0].event_type == EventType.REASONING


def test_capture_current_step():
    capture = TrajectoryCapture(task_id="test-005")
    assert capture.current_step() == 0
    capture.record_reasoning(step=0, text="start")
    capture.record_tool_call(step=5, tool_name="read_file")
    assert capture.current_step() == 5


def test_analyzer_finds_materialization_points():
    capture = _build_capture_with_events()
    analyzer = IrreversibilityAnalyzer(task_id="test-001")
    report = analyzer.analyze(capture.get_trajectory())
    assert report.total_steps == 3
    assert len(report.materialization_points) > 0


def test_analyzer_risk_distribution():
    capture = _build_capture_with_events()
    analyzer = IrreversibilityAnalyzer(task_id="test-001")
    dist = analyzer.summarize_risk_distribution(capture.get_trajectory())
    assert "critical" in dist
    assert "low" in dist
    assert dist["critical"] >= 1  # execute_bash


def test_analyzer_irreversibility_fraction_bounded():
    capture = _build_capture_with_events()
    analyzer = IrreversibilityAnalyzer(task_id="test-001")
    report = analyzer.analyze(capture.get_trajectory())
    assert 0.0 <= report.irreversibility_fraction <= 1.0
