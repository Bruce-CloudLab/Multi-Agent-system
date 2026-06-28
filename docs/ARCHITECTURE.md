# Architecture

## Overview

Enterprise Office Multi-Agent System is a LangGraph workflow for routing and
executing enterprise office requests with explicit risk, permission, evidence,
and trace boundaries.

The graph uses mock Tool/API/RAG results so the orchestration design can be run
locally and verified by tests.

## Main Responsibilities

- Orchestrator Agent: intent recognition, risk pre-check, routing, result
  collection, and disclosure control.
- Permission/Audit Agent: identity-sensitive permission checks and audit logs.
- HR Agent: HR-oriented query and workflow paths.
- Admin Agent: repair, reception, and administration workflows.
- IT Agent: IT support request paths.
- Knowledge/RAG Agent: policy and document retrieval with quality checks.
- Project Agent: project access, owner lookup, and project inquiry workflows.
- Task/Workflow Agent: action item and owner task lifecycle.
- File Processing Agent: uploaded file scan, classification, and extraction.
- Trace Recorder/Review: execution trace capture and integrity checks.

## LangGraph Mapping

| LangGraph Concept | Implementation Shape |
| --- | --- |
| State | `src/office_agent/state.py` defines `OfficeAgentState`. |
| Node | `src/office_agent/nodes.py` contains deterministic node functions. |
| Edge | `src/office_agent/graph.py` wires node order and graph routes. |
| Conditional Edge | Route functions branch on request type, risk, permission, RAG quality, file status, and resume validation. |
| Checkpoint | `src/office_agent/checkpointing.py` provides JSON checkpoint storage for waiting project inquiries. |
| Interrupt | S15 stores `waiting_for=project_owner_reply` while owner reply is pending. |
| Resume | Resume helpers validate owner reply events before writing business evidence. |
| Trace | Nodes append trace events that expose the executed path. |
| Evidence | Tool/API/RAG mock results append evidence refs that support final factual conclusions. |

## Runtime Layers

```text
User request
-> LangGraph runtime
-> deterministic mock Tool/API/RAG calls
-> trace/evidence collection
-> final response
```

The local HTTP service in `src/office_agent/service_runtime.py` is an adapter
over the graph. It is not a business Agent and does not create business
evidence.

## Key Workflow Examples

- S01 repair: low-risk direct administration workflow.
- S08 policy query: RAG retrieval plus quality gate.
- S05 reception schedule: high-risk permission/audit before disclosure.
- S14 reception plan upload: file processing, business update, tasks,
  notification, and RAG decision.
- S15 project inquiry: project access, owner task, checkpoint, interrupt,
  owner reply resume, task completion, and RAG decision.
