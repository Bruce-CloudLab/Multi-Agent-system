from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlparse

from office_agent.checkpointing import JsonCheckpointStore
from office_agent.graph import run_scenario, start_project_inquiry_thread
from office_agent.portfolio_demo import (
    display_response_for_case,
    display_response_zh_for_case,
    render_demo_report,
    run_portfolio_demo,
)
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


def summarize_runtime_state(scenario_id: str, state: dict[str, Any]) -> dict[str, Any]:
    checkpoint_context = state.get("checkpoint_context", {})
    raw_final_response = state.get("final_response", "")
    portfolio_case_id = _portfolio_case_id_for_scenario(scenario_id, state)
    display_response = (
        display_response_for_case(portfolio_case_id, state)
        if portfolio_case_id
        else raw_final_response
    )
    display_response_zh = (
        display_response_zh_for_case(portfolio_case_id, state)
        if portfolio_case_id
        else raw_final_response
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
        "display_locale": "zh-CN" if portfolio_case_id else "source",
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


def render_demo_ui() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>企业办公 Agent 本地演示控制台</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fb;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #5f6b7a;
      --line: #d9dee7;
      --teal: #0f766e;
      --teal-soft: #e0f2f1;
      --amber: #b7791f;
      --green: #2f855a;
      --red: #b91c1c;
      --code: #111827;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }

    button,
    select {
      font: inherit;
    }

    .app-shell {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 20px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .mark {
      width: 36px;
      height: 36px;
      border: 1px solid #7dd3c7;
      border-radius: 8px;
      display: grid;
      place-items: center;
      color: var(--teal);
      background: var(--teal-soft);
      font-weight: 800;
    }

    h1 {
      margin: 0;
      font-size: 18px;
      line-height: 1.25;
    }

    .subtitle {
      margin-top: 2px;
      color: var(--muted);
      font-size: 13px;
    }

    .status-pill {
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #ffffff;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }

    .workspace {
      display: grid;
      grid-template-columns: minmax(220px, 280px) minmax(360px, 1fr) minmax(280px, 380px);
      min-height: 0;
    }

    .rail,
    .detail,
    .inspect {
      min-width: 0;
      padding: 18px;
    }

    .rail {
      border-right: 1px solid var(--line);
      background: #fbfcfe;
    }

    .detail {
      background: var(--panel);
      border-right: 1px solid var(--line);
    }

    .inspect {
      background: #fbfcfe;
    }

    .section-title {
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }

    .case-list,
    .scenario-list {
      display: grid;
      gap: 8px;
    }

    .case-button,
    .scenario-button,
    .refresh-button {
      min-height: 40px;
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      color: var(--ink);
      cursor: pointer;
      text-align: left;
      padding: 8px 10px;
    }

    .case-button:hover,
    .scenario-button:hover,
    .refresh-button:hover,
    .case-button.active {
      border-color: #5eead4;
      background: var(--teal-soft);
    }

    .scenario-button {
      text-align: center;
    }

    .refresh-button {
      margin-top: 14px;
      text-align: center;
      color: #ffffff;
      background: var(--teal);
      border-color: var(--teal);
      font-weight: 700;
    }

    .case-kicker {
      color: var(--muted);
      font-size: 12px;
    }

    .case-name {
      margin-top: 2px;
      font-size: 14px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 16px 0;
    }

    .metric {
      min-height: 72px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfcfe;
    }

    .metric-label {
      color: var(--muted);
      font-size: 12px;
    }

    .metric-value {
      margin-top: 6px;
      font-size: 16px;
      font-weight: 800;
      overflow-wrap: anywhere;
    }

    .response {
      border: 1px solid #b7e4dc;
      border-radius: 8px;
      padding: 14px;
      background: #f0fdfa;
      line-height: 1.5;
    }

    .concept-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }

    .concept {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-height: 108px;
      background: #ffffff;
    }

    .concept h3 {
      margin: 0 0 8px;
      font-size: 13px;
    }

    .concept p,
    .concept code {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
      overflow-wrap: anywhere;
    }

    .node-path {
      margin-top: 12px;
      padding: 12px;
      border-radius: 8px;
      background: #111827;
      color: #e5e7eb;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.6;
      overflow-wrap: anywhere;
    }

    .list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 16px;
    }

    .tag {
      max-width: 100%;
      padding: 6px 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #ffffff;
      color: var(--code);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      overflow-wrap: anywhere;
    }

    .tag.evidence {
      border-color: #9ae6b4;
      background: #f0fff4;
      color: var(--green);
    }

    .tag.gate {
      border-color: #fbd38d;
      background: #fffaf0;
      color: var(--amber);
    }

    .raw-json {
      width: 100%;
      min-height: 280px;
      margin: 0;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #111827;
      color: #e5e7eb;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.5;
      overflow: auto;
      white-space: pre-wrap;
    }

    .error-text {
      color: var(--red);
      font-weight: 700;
    }

    .spacer {
      height: 18px;
    }

    @media (max-width: 1020px) {
      .workspace {
        grid-template-columns: 1fr;
      }

      .rail,
      .detail,
      .inspect {
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }

      .summary-grid,
      .concept-grid {
        grid-template-columns: 1fr 1fr;
      }
    }

    @media (max-width: 640px) {
      .topbar {
        align-items: flex-start;
        flex-direction: column;
      }

      .summary-grid,
      .concept-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="mark" aria-hidden="true">EA</div>
        <div>
          <h1>企业办公 Agent 本地演示控制台</h1>
          <div class="subtitle">LangGraph 演示：mock Tool/API/RAG 证据、权限审计、检查点和恢复。</div>
        </div>
      </div>
      <div id="status" class="status-pill">正在加载 demo 数据</div>
    </header>

    <main class="workspace">
      <aside class="rail">
        <h2 class="section-title">精选演示 Curated Demo</h2>
        <div id="caseList" class="case-list"></div>
        <button id="refreshButton" class="refresh-button" type="button">刷新 Demo</button>

        <div class="spacer"></div>
        <h2 class="section-title">运行场景 Run Scenario</h2>
        <div id="scenarioList" class="scenario-list"></div>
      </aside>

      <section class="detail" aria-live="polite">
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
            <p>只有 evidence_refs 是业务证据。Trace 和展示文案不是证据。</p>
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
        <pre id="rawJson" class="raw-json">{}</pre>
      </aside>
    </main>
  </div>

  <script>
    const scenarioIds = ['S01', 'S08', 'S05', 'S14', 'S15'];
    let cases = [];
    let selectedCaseId = null;

    const elements = {
      status: document.getElementById('status'),
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
    };

    function setStatus(message, isError = false) {
      elements.status.textContent = message;
      elements.status.classList.toggle('error-text', isError);
    }

    function asText(value, fallback = 'none') {
      if (value === null || value === undefined || value === '') {
        return fallback;
      }
      return String(value);
    }

    function nodePath(summary) {
      const nodes = summary.trace_nodes || [];
      return nodes.length ? nodes.join(' -> ') : 'none';
    }

    function stateFocus(summary) {
      return summary.state_focus || [
        `request_type=${asText(summary.request_type, 'unknown')}`,
        `risk=${asText(summary.risk_level, 'unknown')}`,
        `waiting_for=${asText(summary.waiting_for)}`,
        `checkpoint_status=${asText(summary.checkpoint_status)}`,
      ].join('; ');
    }

    function renderTags(container, values, className) {
      container.innerHTML = '';
      const items = values && values.length ? values : ['none'];
      for (const value of items) {
        const tag = document.createElement('span');
        tag.className = `tag ${className}`;
        tag.textContent = value;
        container.appendChild(tag);
      }
    }

    function renderSummary(summary) {
      selectedCaseId = summary.case_id || summary.scenario_id;
      elements.title.textContent = summary.title || summary.scenario_id || 'Scenario';
      elements.capability.textContent = summary.capability || 'Single scenario run from /scenario.';
      elements.stateMetric.textContent = `${asText(summary.request_type, 'unknown')} / ${asText(summary.risk_level, 'unknown')}`;
      elements.checkpointMetric.textContent = asText(summary.checkpoint_status);
      elements.interruptMetric.textContent = asText(summary.waiting_for);
      elements.traceMetric.textContent = `${summary.trace_event_count || 0} events`;
      elements.displayResponse.textContent = summary.display_response_zh || summary.display_response || summary.final_response || '没有可展示的回复。';
      elements.nodeFocus.textContent = summary.node_focus || nodePath(summary);
      elements.conditionalEdgeFocus.textContent = summary.conditional_edge_focus || '查看门禁检查和路由摘要。';
      elements.resumeFocus.textContent = summary.resume_focus || (summary.waiting_for ? '正在等待人工回复。' : '本次运行没有恢复路径。');
      elements.nodePath.textContent = nodePath(summary);
      renderTags(elements.evidenceList, summary.evidence_refs || [], 'evidence');
      renderTags(elements.gateList, summary.gate_checks || [], 'gate');
      elements.rawJson.textContent = JSON.stringify(summary, null, 2);
      renderCaseButtons();
    }

    function renderCaseButtons() {
      elements.caseList.innerHTML = '';
      for (const item of cases) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `case-button ${item.case_id === selectedCaseId ? 'active' : ''}`;
        button.innerHTML = `<div class="case-kicker">${item.case_id}</div><div class="case-name">${item.title}</div>`;
        button.addEventListener('click', () => renderSummary(item));
        elements.caseList.appendChild(button);
      }
    }

    function renderScenarioButtons() {
      elements.scenarioList.innerHTML = '';
      for (const id of scenarioIds) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'scenario-button';
        button.textContent = id;
        button.addEventListener('click', () => runScenario(id));
        elements.scenarioList.appendChild(button);
      }
    }

    async function loadDemo() {
      setStatus('正在加载 /demo');
      try {
        const response = await fetch('/demo');
        if (!response.ok) {
          throw new Error(`GET /demo failed with ${response.status}`);
        }
        const payload = await response.json();
        cases = payload.cases || [];
        renderCaseButtons();
        if (cases.length) {
          renderSummary(cases[0]);
          setStatus(`已加载 ${cases.length} 个精选案例`);
        } else {
          setStatus('未返回精选案例', true);
        }
      } catch (error) {
        setStatus(error.message, true);
        elements.displayResponse.textContent = '无法加载 /demo。';
      }
    }

    async function runScenario(scenarioId) {
      setStatus(`正在运行 ${scenarioId}`);
      try {
        const response = await fetch('/scenario', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({scenario_id: scenarioId}),
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error ? payload.error.message : `POST /scenario failed with ${response.status}`);
        }
        renderSummary({
          ...payload.summary,
          scenario_id: scenarioId,
          title: `场景 Scenario ${scenarioId}`,
        });
        setStatus(`场景 ${scenarioId} 已完成`);
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    elements.refreshButton.addEventListener('click', loadDemo);
    renderScenarioButtons();
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
