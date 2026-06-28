from office_agent.graph import route_after_rag_evaluation, run_scenario


def evidence_refs(state):
    return {item["evidence_ref"] for item in state["evidence_refs"]}


def test_s01_repair_path_creates_ticket_from_tool_evidence():
    state = run_scenario("S01")

    assert state["request_type"] == "repair"
    assert "ADMIN-REPAIR-RESULT-0001" in evidence_refs(state)
    assert state["domain_context"]["repair"]["ticket_id"] == "ADMIN-REPAIR-0001"
    assert "ADMIN-REPAIR-0001" in state["final_response"]
    assert state["trace_events"]


def test_s08_policy_query_uses_rag_evidence():
    state = run_scenario("S08")

    assert state["request_type"] == "policy_query"
    assert "RAG-POLICY-RESULT-0001" in evidence_refs(state)
    assert "RAG-EVAL-POLICY-0001" not in evidence_refs(state)
    assert state["domain_context"]["policy_query"]["source_doc"] == "POLICY-TRAVEL-2026"
    assert state["domain_context"]["rag_evaluation"]["gate_status"] == "passed"
    assert state["domain_context"]["rag_evaluation"]["source_evidence_ref"] == "RAG-POLICY-RESULT-0001"
    assert any(
        event["node"] == "rag_evaluation_node"
        and event["action"] == "rag_quality_evaluated"
        for event in state["trace_events"]
    )
    assert any(
        gate["gate"] == "rag_quality_gate"
        and gate["status"] == "passed"
        for gate in state["gate_checks"]
    )
    assert "POLICY-TRAVEL-2026" in state["final_response"]
    assert "rag_quality_gate=passed" in state["final_response"]
    assert state["trace_events"]


def test_s08_blocked_rag_evaluation_routes_to_manual_review():
    state = {
        "domain_context": {
            "rag_evaluation": {
                "gate_status": "blocked",
            }
        },
        "next_action": {
            "type": "manual_review",
            "target": "rag_quality_gate",
        },
    }

    assert route_after_rag_evaluation(state) == "manual_review_node"


def test_s04_leave_cancellation_queries_tasks_and_submits():
    state = run_scenario("S04")

    assert state["request_type"] == "leave_cancellation"
    refs = evidence_refs(state)
    assert "HR-LEAVE-RECORD-0001" in refs
    assert "TASK-LIST-RESULT-0001" in refs
    assert "HR-LEAVE-CANCEL-SUBMIT-0001" in refs
    assert state["domain_context"]["leave_cancellation"]["reviewer_role"] == "attendance_staff"
    assert "考勤人员审核" in state["final_response"]
    assert state["trace_events"]
