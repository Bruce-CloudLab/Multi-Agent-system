from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlparse

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from office_agent.checkpointing import JsonCheckpointStore
from office_agent.graph import build_graph, run_scenario, start_project_inquiry_thread
from office_agent.mock_tools import TEST_EMPLOYEE_ID
from office_agent.portfolio_demo import (
    display_response_for_case,
    display_response_zh_for_case,
    render_demo_report,
    run_portfolio_demo,
)
from office_agent.scenario_catalog import DESIGNED_SCENARIOS, scenario_catalog_payload
from office_agent.scenarios import SCENARIOS


RUNTIME_NAME = "local-service-v1"
SERVICE_NAME = "enterprise-office-agent"
S15_SCENARIO_THREAD_ID = "THREAD-SERVICE-RUNTIME-S15"


@dataclass(frozen=True)
class ServiceResponse:
    status: int
    content_type: str
    body: str


def _json_response(payload: dict[str, Any], status: int = 200) -> ServiceResponse:
    return ServiceResponse(
        status=status,
        content_type="application/json",
        body=json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )


def _text_response(body: str, status: int = 200) -> ServiceResponse:
    return ServiceResponse(status=status, content_type="text/plain; charset=utf-8", body=body)


def _html_response(body: str, status: int = 200) -> ServiceResponse:
    return ServiceResponse(status=status, content_type="text/html; charset=utf-8", body=body)


def _error_response(status: int, code: str, message: str) -> ServiceResponse:
    return _json_response(
        {
            "runtime": RUNTIME_NAME,
            "error": {
                "code": code,
                "message": message,
            },
        },
        status=status,
    )


def _evidence_refs(state: dict[str, Any]) -> list[str]:
    return [item["evidence_ref"] for item in state.get("evidence_refs", [])]


def _trace_nodes(state: dict[str, Any]) -> list[str]:
    return [event.get("node", "unknown_node") for event in state.get("trace_events", [])]


def _gate_checks(state: dict[str, Any]) -> list[str]:
    checks = []
    for gate in state.get("gate_checks", []):
        checks.append(f"{gate.get('gate', 'unknown_gate')}={gate.get('status', 'unknown')}")
    return checks


def _portfolio_case_id_for_scenario(scenario_id: str, state: dict[str, Any]) -> str | None:
    if scenario_id in {"S01", "S08", "S05", "S14"}:
        return scenario_id
    if scenario_id == "S15" and state.get("waiting_for") == "project_owner_reply":
        return "S15-start"
    return None


def _display_scenario_id_for_request_type(request_type: str) -> str:
    return {
        "repair": "S01",
        "salary_query": "S02",
        "leave_cancellation": "S04",
        "reception_schedule": "S05",
        "policy_query": "S08",
        "reception_plan_upload": "S14",
        "project_inquiry": "S15",
    }.get(request_type, "agent-query")


def _display_response_for_scenario(scenario_id: str, state: dict[str, Any]) -> tuple[str, str, str]:
    portfolio_case_id = _portfolio_case_id_for_scenario(scenario_id, state)
    if portfolio_case_id:
        return (
            display_response_for_case(portfolio_case_id, state),
            display_response_zh_for_case(portfolio_case_id, state),
            "zh-CN",
        )

    context = state.get("domain_context", {})
    evidence = ", ".join(_evidence_refs(state)) or "none"

    if scenario_id == "S02":
        salary = context.get("salary_query", {})
        permission = state.get("permission_context", {})
        permission_status = permission.get("permission_status")
        if permission_status != "allowed" or not salary:
            reason = permission.get("denial_reason") or state.get(
                "blocked_reason",
                "permission_denied",
            )
            english = (
                "Permission check did not allow salary preview disclosure. "
                "No salary data was loaded. Audit was recorded. "
                f"Reason: {reason}. Business evidence: {evidence}."
            )
            chinese = (
                "权限校验未通过，系统没有读取或披露薪资预览。"
                f"审计已记录。原因：{reason}。业务证据：{evidence}。"
            )
            return english, chinese, "zh-CN"

        month = salary.get("target_month", "unknown_month")
        gross_salary = salary.get("gross_salary", "unknown")
        net_salary = salary.get("estimated_net_salary", "unknown")
        currency = salary.get("currency", "CNY")
        english = (
            "Permission and audit passed before salary preview disclosure. "
            f"For {month}, gross salary is {gross_salary} {currency}, estimated "
            f"net salary is {net_salary} {currency}. Business evidence: {evidence}."
        )
        chinese = (
            "系统先完成权限校验和审计，再披露薪资预览。"
            f"{month} 的税前薪资为 {gross_salary} {currency}，"
            f"预估税后薪资为 {net_salary} {currency}。业务证据：{evidence}。"
        )
        return english, chinese, "zh-CN"

    if scenario_id == "S04":
        leave = context.get("leave_record", {})
        cancellation = context.get("leave_cancellation", {})
        leave_id = leave.get("leave_id", "unknown_leave")
        cancellation_id = cancellation.get("cancellation_id", "unknown_cancellation")
        english = (
            f"Leave cancellation {cancellation_id} was submitted for leave "
            f"{leave_id}. Business evidence: {evidence}."
        )
        chinese = (
            f"已为请假记录 {leave_id} 提交销假申请 {cancellation_id}。"
            f"业务证据：{evidence}。"
        )
        return english, chinese, "zh-CN"

    raw_response = state.get("final_response", "")
    return raw_response, raw_response, "source"


def summarize_runtime_state(scenario_id: str, state: dict[str, Any]) -> dict[str, Any]:
    checkpoint_context = state.get("checkpoint_context", {})
    raw_final_response = state.get("final_response", "")
    display_response, display_response_zh, display_locale = _display_response_for_scenario(
        scenario_id,
        state,
    )
    return {
        "scenario_id": scenario_id,
        "request_type": state.get("request_type", "unknown"),
        "risk_level": state.get("risk_precheck", {}).get("level", "unknown"),
        "waiting_for": state.get("waiting_for"),
        "checkpoint_status": checkpoint_context.get("status", "none"),
        "trace_nodes": _trace_nodes(state),
        "trace_event_count": len(state.get("trace_events", [])),
        "evidence_refs": _evidence_refs(state),
        "gate_checks": _gate_checks(state),
        "display_response": display_response,
        "display_response_zh": display_response_zh,
        "display_locale": display_locale,
        "raw_final_response": raw_final_response,
        "final_response": display_response,
    }


def _run_s15_start_summary() -> dict[str, Any]:
    with TemporaryDirectory(prefix="office-agent-service-s15-") as temp_dir:
        checkpoint_store = JsonCheckpointStore(Path(temp_dir) / "s15")
        waiting = start_project_inquiry_thread(
            "S15",
            checkpoint_store=checkpoint_store,
            thread_id=S15_SCENARIO_THREAD_ID,
        )
        return summarize_runtime_state("S15", waiting)


def _run_scenario_summary(scenario_id: str) -> dict[str, Any]:
    if scenario_id == "S15":
        return _run_s15_start_summary()
    return summarize_runtime_state(scenario_id, run_scenario(scenario_id))


def _demo_payload() -> dict[str, Any]:
    cases = run_portfolio_demo()
    return {
        "runtime": RUNTIME_NAME,
        "service": SERVICE_NAME,
        "case_count": len(cases),
        "cases": cases,
    }


def _parse_json_body(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_json") from exc
    if not isinstance(payload, dict):
        raise ValueError("json_body_must_be_object")
    return payload


def _handle_scenario(body: bytes) -> ServiceResponse:
    try:
        payload = _parse_json_body(body)
    except ValueError as exc:
        return _error_response(400, str(exc), "Request body must be a valid JSON object.")

    scenario_id = payload.get("scenario_id")
    if not isinstance(scenario_id, str):
        return _error_response(400, "missing_scenario_id", "scenario_id must be a string.")
    if scenario_id not in SCENARIOS:
        return _error_response(400, "unsupported_scenario_id", f"Unsupported scenario_id: {scenario_id}")

    return _json_response(
        {
            "runtime": RUNTIME_NAME,
            "service": SERVICE_NAME,
            "scenario_id": scenario_id,
            "summary": _run_scenario_summary(scenario_id),
        }
    )


def _run_agent_query_summary(message: str, employee_id: str) -> dict[str, Any]:
    app = build_graph()
    state = app.invoke(
        {
            "user_input": message,
            "operator": {
                "employee_id": employee_id,
                "name": employee_id,
            },
        }
    )
    display_scenario_id = _display_scenario_id_for_request_type(
        state.get("request_type", "unknown")
    )
    summary = summarize_runtime_state(display_scenario_id, state)
    summary["scenario_id"] = "agent-query"
    summary["display_scenario_id"] = display_scenario_id
    summary["source"] = "agent_query"
    summary["message"] = message
    summary["employee_id"] = employee_id
    return summary


def _handle_agent_query(body: bytes) -> ServiceResponse:
    try:
        payload = _parse_json_body(body)
    except ValueError as exc:
        return _error_response(400, str(exc), "Request body must be a valid JSON object.")

    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        return _error_response(400, "missing_message", "message must be a non-empty string.")

    employee_id = payload.get("employee_id", TEST_EMPLOYEE_ID)
    if not isinstance(employee_id, str) or not employee_id.strip():
        return _error_response(
            400,
            "invalid_employee_id",
            "employee_id must be a non-empty string when provided.",
        )

    employee_id = employee_id.strip()
    message = message.strip()
    return _json_response(
        {
            "runtime": RUNTIME_NAME,
            "service": SERVICE_NAME,
            "entry": "agent_query",
            "message": message,
            "employee_id": employee_id,
            "summary": _run_agent_query_summary(message, employee_id),
        }
    )


def _scenario_id_json() -> str:
    ids = [item["scenario_id"] for item in DESIGNED_SCENARIOS]
    return json.dumps(ids, ensure_ascii=False)


def render_demo_ui() -> str:
    scenario_ids = _scenario_id_json()
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>企业办公 Agent 本地运行台</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --panel-soft: #f9fafb;
      --ink: #17202a;
      --muted: #647184;
      --line: #d8dee8;
      --teal: #0f766e;
      --teal-soft: #e0f2f1;
      --blue: #1d4ed8;
      --blue-soft: #eff6ff;
      --amber: #a16207;
      --amber-soft: #fffbeb;
      --green: #237a4b;
      --green-soft: #f0fdf4;
      --red: #b91c1c;
      --code: #111827;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}

    button {{
      font: inherit;
    }}

    .app-shell {{
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }}

    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 20px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}

    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }}

    .mark {{
      width: 36px;
      height: 36px;
      border: 1px solid #7dd3c7;
      border-radius: 8px;
      display: grid;
      place-items: center;
      color: var(--teal);
      background: var(--teal-soft);
      font-weight: 800;
    }}

    h1 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.25;
    }}

    h2 {{
      margin: 0;
      font-size: 17px;
      line-height: 1.35;
    }}

    .subtitle {{
      margin-top: 2px;
      color: var(--muted);
      font-size: 13px;
    }}

    .status-pill {{
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--panel);
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }}

    .workspace {{
      display: grid;
      grid-template-columns: minmax(300px, 360px) minmax(360px, 1fr) minmax(300px, 390px);
      min-height: 0;
    }}

    .rail,
    .detail,
    .inspect {{
      min-width: 0;
      padding: 18px;
    }}

    .rail {{
      border-right: 1px solid var(--line);
      background: var(--panel-soft);
      overflow: auto;
    }}

    .detail {{
      background: var(--panel);
      border-right: 1px solid var(--line);
      overflow: auto;
    }}

    .inspect {{
      background: var(--panel-soft);
      overflow: auto;
    }}

    .section-title {{
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}

    .case-list,
    .scenario-list {{
      display: grid;
      gap: 8px;
    }}

    .case-button,
    .scenario-card,
    .refresh-button {{
      min-height: 42px;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--ink);
      cursor: pointer;
      text-align: left;
      padding: 9px 10px;
    }}

    .case-button:hover,
    .scenario-card:hover,
    .refresh-button:hover,
    .case-button.active,
    .scenario-card.active {{
      border-color: #5eead4;
      background: var(--teal-soft);
    }}

    .scenario-card:disabled {{
      cursor: default;
      color: var(--muted);
      background: #f1f3f6;
    }}

    .scenario-card:disabled:hover {{
      border-color: var(--line);
      background: #f1f3f6;
    }}

    .refresh-button {{
      margin-top: 14px;
      text-align: center;
      color: #ffffff;
      background: var(--teal);
      border-color: var(--teal);
      font-weight: 700;
    }}

    .case-kicker,
    .scenario-meta {{
      color: var(--muted);
      font-size: 12px;
    }}

    .case-name,
    .scenario-title {{
      margin-top: 3px;
      font-size: 14px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }}

    .scenario-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }}

    .badge {{
      flex: 0 0 auto;
      padding: 3px 7px;
      border-radius: 999px;
      border: 1px solid var(--line);
      font-size: 11px;
      color: var(--muted);
      background: var(--panel);
    }}

    .badge.runnable {{
      color: var(--green);
      border-color: #86efac;
      background: var(--green-soft);
    }}

    .badge.not_connected {{
      color: var(--amber);
      border-color: #facc15;
      background: var(--amber-soft);
    }}

    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 16px 0;
    }}

    .metric {{
      min-height: 72px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: var(--panel-soft);
    }}

    .metric-label {{
      color: var(--muted);
      font-size: 12px;
    }}

    .metric-value {{
      margin-top: 6px;
      font-size: 16px;
      font-weight: 800;
      overflow-wrap: anywhere;
    }}

    .response {{
      border: 1px solid #b7e4dc;
      border-radius: 8px;
      padding: 14px;
      background: #f0fdfa;
      line-height: 1.55;
    }}

    .agent-panel {{
      border: 1px solid #b7e4dc;
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 16px;
      background: #f8fffe;
    }}

    .agent-form {{
      display: grid;
      gap: 10px;
      margin-top: 10px;
    }}

    .agent-message {{
      width: 100%;
      min-height: 92px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      color: var(--ink);
      background: var(--panel);
      font: inherit;
      line-height: 1.45;
    }}

    .agent-controls {{
      display: grid;
      grid-template-columns: auto minmax(180px, 1fr) auto;
      gap: 8px;
      align-items: center;
    }}

    .field-label {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }}

    .agent-input {{
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px 10px;
      color: var(--ink);
      background: var(--panel);
      font: inherit;
    }}

    .primary-button {{
      min-height: 40px;
      border: 1px solid var(--teal);
      border-radius: 8px;
      padding: 8px 14px;
      color: #ffffff;
      background: var(--teal);
      cursor: pointer;
      font-weight: 800;
      white-space: nowrap;
    }}

    .primary-button:hover {{
      background: #115e59;
    }}

    .concept-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }}

    .concept {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-height: 108px;
      background: var(--panel);
    }}

    .concept h3 {{
      margin: 0 0 8px;
      font-size: 13px;
    }}

    .concept p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
      overflow-wrap: anywhere;
    }}

    .node-path {{
      margin-top: 12px;
      padding: 12px;
      border-radius: 8px;
      background: var(--code);
      color: #e5e7eb;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.6;
      overflow-wrap: anywhere;
    }}

    .list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 16px;
    }}

    .tag {{
      max-width: 100%;
      padding: 6px 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--code);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      overflow-wrap: anywhere;
    }}

    .tag.evidence {{
      border-color: #9ae6b4;
      background: var(--green-soft);
      color: var(--green);
    }}

    .tag.gate {{
      border-color: #fbd38d;
      background: var(--amber-soft);
      color: var(--amber);
    }}

    .raw-json {{
      width: 100%;
      min-height: 280px;
      margin: 0;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--code);
      color: #e5e7eb;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.5;
      overflow: auto;
      white-space: pre-wrap;
    }}

    .error-text {{
      color: var(--red);
      font-weight: 700;
    }}

    .spacer {{
      height: 18px;
    }}

    @media (max-width: 1120px) {{
      .workspace {{
        grid-template-columns: 1fr;
      }}

      .rail,
      .detail,
      .inspect {{
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }}

      .summary-grid,
      .concept-grid {{
        grid-template-columns: 1fr 1fr;
      }}
    }}

    @media (max-width: 640px) {{
      .topbar {{
        align-items: flex-start;
        flex-direction: column;
      }}

      .agent-controls {{
        grid-template-columns: 1fr;
      }}

      .summary-grid,
      .concept-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="mark" aria-hidden="true">EA</div>
        <div>
          <h1>企业办公 Agent 本地运行台</h1>
          <div class="subtitle">系统运行入口 · LangGraph + mock Tool/API/RAG evidence</div>
        </div>
      </div>
      <div id="status" class="status-pill">正在加载运行目录</div>
    </header>

    <main class="workspace">
      <aside class="rail">
        <h2 class="section-title">系统运行入口</h2>
        <div id="scenarioList" class="scenario-list"></div>

        <div class="spacer"></div>
        <h2 class="section-title">精选演示 Curated Demo</h2>
        <div id="caseList" class="case-list"></div>
        <button id="refreshButton" class="refresh-button" type="button">刷新 Demo</button>
      </aside>

      <section class="detail" aria-live="polite">
        <div class="agent-panel">
          <h2>Agent 对话入口</h2>
          <form id="agentForm" class="agent-form">
            <textarea id="agentMessage" class="agent-message" name="message">查一下我的工资</textarea>
            <div class="agent-controls">
              <label class="field-label" for="employeeId">员工 ID</label>
              <input id="employeeId" class="agent-input" name="employee_id" value="{TEST_EMPLOYEE_ID}">
              <button id="askButton" class="primary-button" type="submit">发送</button>
            </div>
          </form>
        </div>

        <h2 id="title">状态 State</h2>
        <p id="capability" class="subtitle"></p>

        <div class="summary-grid">
          <div class="metric">
            <div class="metric-label">状态 State</div>
            <div id="stateMetric" class="metric-value">none</div>
          </div>
          <div class="metric">
            <div class="metric-label">检查点 Checkpoint</div>
            <div id="checkpointMetric" class="metric-value">none</div>
          </div>
          <div class="metric">
            <div class="metric-label">中断 Interrupt</div>
            <div id="interruptMetric" class="metric-value">none</div>
          </div>
          <div class="metric">
            <div class="metric-label">轨迹 Trace</div>
            <div id="traceMetric" class="metric-value">0 events</div>
          </div>
        </div>

        <h2 class="section-title">中文展示 Display Response</h2>
        <div id="displayResponse" class="response">正在加载。</div>

        <div class="concept-grid">
          <div class="concept">
            <h3>节点路径 Node Path</h3>
            <p id="nodeFocus">图节点路径会显示在这里。</p>
          </div>
          <div class="concept">
            <h3>条件边 Conditional Edge</h3>
            <p id="conditionalEdgeFocus">分支判断会显示在这里。</p>
          </div>
          <div class="concept">
            <h3>恢复 Resume</h3>
            <p id="resumeFocus">恢复状态会显示在这里。</p>
          </div>
          <div class="concept">
            <h3>证据 Evidence</h3>
            <p>只有 evidence_refs 是业务证据；Trace、目录和展示文案不是证据。</p>
          </div>
        </div>

        <h2 class="section-title" style="margin-top: 18px;">边 Edge</h2>
        <div id="nodePath" class="node-path">none</div>
      </section>

      <aside class="inspect">
        <h2 class="section-title">证据 Evidence</h2>
        <div id="evidenceList" class="list"></div>

        <h2 class="section-title">门禁检查 Gate Checks</h2>
        <div id="gateList" class="list"></div>

        <h2 class="section-title">原始摘要 Raw Summary</h2>
        <pre id="rawJson" class="raw-json">{{}}</pre>
      </aside>
    </main>
  </div>

  <script>
    const expectedScenarioIds = {scenario_ids};
    const statusLabels = {{
      runnable: '可运行',
      not_connected: '未接入运行',
    }};
    let cases = [];
    let scenarioCatalog = expectedScenarioIds.map((id) => ({{
      scenario_id: id,
      title: id,
      request_type: 'unknown',
      risk_level: 'unknown',
      status: 'not_connected',
      run_hint: '正在加载运行目录',
      description: '',
    }}));
    let selectedCaseId = null;

    const elements = {{
      status: document.getElementById('status'),
      agentForm: document.getElementById('agentForm'),
      agentMessage: document.getElementById('agentMessage'),
      employeeId: document.getElementById('employeeId'),
      askButton: document.getElementById('askButton'),
      caseList: document.getElementById('caseList'),
      scenarioList: document.getElementById('scenarioList'),
      refreshButton: document.getElementById('refreshButton'),
      title: document.getElementById('title'),
      capability: document.getElementById('capability'),
      stateMetric: document.getElementById('stateMetric'),
      checkpointMetric: document.getElementById('checkpointMetric'),
      interruptMetric: document.getElementById('interruptMetric'),
      traceMetric: document.getElementById('traceMetric'),
      displayResponse: document.getElementById('displayResponse'),
      nodeFocus: document.getElementById('nodeFocus'),
      conditionalEdgeFocus: document.getElementById('conditionalEdgeFocus'),
      resumeFocus: document.getElementById('resumeFocus'),
      nodePath: document.getElementById('nodePath'),
      evidenceList: document.getElementById('evidenceList'),
      gateList: document.getElementById('gateList'),
      rawJson: document.getElementById('rawJson'),
    }};

    function setStatus(message, isError = false) {{
      elements.status.textContent = message;
      elements.status.classList.toggle('error-text', isError);
    }}

    function asText(value, fallback = 'none') {{
      if (value === null || value === undefined || value === '') {{
        return fallback;
      }}
      return String(value);
    }}

    function nodePath(summary) {{
      const nodes = summary.trace_nodes || [];
      return nodes.length ? nodes.join(' -> ') : 'none';
    }}

    function renderTags(container, values, className) {{
      container.innerHTML = '';
      const items = values && values.length ? values : ['none'];
      for (const value of items) {{
        const tag = document.createElement('span');
        tag.className = `tag ${{className}}`;
        tag.textContent = value;
        container.appendChild(tag);
      }}
    }}

    function renderSummary(summary) {{
      selectedCaseId = summary.case_id || summary.scenario_id;
      elements.title.textContent = summary.title || summary.scenario_id || 'Scenario';
      elements.capability.textContent = summary.capability || 'Single scenario run from /scenario.';
      elements.stateMetric.textContent = `${{asText(summary.request_type, 'unknown')}} / ${{asText(summary.risk_level, 'unknown')}}`;
      elements.checkpointMetric.textContent = asText(summary.checkpoint_status);
      elements.interruptMetric.textContent = asText(summary.waiting_for);
      elements.traceMetric.textContent = `${{summary.trace_event_count || 0}} events`;
      elements.displayResponse.textContent = summary.display_response_zh || summary.display_response || summary.final_response || '没有可展示的回复。';
      elements.nodeFocus.textContent = summary.node_focus || nodePath(summary);
      elements.conditionalEdgeFocus.textContent = summary.conditional_edge_focus || '查看门禁检查和路由摘要。';
      elements.resumeFocus.textContent = summary.resume_focus || (summary.waiting_for ? '正在等待人工回复。' : '本次运行没有恢复路径。');
      elements.nodePath.textContent = nodePath(summary);
      renderTags(elements.evidenceList, summary.evidence_refs || [], 'evidence');
      renderTags(elements.gateList, summary.gate_checks || [], 'gate');
      elements.rawJson.textContent = JSON.stringify(summary, null, 2);
      renderCaseButtons();
      renderScenarioCatalog();
    }}

    function renderCaseButtons() {{
      elements.caseList.innerHTML = '';
      for (const item of cases) {{
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `case-button ${{item.case_id === selectedCaseId ? 'active' : ''}}`;
        button.innerHTML = `<div class="case-kicker">${{item.case_id}}</div><div class="case-name">${{item.title}}</div>`;
        button.addEventListener('click', () => renderSummary(item));
        elements.caseList.appendChild(button);
      }}
    }}

    function renderScenarioCatalog() {{
      elements.scenarioList.innerHTML = '';
      for (const item of scenarioCatalog) {{
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `scenario-card ${{item.scenario_id === selectedCaseId ? 'active' : ''}}`;
        button.disabled = item.status !== 'runnable';
        button.innerHTML = `
          <div class="scenario-row">
            <span class="scenario-meta">${{item.scenario_id}} · ${{item.request_type}} · ${{item.risk_level}}</span>
            <span class="badge ${{item.status}}">${{statusLabels[item.status] || item.status}}</span>
          </div>
          <div class="scenario-title">${{item.title}}</div>
          <div class="scenario-meta">${{item.description}}</div>
          <div class="scenario-meta">${{item.run_hint}}</div>
        `;
        if (item.status === 'runnable') {{
          button.addEventListener('click', () => runScenario(item.scenario_id, item));
        }}
        elements.scenarioList.appendChild(button);
      }}
    }}

    async function runAgentQuery(event) {{
      event.preventDefault();
      const message = elements.agentMessage.value.trim();
      const employeeId = elements.employeeId.value.trim();
      if (!message) {{
        setStatus('请输入问题', true);
        return;
      }}
      setStatus('正在运行 Agent');
      try {{
        const response = await fetch('/agent/query', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{
            message,
            employee_id: employeeId || undefined,
          }}),
        }});
        const payload = await response.json();
        if (!response.ok) {{
          throw new Error(payload.error ? payload.error.message : `POST /agent/query failed with ${{response.status}}`);
        }}
        renderSummary({{
          ...payload.summary,
          title: 'Agent 对话入口',
          capability: `输入：${{payload.message}}`,
        }});
        setStatus('Agent 已完成');
      }} catch (error) {{
        setStatus(error.message, true);
      }}
    }}

    async function loadScenarioCatalog() {{
      try {{
        const response = await fetch('/scenarios');
        if (!response.ok) {{
          throw new Error(`GET /scenarios failed with ${{response.status}}`);
        }}
        const payload = await response.json();
        scenarioCatalog = payload.scenarios || [];
        renderScenarioCatalog();
        setStatus(`已加载 ${{payload.total_count}} 个场景，${{payload.runnable_count}} 个可运行`);
      }} catch (error) {{
        setStatus(error.message, true);
      }}
    }}

    async function loadDemo() {{
      setStatus('正在加载 /demo');
      try {{
        const response = await fetch('/demo');
        if (!response.ok) {{
          throw new Error(`GET /demo failed with ${{response.status}}`);
        }}
        const payload = await response.json();
        cases = payload.cases || [];
        renderCaseButtons();
        if (cases.length) {{
          renderSummary(cases[0]);
        }}
      }} catch (error) {{
        setStatus(error.message, true);
        elements.displayResponse.textContent = '无法加载 /demo。';
      }}
    }}

    async function runScenario(scenarioId, catalogItem) {{
      setStatus(`正在运行 ${{scenarioId}}`);
      try {{
        const response = await fetch('/scenario', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{scenario_id: scenarioId}}),
        }});
        const payload = await response.json();
        if (!response.ok) {{
          throw new Error(payload.error ? payload.error.message : `POST /scenario failed with ${{response.status}}`);
        }}
        renderSummary({{
          ...payload.summary,
          scenario_id: scenarioId,
          title: `${{scenarioId}} ${{catalogItem.title}}`,
          capability: catalogItem.description,
        }});
        setStatus(`场景 ${{scenarioId}} 已完成`);
      }} catch (error) {{
        setStatus(error.message, true);
      }}
    }}

    elements.agentForm.addEventListener('submit', runAgentQuery);
    elements.refreshButton.addEventListener('click', loadDemo);
    renderScenarioCatalog();
    loadScenarioCatalog();
    loadDemo();
  </script>
</body>
</html>
"""


def dispatch_request(method: str, path: str, body: bytes = b"") -> ServiceResponse:
    route = urlparse(path).path
    method = method.upper()

    try:
        if route in {"/", "/demo/ui"}:
            if method != "GET":
                return _error_response(405, "method_not_allowed", "Use GET for the demo UI.")
            return _html_response(render_demo_ui())

        if route == "/health":
            if method != "GET":
                return _error_response(405, "method_not_allowed", "Use GET for /health.")
            return _json_response(
                {
                    "status": "ok",
                    "service": SERVICE_NAME,
                    "runtime": RUNTIME_NAME,
                }
            )

        if route == "/scenarios":
            if method != "GET":
                return _error_response(405, "method_not_allowed", "Use GET for /scenarios.")
            return _json_response(scenario_catalog_payload(RUNTIME_NAME, SERVICE_NAME))

        if route == "/demo":
            if method != "GET":
                return _error_response(405, "method_not_allowed", "Use GET for /demo.")
            return _json_response(_demo_payload())

        if route == "/demo/report":
            if method != "GET":
                return _error_response(405, "method_not_allowed", "Use GET for /demo/report.")
            return _text_response(render_demo_report(run_portfolio_demo()))

        if route == "/scenario":
            if method != "POST":
                return _error_response(405, "method_not_allowed", "Use POST for /scenario.")
            return _handle_scenario(body)

        if route == "/agent/query":
            if method != "POST":
                return _error_response(405, "method_not_allowed", "Use POST for /agent/query.")
            return _handle_agent_query(body)
    except Exception:
        return _error_response(
            500,
            "runtime_error",
            "The local service runtime failed while executing the request.",
        )

    return _error_response(404, "not_found", f"Unknown path: {route}")


def make_handler() -> type[BaseHTTPRequestHandler]:
    class OfficeAgentRequestHandler(BaseHTTPRequestHandler):
        server_version = "OfficeAgentLocalService/1.0"

        def do_GET(self) -> None:
            self._send(dispatch_request("GET", self.path))

        def do_POST(self) -> None:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)
            self._send(dispatch_request("POST", self.path, body))

        def _send(self, response: ServiceResponse) -> None:
            body = response.body.encode("utf-8")
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return OfficeAgentRequestHandler


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), make_handler())
    print(f"{SERVICE_NAME} {RUNTIME_NAME} listening on http://{host}:{port}", flush=True)
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Enterprise Office Agent local service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    serve(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
