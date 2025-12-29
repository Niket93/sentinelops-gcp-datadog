# src/web/ui.py
def ui_html() -> str:
    return r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>SentinelOps • Vision-to-Action</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    :root { color-scheme: dark; }
    html, body { height: 100%; }
    .t-12 { font-size: 12px; line-height: 18px; }
    .t-14 { font-size: 14px; line-height: 20px; }
    .t-16 { font-size: 16px; line-height: 24px; }
    .t-18 { font-size: 18px; line-height: 26px; }
    .t-22 { font-size: 22px; line-height: 30px; }
    .t-26 { font-size: 26px; line-height: 34px; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: translateY(0); } }
  </style>
</head>

<body class="min-h-screen bg-zinc-950 text-zinc-50 antialiased">
  <div class="fixed inset-0 -z-10">
    <div class="absolute inset-0 bg-[radial-gradient(900px_circle_at_20%_10%,rgba(16,185,129,0.14),transparent_45%),radial-gradient(900px_circle_at_80%_0%,rgba(99,102,241,0.10),transparent_40%),radial-gradient(900px_circle_at_50%_90%,rgba(244,63,94,0.08),transparent_45%)]"></div>
    <div class="absolute inset-0 opacity-20 bg-[linear-gradient(to_right,rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.04)_1px,transparent_1px)] bg-[size:72px_72px]"></div>
  </div>

  <div class="w-full max-w-none px-4 sm:px-6 lg:px-10 2xl:px-12 py-6">

    <!-- PROMINENT BANNER -->
    <div class="rounded-3xl border border-emerald-500/25 bg-emerald-500/5 backdrop-blur px-6 py-4 shadow-[0_0_0_1px_rgba(16,185,129,0.05)]">
      <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
        <div class="min-w-0">
          <div class="t-18 font-semibold text-emerald-100 tracking-tight">
            Powered by Vertex AI Intelligence + Datadog Observability
          </div>
          <div class="t-14 text-emerald-200/80 mt-1">
            End-to-end Vision → Reasoning → Action pipeline with Runtime Telemetry, Security Signals, SLOs, and Incident Readiness.
          </div>
        </div>
        <div class="shrink-0 inline-flex items-center gap-2 rounded-2xl bg-zinc-950/40 ring-1 ring-emerald-500/20 px-4 py-2">
          <span class="t-12 text-zinc-400">LLM App:</span>
          <span class="t-14 text-zinc-100 font-semibold">SentinelOps</span>
        </div>
      </div>
    </div>

    <!-- Header -->
    <header class="mt-6 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
      <div class="leading-tight min-w-0">
        <div class="t-26 font-semibold tracking-tight truncate">SentinelOps</div>
        <div class="t-16 text-zinc-300 truncate">Agentic Video Intelligence • Detect → Decide → Act • Audit-First Operations</div>
      </div>

      <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 shrink-0">

        <!-- Streaming status + controls -->
        <div class="flex items-center gap-3">
          <div class="inline-flex items-center gap-2 rounded-2xl bg-zinc-900/60 ring-1 ring-zinc-800 px-3 py-2">
            <span id="statusDot" class="h-2 w-2 rounded-full bg-rose-400"></span>
            <span id="statusText" class="t-16 text-zinc-200">Stopped</span>
          </div>

          <!-- Only show one of Start/Stop at a time -->
          <button id="btnStart" class="hidden rounded-2xl bg-emerald-500/15 px-4 py-2 t-16 ring-1 ring-emerald-500/25 hover:ring-emerald-500/60">
            ▶ Start
          </button>
          <button id="btnStop" class="hidden rounded-2xl bg-rose-500/15 px-4 py-2 t-16 ring-1 ring-rose-500/25 hover:ring-rose-500/60">
            ■ Stop
          </button>
        </div>

        <!-- GameDay controls -->
        <div class="flex items-center gap-2 rounded-2xl bg-zinc-900/60 ring-1 ring-zinc-800 px-3 py-2">
          <span class="t-14 text-zinc-400">GameDay</span>

          <select id="scenario" class="bg-zinc-950/40 ring-1 ring-zinc-800 rounded-xl px-3 py-2 t-14">
            <option value="none">none</option>
            <option value="dispatcher_outage">dispatcher_outage</option>
            <option value="long_running_observer">long_running_observer</option>
            <option value="injection">injection</option>
          </select>

          <button id="btnRun" class="rounded-2xl bg-violet-500/15 px-4 py-2 t-14 ring-1 ring-violet-500/25 hover:ring-violet-500/60">
            Run
          </button>

          <button id="btnReset" class="rounded-2xl bg-zinc-950/40 px-4 py-2 t-14 ring-1 ring-zinc-800 hover:ring-zinc-600">
            Reset
          </button>

          <div class="t-12 text-zinc-500 ml-2">
            Active: <span id="activeScenario" class="text-zinc-200">—</span>
          </div>
        </div>

      </div>
    </header>

    <!-- Health KPIs -->
    <section class="mt-5 rounded-3xl border border-zinc-800/70 bg-zinc-900/30 backdrop-blur overflow-hidden shadow-[0_0_0_1px_rgba(255,255,255,0.03)]">
      <div class="px-6 py-5">
        <div class="flex items-start justify-between gap-4">
          <div>
            <div class="t-18 font-semibold text-zinc-100">Application Health KPIs</div>
            <div class="t-14 text-zinc-400">Real-Time Pipeline Health • Performance • Integrity</div>
          </div>
          <button id="btnRefreshHealth" class="rounded-2xl bg-zinc-950/40 px-4 py-2 t-16 ring-1 ring-zinc-800 hover:ring-zinc-600">
            Refresh
          </button>
        </div>

        <div class="mt-4 grid grid-cols-1 md:grid-cols-6 gap-4">
          <div class="rounded-2xl bg-zinc-950/40 ring-1 ring-zinc-800/70 px-4 py-3">
            <div class="t-12 text-zinc-500">Decision p95 (ms)</div>
            <div class="t-22 text-sky-200 font-semibold" id="hDecP95">—</div>
          </div>

          <div class="rounded-2xl bg-zinc-950/40 ring-1 ring-zinc-800/70 px-4 py-3">
            <div class="t-12 text-zinc-500">Action Success Rate</div>
            <div class="t-22 text-emerald-200 font-semibold" id="hActRate">—</div>
          </div>

          <div class="rounded-2xl bg-zinc-950/40 ring-1 ring-zinc-800/70 px-4 py-3">
            <div class="t-12 text-zinc-500">LLM Integrity Rate</div>
            <div class="t-22 text-violet-200 font-semibold" id="hLlmRate">—</div>
          </div>

          <div class="rounded-2xl bg-zinc-950/40 ring-1 ring-zinc-800/70 px-4 py-3">
            <div class="t-12 text-zinc-500">Tool Failures</div>
            <div class="t-22 text-rose-200 font-semibold" id="hToolErr">—</div>
          </div>

          <div class="rounded-2xl bg-zinc-950/40 ring-1 ring-zinc-800/70 px-4 py-3">
            <div class="t-12 text-zinc-500">Tokens</div>
            <div class="t-22 text-zinc-100 font-semibold" id="hTokens">—</div>
          </div>

          <div class="rounded-2xl bg-zinc-950/40 ring-1 ring-zinc-800/70 px-4 py-3">
            <div class="t-12 text-zinc-500">Cost (USD)</div>
            <div class="t-22 text-zinc-100 font-semibold" id="hCost">—</div>
          </div>
        </div>

        <!-- Live log stream under KPIs -->
        <div class="mt-5 rounded-2xl bg-zinc-950/35 ring-1 ring-zinc-800/70 p-4">
          <div class="t-14 font-semibold text-zinc-100">Operational Signals</div>
          <div id="liveLogs" class="mt-3 h-[180px] overflow-auto space-y-2"></div>
        </div>

      </div>
    </section>

    <!-- Video -->
    <section class="mt-6 rounded-3xl border border-zinc-800/70 bg-zinc-900/30 backdrop-blur overflow-hidden shadow-[0_0_0_1px_rgba(255,255,255,0.03)]">
      <div class="px-6 py-5 flex items-center justify-between border-b border-zinc-800/70">
        <div class="min-w-0">
          <div class="t-14 text-zinc-400">Video</div>
          <div class="t-18 font-semibold text-zinc-100 mt-0.5 truncate">Security camera</div>
        </div>
        <div class="t-14 text-zinc-400 hidden sm:block">Clip → Observe → Decide → Act → Audit</div>
      </div>

      <div class="bg-black">
        <video id="video" class="w-full aspect-video" controls autoplay muted playsinline>
          <source src="/video" type="video/mp4" />
        </video>
      </div>

      <div class="px-6 py-5 border-t border-zinc-800/70 flex justify-center">
        <button id="btnReplay" class="rounded-2xl bg-zinc-950/40 px-5 py-3 t-16 ring-1 ring-zinc-800 hover:ring-zinc-600">
          Replay
        </button>
      </div>
    </section>

    <!-- 3 Panels -->
    <section class="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">

      <!-- Stream -->
      <div class="rounded-3xl border border-zinc-800/70 bg-zinc-900/30 backdrop-blur overflow-hidden shadow-[0_0_0_1px_rgba(255,255,255,0.03)] flex flex-col min-h-0">
        <div class="px-6 py-5 border-b border-zinc-800/70">
          <div class="t-14 text-zinc-400">Pipeline Feed</div>
          <div class="t-18 font-semibold text-zinc-100 mt-0.5">Observations • Decisions • Actions</div>
        </div>
        <div id="feed" class="p-5 space-y-4 h-[560px] overflow-auto"></div>
      </div>

      <!-- Decision Detail -->
      <div class="rounded-3xl border border-zinc-800/70 bg-zinc-900/30 backdrop-blur overflow-hidden shadow-[0_0_0_1px_rgba(255,255,255,0.03)] flex flex-col min-h-0">
        <div class="px-6 py-5 border-b border-zinc-800/70">
          <div class="t-14 text-zinc-400">Decision detail (LLM Reasoning)</div>
          <div class="t-18 font-semibold text-zinc-100 mt-0.5">Latest Decision Breakdown</div>
        </div>
        <div class="p-5 h-[560px] overflow-auto" id="thinkingPanel">
          <div class="rounded-2xl bg-zinc-950/40 ring-1 ring-zinc-800/70 p-5">
            <div class="t-16 text-zinc-200">No decision yet.</div>
            <div class="t-14 text-zinc-500 mt-2">When a decision arrives, it will appear here.</div>
          </div>
        </div>
      </div>

      <!-- Chat -->
      <div class="rounded-3xl border border-zinc-800/70 bg-zinc-900/30 backdrop-blur overflow-hidden shadow-[0_0_0_1px_rgba(255,255,255,0.03)] flex flex-col min-h-0">
        <div class="px-6 py-5 border-b border-zinc-800/70">
          <div class="t-14 text-zinc-400">Audit Chat</div>
          <div class="t-18 font-semibold text-zinc-100 mt-0.5">Ask Questions About Actions & Incidents...</div>
        </div>

        <div id="chatLog" class="p-5 space-y-4 h-[440px] overflow-auto"></div>

        <form id="chatForm" class="p-5 border-t border-zinc-800/70 flex gap-2">
          <input id="chatInput"
            class="flex-1 rounded-2xl bg-zinc-950/60 px-4 py-3 t-16 ring-1 ring-zinc-800 focus:outline-none focus:ring-emerald-500/55"
            placeholder="Ask: Why did we trigger Stop Line signal? Which clip shows it?"
          />
          <button class="rounded-2xl bg-emerald-500/15 px-5 py-3 t-16 font-medium text-emerald-200 ring-1 ring-emerald-500/25 hover:ring-emerald-500/60" type="submit">
            Send
          </button>
        </form>

        <div class="px-6 pb-5 t-14 text-zinc-500">
          Answers are grounded in the audit log (no hallucinations).
        </div>
      </div>

    </section>

  </div>

<script>
  let seen = new Set();
  let latestDecision = null;

  const feedEl = document.getElementById("feed");
  const thinkingPanel = document.getElementById("thinkingPanel");
  const liveLogs = document.getElementById("liveLogs");

  const btnStart = document.getElementById("btnStart");
  const btnStop = document.getElementById("btnStop");
  const btnReplay = document.getElementById("btnReplay");
  const btnRefreshHealth = document.getElementById("btnRefreshHealth");

  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");

  const scenarioSel = document.getElementById("scenario");
  const btnRun = document.getElementById("btnRun");
  const btnReset = document.getElementById("btnReset");
  const activeScenarioEl = document.getElementById("activeScenario");

  const videoEl = document.getElementById("video");

  function esc(s){ return (s||"").replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c])); }

  function pill(label, kind) {
    const base = "inline-flex items-center rounded-full px-2.5 py-1 t-12 ring-1 ";
    if (kind === "slo") return `<span class="${base} bg-rose-500/10 text-rose-200 ring-rose-500/20">${label}</span>`;
    if (kind === "tool") return `<span class="${base} bg-amber-500/10 text-amber-200 ring-amber-500/20">${label}</span>`;
    if (kind === "security") return `<span class="${base} bg-fuchsia-500/10 text-fuchsia-200 ring-fuchsia-500/20">${label}</span>`;
    if (kind === "llm") return `<span class="${base} bg-violet-500/10 text-violet-200 ring-violet-500/20">${label}</span>`;
    if (kind === "degrade") return `<span class="${base} bg-sky-500/10 text-sky-200 ring-sky-500/20">${label}</span>`;
    return `<span class="${base} bg-zinc-500/10 text-zinc-200 ring-zinc-500/20">${label}</span>`;
  }

  function describe(ev){
    const p = ev.payload || {};
    if (ev.kind === "observation") return p.summary || "Observation";
    if (ev.kind === "decision") {
      const a0 = (p.recommended_actions||[])[0] || {};
      return a0.message || (p.assessment?.rule_id || "Decision");
    }
    if (ev.kind === "action") return (p.action?.message || p.action?.type || "Action");
    if (ev.kind === "tool_error") return `Tool failure: ${(p.tool_name||"tool")} • ${(p.error_type||"")} • ${(p.error||"")}`;
    if (ev.kind === "stage_timeout") return `SLO breach: ${(p.stage||"stage")} • ${p.elapsed_ms||""}ms (SLO ${p.slo_ms||""}ms)`;
    if (ev.kind === "security") return `Security blocked: ${(p.event||"blocked")} • ${(p.reason||"")}`;
    if (ev.kind === "health") {
      const e = p.event || "";
      if (e === "llm_call" && p.parse_ok === false) return `LLM parse failure • agent ${p.agent || ""} • model ${p.model || ""}`;
      if (e === "degradation") return `Degraded mode • ${p.reason || "unknown"} • rule ${p.rule_id || ""}`;
    }
    return ev.kind;
  }

  function isOperationalSignal(ev){
    const p = ev.payload || {};
    if (ev.kind === "stage_timeout") return true;
    if (ev.kind === "tool_error") return true;
    if (ev.kind === "security") return true;
    if (ev.kind === "health" && p.event === "llm_call" && p.parse_ok === false) return true;
    if (ev.kind === "health" && p.event === "degradation") return true;
    return false;
  }

  function operationalPill(ev){
    const p = ev.payload || {};
    if (ev.kind === "stage_timeout") return pill("SLO BREACH", "slo");
    if (ev.kind === "tool_error") return pill("TOOL FAILURE", "tool");
    if (ev.kind === "security") return pill("SECURITY BLOCK", "security");
    if (ev.kind === "health" && p.event === "llm_call" && p.parse_ok === false) return pill("LLM PARSE FAIL", "llm");
    if (ev.kind === "health" && p.event === "degradation") return pill("DEGRADED", "degrade");
    return pill("SIGNAL", "other");
  }

  async function refreshStatus(){
    try{
      const r = await fetch("/stream/status");
      const s = await r.json();
      const running = !!s.running;
      statusDot.className = "h-2 w-2 rounded-full " + (running ? "bg-emerald-400" : "bg-rose-400");
      statusText.textContent = running ? "Streaming" : "Stopped";

      btnStart.classList.toggle("hidden", running);
      btnStop.classList.toggle("hidden", !running);
    }catch(e){}
  }

  async function refreshGameDay(){
    try{
      const r = await fetch("/gameday");
      const g = await r.json();
      activeScenarioEl.textContent = g.scenario || "none";
      if (g.scenario) scenarioSel.value = g.scenario;
    }catch(e){}
  }

  async function refreshHealth(){
    try{
      const r = await fetch("/healthz");
      const h = await r.json();
      document.getElementById("hDecP95").textContent = (h.slo?.decision_latency_p95_ms ?? "—");
      document.getElementById("hActRate").textContent = String(h.slo?.action_success_rate ?? "—");
      document.getElementById("hLlmRate").textContent = String(h.slo?.llm_integrity_rate ?? "—");
      document.getElementById("hToolErr").textContent = String(h.totals?.tool_errors ?? 0);
      document.getElementById("hTokens").textContent = String(h.totals?.tokens ?? 0);
      document.getElementById("hCost").textContent = (h.totals?.cost_usd ?? 0).toFixed ? (h.totals.cost_usd).toFixed(4) : String(h.totals?.cost_usd ?? 0);
    }catch(e){}
  }

  function pushLiveLog(ev){
    if (!isOperationalSignal(ev)) return;

    const html = `
      <div class="rounded-xl bg-zinc-950/45 ring-1 ring-zinc-800/70 p-3">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="t-14 font-semibold text-zinc-100">${esc(describe(ev))}</div>
            <div class="t-12 text-zinc-500 mt-1">${esc(ev.ts)} • trace ${(ev.trace_id||"").slice(0,8)}</div>
          </div>
          <div class="shrink-0">${operationalPill(ev)}</div>
        </div>
      </div>
    `;
    liveLogs.insertAdjacentHTML("afterbegin", html);

    while (liveLogs.children.length > 12) {
      liveLogs.removeChild(liveLogs.lastChild);
    }
  }

  function renderDecisionPanel(ev){
    if (!ev) return;
    const p = ev.payload || {};
    const a = p.assessment || {};
    const actions = Array.isArray(p.recommended_actions) ? p.recommended_actions : [];
    const a0 = actions[0] || {};

    thinkingPanel.innerHTML = `
      <div class="rounded-2xl bg-zinc-950/45 ring-1 ring-zinc-800/70 p-5">
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="t-18 font-semibold text-zinc-100">Decision</div>
            <div class="t-14 text-zinc-500 mt-1">${esc(ev.ts)} • trace ${(ev.trace_id||"").slice(0,8)}</div>
          </div>
          <div class="shrink-0">${pill("DECISION", "llm")}</div>
        </div>

        <div class="mt-4 space-y-4">
          <div class="rounded-xl bg-zinc-950/35 ring-1 ring-zinc-800/70 p-4">
            <div class="t-14 text-zinc-400">Recommended action</div>
            <div class="mt-1 t-18 font-semibold text-zinc-100">${esc(a0.type || "unknown")} • ${esc(a0.priority || "")}</div>
            <div class="mt-1 t-16 text-zinc-200">${esc(a0.message || "-")}</div>
          </div>

          <div class="rounded-xl bg-zinc-950/35 ring-1 ring-zinc-800/70 p-4 space-y-2">
            <div class="t-14 text-zinc-400">Assessment</div>
            <div class="t-14 text-zinc-200">rule_id: <span class="text-zinc-100 font-semibold">${esc(a.rule_id || "-")}</span></div>
            <div class="t-14 text-zinc-200">severity: <span class="text-zinc-100 font-semibold">${esc(a.severity || "-")}</span></div>
            <div class="t-14 text-zinc-200">confidence: <span class="text-zinc-100 font-semibold">${esc(String(a.confidence ?? "-"))}</span></div>
            <div class="t-14 text-zinc-200">risk: <span class="text-zinc-100 font-semibold">${esc(a.risk || "-")}</span></div>
          </div>

          <div class="rounded-xl bg-zinc-950/35 ring-1 ring-zinc-800/70 p-4">
            <div class="t-14 text-zinc-400">Rationale</div>
            <div class="mt-1 t-16 text-zinc-200">${esc(p.rationale?.short || "-")}</div>
          </div>
        </div>
      </div>
    `;
  }

  async function poll(){
    try{
      const r = await fetch("/recent?limit=320");
      const items = await r.json();

      items.reverse().forEach(ev=>{
        if(seen.has(ev.audit_id)) return;

        const showInFeed = ["observation","decision","action"].includes(ev.kind);

        if(showInFeed){
          const html = `
            <div class="rounded-2xl bg-zinc-950/45 ring-1 ring-zinc-800/70 p-4">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="t-16 font-semibold text-zinc-100">${esc(ev.kind)}</div>
                  <div class="t-12 text-zinc-500 mt-1">${esc(ev.ts)} • trace ${(ev.trace_id||"").slice(0,8)}</div>
                </div>
                <div class="shrink-0">${pill(ev.kind.toUpperCase(), "other")}</div>
              </div>
              <div class="mt-2 t-16 text-zinc-200">${esc(describe(ev))}</div>
            </div>
          `;
          feedEl.insertAdjacentHTML("beforeend", html);
          feedEl.scrollTop = feedEl.scrollHeight;

          if (ev.kind === "decision") {
            latestDecision = ev;
            renderDecisionPanel(latestDecision);
          }
        }

        pushLiveLog(ev);

        seen.add(ev.audit_id);
      });
    }catch(e){}
  }

  btnStart.addEventListener("click", async ()=>{
    await fetch("/stream/start", {method:"POST"});
    refreshStatus();
  });

  btnStop.addEventListener("click", async ()=>{
    await fetch("/stream/stop", {method:"POST"});
    refreshStatus();
  });

  btnReplay.addEventListener("click", ()=>{
    videoEl.currentTime = 0;
    videoEl.play();
  });

  btnRefreshHealth.addEventListener("click", refreshHealth);

  btnRun.addEventListener("click", async ()=>{
    const scenario = scenarioSel.value;
    await fetch("/gameday/run", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({scenario})
    });
    refreshGameDay();
  });

  btnReset.addEventListener("click", async ()=>{
    await fetch("/gameday/reset", {method:"POST"});
    refreshGameDay();
  });

  const chatLog = document.getElementById("chatLog");
  const chatForm = document.getElementById("chatForm");
  const chatInput = document.getElementById("chatInput");

  function addChat(role, text){
    const align = role === "user" ? "justify-end" : "justify-start";
    const bubble = role === "user"
      ? "bg-emerald-500/15 ring-1 ring-emerald-500/25 text-emerald-50"
      : "bg-zinc-950/45 ring-1 ring-zinc-800/70 text-zinc-50";
    const label = role === "user" ? "You" : "SentinelOps";

    const html = `
      <div class="flex ${align}">
        <div class="max-w-[92%] rounded-3xl px-4 py-3 ${bubble}">
          <div class="t-12 text-zinc-400 mb-1">${label}</div>
          <div class="t-16 whitespace-pre-wrap">${esc(text)}</div>
        </div>
      </div>
    `;
    chatLog.insertAdjacentHTML("beforeend", html);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  chatForm.addEventListener("submit", async (e)=>{
    e.preventDefault();
    const q = (chatInput.value || "").trim();
    if(!q) return;
    chatInput.value = "";
    addChat("user", q);

    try{
      const resp = await fetch("/chat", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({question: q, limit: 200})
      });
      const data = await resp.json();
      addChat("assistant", data.answer || "(no answer)");
    }catch(err){
      addChat("assistant", "Chat failed. Check server logs.");
    }
  });

  refreshStatus();
  refreshGameDay();
  refreshHealth();
  poll();

  setInterval(poll, 1000);
  setInterval(refreshHealth, 2500);
  setInterval(refreshStatus, 1200);
  setInterval(refreshGameDay, 3000);
</script>

</body>
</html>
"""