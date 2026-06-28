# Enterprise Office Multi-Agent System

A LangGraph-based enterprise office Multi-Agent workflow system.

The project models an office assistant that can route requests across HR,
administration, IT, knowledge/RAG, project inquiry, task, notification, file
processing, permission/audit, and trace review responsibilities. It uses mock
Tool/API/RAG data so the control flow can be run and tested locally without
private enterprise systems.

## Capabilities

- Orchestrator routing for enterprise office requests.
- Low-risk direct tool/API workflows.
- Medium/high-risk identity, permission, and audit gates.
- RAG policy retrieval with a lightweight quality gate.
- File upload processing, classification, business update, task creation,
  notification, and RAG-ingestion decision.
- Human-in-the-loop project inquiry with checkpoint, interrupt, resume, and
  replay protection.
- Trace and evidence separation for debuggable execution.
- Concurrent isolation tests for state, trace, evidence, operator, and request
  boundaries.
- Local HTTP runtime with a browser Agent input and scenario simulation
  console.

## Architecture

The runtime is organized around LangGraph concepts:

| Concept | Project Mapping |
| --- | --- |
| State | `OfficeAgentState` carries request, risk, identity, permission, domain context, trace, evidence, and final response fields. |
| Node | Each node handles one execution step, such as orchestrator routing, permission/audit, RAG retrieval, file processing, task creation, or final response. |
| Edge | Graph edges describe the route from one node to the next. |
| Conditional Edge | Branches handle risk level, permission result, RAG quality, file classification, notification failure, and resume validation. |
| Checkpoint | S15 project inquiry can persist waiting state by `thread_id`. |
| Interrupt | Project inquiry waits at `waiting_for=project_owner_reply`. |
| Resume | Owner reply events resume the saved inquiry state after validation. |
| Trace | Trace events record execution flow and recovery-control metadata. |
| Evidence | Only Tool/API/RAG evidence refs support factual conclusions. |

More detail:

- [Architecture](docs/ARCHITECTURE.md)
- [Demo Guide](docs/DEMO_GUIDE.md)
- [Testing](docs/TESTING.md)
- [Trace And Evidence](docs/TRACE_AND_EVIDENCE.md)

## Quick Start

Python 3.12 is recommended.

```powershell
python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -e .
& '.\.venv\Scripts\python.exe' -m pip install pytest
```

Run the full test suite:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests -q
```

Current verified baseline:

```text
70 passed
```

## Run The Demo Harness

Run the command-line demo harness:

```powershell
& '.\.venv\Scripts\python.exe' -m office_agent.demo_harness
```

It executes a curated set of implemented workflows:

```text
S01 repair
S08 policy_query
S05 reception_schedule
S14 reception_plan_upload
S15 project_inquiry start
S15 project_inquiry resume
```

The report prints compact State, Node Path, Edge, Conditional Edge, Checkpoint,
Interrupt, Resume, Trace, Evidence, and display-response summaries.

## Run The Local Service

Start the local HTTP runtime:

```powershell
& '.\.venv\Scripts\python.exe' -m office_agent.service_runtime --port 8765
```

Open:

```text
http://127.0.0.1:8765/
```

The root page includes a browser Agent input backed by the existing LangGraph.
It also shows all S01-S15 designed scenarios, marks which ones are currently
runnable, and lets runnable scenarios execute through the local mock runtime.

Implemented endpoints:

```text
GET  /
GET  /demo/ui
GET  /health
GET  /scenarios
GET  /demo
GET  /demo/report
POST /agent/query
POST /scenario
```

`POST /agent/query` accepts:

```json
{"message": "查一下我的工资", "employee_id": "EMP-IT-DEV-0001"}
```

`POST /scenario` accepts:

```json
{"scenario_id": "S08"}
```

Designed-but-not-connected scenario IDs are visible in `GET /scenarios`, but
they still return `unsupported_scenario_id` if submitted to `POST /scenario`.

## Evidence Boundary

The system separates execution trace from factual evidence:

- `evidence_refs` are business evidence.
- RAG evaluation refs are quality metadata, not business evidence.
- checkpoint events are recovery-control trace, not business evidence.
- display text is presentation text, not business evidence.

If evidence is missing, the workflow must ask for clarification, route to manual
review, reject, or escalate instead of inventing enterprise facts.

## Current Limitations

- Tool/API/RAG integrations are deterministic local mocks.
- The local HTTP runtime is a demo adapter, not a production deployment layer.
- Authentication, real enterprise directories, real document stores, and
  production observability backends are outside the current local runtime.
- The static browser console is intentionally dependency-light and does not use
  a frontend build system.
