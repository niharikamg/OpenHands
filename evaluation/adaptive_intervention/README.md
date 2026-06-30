# Adaptive Intervention Node

OpenHands Agent Evaluation and Intervention Framework for agentic data-engineering workflows.

## Overview

Adaptive Intervention Node is a research framework built on the [OpenHands](https://github.com/All-Hands-AI/OpenHands) agent platform. It evaluates LLM agents against the DAComp benchmark, captures complete execution trajectories, identifies irreversible failure points, and injects corrective actions before unrecoverable state transitions occur.

```
DAComp Benchmark
      │
      ▼
 Agent Execution ──► Trajectory Capture ──► Irreversibility Analysis
                                                      │
                                          Oracle-Recovery Forking
                                                      │
                                        Prefix-Only Intervention
                                        (Detector + Injector)
                                                      │
                                        Timing-Controlled Studies
                                                      │
                                        Comparative Report & Artifacts
```

## Key Components

### DAComp Benchmark
Five data-engineering task categories evaluated against LLM agents:

| Category | Task ID | Difficulty |
|---|---|---|
| Filter | `dacomp-filter-001` | 1 |
| Join | `dacomp-join-001` | 2 |
| Aggregate | `dacomp-agg-001` | 2 |
| Transform | `dacomp-transform-001` | 3 |
| Multi-stage Compose | `dacomp-compose-001` | 5 |

### Trajectory Capture
Records the complete event stream for every agent execution:
- Tool calls and results (with irreversibility and risk classification)
- Intermediate reasoning states
- State writes and downstream dependencies
- Listener hooks for real-time monitoring

### Irreversibility Analysis
Detects when incorrect intermediate outputs become durably materialized and traces how errors propagate across downstream execution stages as trusted system state.

### Oracle-Recovery Forking
Identifies the **earliest unrecoverable execution step** in a multi-stage pipeline by:
1. Enumerating all irreversible fork points in the trajectory
2. Classifying each as RECOVERABLE or UNRECOVERABLE using oracle ground truth
3. Ranking recovery candidates by probability and estimated cost
4. Supporting fork-and-replay on any identified prefix

### Prefix-Only Intervention
Detects high-risk execution trajectories from **partial agent histories** before irreversible transitions occur. Five heuristics:

| Heuristic | Trigger |
|---|---|
| Irreversible accumulation | 3+ irreversible ops in a sliding window |
| Repeated tool failures | 2+ tool errors in the prefix |
| Anomalous sequences | Destructive call without prior read/validation |
| Escalating risk | Risk level trending upward across steps |
| Reasoning uncertainty | Explicit uncertainty markers in agent reasoning |

Five intervention strategies:

| Strategy | Action |
|---|---|
| `CHECKPOINT` | Force validation of intermediate state before proceeding |
| `REVERT` | Roll back the most recent irreversible operation |
| `REDIRECT` | Replace the next tool call with a safer alternative |
| `REROUTE` | Re-route through a validated safe sub-trajectory |
| `ABORT` | Halt execution and surface the risk to the caller |

### Timing-Controlled Studies
Runs each task under four intervention timing configurations and records recovery effectiveness:

| Timing | Fraction | Default Strategy |
|---|---|---|
| Early | 25% of steps | CHECKPOINT |
| Mid | 50% of steps | REDIRECT |
| Late | 75% of steps | REVERT |
| No intervention | — | baseline |

## Project Structure

```
evaluation/adaptive_intervention/
├── models.py                  # Core data models
├── benchmark/
│   └── dacomp.py              # DAComp benchmark tasks and scoring
├── trajectory/
│   ├── capture.py             # Trajectory event capture
│   └── analyzer.py            # Irreversibility and propagation analysis
├── oracle/
│   └── recovery.py            # Oracle-recovery forking methodology
├── intervention/
│   ├── detector.py            # Prefix-only high-risk detector
│   └── injector.py            # Corrective action injector
├── studies/
│   └── runner.py              # Timing-controlled study runner
└── reporting/
    ├── logger.py              # Structured experiment logger
    └── report.py              # Comparative analysis report generator
```

## Quick Start

```python
from pathlib import Path
from evaluation.adaptive_intervention import (
    DACompBenchmark,
    InterventionStudyRunner,
    ReportGenerator,
)

benchmark = DACompBenchmark()

runner = InterventionStudyRunner(benchmark, output_dir=Path("results/"))
results = runner.run_batch()

report = ReportGenerator().generate(results)
print(ReportGenerator().render_text_summary(report))
```

### Run a single task with manual trajectory capture

```python
from evaluation.adaptive_intervention import (
    TrajectoryCapture,
    HighRiskDetector,
    ActionInjector,
    AgentState,
)

capture = TrajectoryCapture(task_id="dacomp-filter-001")

# Hook the detector to fire on every event
detector = HighRiskDetector(intervene_threshold=0.65)
injector = ActionInjector(default_strategy="CHECKPOINT")

def on_event(event):
    prefix = capture.get_prefix(up_to_step=event.step)
    detection = detector.detect(prefix)
    if detection.should_intervene:
        result = injector.inject(detection, prefix, AgentState(step=event.step))
        print(f"Intervention triggered at step {event.step}: {result.strategy}")

capture.add_listener(on_event)

# Record agent execution
capture.record_reasoning(step=0, text="Loading input data.")
capture.record_tool_call(step=1, tool_name="read_file", args={"path": "input.csv"})
capture.record_tool_result(step=1, result={"rows": [...]})
```

### Oracle-recovery analysis

```python
from evaluation.adaptive_intervention import OracleRecovery

oracle = OracleRecovery(task_id="dacomp-compose-001")
result = oracle.analyze(
    trajectory=capture.get_trajectory(),
    state_history=[],
    ground_truth={"output_key": expected_value},
)

print(f"Earliest unrecoverable step: {result.earliest_unrecoverable_step}")
print(f"Latest recoverable step:     {result.latest_recoverable_step}")
print(f"Recovery window:             {result.recovery_window_size} steps")
```

## Running Tests

```bash
pytest tests/unit/adaptive_intervention/ -v
```

60 tests covering all modules.

## Data Models

| Model | Description |
|---|---|
| `TrajectoryEvent` | Single captured event (tool call, result, reasoning, state write, intervention) |
| `AgentState` | Snapshot of agent workspace at a given step |
| `ExecutionOutcome` | Final result of a task execution including trajectory and score |
| `ForkPoint` | An irreversible step classified as recoverable or unrecoverable |
| `InterventionResult` | Outcome of a triggered intervention including corrective actions |

## Research Background

This framework was developed as part of graduate research at the University of Cincinnati investigating:

- **Irreversibility in agentic workflows**: How incorrect intermediate outputs propagate across downstream execution stages and become treated as trusted system state.
- **Oracle-recovery forking**: A methodology for systematically measuring where recovery from agent errors becomes impossible.
- **Prefix-only intervention**: Whether high-risk trajectories can be detected and corrected from partial execution histories alone, before irreversible state is committed.
- **Intervention timing**: How the placement of corrective interventions (early vs. mid vs. late) affects overall task recovery and benchmark score.

## License

MIT — see [LICENSE](../../LICENSE).
