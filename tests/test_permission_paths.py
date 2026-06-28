from office_agent.graph import run_scenario


def evidence_refs(state):
    return {item["evidence_ref"] for item in state["evidence_refs"]}


def trace_nodes(state):
    return [event["node"] for event in state["trace_events"]]


def assert_node_before(state, before, after):
    nodes = trace_nodes(state)
    assert before in nodes
    assert after in nodes
    assert nodes.index(before) < nodes.index(after)


def test_s02_salary_query_requires_permission_and_audit_before_payroll():
    state = run_scenario("S02")
    refs = evidence_refs(state)

    assert state["request_type"] == "salary_query"
    assert state["risk_precheck"]["level"] == "high"
    assert state["permission_context"]["permission_status"] == "allowed"
    assert state["audit_context"]["audit_status"] == "created"
    assert "PERMISSION-CHECK-SALARY-0001" in refs
    assert "AUDIT-LOG-SALARY-0001" in refs
    assert "HR-SALARY-PREVIEW-0001" in refs
    assert_node_before(state, "business_router_node", "permission_audit_node")
    assert_node_before(state, "permission_audit_node", "payroll_query_node")
    assert "已完成权限校验和审计记录" in state["final_response"]
    assert "2026-07" in state["final_response"]


def test_s05_reception_schedule_requires_permission_and_audit_before_schedule():
    state = run_scenario("S05")
    refs = evidence_refs(state)

    assert state["request_type"] == "reception_schedule"
    assert state["risk_precheck"]["level"] == "high"
    assert state["permission_context"]["permission_status"] == "allowed"
    assert state["audit_context"]["audit_status"] == "created"
    assert "PERMISSION-CHECK-RECEPTION-0001" in refs
    assert "AUDIT-LOG-RECEPTION-0001" in refs
    assert "ADMIN-RECEPTION-SCHEDULE-0001" in refs
    assert_node_before(state, "business_router_node", "permission_audit_node")
    assert_node_before(state, "permission_audit_node", "reception_schedule_node")
    assert "已完成权限校验和审计记录" in state["final_response"]
    assert "客户 A 重要接待" in state["final_response"]
