# OpenHands Paper Reproduction Report

Date: 2026-06-03

Paper/source used:

- PDF: `C:\Users\mgnih\Downloads\LLM Research\4.pdf`
- Extracted text: `C:\Users\mgnih\Downloads\LLM Research\4.txt`
- Paper code link found in the PDF: `https://github.com/All-Hands-AI/OpenHands`
- Local fork clone: `C:\Users\mgnih\Projects\OpenHands`
- Git remote: `https://github.com/niharikamg/OpenHands.git`

## What The Paper Does

The OpenHands paper presents an agent platform where a language-model agent, especially `CodeActAgent`, receives natural-language software tasks, uses tools such as a terminal and file editor, runs inside a Docker sandbox, and is evaluated on benchmarks such as SWE-bench Lite, HumanEvalFix, WebArena, GPQA, GAIA, BIRD, ML-Bench, and BioCoder.

The full paper evaluation is not a small local run. It requires benchmark datasets, the separate OpenHands benchmark infrastructure, paid LLM access, and enough compute/API budget to run many tasks.

## What Was Reproduced Locally

The OpenHands repository was cloned from the user's fork and run locally with Docker Compose.

Verified local services:

- Docker engine: running, version `28.5.1`
- OpenHands app container: `openhands-app-`
- OpenHands web UI: `http://localhost:3000`
- Web UI health check: HTTP `200 OK`
- Agent sandbox container started: `oh-agent-server-17weBLQARKgHNeoGrpTFez`
- Agent server image: `ghcr.io/openhands/agent-server:1.19.1-python`
- Agent server exposed ports:
  - `8000 -> 51053`
  - `8001 -> 53977`
  - `8011 -> 59951`
  - `8012 -> 54513`

This reproduces the paper's core system setup: OpenHands app plus Docker sandbox runtime.

## Agent Task Attempt

A small paper-style task was submitted to OpenHands:

```text
Reproduce a small OpenHands-style software engineering task. In the sandbox workspace,
create a folder named paper_demo. Inside it, create demo.py with a function add(a, b)
that returns the sum, create test_demo.py with two pytest tests for add, run the tests,
and then create RESULT.md summarizing exactly what files you created and whether the
tests passed.
```

Conversation start task:

- Start task id: `c7eba100e6ca4a67b6122665e84f8d0f`
- Conversation id: `0c4c761a5e32414daefde97528f1f7a3`
- Sandbox id: `oh-agent-server-17weBLQARKgHNeoGrpTFez`
- Start status: `READY`

## Result

The sandbox and conversation were created successfully, but the agent did not complete the task because the configured LLM credential failed authentication.

Observed error:

```text
litellm.AuthenticationError: AuthenticationError: Litellm_proxyException -
LiteLLM Virtual Key expected. Received=Admi****@123, expected to start with 'sk-'.
```

Because the LLM call failed before the agent's first reasoning/action step, no `paper_demo` files were created in the mounted workspace.

## What Is Needed Next

To complete the actual CodeActAgent reproduction, configure OpenHands with a valid LLM API key for the selected provider.

Current saved agent settings use:

- Agent: `CodeActAgent`
- Model route: `litellm_proxy/claude-opus-4-5-20251101`
- Base URL: `https://llm-proxy.app.all-hands.dev/`

That LiteLLM proxy requires a valid LiteLLM virtual key beginning with `sk-`. Once a valid key is set in the OpenHands UI at `http://localhost:3000`, rerun the same task. After that, the expected successful reproduction evidence should be:

- `workspace/paper_demo/demo.py`
- `workspace/paper_demo/test_demo.py`
- `workspace/paper_demo/RESULT.md`
- A pytest output showing the tests passed

## Commands Used For The Local Reproduction

```powershell
cd C:\Users\mgnih\Projects\OpenHands
docker compose up -d --build
```

OpenHands URL:

```text
http://localhost:3000
```

Stop command:

```powershell
cd C:\Users\mgnih\Projects\OpenHands
docker compose down
```
