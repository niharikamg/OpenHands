"""
Adaptive Intervention Node — OpenHands Agent Evaluation and Intervention Framework.

Provides:
  - DAComp benchmark integration for LLM agent evaluation
  - Trajectory event capture (complete event streams, reasoning states, tool interactions)
  - Irreversibility analysis of agentic data-engineering workflows
  - Oracle-recovery forking methodology
  - Prefix-only intervention framework with corrective action injection
  - Timing-controlled intervention studies with reproducible experimental datasets
"""

from evaluation.adaptive_intervention.benchmark.dacomp import DACompBenchmark, DACompTask, TaskCategory
from evaluation.adaptive_intervention.intervention.detector import HighRiskDetector, DetectionResult
from evaluation.adaptive_intervention.intervention.injector import ActionInjector
from evaluation.adaptive_intervention.models import (
    AgentState,
    EventType,
    ExecutionOutcome,
    ForkPoint,
    InterventionResult,
    RecoveryStatus,
    RiskLevel,
    TaskStatus,
    TrajectoryEvent,
)
from evaluation.adaptive_intervention.oracle.recovery import OracleRecovery
from evaluation.adaptive_intervention.reporting.logger import ExperimentLogger
from evaluation.adaptive_intervention.reporting.report import ReportGenerator
from evaluation.adaptive_intervention.studies.runner import InterventionStudyRunner
from evaluation.adaptive_intervention.trajectory.analyzer import IrreversibilityAnalyzer
from evaluation.adaptive_intervention.trajectory.capture import TrajectoryCapture, TrajectoryStore

__all__ = [
    "DACompBenchmark",
    "DACompTask",
    "TaskCategory",
    "HighRiskDetector",
    "DetectionResult",
    "ActionInjector",
    "AgentState",
    "EventType",
    "ExecutionOutcome",
    "ForkPoint",
    "InterventionResult",
    "RecoveryStatus",
    "RiskLevel",
    "TaskStatus",
    "TrajectoryEvent",
    "OracleRecovery",
    "ExperimentLogger",
    "ReportGenerator",
    "InterventionStudyRunner",
    "IrreversibilityAnalyzer",
    "TrajectoryCapture",
    "TrajectoryStore",
]
