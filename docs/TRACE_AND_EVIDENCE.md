# Trace And Evidence

## Core Rule

Trace explains what happened.

Evidence supports factual conclusions.

These two concepts are intentionally separate.

## Trace

Trace data includes:

```text
trace_events
trace_nodes
trace_event_count
gate_checks
checkpoint events
runtime route summaries
```

Trace is useful for debugging and auditing the executed path, but it is not by
itself proof of an enterprise fact.

## Evidence

Business evidence is stored in:

```text
evidence_refs
```

Examples:

```text
RAG-POLICY-RESULT-0001
PERMISSION-CHECK-RECEPTION-0001
PERMISSION-CHECK-SALARY-DENIED-0001
ADMIN-RECEPTION-SCHEDULE-0001
PROJECT-INQUIRY-REPLY-0001
TASK-RESULT-COMPLETE-INQUIRY-0001
```

Final factual conclusions must be backed by these evidence refs.

## Not Business Evidence

The following are not business evidence:

```text
display_response
display_response_zh
raw JSON panels
UI status text
RAG-EVAL-POLICY-0001
checkpoint_store events
native checkpoint metadata
```

They may explain quality, routing, presentation, or recovery behavior, but they
do not support factual business claims.

## Salary Permission Boundary

For salary requests, permission/audit evidence is not salary evidence.

Denied salary path:

```text
PERMISSION-CHECK-SALARY-DENIED-0001
AUDIT-LOG-SALARY-0001
no HR-SALARY-PREVIEW-0001
```

Allowed salary path:

```text
PERMISSION-CHECK-SALARY-0001
AUDIT-LOG-SALARY-0001
HR-SALARY-PREVIEW-0001
```

The salary amount may be displayed only in the allowed path where the payroll
tool actually ran.

## Failure Policy

If required evidence is missing, the graph should:

```text
ask for clarification
route to manual review
reject the request
escalate according to risk policy
```

It must not invent enterprise facts.
