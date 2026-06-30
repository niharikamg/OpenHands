"""Structured logging and artifact generation for intervention study experiments."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation.adaptive_intervention.models import (
    ExecutionOutcome,
    InterventionResult,
    TrajectoryEvent,
)
from evaluation.adaptive_intervention.studies.runner import StudyResult


def configure_structured_logging(level: int = logging.INFO, log_file: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        handlers=handlers,
    )


class ExperimentLogger:
    """Logs experiment events as structured JSON entries for reproducible analysis."""

    def __init__(self, experiment_id: str, log_dir: Path) -> None:
        self.experiment_id = experiment_id
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._entries: list[dict[str, Any]] = []
        self._log_path = self.log_dir / f"{experiment_id}.jsonl"

    def log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        entry = {
            "experiment_id": self.experiment_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            **payload,
        }
        self._entries.append(entry)
        with self._log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def log_trajectory_event(self, event: TrajectoryEvent) -> None:
        self.log_event("trajectory_event", event.to_dict())

    def log_intervention(self, result: InterventionResult) -> None:
        self.log_event("intervention", result.to_dict())

    def log_outcome(self, outcome: ExecutionOutcome) -> None:
        self.log_event("outcome", outcome.to_dict())

    def log_study_result(self, result: StudyResult) -> None:
        self.log_event("study_result", result.to_dict())

    def get_entries(self, event_type: str | None = None) -> list[dict[str, Any]]:
        if event_type:
            return [e for e in self._entries if e.get("event_type") == event_type]
        return list(self._entries)

    def flush_artifact(self, name: str, data: Any) -> Path:
        path = self.log_dir / f"{self.experiment_id}_{name}.json"
        path.write_text(json.dumps(data, indent=2))
        return path
