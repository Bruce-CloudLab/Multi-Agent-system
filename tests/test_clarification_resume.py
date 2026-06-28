from office_agent.graph import build_graph


def evidence_refs(state):
    return {item["evidence_ref"] for item in state.get("evidence_refs", [])}


def trace_nodes(state):
    return [event["node"] for event in state.get("trace_events", [])]


def assert_node_before(state, before, after):
    nodes = trace_nodes(state)
    assert before in nodes
    assert after in nodes
    assert nodes.index(before) < nodes.index(after)


def test_s04_missing_identity_asks_then_completes_after_identity_is_provided():
    app = build_graph()

    first_state = app.invoke(
        {
            "scenario_id": "S04",
            "user_input": "leave cancellation request",
            "operator": {"name": "Zhang San"},
        }
    )

    assert first_state["request_type"] == "leave_cancellation"
    assert first_state["blocked_reason"] == "missing_employee_identity"
    assert "resolve_identity_node" in trace_nodes(first_state)
    assert "ask_clarification_node" in trace_nodes(first_state)
    assert "HR-LEAVE-RECORD-0001" not in evidence_refs(first_state)
    assert "TASK-LIST-RESULT-0001" not in evidence_refs(first_state)
    assert "HR-LEAVE-CANCEL-SUBMIT-0001" not in evidence_refs(first_state)

    second_state = app.invoke(
        {
            "scenario_id": "S04",
            "user_input": "leave cancellation request",
            "operator": {"employee_id": "EMP-1001", "name": "Zhang San"},
        }
    )

    refs = evidence_refs(second_state)
    assert second_state["request_type"] == "leave_cancellation"
    assert second_state["identity_check"]["status"] == "resolved"
    assert second_state["blocked_reason"] == ""
    assert "HR-LEAVE-RECORD-0001" in refs
    assert "TASK-LIST-RESULT-0001" in refs
    assert "HR-LEAVE-CANCEL-SUBMIT-0001" in refs
    assert_node_before(second_state, "resolve_identity_node", "leave_record_node")


def test_s02_missing_identity_asks_then_completes_permission_path_after_identity_is_provided():
    app = build_graph()

    first_state = app.invoke(
        {
            "scenario_id": "S02",
            "user_input": "salary query request",
            "operator": {"name": "Zhang San"},
        }
    )

    assert first_state["request_type"] == "salary_query"
    assert first_state["blocked_reason"] == "missing_employee_identity"
    assert "resolve_identity_node" in trace_nodes(first_state)
    assert "ask_clarification_node" in trace_nodes(first_state)
    assert "permission_audit_node" not in trace_nodes(first_state)
    assert "PERMISSION-CHECK-SALARY-0001" not in evidence_refs(first_state)
    assert "HR-SALARY-PREVIEW-0001" not in evidence_refs(first_state)

    second_state = app.invoke(
        {
            "scenario_id": "S02",
            "user_input": "salary query request",
            "operator": {"employee_id": "EMP-HR-PAY-0001", "name": "Test Payroll Reader"},
        }
    )

    refs = evidence_refs(second_state)
    assert second_state["request_type"] == "salary_query"
    assert second_state["identity_check"]["status"] == "resolved"
    assert second_state["blocked_reason"] == ""
    assert "PERMISSION-CHECK-SALARY-0001" in refs
    assert "AUDIT-LOG-SALARY-0001" in refs
    assert "HR-SALARY-PREVIEW-0001" in refs
    assert_node_before(second_state, "business_router_node", "permission_audit_node")
    assert_node_before(second_state, "permission_audit_node", "payroll_query_node")
