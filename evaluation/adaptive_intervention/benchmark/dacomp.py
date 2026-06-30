"""DAComp benchmark integration for evaluating LLM agents on data-engineering tasks."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TaskCategory(str, Enum):
    FILTER = "filter"
    JOIN = "join"
    AGGREGATE = "aggregate"
    TRANSFORM = "transform"
    EXTRACT = "extract"
    COMPOSE = "compose"


@dataclass
class DACompTask:
    task_id: str
    category: TaskCategory
    description: str
    input_schema: dict[str, Any]
    expected_output_schema: dict[str, Any]
    sample_input: dict[str, Any]
    expected_output: Any
    difficulty: int  # 1 (easy) – 5 (hard)
    max_steps: int = 20
    time_limit_seconds: float = 300.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "category": self.category.value,
            "description": self.description,
            "difficulty": self.difficulty,
            "max_steps": self.max_steps,
            "time_limit_seconds": self.time_limit_seconds,
            "tags": self.tags,
        }


class DACompBenchmark:
    """Loads and serves DAComp benchmark tasks for agent evaluation."""

    _BUILTIN_TASKS: list[dict[str, Any]] = [
        {
            "task_id": "dacomp-filter-001",
            "category": "filter",
            "description": (
                "Filter a CSV dataset of sales records to return only rows where "
                "revenue > 10000 and region == 'WEST'. Write the result to output.csv."
            ),
            "input_schema": {"type": "csv", "columns": ["id", "region", "revenue", "date"]},
            "expected_output_schema": {"type": "csv", "columns": ["id", "region", "revenue", "date"]},
            "sample_input": {
                "rows": [
                    {"id": 1, "region": "WEST", "revenue": 15000, "date": "2025-01-01"},
                    {"id": 2, "region": "EAST", "revenue": 20000, "date": "2025-01-02"},
                    {"id": 3, "region": "WEST", "revenue": 8000, "date": "2025-01-03"},
                ]
            },
            "expected_output": {"rows": [{"id": 1, "region": "WEST", "revenue": 15000, "date": "2025-01-01"}]},
            "difficulty": 1,
            "tags": ["filter", "csv", "threshold"],
        },
        {
            "task_id": "dacomp-join-001",
            "category": "join",
            "description": (
                "Join users.csv and orders.csv on user_id. Keep only users who have "
                "at least one order. Write the merged result to joined.csv."
            ),
            "input_schema": {
                "type": "multi_csv",
                "tables": {
                    "users": ["user_id", "name", "email"],
                    "orders": ["order_id", "user_id", "amount", "status"],
                },
            },
            "expected_output_schema": {
                "type": "csv",
                "columns": ["user_id", "name", "email", "order_id", "amount", "status"],
            },
            "sample_input": {
                "users": [
                    {"user_id": 1, "name": "Alice", "email": "alice@example.com"},
                    {"user_id": 2, "name": "Bob", "email": "bob@example.com"},
                ],
                "orders": [
                    {"order_id": 101, "user_id": 1, "amount": 250.0, "status": "shipped"},
                ],
            },
            "expected_output": {
                "rows": [
                    {
                        "user_id": 1,
                        "name": "Alice",
                        "email": "alice@example.com",
                        "order_id": 101,
                        "amount": 250.0,
                        "status": "shipped",
                    }
                ]
            },
            "difficulty": 2,
            "tags": ["join", "inner-join", "multi-table"],
        },
        {
            "task_id": "dacomp-agg-001",
            "category": "aggregate",
            "description": (
                "Compute total revenue and average order value grouped by region "
                "from transactions.csv. Write summary to report.json."
            ),
            "input_schema": {"type": "csv", "columns": ["transaction_id", "region", "amount", "date"]},
            "expected_output_schema": {
                "type": "json",
                "fields": ["region", "total_revenue", "avg_order_value", "transaction_count"],
            },
            "sample_input": {
                "rows": [
                    {"transaction_id": 1, "region": "WEST", "amount": 100.0, "date": "2025-01-01"},
                    {"transaction_id": 2, "region": "WEST", "amount": 200.0, "date": "2025-01-02"},
                    {"transaction_id": 3, "region": "EAST", "amount": 150.0, "date": "2025-01-03"},
                ]
            },
            "expected_output": [
                {"region": "WEST", "total_revenue": 300.0, "avg_order_value": 150.0, "transaction_count": 2},
                {"region": "EAST", "total_revenue": 150.0, "avg_order_value": 150.0, "transaction_count": 1},
            ],
            "difficulty": 2,
            "tags": ["aggregation", "groupby", "summary"],
        },
        {
            "task_id": "dacomp-transform-001",
            "category": "transform",
            "description": (
                "Normalize the 'score' column in students.csv to a 0–1 range using "
                "min-max normalization. Add a 'grade' column: A if score>=0.9, B if "
                ">=0.75, C if >=0.6, else F. Write to students_normalized.csv."
            ),
            "input_schema": {"type": "csv", "columns": ["student_id", "name", "score"]},
            "expected_output_schema": {
                "type": "csv",
                "columns": ["student_id", "name", "score", "normalized_score", "grade"],
            },
            "sample_input": {
                "rows": [
                    {"student_id": 1, "name": "Alice", "score": 95},
                    {"student_id": 2, "name": "Bob", "score": 72},
                    {"student_id": 3, "name": "Carol", "score": 60},
                ]
            },
            "expected_output": {
                "rows": [
                    {"student_id": 1, "name": "Alice", "score": 95, "normalized_score": 1.0, "grade": "A"},
                    {"student_id": 2, "name": "Bob", "score": 72, "normalized_score": 0.343, "grade": "C"},
                    {"student_id": 3, "name": "Carol", "score": 60, "normalized_score": 0.0, "grade": "F"},
                ]
            },
            "difficulty": 3,
            "tags": ["normalization", "feature-engineering", "conditional"],
        },
        {
            "task_id": "dacomp-compose-001",
            "category": "compose",
            "description": (
                "Multi-stage pipeline: (1) load raw_events.csv, (2) filter to "
                "event_type='purchase', (3) join with product_catalog.csv on product_id "
                "to enrich with product_name and category, (4) aggregate total spend per "
                "category, (5) write final_report.json with top 3 categories by spend."
            ),
            "input_schema": {
                "type": "multi_csv",
                "tables": {
                    "raw_events": ["event_id", "event_type", "product_id", "amount", "user_id"],
                    "product_catalog": ["product_id", "product_name", "category"],
                },
            },
            "expected_output_schema": {
                "type": "json",
                "fields": ["rank", "category", "total_spend"],
            },
            "sample_input": {
                "raw_events": [
                    {"event_id": 1, "event_type": "purchase", "product_id": "P1", "amount": 50.0, "user_id": 1},
                    {"event_id": 2, "event_type": "view", "product_id": "P2", "amount": 0, "user_id": 2},
                    {"event_id": 3, "event_type": "purchase", "product_id": "P2", "amount": 30.0, "user_id": 3},
                    {"event_id": 4, "event_type": "purchase", "product_id": "P1", "amount": 70.0, "user_id": 4},
                ],
                "product_catalog": [
                    {"product_id": "P1", "product_name": "Widget A", "category": "Electronics"},
                    {"product_id": "P2", "product_name": "Widget B", "category": "Apparel"},
                ],
            },
            "expected_output": [
                {"rank": 1, "category": "Electronics", "total_spend": 120.0},
                {"rank": 2, "category": "Apparel", "total_spend": 30.0},
            ],
            "difficulty": 5,
            "tags": ["multi-stage", "filter", "join", "aggregate", "rank"],
        },
    ]

    def __init__(self, task_dir: Path | None = None) -> None:
        self._tasks: dict[str, DACompTask] = {}
        self._load_builtin_tasks()
        if task_dir and task_dir.exists():
            self._load_from_directory(task_dir)

    def _load_builtin_tasks(self) -> None:
        for raw in self._BUILTIN_TASKS:
            task = DACompTask(
                task_id=raw["task_id"],
                category=TaskCategory(raw["category"]),
                description=raw["description"],
                input_schema=raw["input_schema"],
                expected_output_schema=raw["expected_output_schema"],
                sample_input=raw["sample_input"],
                expected_output=raw["expected_output"],
                difficulty=raw["difficulty"],
                tags=raw.get("tags", []),
            )
            self._tasks[task.task_id] = task

    def _load_from_directory(self, task_dir: Path) -> None:
        for json_file in task_dir.glob("*.json"):
            try:
                raw = json.loads(json_file.read_text())
                task = DACompTask(
                    task_id=raw.get("task_id", str(uuid.uuid4())),
                    category=TaskCategory(raw["category"]),
                    description=raw["description"],
                    input_schema=raw.get("input_schema", {}),
                    expected_output_schema=raw.get("expected_output_schema", {}),
                    sample_input=raw.get("sample_input", {}),
                    expected_output=raw.get("expected_output"),
                    difficulty=raw.get("difficulty", 3),
                    max_steps=raw.get("max_steps", 20),
                    time_limit_seconds=raw.get("time_limit_seconds", 300.0),
                    tags=raw.get("tags", []),
                    metadata=raw.get("metadata", {}),
                )
                self._tasks[task.task_id] = task
            except (KeyError, ValueError):
                pass

    def get_task(self, task_id: str) -> DACompTask:
        if task_id not in self._tasks:
            raise KeyError(f"Task '{task_id}' not found in DAComp benchmark.")
        return self._tasks[task_id]

    def list_tasks(
        self,
        category: TaskCategory | None = None,
        max_difficulty: int | None = None,
        tags: list[str] | None = None,
    ) -> list[DACompTask]:
        tasks = list(self._tasks.values())
        if category:
            tasks = [t for t in tasks if t.category == category]
        if max_difficulty is not None:
            tasks = [t for t in tasks if t.difficulty <= max_difficulty]
        if tags:
            tag_set = set(tags)
            tasks = [t for t in tasks if tag_set.intersection(t.tags)]
        return sorted(tasks, key=lambda t: (t.difficulty, t.task_id))

    def score_output(self, task: DACompTask, agent_output: Any) -> float:
        """Return a 0–1 correctness score by comparing agent output to expected output."""
        expected = task.expected_output
        if agent_output is None:
            return 0.0
        if expected == agent_output:
            return 1.0
        if isinstance(expected, list) and isinstance(agent_output, list):
            return self._score_list(expected, agent_output)
        if isinstance(expected, dict) and isinstance(agent_output, dict):
            return self._score_dict(expected, agent_output)
        return 0.0

    def _score_list(self, expected: list, actual: list) -> float:
        if not expected:
            return 1.0 if not actual else 0.0
        matched = sum(1 for e in expected if e in actual)
        precision = matched / len(actual) if actual else 0.0
        recall = matched / len(expected)
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def _score_dict(self, expected: dict, actual: dict) -> float:
        if not expected:
            return 1.0
        matching_keys = set(expected) & set(actual)
        if not matching_keys:
            return 0.0
        scores = [1.0 if expected[k] == actual[k] else 0.0 for k in matching_keys]
        return sum(scores) / len(expected)

    def __len__(self) -> int:
        return len(self._tasks)
