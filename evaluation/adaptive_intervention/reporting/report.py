"""Comparative analysis report generator for intervention study results."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation.adaptive_intervention.studies.runner import StudyResult


@dataclass
class ComparativeReport:
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    study_count: int = 0
    task_results: list[dict[str, Any]] = field(default_factory=list)
    timing_performance: dict[str, dict[str, float]] = field(default_factory=dict)
    strategy_performance: dict[str, dict[str, float]] = field(default_factory=dict)
    difficulty_breakdown: dict[int, dict[str, float]] = field(default_factory=dict)
    overall_avg_improvement: float = 0.0
    best_overall_timing: str | None = None
    best_overall_strategy: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "study_count": self.study_count,
            "overall_avg_improvement": self.overall_avg_improvement,
            "best_overall_timing": self.best_overall_timing,
            "best_overall_strategy": self.best_overall_strategy,
            "timing_performance": self.timing_performance,
            "strategy_performance": self.strategy_performance,
            "difficulty_breakdown": {str(k): v for k, v in self.difficulty_breakdown.items()},
            "task_results": self.task_results,
        }


class ReportGenerator:
    """Builds comparative analysis reports across multiple intervention study results."""

    def generate(self, studies: list[StudyResult]) -> ComparativeReport:
        report = ComparativeReport(study_count=len(studies))

        timing_scores: dict[str, list[float]] = defaultdict(list)
        strategy_scores: dict[str, list[float]] = defaultdict(list)
        difficulty_scores: dict[int, list[float]] = defaultdict(list)
        improvements: list[float] = []

        for study in studies:
            report.task_results.append(study.to_dict())
            improvements.append(study.improvement_over_baseline)

            for run in study.runs:
                timing_scores[run.timing_label].append(run.benchmark_score)
                strategy_scores[run.strategy].append(run.benchmark_score)
                diff = run.metadata.get("difficulty", 3)
                if isinstance(diff, int):
                    difficulty_scores[diff].append(run.benchmark_score)

        report.overall_avg_improvement = (
            sum(improvements) / len(improvements) if improvements else 0.0
        )

        for label, scores in timing_scores.items():
            report.timing_performance[label] = {
                "avg_score": sum(scores) / len(scores),
                "min_score": min(scores),
                "max_score": max(scores),
                "sample_count": len(scores),
            }

        for strat, scores in strategy_scores.items():
            report.strategy_performance[strat] = {
                "avg_score": sum(scores) / len(scores),
                "sample_count": len(scores),
            }

        for diff, scores in difficulty_scores.items():
            report.difficulty_breakdown[diff] = {
                "avg_score": sum(scores) / len(scores),
                "sample_count": len(scores),
            }

        if report.timing_performance:
            report.best_overall_timing = max(
                report.timing_performance,
                key=lambda k: report.timing_performance[k]["avg_score"],
            )

        if report.strategy_performance:
            report.best_overall_strategy = max(
                report.strategy_performance,
                key=lambda k: report.strategy_performance[k]["avg_score"],
            )

        return report

    def save(self, report: ComparativeReport, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report.to_dict(), indent=2))
        return output_path

    def render_text_summary(self, report: ComparativeReport) -> str:
        lines = [
            "=" * 60,
            "ADAPTIVE INTERVENTION NODE — COMPARATIVE REPORT",
            f"Generated: {report.generated_at}",
            f"Studies: {report.study_count}",
            "=" * 60,
            "",
            f"Overall avg improvement over baseline: {report.overall_avg_improvement:+.3f}",
            f"Best timing configuration:             {report.best_overall_timing}",
            f"Best intervention strategy:            {report.best_overall_strategy}",
            "",
            "Timing Configuration Performance:",
        ]
        for label, stats in sorted(report.timing_performance.items()):
            lines.append(
                f"  {label:<20} avg={stats['avg_score']:.3f}  "
                f"[{stats['min_score']:.3f}, {stats['max_score']:.3f}]  n={stats['sample_count']}"
            )
        lines.append("")
        lines.append("Strategy Performance:")
        for strat, stats in sorted(report.strategy_performance.items()):
            lines.append(
                f"  {strat:<20} avg={stats['avg_score']:.3f}  n={stats['sample_count']}"
            )
        lines.append("")
        lines.append("By Difficulty:")
        for diff in sorted(report.difficulty_breakdown):
            stats = report.difficulty_breakdown[diff]
            lines.append(
                f"  Difficulty {diff}: avg={stats['avg_score']:.3f}  n={stats['sample_count']}"
            )
        lines.append("=" * 60)
        return "\n".join(lines)
