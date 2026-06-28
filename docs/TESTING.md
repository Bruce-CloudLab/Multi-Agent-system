# Testing

## Full Test Suite

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests -q
```

Current verified baseline:

```text
66 passed
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
- Demo harness and UI readability.
- Scenario catalog and browser simulation console.
- Test employee seed identity profile.

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
- the scenario catalog shows all S01-S15 entries while unsupported paths remain
  non-executable through `POST /scenario`.
- the test employee id `EMP-IT-DEV-0001` resolves to IT Department /
  Software Developer without entering business `evidence_refs`.
