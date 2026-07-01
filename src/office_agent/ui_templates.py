from __future__ import annotations

import json
from typing import Any

from office_agent.auth import public_demo_accounts


def _json_script_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_login_ui(error_message: str | None = None) -> str:
    accounts_json = _json_script_value(public_demo_accounts())
    error_json = _json_script_value(error_message or "")
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>企业办公 Agent · 登录</title>
  <style>
    :root {
      color-scheme: light;
      --paper: #f7f5ef;
      --panel: rgba(255, 255, 252, 0.88);
      --panel-solid: #fffefa;
      --ink: #171a17;
      --muted: #6e746f;
      --line: rgba(23, 26, 23, 0.14);
      --line-strong: rgba(23, 26, 23, 0.24);
      --teal: #0f766e;
      --teal-dark: #0b4f4a;
      --gold: #9a6a22;
      --danger: #a12828;
      --shadow: 0 24px 80px rgba(22, 28, 24, 0.16);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--paper);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }

    button,
    input {
      font: inherit;
    }

    .login-shell {
      min-height: 100vh;
      display: grid;
      grid-template-columns: minmax(420px, 1fr) minmax(380px, 520px);
    }

    .art {
      position: relative;
      min-height: 100vh;
      background:
        linear-gradient(90deg, rgba(247, 245, 239, 0.18), rgba(247, 245, 239, 0.04)),
        url("/static/agent-oil-hero.png") center / cover no-repeat;
      border-right: 1px solid var(--line);
      overflow: hidden;
    }

    .art::after {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(255,255,255,0.14), rgba(15,31,29,0.08));
      pointer-events: none;
    }

    .brand-lockup {
      position: absolute;
      left: 34px;
      top: 30px;
      display: flex;
      align-items: center;
      gap: 12px;
      z-index: 1;
    }

    .mark {
      width: 36px;
      height: 36px;
      border: 1px solid rgba(255, 255, 255, 0.5);
      border-radius: 9px;
      display: grid;
      place-items: center;
      color: #f9f7ee;
      background: rgba(10, 18, 16, 0.42);
      backdrop-filter: blur(18px);
      font-weight: 800;
    }

    .brand-title {
      color: #fbfaf4;
      text-shadow: 0 1px 12px rgba(0, 0, 0, 0.26);
      font-size: 15px;
      font-weight: 750;
    }

    .login-panel {
      min-height: 100vh;
      display: grid;
      align-content: center;
      padding: 52px;
      background: var(--panel-solid);
    }

    .panel-inner {
      width: 100%;
      max-width: 420px;
      margin: 0 auto;
    }

    .eyebrow {
      margin: 0 0 18px;
      color: var(--gold);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }

    h1 {
      margin: 0;
      font-size: 36px;
      line-height: 1.08;
      font-weight: 780;
    }

    .lead {
      margin: 14px 0 28px;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.58;
    }

    .form {
      display: grid;
      gap: 14px;
    }

    .field {
      display: grid;
      gap: 7px;
    }

    label {
      color: var(--muted);
      font-size: 13px;
      font-weight: 750;
    }

    input {
      min-height: 46px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 11px 13px;
      background: #ffffff;
      color: var(--ink);
      outline: none;
    }

    input:focus {
      border-color: var(--teal);
      box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.12);
    }

    .primary {
      min-height: 46px;
      border: 1px solid var(--ink);
      border-radius: 10px;
      background: var(--ink);
      color: #ffffff;
      cursor: pointer;
      font-weight: 800;
    }

    .primary:hover {
      background: #2a2d29;
    }

    .account-grid {
      display: grid;
      gap: 9px;
      margin-top: 18px;
    }

    .account-button {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #ffffff;
      color: var(--ink);
      cursor: pointer;
      padding: 10px 12px;
      text-align: left;
    }

    .account-button:hover {
      border-color: var(--line-strong);
      background: #f8f7f1;
    }

    .account-main {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      font-weight: 800;
      font-size: 13px;
    }

    .account-meta {
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }

    .error {
      min-height: 20px;
      color: var(--danger);
      font-size: 13px;
      font-weight: 750;
    }

    @media (max-width: 880px) {
      .login-shell {
        grid-template-columns: 1fr;
      }

      .art {
        min-height: 260px;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }

      .login-panel {
        min-height: auto;
        padding: 32px 22px 44px;
      }

      h1 {
        font-size: 30px;
      }
    }
  </style>
</head>
<body>
  <main class="login-shell">
    <section class="art" aria-label="抽象油画背景">
      <div class="brand-lockup">
        <div class="mark" aria-hidden="true">EA</div>
        <div class="brand-title">Enterprise Office Agent</div>
      </div>
    </section>

    <section class="login-panel">
      <div class="panel-inner">
        <p class="eyebrow">Local Demo Access</p>
        <h1>企业办公 Agent</h1>
        <p class="lead">登录后进入工作台，使用演示账号触发真实 LangGraph 路由、权限门禁、Trace 与 Evidence 展示。</p>

        <form id="loginForm" class="form">
          <div class="field">
            <label for="username">账号</label>
            <input id="username" name="username" autocomplete="username" value="it.demo">
          </div>
          <div class="field">
            <label for="password">密码</label>
            <input id="password" name="password" type="password" autocomplete="current-password" value="demo123">
          </div>
          <button class="primary" type="submit">进入工作台</button>
          <div id="error" class="error" role="status"></div>
        </form>

        <div id="accounts" class="account-grid" aria-label="演示账号"></div>
      </div>
    </section>
  </main>

  <script>
    const accounts = __ACCOUNTS__;
    const initialError = __ERROR__;
    const username = document.getElementById('username');
    const password = document.getElementById('password');
    const error = document.getElementById('error');
    const accountsEl = document.getElementById('accounts');
    error.textContent = initialError;

    function fillAccount(account) {
      username.value = account.username;
      password.value = account.password;
      error.textContent = '';
    }

    for (const account of accounts) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'account-button';
      button.innerHTML = `
        <div class="account-main">
          <span>${account.username}</span>
          <span>${account.password}</span>
        </div>
        <div class="account-meta">${account.employee_id} · ${account.role_label}</div>
      `;
      button.addEventListener('click', () => fillAccount(account));
      accountsEl.appendChild(button);
    }

    document.getElementById('loginForm').addEventListener('submit', async (event) => {
      event.preventDefault();
      error.textContent = '';
      const response = await fetch('/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          username: username.value.trim(),
          password: password.value,
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        error.textContent = payload.error ? payload.error.message : '登录失败';
        return;
      }
      window.location.href = payload.redirect_to || '/';
    });
  </script>
</body>
</html>
""".replace("__ACCOUNTS__", accounts_json).replace("__ERROR__", error_json)


def render_dashboard_ui(default_employee_id: str, current_user: dict[str, str]) -> str:
    user_json = _json_script_value(current_user)
    default_prompt_json = _json_script_value(
        current_user.get("default_prompt", "查一下我的工资")
    )
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>企业办公 Agent 工作台</title>
  <style>
    :root {
      color-scheme: light;
      --canvas: #f5f4ef;
      --surface: #fffefa;
      --surface-soft: #faf9f3;
      --ink: #171a17;
      --muted: #69716b;
      --line: rgba(23, 26, 23, 0.13);
      --line-strong: rgba(23, 26, 23, 0.22);
      --teal: #0f766e;
      --teal-soft: #e5f4f1;
      --gold: #9a6a22;
      --gold-soft: #f4ead8;
      --green: #2f7d55;
      --red: #a12828;
      --code: #151815;
      --shadow: 0 18px 60px rgba(22, 28, 24, 0.12);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--canvas);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }

    button,
    textarea,
    input {
      font: inherit;
    }

    .app {
      min-height: 100vh;
      display: grid;
      grid-template-rows: 68px 1fr;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 0 22px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 254, 250, 0.88);
      backdrop-filter: blur(18px);
      position: sticky;
      top: 0;
      z-index: 5;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .mark {
      width: 34px;
      height: 34px;
      border: 1px solid var(--line-strong);
      border-radius: 9px;
      display: grid;
      place-items: center;
      color: var(--ink);
      background: var(--surface);
      font-weight: 850;
    }

    h1,
    h2,
    h3,
    p {
      margin: 0;
    }

    h1 {
      font-size: 17px;
      line-height: 1.2;
    }

    .subtitle {
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
    }

    .userbar {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }

    .identity {
      text-align: right;
      min-width: 0;
    }

    .identity strong {
      display: block;
      font-size: 13px;
      overflow-wrap: anywhere;
    }

    .identity span {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }

    .ghost-button,
    .primary-button,
    .scenario-card,
    .case-button {
      border: 1px solid var(--line);
      border-radius: 10px;
      cursor: pointer;
    }

    .ghost-button {
      min-height: 36px;
      padding: 7px 11px;
      background: var(--surface);
      color: var(--ink);
      font-weight: 750;
    }

    .primary-button {
      min-height: 42px;
      padding: 9px 16px;
      background: var(--ink);
      border-color: var(--ink);
      color: #ffffff;
      font-weight: 850;
    }

    .primary-button:hover,
    .ghost-button:hover,
    .scenario-card:hover,
    .case-button:hover,
    .scenario-card.active,
    .case-button.active {
      border-color: var(--line-strong);
      background: #f3f1ea;
    }

    .primary-button:hover {
      background: #2a2d29;
    }

    .workspace {
      min-height: 0;
      display: grid;
      grid-template-columns: minmax(270px, 330px) minmax(420px, 1fr) minmax(310px, 390px);
    }

    .sidebar,
    .main,
    .inspector {
      min-width: 0;
      padding: 18px;
      overflow: auto;
    }

    .sidebar {
      border-right: 1px solid var(--line);
      background: var(--surface-soft);
    }

    .main {
      background: var(--surface);
      border-right: 1px solid var(--line);
    }

    .inspector {
      background: var(--surface-soft);
    }

    .art-strip {
      min-height: 132px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background:
        linear-gradient(90deg, rgba(14, 19, 16, 0.34), rgba(14, 19, 16, 0.04)),
        url("/static/agent-oil-hero.png") center / cover no-repeat;
      box-shadow: var(--shadow);
      margin-bottom: 18px;
    }

    .section-title {
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 850;
      text-transform: uppercase;
    }

    .scenario-list,
    .case-list {
      display: grid;
      gap: 8px;
    }

    .scenario-card,
    .case-button {
      width: 100%;
      min-height: 48px;
      padding: 10px 11px;
      background: var(--surface);
      color: var(--ink);
      text-align: left;
    }

    .scenario-card:disabled {
      cursor: default;
      color: var(--muted);
      background: #eeede7;
    }

    .scenario-card:disabled:hover {
      border-color: var(--line);
      background: #eeede7;
    }

    .row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 9px;
    }

    .meta,
    .case-kicker {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }

    .title {
      margin-top: 4px;
      font-size: 14px;
      font-weight: 820;
      overflow-wrap: anywhere;
    }

    .badge {
      flex: 0 0 auto;
      padding: 3px 7px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--surface);
      color: var(--muted);
      font-size: 11px;
    }

    .badge.runnable {
      border-color: rgba(15, 118, 110, 0.28);
      background: var(--teal-soft);
      color: var(--teal);
    }

    .badge.not_connected {
      border-color: rgba(154, 106, 34, 0.28);
      background: var(--gold-soft);
      color: var(--gold);
    }

    .composer,
    .result-panel,
    .metric,
    .concept,
    .raw-json,
    .tag {
      border: 1px solid var(--line);
      border-radius: 12px;
    }

    .composer {
      padding: 14px;
      background: var(--surface-soft);
    }

    .composer-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 11px;
    }

    .composer h2,
    .result-panel h2 {
      font-size: 17px;
    }

    .identity-pill {
      border: 1px solid rgba(15, 118, 110, 0.24);
      border-radius: 999px;
      background: var(--teal-soft);
      color: var(--teal-dark);
      padding: 5px 9px;
      font-size: 12px;
      font-weight: 800;
      white-space: nowrap;
    }

    textarea {
      width: 100%;
      min-height: 112px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 12px;
      background: #ffffff;
      color: var(--ink);
      line-height: 1.52;
      outline: none;
    }

    textarea:focus {
      border-color: var(--teal);
      box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.12);
    }

    .composer-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-top: 10px;
    }

    .status {
      color: var(--muted);
      font-size: 12px;
      min-height: 18px;
      overflow-wrap: anywhere;
    }

    .status.error {
      color: var(--red);
      font-weight: 800;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 16px 0;
    }

    .metric {
      min-height: 78px;
      padding: 10px;
      background: var(--surface-soft);
    }

    .metric-label {
      color: var(--muted);
      font-size: 12px;
    }

    .metric-value {
      margin-top: 7px;
      font-size: 15px;
      font-weight: 850;
      overflow-wrap: anywhere;
    }

    .result-panel {
      margin-top: 16px;
      padding: 14px;
      background: #f8faf7;
    }

    .response {
      margin-top: 11px;
      padding: 14px;
      border-left: 3px solid var(--teal);
      background: #ffffff;
      line-height: 1.62;
      overflow-wrap: anywhere;
    }

    .concept-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 16px;
    }

    .concept {
      min-height: 104px;
      padding: 12px;
      background: var(--surface);
    }

    .concept h3 {
      font-size: 13px;
      margin-bottom: 8px;
    }

    .concept p {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.48;
      overflow-wrap: anywhere;
    }

    .node-path,
    .raw-json {
      background: var(--code);
      color: #ecf0e8;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.58;
      overflow-wrap: anywhere;
    }

    .node-path {
      margin-top: 11px;
      border-radius: 12px;
      padding: 12px;
    }

    .list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 17px;
    }

    .tag {
      max-width: 100%;
      padding: 6px 8px;
      background: var(--surface);
      color: var(--code);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      overflow-wrap: anywhere;
    }

    .tag.evidence {
      border-color: rgba(47, 125, 85, 0.24);
      background: #eef8f1;
      color: var(--green);
    }

    .tag.gate {
      border-color: rgba(154, 106, 34, 0.28);
      background: var(--gold-soft);
      color: var(--gold);
    }

    .raw-json {
      width: 100%;
      min-height: 330px;
      margin: 0;
      padding: 12px;
      white-space: pre-wrap;
      overflow: auto;
    }

    .spacer {
      height: 18px;
    }

    @media (max-width: 1180px) {
      .workspace {
        grid-template-columns: 1fr;
      }

      .sidebar,
      .main,
      .inspector {
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }

      .summary-grid,
      .concept-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 680px) {
      .topbar {
        height: auto;
        min-height: 68px;
        align-items: flex-start;
        flex-direction: column;
        padding: 14px 16px;
      }

      .userbar {
        width: 100%;
        justify-content: space-between;
      }

      .identity {
        text-align: left;
      }

      .sidebar,
      .main,
      .inspector {
        padding: 14px;
      }

      .summary-grid,
      .concept-grid {
        grid-template-columns: 1fr;
      }

      .composer-head,
      .composer-actions {
        align-items: stretch;
        flex-direction: column;
      }

      .primary-button {
        width: 100%;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="topbar">
      <div class="brand">
        <div class="mark" aria-hidden="true">EA</div>
        <div>
          <h1>企业办公 Agent 工作台</h1>
          <div class="subtitle">LangGraph · Tool/API/RAG · Trace/Evidence</div>
        </div>
      </div>
      <div class="userbar">
        <div class="identity">
          <strong id="userName">Demo User</strong>
          <span id="userMeta">EMP</span>
        </div>
        <button id="logoutButton" class="ghost-button" type="button">退出</button>
      </div>
    </header>

    <main class="workspace">
      <aside class="sidebar">
        <div class="art-strip" aria-hidden="true"></div>

        <h2 class="section-title">系统运行入口</h2>
        <div id="scenarioList" class="scenario-list"></div>

        <div class="spacer"></div>
        <h2 class="section-title">精选演示</h2>
        <div id="caseList" class="case-list"></div>
        <button id="refreshButton" class="ghost-button" type="button" style="width:100%;margin-top:12px;">刷新</button>
      </aside>

      <section class="main" aria-live="polite">
        <div class="composer">
          <div class="composer-head">
            <h2>Agent 对话入口</h2>
            <div id="identityPill" class="identity-pill">__DEFAULT_EMPLOYEE_ID__</div>
          </div>
          <form id="agentForm">
            <textarea id="agentMessage" name="message"></textarea>
            <div class="composer-actions">
              <div id="status" class="status">正在加载运行目录</div>
              <button id="askButton" class="primary-button" type="submit">发送</button>
            </div>
          </form>
        </div>

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

        <div class="result-panel">
          <h2 id="title">状态 State</h2>
          <div id="capability" class="subtitle"></div>
          <div id="displayResponse" class="response">正在加载。</div>
        </div>

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

      <aside class="inspector">
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
    const currentUser = __CURRENT_USER__;
    const defaultPrompt = __DEFAULT_PROMPT__;
    const statusLabels = {
      runnable: '可运行',
      not_connected: '未接入运行',
    };
    let cases = [];
    let scenarioCatalog = [];
    let selectedCaseId = null;

    const elements = {
      userName: document.getElementById('userName'),
      userMeta: document.getElementById('userMeta'),
      identityPill: document.getElementById('identityPill'),
      logoutButton: document.getElementById('logoutButton'),
      status: document.getElementById('status'),
      agentForm: document.getElementById('agentForm'),
      agentMessage: document.getElementById('agentMessage'),
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
      elements.status.classList.toggle('error', isError);
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
      renderScenarioCatalog();
    }

    function renderCaseButtons() {
      elements.caseList.innerHTML = '';
      for (const item of cases) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `case-button ${item.case_id === selectedCaseId ? 'active' : ''}`;
        button.innerHTML = `<div class="case-kicker">${item.case_id}</div><div class="title">${item.title}</div>`;
        button.addEventListener('click', () => renderSummary(item));
        elements.caseList.appendChild(button);
      }
    }

    function renderScenarioCatalog() {
      elements.scenarioList.innerHTML = '';
      for (const item of scenarioCatalog) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `scenario-card ${item.scenario_id === selectedCaseId ? 'active' : ''}`;
        button.disabled = item.status !== 'runnable';
        button.innerHTML = `
          <div class="row">
            <span class="meta">${item.scenario_id} · ${item.request_type} · ${item.risk_level}</span>
            <span class="badge ${item.status}">${statusLabels[item.status] || item.status}</span>
          </div>
          <div class="title">${item.title}</div>
          <div class="meta">${item.description}</div>
        `;
        if (item.status === 'runnable') {
          button.addEventListener('click', () => runScenario(item.scenario_id, item));
        }
        elements.scenarioList.appendChild(button);
      }
    }

    async function runAgentQuery(event) {
      event.preventDefault();
      const message = elements.agentMessage.value.trim();
      if (!message) {
        setStatus('请输入问题', true);
        return;
      }
      setStatus('正在运行 Agent');
      try {
        const response = await fetch('/agent/query', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({message}),
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error ? payload.error.message : `POST /agent/query failed with ${response.status}`);
        }
        renderSummary({
          ...payload.summary,
          title: 'Agent 对话入口',
          capability: `输入：${payload.message}`,
        });
        setStatus('Agent 已完成');
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function loadScenarioCatalog() {
      try {
        const response = await fetch('/scenarios');
        if (!response.ok) {
          throw new Error(`GET /scenarios failed with ${response.status}`);
        }
        const payload = await response.json();
        scenarioCatalog = payload.scenarios || [];
        renderScenarioCatalog();
        setStatus(`已加载 ${payload.total_count} 个场景，${payload.runnable_count} 个可运行`);
      } catch (error) {
        setStatus(error.message, true);
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
        }
      } catch (error) {
        setStatus(error.message, true);
        elements.displayResponse.textContent = '无法加载 /demo。';
      }
    }

    async function runScenario(scenarioId, catalogItem) {
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
          title: `${scenarioId} ${catalogItem.title}`,
          capability: catalogItem.description,
        });
        setStatus(`场景 ${scenarioId} 已完成`);
      } catch (error) {
        setStatus(error.message, true);
      }
    }

    async function logout() {
      await fetch('/auth/logout', {method: 'POST'});
      window.location.href = '/login';
    }

    elements.userName.textContent = currentUser.display_name;
    elements.userMeta.textContent = `${currentUser.employee_id} · ${currentUser.role_label}`;
    elements.identityPill.textContent = currentUser.employee_id;
    elements.agentMessage.value = defaultPrompt;
    elements.logoutButton.addEventListener('click', logout);
    elements.agentForm.addEventListener('submit', runAgentQuery);
    elements.refreshButton.addEventListener('click', loadDemo);
    loadScenarioCatalog();
    loadDemo();
  </script>
</body>
</html>
""".replace("__CURRENT_USER__", user_json).replace(
        "__DEFAULT_PROMPT__", default_prompt_json
    ).replace("__DEFAULT_EMPLOYEE_ID__", default_employee_id)
