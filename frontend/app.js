const state = {
  sessionId: localStorage.getItem("air_agent_session_id") || "",
  activeCaseId: localStorage.getItem("air_agent_case_id") || "case_01",
  cases: [],
};

const caseLabels = {
  case_01: "Case 01 自主感測",
  case_02: "Case 02 智慧監控",
  case_03: "案例 3 自動交班",
  case_06: "案例 3 自動交班",
};

const defaultPrompts = {
  case_01: "請分析自主感測資料，判斷多個感測訊號是否異常。",
  case_02: "請比較生產與非生產時段，判斷是否有夜間漏氣。",
  case_03: "請把重複異常整理成自動交班摘要。",
  case_06: "請把重複異常整理成自動交班摘要。",
};

const el = {
  healthText: document.querySelector("#healthText"),
  caseList: document.querySelector("#caseList"),
  activeCaseTitle: document.querySelector("#activeCaseTitle"),
  sessionText: document.querySelector("#sessionText"),
  messages: document.querySelector("#messages"),
  chatForm: document.querySelector("#chatForm"),
  messageInput: document.querySelector("#messageInput"),
  sendButton: document.querySelector("#sendButton"),
  clearSessionButton: document.querySelector("#clearSessionButton"),
  memoryForm: document.querySelector("#memoryForm"),
  memoryValue: document.querySelector("#memoryValue"),
  memoryList: document.querySelector("#memoryList"),
  toolCalls: document.querySelector("#toolCalls"),
  evidenceBox: document.querySelector("#evidenceBox"),
  nextActions: document.querySelector("#nextActions"),
};

function setSessionId(sessionId) {
  state.sessionId = sessionId;
  if (sessionId) {
    localStorage.setItem("air_agent_session_id", sessionId);
  } else {
    localStorage.removeItem("air_agent_session_id");
  }
  el.sessionText.textContent = sessionId ? sessionId : "尚未建立 session";
}

function setActiveCase(caseId) {
  state.activeCaseId = caseId;
  localStorage.setItem("air_agent_case_id", caseId);
  el.activeCaseTitle.textContent = caseLabels[caseId] || caseId;
  el.messageInput.placeholder = defaultPrompts[caseId] || "輸入問題";
  renderCases();
}

function appendMessage(role, text) {
  const node = document.createElement("div");
  node.className = `message ${role}`;
  node.textContent = text;
  el.messages.appendChild(node);
  el.messages.scrollTop = el.messages.scrollHeight;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}

function renderCases() {
  const displayCases = [
    { case_id: "case_01", title: "Autonomous sensing anomaly diagnosis" },
    { case_id: "case_02", title: "Smart monitoring and night leakage review" },
    { case_id: "case_03", title: "Auto logbook and shift handover" },
  ];
  el.caseList.innerHTML = "";
  displayCases.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `case-button ${state.activeCaseId === item.case_id ? "active" : ""}`;
    button.textContent = `${caseLabels[item.case_id] || item.case_id}\n${item.title}`;
    button.addEventListener("click", () => setActiveCase(item.case_id));
    el.caseList.appendChild(button);
  });
}

function renderMemory(items) {
  el.memoryList.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "目前無記憶";
    el.memoryList.appendChild(empty);
    return;
  }
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "memory-item";
    const text = document.createElement("span");
    text.textContent = item.value;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "刪除";
    button.addEventListener("click", async () => {
      await api(`/api/memory/${item.id}`, { method: "DELETE" });
      await loadMemory();
    });
    row.append(text, button);
    el.memoryList.appendChild(row);
  });
}

function renderToolCalls(toolCalls) {
  el.toolCalls.innerHTML = "";
  if (!toolCalls.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "尚無工具紀錄";
    el.toolCalls.appendChild(empty);
    return;
  }
  toolCalls.forEach((call) => {
    const node = document.createElement("div");
    node.className = "tool-call";
    node.textContent = call.name ? `${call.type}: ${call.name}` : call.type;
    el.toolCalls.appendChild(node);
  });
}

function renderEvidence(evidence, actions) {
  el.evidenceBox.textContent = JSON.stringify(evidence || {}, null, 2);
  el.nextActions.innerHTML = "";
  (actions || []).forEach((action) => {
    const li = document.createElement("li");
    li.textContent = action;
    el.nextActions.appendChild(li);
  });
}

async function loadHealth() {
  try {
    const health = await api("/api/health");
    const sqliteReady = health.sqlite?.ready ? "SQLite ready" : "SQLite not ready";
    const mcpReady = health.mcp?.ready ? "MCP ready" : "MCP not ready";
    el.healthText.textContent = `${sqliteReady}, ${mcpReady}`;
  } catch (error) {
    el.healthText.textContent = "health check failed";
  }
}

async function loadCases() {
  try {
    const payload = await api("/api/cases");
    state.cases = payload.cases || [];
  } catch (error) {
    state.cases = [];
  }
  renderCases();
}

async function loadMemory() {
  const payload = await api("/api/memory");
  renderMemory(payload.memory || []);
}

el.chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = el.messageInput.value.trim() || defaultPrompts[state.activeCaseId] || "";
  if (!message) return;

  el.messageInput.value = "";
  appendMessage("user", message);
  el.sendButton.disabled = true;
  el.sendButton.textContent = "處理中";
  try {
    const payload = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        session_id: state.sessionId || null,
        message,
        case_id: state.activeCaseId,
        use_memory: true,
      }),
    });
    setSessionId(payload.session_id);
    appendMessage("assistant", payload.answer);
    renderToolCalls(payload.tool_calls || []);
    renderEvidence(payload.evidence || {}, payload.suggested_next_actions || []);
  } catch (error) {
    appendMessage("error", error.message);
  } finally {
    el.sendButton.disabled = false;
    el.sendButton.textContent = "送出";
  }
});

el.memoryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = el.memoryValue.value.trim();
  if (!value) return;
  await api("/api/memory", {
    method: "POST",
    body: JSON.stringify({ scope: "user", key: "note", value }),
  });
  el.memoryValue.value = "";
  await loadMemory();
});

el.clearSessionButton.addEventListener("click", async () => {
  if (state.sessionId) {
    await api(`/api/sessions/${state.sessionId}`, { method: "DELETE" });
  }
  setSessionId("");
  el.messages.innerHTML = "";
  renderToolCalls([]);
  renderEvidence({}, []);
});

async function boot() {
  setSessionId(state.sessionId);
  setActiveCase(state.activeCaseId);
  renderToolCalls([]);
  renderEvidence({}, []);
  await Promise.all([loadHealth(), loadCases(), loadMemory()]);
}

boot();
