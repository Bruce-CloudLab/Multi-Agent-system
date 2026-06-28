from office_agent.concurrency import run_concurrent_requests


def evidence_refs(state):
    return {item["evidence_ref"] for item in state.get("evidence_refs", [])}


def trace_nodes(state):
    return [event["node"] for event in state.get("trace_events", [])]


def assert_node_before(state, before, after):
    nodes = trace_nodes(state)
    assert before in nodes
    assert after in nodes
    assert nodes.index(before) < nodes.index(after)


def high_risk_requests():
    return [
        {
            "scenario_id": "S02",
            "user_input": "salary query request",
            "operator": {"employee_id": "EMP-HR-3001", "name": "Salary User A"},
        },
        {
            "scenario_id": "S05",
            "user_input": "important reception schedule query",
            "operator": {
                "employee_id": "EMP-HR-3002",
                "name": "Reception Viewer A",
                "roles": ["leader", "reception_viewer"],
            },
            "business_object": {"reception_id": "RECEPTION-20260627-AM"},
        },
        {
            "scenario_id": "S14",
            "user_input": "upload important reception itinerary and action plan",
            "operator": {
                "employee_id": "EMP-HR-3003",
                "name": "Reception Admin A",
                "roles": ["leader", "reception_admin"],
            },
            "business_object": {
                "reception_id": "RECEPTION-20260627-AM",
                "file_name": "reception-plan-client-a-1.pdf",
            },
        },
        {
            "scenario_id": "S02",
            "user_input": "salary query request",
            "operator": {"employee_id": "EMP-HR-3004", "name": "Salary User B"},
        },
        {
            "scenario_id": "S05",
            "user_input": "important reception schedule query",
            "operator": {
                "employee_id": "EMP-HR-3005",
                "name": "Reception Viewer B",
                "roles": ["leader", "reception_viewer"],
            },
            "business_object": {"reception_id": "RECEPTION-20260627-AM"},
        },
        {
            "scenario_id": "S14",
            "user_input": "upload important reception itinerary and action plan",
            "operator": {
                "employee_id": "EMP-HR-3006",
                "name": "Reception Admin B",
                "roles": ["leader", "reception_admin"],
            },
            "business_object": {
                "reception_id": "RECEPTION-20260627-AM",
                "file_name": "reception-plan-client-a-2.pdf",
            },
        },
        {
            "scenario_id": "S02",
            "user_input": "salary query request",
            "operator": {"employee_id": "EMP-HR-3007", "name": "Salary User C"},
        },
        {
            "scenario_id": "S05",
            "user_input": "important reception schedule query",
            "operator": {
                "employee_id": "EMP-HR-3008",
                "name": "Reception Viewer C",
                "roles": ["leader", "reception_viewer"],
            },
            "business_object": {"reception_id": "RECEPTION-20260627-AM"},
        },
        {
            "scenario_id": "S14",
            "user_input": "upload important reception itinerary and action plan",
            "operator": {
                "employee_id": "EMP-HR-3009",
                "name": "Reception Admin C",
                "roles": ["leader", "reception_admin"],
            },
            "business_object": {
                "reception_id": "RECEPTION-20260627-AM",
                "file_name": "reception-plan-client-a-3.pdf",
            },
        },
    ]


def expected_refs_for(request_type):
    return {
        "salary_query": {
            "PERMISSION-CHECK-SALARY-0001",
            "AUDIT-LOG-SALARY-0001",
            "HR-SALARY-PREVIEW-0001",
        },
        "reception_schedule": {
            "PERMISSION-CHECK-RECEPTION-0001",
            "AUDIT-LOG-RECEPTION-0001",
            "ADMIN-RECEPTION-SCHEDULE-0001",
        },
        "reception_plan_upload": {
            "PERMISSION-CHECK-RECEPTION-UPLOAD-0001",
            "AUDIT-LOG-RECEPTION-UPLOAD-0001",
            "FILE-UPLOAD-SESSION-0001",
            "FILE-SCAN-RESULT-0001",
            "FILE-CLASSIFY-RECEPTION-0001",
            "FILE-ACTION-ITEMS-0001",
            "ADMIN-RECEPTION-UPDATE-0001",
            "TASK-RESULT-CREATE-BATCH-0001",
            "NOTIFY-RESULT-RECEPTION-TASKS-0001",
            "RAG-INGESTION-DECISION-0001",
        },
    }[request_type]


def test_high_risk_concurrent_requests_all_complete():
    requests = high_risk_requests()
    results = run_concurrent_requests(requests, max_workers=6)

    assert len(results) == len(requests)
    assert [result["status"] for result in results] == ["success"] * len(requests)
    assert all(result["state"] is not None for result in results)
    assert all(result["error"] is None for result in results)


def test_high_risk_concurrent_results_keep_request_trace_and_operator_isolated():
    requests = high_risk_requests()
    results = run_concurrent_requests(requests, max_workers=6)
    states = [result["state"] for result in results]

    request_ids = {state["request_id"] for state in states}
    trace_ids = {state["trace_id"] for state in states}

    assert len(request_ids) == len(requests)
    assert len(trace_ids) == len(requests)

    for request, state in zip(requests, states):
        assert state["scenario_id"] == request["scenario_id"]
        assert state["operator"]["employee_id"] == request["operator"]["employee_id"]
        assert state["trace_events"]
        assert state["final_response"]

        if request["scenario_id"] == "S14":
            assert (
                state["domain_context"]["file_processing"]["upload"]["file_name"]
                == request["business_object"]["file_name"]
            )


def test_high_risk_concurrent_requests_do_not_mix_evidence_or_responses():
    results = run_concurrent_requests(high_risk_requests(), max_workers=6)

    for result in results:
        state = result["state"]
        refs = evidence_refs(state)

        assert refs == expected_refs_for(state["request_type"])

        if state["request_type"] == "salary_query":
            assert "2026-07" in state["final_response"]
            assert "TASK-BATCH-RECEPTION-0001" not in state["final_response"]
            assert "skipped_by_policy" not in state["final_response"]

        if state["request_type"] == "reception_schedule":
            assert "RECEPTION-20260627-AM" in str(state["domain_context"]["reception_schedule"])
            assert "HR-SALARY-PREVIEW-0001" not in refs
            assert "TASK-BATCH-RECEPTION-0001" not in state["final_response"]

        if state["request_type"] == "reception_plan_upload":
            assert "TASK-BATCH-RECEPTION-0001" in state["final_response"]
            assert "skipped_by_policy" in state["final_response"]
            assert "HR-SALARY-PREVIEW-0001" not in refs
            assert "ADMIN-RECEPTION-SCHEDULE-0001" not in refs


def test_high_risk_concurrent_requests_preserve_required_node_order():
    results = run_concurrent_requests(high_risk_requests(), max_workers=6)

    for result in results:
        state = result["state"]

        assert_node_before(state, "business_router_node", "permission_audit_node")

        if state["request_type"] == "salary_query":
            assert_node_before(state, "permission_audit_node", "payroll_query_node")

        if state["request_type"] == "reception_schedule":
            assert_node_before(state, "permission_audit_node", "reception_schedule_node")

        if state["request_type"] == "reception_plan_upload":
            assert_node_before(state, "permission_audit_node", "file_processing_node")
            assert_node_before(state, "file_processing_node", "reception_update_node")
            assert_node_before(
                state,
                "reception_update_node",
                "create_action_item_tasks_node",
            )
            assert_node_before(
                state,
                "create_action_item_tasks_node",
                "notification_node",
            )
            assert_node_before(
                state,
                "notification_node",
                "rag_ingestion_decision_node",
            )
