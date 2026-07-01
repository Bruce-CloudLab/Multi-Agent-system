# Testing

## Full Test Suite

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests -q
```

Historical full-suite baseline before the authenticated demo entry iteration:

```text
73 passed
```

Current full-suite note:

```text
In the current Windows sandbox, full-suite collection reaches tests that use
pytest tmp_path, then fails during temp-directory setup with access denied under
the sandbox-managed temp path. This is an environment permission failure, not a
known assertion failure in the authenticated demo entry code.
```

## Current Focused Verification

For the authenticated local service entry, run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\test_local_service_runtime.py -q -p no:cacheprovider
```

Current result:

```text
23 passed
```

## Test Areas

- LangGraph skeleton routes.
- Permission and audit paths.
- Clarification and resume behavior.
- File processing workflow.
- Project inquiry checkpoint/interrupt/resume.
- Persistent checkpoint/thread resume.
- Native checkpoint resume evaluation.
- Concurrent state/trace/evidence isolation.
- RAG evaluation boundary.
- Local service runtime.
- Authenticated demo login and session handling.
- Demo static UI assets.
- Demo harness and UI readability.
- Scenario catalog and browser simulation console.
- Test employee seed identity profile.
- Agent query browser/runtime entry.
- Salary permission policy: resolved identity is not enough for payroll
  disclosure.

## What The Tests Protect

The tests verify:

- request type classification and route selection.
- high-risk requests pass through permission/audit before sensitive execution.
- factual output is backed by Tool/API/RAG evidence refs.
- RAG evaluation refs are not business evidence.
- checkpoint trace is not business evidence.
- concurrent requests do not cross-contaminate request ids, trace ids,
  operators, domain ids, evidence refs, or final responses.
- S15 resume validation rejects mismatched or stale owner reply events.
- local service endpoints keep the runtime adapter boundary.
- unauthenticated users are redirected from browser pages or rejected from JSON
  endpoints.
- successful demo login sets `office_agent_session`.
- logout clears the session cookie.
- the static oil-painting asset is served from package data.
- `/agent/query` binds `operator.employee_id` from the logged-in session and
  ignores client-supplied employee id overrides.
- the test employee id `EMP-IT-DEV-0001` resolves to IT Department /
  Software Developer without entering business `evidence_refs`.
- the default IT developer demo login is denied for salary preview and does not
  produce `HR-SALARY-PREVIEW-0001`.
- the payroll-reader demo login `EMP-HR-PAY-0001` can exercise the allowed salary
  path after permission and audit pass.
- `POST /agent/query` routes natural-language salary and policy requests through
  the existing LangGraph and preserves trace/evidence boundaries.
