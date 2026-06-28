from office_agent.graph import build_graph
from office_agent.mock_tools import TEST_EMPLOYEE_ID, get_employee_profile


def evidence_refs(state):
    return {item["evidence_ref"] for item in state.get("evidence_refs", [])}


def trace_nodes(state):
    return [event["node"] for event in state.get("trace_events", [])]


def test_it_developer_test_employee_profile_is_available():
    result = get_employee_profile(TEST_EMPLOYEE_ID)
    profile = result["data"]

    assert result["status"] == "success"
    assert result["evidence_ref"] == "EMPLOYEE-PROFILE-IT-DEV-0001"
    assert profile["employee_id"] == "EMP-IT-DEV-0001"
    assert profile["display_name"] == "Test IT Developer"
    assert profile["department"] == "IT Department"
    assert profile["position"] == "Software Developer"
    assert profile["job_family"] == "Engineering"
    assert profile["employment_status"] == "active"
    assert {"employee", "it_staff", "developer"}.issubset(set(profile["roles"]))


def test_it_developer_test_employee_resolves_identity_without_bypassing_salary_permission():
    app = build_graph()

    state = app.invoke(
        {
            "scenario_id": "S02",
            "user_input": "salary query request",
            "operator": {
                "employee_id": TEST_EMPLOYEE_ID,
                "name": "Test IT Developer",
            },
        }
    )

    assert state["request_type"] == "salary_query"
    assert state["identity_check"]["status"] == "resolved"
    assert state["identity_check"]["employee_id"] == TEST_EMPLOYEE_ID
    assert state["identity_check"]["department"] == "IT Department"
    assert state["identity_check"]["position"] == "Software Developer"
    assert "developer" in state["identity_check"]["roles"]
    assert state["identity_check"]["profile_evidence_ref"] == "EMPLOYEE-PROFILE-IT-DEV-0001"
    assert state["domain_context"]["employee_profile"]["employee_id"] == TEST_EMPLOYEE_ID

    assert state["permission_context"]["employee_id"] == TEST_EMPLOYEE_ID
    assert state["permission_context"]["permission_status"] == "denied"
    assert state["blocked_reason"] == "permission_denied"
    assert "PERMISSION-CHECK-SALARY-DENIED-0001" in evidence_refs(state)
    assert "AUDIT-LOG-SALARY-0001" in evidence_refs(state)
    assert "HR-SALARY-PREVIEW-0001" not in evidence_refs(state)
    assert "EMPLOYEE-PROFILE-IT-DEV-0001" not in evidence_refs(state)
    assert "payroll_query_node" not in trace_nodes(state)
    assert "manual_review_node" in trace_nodes(state)
