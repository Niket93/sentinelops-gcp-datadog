# src/web/api.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import hashlib

from ..config.settings import Settings
from ..bus.bus import Bus
from ..audit.buffer import AuditBuffer
from ..ingest.producer import ClipProducer
from ..gameday.controller import GameDayController
from ..runtime.state import RuntimeState
from ..tools.dispatcher import DispatcherTool
from ..shared.vertex import model_if_enabled
from ..web.ui import ui_html
from ..security.detectors import detect_injection, detect_hijack
from ..obs.datadog import metric_count, create_incident, create_case


class ChatIn(BaseModel):
    question: str
    limit: int = 120


class GameDayIn(BaseModel):
    scenario: str


def _parse_iso(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _p95(values: List[float]) -> Optional[float]:
    if not values:
        return None
    vs = sorted(values)
    idx = int(round(0.95 * (len(vs) - 1)))
    idx = max(0, min(idx, len(vs) - 1))
    return float(vs[idx])


def _fingerprint(text: str) -> str:
    t = (text or "").encode("utf-8", errors="ignore")
    return hashlib.sha1(t).hexdigest()[:10]


def build_app(
    cfg: Settings,
    bus: Bus,
    audit: AuditBuffer,
    producer: ClipProducer,
    gameday: GameDayController,
    state: RuntimeState,
    dispatcher: DispatcherTool,
) -> FastAPI:
    app = FastAPI(title="SentinelOps")

    @app.get("/ui", response_class=HTMLResponse)
    def ui():
        return ui_html()

    @app.get("/video")
    def video():
        return FileResponse(cfg.security_video_path, media_type="video/mp4")

    @app.get("/stream/status")
    def stream_status():
        return {"running": producer.running}

    @app.post("/stream/start")
    def stream_start():
        producer.start()
        return {"ok": True, "running": producer.running}

    @app.post("/stream/stop")
    def stream_stop():
        producer.stop()
        return {"ok": True, "running": producer.running}

    @app.get("/recent")
    def recent(limit: int = 200):
        return audit.recent(limit=limit)

    @app.get("/kpi")
    def kpi():
        return audit.kpi()

    @app.get("/gameday")
    def gameday_get():
        st = gameday.status()
        return {
            "enabled": st.enabled,
            "scenario": st.scenario,
            "since_ts": st.since_ts,
            "force": st.force,
            "dispatcher_down": dispatcher.simulated_down,
            "dispatcher_latency_ms": dispatcher.simulated_latency_ms,
        }

    @app.post("/gameday/run")
    def gameday_run(inp: GameDayIn):
        scenario = (inp.scenario or "none").strip()
        gameday.set_scenario(scenario)
        return {"ok": True, "scenario": gameday.status().scenario}

    @app.post("/gameday/reset")
    def gameday_reset():
        gameday.reset()
        return {"ok": True, "scenario": gameday.status().scenario}

    @app.get("/healthz")
    def healthz():
        items = audit.recent(limit=4000)

        totals = {
            "stage_timeout": 0,
            "tool_errors": 0,
            "llm_parse_fail": 0,
            "tokens": 0,
            "cost_usd": 0.0,
            "llm_calls": 0,
        }

        e2e_latencies: List[float] = []
        stage_lat_by_stage: Dict[str, List[float]] = {
            "observer": [], "thinker": [], "doer": [], "dispatcher": [], "producer": []
        }

        action_attempted = 0
        action_sent = 0

        llm_parse_ok = 0
        llm_calls = 0

        for ev in items:
            kind = ev.get("kind")
            payload = ev.get("payload") or {}

            if kind == "stage_timeout":
                totals["stage_timeout"] += 1

            if kind == "tool_error":
                totals["tool_errors"] += 1

            if kind == "health" and payload.get("event") == "llm_call":
                llm_calls += 1
                totals["llm_calls"] += 1

                parse_ok = bool(payload.get("parse_ok", True))
                if parse_ok:
                    llm_parse_ok += 1
                else:
                    totals["llm_parse_fail"] += 1

                totals["tokens"] += int(payload.get("total_tokens", 0) or 0)
                totals["cost_usd"] += float(payload.get("cost_usd", 0.0) or 0.0)

            if kind == "health" and payload.get("event") == "e2e_decision_latency":
                try:
                    e2e_latencies.append(float(payload.get("latency_ms", 0)))
                except Exception:
                    pass

            if kind == "stage" and payload.get("event") == "stage_end":
                stg = str(payload.get("stage", ""))
                if stg in stage_lat_by_stage:
                    try:
                        stage_lat_by_stage[stg].append(float(payload.get("latency_ms", 0)))
                    except Exception:
                        pass

            if kind == "action":
                status = str(payload.get("status", payload.get("payload", {}).get("status", ""))).lower()
                if status in {"sent", "failed"}:
                    action_attempted += 1
                    if status == "sent":
                        action_sent += 1

        decision_latency_p95 = _p95(e2e_latencies)
        action_success_rate = (action_sent / action_attempted) if action_attempted > 0 else 1.0
        llm_integrity_rate = (llm_parse_ok / llm_calls) if llm_calls > 0 else 1.0

        stage_p95 = {k: _p95(v) for k, v in stage_lat_by_stage.items()}

        pipeline = {
            "clips_in_queue": bus.qsize(bus.TOPIC_CLIPS) if hasattr(bus, "qsize") else 0,
            "obs_in_queue": bus.qsize(bus.TOPIC_OBSERVATIONS) if hasattr(bus, "qsize") else 0,
            "dec_in_queue": bus.qsize(bus.TOPIC_DECISIONS) if hasattr(bus, "qsize") else 0,
            "act_in_queue": bus.qsize(bus.TOPIC_ACTIONS) if hasattr(bus, "qsize") else 0,
        }

        st = gameday.status()

        return {
            "scenario": st.scenario,
            "pipeline": pipeline,
            "totals": totals,
            "slo": {
                "decision_latency_p95_ms": int(decision_latency_p95) if decision_latency_p95 is not None else None,
                "action_success_rate": round(float(action_success_rate), 3),
                "llm_integrity_rate": round(float(llm_integrity_rate), 3),
            },
            "stage_latency_p95_ms": {
                k: (int(v) if v is not None else None) for k, v in stage_p95.items()
            },
            "deps": {
                "dispatcher": {"down": dispatcher.simulated_down, "latency_ms": dispatcher.simulated_latency_ms},
            },
        }

    @app.post("/chat")
    def chat(inp: ChatIn):
        q = (inp.question or "").strip()
        if not q:
            return {"answer": "Ask a question.", "source": "none"}

        if gameday.active("injection") and cfg.gameday_force:
            inj = True
            hij = True
            inj_reason = "gameday_forced"
            hij_reason = "gameday_forced"
        else:
            inj_res = detect_injection(q)
            hij_res = detect_hijack(q)
            inj = inj_res.hit
            hij = hij_res.hit
            inj_reason = inj_res.reason
            hij_reason = hij_res.reason

        if inj or hij:
            kind = "prompt_injection" if inj else "action_hijack"
            reason = inj_reason if inj else hij_reason
            fp = _fingerprint(q[:200])

            audit.add("security", "chat", {
                "event": kind,
                "blocked": True,
                "reason": reason,
                "fingerprint": fp,
                "question_preview": q[:200],
                **gameday.tags(),
            })
            metric_count("sentinel.security.event", 1, {"type": kind, "fingerprint": fp, **gameday.tags()})

            create_case(
                title=f"SentinelOps Security Event: {kind}",
                description=(
                    f"Blocked prompt injection / action hijack.\n"
                    f"Reason={reason}\n"
                    f"Fingerprint={fp}\n"
                    f"Preview={q[:200]}\n"
                    f"Scenario={gameday.status().scenario}"
                ),
                tags={"signal": "security", "type": kind, "fingerprint": fp, **gameday.tags()},
                priority="HIGH",
            )

            create_incident(
                title=f"SentinelOps: Security block ({kind})",
                summary=f"Blocked attempt. fingerprint={fp} reason={reason}",
                severity="SEV-3",
                tags={"signal": "security", "type": kind, "fingerprint": fp, **gameday.tags()},
                metadata={"reason": reason, "fingerprint": fp, "preview": q[:200]},
            )

            return {
                "answer": "Blocked: detected prompt injection / action hijack attempt. A security event has been recorded.",
                "source": "security_guard",
            }

        ctx = audit.recent(limit=min(max(inp.limit, 10), 250))
        lines = []
        for ev in reversed(ctx[-60:]):
            kind = ev["kind"]
            trace = (ev["trace_id"] or "")[:8]
            desc = ""
            p = ev.get("payload") or {}
            if kind == "observation":
                desc = p.get("summary", "")
            elif kind == "decision":
                a0 = (p.get("recommended_actions") or [{}])[0]
                desc = a0.get("message", "") or (p.get("assessment", {}) or {}).get("rule_id", "")
            elif kind == "action":
                desc = (p.get("action") or {}).get("message", "") or (p.get("action") or {}).get("type", "")
            elif kind in {"tool_error", "stage_timeout", "security"}:
                desc = p.get("event", "") or p.get("error", "") or ""
            if desc:
                lines.append(f"{kind.upper()} trace={trace}: {desc}")

        prompt = (
            "You are SentinelOps. Answer using ONLY the audit log below.\n"
            "If the answer is not supported by the log, say 'I don't know from the audit log'.\n\n"
            "AUDIT LOG:\n" + "\n".join(lines) + "\n\n"
            f"QUESTION: {q}\n"
            "Answer in 1-5 sentences."
        )

        m = model_if_enabled(cfg, cfg.gemini_thinker_model)
        if m is None:
            return {"answer": "USE_GEMINI=false. Chat disabled in stub mode.", "source": "stub"}
        try:
            resp = m.generate_content([prompt], generation_config={"temperature": 0.2, "max_output_tokens": 600})
            audit.add("chat", "chat", {"event": "chat_answer", "q": q, "answer": resp.text, **gameday.tags()})
            return {"answer": (resp.text or "").strip(), "source": "gemini"}
        except Exception as e:
            return JSONResponse({"answer": f"Chat failed: {e}", "source": "error"}, status_code=500)

    return app