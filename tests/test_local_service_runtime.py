import json

from office_agent.service_runtime import dispatch_request


def payload(response):
    return json.loads(response.body)


def test_health_returns_ok():
    response = dispatch_request("GET", "/health")

    assert response.status == 200
    assert response.content_type == "application/json"
    assert payload(response)["status"] == "ok"
    assert payload(response)["runtime"] == "local-service-v1"


def test_scenarios_endpoint_returns_full_catalog():
    response = dispatch_request("GET", "/scenarios")
    data = payload(response)

    assert response.status == 200
    assert data["runtime"] == "local-service-v1"
    assert data["service"] == "enterprise-office-agent"
    assert data["total_count"] == 15
    assert data["runnable_count"] == 7
    assert [item["scenario_id"] for item in data["scenarios"]] == [
        f"S{i:02d}" for i in range(1, 16)
    ]

    s01 = data["scenarios"][0]
    assert s01["scenario_id"] == "S01"
    assert s01["title"] == "工位报修"
    assert s01["status"] == "runnable"
    assert s01["request_type"] == "repair"

    s03 = next(item for item in data["scenarios"] if item["scenario_id"] == "S03")
    assert s03["status"] == "not_connected"
    assert s03["run_hint"] == "已设计，当前本地运行台未接入执行"


def test_root_returns_system_simulation_console_with_all_scenarios():
    response = dispatch_request("GET", "/")

    assert response.status == 200
    assert response.content_type == "text/html; charset=utf-8"
    assert '<html lang="zh-CN">' in response.body
    assert "企业办公 Agent 本地运行台" in response.body
    assert "系统运行入口" in response.body
    assert "loadScenarioCatalog" in response.body
    assert "fetch('/scenarios')" in response.body
    assert "fetch('/demo')" in response.body
    assert "fetch('/scenario'" in response.body
    assert "display_response_zh || summary.display_response" in response.body
    assert "未接入运行" in response.body
    for scenario_id in [f"S{i:02d}" for i in range(1, 16)]:
        assert scenario_id in response.body
    for label in [
        "状态 State",
        "节点路径 Node Path",
        "条件边 Conditional Edge",
        "检查点 Checkpoint",
        "中断 Interrupt",
        "恢复 Resume",
        "轨迹 Trace",
        "证据 Evidence",
    ]:
        assert label in response.body


def test_demo_ui_route_returns_same_console():
    root = dispatch_request("GET", "/")
    response = dispatch_request("GET", "/demo/ui")

    assert response.status == 200
    assert response.content_type == "text/html; charset=utf-8"
    assert response.body == root.body


def test_demo_endpoint_returns_curated_cases():
    response = dispatch_request("GET", "/demo")
    data = payload(response)

    assert response.status == 200
    assert data["case_count"] == 6
    assert [case["case_id"] for case in data["cases"]] == [
        "S01",
        "S08",
        "S05",
        "S14",
        "S15-start",
        "S15-resume",
    ]
    assert "display_response" in data["cases"][0]
    assert "display_response_zh" in data["cases"][0]
    assert data["cases"][0]["display_locale"] == "zh-CN"
    assert "raw_final_response" in data["cases"][0]
    assert "Repair ticket ADMIN-REPAIR-0001 was created" in data["cases"][0]["display_response"]
    assert "已创建报修工单 ADMIN-REPAIR-0001" in data["cases"][0]["display_response_zh"]


def test_demo_report_endpoint_returns_teaching_text():
    response = dispatch_request("GET", "/demo/report")

    assert response.status == 200
    assert response.content_type == "text/plain; charset=utf-8"
    assert "状态 State:" in response.body
    assert "轨迹 Trace:" in response.body
    assert "证据 Evidence:" in response.body
    assert "中文展示:" in response.body
    assert "Display Response:" in response.body
    assert "差旅报销政策" in response.body
    assert "浼佷笟" not in response.body


def test_scenario_endpoint_runs_s08_and_preserves_rag_evidence_boundary():
    response = dispatch_request("POST", "/scenario", b'{"scenario_id": "S08"}')
    data = payload(response)
    summary = data["summary"]

    assert response.status == 200
    assert data["scenario_id"] == "S08"
    assert summary["request_type"] == "policy_query"
    assert "display_response" in summary
    assert "display_response_zh" in summary
    assert summary["display_locale"] == "zh-CN"
    assert "raw_final_response" in summary
    assert "travel reimbursement policy" in summary["display_response"]
    assert "差旅报销政策" in summary["display_response_zh"]
    assert "RAG-POLICY-RESULT-0001" in summary["evidence_refs"]
    assert "RAG-EVAL-POLICY-0001" not in summary["evidence_refs"]
    assert "rag_quality_gate=passed" in summary["gate_checks"]


def test_scenario_endpoint_runs_s02_and_s04_as_supported_paths():
    s02 = payload(dispatch_request("POST", "/scenario", b'{"scenario_id": "S02"}'))["summary"]
    s04 = payload(dispatch_request("POST", "/scenario", b'{"scenario_id": "S04"}'))["summary"]

    assert s02["request_type"] == "salary_query"
    assert s02["risk_level"] == "high"
    assert "PERMISSION-CHECK-SALARY-0001" in s02["evidence_refs"]
    assert s04["request_type"] == "leave_cancellation"
    assert "HR-LEAVE-CANCEL-SUBMIT-0001" in s04["evidence_refs"]


def test_scenario_endpoint_returns_s15_waiting_summary_without_resume():
    response = dispatch_request("POST", "/scenario", b'{"scenario_id": "S15"}')
    summary = payload(response)["summary"]

    assert response.status == 200
    assert summary["request_type"] == "project_inquiry"
    assert summary["waiting_for"] == "project_owner_reply"
    assert summary["checkpoint_status"] == "ready_for_resume"
    assert "PROJECT-INQUIRY-REPLY-0001" not in summary["evidence_refs"]


def test_scenario_endpoint_rejects_designed_but_not_connected_scenario():
    response = dispatch_request("POST", "/scenario", b'{"scenario_id": "S03"}')
    data = payload(response)

    assert response.status == 400
    assert data["error"]["code"] == "unsupported_scenario_id"


def test_scenario_endpoint_rejects_unknown_scenario():
    response = dispatch_request("POST", "/scenario", b'{"scenario_id": "S99"}')
    data = payload(response)

    assert response.status == 400
    assert data["error"]["code"] == "unsupported_scenario_id"


def test_scenario_endpoint_rejects_malformed_json():
    response = dispatch_request("POST", "/scenario", b"{")
    data = payload(response)

    assert response.status == 400
    assert data["error"]["code"] == "invalid_json"


def test_agent_query_endpoint_denies_salary_request_with_default_test_employee():
    response = dispatch_request(
        "POST",
        "/agent/query",
        '{"message":"查一下我的工资"}'.encode("utf-8"),
    )
    data = payload(response)
    summary = data["summary"]

    assert response.status == 200
    assert data["entry"] == "agent_query"
    assert data["employee_id"] == "EMP-IT-DEV-0001"
    assert summary["request_type"] == "salary_query"
    assert summary["risk_level"] == "high"
    assert "resolve_identity_node" in summary["trace_nodes"]
    assert "permission_audit_node" in summary["trace_nodes"]
    assert "manual_review_node" in summary["trace_nodes"]
    assert "payroll_query_node" not in summary["trace_nodes"]
    assert "PERMISSION-CHECK-SALARY-DENIED-0001" in summary["evidence_refs"]
    assert "AUDIT-LOG-SALARY-0001" in summary["evidence_refs"]
    assert "HR-SALARY-PREVIEW-0001" not in summary["evidence_refs"]
    assert "EMPLOYEE-PROFILE-IT-DEV-0001" not in summary["evidence_refs"]
    assert "permission_audit=blocked" in summary["gate_checks"]
    assert "did not allow salary preview disclosure" in summary["display_response"]
    assert "18000" not in summary["display_response"]
    assert "14250" not in summary["display_response"]


def test_agent_query_endpoint_allows_salary_request_with_payroll_reader():
    response = dispatch_request(
        "POST",
        "/agent/query",
        b'{"message":"salary query request","employee_id":"EMP-HR-PAY-0001"}',
    )
    data = payload(response)
    summary = data["summary"]

    assert response.status == 200
    assert data["entry"] == "agent_query"
    assert data["employee_id"] == "EMP-HR-PAY-0001"
    assert summary["request_type"] == "salary_query"
    assert summary["risk_level"] == "high"
    assert "permission_audit_node" in summary["trace_nodes"]
    assert "payroll_query_node" in summary["trace_nodes"]
    assert "PERMISSION-CHECK-SALARY-0001" in summary["evidence_refs"]
    assert "AUDIT-LOG-SALARY-0001" in summary["evidence_refs"]
    assert "HR-SALARY-PREVIEW-0001" in summary["evidence_refs"]
    assert "permission_audit=passed" in summary["gate_checks"]
    assert "18000" in summary["display_response"]
    assert "14250" in summary["display_response"]


def test_agent_query_endpoint_runs_policy_request_from_natural_language():
    response = dispatch_request(
        "POST",
        "/agent/query",
        '{"message":"请查询差旅报销制度"}'.encode("utf-8"),
    )
    summary = payload(response)["summary"]

    assert response.status == 200
    assert summary["request_type"] == "policy_query"
    assert "RAG-POLICY-RESULT-0001" in summary["evidence_refs"]
    assert "RAG-EVAL-POLICY-0001" not in summary["evidence_refs"]
    assert "rag_quality_gate=passed" in summary["gate_checks"]


def test_agent_query_endpoint_rejects_empty_message():
    response = dispatch_request("POST", "/agent/query", b'{"message":"  "}')
    data = payload(response)

    assert response.status == 400
    assert data["error"]["code"] == "missing_message"


def test_root_ui_contains_agent_query_entry():
    response = dispatch_request("GET", "/")

    assert response.status == 200
    assert "Agent 对话入口" in response.body
    assert "agentMessage" in response.body
    assert "EMP-IT-DEV-0001" in response.body
    assert "fetch('/agent/query'" in response.body
