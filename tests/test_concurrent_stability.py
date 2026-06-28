from office_agent.concurrency import run_concurrent_requests


def evidence_refs(state):
    return {item["evidence_ref"] for item in state["evidence_refs"]}


def mixed_requests():
    return [
        {
            "scenario_id": "S01",
            "user_input": "工位上方的灯坏了，需要报修",
            "operator": {"employee_id": "EMP-2001", "name": "员工A"},
        },
        {
            "scenario_id": "S08",
            "user_input": "员工想查询差旅报销制度",
            "operator": {"employee_id": "EMP-2002", "name": "员工B"},
        },
        {
            "scenario_id": "S04",
            "user_input": "员工请假回来走销假流程",
            "operator": {"employee_id": "EMP-2003", "name": "员工C"},
        },
        {
            "scenario_id": "S08",
            "user_input": "下月出差前需要查一下差旅制度",
            "operator": {"employee_id": "EMP-2004", "name": "员工D"},
        },
        {
            "scenario_id": "S01",
            "user_input": "会议室旁边工位灯不亮，需要报修",
            "operator": {"employee_id": "EMP-2005", "name": "员工E"},
        },
        {
            "scenario_id": "S04",
            "user_input": "我休假结束了，帮我走销假流程",
            "operator": {"employee_id": "EMP-2006", "name": "员工F"},
        },
        {
            "scenario_id": "S01",
            "user_input": "工位上方灯坏了",
            "operator": {"employee_id": "EMP-2007", "name": "员工G"},
        },
        {
            "scenario_id": "S08",
            "user_input": "查询差旅报销制度",
            "operator": {"employee_id": "EMP-2008", "name": "员工H"},
        },
        {
            "scenario_id": "S04",
            "user_input": "请假回来需要销假",
            "operator": {"employee_id": "EMP-2009", "name": "员工I"},
        },
        {
            "scenario_id": "S08",
            "user_input": "差旅制度怎么要求上传材料",
            "operator": {"employee_id": "EMP-2010", "name": "员工J"},
        },
    ]


def expected_refs_for(request_type):
    return {
        "repair": {"ADMIN-REPAIR-RESULT-0001"},
        "policy_query": {"RAG-POLICY-RESULT-0001"},
        "leave_cancellation": {
            "HR-LEAVE-RECORD-0001",
            "TASK-LIST-RESULT-0001",
            "HR-LEAVE-CANCEL-SUBMIT-0001",
        },
    }[request_type]


def test_multiple_employees_send_mixed_requests_concurrently():
    requests = mixed_requests()
    results = run_concurrent_requests(requests, max_workers=5)

    assert len(results) == len(requests)
    assert [result["status"] for result in results] == ["success"] * len(requests)


def test_concurrent_results_keep_request_and_trace_isolated():
    requests = mixed_requests()
    results = run_concurrent_requests(requests, max_workers=5)
    states = [result["state"] for result in results]

    request_ids = {state["request_id"] for state in states}
    trace_ids = {state["trace_id"] for state in states}

    assert len(request_ids) == len(requests)
    assert len(trace_ids) == len(requests)

    for request, state in zip(requests, states):
        assert state["operator"]["employee_id"] == request["operator"]["employee_id"]
        assert state["scenario_id"] == request["scenario_id"]
        assert state["trace_events"]
        assert state["final_response"]


def test_concurrent_requests_do_not_mix_evidence_between_scenarios():
    results = run_concurrent_requests(mixed_requests(), max_workers=5)

    for result in results:
        state = result["state"]
        refs = evidence_refs(state)
        assert refs == expected_refs_for(state["request_type"])

        if state["request_type"] == "repair":
            assert "ADMIN-REPAIR-0001" in state["final_response"]
            assert "POLICY-TRAVEL-2026" not in state["final_response"]
            assert "LEAVE-CANCEL-0001" not in state["final_response"]

        if state["request_type"] == "policy_query":
            assert "POLICY-TRAVEL-2026" in state["final_response"]
            assert "ADMIN-REPAIR-0001" not in state["final_response"]
            assert "LEAVE-CANCEL-0001" not in state["final_response"]

        if state["request_type"] == "leave_cancellation":
            assert "LEAVE-CANCEL-0001" in state["final_response"]
            assert "POLICY-TRAVEL-2026" not in state["final_response"]
            assert "ADMIN-REPAIR-0001" not in state["final_response"]
