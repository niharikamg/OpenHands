"""
Timing-controlled intervention studies.

Conducts experiments across benchmark workloads to evaluate recovery
effectiveness, intervention placement strategies, and agent robustness.
Generates reproducible experimental datasets for comparative analysis.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation.adaptive_intervention.benchmark.dacomp import DACompBenchmark, DACompTask
from evaluation.adaptive_intervention.intervention.detector import HighRiskDetector
from evaluation.adaptive_intervention.intervention.injector import ActionInjector
from evaluation.adaptive_intervention.models import (
    AgentState,
    ExecutionOutcome,
    InterventionResult,
    RiskLevel,
    TaskStatus,
    TrajectoryEvent,
)
from evaluation.adaptive_intervention.oracle.recovery import OracleRecovery
from evaluation.adaptive_intervention.trajectory.capture import TrajectoryCapture

logger = logging.getLogger(__name__)


@dataclass
class InterventionTiming:
    """Specifies when and how to trigger an intervention during execution."""

    label: str
    trigger_at_fraction: float  # 0.0 = immediately, 1.0 = at the very end
    strategy: str = "CHECKPOINT"
    enabled: bool = True

    def trigger_step(self, total_steps: int) -> int:
        return max(0, int(total_steps * self.trigger_at_fraction))


TIMING_CONFIGURATIONS: list[InterventionTiming] = [
    InterventionTiming(label="early", trigger_at_fraction=0.25, strategy="CHECKPOINT"),
    InterventionTiming(label="mid", trigger_at_fraction=0.50, strategy="REDIRECT"),
    InterventionTiming(label="late", trigger_at_fraction=0.75, strategy="REVERT"),
    InterventionTiming(label="no_intervention", trigger_at_fraction=1.0, enabled=False),
]


@dataclass
class StudyRun:
    run_id: str
    task_id: str
    timing_label: str
    strategy: str
    intervention_result: InterventionResult | None
    outcome: ExecutionOutcome
    wall_time_seconds: float
    benchmark_score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "timing_label": self.timing_label,
            "strategy": self.strategy,
            "wall_time_seconds": self.wall_time_seconds,
            "benchmark_score": self.benchmark_score,
            "intervention": self.intervention_result.to_dict() if self.intervention_result else None,
            "outcome": self.outcome.to_dict(),
            "metadata": self.metadata,
        }


@dataclass
class StudyResult:
    study_id: str
    task_id: str
    runs: list[StudyRun] = field(default_factory=list)
    best_timing: str | None = None
    best_score: float = 0.0
    no_intervention_score: float = 0.0
    improvement_over_baseline: float = 0.0
    completed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def compute_summary(self) -> None:
        if not self.runs:
            return
        baseline = next((r for r in self.runs if r.timing_label == "no_intervention"), None)
        self.no_intervention_score = baseline.benchmark_score if baseline else 0.0

        intervened = [r for r in self.runs if r.timing_label != "no_intervention"]
        if not intervened:
            return

        best = max(intervened, key=lambda r: r.benchmark_score)
        self.best_timing = best.timing_label
        self.best_score = best.benchmark_score
        self.improvement_over_baseline = self.best_score - self.no_intervention_score

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "task_id": self.task_id,
            "run_count": len(self.runs),
            "best_timing": self.best_timing,
            "best_score": self.best_score,
            "no_intervention_score": self.no_intervention_score,
            "improvement_over_baseline": self.improvement_over_baseline,
            "completed_at": self.completed_at,
            "runs": [r.to_dict() for r in self.runs],
        }


class InterventionStudyRunner:
    """
    Runs timing-controlled intervention studies across DAComp benchmark tasks.

    For each task, the runner executes the agent under multiple intervention
    timing configurations and records recovery effectiveness, intervention
    placement quality, and benchmark scores for comparative analysis.
    """

    def __init__(
        self,
        benchmark: DACompBenchmark,
        output_dir: Path,
        detector: HighRiskDetector | None = None,
        injector: ActionInjector | None = None,
        timing_configs: list[InterventionTiming] | None = None,
    ) -> None:
        self.benchmark = benchmark
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.detector = detector or HighRiskDetector()
        self.injector = injector or ActionInjector()
        self.timing_configs = timing_configs or TIMING_CONFIGURATIONS

    def run_study(self, task_id: str) -> StudyResult:
        task = self.benchmark.get_task(task_id)
        study = StudyResult(
            study_id=str(uuid.uuid4()),
            task_id=task_id,
        )
        logger.info("Starting intervention study for task=%s", task_id)

        for timing in self.timing_configs:
            run = self._execute_run(task, timing)
            study.runs.append(run)
            logger.info(
                "  [%s] score=%.3f wall_time=%.2fs",
                timing.label,
                run.benchmark_score,
                run.wall_time_seconds,
            )

        study.compute_summary()
        self._save_study(study)
        return study

    def run_batch(self, task_ids: list[str] | None = None) -> list[StudyResult]:
        tasks = self.benchmark.list_tasks()
        if task_ids:
            tasks = [t for t in tasks if t.task_id in task_ids]

        results: list[StudyResult] = []
        for task in tasks:
            study = self.run_study(task.task_id)
            results.append(study)

        self._save_batch_summary(results)
        return results

    # ------------------------------------------------------------------
    # Internal execution
    # ------------------------------------------------------------------

    def _execute_run(self, task: DACompTask, timing: InterventionTiming) -> StudyRun:
        t0 = time.monotonic()
        run_id = str(uuid.uuid4())

        capture = TrajectoryCapture(task_id=task.task_id, max_steps=task.max_steps)
        simulated_trajectory = self._simulate_trajectory(task, capture)
        state = AgentState(step=len(simulated_trajectory))

        intervention_result: InterventionResult | None = None
        score = 0.0

        if timing.enabled:
            trigger_step = timing.trigger_step(len(simulated_trajectory))
            prefix = capture.get_prefix(up_to_step=trigger_step)
            detection = self.detector.detect(prefix)

            if detection.should_intervene:
                intervention_result = self.injector.inject(
                    detection=detection,
                    trajectory=simulated_trajectory,
                    current_state=state,
                    strategy=timing.strategy,
                )
                score = self._score_with_intervention(task, intervention_result)
            else:
                score = self._score_without_intervention(task, simulated_trajectory)
        else:
            score = self._score_without_intervention(task, simulated_trajectory)

        outcome = ExecutionOutcome(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED if score > 0.5 else TaskStatus.FAILED,
            final_state=state,
            trajectory=simulated_trajectory,
            total_steps=len(simulated_trajectory),
            wall_time_seconds=time.monotonic() - t0,
            benchmark_score=score,
        )

        return StudyRun(
            run_id=run_id,
            task_id=task.task_id,
            timing_label=timing.label,
            strategy=timing.strategy if timing.enabled else "none",
            intervention_result=intervention_result,
            outcome=outcome,
            wall_time_seconds=time.monotonic() - t0,
            benchmark_score=score,
            metadata={"difficulty": task.difficulty, "category": task.category.value},
        )

    def _simulate_trajectory(
        self, task: DACompTask, capture: TrajectoryCapture
    ) -> list[TrajectoryEvent]:
        """
        Produce a deterministic simulated trajectory for a DAComp task.
        In production this is replaced by a live LLM agent execution loop.
        """
        steps: list[tuple[str, dict[str, Any]]] = [
            ("reasoning", {"text": f"I will solve: {task.description[:80]}"}),
            ("tool_call", {"tool": "read_file", "args": {"path": "input.csv"}}),
            ("tool_result", {"result": task.sample_input}),
            ("reasoning", {"text": "Data loaded. Planning transformation steps."}),
            ("tool_call", {"tool": "write_file", "args": {"path": "intermediate.csv", "data": "..."}}),
            ("tool_result", {"result": {"file": "intermediate.csv"}}),
            ("tool_call", {"tool": "execute_bash", "args": {"cmd": "python transform.py"}}),
            ("tool_result", {"result": {"output": "Done", "exit_code": 0}}),
            ("tool_call", {"tool": "write_file", "args": {"path": "output.csv", "data": "..."}}),
            ("tool_result", {"result": {"file": "output.csv"}}),
            ("reasoning", {"text": "Output written. Task complete."}),
        ]

        for i, (kind, data) in enumerate(steps):
            if kind == "reasoning":
                capture.record_reasoning(step=i, text=data["text"])
            elif kind == "tool_call":
                capture.record_tool_call(step=i, tool_name=data["tool"], args=data.get("args"))
            elif kind == "tool_result":
                capture.record_tool_result(step=i, result=data.get("result"))

        return capture.get_trajectory()

    def _score_with_intervention(
        self, task: DACompTask, intervention: InterventionResult
    ) -> float:
        base = 0.5 if intervention.recovery_success else 0.3
        risk_bonus = {
            RiskLevel.CRITICAL: 0.25,
            RiskLevel.HIGH: 0.20,
            RiskLevel.MEDIUM: 0.10,
            RiskLevel.LOW: 0.05,
        }.get(intervention.risk_level, 0.0)
        difficulty_penalty = max(0.0, (task.difficulty - 3) * 0.05)
        return min(1.0, base + risk_bonus - difficulty_penalty)

    def _score_without_intervention(
        self, task: DACompTask, trajectory: list[TrajectoryEvent]
    ) -> float:
        irreversible_count = sum(1 for e in trajectory if e.is_irreversible)
        base = max(0.0, 0.7 - irreversible_count * 0.05)
        difficulty_penalty = (task.difficulty - 1) * 0.06
        return min(1.0, max(0.0, base - difficulty_penalty))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_study(self, study: StudyResult) -> Path:
        path = self.output_dir / f"{study.task_id}_{study.study_id[:8]}.json"
        path.write_text(json.dumps(study.to_dict(), indent=2))
        logger.info("Saved study to %s", path)
        return path

    def _save_batch_summary(self, results: list[StudyResult]) -> Path:
        summary = {
            "generated_at": datetime.utcnow().isoformat(),
            "study_count": len(results),
            "tasks": [r.task_id for r in results],
            "aggregate": {
                "avg_improvement": sum(r.improvement_over_baseline for r in results) / max(len(results), 1),
                "best_timings": {r.task_id: r.best_timing for r in results},
            },
            "studies": [r.to_dict() for r in results],
        }
        path = self.output_dir / "batch_summary.json"
        path.write_text(json.dumps(summary, indent=2))
        logger.info("Saved batch summary to %s", path)
        return path
