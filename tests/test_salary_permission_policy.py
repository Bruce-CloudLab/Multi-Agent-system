from office_agent.graph import build_graph
from office_agent.mock_tools import PAYROLL_TEST_EMPLOYEE_ID, TEST_EMPLOYEE_ID


def evidence_refs(state):
    return {item["evidence_ref"] for item in state.get("evidence_refs", [])}


def trace_nodes(state):
    return [event["node"] for event in state.get("trace_events", [])]


def assert_node_before(state, before, after):
    nodes = trace_nodes(state)
    assert before in nodes
    assert after in nodes
    assert nodes.index(before) < nodes.index(after)


def test_it_developer_salary_query_is_denied_before_payroll():
    state = build_graph().invoke(
        {
            "scenario_id": "S02",
            "user_input": "salary query request",
            "operator": {
                "employee_id": TEST_EMPLOYEE_ID,
                "name": "Test IT Developer",
            },
        }
    )
    refs = evidence_refs(state)
    nodes = trace_nodes(state)

    assert state["request_type"] == "salary_query"
    assert state["identity_check"]["status"] == "resolved"
    assert state["permission_context"]["permission_status"] == "denied"
    assert state["permission_context"]["denial_reason"] == "operator_missing_payroll_reader_role"
    assert state["blocked_reason"] == "permission_denied"
    assert state["audit_context"]["audit_status"] == "created"
    assert "PERMISSION-CHECK-SALARY-DENIED-0001" in refs
    assert "AUDIT-LOG-SALARY-0001" in refs
    assert "HR-SALARY-PREVIEW-0001" not in refs
    assert "hr_api.get_salary_preview" not in state.get("tool_results", {})
    assert "payroll_query_node" not in nodes
    assert "manual_review_node" in nodes
    assert any(
        gate.get("gate") == "permission_audit" and gate.get("status") == "blocked"
        for gate in state.get("gate_checks", [])
    )
    assert_node_before(state, "permission_audit_node", "manual_review_node")
    assert "18000" not in state["final_response"]
    assert "14250" not in state["final_response"]


def test_payroll_reader_salary_query_reaches_payroll_after_permission():
    state = build_graph().invoke(
        {
            "scenario_id": "S02",
            "user_input": "salary query request",
            "operator": {
                "employee_id": PAYROLL_TEST_EMPLOYEE_ID,
                "name": "Test Payroll Reader",
            },
        }
    )
    refs = evidence_refs(state)

    assert state["request_type"] == "salary_query"
    assert state["identity_check"]["status"] == "resolved"
    assert state["permission_context"]["permission_status"] == "allowed"
    assert state["permission_context"]["matched_roles"] == ["payroll_reader"]
    assert state["audit_context"]["audit_status"] == "created"
    assert "PERMISSION-CHECK-SALARY-0001" in refs
    assert "AUDIT-LOG-SALARY-0001" in refs
    assert "HR-SALARY-PREVIEW-0001" in refs
    assert "hr_api.get_salary_preview" in state.get("tool_results", {})
    assert_node_before(state, "permission_audit_node", "payroll_query_node")
    assert "2026-07" in state["final_response"]
    assert "18000" in state["final_response"]
    assert "14250" in state["final_response"]
