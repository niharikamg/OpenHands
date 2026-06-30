"""Trajectory event capture for LLM agent execution on OpenHands."""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from evaluation.adaptive_intervention.models import (
    AgentState,
    EventType,
    RiskLevel,
    TrajectoryEvent,
)

logger = logging.getLogger(__name__)

# Tools that write durable state and are considered irreversible
_IRREVERSIBLE_TOOLS = {
    "write_file",
    "execute_bash",
    "run_command",
    "delete_file",
    "create_directory",
    "http_post",
    "http_put",
    "http_delete",
    "database_write",
    "database_delete",
    "api_write",
}

_HIGH_RISK_TOOLS = {
    "execute_bash",
    "run_command",
    "delete_file",
    "http_delete",
    "database_delete",
}


def _classify_risk(tool_name: str | None, tool_args: dict[str, Any]) -> tuple[bool, RiskLevel]:
    """Return (is_irreversible, risk_level) for a tool call."""
    if tool_name is None:
        return False, RiskLevel.LOW
    name = tool_name.lower()
    is_irreversible = name in _IRREVERSIBLE_TOOLS
    if name in _HIGH_RISK_TOOLS:
        return True, RiskLevel.CRITICAL
    if is_irreversible:
        return True, RiskLevel.HIGH
    if "read" in name or "list" in name or "search" in name:
        return False, RiskLevel.LOW
    return False, RiskLevel.MEDIUM


@dataclass
class TrajectoryCapture:
    """
    Hooks into agent execution steps to record complete trajectory event streams.

    Usage:
        capture = TrajectoryCapture(task_id="dacomp-filter-001")
        capture.record_reasoning(step=0, text="I will read the input CSV first.")
        capture.record_tool_call(step=1, tool_name="read_file", args={"path": "input.csv"})
        capture.record_tool_result(step=1, result={"rows": [...]})
        ...
        trajectory = capture.get_trajectory()
    """

    task_id: str
    max_steps: int = 50
    _events: list[TrajectoryEvent] = field(default_factory=list, init=False)
    _state_history: list[AgentState] = field(default_factory=list, init=False)
    _current_state: AgentState = field(init=False)
    _step_times: dict[int, float] = field(default_factory=dict, init=False)
    _listeners: list[Callable[[TrajectoryEvent], None]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._current_state = AgentState(step=0)

    # ------------------------------------------------------------------
    # Public recording API
    # ------------------------------------------------------------------

    def record_reasoning(self, step: int, text: str) -> TrajectoryEvent:
        event = TrajectoryEvent(
            event_type=EventType.REASONING,
            step=step,
            reasoning=text,
        )
        return self._append(event)

    def record_tool_call(
        self,
        step: int,
        tool_name: str,
        args: dict[str, Any] | None = None,
    ) -> TrajectoryEvent:
        args = args or {}
        is_irrev, risk = _classify_risk(tool_name, args)
        self._step_times[step] = time.monotonic()
        event = TrajectoryEvent(
            event_type=EventType.TOOL_CALL,
            step=step,
            tool_name=tool_name,
            tool_args=args,
            is_irreversible=is_irrev,
            risk_level=risk,
        )
        return self._append(event)

    def record_tool_result(
        self,
        step: int,
        result: Any,
        error: str | None = None,
    ) -> TrajectoryEvent:
        elapsed_ms = 0.0
        if step in self._step_times:
            elapsed_ms = (time.monotonic() - self._step_times[step]) * 1000

        event = TrajectoryEvent(
            event_type=EventType.TOOL_RESULT,
            step=step,
            tool_result=result,
            metadata={"error": error, "elapsed_ms": elapsed_ms},
        )
        self._apply_result_to_state(step, result, event)
        return self._append(event)

    def record_state_write(
        self,
        step: int,
        key: str,
        value: Any,
        is_irreversible: bool = True,
    ) -> TrajectoryEvent:
        self._current_state.intermediate_outputs[key] = value
        event = TrajectoryEvent(
            event_type=EventType.STATE_WRITE,
            step=step,
            state_delta={key: value},
            is_irreversible=is_irreversible,
            risk_level=RiskLevel.HIGH if is_irreversible else RiskLevel.LOW,
        )
        self._snapshot_state(step)
        return self._append(event)

    def record_observation(self, step: int, observation: str) -> TrajectoryEvent:
        event = TrajectoryEvent(
            event_type=EventType.OBSERVATION,
            step=step,
            reasoning=observation,
        )
        return self._append(event)

    def add_listener(self, fn: Callable[[TrajectoryEvent], None]) -> None:
        """Register a callback that fires on every new event (used by the intervention detector)."""
        self._listeners.append(fn)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_trajectory(self) -> list[TrajectoryEvent]:
        return list(self._events)

    def get_prefix(self, up_to_step: int) -> list[TrajectoryEvent]:
        return [e for e in self._events if e.step <= up_to_step]

    def get_state_at(self, step: int) -> AgentState | None:
        for state in reversed(self._state_history):
            if state.step <= step:
                return state
        return None

    def current_step(self) -> int:
        return self._events[-1].step if self._events else 0

    def irreversible_events(self) -> list[TrajectoryEvent]:
        return [e for e in self._events if e.is_irreversible]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append(self, event: TrajectoryEvent) -> TrajectoryEvent:
        self._events.append(event)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("Trajectory listener raised an exception")
        return event

    def _apply_result_to_state(self, step: int, result: Any, event: TrajectoryEvent) -> None:
        if not isinstance(result, dict):
            return
        if "file" in result or "path" in result:
            path = result.get("file") or result.get("path", "")
            if path:
                self._current_state.files_written.append(str(path))
        if "command" in result:
            self._current_state.commands_executed.append(result["command"])
        self._snapshot_state(step)

    def _snapshot_state(self, step: int) -> None:
        snapshot = self._current_state.clone()
        snapshot.step = step
        snapshot.timestamp = datetime.utcnow()
        self._state_history.append(snapshot)


class TrajectoryStore:
    """Persists and retrieves trajectories for post-hoc analysis."""

    def __init__(self, store_dir: Path) -> None:
        self.store_dir = store_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, list[str]] = defaultdict(list)

    def save(self, task_id: str, run_id: str, capture: TrajectoryCapture) -> Path:
        run_dir = self.store_dir / task_id / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "task_id": task_id,
            "run_id": run_id,
            "captured_at": datetime.utcnow().isoformat(),
            "events": [e.to_dict() for e in capture.get_trajectory()],
        }
        out_path = run_dir / "trajectory.json"
        out_path.write_text(json.dumps(payload, indent=2))
        self._index[task_id].append(run_id)
        logger.info("Saved trajectory for task=%s run=%s to %s", task_id, run_id, out_path)
        return out_path

    def load(self, task_id: str, run_id: str) -> list[dict[str, Any]]:
        path = self.store_dir / task_id / run_id / "trajectory.json"
        if not path.exists():
            raise FileNotFoundError(f"No trajectory found at {path}")
        data = json.loads(path.read_text())
        return data["events"]

    def list_runs(self, task_id: str) -> list[str]:
        task_dir = self.store_dir / task_id
        if not task_dir.exists():
            return []
        return [d.name for d in task_dir.iterdir() if d.is_dir()]
