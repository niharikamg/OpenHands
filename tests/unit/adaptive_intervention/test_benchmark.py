"""Tests for DAComp benchmark integration."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from evaluation.adaptive_intervention.benchmark.dacomp import DACompBenchmark, TaskCategory


def test_benchmark_loads_builtin_tasks():
    bench = DACompBenchmark()
    assert len(bench) == 5


def test_benchmark_list_all_tasks():
    bench = DACompBenchmark()
    tasks = bench.list_tasks()
    assert len(tasks) == 5


def test_benchmark_filter_by_category():
    bench = DACompBenchmark()
    filter_tasks = bench.list_tasks(category=TaskCategory.FILTER)
    assert all(t.category == TaskCategory.FILTER for t in filter_tasks)
    assert len(filter_tasks) >= 1


def test_benchmark_filter_by_difficulty():
    bench = DACompBenchmark()
    easy = bench.list_tasks(max_difficulty=2)
    assert all(t.difficulty <= 2 for t in easy)


def test_benchmark_filter_by_tags():
    bench = DACompBenchmark()
    tasks = bench.list_tasks(tags=["join"])
    assert len(tasks) >= 1
    assert all(any(tag in t.tags for tag in ["join"]) for t in tasks)


def test_benchmark_get_task_valid():
    bench = DACompBenchmark()
    task = bench.get_task("dacomp-filter-001")
    assert task.task_id == "dacomp-filter-001"
    assert task.category == TaskCategory.FILTER
    assert task.difficulty == 1


def test_benchmark_get_task_invalid_raises():
    bench = DACompBenchmark()
    try:
        bench.get_task("does-not-exist")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass


def test_benchmark_tasks_sorted_by_difficulty():
    bench = DACompBenchmark()
    tasks = bench.list_tasks()
    difficulties = [t.difficulty for t in tasks]
    assert difficulties == sorted(difficulties)


def test_benchmark_score_exact_match():
    bench = DACompBenchmark()
    task = bench.get_task("dacomp-filter-001")
    score = bench.score_output(task, task.expected_output)
    assert score == 1.0


def test_benchmark_score_none_output():
    bench = DACompBenchmark()
    task = bench.get_task("dacomp-filter-001")
    assert bench.score_output(task, None) == 0.0


def test_benchmark_score_partial_list():
    bench = DACompBenchmark()
    task = bench.get_task("dacomp-agg-001")
    partial = task.expected_output[:1]
    score = bench.score_output(task, partial)
    assert 0.0 < score < 1.0


def test_benchmark_task_to_dict():
    bench = DACompBenchmark()
    task = bench.get_task("dacomp-compose-001")
    d = task.to_dict()
    assert d["task_id"] == "dacomp-compose-001"
    assert d["category"] == "compose"
    assert d["difficulty"] == 5


def test_benchmark_all_tasks_have_required_fields():
    bench = DACompBenchmark()
    for task in bench.list_tasks():
        assert task.task_id
        assert task.description
        assert task.sample_input is not None
        assert task.expected_output is not None
        assert 1 <= task.difficulty <= 5
