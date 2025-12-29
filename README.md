# 🛡️ SentinelOps: Vision-to-Action Pipeline

**Powered by Google Gemini (Vertex AI) + Datadog Observability**

*Transforming video streams into intelligent operational decisions*

---

## 🎯 Executive Summary

**SentinelOps** is an AI operations system that transforms video footage into real-time operational decisions and actions. It showcases the powerful synergy between **Gemini's intelligence** and **Datadog's operational excellence**.

### Why SentinelOps Stands Out

- **🧠 Gemini Expertise**: Three specialized AI agents (Observer, Thinker, Doer) demonstrate advanced video understanding, policy-aware reasoning, and structured decision-making
- **📊 Datadog Excellence**: Complete observability stack with traces, metrics, LLM monitoring, SLOs, automated incident response, and case management
- **🎮 GameDay Ready**: Built-in fault injection scenarios demonstrate system resilience with real operational telemetry
- **🔧 Thoughtfully Built**: Every component is instrumented, measured, and monitored to show how AI systems can be operated reliably

---

## 🏗️ Architecture: Intelligence Meets Reliability

### The Core Philosophy

> **Gemini provides the intelligence. Datadog provides the trust.**

SentinelOps operates as a multi-stage pipeline where each stage is independently monitored, traced, and subject to SLO enforcement:

```
Video Feed → Producer → Observer → Thinker → Doer → Actions
              ↓          ↓         ↓        ↓       ↓
           Datadog    Datadog   Datadog  Datadog  Datadog
           Traces     LLMObs    Metrics   SLOs   Incidents
```

---

## 🤖 Gemini-Powered Intelligence Layer

### 1. **Observer Agent** (Video Understanding)

**Input**: MP4 video clip bytes  
**Model**: Gemini 2.5 Flash (video-native multimodal)  
**Output**: Strict JSON observation schema

```json
{
  "summary": "Worker approaching machinery with panel open",
  "signals": {
    "people_present": true,
    "machine_operating": true,
    "panel_open": true,
    "unsafe_proximity": true,
    "guard_open": false,
    "restricted_area_entry": false,
    "walkway_violation": false
  }
}
```

**Why This Matters**: 
- Gemini's video understanding extracts structured operational signals from raw footage
- Conservative inference: outputs "uncertain" rather than guessing when evidence is unclear
- Demonstrates multimodal AI capabilities beyond simple image classification

### 2. **Thinker Agent** (Policy-Aware Reasoning)

**Input**: Observation + SOP policy citations  
**Model**: Gemini 2.5 Pro (reasoning with grounding)  
**Output**: Risk-assessed decision with citations

```json
{
  "violation_detected": true,
  "rule_id": "SAFE-002",
  "severity": "HIGH",
  "confidence": 0.92,
  "risk_level": "CRITICAL",
  "recommended_actions": ["stop_line"],
  "rationale": "Machine operating with panel open violates SOP SAFE-002...",
  "citations": ["safety_protocols.md#electrical-panels"],
  "evidence": {"clip_id": "clip_001", "timestamp_range": [0.5, 1.8]}
}
```

**Why This Matters**:
- Demonstrates Gemini's reasoning capabilities with policy grounding
- Tool integration (SOP lookup) shows practical RAG patterns
- Risk assessment and confidence scoring show thoughtful AI decision-making
- Automatic degradation to lower-severity actions when policy grounding is weak

### 3. **Doer Agent** (Action Enrichment)

**Input**: Decision + recommended action  
**Model**: Gemini 2.5 Pro (efficient for structured output)  
**Output**: Operator-ready instructions

```json
{
  "action_type": "stop_line",
  "operator_message": "EMERGENCY STOP: Electrical panel open during operation",
  "execution_steps": [
    "Activate emergency stop on Line 3",
    "Dispatch safety officer to Panel B",
    "Verify machine state before restart"
  ],
  "priority": "P0",
  "notes": "Supervisor notification required per SOP SAFE-002"
}
```

**Why This Matters**:
- Shows Gemini's ability to generate actionable, context-aware outputs
- Maintains action consistency while adding operational detail
- Demonstrates practical AI augmentation of human workflows

---

## 📊 Datadog: Operational Excellence at Scale

### Full-Stack Observability

#### 1. **Distributed Tracing**

Every pipeline stage generates instrumented spans with complete context propagation:

- `sentinel.stage.producer` → Video splitting and clip creation
- `sentinel.stage.observer` → Gemini video analysis
- `sentinel.stage.thinker` → Decision reasoning
- `sentinel.stage.doer` → Action enrichment and dispatch
- `sentinel.tool.dispatcher` → Action delivery

**Impact**: Trace any decision back to its source clip in milliseconds. Full causal chain visibility.

#### 2. **LLM Observability (LLMObs)**

Specialized tracking for all Gemini interactions:

- **Token Metrics**: Input/output tokens per agent, total pipeline token consumption
- **Cost Tracking**: Real-time USD estimates for each model call
- **Latency Distribution**: P50, P95, P99 for observer/thinker/doer agents
- **Parse Integrity**: Success rate for structured JSON outputs
- **Model Metadata**: Track which Gemini models are called, with what parameters

**Impact**: Complete visibility into AI system behavior—no black boxes. Cost and performance optimization built-in.

#### 3. **Metrics That Matter**

Production-grade metrics across the entire pipeline:

```
# Stage Performance
sentinel.stage.latency_ms (by stage, p95 tracked)
sentinel.e2e.decision_latency_ms

# SLO Compliance
sentinel.stage.timeout (SLO breach counter)

# Reliability
sentinel.tool.calls
sentinel.tool.error
sentinel.action.sent / failed / skipped

# LLM Health
sentinel.llm.calls
sentinel.llm.parse_ok / parse_fail
sentinel.llm.tokens.total
sentinel.llm.cost.usd

# System Health
sentinel.pipeline.queue_depth
sentinel.degradation.low_grounding
```

**Impact**: Real-time operational dashboards. Proactive issue detection.

#### 4. **SLO Enforcement with Watchdog**

Each pipeline stage has configurable SLO timers:

- Observer: 8 seconds max
- Thinker: 6 seconds max  
- Doer: 5 seconds max
- E2E pipeline: 20 seconds max

When breached:
1. ⏰ `stage_timeout` audit event emitted
2. 📊 Datadog metric incremented
3. 🚨 Datadog event created
4. 📧 Monitor alerts fire

**Impact**: Proactive latency management. No silent degradation.

#### 5. **Automated Incident Response**

When critical failures occur (dispatcher outage, E2E latency breach):

1. 🔴 **Datadog Incident Created** (SEV-2/SEV-3)
2. 📋 **Datadog Case Created** (HIGH priority)
3. 🔔 **On-call engineers notified**
4. 📝 **Audit log updated**
5. 📊 **Dashboard reflects incident state**

**Impact**: Zero-touch incident management. Full integration with Datadog's incident lifecycle.

---

## 🎮 GameDay: Proving Resilience

Built-in fault injection scenarios demonstrate real operational behavior:

### Scenario 1: `dispatcher_outage`

**What Happens**:
- Forces dispatcher tool to fail
- Creates `tool_error` audit events
- Automatically triggers Datadog SEV-2 incident
- Creates Datadog case for investigation
- Action marked as failed with fallback message

**Why It Matters**: Demonstrates automated incident response pipeline and how AI system failures can be caught, tracked, and escalated.

### Scenario 2: `long_running_observer`

**What Happens**:
- Observer agent intentionally exceeds SLO
- Watchdog detects breach and emits `stage_timeout`
- P95 latency metrics spike
- SLO monitors fire
- Dashboard reflects degraded performance

**Why It Matters**: Demonstrates SLO enforcement and performance monitoring. Shows how the system self-diagnoses slowdowns.

### Scenario 3: `injection`

**What Happens**:
- Simulates prompt injection attack
- Security detector blocks malicious input
- Generates `security` audit events
- Security monitors trigger alerts

**Why It Matters**: Demonstrates built-in AI system protections and defense against adversarial inputs.

---

## 🖥️ Live Operational UI

### Real-Time Monitoring Dashboard

The SentinelOps UI provides enterprise-grade operational visibility:

#### **Health KPIs**
- Decision latency (P95)
- Action success rate
- LLM integrity rate (parse success)
- Tool failure count
- Total tokens consumed
- Estimated cost (USD)

#### **Operational Signals Panel**
Real-time feed of critical events:
- ⏰ SLO breaches
- ❌ Tool failures
- 🔒 Security blocks
- 🚨 LLM parse failures
- ⚠️ Degraded mode triggers

#### **Pipeline Feed**
Live stream of all events:
- Observations (what Gemini saw)
- Decisions (what policy triggered)
- Actions (what was executed)

#### **Audit-Grounded Chat**
Ask questions answered from audit log only:
- "Why did we trigger Stop Line?"
- "Which clip caused the alert?"
- "Show me all HIGH severity decisions"


---

## 🚀 Quick Start Guide

### Prerequisites

- Python 3.10+
- `ffmpeg` installed
- Google Cloud project with Vertex AI enabled
- Datadog Agent running locally
- Datadog API keys (API key + App key)

### Setup

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Verify ffmpeg
ffmpeg -version

# 3. Configure environment variables
cat > .env << EOF
# Gemini / Vertex AI
USE_GEMINI=true
GCP_PROJECT=your_project_id
GCP_REGION=us-central1
GEMINI_OBSERVER_MODEL=gemini-1.5-pro
GEMINI_THINKER_MODEL=gemini-1.5-pro

# Datadog
DD_ENABLED=true
DD_API_KEY=your_api_key
DD_APP_KEY=your_app_key
DD_SITE=datadoghq.com
DD_SERVICE=sentinelops
DD_ENV=dev
DD_VERSION=0.1.0
DD_LLMOBS_ENABLED=true

# Pipeline
SECURITY_VIDEO_PATH=data/videos/security.mp4
CLIP_SECONDS=2
SAMPLE_FPS=6
EOF

# 4. Run the system
./scripts/run_demo_local.sh
```

### Access the UI

Open your browser to: `http://127.0.0.1:8000/ui`

---

## 🎬 Recommended Demo Flow (Hackathon Judges)

### Phase 1: Baseline Operation (3 minutes)

1. **Start the stream** in UI
2. **Show live pipeline feed**: Observation → Decision → Action
3. **Highlight decision detail**: confidence scores, risk levels, citations
4. **Open Datadog APM**: Show distributed traces across all stages
5. **Open LLMObs**: Show token usage, cost, and latency by agent

### Phase 2: Datadog Dashboards (2 minutes)

1. **Navigate to SentinelOps Dashboard** in Datadog
2. **Highlight key metrics**:
   - Decision latency P95
   - Action success rate
   - LLM parse integrity
   - Real-time token consumption
3. **Show SLO tracking**: Current compliance vs. target

### Phase 3: GameDay Chaos (4 minutes)

1. **Run Scenario**: `dispatcher_outage`
   - Show tool failure in UI
   - Navigate to **Datadog Incidents**
   - Show auto-created SEV-2 incident
   - Show associated Datadog case
   - Show monitor alert firing

2. **Reset and run**: `long_running_observer`
   - Show SLO breach in UI
   - Show P95 latency spike in Datadog
   - Show stage timeout events in trace

3. **Explain**: This proves the system is production-ready with automated incident response

### Phase 4: The Key Insight (1 minute)

**Highlight what makes this valuable**:

> "SentinelOps demonstrates how Gemini and Datadog work together: Gemini brings multimodal intelligence and structured reasoning, while Datadog provides complete visibility into how that AI system behaves. Every decision is traceable. Every failure creates an incident. This is a framework for building AI systems you can trust and operate."

---

## 📦 Included Datadog Assets

### Ready to Import

All Datadog configuration is included in this repository:

#### **Dashboard**
- `datadog/dashboards/sentinelops_gameday_dashboard.json`
- Visualizes: KPIs, latency, errors, SLO compliance, LLM metrics

#### **Monitors** (9 total)
- Decision latency P95 threshold
- Stage timeout alerts
- Tool error rate
- Dispatcher failure detection
- Prompt injection blocks
- LLM parse failure rate
- Queue depth warning
- E2E latency breach

#### **SLO**
- `datadog/slos/action_delivery_slo.json`
- Target: 99.5% of actions delivered within SLO

**Import with one command**:
```bash
# Dashboard
datadog dashboard import datadog/dashboards/sentinelops_gameday_dashboard.json

# Monitors
for monitor in datadog/monitors/*.json; do
  datadog monitor import "$monitor"
done

# SLO
datadog slo import datadog/slos/action_delivery_slo.json
```

---

## 🏆 What Makes SentinelOps Interesting

### Technical Depth

✅ **Real Gemini Usage**: Actual video understanding, reasoning, and structured generation across multiple agents  
✅ **Complete Datadog Integration**: Traces, metrics, logs, LLMObs, incidents, cases, SLOs working together  
✅ **Thoughtful Patterns**: Error handling, fallbacks, audit logs, deliberate design choices  
✅ **Fault Injection**: Built-in chaos engineering to demonstrate resilience  

### Innovation

✅ **Multi-Agent Pipeline**: Three specialized Gemini agents working in concert  
✅ **Policy Grounding**: RAG pattern with SOP lookup and citation tracking  
✅ **Automated Degradation**: System intelligently downgrades actions when confidence is low  
✅ **Audit-Grounded Chat**: LLM answers questions from structured logs, not hallucinations  

### Demonstration Value

✅ **Live Processing**: Real video processing, real decisions, real actions  
✅ **Clear Visibility**: Operational dashboard with health metrics and live feeds  
✅ **Datadog Showcase**: Seamlessly demonstrate value in external platform  
✅ **GameDay Scenarios**: Create real incidents on-demand during demonstration  

### Practical Applications

✅ **Versatile Use Cases**: Industrial monitoring, facility management, process automation, compliance tracking  
✅ **Thoughtful Architecture**: Built to show how AI systems can be instrumented and operated  
✅ **Observable AI**: Cost tracking, performance optimization, incident management for AI workloads  

---

## 🔧 Troubleshooting

<details>
<summary><b>ffmpeg not found</b></summary>

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Verify
ffmpeg -version
```
</details>

<details>
<summary><b>No clips being produced</b></summary>

1. Verify video file exists: `ls -lh data/videos/security.mp4`
2. Check file permissions: `chmod 644 data/videos/security.mp4`
3. Verify ffmpeg can read it: `ffmpeg -i data/videos/security.mp4`
</details>

<details>
<summary><b>Datadog metrics not appearing</b></summary>

1. Confirm agent is running: `datadog-agent status`
2. Check DogStatsD port: `netstat -an | grep 8125`
3. Verify environment variables: `echo $DD_AGENT_HOST`
4. Check agent logs: `tail -f /var/log/datadog/agent.log`
</details>

<details>
<summary><b>Incidents not being created</b></summary>

1. Verify `DD_APP_KEY` is set (required for Datadog v2 APIs)
2. Check API key permissions in Datadog UI
3. Run smoke test: `python scripts/dd_create_incident_case_smoketest.py`
4. Check logs for API errors
</details>

<details>
<summary><b>Gemini not working</b></summary>

1. Verify `USE_GEMINI=true`
2. Check GCP authentication: `gcloud auth application-default login`
3. Verify project/region: `echo $GCP_PROJECT $GCP_REGION`
4. Check Vertex AI API is enabled in GCP Console
</details>

---

## 📄 License

MIT License - See LICENSE file for details

---

<div align="center">

**🛡️ SentinelOps: Where AI Intelligence Meets Operational Visibility**

*Gemini understands. Datadog illuminates. Better AI systems emerge.*

</div>