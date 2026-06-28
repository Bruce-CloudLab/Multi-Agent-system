# Demo Guide

## Command-Line Demo Harness

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m office_agent.demo_harness
```

The command runs:

```text
S01 repair
S08 policy_query
S05 reception_schedule
S14 reception_plan_upload
S15 project_inquiry start
S15 project_inquiry resume
```

The output is a compact execution report with:

```text
State
Node Path
Edge
Conditional Edge
Checkpoint
Interrupt
Resume
Trace
Evidence
Display response
```

## Local HTTP Runtime

Start:

```powershell
& '.\.venv\Scripts\python.exe' -m office_agent.service_runtime --port 8765
```

Open:

```text
http://127.0.0.1:8765/
```

The root route serves a static browser console with an Agent input. The console
reads:

```text
POST /agent/query
GET /scenarios
GET /demo
POST /scenario
```

The Agent input sends a natural-language message and employee id into the
existing LangGraph. The default local test id is `EMP-IT-DEV-0001`.

The scenario catalog shows all S01-S15 design scenarios. Runnable scenarios can
be executed from the page; not-connected scenarios are shown as disabled entries
so the runtime does not pretend to execute paths that are not wired into the
current graph.

## Test Operator

The local mock runtime includes one deterministic test employee profile:

```text
employee_id: EMP-IT-DEV-0001
department: IT Department
position: Software Developer
roles: employee, it_staff, developer
```

This id is seed data for local graph tests. It is not a login account or an
authentication token, and it does not bypass permission or audit gates.

## Endpoint Examples

Health:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/health
```

Text report:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/demo/report
```

Ask the Agent entry:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/agent/query `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"message":"查一下我的工资","employee_id":"EMP-IT-DEV-0001"}'
```

Scenario catalog:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/scenarios
```

Run one scenario:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/scenario `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"scenario_id":"S08"}'
```

## S15 Boundary

`GET /demo` includes both S15 start and S15 resume so the human-in-the-loop
checkpoint flow is visible.

`POST /scenario` with `S15` returns the waiting/start state only. It does not
add a separate ad-hoc resume API.
