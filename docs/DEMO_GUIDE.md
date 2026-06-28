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

The root route serves a static browser console. The console reads:

```text
GET /demo
POST /scenario
```

## Endpoint Examples

Health:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/health
```

Text report:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/demo/report
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
