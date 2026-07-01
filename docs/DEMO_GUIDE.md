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

Start the local website runtime from a separate terminal:

```powershell
& '.\.venv\Scripts\python.exe' -m office_agent.service_runtime --port 8765
```

Open:

```text
http://127.0.0.1:8765/login
```

Demo login accounts:

```text
it.demo / demo123
hr.payroll / demo123
```

After login, the dashboard provides:

```text
Agent query entry
scenario catalog
curated demo run
trace panel
evidence panel
raw JSON summary
```

The dashboard sends natural-language requests into the existing LangGraph. The
logged-in account controls the demo operator identity; the browser does not need
to expose an editable `employee_id` field.

## Demo Operators

The local mock runtime includes deterministic test employee profiles:

```text
login: it.demo / demo123
employee_id: EMP-IT-DEV-0001
department: IT Department
position: Software Developer
roles: employee, it_staff, developer
salary_query: denied

login: hr.payroll / demo123
employee_id: EMP-HR-PAY-0001
department: HR Department
position: Payroll Specialist
roles: employee, hr_staff, payroll_reader
salary_query: allowed
```

These login accounts are local demo seeds. They are not production enterprise
accounts. A logged-in identity still does not bypass permission or audit gates.

## Browser Walkthrough

1. Open `/login`.
2. Sign in as `it.demo / demo123`.
3. Ask `salary query request` or `查一下我的工资`.
4. Confirm the trace shows the permission/audit path and no salary preview is
   disclosed.
5. Log out and sign in as `hr.payroll / demo123`.
6. Ask the same salary question.
7. Confirm the salary path is allowed only for the payroll-reader identity.
8. Run a supported scenario such as `S08` from the scenario list.

## Endpoint Examples

Health remains public:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/health
```

Login and reuse the session cookie:

```powershell
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/auth/login `
  -Method Post `
  -WebSession $session `
  -ContentType 'application/json' `
  -Body '{"username":"it.demo","password":"demo123"}'
```

Ask the Agent entry with the logged-in identity:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/agent/query `
  -Method Post `
  -WebSession $session `
  -ContentType 'application/json; charset=utf-8' `
  -Body '{"message":"salary query request"}'
```

Scenario catalog:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/scenarios `
  -WebSession $session
```

Run one scenario:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/scenario `
  -Method Post `
  -WebSession $session `
  -ContentType 'application/json' `
  -Body '{"scenario_id":"S08"}'
```

Text report:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8765/demo/report `
  -WebSession $session
```

## S15 Boundary

`GET /demo` includes both S15 start and S15 resume so the human-in-the-loop
checkpoint flow is visible.

`POST /scenario` with `S15` returns the waiting/start state only. It does not
add a separate ad-hoc resume API.

S15 remains frozen as the portfolio golden path; this iteration only changed the
browser entry and local demo checkpoint storage reliability.
