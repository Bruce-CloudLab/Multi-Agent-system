from office_agent.concurrency import (
    run_concurrent_project_inquiry_resumes,
    run_concurrent_requests,
)


INITIAL_REFS = {
    "PERMISSION-CHECK-PROJECT-INQUIRY-0001",
    "AUDIT-LOG-PROJECT-INQUIRY-0001",
    "PROJECT-ACCESS-SCOPE-0001",
    "PROJECT-OWNER-0001",
    "PROJECT-INQUIRY-RESULT-0001",
    "TASK-RESULT-CREATE-INQUIRY-0001",
    "NOTIFY-RESULT-PROJECT-INQUIRY-0001",
}

RESUME_ONLY_REFS = {
    "PROJECT-INQUIRY-REPLY-0001",
    "TASK-RESULT-COMPLETE-INQUIRY-0001",
    "PROJECT-RAG-INGESTION-DECISION-0001",
}


def evidence_refs(state):
    return {item["evidence_ref"] for item in state.get("evidence_refs", [])}


def trace_nodes(state):
    return [event["node"] for event in state.get("trace_events", [])]


def inquiry_id(state):
    return state["domain_context"]["project_inquiry"]["inquiry_id"]


def owner_task_id(state):
    return state["domain_context"]["project_inquiry_task"]["task_id"]


def s15_requests():
    return [
        {
            "scenario_id": "S15",
            "user_input": "project inquiry for customer A",
            "operator": {"employee_id": "EMP-S15-4001", "name": "Project Member A"},
            "business_object": {
                "project_id": "PROJ-CUST-A",
                "question": "客户 A 交付材料是否还需要补充附件？",
                "question_type": "customer_delivery",
            },
        },
        {
            "scenario_id": "S15",
            "user_input": "project inquiry for customer B",
            "operator": {"employee_id": "EMP-S15-4002", "name": "Project Member B"},
            "business_object": {
                "project_id": "PROJ-CUST-B",
                "question": "客户 B 上线节点是否需要延期？",
                "question_type": "major_milestone",
            },
        },
        {
            "scenario_id": "S15",
            "user_input": "project inquiry for customer C",
            "operator": {"employee_id": "EMP-S15-4003", "name": "Project Member C"},
            "business_object": {
                "project_id": "PROJ-CUST-C",
                "question": "客户 C 反馈是否由交付组处理？",
                "question_type": "customer_feedback",
            },
        },
        {
            "scenario_id": "S15",
            "user_input": "project inquiry for customer D",
            "operator": {"employee_id": "EMP-S15-4004", "name": "Project Member D"},
            "business_object": {
                "project_id": "PROJ-CUST-D",
                "question": "客户 D 验收材料是否已经确认？",
                "question_type": "acceptance_material",
            },
        },
    ]


def test_concurrent_s15_requests_create_isolated_waiting_states():
    requests = s15_requests()
    results = run_concurrent_requests(requests, max_workers=4)
    states = [result["state"] for result in results]

    assert [result["status"] for result in results] == ["success"] * len(requests)
    assert all(result["error"] is None for result in results)
    assert len({state["request_id"] for state in states}) == len(states)
    assert len({state["trace_id"] for state in states}) == len(states)
    assert len({inquiry_id(state) for state in states}) == len(states)
    assert len({owner_task_id(state) for state in states}) == len(states)

    for request, state in zip(requests, states):
        assert state["request_type"] == "project_inquiry"
        assert state["waiting_for"] == "project_owner_reply"
        assert state["operator"]["employee_id"] == request["operator"]["employee_id"]
        assert (
            state["domain_context"]["project_access"]["project_id"]
            == request["business_object"]["project_id"]
        )
        assert state["interrupt_context"]["inquiry_id"] == inquiry_id(state)
        assert state["interrupt_context"]["owner_task_id"] == owner_task_id(state)

        refs = evidence_refs(state)
        assert refs == INITIAL_REFS
        assert refs.isdisjoint(RESUME_ONLY_REFS)
        assert "wait_for_owner_reply_node" in trace_nodes(state)
        assert "inquiry_add_reply_node" not in trace_nodes(state)
        assert "waiting_for_owner_reply" in state["final_response"]
        assert "owner_reply_recorded" not in state["final_response"]
        assert "owner_task_completed" not in state["final_response"]


def test_concurrent_s15_resumes_preserve_each_waiting_context():
    requests = s15_requests()
    waiting_results = run_concurrent_requests(requests, max_workers=4)
    waiting_states = [result["state"] for result in waiting_results]
    owner_reply_events = [
        {
            "inquiry_id": inquiry_id(state),
            "responder_id": state["domain_context"]["project_owner"]["owner_id"],
            "reply_summary": f"reply-marker-{index}",
            "reply_sensitivity_level": "confidential",
        }
        for index, state in enumerate(waiting_states, start=1)
    ]

    resume_results = run_concurrent_project_inquiry_resumes(
        waiting_states,
        owner_reply_events,
        max_workers=4,
    )
    resumed_states = [result["state"] for result in resume_results]
    all_task_ids = {owner_task_id(state) for state in resumed_states}

    assert [result["status"] for result in resume_results] == ["success"] * len(requests)
    assert all(result["error"] is None for result in resume_results)

    for waiting_state, reply_event, resumed_state in zip(
        waiting_states,
        owner_reply_events,
        resumed_states,
    ):
        assert resumed_state["request_id"] == waiting_state["request_id"]
        assert resumed_state["trace_id"] == waiting_state["trace_id"]
        assert resumed_state["waiting_for"] is None
        assert inquiry_id(resumed_state) == inquiry_id(waiting_state)
        assert owner_task_id(resumed_state) == owner_task_id(waiting_state)
        assert (
            resumed_state["domain_context"]["project_access"]["project_id"]
            == waiting_state["domain_context"]["project_access"]["project_id"]
        )
        assert (
            resumed_state["domain_context"]["project_inquiry"]["reply_summary"]
            == reply_event["reply_summary"]
        )

        refs = evidence_refs(resumed_state)
        assert refs == INITIAL_REFS | RESUME_ONLY_REFS
        assert "inquiry_add_reply_node" in trace_nodes(resumed_state)
        assert "complete_owner_task_node" in trace_nodes(resumed_state)
        assert "project_rag_ingestion_decision_node" in trace_nodes(resumed_state)
        assert owner_task_id(resumed_state) in resumed_state["final_response"]
        assert inquiry_id(resumed_state) in resumed_state["final_response"]

        leaked_task_ids = all_task_ids - {owner_task_id(resumed_state)}
        assert all(
            task_id not in resumed_state["final_response"]
            for task_id in leaked_task_ids
        )
