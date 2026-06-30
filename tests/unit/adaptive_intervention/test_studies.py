"""Tests for timing-controlled intervention studies and report generation."""

import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from evaluation.adaptive_intervention.benchmark.dacomp import DACompBenchmark
from evaluation.adaptive_intervention.studies.runner import (
    InterventionStudyRunner,
    InterventionTiming,
    TIMING_CONFIGURATIONS,
)
from evaluation.adaptive_intervention.reporting.report import ReportGenerator


def test_study_runner_single_task():
    bench = DACompBenchmark()
    with tempfile.TemporaryDirectory() as tmp:
        runner = InterventionStudyRunner(bench, output_dir=Path(tmp))
        result = runner.run_study("dacomp-filter-001")
    assert result.task_id == "dacomp-filter-001"
    assert len(result.runs) == len(TIMING_CONFIGURATIONS)


def test_study_result_has_scores():
    bench = DACompBenchmark()
    with tempfile.TemporaryDirectory() as tmp:
        runner = InterventionStudyRunner(bench, output_dir=Path(tmp))
        result = runner.run_study("dacomp-filter-001")
    for run in result.runs:
        assert 0.0 <= run.benchmark_score <= 1.0


def test_study_result_compute_summary():
    bench = DACompBenchmark()
    with tempfile.TemporaryDirectory() as tmp:
        runner = InterventionStudyRunner(bench, output_dir=Path(tmp))
        result = runner.run_study("dacomp-filter-001")
    assert result.best_timing is not None
    assert 0.0 <= result.best_score <= 1.0


def test_study_runner_saves_json_artifact():
    bench = DACompBenchmark()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        runner = InterventionStudyRunner(bench, output_dir=out)
        runner.run_study("dacomp-filter-001")
        json_files = list(out.glob("*.json"))
        assert len(json_files) >= 1


def test_study_batch_run():
    bench = DACompBenchmark()
    with tempfile.TemporaryDirectory() as tmp:
        runner = InterventionStudyRunner(bench, output_dir=Path(tmp))
        results = runner.run_batch(task_ids=["dacomp-filter-001", "dacomp-join-001"])
    assert len(results) == 2


def test_batch_saves_summary():
    bench = DACompBenchmark()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        runner = InterventionStudyRunner(bench, output_dir=out)
        runner.run_batch(task_ids=["dacomp-filter-001"])
        assert (out / "batch_summary.json").exists()


def test_intervention_timing_trigger_step():
    timing = InterventionTiming(label="mid", trigger_at_fraction=0.5)
    assert timing.trigger_step(10) == 5
    assert timing.trigger_step(0) == 0


def test_report_generator_produces_report():
    bench = DACompBenchmark()
    with tempfile.TemporaryDirectory() as tmp:
        runner = InterventionStudyRunner(bench, output_dir=Path(tmp))
        results = runner.run_batch(task_ids=["dacomp-filter-001", "dacomp-agg-001"])
        gen = ReportGenerator()
        report = gen.generate(results)
    assert report.study_count == 2
    assert report.best_overall_timing is not None
    assert len(report.timing_performance) > 0


def test_report_text_summary_renders():
    bench = DACompBenchmark()
    with tempfile.TemporaryDirectory() as tmp:
        runner = InterventionStudyRunner(bench, output_dir=Path(tmp))
        results = runner.run_batch(task_ids=["dacomp-filter-001"])
        gen = ReportGenerator()
        report = gen.generate(results)
        text = gen.render_text_summary(report)
    assert "ADAPTIVE INTERVENTION NODE" in text
    assert "Timing Configuration Performance" in text


def test_report_saved_to_file():
    bench = DACompBenchmark()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        runner = InterventionStudyRunner(bench, output_dir=out)
        results = runner.run_batch(task_ids=["dacomp-filter-001"])
        gen = ReportGenerator()
        report = gen.generate(results)
        saved = gen.save(report, out / "report.json")
        assert saved.exists()
